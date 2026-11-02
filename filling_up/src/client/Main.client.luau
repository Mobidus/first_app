--!strict
-- Client bootstrap: controllers consume authoritative server state; none of them grants anything.
local Controllers = script.Parent:WaitForChild("Controllers")

for _, name in
	{
		"SettingsController",
		"MovementController",
		"CameraController",
		"HUDController",
		"TutorialController",
		"TutorialShopController",
		"ShopController",
		"ToolController",
		"EffectsController",
		"PlushDeformationController",
	}
do
	local ok, err = pcall(function()
		(require(Controllers:WaitForChild(name)) :: any).start()
	end)
	if not ok then
		warn("[FillingUp] controller failed:", name, err)
	end
end
