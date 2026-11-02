--!strict
-- Radar POP (first tool, T12 vertical slice). Server picks up to 3 usable surfaces in range from
-- the CURRENT room supports (anchored, not buried, head clearance free) and tells the client which
-- ones to highlight for the configured duration. It never moves the avatar.
local Workspace = game:GetService("Workspace")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Tools = require(Shared.Domain.ToolRules)

local StarterRadar = {}

StarterRadar.ID = "radar_pop"

local function clearAbove(col: BasePart): boolean
	local params = OverlapParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { col.Parent :: Instance }
	local box = col.CFrame * CFrame.new(0, col.Size.Y / 2 + 3, 0)
	return #Workspace:GetPartBoundsInBox(box, Vector3.new(3, 5.5, 3), params) == 0
end

-- candidates from the room model: every prop collider currently anchored
function StarterRadar.candidates(roomModel: Model): { any }
	local out = {}
	for _, m in roomModel:GetChildren() do
		if m:IsA("Model") and m.PrimaryPart and m:GetAttribute("PropId") then
			local col = m.PrimaryPart :: BasePart
			local top = col.Position + Vector3.new(0, col.Size.Y / 2, 0)
			table.insert(out, {
				id = m:GetAttribute("ObjectInstanceId") or m:GetFullName(),
				x = top.X,
				y = top.Y,
				z = top.Z,
				usable = col.Anchored and clearAbove(col),
				buried = col:HasTag("FillAggregate"),
				model = m,
			})
		end
	end
	return out
end

function StarterRadar.resolve(effect: any, rootPos: Vector3, roomModel: Model): { Model }
	local cands = StarterRadar.candidates(roomModel)
	local ids = Tools.radarTargets({ x = rootPos.X, y = rootPos.Y, z = rootPos.Z }, cands, effect.stats)
	local models = {}
	for _, id in ids do
		for _, c in cands do
			if c.id == id then
				table.insert(models, c.model)
			end
		end
	end
	return models
end

return StarterRadar
