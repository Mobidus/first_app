--!strict
-- Room template "bin" (palette, machine and props: config/rooms.json family "bin").
local Template = require(script.Parent.Template)

return Template.make("bin", {
	floorMaterial = Enum.Material.SmoothPlastic,
	wallMaterial = Enum.Material.SmoothPlastic,
	propMaterial = Enum.Material.SmoothPlastic,
	propColors = {
		bin_compact_container = Color3.fromHex("#F6EEDC"),
		bin_hex_block = Color3.fromHex("#16D9FF"),
	},
})
