--!strict
-- Builds a prop as: one SIMPLE server collider (invisible Part, the only collision) + visual parts
-- (no collision, no query) + a top marker (function colour AND icon). Uses the T03 parametric
-- generators when present (ServerStorage.AssetGenerators), otherwise a clearly identified proxy.
-- Plush props get a visual "PlushVisual" model the client deforms; the collider never deforms.
local CollectionService = game:GetService("CollectionService")
local ServerStorage = game:GetService("ServerStorage")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.GeneratedConfig)
local Template = require(script.Parent.Parent.RoomTemplates.Template)

local PropFactory = {}

local PROPS: { [string]: any } = {}
for _, f in Config.Rooms.families do
	for _, p in f.props do
		PROPS[p.id] = p
	end
end
PropFactory.PROPS = PROPS

local generators = ServerStorage:FindFirstChild("AssetGenerators")

local function v3(t: { number }): Vector3
	return Vector3.new(t[1], t[2], t[3])
end

local function addMarker(model: Model, behavior: string, w: number, d: number, topY: number)
	local marker = Instance.new("Part")
	marker.Name = "TopMarker"
	marker.Anchored = false
	marker.CanCollide = false
	marker.CanQuery = false
	marker.CanTouch = false
	marker.Massless = true
	marker.Size = Vector3.new(math.min(3, w * 0.4), 0.06, math.min(3, d * 0.4))
	marker.Color = Template.markerColor(behavior)
	marker.Material = Enum.Material.Neon
	marker.Transparency = 0.15
	marker:SetAttribute("Icon", Template.markerIcon(behavior)) -- footprint / spring / arrows / hourglass
	marker:SetAttribute("LocalY", topY + 0.03)
	CollectionService:AddTag(marker, "DecorOnly")
	local decal = Instance.new("Decal")
	decal.Face = Enum.NormalId.Top
	decal.Texture = "" -- icon texture id: null until assets are imported (manifest)
	decal.Parent = marker
	marker.Parent = model
end

-- Returns Model whose PrimaryPart is the collider ("Collider"). Pivot = bottom centre.
function PropFactory.create(propId: string, template: any?): Model
	local p = PROPS[propId]
	assert(p, "unknown prop " .. propId)
	local size = p.collider.size_studs -- width, depth, height
	local w, d, h = size[1], size[2], size[3]
	local model = Instance.new("Model")
	model.Name = propId
	model:SetAttribute("PropId", propId)
	model:SetAttribute("Behavior", p.behavior)

	local collider = Instance.new("Part")
	collider.Name = "Collider"
	collider.Size = Vector3.new(w, h, d)
	collider.Transparency = 1
	collider.CanCollide = true
	collider.CanQuery = true
	collider.TopSurface = Enum.SurfaceType.Smooth
	collider.CustomPhysicalProperties = PhysicalProperties.new(0.7, 0.8, 0.05, 1, 1)
	collider:SetAttribute("WalkableW", p.collider.walkable_top[1])
	collider:SetAttribute("WalkableD", p.collider.walkable_top[2])
	CollectionService:AddTag(collider, "FillCollider")
	collider.Parent = model
	model.PrimaryPart = collider

	local gen = generators and generators:FindFirstChild(propId)
	local visualRoot = Instance.new("Model")
	visualRoot.Name = if p.deformation_profile == "plush_soft" then "PlushVisual" else "Visual"
	if gen and gen:IsA("ModuleScript") then
		local desc = (require(gen) :: any).build({ size = p.size_studs })
		for _, spec in desc.parts do
			local part = Instance.new("Part")
			part.Name = spec.name
			part.Size = v3(spec.size)
			part.Color = Color3.fromHex(spec.color)
			local okMat = pcall(function()
				part.Material = (Enum.Material :: any)[spec.material]
			end)
			if not okMat then
				part.Material = Enum.Material.SmoothPlastic
			end
			part.Shape = (Enum.PartType :: any)[spec.shape == "Cylinder" and "Cylinder" or spec.shape == "Ball" and "Ball" or "Block"]
			part.CanCollide = false
			part.CanQuery = false
			part.CanTouch = false
			part.Massless = true
			part:SetAttribute("LocalOffset", v3(spec.offset) - Vector3.new(0, h / 2, 0))
			-- generator rotation hints (Roblox cylinders run along X): per part, per name, or for all cylinders
			local rot = spec.rotationDeg
				or (desc.chevronRotationDeg and desc.chevronRotationDeg[spec.name])
				or (spec.shape == "Cylinder" and (desc.edgeCylinderRotationDeg or desc.stampRotationDeg))
			if rot then
				part:SetAttribute("LocalRotationDeg", v3(rot))
			end
			part.Parent = visualRoot
		end
	else
		-- PROXY (diagnostic only, not the final art): coloured block with rounded silhouette hints
		local body = Instance.new("Part")
		body.Name = "ProxyBody"
		body.Size = Vector3.new(p.size_studs[1], h, p.size_studs[2])
		body.Color = (template and template.propColors[propId]) or Color3.fromRGB(240, 230, 210)
		body.Material = if template then template.propMaterial else Enum.Material.SmoothPlastic
		body.CanCollide = false
		body.CanQuery = false
		body.CanTouch = false
		body.Massless = true
		body:SetAttribute("LocalOffset", Vector3.zero)
		body:SetAttribute("Proxy", true)
		body.Parent = visualRoot
		model:SetAttribute("VisualStatus", "proxy_not_final_art")
	end
	visualRoot.Parent = model
	if p.deformation_profile == "plush_soft" then
		CollectionService:AddTag(model, "Plush")
	end
	addMarker(model, p.behavior, p.collider.walkable_top[1], p.collider.walkable_top[2], h / 2)
	-- weld visual parts to the collider (unanchored, massless: they follow the physical root)
	for _, part in model:GetDescendants() do
		if part:IsA("BasePart") and part ~= collider then
			local off = part:GetAttribute("LocalOffset") or Vector3.new(0, (part:GetAttribute("LocalY") :: number?) or 0, 0)
			local rot = part:GetAttribute("LocalRotationDeg") :: Vector3?
			part.CFrame = collider.CFrame
				* CFrame.new(off :: Vector3)
				* (if rot then CFrame.Angles(math.rad(rot.X), math.rad(rot.Y), math.rad(rot.Z)) else CFrame.identity)
			if visualRoot.Name ~= "PlushVisual" or part.Name == "TopMarker" then
				local weld = Instance.new("WeldConstraint")
				weld.Part0 = collider
				weld.Part1 = part
				weld.Parent = part
			else
				-- plush visual: NOT welded to the falling root; anchored template that each client
				-- re-poses locally every frame from the collider CFrame (PlushDeformationController)
				part.Anchored = true
			end
		end
	end
	return model
end

-- Pool reset routine: clears everything a previous life could leave behind.
function PropFactory.reset(model: Model)
	local collider = model.PrimaryPart :: BasePart
	collider.Anchored = true
	collider.AssemblyLinearVelocity = Vector3.zero
	collider.AssemblyAngularVelocity = Vector3.zero
	for _, attr in { "ObjectInstanceId", "RewardTag", "SettledFor", "Occupied", "Stabilized", "Structural", "RouteNode" } do
		model:SetAttribute(attr, nil)
	end
	for _, tag in { "FillAggregate", "Stabilizable", "RouteSupport" } do
		CollectionService:RemoveTag(collider, tag)
	end
	for _, d in model:GetDescendants() do
		if d:IsA("ParticleEmitter") or d:IsA("Trail") or d:IsA("Highlight") then
			d:Destroy()
		end
	end
	model.Parent = nil
end

return PropFactory
