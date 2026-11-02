--!strict
-- Tool button (>= 48 px, bottom-right, away from the jump button) sending a USE INTENT only.
-- Visual feedback starts when the server answers; a refused use shows its reason and nothing else.
local Net = require(script.Parent.Parent.Net)
local Ui = require(script.Parent.Ui)
local Movement = require(script.Parent.MovementController)

local ToolController = {}

local function targetUnderCrosshair(): string
	local cam = workspace.CurrentCamera
	local ray = cam:ViewportPointToRay(cam.ViewportSize.X / 2, cam.ViewportSize.Y / 2)
	local hit = workspace:Raycast(ray.Origin, ray.Direction * 40)
	local m = hit and hit.Instance.Parent
	if m and m:IsA("Model") and m:GetAttribute("ObjectInstanceId") then
		return m:GetAttribute("ObjectInstanceId") :: string
	end
	return ""
end

function ToolController.start()
	local gui = Ui.screen("ToolButton")
	local btn = Ui.button(gui, "", UDim2.new(0, 84, 0, 84), UDim2.new(1, -196, 1, -110), Ui.C.cyan, function() end)
	btn.Visible = false
	local charges = Ui.label(btn, "", UDim2.new(0, 30, 0, 24), UDim2.new(1, -28, 0, -6), Ui.C.navy)
	btn.Activated:Connect(function()
		local toolId = Net.state.loadout and Net.state.loadout.active
		if not toolId then
			return
		end
		local res = Net.intent("RequestToolUse", toolId, targetUnderCrosshair(), Net.requestId())
		if not res.ok then
			btn.Text = "×"
			task.delay(0.6, function()
				btn.Text = ""
			end)
			return
		end
		charges.Text = tostring(res.charges)
		if res.kind == "glide" then
			Movement.setGlide(res.descentMultiplier, res.duration)
		end
	end)
	Net.on("State", function(s)
		local toolId = s.loadout and s.loadout.active
		btn.Visible = toolId ~= nil and s.phase == "Active" and not s.inSas
		if toolId and s.charges then
			charges.Text = tostring(s.charges[toolId] or 0)
		end
	end)
end

return ToolController
