--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Tools = Loader.require("src/shared/Domain/ToolRules")
local Mut = Loader.require("src/shared/Domain/ProfileMutations")
local Plan = Loader.require("src/shared/Domain/RoomPlan")
local Config = Loader.require("src/shared/GeneratedConfig")

local function owner(toolIds, active, passive)
	local p = Mut.newProfile()
	for _, id in toolIds do
		p.ownedTools[id] = true
		p.toolRanks[id] = 1
	end
	p.equippedLoadout.active = active
	p.equippedLoadout.passive = passive
	return p
end

local function ctx(p, extra)
	local c = {
		profile = p,
		roomState = "Active",
		inSas = false,
		now = 100,
		player = { x = 0, y = 4, z = 0, vy = 0, grounded = true },
		target = nil,
	}
	for k, v in extra or {} do
		c[k] = v
	end
	return c
end

describe("ToolRules", function()
	it("radar: 4 charges per room, cooldown, refused use keeps the charge", function()
		local p = owner({ "radar_pop" }, "radar_pop")
		local st = Tools.enterRoom(Tools.newState(), p, "run:1", nil)
		expect(st.charges.radar_pop).toBe(4)
		local ok, eff = Tools.check(st, "radar_pop", ctx(p))
		expect(ok).toBe(true)
		st = Tools.commit(st, eff, 100)
		expect(st.charges.radar_pop).toBe(3)
		local ok2, why = Tools.check(st, "radar_pop", ctx(p, { now = 110 }))
		expect(ok2).toBe(false)
		expect(why).toBe("cooldown")
		expect(st.charges.radar_pop).toBe(3)
		expect((Tools.check(st, "radar_pop", ctx(p, { now = 120 })))).toBe(true)
	end)

	it("charges refill on a NEW room instance only (reload of the same room keeps them)", function()
		local p = owner({ "radar_pop" }, "radar_pop")
		local st = Tools.enterRoom(Tools.newState(), p, "run:5", nil)
		local _, eff = Tools.check(st, "radar_pop", ctx(p))
		st = Tools.commit(st, eff, 100)
		local same = Tools.enterRoom(st, p, "run:5", nil)
		expect(same.charges.radar_pop).toBe(3)
		local resumed = Tools.enterRoom(Tools.newState(), p, "run:5", { radar_pop = 3 })
		expect(resumed.charges.radar_pop).toBe(3)
		local nextRoom = Tools.enterRoom(st, p, "run:6", nil)
		expect(nextRoom.charges.radar_pop).toBe(4)
	end)

	it("not owned / not equipped / in sas / after KO are refused", function()
		local p = owner({ "radar_pop" }, nil)
		local st = Tools.enterRoom(Tools.newState(), p, "r:1", nil)
		expect(select(2, Tools.check(st, "radar_pop", ctx(p)))).toBe("not_equipped")
		p.equippedLoadout.active = "radar_pop"
		expect(select(2, Tools.check(st, "radar_pop", ctx(p, { inSas = true })))).toBe("not_in_active_room")
		expect(select(2, Tools.check(st, "radar_pop", ctx(p, { roomState = "KO" })))).toBe("not_in_active_room")
		local q = owner({}, nil)
		expect(select(2, Tools.check(st, "radar_pop", ctx(q)))).toBe("not_owned")
	end)

	it("radar highlights at most 3 usable surfaces in range, nearest first", function()
		local stats = Config.Economy.tools[1].ranks[1].stats
		local cands = {}
		for i = 1, 10 do
			table.insert(cands, { id = "s" .. i, x = i * 3, y = 0, z = 0, usable = i ~= 2, buried = i == 3 })
		end
		local out = Tools.radarTargets({ x = 0, y = 0, z = 0 }, cands, stats)
		expect(#out).toBe(3)
		expect(out[1]).toBe("s1")
		expect(out[2]).toBe("s4")
	end)

	it("ventouse: eligible small target in range only; never exit, structure or route support", function()
		local p = owner({ "ventouse_chantier" }, "ventouse_chantier")
		local st = Tools.enterRoom(Tools.newState(), p, "r:1", nil)
		local good = { id = "o1", x = 5, y = 4, z = 0, stabilizable = true, sizeClass = 2 }
		expect((Tools.check(st, "ventouse_chantier", ctx(p, { target = good })))).toBe(true)
		for _, bad in
			{
				{ id = "x", x = 5, y = 4, z = 0, stabilizable = true, sizeClass = 3 },
				{ id = "x", x = 5, y = 4, z = 0, stabilizable = true, sizeClass = 1, isExit = true },
				{ id = "x", x = 5, y = 4, z = 0, stabilizable = true, sizeClass = 1, structural = true },
				{ id = "x", x = 5, y = 4, z = 0, stabilizable = true, sizeClass = 1, protectedRoute = true },
				{ id = "x", x = 50, y = 4, z = 0, stabilizable = true, sizeClass = 1 },
				{ id = "x", x = 5, y = 4, z = 0, stabilizable = false, sizeClass = 1 },
			}
		do
			expect((Tools.check(st, "ventouse_chantier", ctx(p, { target = bad })))).toBe(false)
		end
	end)

	it("umbrella only while descending; never upward", function()
		local p = owner({ "parapluie_bonbon" }, "parapluie_bonbon")
		local st = Tools.enterRoom(Tools.newState(), p, "r:1", nil)
		expect((Tools.check(st, "parapluie_bonbon", ctx(p)))).toBe(false)
		local ok, eff = Tools.check(st, "parapluie_bonbon", ctx(p, { player = { x = 0, y = 10, z = 0, vy = -30, grounded = false } }))
		expect(ok).toBe(true)
		expect(eff.descentMultiplier).toBe(0.6)
	end)

	it("magnet attracts existing unclaimed tokens only, max 6, never creates any", function()
		local p = owner({ "aimant_poche" }, nil, "aimant_poche")
		local tokens = {}
		for i = 1, 6 do
			table.insert(tokens, { id = i, x = i, y = 0, z = 0 })
		end
		local pulled = Tools.magnetPull(p, { x = 0, y = 0, z = 0 }, tokens, bit32.lshift(1, 4), 4)
		expect(table.find(pulled, 1)).toBe(nil) -- token 1 already claimed
		expect(#pulled).toBe(4) -- range 5 => tokens 2..5
		expect((Tools.check(Tools.newState(), "aimant_poche", ctx(p)))).toBe(false) -- passive
	end)

	it("one active + one passive at most; companion gives no power", function()
		expect(Tools.MAX_POWERS).toBe(2)
		local p = owner({ "radar_pop", "aimant_poche" }, "radar_pop", "aimant_poche")
		p.equippedLoadout.companion = "compagnon_bob_papier"
		expect(Tools.loadoutPowers(p)).toBe(2)
	end)

	it("every main route stays feasible with NO tool (validator has no tool input)", function()
		for depth = 1, 30 do
			local room = Plan.build(Plan.selectSpec(depth, 31, {}), depth, 31)
			expect(room ~= nil).toBe(true)
			for _, n in room.routeGraph.nodes do
				expect(n.requiresTool == nil).toBe(true)
			end
		end
	end)
end)

return true
