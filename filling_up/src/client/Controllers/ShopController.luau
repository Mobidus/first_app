--!strict
-- Sas shop (Coins), Robux tab (always "Boutique indisponible" while product ids are null) and the
-- rebirth flow (preview from the server, then confirm). Opened by a button only in the sas;
-- continuing straight through the door never requires it. States: owned / buyable / insufficient
-- / locked / unavailable, each with text (not colour only).
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Strings = require(Shared.Strings)
local Net = require(script.Parent.Parent.Net)
local Ui = require(script.Parent.Ui)

local ShopController = {}

local function lang(): string
	return (Net.state.settings and Net.state.settings.language) or "fr"
end

local function stateText(item): (string, Color3)
	local L = lang()
	if item.state == "owned" then
		return Strings.get(L, "owned"), Ui.C.mint
	elseif item.state == "buyable" then
		return Strings.get(L, "buy_coins", item.price), Ui.C.yellow
	elseif item.state == "insufficient" then
		return Strings.get(L, "insufficient", item.price - (Net.state.coins or 0)), Ui.C.cream
	elseif item.state == "rooms_required" then
		return Strings.get(L, "locked_rooms", item.minRooms or 0), Ui.C.cream
	elseif item.state == "unavailable" then
		return Strings.get(L, "unavailable"), Ui.C.cream
	end
	return tostring(item.state), Ui.C.cream
end

function ShopController.start()
	local gui = Ui.screen("SasShop")
	local open = Ui.button(gui, "Boutique", UDim2.new(0, 140, 0, 52), UDim2.new(1, -156, 0, 12), Ui.C.cyan, function() end)
	open.Visible = false
	local panel = Ui.panel(gui, UDim2.new(0.62, 0, 0.74, 0), UDim2.new(0.19, 0, 0.13, 0))
	panel.Visible = false
	local list = Instance.new("ScrollingFrame")
	list.Size = UDim2.new(1, -20, 1, -130)
	list.Position = UDim2.new(0, 10, 0, 60)
	list.BackgroundTransparency = 1
	list.AutomaticCanvasSize = Enum.AutomaticSize.Y
	list.CanvasSize = UDim2.new()
	local layout = Instance.new("UIListLayout")
	layout.Padding = UDim.new(0, 6)
	layout.Parent = list
	list.Parent = panel
	local robux = Ui.label(panel, "", UDim2.new(1, -20, 0, 26), UDim2.new(0, 10, 1, -64), Ui.C.navy)
	Ui.button(panel, "×", UDim2.new(0, 48, 0, 48), UDim2.new(1, -58, 0, 6), Ui.C.cream, function()
		panel.Visible = false
	end)
	local rebirthBtn = Ui.button(panel, "", UDim2.new(0, 220, 0, 48), UDim2.new(0, 10, 0, 6), Ui.C.violet, function() end)

	local function render()
		for _, c in list:GetChildren() do
			if c:IsA("Frame") then
				c:Destroy()
			end
		end
		for _, item in Net.state.catalog or {} do
			local row = Ui.panel(list, UDim2.new(1, -8, 0, 56), UDim2.new())
			Ui.label(
				row,
				item.name .. (if item.rank then " · rang " .. item.rank else "") .. "  ·  " .. Strings.get(lang(), "permanent"),
				UDim2.new(0.55, 0, 1, -10),
				UDim2.new(0, 10, 0, 5),
				Ui.C.navy
			)
			local text, color = stateText(item)
			local b = Ui.button(row, text, UDim2.new(0.4, 0, 1, -10), UDim2.new(0.58, 0, 0, 5), color, function()
				if item.state == "buyable" then
					Net.intent("RequestCoinPurchase", item.skuId, Net.requestId())
				elseif item.state == "owned" and item.kind ~= "upgrade" then
					Net.intent("RequestEquip", item.skuId, item.slot, Net.requestId())
				end
			end)
			b.AutoButtonColor = item.state == "buyable" or item.state == "owned"
		end
		robux.Text = "Robux : " .. Strings.get(lang(), "robux_unavailable")
		rebirthBtn.Text = Strings.get(lang(), "rebirth")
	end

	rebirthBtn.Activated:Connect(function()
		local prev = Net.intent("RequestRebirthPreview", 1, Net.requestId())
		if not prev.ok then
			robux.Text = tostring(prev.error)
			return
		end
		local max = prev.preview
		-- confirmation screen: exact cost, ranks, bonus, remaining permits, restart at room 1
		local confirm = Ui.panel(gui, UDim2.new(0, 460, 0, 260), UDim2.new(0.5, -230, 0.5, -130))
		local L = lang()
		Ui.label(
			confirm,
			string.format(
				"-%d ◆  →  rang %d  ·  bonus +%d%%  ·  reste %d ◆",
				max.cost,
				max.ranksAfter,
				math.floor(max.bonusAfter * 100 + 0.5),
				max.permitsAfter
			),
			UDim2.new(1, -20, 0, 40),
			UDim2.new(0, 10, 0, 14),
			Ui.C.navy
		)
		Ui.label(confirm, Strings.get(L, "rebirth_restart"), UDim2.new(1, -20, 0, 34), UDim2.new(0, 10, 0, 64), Ui.C.coral)
		Ui.label(confirm, Strings.get(L, "rebirth_kept"), UDim2.new(1, -20, 0, 34), UDim2.new(0, 10, 0, 104), Ui.C.navy)
		Ui.button(confirm, Strings.get(L, "rebirth_confirm"), UDim2.new(0.45, 0, 0, 52), UDim2.new(0.03, 0, 1, -64), Ui.C.violet, function()
			Net.intent("RequestRebirth", max.quantity, max.revision, max.token, Net.requestId())
			confirm:Destroy()
		end)
		Ui.button(confirm, Strings.get(L, "continue"), UDim2.new(0.45, 0, 0, 52), UDim2.new(0.52, 0, 1, -64), Ui.C.mint, function()
			confirm:Destroy()
		end)
	end)

	open.Activated:Connect(function()
		panel.Visible = not panel.Visible
		render()
	end)
	Net.on("State", function(s)
		open.Visible = s.inSas == true and not s.kiosk
		if not s.inSas then
			panel.Visible = false
		elseif panel.Visible then
			render()
		end
	end)
end

return ShopController
