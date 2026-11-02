--!strict
-- Room template "kitchen" (palette, machine and props: config/rooms.json family "kitchen").
local Template = require(script.Parent.Template)

return Template.make("kitchen", {
	floorMaterial = Enum.Material.SmoothPlastic,
	wallMaterial = Enum.Material.SmoothPlastic,
	propMaterial = Enum.Material.SmoothPlastic,
	propColors = {
		kitchen_cereal_box = Color3.fromHex("#FF9B47"),
		kitchen_closed_pot = Color3.fromHex("#24BFC4"),
	},
})
