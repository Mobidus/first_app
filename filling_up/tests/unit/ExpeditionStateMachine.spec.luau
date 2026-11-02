--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local fs = require("@lune/fs")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local M = Loader.require("src/shared/Domain/ExpeditionStateMachine")

local function active()
	local s = M.create({ runId = "run-1", seed = 42 })
	local ok
	ok, s = M.apply(s, { type = "RoomReady", roomId = "room-1" })
	assert(ok)
	return s
end

describe("ExpeditionStateMachine", function()
	it("starts Preparing at depth 1 and becomes Active on RoomReady", function()
		local s = M.create({ runId = "r", seed = 1 })
		expect(s.state).toBe("Preparing")
		expect(s.depth).toBe(1)
		local ok, s2 = M.apply(s, { type = "RoomReady", roomId = "a" })
		expect(ok).toBe(true)
		expect(s2.state).toBe("Active")
		expect(s.state).toBe("Preparing") -- input not mutated
	end)

	it("double exit increments depth exactly once", function()
		local s = active()
		local ok1, s1 = M.apply(s, { type = "ExitReached", roomId = "room-1", depth = 1 })
		expect(ok1).toBe(true)
		expect(s1.depth).toBe(2)
		expect(s1.lastCommittedDepth).toBe(1)
		local ok2, err = M.apply(s1, { type = "ExitReached", roomId = "room-1", depth = 1 })
		expect(ok2).toBe(false)
		expect(err).toBe("duplicate_exit")
		-- replaying the same event on the old state object (client spam) yields the same single increment
		local ok3, s3 = M.apply(s, { type = "ExitReached", roomId = "room-1", depth = 1 })
		expect(ok3).toBe(true)
		expect(s3.depth).toBe(2)
	end)

	it("stale exit (other room / depth) is rejected", function()
		local s = active()
		local ok, err = M.apply(s, { type = "ExitReached", roomId = "other", depth = 1 })
		expect(ok).toBe(false)
		expect(err).toBe("stale_exit")
	end)

	it("resumed run cannot re-commit an already committed depth", function()
		local s = M.create({ runId = "r", seed = 1, depth = 3, lastCommittedDepth = 3 })
		local _, a = M.apply(s, { type = "RoomReady", roomId = "x" })
		local ok, err = M.apply(a, { type = "ExitReached", roomId = "x", depth = 3 })
		expect(ok).toBe(false)
		expect(err).toBe("already_committed")
	end)

	it("rejects KO causes based on time or global fill", function()
		local s = active()
		for _, cause in { "room_timeout", "fill_100", "elapsed_time", "fill_percent" } do
			local ok, err = M.apply(s, { type = "KOConfirmed", cause = cause })
			expect(ok).toBe(false)
			expect(err).toBe("ko_cause_not_allowed")
		end
		local ok, ko = M.apply(s, { type = "KOConfirmed", cause = "confirmed_burial" })
		expect(ok).toBe(true)
		expect(ko.state).toBe("KO")
		expect(M.isTerminal(ko)).toBe(true)
	end)

	it("KO during transition (sas) is impossible", function()
		local s = active()
		local _, t = M.apply(s, { type = "ExitReached", roomId = "room-1", depth = 1 })
		local ok, err = M.apply(t, { type = "KOConfirmed", cause = "confirmed_burial" })
		expect(ok).toBe(false)
		expect(err).toBe("ko_outside_active_room")
	end)

	it("KO is terminal: nothing can follow it", function()
		local s = active()
		local _, ko = M.apply(s, { type = "KOConfirmed", cause = "marked_kill_volume" })
		for _, ev in { { type = "RoomReady", roomId = "z" }, { type = "Resume" }, { type = "Suspend" }, { type = "Extract", inSas = true } } do
			local ok = M.apply(ko, ev)
			expect(ok).toBe(false)
		end
	end)

	it("transition -> next room resets the room reward mask and wave index", function()
		local s = active()
		s.roomRewardMask = 7
		local _, t = M.apply(s, { type = "ExitReached", roomId = "room-1", depth = 1 })
		local ok, n = M.apply(t, { type = "NextRoomActive", roomId = "room-2" })
		expect(ok).toBe(true)
		expect(n.roomRewardMask).toBe(0)
		expect(n.roomId).toBe("room-2")
		expect(n.state).toBe("Active")
	end)

	it("suspend and resume returns to Preparing with resumed flag", function()
		local s = active()
		local _, sus = M.apply(s, { type = "Suspend", checkpointRevision = 9 })
		expect(sus.state).toBe("Suspended")
		local _, prep = M.apply(sus, { type = "Resume" })
		expect(prep.state).toBe("Preparing")
		expect(prep.resumed).toBe(true)
		expect(prep.checkpointRevision).toBe(9)
	end)

	it("extraction is only possible in the sas", function()
		local s = active()
		expect((M.apply(s, { type = "Extract", inSas = true }))).toBe(false)
		local _, t = M.apply(s, { type = "ExitReached", roomId = "room-1", depth = 1 })
		expect((M.apply(t, { type = "Extract", inSas = false }))).toBe(false)
		local ok, x = M.apply(t, { type = "Extract", inSas = true })
		expect(ok).toBe(true)
		expect(x.state).toBe("Extracted")
	end)

	it("wave index is monotonic", function()
		local s = active()
		local ok, w = M.apply(s, { type = "WaveAdvanced", waveIndex = 1 })
		expect(ok).toBe(true)
		expect((M.apply(w, { type = "WaveAdvanced", waveIndex = 1 }))).toBe(false)
	end)

	it("no expedition depth cap: 10 000 transitions keep incrementing", function()
		local s = active()
		for i = 1, 10000 do
			local ok
			ok, s = M.apply(s, { type = "ExitReached", roomId = s.roomId, depth = s.depth })
			assert(ok, "exit " .. i)
			ok, s = M.apply(s, { type = "NextRoomActive", roomId = "room-" .. (i + 1) })
			assert(ok)
		end
		expect(s.depth).toBe(10001)
		expect(s.state).toBe("Active")
	end)

	it("source of the machine contains no timer or fill-percentage KO path", function()
		local src = fs.readFile("src/shared/Domain/ExpeditionStateMachine.luau")
		local code = string.gsub(src, "%-%-[^\n]*", "") -- strip comments
		for _, forbidden in { "elapsed", "fillPercent", "fill_percent", "roomLimit", "roomDuration", "os.clock", "tick%(" } do
			expect(string.find(code, forbidden) == nil).toBe(true)
		end
	end)
end)

return true
