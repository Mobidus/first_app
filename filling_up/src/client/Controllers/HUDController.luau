--!strict
-- Room HUD: coins / permits, room label (brief, non-blocking), gains summary in the sas, burial
-- alert "DÉGAGE-TOI" with free direction, KO panel with a FREE restart. Displays server state
-- only; it never credits anything. There is NO survival timer and NO global fill bar.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Strings = require(Shared.Strings)
local Net = require(script.Parent.Parent.Net)
local Ui = require(script.Parent.Ui)

local HUDController = {}

local function lang(): string
	return (Net.state.settings and Net.state.settings.language) or "fr"
end

function HUDController.start()
	local gui = Ui.screen("HUD")
	local top = Ui.panel(gui, UDim2.new(0, 260, 0, 54), UDim2.new(0, 16, 0, 12))
	local coins = Ui.label(top, "0", UDim2.new(0.5, -8, 1, -12), UDim2.new(0, 10, 0, 6), Ui.C.navy)
	local permits = Ui.label(top, "0", UDim2.new(0.5, -8, 1, -12), UDim2.new(0.5, 0, 0, 6), Ui.C.violet)
	local roomLabel = Ui.label(gui, "", UDim2.new(0, 360, 0, 40), UDim2.new(0.5, -180, 0, 14), Ui.C.navy)
	roomLabel.Visible = false
	local toast = Ui.label(gui, "", UDim2.new(0, 420, 0, 46), UDim2.new(0.5, -210, 0.18, 0), Ui.C.navy)
	toast.Visible = false
	local alert = Ui.panel(gui, UDim2.new(0, 300, 0, 64), UDim2.new(0.5, -150, 0.72, 0), Ui.C.coral)
	alert.Visible = false
	Ui.label(alert, "▲ " .. Strings.get(lang(), "dig_out"), UDim2.new(1, -16, 1, -12), UDim2.new(0, 8, 0, 6), Ui.C.cream)

	local function showToast(text: string, seconds: number)
		toast.Text = text
		toast.Visible = true
		task.delay(seconds, function()
			if toast.Text == text then
				toast.Visible = false
			end
		end)
	end

	Net.on("State", function(s)
		coins.Text = "● " .. tostring(s.coins or 0)
		permits.Text = "◆ " .. tostring(s.permits or 0)
		if gui:GetAttribute("NonPersistent") == nil and game:GetService("Players").LocalPlayer:GetAttribute("NonPersistentProgress") then
			gui:SetAttribute("NonPersistent", true)
			showToast("Test : progression non persistante", 4)
		end
	end)

	local koPanel: Frame? = nil
	Net.on("Hud", function(e)
		if e.type == "room_enter" then
			roomLabel.Text = Strings.get(lang(), "room_label", e.family, e.depth)
			roomLabel.Visible = true
			task.delay(2.5, function()
				roomLabel.Visible = false
			end)
			if koPanel then
				koPanel:Destroy()
				koPanel = nil
			end
		elseif e.type == "hint" then
			showToast(Strings.get(lang(), e.key), 4)
		elseif e.type == "reward" or e.type == "milestone" then
			showToast(
				"+"
					.. tostring(e.amount or e.coins)
					.. " Coins"
					.. (if e.type == "milestone" then "  ·  " .. Strings.get(lang(), "climb") else ""),
				1.5
			)
		elseif e.type == "gains" then
			showToast(string.format("+%d Coins  +%d ◆  +%d XP", e.coins or 0, e.permits or 0, e.xp or 0), 2.5)
		elseif e.type == "save_status" then
			showToast(Strings.get(lang(), if e.ok then "saved" else "save_failed"), 1.5)
		elseif e.type == "save_failed_retry" then
			showToast(Strings.get(lang(), "save_failed"), 1)
		elseif e.type == "loading_next" then
			showToast(Strings.get(lang(), "loading_next"), 1)
		elseif e.type == "ko" then
			local panel = Ui.panel(gui, UDim2.new(0, 380, 0, 220), UDim2.new(0.5, -190, 0.5, -110))
			Ui.label(panel, Strings.get(lang(), "ko_title"), UDim2.new(1, -20, 0, 50), UDim2.new(0, 10, 0, 10), Ui.C.coral)
			Ui.label(panel, Strings.get(lang(), "ko_kept"), UDim2.new(1, -20, 0, 40), UDim2.new(0, 10, 0, 70), Ui.C.navy)
			Ui.button(panel, Strings.get(lang(), "restart"), UDim2.new(0, 220, 0, 56), UDim2.new(0.5, -110, 1, -76), Ui.C.mint, function()
				Net.intent("RequestRestart", Net.requestId())
			end)
			koPanel = panel
		end
	end)

	Net.on("BurialWarning", function(e)
		alert.Visible = e.on == true
	end)
end

return HUDController
