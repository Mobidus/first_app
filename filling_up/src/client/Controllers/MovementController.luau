--!strict
-- Shared controller for every player (no paid movement advantage): normalized walk speed and jump
-- height from config, coyote time 0.12 s, jump buffer 0.12 s, basic ledge recovery. The assist
-- never jumps by itself: it only honours a jump the player pressed slightly early / late.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.GeneratedConfig)

local P = Config.Runtime.player

local MovementController = {}

local lastGrounded = -math.huge
local lastJumpPress = -math.huge
local glideMultiplier: number? = nil
local glideUntil = 0
local stepConn: RBXScriptConnection? = nil

function MovementController.setGlide(mult: number, duration: number)
	glideMultiplier = mult
	glideUntil = os.clock() + duration
end

local function bind(character: Model)
	local hum = character:WaitForChild("Humanoid") :: Humanoid
	local root = character:WaitForChild("HumanoidRootPart") :: BasePart
	hum.UseJumpPower = false
	hum.WalkSpeed = P.walk_speed_studs_s
	hum.JumpHeight = P.jump_height_studs
	workspace.Gravity = P.gravity_studs_s2
	hum.StateChanged:Connect(function(_, new)
		if new == Enum.HumanoidStateType.Landed or new == Enum.HumanoidStateType.Running then
			lastGrounded = os.clock()
			-- jump buffer: a press within 0.12 s before landing is honoured
			if os.clock() - lastJumpPress <= P.jump_buffer_seconds then
				lastJumpPress = -math.huge
				hum:ChangeState(Enum.HumanoidStateType.Jumping)
			end
		end
	end)
	if stepConn then
		stepConn:Disconnect() -- one per character: no pile-up across respawns
	end
	stepConn = RunService.RenderStepped:Connect(function()
		if hum.FloorMaterial ~= Enum.Material.Air then
			lastGrounded = os.clock()
		end
		-- umbrella glide (server-approved effect): caps descent speed only, never pushes up
		if glideMultiplier and os.clock() < glideUntil then
			local v = root.AssemblyLinearVelocity
			local cap = -math.sqrt(2 * P.gravity_studs_s2 * P.jump_height_studs) * glideMultiplier
			if v.Y < cap then
				root.AssemblyLinearVelocity = Vector3.new(v.X, cap, v.Z)
			end
		else
			glideMultiplier = nil
		end
		-- basic ledge recovery: if chest-high on a ledge edge while rising/falling slowly toward it
		if hum.FloorMaterial == Enum.Material.Air and hum.MoveDirection.Magnitude > 0.5 then
			local params = RaycastParams.new()
			params.FilterType = Enum.RaycastFilterType.Exclude
			params.FilterDescendantsInstances = { character }
			params.RespectCanCollide = true -- ignore query-only volumes such as ExitClearance
			local ahead = hum.MoveDirection * 1.6
			local hitChest = workspace:Raycast(root.Position, ahead, params)
			local hitHead = workspace:Raycast(root.Position + Vector3.new(0, 1.6, 0), ahead, params)
			if hitChest and not hitHead and root.AssemblyLinearVelocity.Y < 6 then
				local v = root.AssemblyLinearVelocity
				root.AssemblyLinearVelocity = Vector3.new(v.X, 14, v.Z)
			end
		end
	end)
end

function MovementController.start()
	UserInputService.JumpRequest:Connect(function()
		local char = Players.LocalPlayer.Character
		local hum = char and char:FindFirstChildOfClass("Humanoid")
		if not hum then
			return
		end
		lastJumpPress = os.clock()
		-- coyote time: a jump pressed up to 0.12 s after leaving a ledge still counts
		if hum.FloorMaterial == Enum.Material.Air and os.clock() - lastGrounded <= P.coyote_time_seconds then
			lastGrounded = -math.huge
			hum:ChangeState(Enum.HumanoidStateType.Jumping)
		end
	end)
	local plr = Players.LocalPlayer
	if plr.Character then
		bind(plr.Character)
	end
	plr.CharacterAdded:Connect(bind)
end

return MovementController
