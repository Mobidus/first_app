--!nocheck
-- FAKE-ENGINE INTEGRATION: runs the real src/server/Main.server (and every service it wires) on
-- tests/_harness/FakeEngine. Proves orchestration, persistence and anti-duplication logic of the
-- engine-facing code. Does NOT prove physics, collisions, rendering, network or timing in Roblox.
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local FakeEngine = require("../_harness/FakeEngine")
local roblox = require("@lune/roblox")
local Config = Loader.require("src/shared/GeneratedConfig")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local V3, CF = roblox.Vector3, roblox.CFrame
local DS = "FillingUp_Profiles_TEST_v3/profile_"

local function boot()
	Loader.reset()
	local E = FakeEngine.new({ baseGame = Loader.game })
	Loader.setEngine(E.env)
	Loader.runScript("src/server/Main.server")
	return E
end

local function find(E, name, root)
	for _, d in (root or E.Workspace):GetDescendants() do
		if d.Name == name then
			return d
		end
	end
	return nil
end

local function roomModel(E, depth, slotX)
	for _, d in E.Workspace:GetDescendants() do
		if d.ClassName == "Model" and string.sub(d.Name, 1, 5) == "Room_" and d:GetAttribute("Depth") == depth then
			if slotX == nil then
				return d
			end
			local floor = find(E, "Floor", d)
			if floor and math.abs(floor.Position.X - slotX) < 1000 then
				return d
			end
		end
	end
	return nil
end

local function state(E, p)
	return E:lastState(p)
end

local function toExit(E, p, depth)
	local slotX = p.Character.PrimaryPart.Position.X
	local trig = find(E, "ExitTrigger", roomModel(E, depth, slotX))
	E:placeFeet(p, trig.Position - V3.new(0, 2, 0))
	E:step(0.6)
end

local function toDoor(E, p)
	local slotX = p.Character.PrimaryPart.Position.X
	for _, d in E.Workspace:GetDescendants() do
		if d.Name == "ContinueDoor" and math.abs(d.Position.X - slotX) < 1000 then
			E:placeFeet(p, d.Position - V3.new(0, 4, 0))
			E:step(0.6)
			return
		end
	end
	error("no ContinueDoor near the player")
end

local function climbLedge(E, p, depth)
	local slotX = p.Character.PrimaryPart.Position.X
	local ledge = find(E, "exit_ledge", roomModel(E, depth, slotX))
	E:placeFeet(p, ledge.Position + V3.new(0, ledge.Size.Y / 2, 0))
	E:step(0.6)
end

local function tutorial(E, p, buyRadar)
	E:step(1.5)
	local col = find(E, Config.Rooms.tutorial.falling_prop_id).PrimaryPart
	E:placeFeet(p, col.Position + V3.new(0, col.Size.Y / 2, 0))
	E:step(0.5)
	toExit(E, p, 0)
	if buyRadar then
		assert(E:invoke(p, "RequestCoinPurchase", "radar_pop", "buy-1").ok)
		assert(E:invoke(p, "RequestEquip", "radar_pop", "active", "eq-1").ok)
	end
	toDoor(E, p)
end

local function bury(E, p)
	local root = p.Character.PrimaryPart
	local made = {}
	for _, off in
		{
			V3.new(2.6, 0, 0),
			V3.new(-2.6, 0, 0),
			V3.new(0, 0, 2.6),
			V3.new(0, 0, -2.6),
			V3.new(2.6, 0, 2.6),
			V3.new(-2.6, 0, 2.6),
			V3.new(2.6, 0, -2.6),
			V3.new(-2.6, 0, -2.6),
			V3.new(0, 4, 0),
		}
	do
		local part = E.env.Instance.new("Part")
		part.Size = V3.new(2.6, if off.Y > 0 then 2 else 6, 2.6)
		part.Anchored = true
		part.CFrame = CF.new(root.Position + off)
		part.Parent = E.Workspace
		E.CollectionService:AddTag(part, "FillCollider")
		table.insert(made, part)
	end
	return made
end

local function doc(E, userId)
	return E.datastore[DS .. userId]
end

