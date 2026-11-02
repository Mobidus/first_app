--!strict
-- Room template "garage" (palette, machine and props: config/rooms.json family "garage").
local Template = require(script.Parent.Template)

return Template.make("garage", {
	floorMaterial = Enum.Material.Concrete,
	wallMaterial = Enum.Material.SmoothPlastic,
	propMaterial = Enum.Material.Metal,
	propColors = {
		garage_tool_chest = Color3.fromHex("#FF684B"),
		garage_flat_car = Color3.fromHex("#8855FF"),
	},
})
