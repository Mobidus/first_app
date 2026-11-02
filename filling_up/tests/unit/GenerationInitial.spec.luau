--!nocheck
-- Certification sweep for the MVP release profile (T16). Seeds that fail are kept in the report
-- as reproducible regressions; the build never presents an unvalidated room.
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local serde = require("@lune/serde")
local fs = require("@lune/fs")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Plan = Loader.require("src/shared/Domain/RoomPlan")
local V = Loader.require("src/shared/Domain/RouteValidator")
local Config = Loader.require("src/shared/GeneratedConfig")

local Certify = require("../_harness/Certify")
local SEEDS_PER_COMBO = Certify.SEEDS_PER_COMBO
local certify = Certify.certify

describe("Generation certification (MVP)", function()
	local report = certify("mvp", "reports/room_certification_initial.json")

	it("every MVP family/format/exit combination is buildable for every tested seed", function()
		expect(report.unbuildable).toBe(0)
		expect(report.total).toBeAtLeast(SEEDS_PER_COMBO * 20)
	end)

	it("primary generator succeeds for the large majority of seeds (fallback is the exception)", function()
		expect(report.primary_ok / report.total).toBeAtLeast(0.9)
	end)

	it("generation is deterministic for a seed", function()
		local spec = { family = "toy", format = "M", exit = "roof", allowedBehaviors = { "stable", "bounce" } }
		local a = Plan.build(spec, 4, 99)
		local b = Plan.build(spec, 4, 99)
		expect(serde.encode("json", a)).toBe(serde.encode("json", b))
	end)

	it("first ten rooms follow the pedagogical table with MVP substitutions", function()
		local expected = {
			{ "reception", "S", "door" },
			{ "reception", "XL", "window" },
			{ "toy", "S", "door" },
			{ "toy", "XL", "roof" },
			{ "bureau", "S", "door" },
			{ "reception", "XV", "window" },
			{ "bureau", "XL", "window" },
			{ "toy", "S", "window" },
			{ "bureau", "XL", "door" },
			{ "toy", "XV", "window" },
		}
		for depth, e in expected do
			local s = Plan.selectSpec(depth, 1, {})
			expect(s.family).toBe(e[1])
			expect(s.format).toBe(e[2])
			expect(s.exit).toBe(e[3])
		end
		expect(Plan.selectSpec(9, 1, {}).propVariant.variant).toBe("lift")
	end)

	it("room 1 hosts Mallow as a guest support arriving with the first structural wave", function()
		local room = Plan.build(Plan.selectSpec(1, 5, {}), 1, 5)
		local found = false
		for _, n in room.routeGraph.nodes do
			if n.topProp == "toy_plush_mallow" then
				found = true
				expect(n.arrival).toBe("wave1")
			end
		end
		expect(found).toBe(true)
	end)

	it("mechanisms are introduced gradually: room 1-2 only stable props", function()
		for depth = 1, 2 do
			local room = Plan.build(Plan.selectSpec(depth, 3, {}), depth, 3)
			for _, n in room.routeGraph.nodes do
				expect(n.behavior).toBe("stable")
			end
		end
	end)

	it("never more than two identical family/format/exit in a row after depth 10", function()
		local history = {}
		for depth = 1, 400 do
			local s = Plan.selectSpec(depth, 777, history)
			table.insert(history, s)
		end
		for i = 13, #history do
			local a, b, c = history[i - 2], history[i - 1], history[i]
			local same = a.family == b.family
				and b.family == c.family
				and a.format == b.format
				and b.format == c.format
				and a.exit == b.exit
				and b.exit == c.exit
			expect(same).toBe(false)
		end
	end)

	it("Giant Bin / V1 families are not selected under the MVP profile", function()
		for depth = 11, 200 do
			local s = Plan.selectSpec(depth, 42, {})
			expect(table.find({ "reception", "toy", "bureau" }, s.family) ~= nil).toBe(true)
		end
	end)
end)

return true
