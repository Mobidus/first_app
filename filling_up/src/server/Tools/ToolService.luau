--!strict
-- Generalises the StarterRadar protocol to the other MVP tools (catalogue order): intent ->
-- ToolRules.check (ownership, slot, charges, cooldown, range, target, room state) -> commit ->
-- effect. Refusals never consume a charge. V1 tools stay "unavailable" until implemented.
local CollectionService = game:GetService("CollectionService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Tools = require(Shared.Domain.ToolRules)
local StarterRadar = require(script.Parent.StarterRadar)

local ToolService = {}
ToolService.__index = ToolService

function ToolService.new(telemetry: any)
	return setmetatable({ telemetry = telemetry, states = {} :: { [Player]: any } }, ToolService)
end

function ToolService.enterRoom(self, player: Player, profile: any, roomInstanceId: string, snapshot: { [string]: number }?)
	self.states[player] = Tools.enterRoom(self.states[player] or Tools.newState(), profile, roomInstanceId, snapshot)
end

function ToolService.charges(self, player: Player): { [string]: number }
	local s = self.states[player]
	return s and table.clone(s.charges) or {}
end

local function resolveTarget(roomModel: Model?, targetId: string): any?
	if not roomModel or targetId == "" then
		return nil
	end
	for _, m in roomModel:GetChildren() do
		if m:IsA("Model") and m:GetAttribute("ObjectInstanceId") == targetId and m.PrimaryPart then
			local col = m.PrimaryPart :: BasePart
			local size = col.Size
			local volume = size.X * size.Y * size.Z
			return {
				id = targetId,
				model = m,
				x = col.Position.X,
				y = col.Position.Y,
				z = col.Position.Z,
				stabilizable = col:HasTag("Stabilizable") or not col.Anchored,
				structural = col:HasTag("Architecture") or m:GetAttribute("Structural") == true,
				protectedRoute = col:HasTag("RouteSupport"),
				isExit = col:HasTag("ExitTrigger") or col:HasTag("ExitClearance"),
				sizeClass = if volume <= 150 then 1 elseif volume <= 400 then 2 else 3,
				buried = col:HasTag("FillAggregate"),
			}
		end
	end
	return nil
end

-- ctx: { profile, roomState, inSas, now, roomModel }
function ToolService.use(self, player: Player, toolId: string, targetId: string, ctx: any): any
	local state = self.states[player] or Tools.newState()
	local root = player.Character and player.Character:FindFirstChild("HumanoidRootPart") :: BasePart?
	if not root then
		return { ok = false, error = "no_character" }
	end
	local hum = player.Character and player.Character:FindFirstChildOfClass("Humanoid")
	local useCtx = {
		profile = ctx.profile,
		roomState = ctx.roomState,
		inSas = ctx.inSas,
		now = ctx.now,
		player = {
			x = root.Position.X,
			y = root.Position.Y,
			z = root.Position.Z,
			vy = root.AssemblyLinearVelocity.Y,
			grounded = hum ~= nil and hum.FloorMaterial ~= Enum.Material.Air,
		},
		target = resolveTarget(ctx.roomModel, targetId),
	}
	local ok, effect = Tools.check(state, toolId, useCtx)
	if not ok then
		return { ok = false, error = effect }
	end
	self.states[player] = Tools.commit(state, effect, ctx.now)
	local payload: any =
		{ ok = true, toolId = toolId, kind = effect.kind, duration = effect.duration, charges = self.states[player].charges[toolId] }
	if effect.kind == "highlight" then
		payload.targets = StarterRadar.resolve(effect, root.Position, ctx.roomModel)
	elseif effect.kind == "stabilize" then
		local target = useCtx.target
		local col = target.model.PrimaryPart :: BasePart
		local wasAnchored = col.Anchored
		col.Anchored = true
		task.delay(effect.duration, function()
			if col.Parent and not wasAnchored and not col:HasTag("RouteSupport") then
				col.Anchored = false
			end
		end)
		payload.targetId = target.id
	elseif effect.kind == "glide" then
		payload.descentMultiplier = effect.descentMultiplier
	end
	self.telemetry:event(tostring(player.UserId), "tool_use", { toolId = toolId, kind = effect.kind })
	return payload
end

function ToolService.forget(self, player: Player)
	self.states[player] = nil
end

-- tokens attracted by the passive magnet (server decides; claim goes through RewardService)
function ToolService.magnetTokens(profile: any, rootPos: Vector3, tokens: { any }, mask: number, bit0: number): { number }
	return Tools.magnetPull(profile, { x = rootPos.X, y = rootPos.Y, z = rootPos.Z }, tokens, mask, bit0)
end

ToolService.CollectionService = CollectionService
return ToolService
