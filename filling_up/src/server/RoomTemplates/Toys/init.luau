--!strict
-- Room template "toy" (palette, machine and props: config/rooms.json family "toy").
local Template = require(script.Parent.Template)

return Template.make("toy", {
	floorMaterial = Enum.Material.SmoothPlastic,
	wallMaterial = Enum.Material.SmoothPlastic,
	propMaterial = Enum.Material.Fabric,
	propColors = {
		toy_plush_mallow = Color3.fromHex("#FFF1D6"),
		toy_plush_octo = Color3.fromHex("#8FEFC4"),
		toy_plush_loppy = Color3.fromHex("#C9B3F5"),
		toy_flat_duck = Color3.fromHex("#FFE14D"),
		toy_shape_cube = Color3.fromHex("#FF4CB8"),
	},
})
