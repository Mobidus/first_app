--!strict
-- Visual plush deformation, reconstructed from the REFERENCE pose and an impact event every time
-- (no cumulative transform => no drift). Output = bone translations + rotations; there is no bone
-- scale (Bone.Transform is a CFrame). Server collisions, rewards and KO never read this module.

local Config = require(script.Parent.Parent.GeneratedConfig)

local D = Config.Runtime.deformation

local Pose = {}

Pose.COMPRESS = D.impact_compression_seconds
Pose.REBOUND = D.rebound_seconds
Pose.TOTAL = D.max_total_settle_seconds
-- settle phase is shortened so that compression + rebound + settle never exceeds the cap
Pose.SETTLE = math.min(D.settle_seconds, D.max_total_settle_seconds - D.impact_compression_seconds - D.rebound_seconds)
Pose.MIN_Y = D.impact_scale_y_min
Pose.MAX_XZ = D.impact_scale_xz_max
Pose.MAX_STRETCH = D.fall_stretch_y_max
Pose.MAX_SECONDARY_RAD = math.rad(D.max_secondary_angle_degrees)
Pose.TOP_TOLERANCE = D.walkable_top_alignment_tolerance_studs
-- reference speeds (decision 0007, to calibrate in PlushLab): full stretch / full impact
Pose.FALL_REF_SPEED = 60
Pose.IMPACT_REF_SPEED = 50
Pose.OVERSHOOT = 0.06
Pose.CONTACT_DENT = 0.15 -- player standing on a supporting plush: <= tolerance (0.25)

export type BoneRest = { name: string, x: number, y: number, z: number, secondary: boolean, sign: number? }

-- Mallow rig as exported by assets/source/blender/build_plush.py (pose_library.json
-- bone_rest_heads, studs, Roblox model space, relative to the non-deforming Root at base centre):
-- 9 belly lattice bones Belly_<x><z> + 5 secondary bones. Used for the proxy and as a fallback;
-- with the imported mesh the controller reads the actual Bones (Pose.rigFromBones).
local MALLOW_REST = {
	{ "Belly_00", -4, 3, 3 },
	{ "Belly_10", -1, 3, 3 },
	{ "Belly_20", 2, 3, 3 },
	{ "Belly_01", -4, 3, 0 },
	{ "Belly_11", -1, 3, 0 },
	{ "Belly_21", 2, 3, 0 },
	{ "Belly_02", -4, 3, -3 },
	{ "Belly_12", -1, 3, -3 },
	{ "Belly_22", 2, 3, -3 },
	{ "Head", 3, 2.6, 0 },
	{ "Arm_L", 1.2, 2.4, -3.1 },
	{ "Arm_R", 1.2, 2.4, 3.1 },
	{ "Leg_L", -3.8, 2.2, -2.6 },
	{ "Leg_R", -3.8, 2.2, 2.6 },
}

local function isSecondary(name: string): boolean
	return string.sub(name, 1, 6) ~= "Belly_"
end

-- Right-side bones mirror the secondary swing. Side = last letter of an upper-case suffix:
-- Arm_R, Ear_R, Fin_R, but also Leg_FR / Leg_BR (front/back right, plush_v2 rigs).
local function sideSign(name: string): number
	local suffix = string.match(name, "_(%u+)$")
	return if suffix ~= nil and string.sub(suffix, -1) == "R" then -1 else 1
end
Pose.sideSign = sideSign

function Pose.mallowRig(): { BoneRest }
	local bones = {}
	for _, b in MALLOW_REST do
		table.insert(bones, { name = b[1], x = b[2], y = b[3], z = b[4], secondary = isSecondary(b[1]), sign = sideSign(b[1]) })
	end
	return bones
end

-- Build a rig description from runtime bones: { {name, x, y, z} } in root space. "Root" is skipped
-- (it never moves). Belly lattice = names starting with "Belly_".
function Pose.rigFromBones(list: { { name: string, x: number, y: number, z: number } }): { BoneRest }
	local bones = {}
	for _, b in list do
		if b.name ~= "Root" then
			table.insert(bones, { name = b.name, x = b.x, y = b.y, z = b.z, secondary = isSecondary(b.name), sign = sideSign(b.name) })
		end
	end
	return bones
end

local function easeOut(x: number): number
	return 1 - (1 - x) * (1 - x)
end

function Pose.strengthFromSpeed(impactSpeed: number): number
	return math.clamp(impactSpeed / Pose.IMPACT_REF_SPEED, 0, 1)
