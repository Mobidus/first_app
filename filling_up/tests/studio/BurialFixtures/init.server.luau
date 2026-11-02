--!strict
-- T09 burial reference scenes, evaluated by the REAL BurialService probes + BurialLogic:
--   1 true burial (fill all around and above)   -> KO expected after 1.2 s
--   2 under an open table (roof, open sides)     -> no KO
--   3 object passing overhead                    -> no KO
--   4 moving platform under the avatar           -> no KO
--   5 near the exit with clear sides             -> no KO
-- An anchored NPC stands in for the player; probes use FillCollider-tagged parts only.
local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local Harness = require(script.Parent:WaitForChild("StudioHarness"))
if not Harness.selected("burial") then
	return
end
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Burial = require(Shared.Domain.BurialLogic)
local BurialService = require(game:GetService("ServerScriptService").Server.Services.BurialService)

local s = Harness.suite("burial")
local svc = BurialService.new()

local function fill(pos: Vector3, size: Vector3): Part
	local p = Instance.new("Part")
	p.Anchored = true
	p.Size = size
	p.Position = pos
	CollectionService:AddTag(p, "FillCollider")
	p.Parent = workspace
	return p
end

local function npcAt(pos: Vector3): (Model, BasePart)
	local m = Players:CreateHumanoidModelFromDescription(Instance.new("HumanoidDescription"), Enum.HumanoidRigType.R15)
	m:PivotTo(CFrame.new(pos))
	m.Parent = workspace
	local root = m:WaitForChild("HumanoidRootPart") :: BasePart
	root.Anchored = true
	return m, root
end

local function runScene(name: string, build: (Vector3) -> { Instance }, expectKO: boolean, seconds: number)
	local origin = Vector3.new(#s.results * 60, 20, 0)
	local parts = build(origin)
	local npc, root = npcAt(origin + Vector3.new(0, 3, 0))
	task.wait(0.2)
	local tracker = Burial.new()
	local ko = false
	local t = 0
	while t < seconds do
		local sample = svc:probe(root)
		sample.inKillVolume = false
		sample.roomActive = true
		sample.secondsSinceSpawn = 100
		local ev = Burial.step(tracker, sample, Burial.SAMPLE_DT)
		if ev == "ko_burial" then
			ko = true
		end
		task.wait(Burial.SAMPLE_DT)
		t += Burial.SAMPLE_DT
	end
	Harness.expect(s, name, ko == expectKO, { ko = ko })
	npc:Destroy()
	for _, p in parts do
		p:Destroy()
	end
end

runScene("true burial -> KO", function(o)
	local list = {}
	for x = -1, 1 do
		for z = -1, 1 do
			if not (x == 0 and z == 0) then
				table.insert(list, fill(o + Vector3.new(x * 2.6, 3, z * 2.6), Vector3.new(2.6, 6, 2.6)))
			end
		end
	end
	table.insert(list, fill(o + Vector3.new(0, 7.2, 0), Vector3.new(9, 2, 9)))
	return list
end, true, 3)
runScene("open table -> no KO", function(o)
	return { fill(o + Vector3.new(0, 6.5, 0), Vector3.new(10, 1, 10)) }
end, false, 5)
runScene("transient overhead object -> no KO", function(o)
	local p = fill(o + Vector3.new(0, 7, 0), Vector3.new(4, 1, 4))
	task.delay(0.6, function()
		p:Destroy()
	end)
	return {}
end, false, 4)
runScene("clear sides near exit -> no KO", function(o)
	return { fill(o + Vector3.new(6, 2, 0), Vector3.new(2, 4, 8)) }
end, false, 4)
Harness.record(s, "moving platform under avatar (manual scene)", "NOT_RUN")
Harness.finish(s)
svc:destroy()
