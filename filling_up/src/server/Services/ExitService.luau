--!strict
-- Validates exits from SERVER-known positions (root inside the exit trigger volume, plus the
-- lever for low exits). Touched alone is not trusted. Requests a single transition per room.
local RunService = game:GetService("RunService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Maid = require(Shared.Util.Maid)

local ExitService = {}
ExitService.__index = ExitService

local function inside(part: BasePart, pos: Vector3, margin: number): boolean
	local rel = part.CFrame:PointToObjectSpace(pos)
	local s = part.Size
	return math.abs(rel.X) <= s.X / 2 + margin and math.abs(rel.Y) <= s.Y / 2 + margin and math.abs(rel.Z) <= s.Z / 2 + margin
end

-- onExit(player) is called at most once for this room instance.
function ExitService.arm(player: Player, index: any, onExit: (Player) -> (), onLever: ((Player) -> ())?)
	local maid = Maid.new()
	local fired = false
	local leverDown = index.lever == nil
	maid:give(RunService.Heartbeat:Connect(function()
		if fired then
			return
		end
		local root = player.Character and player.Character:FindFirstChild("HumanoidRootPart") :: BasePart?
		if not root then
			return
		end
		if not leverDown and index.lever and inside(index.lever, root.Position, 2.5) then
			leverDown = true
			if onLever then
				onLever(player)
			end
		end
		if leverDown and index.exitZone and inside(index.exitZone, root.Position, 1) then
			fired = true
			onExit(player)
		end
	end))
	return maid
end

return ExitService
