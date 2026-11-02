--!strict
-- Mobile-friendly third-person camera: classic follow with a slightly higher default pitch so the
-- next landing stays visible; zoom bounds fit small rooms; decorative parts never block the view
-- (they are CanQuery = false). The camera never performs a jump for the player.
local Players = game:GetService("Players")

local CameraController = {}

function CameraController.start()
	local plr = Players.LocalPlayer
	plr.CameraMinZoomDistance = 8
	plr.CameraMaxZoomDistance = 28
	plr.DevComputerCameraMode = Enum.DevComputerCameraMovementMode.Classic
	plr.DevTouchCameraMode = Enum.DevTouchCameraMovementMode.Classic
	local cam = workspace.CurrentCamera
	cam.FieldOfView = 72
end

return CameraController
