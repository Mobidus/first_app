--!strict
-- T06 MovementLab: measures the REAL controller (R15 normalized body, config walk/jump/gravity).
-- For each (rise, gap) pair a take-off and a landing platform are built; an NPC rig built from a
-- default HumanoidDescription runs to the edge and jumps (Humanoid.Jump). Success = lands on the
-- target top. Output: table { rise, reach } to feed JumpModel.setMeasuredTable and
-- reports/movement_calibration.json. Mobile touch checks are manual (see README).
local Players = game:GetService("Players")
local Harness = require(script.Parent:WaitForChild("StudioHarness"))
if not Harness.selected("movement") then
	return
end
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.GeneratedConfig)
local P = Config.Runtime.player

local s = Harness.suite("movement")
workspace.Gravity = P.gravity_studs_s2

local function platform(pos: Vector3, size: Vector3): Part
	local p = Instance.new("Part")
	p.Anchored = true
	p.Size = size
	p.Position = pos
	p.Parent = workspace
	return p
end

local function rig(): Model
	local desc = Instance.new("HumanoidDescription")
	local m = Players:CreateHumanoidModelFromDescription(desc, Enum.HumanoidRigType.R15)
	local hum = m:FindFirstChildOfClass("Humanoid") :: Humanoid
	hum.UseJumpPower = false
	hum.JumpHeight = P.jump_height_studs
	hum.WalkSpeed = P.walk_speed_studs_s
	m.Parent = workspace
	return m
end

local rows = {}
for _, rise in { -4, 0, 1, 2, 3, 4, 5, 5.4, 6, 7 } do
	local best = 0
	for gap = 2, 12, 0.5 do
		local origin = Vector3.new(0, 50, gap * 40 + rise * 400)
		local a = platform(origin, Vector3.new(10, 1, 10))
		local b = platform(origin + Vector3.new(0, rise, 5 + gap + 5), Vector3.new(10, 1, 10))
		local npc = rig()
		npc:PivotTo(CFrame.new(origin + Vector3.new(0, 3.5, -3)))
		local hum = npc:FindFirstChildOfClass("Humanoid") :: Humanoid
		local root = npc:WaitForChild("HumanoidRootPart") :: BasePart
		task.wait(0.5)
		hum:MoveTo(b.Position + Vector3.new(0, 1, 0))
		local jumped = false
		local t0 = os.clock()
		while os.clock() - t0 < 3 do
			if not jumped and root.Position.Z >= a.Position.Z + 4.6 then
				hum.Jump = true
				jumped = true
			end
			task.wait()
		end
		local rel = b.CFrame:PointToObjectSpace(root.Position)
		local landed = math.abs(rel.X) < 5 and math.abs(rel.Z) < 5 and rel.Y > 0 and rel.Y < 5
		if landed then
			best = gap
		end
		npc:Destroy()
		a:Destroy()
		b:Destroy()
	end
	table.insert(rows, { rise = rise, reach = best })
	Harness.record(s, string.format("reach at rise %.1f = %.1f studs", rise, best), "PASS", { rise = rise, reach = best })
end
Harness.expect(s, "flat reach is positive", rows[2].reach > 0, rows)
Harness.record(s, "mobile touch jump / camera (manual on devices)", "NOT_RUN")
Harness.record(s, "avatar shapes (R15 scales) normalised (manual)", "NOT_RUN")
Harness.finish(s)
