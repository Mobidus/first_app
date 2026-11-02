--!strict
-- Room template "pool" (palette, machine and props: config/rooms.json family "pool", decision 0020).
local Template = require(script.Parent.Template)

return Template.make("pool", {
	floorMaterial = Enum.Material.SmoothPlastic,
	wallMaterial = Enum.Material.SmoothPlastic,
	propMaterial = Enum.Material.SmoothPlastic,
	propColors = {
		pool_inflatable_duck = Color3.fromHex("#FFD23F"),
		pool_flamingo_float = Color3.fromHex("#FF7FB8"),
		pool_beach_ball = Color3.fromHex("#FF684B"),
		pool_donut_ring = Color3.fromHex("#FF9FC9"),
		pool_unicorn_float = Color3.fromHex("#FFFFFF"),
		pool_cooler = Color3.fromHex("#1FA8E0"),
		pool_croc_float = Color3.fromHex("#39E68B"),
		pool_air_mattress = Color3.fromHex("#FFE14D"),
	},
})