end

-- Vertical scale envelope after an impact of `strength` (0..1), t seconds after impact.
function Pose.scaleYAfterImpact(strength: number, t: number): number
	local s = math.clamp(strength, 0, 1)
	local minY = 1 - (1 - Pose.MIN_Y) * s
	local peak = 1 + Pose.OVERSHOOT * s
	if t <= 0 then
		return 1
	elseif t < Pose.COMPRESS then
		return 1 + (minY - 1) * easeOut(t / Pose.COMPRESS)
	elseif t < Pose.COMPRESS + Pose.REBOUND then
		local u = (t - Pose.COMPRESS) / Pose.REBOUND
		return minY + (peak - minY) * easeOut(u)
	elseif t < Pose.TOTAL then
		local u = (t - Pose.COMPRESS - Pose.REBOUND) / (Pose.TOTAL - Pose.COMPRESS - Pose.REBOUND)
		-- damped oscillation from the overshoot back to rest (1.5 half-periods), exactly 1 at the end
		local amp = (peak - 1) * (1 - u)
		return 1 + amp * math.cos(u * math.pi * 3)
	end
	return 1
end

function Pose.scaleYFalling(verticalSpeed: number): number
	local f = math.clamp(math.abs(verticalSpeed) / Pose.FALL_REF_SPEED, 0, 1)
	return 1 + (Pose.MAX_STRETCH - 1) * f
end

function Pose.scaleXZFor(scaleY: number): number
	if scaleY < 1 then
		return math.min(Pose.MAX_XZ, 1 + (1 - scaleY) * ((Pose.MAX_XZ - 1) / (1 - Pose.MIN_Y)))
	end
	return math.max(0.94, 1 - (scaleY - 1) * 0.5)
end

function Pose.settleState(t: number): string
	if t < 0 then
		return "falling"
	elseif t < Pose.COMPRESS then
		return "impact"
	elseif t < Pose.TOTAL then
		return "settling"
	end
	return "supporting"
end

export type BonePose = { name: string, offset: { number }, rotation: { number } }
export type PoseResult = { scaleY: number, scaleXZ: number, state: string, bones: { BonePose }, topOffset: number }

-- Full pose. `phase` = "falling" (uses verticalSpeed) or "impact" (uses strength + t).
-- `enabled=false` (low-end devices / reduced effects) => reference pose; gameplay unchanged.
function Pose.compute(
	rig: { BoneRest },
	params: { phase: string, t: number?, strength: number?, verticalSpeed: number?, standing: boolean?, enabled: boolean? }
): PoseResult
	local sy = 1
	local state = "supporting"
	local t = params.t or 0
	if params.enabled ~= false then
		if params.phase == "falling" then
			sy = Pose.scaleYFalling(params.verticalSpeed or 0)
			state = "falling"
		else
			sy = Pose.scaleYAfterImpact(params.strength or 0, t)
			state = Pose.settleState(t)
		end
	elseif params.phase == "falling" then
		state = "falling"
	else
		state = Pose.settleState(t)
	end
	local sxz = Pose.scaleXZFor(sy)
	local bones = {}
	local lag = 0
	if params.enabled ~= false and params.phase ~= "falling" and t > 0 and t < Pose.TOTAL then
		lag = math.sin(math.pi * math.min(1, t / (Pose.COMPRESS + Pose.REBOUND)))
			* (1 - t / Pose.TOTAL)
			* math.clamp(params.strength or 0, 0, 1)
	elseif params.enabled ~= false and params.phase == "falling" then
		lag = -0.5 * (sy - 1) / (Pose.MAX_STRETCH - 1 + 1e-9)
	end
	local dent = if params.standing and state == "supporting" and params.enabled ~= false then Pose.CONTACT_DENT else 0
	local topOffset = 0
	for _, b in rig do
		local ox, oy, oz = b.x * (sxz - 1), b.y * (sy - 1), b.z * (sxz - 1)
		local rx, rz = 0, 0
		if b.secondary then
			rx = Pose.MAX_SECONDARY_RAD * lag * (b.sign or 1)
			rz = Pose.MAX_SECONDARY_RAD * lag * 0.5 * (b.sign or 1)
		else
			oy -= dent
			topOffset = math.min(topOffset, oy)
		end
		table.insert(bones, { name = b.name, offset = { ox, oy, oz }, rotation = { rx, 0, rz } })
	end
	return { scaleY = sy, scaleXZ = sxz, state = state, bones = bones, topOffset = topOffset }
end

return Pose
