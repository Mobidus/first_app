--!strict
-- Immediate visual feedback: wave warnings (coral triangle zone under the mouth, before impact),
-- Radar highlights (mint outline, removed after the configured duration). Purely visual.
local Debris = game:GetService("Debris")

local Net = require(script.Parent.Parent.Net)

local EffectsController = {}

function EffectsController.start()
	Net.on("WaveWarning", function(e)
		if typeof(e.mouth) ~= "CFrame" then
			return
		end
		local zone = Instance.new("Part")
		zone.Name = "WaveWarning"
		zone.Anchored = true
		zone.CanCollide = false
		zone.CanQuery = false
		zone.Size = Vector3.new(e.size.X, 0.2, e.size.Z)
		zone.CFrame = CFrame.new(e.mouth.Position.X, e.mouth.Position.Y - 0.6, e.mouth.Position.Z)
		zone.Color = Color3.fromHex("#FF684B")
		zone.Material = Enum.Material.Neon
		zone.Transparency = 0.35
		local sign = Instance.new("BillboardGui")
		sign.Size = UDim2.new(0, 64, 0, 64)
		sign.AlwaysOnTop = true
		local tri = Instance.new("TextLabel")
		tri.Size = UDim2.new(1, 0, 1, 0)
		tri.BackgroundTransparency = 1
		tri.Text = "▲"
		tri.TextScaled = true
		tri.TextColor3 = Color3.fromHex("#FF684B")
		tri.Parent = sign
		sign.Parent = zone
		zone.Parent = workspace
		Debris:AddItem(zone, math.max(0.2, e.impactIn) + 0.3)
	end)
	Net.on("ToolEffect", function(e)
		if e.kind ~= "highlight" then
			return
		end
		for _, m in e.targets or {} do
			if typeof(m) == "Instance" then
				local h = Instance.new("Highlight")
				h.FillTransparency = 0.7
				h.FillColor = Color3.fromHex("#39E68B")
				h.OutlineColor = Color3.fromHex("#39E68B")
				h.Parent = m
				Debris:AddItem(h, e.duration)
			end
		end
	end)
end

return EffectsController