describe("Server flow on the fake engine (integration)", function()
	it("first session: tutorial 65, Radar 50 -> 15, used in room 1, exit pays band + discovery once", function()
		local E = boot()
		local p = E:addPlayer(1001)
		tutorial(E, p, true)
		local s = state(E, p)
		expect(s.phase).toBe("Active")
		expect(s.depth).toBe(1)
		expect(s.coins).toBe(15)
		local r = E:invoke(p, "RequestToolUse", "radar_pop", "", "tool-1")
		expect(r.ok).toBe(true)
		expect(r.charges).toBe(3)
		E:step(0.3)
		expect(doc(E, 1001).profile.checkpoint.chargesSnapshot.radar_pop).toBe(3)
		climbLedge(E, p, 1)
		expect(state(E, p).coins).toBe(15 + 30)
		toExit(E, p, 1)
		toExit(E, p, 1) -- standing in the exit again never pays twice
		s = state(E, p)
		expect(s.phase).toBe("Transitioning")
		expect(s.depth).toBe(2)
		expect(s.coins).toBe(15 + 150 + 50)
		expect(s.permits).toBe(1)
		expect(doc(E, 1001).profile.checkpoint.depth).toBe(2)
		expect(#E.warnings).toBe(0)
	end)

	it("30 room transitions: no Heartbeat/instance growth, <= 2 room models + sas resident", function()
		local E = boot()
		local p = E:addPlayer(1002)
		tutorial(E, p, false)
		local hbAfterFirst, folderAfterFirst
		for depth = 1, 30 do
			climbLedge(E, p, depth)
			toExit(E, p, depth)
			toDoor(E, p)
			if depth == 3 then
				hbAfterFirst = E:heartbeatConnections()
			end
			local rooms = 0
			for _, d in E.Workspace:GetDescendants() do
				if d.ClassName == "Model" and (string.sub(d.Name, 1, 5) == "Room_" or d.Name == "Sas") then
					rooms += 1
				end
			end
			expect(rooms).toBeAtMost(3)
		end
		expect(state(E, p).depth).toBe(31)
		expect(E:heartbeatConnections()).toBe(hbAfterFirst)
		expect(#E.warnings).toBe(0)
	end)

	it("burial KO keeps coins and permits, clears the run, free restart at depth 1", function()
		local E = boot()
		local p = E:addPlayer(1003)
		tutorial(E, p, false)
		climbLedge(E, p, 1)
		toExit(E, p, 1)
		toDoor(E, p)
		local before = state(E, p)
		E:step(3.5) -- spawn grace elapses
		local made = bury(E, p)
		E:step(2)
		local s = state(E, p)
		expect(s.phase).toBe("KO")
		expect(s.coins).toBe(before.coins)
		expect(s.permits).toBe(before.permits)
		expect(doc(E, 1003).profile.checkpoint).toBe(nil)
		for _, m in made do
			m:Destroy()
		end
		expect(E:invoke(p, "RequestRestart", "rs-1").ok).toBe(true)
		E:step(0.3)
		expect(state(E, p).phase).toBe("Active")
		expect(state(E, p).depth).toBe(1)
	end)

	it("no KO while standing under an open table (roof only)", function()
		local E = boot()
		local p = E:addPlayer(1004)
		tutorial(E, p, false)
		E:step(3.5)
		local root = p.Character.PrimaryPart
		local table_ = E.env.Instance.new("Part")
		table_.Size = V3.new(10, 1, 10)
		table_.Anchored = true
		table_.CFrame = CF.new(root.Position + V3.new(0, 3.2, 0))
		table_.Parent = E.Workspace
		E.CollectionService:AddTag(table_, "FillCollider")
		E:step(10)
		expect(state(E, p).phase).toBe("Active")
	end)

	it("disconnect mid-room then rejoin: same room, milestones not repaid, charges not refilled", function()
		local E = boot()
		local p = E:addPlayer(1005)
		tutorial(E, p, true)
		expect(E:invoke(p, "RequestToolUse", "radar_pop", "", "t1").ok).toBe(true)
		E:step(0.3)
		climbLedge(E, p, 1)
		local coins = state(E, p).coins
		E:removePlayer(p)
		E:step(0.5)
		expect(doc(E, 1005).lock).toBe(nil) -- released on leave
		local p2 = E:addPlayer(1005)
		E:step(1)
		local s = state(E, p2)
		expect(s.phase).toBe("Active")
		expect(s.depth).toBe(1)
		expect(s.charges.radar_pop).toBe(3)
		climbLedge(E, p2, 1)
		expect(state(E, p2).coins).toBe(coins)
	end)

	it("leaving while the profile loads releases the session lock", function()
		local E = boot()
		local p = E:addPlayer(1006)
		E:removePlayer(p) -- before the yielding UpdateAsync returned
		E:step(0.5)
		local d = doc(E, 1006)
		expect(d == nil or d.lock == nil).toBe(true)
	end)

	it("save outage at the exit: never announced as saved, no progression until the write succeeds", function()
		local E = boot()
		local p = E:addPlayer(1007)
		tutorial(E, p, false)
		climbLedge(E, p, 1)
		E.datastoreFail = true
		toExit(E, p, 1)
		local statuses = E:hud(p, "save_status")
		expect(statuses[#statuses].ok).toBe(false)
		toDoor(E, p)
		E:step(2)
		expect(state(E, p).phase).toBe("Transitioning") -- waiting safely in the sas
		E.datastoreFail = false
		E:step(2)
		local s = state(E, p)
		expect(s.phase).toBe("Active")
		expect(s.depth).toBe(2)
		expect(s.coins).toBe(65 + 150 + 50)
	end)

	it("voluntary rebirth in the sas keeps coins and tools, restarts at depth 1", function()
		local E = boot()
		-- seed a qualified profile in the test DataStore (tutorial done, 3 families, 400 permits)
		local Mut = Loader.require("src/shared/Domain/ProfileMutations")
		local prof = Mut.newProfile()
		prof.coins, prof.permits = 777, 400
		prof.tutorialFlags = { tutorial_discovery = true, tutorial_first_landing = true, tutorial_exit = true }
		prof.ownedTools.radar_pop, prof.toolRanks.radar_pop = true, 1
		prof.roomMastery = { totalCompleted = 9, families = { reception = 3, toy = 3, bureau = 3 }, firstRebirthQualified = true }
		E.datastore[DS .. 1008] = { profile = prof, lock = nil }
		local p = E:addPlayer(1008)
		E:step(1)
		expect(state(E, p).inSas).toBe(true)
		local prev = E:invoke(p, "RequestRebirthPreview", 2, "pv-1")
		expect(prev.ok).toBe(true)
		expect(prev.preview.cost).toBe(95)
		local res = E:invoke(p, "RequestRebirth", 2, prev.preview.revision, prev.preview.token, "rb-1")
		expect(res.ok).toBe(true)
		E:step(0.2)
		local s = state(E, p)
		expect(s.rebirthCount).toBe(2)
		expect(s.permits).toBe(305)
		expect(s.coins).toBe(777)
		expect(s.ownedTools.radar_pop).toBe(true)
		-- replaying the same confirmation is refused (revision moved on)
		expect(E:invoke(p, "RequestRebirth", 2, prev.preview.revision, prev.preview.token, "rb-2").ok).toBe(false)
		toDoor(E, p)
		expect(state(E, p).depth).toBe(1)
	end)

	it("two players: separate world slots, one player's burial never affects the other", function()
		local E = boot()
		local a = E:addPlayer(2001)
		local b = E:addPlayer(2002)
		tutorial(E, a, false)
		tutorial(E, b, false)
		expect(math.abs(a.Character.PrimaryPart.Position.X - b.Character.PrimaryPart.Position.X) > 1000).toBe(true)
		E:step(3.5)
		bury(E, a)
		E:step(2)
		expect(state(E, a).phase).toBe("KO")
		expect(state(E, b).phase).toBe("Active")
	end)

	it("forged client intents are rejected (unknown intent, client price, out-of-sas purchase)", function()
		local E = boot()
		local p = E:addPlayer(1009)
		tutorial(E, p, false)
		expect(E:invoke(p, "AddCoins", 500).ok).toBe(false)
		expect(E:invoke(p, "RequestCoinPurchase", "radar_pop", "x1", 0).ok).toBe(false)
		local r = E:invoke(p, "RequestCoinPurchase", "radar_pop", "x2")
		expect(r.ok).toBe(false)
		expect(r.error).toBe("shop_only_in_sas")
		expect(E:invoke(p, "RequestRobuxPurchase", "coins_800", "x3").ok).toBe(false)
	end)
end)

Loader.setEngine(nil)
Loader.reset()
return true
