--!strict
-- Client-only plush deformation (docs/05 §7). Reconstructs every frame from the REFERENCE pose and
-- the last server impact event (objectInstanceId, serverTime, impactNormal, impactStrength,
-- settleState) via PlushPose. Two render paths:
--   * rig: imported skinned MeshPart with Bones -> Bone.Transform = CFrame(translation) * rotation
--     (no scale on Bone.Transform, it is a CFrame);
--   * proxy: primitive visual parts (diagnostic proxy) scaled around the collider base.
-- LOD: <= 6 animated plushes near the hero (nearest first), 30 Hz near, 15 Hz mid, static far.
-- Disabling it (reduced effects) changes nothing in collisions, rewards or KO.
local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.GeneratedConfig)
local Pose = require(Shared.Domain.PlushPose)
local Net = require(script.Parent.Parent.Net)
local Settings = require(script.Parent.SettingsController)

local D = Config.Runtime.deformation

local PlushDeformationController = {}

type Entry = {
	model: Model,
	impactAt: number?,
	strength: number,
	rig: any,
	bones: { [string]: Bone }?,
	proxy: { { part: BasePart, size: Vector3, offset: Vector3 } }?,
	lastUpdate: number,
}

local entries: { [Model]: Entry } = {}

local function setup(model: Model): Entry
	local visual = model:FindFirstChild("PlushVisual")
	local bones: { [string]: Bone } = {}
	local restList = {}
	if visual then
		for _, d in visual:GetDescendants() do
			if d:IsA("Bone") then
				bones[d.Name] = d
				local p = d.WorldPosition - (model.PrimaryPart :: BasePart).Position
				table.insert(restList, { name = d.Name, x = p.X, y = p.Y, z = p.Z })
			end
		end
	end
	local hasRig = next(bones) ~= nil
	local proxy = nil
	if visual then
		proxy = {}
		for _, part in visual:GetDescendants() do
			if part:IsA("BasePart") then
				table.insert(
					proxy,
					{ part = part, size = part.Size, offset = (part:GetAttribute("LocalOffset") :: Vector3?) or Vector3.zero }
				)
			end
		end
	end
	return {
		model = model,
		impactAt = nil,
		strength = 0,
		rig = if hasRig then Pose.rigFromBones(restList) else Pose.mallowRig(),
		bones = if hasRig then bones else nil,
		proxy = proxy,
		lastUpdate = 0,
	}
end

local function apply(e: Entry, pose: any)
	local col = e.model.PrimaryPart :: BasePart
	if e.bones then
		for _, b in pose.bones do
			local bone = e.bones[b.name]
			if bone then
				bone.Transform = CFrame.new(b.offset[1], b.offset[2], b.offset[3])
					* CFrame.Angles(b.rotation[1], b.rotation[2], b.rotation[3])
			end
		end
	end
	if e.proxy then
		local base = col.CFrame * CFrame.new(0, -col.Size.Y / 2, 0)
		for _, pp in e.proxy do
			-- skinned mesh: only follows the physical root (deformation comes from the bones)
			local sy, sxz = if e.bones then 1 else pose.scaleY, if e.bones then 1 else pose.scaleXZ
			pp.part.Size = Vector3.new(pp.size.X * sxz, pp.size.Y * sy, pp.size.Z * sxz)
			local off = pp.offset + Vector3.new(0, col.Size.Y / 2, 0)
			pp.part.CFrame = base * CFrame.new(off.X * sxz, off.Y * sy, off.Z * sxz)
		end
	end
end

function PlushDeformationController.start()
	Net.on("PlushImpact", function(ev)
		local model = ev.model
		if typeof(model) ~= "Instance" or not model:IsA("Model") then
			return
		end
		local e = entries[model] or setup(model)
		entries[model] = e
		-- serverTime keeps all clients consistent; poses always start from the reference
		e.impactAt = os.clock() - math.max(0, Workspace:GetServerTimeNow() - ev.serverTime)
		e.strength = ev.impactStrength
	end)
	CollectionService:GetInstanceRemovedSignal("Plush"):Connect(function(inst)
		entries[inst :: Model] = nil
	end)
	RunService.RenderStepped:Connect(function()
		local char = Players.LocalPlayer.Character
		local hero = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
		if not hero then
			return
		end
		local enabled = not Settings.reducedEffects()
		-- discover plushes and rank by distance
		local ranked = {}
		for _, inst in CollectionService:GetTagged("Plush") do
			local m = inst :: Model
			if m.PrimaryPart and m:IsDescendantOf(Workspace) then
				entries[m] = entries[m] or setup(m)
				table.insert(ranked, { e = entries[m], d = (m.PrimaryPart.Position - hero.Position).Magnitude })
			end
		end
		table.sort(ranked, function(a, b)
			return a.d < b.d
		end)
		local now = os.clock()
		for i, r in ranked do
			local e = r.e
			local col = e.model.PrimaryPart :: BasePart
			local hz = if r.d <= D.near_distance_studs then D.near_visual_hz elseif r.d <= D.mid_distance_studs then D.mid_visual_hz else 0
			local animate = enabled and i <= D.max_near_hero_plush and hz > 0
			if animate and now - e.lastUpdate < 1 / hz then
				continue
			end
			e.lastUpdate = now
			local pose
			if not animate then
				pose = Pose.compute(e.rig, { phase = "impact", t = 99, strength = 0, enabled = false })
			elseif not col.Anchored and col.AssemblyLinearVelocity.Y < -2 and e.impactAt == nil then
				pose = Pose.compute(e.rig, { phase = "falling", verticalSpeed = col.AssemblyLinearVelocity.Y })
			else
				local t = if e.impactAt then now - e.impactAt else 99
				local standing = (hero.Position - col.Position).Magnitude < col.Size.Magnitude / 2 + 3
				pose = Pose.compute(e.rig, { phase = "impact", t = t, strength = e.strength, standing = standing })
			end
			apply(e, pose)
		end
	end)
end

return PlushDeformationController
