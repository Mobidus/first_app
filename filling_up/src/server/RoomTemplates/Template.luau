--!strict
-- Shared room-template builder: palettes, machines and props come from config/rooms.json; this
-- module only maps them to Roblox materials/colours. A template never invents gameplay values.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.GeneratedConfig)

local Template = {}

local MARKERS = Config.Rooms.functional_markers

function Template.make(familyId: string, style: { [string]: any })
	local fam
	for _, f in Config.Rooms.families do
		if f.id == familyId then
			fam = f
		end
	end
	assert(fam, "unknown family " .. familyId)
	local pal = fam.palette
	return table.freeze({
		familyId = familyId,
		name = fam.name,
		release = fam.release,
		palette = {
			background = Color3.fromHex(pal.fond),
			structure = Color3.fromHex(pal.structure),
			accent = Color3.fromHex(pal.accent),
		},
		machine = fam.machine,
		signatureEvent = fam.signature_event,
		exitVisuals = fam.exit_visuals,
		souvenirCosmetics = fam.souvenir_cosmetic_ids,
		floorMaterial = style.floorMaterial or Enum.Material.SmoothPlastic,
		wallMaterial = style.wallMaterial or Enum.Material.SmoothPlastic,
		propMaterial = style.propMaterial or Enum.Material.SmoothPlastic,
		propColors = style.propColors or {},
		ambient = style.ambient or Color3.fromRGB(235, 235, 245),
	})
end

function Template.markerColor(behavior: string): Color3
	local m = MARKERS[behavior] or MARKERS.stable
	return Color3.fromHex(m.color)
end

function Template.markerIcon(behavior: string): string
	local m = MARKERS[behavior] or MARKERS.stable
	return m.icon
end

return Template
