--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local C = Loader.require("src/shared/Domain/Consolidation")

local function objs(nDyn, nStat, opts)
	opts = opts or {}
	local list = {}
	for i = 1, nDyn do
		table.insert(list, {
			id = "d" .. i,
			dynamic = true,
			settledFor = opts.settled or 2,
			occupied = opts.occupiedDyn == i,
			routeSupport = false,
			buried = false,
			age = i,
		})
	end
	for i = 1, nStat do
		table.insert(list, {
			id = "s" .. i,
			dynamic = false,
			settledFor = 10,
			occupied = opts.occupiedStat == i,
			routeSupport = (opts.route or 0) >= i,
			buried = (opts.buried or 0) >= i,
			age = 100 + i,
		})
	end
	return list
end

describe("Consolidation", function()
	it("keeps dynamic bodies <= 40 by anchoring settled ones", function()
		local plan = C.plan(objs(45, 0, { settled = 1 }))
		expect(45 - #plan.anchor).toBeAtMost(40)
	end)

	it("never anchors an occupied body (player standing on it)", function()
		local plan = C.plan(objs(45, 0, { settled = 1, occupiedDyn = 45 }))
		expect(table.find(plan.anchor, "d45")).toBe(nil)
	end)

	it("unsettled bodies are not frozen; new drops are deferred instead", function()
		local plan = C.plan(objs(40, 0, { settled = 0 }))
		expect(#plan.anchor).toBe(0)
		expect(plan.spawnAllowance).toBe(0)
	end)

	it("static budget: merges only buried, non-occupied, non-route colliders", function()
		local plan = C.plan(objs(0, 130, { buried = 30, route = 5, occupiedStat = 7 }))
		for _, id in plan.merge do
			local n = tonumber(string.sub(id, 2))
			expect(n > 5 and n ~= 7 and n <= 30).toBe(true)
		end
		expect(#plan.merge).toBeAtLeast(2)
	end)

	it("when nothing is safely reclaimable, accessible supports are kept and drops deferred", function()
		local plan = C.plan(objs(0, 125, { buried = 0 }))
		expect(#plan.merge + #plan.recycle).toBe(0)
		expect(plan.spawnAllowance).toBe(0)
	end)
end)

return true
