--!strict
-- First-purchase kiosk in the sas after the tutorial: the Radar shown big, a 2-second demo, and
-- exactly two buttons "Acheter 50 Coins" / "Continuer". No timer, no Robux offer, no forced buy.
-- The price shown comes from the server catalog (config); the server re-checks everything.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Strings = require(Shared.Strings)
local Net = require(script.Parent.Parent.Net)
local Ui = require(script.Parent.Ui)

local TutorialShopController = {}

function TutorialShopController.start()
	local gui = Ui.screen("RadarKiosk")
	local panel = Ui.panel(gui, UDim2.new(0, 420, 0, 280), UDim2.new(0.5, -210, 0.5, -140))
	panel.Visible = false
	local title = Ui.label(panel, "Radar POP", UDim2.new(1, -20, 0, 44), UDim2.new(0, 10, 0, 10), Ui.C.navy)
	local info = Ui.label(panel, "", UDim2.new(1, -20, 0, 34), UDim2.new(0, 10, 0, 60), Ui.C.navy)
	local icon = Instance.new("Frame")
	icon.Size = UDim2.new(0, 96, 0, 96)
	icon.Position = UDim2.new(0.5, -48, 0, 98)
	icon.BackgroundColor3 = Ui.C.cyan
	Ui.round(icon, 24)
	icon.Parent = panel
	local status = Ui.label(panel, "", UDim2.new(1, -20, 0, 22), UDim2.new(0, 10, 1, -98), Ui.C.coral)
	local closed = false
	local buy = Ui.button(panel, "", UDim2.new(0.5, -20, 0, 56), UDim2.new(0, 10, 1, -66), Ui.C.yellow, function()
		local lang = (Net.state.settings and Net.state.settings.language) or "fr"
		local res = Net.intent("RequestCoinPurchase", "radar_pop", Net.requestId())
		if res.ok then
			Net.intent("RequestEquip", "radar_pop", "active", Net.requestId())
			panel.Visible = false
			closed = true
		else
			status.Text = if res.error == "network_error" then Strings.get(lang, "network_error") else tostring(res.error)
		end
	end)
	Ui.button(panel, "", UDim2.new(0.5, -20, 0, 56), UDim2.new(0.5, 10, 1, -66), Ui.C.mint, function()
		panel.Visible = false
		closed = true
	end).Name =
		"Continue"

	Net.on("State", function(s)
		local lang = (s.settings and s.settings.language) or "fr"
		if not s.kiosk or closed or (s.ownedTools and s.ownedTools.radar_pop) then
			panel.Visible = false
			return
		end
		local price = 50
		for _, item in s.catalog or {} do
			if item.skuId == "radar_pop" then
				price = item.price
			end
		end
		title.Text = "Radar POP"
		info.Text = string.format("%d Coins → %d", s.coins or 0, (s.coins or 0) - price)
		buy.Text = Strings.get(lang, "buy_coins", price);
		(panel:FindFirstChild("Continue") :: TextButton).Text = Strings.get(lang, "continue")
		panel.Visible = true
		-- 2-second demo pulse of the radar wave (visual only)
		task.spawn(function()
			for _ = 1, 4 do
				icon.BackgroundColor3 = Ui.C.mint
				task.wait(0.25)
				icon.BackgroundColor3 = Ui.C.cyan
				task.wait(0.25)
			end
		end)
	end)
end

return TutorialShopController
