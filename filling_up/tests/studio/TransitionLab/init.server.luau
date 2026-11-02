--!strict
-- T10 TransitionLab: 100 room transitions through the real RoomGenerator + WaveDirector, counting
-- instances under the expedition folder and live connections (Maid.globalLive) after each commit.
-- Pass: counts return to a plateau (no permanent growth), <= 3 resident modules.
local Harness = require(script.Parent:WaitForChild("StudioHarness"))
if not Harness.selected("transitions") then
	return
end
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Maid = require(Shared.Util.Maid)
local Services = game:GetService("ServerScriptService").Server.Services
local RoomGenerator = require(Services.RoomGenerator)
local WaveDirector = require(Services.WaveDirector)

local s = Harness.suite("transitions")
local folder = Instance.new("Folder")
folder.Name = "TransitionLab"
folder.Parent = workspace
local samples = {}
local active = nil
for depth = 1, 100 do
	local def = RoomGenerator.plan(depth, 4242, {}, "mvp")
	local cell = RoomGenerator.CELLS[(depth % 2) + 1]
	local model, index = RoomGenerator.build(def, cell, folder)
	local dir = WaveDirector.new(
		def,
		index,
		cell,
		model,
		depth,
		{ warn = function() end, plushImpact = function() end, diagnostic = function() end }
	)
	dir:start()
	task.wait(2)
	if active then
		active.dir:destroy()
		active.model:Destroy()
	end
	active = { dir = dir, model = model }
	table.insert(
		samples,
		{ depth = depth, instances = #folder:GetDescendants(), maidLive = Maid.globalLive, poolInUse = WaveDirector.pool:inUseCount() }
	)
end
local first, last = samples[10], samples[#samples]
Harness.expect(s, "instances plateau (last <= 1.5 x sample 10)", last.instances <= first.instances * 1.5, samples)
Harness.expect(s, "live connections plateau", last.maidLive <= first.maidLive + 5, { first = first.maidLive, last = last.maidLive })
Harness.record(s, "delayed next-room load keeps player safe in sas (manual)", "NOT_RUN")
Harness.finish(s)
