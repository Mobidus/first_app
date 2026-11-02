--!strict
-- Room template "bureau" (palette, machine and props: config/rooms.json family "bureau").
local Template = require(script.Parent.Template)

return Template.make("bureau", {
	floorMaterial = Enum.Material.SmoothPlastic,
	wallMaterial = Enum.Material.SmoothPlastic,
	propMaterial = Enum.Material.SmoothPlastic,
	propColors = {
		bureau_paper_ream = Color3.fromHex("#FFFFFF"),
		bureau_desk = Color3.fromHex("#B9A4EE"),
		bureau_locker = Color3.fromHex("#2ACBC7"),
	},
})
