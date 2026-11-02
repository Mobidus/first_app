--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local fs = require("@lune/fs")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Pose = Loader.require("src/shared/Domain/PlushPose")
local Config = Loader.require("src/shared/GeneratedConfig")
local D = Config.Runtime.deformation

local rig = Pose.mallowRig()

local function scan(strength)
	local minY, maxY, maxXZ = 1, 1, 1
	local t = 0
	while t <= 1.2 do
		local y = Pose.scaleYAfterImpact(strength, t)
		minY = math.min(minY, y)
		maxY = math.max(maxY, y)
		maxXZ = math.max(maxXZ, Pose.scaleXZFor(y))
		t += 0.001
	end
	return minY, maxY, maxXZ
end

describe("PlushPose", function()
	it("rig: non-deforming root implied, 9 belly lattice bones, <= 6 secondary", function()
		local belly, sec = 0, 0
		for _, b in rig do
			if b.secondary then
				sec += 1
			else
				belly += 1
			end
		end
		expect(belly).toBe(D.plush_lattice_bones)
		expect(sec <= D.secondary_bones_max).toBe(true)
	end)

	it("respects runtime caps: Y >= 0.72, XZ <= 1.18, fall stretch <= 1.12", function()
		local minY, _, maxXZ = scan(1)
		expect(minY).toBeAtLeast(D.impact_scale_y_min - 1e-9)
		expect(minY).toBeNear(D.impact_scale_y_min, 1e-3)
		expect(maxXZ).toBeAtMost(D.impact_scale_xz_max + 1e-9)
		expect(Pose.scaleYFalling(1000)).toBeAtMost(D.fall_stretch_y_max + 1e-9)
		expect(Pose.scaleYFalling(0)).toBe(1)
	end)

	it("phases 0.09 / 0.18 / settle fit inside the 0.90 s cap (no naive sum)", function()
		expect(Pose.COMPRESS).toBe(0.09)
		expect(Pose.REBOUND).toBe(0.18)
		expect(Pose.COMPRESS + Pose.REBOUND + Pose.SETTLE).toBeAtMost(D.max_total_settle_seconds + 1e-9)
		expect(Pose.scaleYAfterImpact(1, D.max_total_settle_seconds)).toBe(1)
		expect(Pose.settleState(0.95)).toBe("supporting")
	end)

	it("weak contact squashes less than a big fall", function()
		local weak = scan(0.2)
		local strong = scan(1)
		expect(weak > strong).toBe(true)
	end)

	it("100 impacts then reset return exactly to the reference pose (no drift)", function()
		for i = 1, 100 do
			Pose.compute(rig, { phase = "impact", t = (i % 9) * 0.1, strength = (i % 7) / 7 })
		end
		local rest = Pose.compute(rig, { phase = "impact", t = 5, strength = 1 })
		for _, b in rest.bones do
			for k = 1, 3 do
				expect(b.offset[k]).toBe(0)
				expect(b.rotation[k]).toBe(0)
			end
		end
	end)

	it("supporting state: visible top within 0.25 stud of the collider, even with a player on it", function()
		local p = Pose.compute(rig, { phase = "impact", t = 1.0, strength = 1, standing = true })
		expect(p.state).toBe("supporting")
		expect(math.abs(p.topOffset)).toBeAtMost(D.walkable_top_alignment_tolerance_studs)
	end)

	it("big compressions only happen before the support becomes active", function()
		local t = 0
		while t < 2 do
			local p = Pose.compute(rig, { phase = "impact", t = t, strength = 1 })
			if p.state == "supporting" then
				expect(math.abs(p.scaleY - 1)).toBeAtMost(1e-9)
			end
			t += 0.01
		end
	end)

	it("pose uses translations/rotations only: no bone scale field", function()
		local p = Pose.compute(rig, { phase = "impact", t = 0.09, strength = 1 })
		for _, b in p.bones do
			expect(b.scale).toBe(nil)
			expect(#b.offset).toBe(3)
			expect(#b.rotation).toBe(3)
		end
		local src = fs.readFile("src/shared/Domain/PlushPose.luau")
		expect(string.find(src, "Transform.Scale") == nil).toBe(true)
	end)

	it("deformation disabled => reference pose, same settle state timeline", function()
		local on = Pose.compute(rig, { phase = "impact", t = 0.1, strength = 1, enabled = true })
		local off = Pose.compute(rig, { phase = "impact", t = 0.1, strength = 1, enabled = false })
		expect(off.scaleY).toBe(1)
		expect(off.state).toBe(on.state)
	end)

	it("server gameplay code never depends on the visual pose", function()
		for _, f in
			{
				"src/shared/Domain/BurialLogic.luau",
				"src/shared/Domain/Rewards.luau",
				"src/shared/Domain/ExpeditionStateMachine.luau",
				"src/server/Services/BurialService.luau",
				"src/server/Services/ExpeditionService.luau",
			}
		do
			if fs.isFile(f) then
				expect(string.find(fs.readFile(f), "PlushPose") == nil).toBe(true)
			end
		end
	end)
end)

return true
