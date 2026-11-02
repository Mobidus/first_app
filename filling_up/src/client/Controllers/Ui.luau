--!strict
-- Tiny UI kit from the design tokens (assets/source/design/design_tokens.json): colours, rounded
-- panels, buttons >= 44 pt, short texts. Every functional state pairs a colour with a text/icon.
local Players = game:GetService("Players")

local Ui = {}

Ui.C = {
	cream = Color3.fromHex("#FFF5DF"),
	navy = Color3.fromHex("#203055"),
	cyan = Color3.fromHex("#16D9FF"),
	yellow = Color3.fromHex("#FFE14D"),
	pink = Color3.fromHex("#FF4CB8"),
	mint = Color3.fromHex("#39E68B"),
	coral = Color3.fromHex("#FF684B"),
	violet = Color3.fromHex("#8855FF"),
}
Ui.MIN_TOUCH = 48

function Ui.screen(name: string): ScreenGui
	local gui = Instance.new("ScreenGui")
	gui.Name = name
	gui.ResetOnSpawn = false
	gui.IgnoreGuiInset = false
	gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	gui.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")
	return gui
end

function Ui.round(inst: GuiObject, radius: number?)
	local c = Instance.new("UICorner")
	c.CornerRadius = UDim.new(0, radius or 14)
	c.Parent = inst
end

function Ui.label(parent: Instance, text: string, size: UDim2, pos: UDim2, color: Color3?, textSize: number?): TextLabel
	local l = Instance.new("TextLabel")
	l.BackgroundTransparency = 1
	l.Size = size
	l.Position = pos
	l.Text = text
	l.Font = Enum.Font.GothamBold
	l.TextColor3 = color or Ui.C.navy
	l.TextScaled = textSize == nil
	if textSize then
		l.TextSize = textSize
	end
	l.Parent = parent
	return l
end

function Ui.panel(parent: Instance, size: UDim2, pos: UDim2, color: Color3?): Frame
	local f = Instance.new("Frame")
	f.Size = size
	f.Position = pos
	f.BackgroundColor3 = color or Ui.C.cream
	f.BorderSizePixel = 0
	Ui.round(f)
	local stroke = Instance.new("UIStroke")
	stroke.Color = Ui.C.navy
	stroke.Thickness = 2
	stroke.Parent = f
	f.Parent = parent
	return f
end

function Ui.button(parent: Instance, text: string, size: UDim2, pos: UDim2, color: Color3, onClick: () -> ()): TextButton
	local b = Instance.new("TextButton")
	b.Size = size
	b.Position = pos
	b.BackgroundColor3 = color
	b.Text = text
	b.Font = Enum.Font.GothamBold
	b.TextColor3 = Ui.C.navy
	b.TextScaled = true
	b.AutoButtonColor = true
	Ui.round(b, 12)
	local c = Instance.new("UISizeConstraint")
	c.MinSize = Vector2.new(Ui.MIN_TOUCH, Ui.MIN_TOUCH)
	c.Parent = b
	b.Activated:Connect(onClick)
	b.Parent = parent
	return b
end

return Ui
