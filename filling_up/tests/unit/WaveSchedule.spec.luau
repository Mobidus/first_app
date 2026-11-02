--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Plan = Loader.require("src/shared/Domain/RoomPlan")
local Wave = Loader.require("src/shared/Domain/WaveSchedule")
local Box = Loader.require("src/shared/Util/Box")
local Config = Loader.require("src/shared/GeneratedConfig")

local function roomAt(depth, seed)
	local spec = Plan.selectSpec(depth, seed, {})
	local room = Plan.build(spec, depth, seed)
	return room, Plan.FAMILIES[room.familyId]
end

describe("WaveSchedule", function()
	it("waves are continuous in time: there is no last wave", function()
		local room, fam = roomAt(3, 11)
		local s = Wave.new(room, fam, 3)
		local w1 = Wave.at(s, 1)
		local w10000 = Wave.at(s, 10000)
		expect(w10000.impactTime > w1.impactTime).toBe(true)
		expect(Wave.countUntil(s, 18000)).toBeAtLeast(1000)
	end)

	it("every wave is announced before its impact (warning >= band warning)", function()
		for _, depth in { 1, 5, 15, 30, 60, 500 } do
			local room, fam = roomAt(depth, depth)
			local s = Wave.new(room, fam, depth)
			for i = 1, 50 do
				local w = Wave.at(s, i)
				expect(w.impactTime - w.warningTime).toBeNear(s.band.warning_seconds, 1e-9)
				expect(w.warningTime).toBeAtLeast(Config.Runtime.safety.spawn_invulnerability_seconds - 1e-9)
			end
		end
	end)

	it("cadence uses simulation seconds and the band interval", function()
		local room, fam = roomAt(25, 2)
		local s = Wave.new(room, fam, 25)
		expect(Wave.impactTime(s, 2) - Wave.impactTime(s, 1)).toBe(8)
		expect(Wave.countUntil(s, Wave.impactTime(s, 7))).toBe(7)
		expect(Wave.countUntil(s, Wave.impactTime(s, 7) - 0.001)).toBe(6)
	end)

	it("mouths alternate and drops stay inside mouth footprints (never over exit clearance)", function()
		local room, fam = roomAt(30, 9)
		local s = Wave.new(room, fam, 30)
		local seenMouths = {}
		for i = 1, 60 do
			local w = Wave.at(s, i)
			seenMouths[w.mouthIndex] = true
			for _, dr in w.drops do
				if not dr.structural then
					local m = room.waveMouths[w.mouthIndex]
					expect(math.abs(dr.x - m.cx) <= m.sx / 2 + 1e-6).toBe(true)
					expect(math.abs(dr.z - m.cz) <= m.sz / 2 + 1e-6).toBe(true)
					local p = Plan.PROPS[dr.propId]
					local fp = Box.new(dr.x, 0, dr.z, p.collider.size_studs[1], 1, p.collider.size_studs[2])
					expect(Box.overlapsXZ(fp, room.exitClearance)).toBe(false)
				end
			end
		end
		local n = 0
		for _ in seenMouths do
			n += 1
		end
		expect(n).toBe(math.min(s.band.mouths, #room.waveMouths))
	end)

	it("objects per wave follow the band and the structural guest replaces one drop", function()
		local room, fam = roomAt(1, 5)
		local s = Wave.new(room, fam, 1)
		local w1 = Wave.at(s, 1)
		expect(#w1.drops).toBe(s.band.physical_objects_per_wave)
		local structural = 0
		for _, dr in w1.drops do
			if dr.structural then
				structural += 1
				expect(dr.propId).toBe("toy_plush_mallow")
			end
		end
		expect(structural).toBe(1)
		expect(#Wave.at(s, 2).drops).toBe(s.band.physical_objects_per_wave)
	end)

	it("schedule is deterministic for a seed", function()
		local room, fam = roomAt(12, 77)
		local a = Wave.at(Wave.new(room, fam, 12), 33)
		local b = Wave.at(Wave.new(room, fam, 12), 33)
		expect(Spec.deepEqual(a, b)).toBe(true)
	end)
end)

return true
