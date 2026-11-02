--!nocheck
-- Fun intruders and the inflatable pool family (decision 0020).
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Plan = Loader.require("src/shared/Domain/RoomPlan")
local Wave = Loader.require("src/shared/Domain/WaveSchedule")
local V = Loader.require("src/shared/Domain/RouteValidator")
local Config = Loader.require("src/shared/GeneratedConfig")

local function isIntruder(id)
	return table.find(Config.Rooms.fun_intruders.prop_ids, id) ~= nil
end

describe("Fun intruders", function()
	it("serious families (reception, bureau, garage, bin) drop ONLY fun objects; their props stay as supports", function()
		for _, famId in Config.Rooms.fun_intruders.fun_only_families do
			local depth = math.max(12, Plan.FAMILIES[famId].minimum_depth)
			local room = Plan.build({ family = famId, format = "M", exit = "door", allowedBehaviors = { "stable" } }, depth, 3)
			local s = Wave.new(room, Plan.FAMILIES[famId], depth)
			for i = 1, 60 do
				for _, dr in Wave.at(s, i).drops do
					if not dr.structural then
						expect(isIntruder(dr.propId)).toBe(true)
					end
				end
			end
			-- the family's own (serious) props are still used as route supports
			local own = 0
			for _, n in room.routeGraph.nodes do
				if n.topProp and string.sub(n.topProp, 1, #famId) == famId then
					own += 1
				end
			end
			expect(own).toBeAtLeast(1)
		end
	end)

	it("mixed families (kitchen): about the configured share of drops are fun intruders; toy and pool keep their own", function()
		local room = Plan.build({ family = "kitchen", format = "M", exit = "door", allowedBehaviors = { "stable" } }, 12, 3)
		local s = Wave.new(room, Plan.FAMILIES.kitchen, 12)
		local fun, total = 0, 0
		for i = 1, 400 do
			for _, dr in Wave.at(s, i).drops do
				if not dr.structural then
					total += 1
					if isIntruder(dr.propId) then
						fun += 1
					end
				end
			end
		end
		local share = Config.Rooms.fun_intruders.share
		expect(fun / total > share - 0.06).toBe(true)
		expect(fun / total < share + 0.06).toBe(true)
		for _, famId in { "pool", "toy" } do
			local r2 = Plan.build({ family = famId, format = "M", exit = "door", allowedBehaviors = { "stable" } }, 12, 3)
			local ps = Wave.new(r2, Plan.FAMILIES[famId], 12)
			expect(#ps.intruders).toBe(0)
			expect(ps.funOnly).toBe(false)
		end
	end)

	it("intruders appear from room 1 and respect their unlock depth", function()
		local list = Wave.intrudersFor("kitchen", 1, "S")
		local ids = {}
		for _, p in list do
			ids[p.id] = true
		end
		expect(ids.pool_inflatable_duck).toBe(true)
		expect(ids.toy_flat_duck == nil).toBe(true) -- stage 3
		expect(#Wave.intrudersFor("kitchen", 3, "S") > #list).toBe(true)
		-- large plushes only fall in big formats
		local function has(l, id)
			for _, p in l do
				if p.id == id then
					return true
				end
			end
			return false
		end
		expect(has(Wave.intrudersFor("bureau", 20, "S"), "toy_plush_balto")).toBe(false)
		expect(has(Wave.intrudersFor("bureau", 20, "XL"), "toy_plush_balto")).toBe(true)
	end)

	it("drop positions are unchanged by the intruder swap (separate random stream)", function()
		local room = Plan.build({ family = "kitchen", format = "XL", exit = "window", allowedBehaviors = { "stable" } }, 20, 9)
		local a = Wave.new(room, Plan.FAMILIES.kitchen, 20)
		local b = Wave.new(room, Plan.FAMILIES.kitchen, 20)
		b.intruders = {}
		for i = 1, 30 do
			local wa, wb = Wave.at(a, i), Wave.at(b, i)
			expect(#wa.drops).toBe(#wb.drops)
			for k, dr in wa.drops do
				-- same draw sequence: a drop that was not swapped is identical
				if dr.propId == wb.drops[k].propId then
					expect(dr.x).toBe(wb.drops[k].x)
					expect(dr.z).toBe(wb.drops[k].z)
				end
			end
		end
	end)

	it("duck line: 5 forms, 15 droppable variants with accessories, the giant captain never falls", function()
		local forms, droppable = {}, 0
		for _, p in Plan.FAMILIES.pool.props do
			if p.duck_form then
				forms[p.duck_form] = (forms[p.duck_form] or 0) + 1
				if p.wave_drop ~= false then
					droppable += 1
					expect(isIntruder(p.id)).toBe(true)
				end
				if
					p.duck_form ~= "mini" and p.duck_form ~= "lilo"
					or p.id ~= "pool_duck_mini_classic" and p.id ~= "pool_duck_lilo_classic"
				then
					expect(#p.accessories >= 1 or p.id == "pool_duck_mini_classic" or p.id == "pool_duck_lilo_classic").toBe(true)
				end
			end
		end
		expect(forms.mini).toBe(4)
		expect(forms.medium).toBe(5)
		expect(forms.lilo).toBe(2)
		expect(forms.large_ring).toBe(3)
		expect(forms.giant).toBe(1)
		expect(droppable).toBe(14)
		expect(Plan.PROPS.pool_duck_captain.wave_drop).toBe(false)
		-- an office XL room at depth 20 can drop ducks of every droppable form
		local seen = {}
		local room = Plan.build({ family = "bureau", format = "XL", exit = "window", allowedBehaviors = { "stable" } }, 20, 4)
		local s = Wave.new(room, Plan.FAMILIES.bureau, 20)
		for i = 1, 300 do
			for _, dr in Wave.at(s, i).drops do
				local p = Plan.PROPS[dr.propId]
				if p.duck_form then
					seen[p.duck_form] = true
				end
				expect(dr.propId ~= "pool_duck_captain").toBe(true)
			end
		end
		expect(seen.mini and seen.medium and seen.lilo and seen.large_ring).toBe(true)
	end)

	it("the pool family builds valid rooms in every format with every exit", function()
		for _, format in Config.Rooms.release_profiles.v1.formats do
			for _, exit in Plan.FAMILIES.pool.exits do
				local room = Plan.build(
					{ family = "pool", format = format, exit = exit, allowedBehaviors = { "stable", "bounce", "moving", "temporary" } },
					20,
					77
				)
				expect(room ~= nil).toBe(true)
				expect((V.validate(room, { gapRatio = room.gapRatio }))).toBe(true)
			end
		end
	end)
end)

return true
