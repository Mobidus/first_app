--!nocheck
-- V1 content sweep (T17): six families, formats S/M/L/V, six exits. Physical parameters must stay
-- bounded at any depth; Giant Bin is a recurring family, never a final room.
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local Certify = require("../_harness/Certify")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Plan = Loader.require("src/shared/Domain/RoomPlan")
local Difficulty = Loader.require("src/shared/Domain/Difficulty")
local Jump = Loader.require("src/shared/Domain/JumpModel")
local Config = Loader.require("src/shared/GeneratedConfig")

describe("Generation certification (V1 profile)", function()
	local report = Certify.certify("v1", "reports/room_certification_full.json")

	it("all V1 family/format/exit combinations build for every tested seed", function()
		expect(report.unbuildable).toBe(0)
		local n = 0
		for _ in report.combos do
			n += 1
		end
		expect(n).toBe(#Config.Rooms.release_profiles.v1.families * #Config.Rooms.release_profiles.v1.formats * 6)
	end)

	it("physical parameters are bounded at any depth (1 .. 1e6)", function()
		local b = Difficulty.bounds()
		for _, depth in { 1, 80, 81, 1000, 100000, 1000000 } do
			local band = Difficulty.bandForDepth(depth)
			expect(band.wave_interval_seconds).toBeAtLeast(b.minInterval)
			expect(band.maximum_required_gap_ratio).toBeAtMost(0.85)
			expect(band.physical_objects_per_wave).toBeAtMost(5)
		end
		expect(Difficulty.bandForDepth(1000000).id).toBe(Difficulty.bandForDepth(81).id)
	end)

	it("deep rooms never require a hop beyond the measured envelope", function()
		for i = 1, 60 do
			local depth = 80 + i * 997
			local spec = Plan.selectSpec(depth, i * 13, {}, "v1")
			local room = Plan.build(spec, depth, i * 101)
			for _, e in room.routeGraph.edges do
				if e.kind == "jump" then
					expect(e.rise).toBeAtMost(Jump.maxRequiredRise() + 1e-9)
				end
			end
		end
	end)

	it("Giant Bin recurs and is never flagged final; no last depth exists", function()
		local bins = 0
		local history = {}
		for depth = 11, 600 do
			local s = Plan.selectSpec(depth, 2024, history, "v1")
			table.insert(history, s)
			if s.family == "bin" then
				bins += 1
			end
		end
		expect(bins).toBeAtLeast(20)
		for _, r in Config.Rooms.first_rooms do
			expect(r.final_room == nil or r.final_room == false).toBe(true)
		end
		expect(Config.Rooms.mode.room_limit == nil).toBe(true)
	end)

	it("size and exit vary compatibly (every family offers every V1 exit and format)", function()
		for _, f in Config.Rooms.families do
			for _, ex in Config.Rooms.release_profiles.v1.exits do
				expect(table.find(f.exits, ex) ~= nil).toBe(true)
			end
		end
	end)

	it("low exits (tailgate / floor_hatch) require reaching the high lever first", function()
		local room = Plan.build({ family = "garage", format = "M", exit = "tailgate", allowedBehaviors = { "stable" } }, 20, 5)
		expect(room.leverId).toBe("lever")
		local gate = false
		for _, e in room.routeGraph.edges do
			if e.kind == "gate" and e.from == "lever" and e.to == room.exitTargetId then
				gate = true
			end
		end
		expect(gate).toBe(true)
	end)
end)

return true
