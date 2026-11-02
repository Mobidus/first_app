--!strict
-- Room template "reception" (palette, machine and props: config/rooms.json family "reception").
local Template = require(script.Parent.Template)

return Template.make("reception", {
	floorMaterial = Enum.Material.SmoothPlastic,
	wallMaterial = Enum.Material.SmoothPlastic,
	propMaterial = Enum.Material.Cardboard,
	propColors = {
		reception_carton = Color3.fromHex("#FFD24A"),
		reception_foam_crate = Color3.fromHex("#9FE7F5"),
		reception_suitcase = Color3.fromHex("#FF9B47"),
		reception_pallet = Color3.fromHex("#2ACBC7"),
		reception_tape_reel = Color3.fromHex("#16D9FF"),
		toy_plush_mallow = Color3.fromHex("#FFF1D6"),
	},
})
