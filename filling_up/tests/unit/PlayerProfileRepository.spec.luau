--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Repo = Loader.require("src/server/Services/PlayerProfileRepository")

local clock = 0
local function now()
	return clock
end

describe("PlayerProfileRepository (MemoryStore)", function()
	it("loads a new profile and takes the session lock", function()
		local store = Repo.MemoryStore.new()
		local r = Repo.new({ store = store, jobId = "job-A", now = now })
		local ok, p = r:load("u1")
		expect(ok).toBe(true)
		expect(p.coins).toBe(0)
		expect(store.data.profile_u1.lock.jobId).toBe("job-A")
	end)

	it("a second server cannot own a locked profile", function()
		local store = Repo.MemoryStore.new()
		local a = Repo.new({ store = store, jobId = "job-A", now = now })
		local b = Repo.new({ store = store, jobId = "job-B", now = now })
		expect((a:load("u1"))).toBe(true)
		local ok, why = b:load("u1")
		expect(ok).toBe(false)
		expect(why).toBe("session_locked")
		expect(a:release("u1")).toBe(true)
		expect((b:load("u1"))).toBe(true)
	end)

	it("stale lock (crashed server) can be taken over after timeout", function()
		local store = Repo.MemoryStore.new()
		local a = Repo.new({ store = store, jobId = "job-A", now = now, lockTimeoutSeconds = 100 })
		a:load("u2")
		clock += 101
		local b = Repo.new({ store = store, jobId = "job-B", now = now, lockTimeoutSeconds = 100 })
		expect((b:load("u2"))).toBe(true)
		-- the old server then fails to write instead of overwriting (no split brain)
		local ok, why = a:mutate("u2", { type = "GrantTutorial", rewardId = "tutorial_discovery" })
		expect(ok).toBe(false)
		expect(why).toBe("session_conflict")
	end)

	it("purchase debit and ownership are committed together after a durable write", function()
		local store = Repo.MemoryStore.new()
		local r = Repo.new({ store = store, jobId = "J", now = now })
		r:load("u3")
		for _, id in { "tutorial_discovery", "tutorial_first_landing", "tutorial_exit" } do
			assert((r:mutate("u3", { type = "GrantTutorial", rewardId = id })))
		end
		local ok, p = r:mutate("u3", { type = "CoinPurchase", skuId = "radar_pop" })
		expect(ok).toBe(true)
		expect(p.coins).toBe(15)
		expect(store.data.profile_u3.profile.coins).toBe(15)
		expect(store.data.profile_u3.profile.ownedTools.radar_pop).toBe(true)
	end)

	it("failed save is reported as failure and leaves the committed profile untouched", function()
		local store = Repo.MemoryStore.new()
		local r = Repo.new({ store = store, jobId = "J", now = now })
		r:load("u4")
		r:mutate("u4", { type = "GrantTutorial", rewardId = "tutorial_exit" })
		store.failNext = 1
		local ok, why = r:mutate("u4", { type = "GrantTutorial", rewardId = "tutorial_discovery" })
		expect(ok).toBe(false)
		expect(why).toBe("save_failed")
		expect(r:get("u4").coins).toBe(50)
		expect(r:get("u4").tutorialFlags.tutorial_discovery).toBe(nil)
		-- retry succeeds and pays exactly once
		local ok2, p2 = r:mutate("u4", { type = "GrantTutorial", rewardId = "tutorial_discovery" })
		expect(ok2).toBe(true)
		expect(p2.coins).toBe(60)
	end)

	it("store outage blocks new mutations (nothing committed in memory)", function()
		local store = Repo.MemoryStore.new()
		local r = Repo.new({ store = store, jobId = "J", now = now })
		r:load("u5")
		store.failAll = true
		for _ = 1, 5 do
			expect((r:mutate("u5", { type = "GrantTutorial", rewardId = "tutorial_exit" }))).toBe(false)
		end
		expect(r:get("u5").coins).toBe(0)
	end)

	it("reload after release returns the persisted profile (coins kept after KO/reconnect)", function()
		local store = Repo.MemoryStore.new()
		local r = Repo.new({ store = store, jobId = "J", now = now })
		r:load("u6")
		r:mutate("u6", { type = "GrantTutorial", rewardId = "tutorial_exit" })
		r:release("u6")
		local r2 = Repo.new({ store = store, jobId = "K", now = now })
		local _, p = r2:load("u6")
		expect(p.coins).toBe(50)
		expect((r2:mutate("u6", { type = "GrantTutorial", rewardId = "tutorial_exit" }))).toBe(false)
	end)

	it("yielding store: concurrent claims built from the same stale mask pay once", function()
		local task = require("@lune/task")
		local inner = Repo.MemoryStore.new()
		local yielding = {
			update = function(_, key, fn)
				task.wait(0.01) -- like UpdateAsync: the caller yields, other requests can be issued
				return inner:update(key, fn)
			end,
		}
		local r = Repo.new({ store = yielding, jobId = "J", now = now })
		r:load("race")
		local results = {}
		for i = 1, 5 do
			task.spawn(function()
				-- every request is built from the stale mask 0, as a 10 Hz loop would do
				results[i] = (
					r:mutate(
						"race",
						{ type = "GrantProgress", runId = "run", depth = 1, index = 1, mask = 0, rateBp = 0, paidBaseCumulative = 0 }
					)
				)
			end)
		end
		task.wait(0.5)
		local granted = 0
		for i = 1, 5 do
			if results[i] then
				granted += 1
			end
		end
		expect(granted).toBe(1)
		expect(r:get("race").coins).toBe(10)
	end)

	it("serializes many queued mutations without lost updates", function()
		local store = Repo.MemoryStore.new()
		local r = Repo.new({ store = store, jobId = "J", now = now })
		r:load("u7")
		for i = 1, 50 do
			r:mutate("u7", { type = "GrantReceipt", receiptId = "p" .. i, coins = 10 })
		end
		expect(r:get("u7").coins).toBe(500)
		expect(r:get("u7").revision).toBe(50)
	end)
end)

return true
