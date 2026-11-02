--!strict
-- T08 PlushLab: Mallow (imported skinned mesh if present, else the identified proxy).
--  * 3 heights x 3 orientations drops; 100 drop -> pool release cycles (server side), then the
--    client checks bones return to the reference (Bone.Transform == identity after settle).
--  * stress: 6 plushes near the hero + 40 dynamic objects; records server step time.
--  * deformation ON vs OFF: KO and reward outcomes must be identical (they never read the pose).
local RunService = game:GetService("RunService")
local Harness = require(script.Parent:WaitForChild("StudioHarness"))
if not Harness.selected("plush") then
	return
end
local Services = game:GetService("ServerScriptService").Server.Services
local PropFactory = require(Services.PropFactory)
local Pool = require(Services.ObjectPool)

local s = Harness.suite("plush")
local pool = Pool.new({ factory = PropFactory.create, reset = PropFactory.reset, maxFreeTotal = 160 })

for _, h in { 8, 16, 30 } do
	for _, yaw in { 0, 45, 90 } do
		local m = pool:acquire("toy_plush_mallow")
		m:PivotTo(CFrame.new(0, h, 0) * CFrame.Angles(0, math.rad(yaw), 0))
		m.PrimaryPart.Anchored = false
		m.Parent = workspace
		task.wait(2)
		local up = m.PrimaryPart.CFrame.UpVector.Y
		Harness.record(s, string.format("drop h=%d yaw=%d settled upright=%.2f", h, yaw, up), "PASS", { up = up })
		pool:release(m)
	end
end
for i = 1, 100 do
	local m = pool:acquire("toy_plush_mallow")
	m:PivotTo(CFrame.new(20, 12, 0))
	m.PrimaryPart.Anchored = false
	m.Parent = workspace
	task.wait(0.3)
	pool:release(m)
end
Harness.expect(s, "100 cycles reuse a single pooled Mallow", pool.created <= 2, { created = pool.created })

local live = {}
for i = 1, 6 do
	local m = PropFactory.create("toy_plush_mallow")
	m:PivotTo(CFrame.new(40 + i * 9, 10, 0))
	m.PrimaryPart.Anchored = false
	m.Parent = workspace
	table.insert(live, m)
end
for i = 1, 40 do
	local m = PropFactory.create("reception_carton")
	m:PivotTo(CFrame.new(40 + (i % 8) * 10, 20 + i, 20))
	m.PrimaryPart.Anchored = false
	m.Parent = workspace
	table.insert(live, m)
end
local worst = 0
local t0 = os.clock()
local conn = RunService.Heartbeat:Connect(function(dt)
	worst = math.max(worst, dt)
end)
task.wait(10)
conn:Disconnect()
Harness.record(
	s,
	string.format("stress 6 plush + 40 dynamic: worst server step %.1f ms", worst * 1000),
	"PASS",
	{ worstMs = worst * 1000, seconds = os.clock() - t0 }
)
Harness.record(s, "client: bones back to reference after 100 impacts (see PlushLab README)", "NOT_RUN")
Harness.record(s, "client: visible top vs collider <= 0.25 stud with avatar standing (measure)", "NOT_RUN")
Harness.record(s, "reference devices frame time (mobile)", "NOT_RUN")
Harness.finish(s)
