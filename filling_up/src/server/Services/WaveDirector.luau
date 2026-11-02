--!strict
-- Drives the waves of the ONE active room (docs/05 §7). Time = active simulation seconds
-- accumulated from Heartbeat dt (a slow client cannot accelerate waves). The director announces,
-- drops, consolidates and recycles; it never decides a KO.
local CollectionService = game:GetService("CollectionService")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.GeneratedConfig)
local Wave = require(Shared.Domain.WaveSchedule)
local Consolidation = require(Shared.Domain.Consolidation)
local RoomPlan = require(Shared.Domain.RoomPlan)
local Maid = require(Shared.Util.Maid)
local Pool = require(script.Parent.ObjectPool)
local PropFactory = require(script.Parent.PropFactory)

local WaveDirector = {}
WaveDirector.__index = WaveDirector

local DROP_HEIGHT_BELOW_CEILING = 2
local CONSOLIDATE_EVERY = 0.5
local SETTLE_SPEED = 0.6

local sharedPool = Pool.new({
	factory = function(kind: string)
		return PropFactory.create(kind)
	end,
	reset = PropFactory.reset,
	destroy = function(m)
		m:Destroy()
	end,
	-- keep up to one full active-room fill budget in reserve (no churn between rooms)
	maxFreeTotal = Config.Runtime.streaming.max_fill_colliders_active_room,
})
WaveDirector.pool = sharedPool

export type Hooks = {
	warn: (info: any) -> (),
	plushImpact: (event: any) -> (),
	diagnostic: (name: string, data: any) -> (),
}

function WaveDirector.new(room: any, index: any, cell: CFrame, roomModel: Model, depth: number, hooks: Hooks)
	local self = setmetatable({}, WaveDirector)
	self.room = room
	self.index = index
	self.cell = cell
	self.model = roomModel
	self.hooks = hooks
	self.schedule = Wave.new(room, RoomPlan.FAMILIES[room.familyId], math.max(depth, 1))
	self.simTime = 0
	self.nextWave = 1
	self.warned = {}
	self.objects = {} :: { [Model]: any }
	self.deferred = {} :: { any }
	self.maid = Maid.new()
	self.running = false
	self.lastConsolidate = 0
	self.serial = 0
	return self
end

function WaveDirector.start(self)
	if self.running then
		return
	end
	self.running = true
	self.maid:give(RunService.Heartbeat:Connect(function(dt)
		self:step(dt)
	end))
end

local function playersStandingOn(model: Model): boolean
	local collider = model.PrimaryPart
	if not collider then
		return false
	end
	for _, plr in game:GetService("Players"):GetPlayers() do
		local char = plr.Character
		local hum = char and char:FindFirstChildOfClass("Humanoid")
		if char and hum and hum.FloorMaterial ~= Enum.Material.Air then
			local root = char:FindFirstChild("HumanoidRootPart") :: BasePart?
			if root then
				local rel = collider.CFrame:PointToObjectSpace(root.Position)
				local s = collider.Size
				if math.abs(rel.X) <= s.X / 2 + 1 and math.abs(rel.Z) <= s.Z / 2 + 1 and rel.Y > 0 and rel.Y < s.Y / 2 + 4 then
					return true
				end
			end
		end
	end
	return false
end

function WaveDirector.spawnDrop(self, drop: any, _impactTime: number)
	local m = sharedPool:acquire(drop.propId)
	self.serial += 1
	local id = string.format("%s:%d", self.room.templateId, self.serial)
	m:SetAttribute("ObjectInstanceId", id)
	local col = m.PrimaryPart :: BasePart
	local y = self.room.size.h - DROP_HEIGHT_BELOW_CEILING - col.Size.Y / 2
	local cf = self.cell * CFrame.new(drop.x, y, drop.z) * CFrame.Angles(0, math.rad(drop.yaw), 0)
	if drop.structural then
		-- structural support: guided descent onto its validated slot, then anchored
		local slot = self.index.structuralSlots[drop.nodeId]
		m:PivotTo(slot.cframe + Vector3.new(0, self.room.size.h * 0.6, 0))
		col.Anchored = true
		m:SetAttribute("Structural", true)
		CollectionService:AddTag(col, "RouteSupport")
		m.Parent = self.model
		local TweenService = game:GetService("TweenService")
		local tween =
			TweenService:Create(col, TweenInfo.new(0.55, Enum.EasingStyle.Quad, Enum.EasingDirection.In), { CFrame = slot.cframe })
		tween.Completed:Once(function()
			self.hooks.plushImpact({
				objectInstanceId = id,
				serverTime = Workspace:GetServerTimeNow(),
				impactNormal = { x = 0, y = 1, z = 0 },
				impactStrength = 1,
				settleState = "impact",
				model = m,
			})
		end)
		tween:Play()
		self.objects[m] = { id = id, dynamic = false, settledFor = 99, age = 0, structural = true }
		return
	end
	m:PivotTo(cf)
	col.Anchored = false
	m.Parent = self.model
	pcall(function()
		col:SetNetworkOwner(nil) -- server-authoritative fill physics
	end)
	local entry = { id = id, dynamic = true, settledFor = 0, age = 0, impacted = false }
	self.objects[m] = entry
	if m:HasTag("Plush") then
		self.maid:give(col.Touched:Connect(function(other)
			if entry.impacted or other:IsDescendantOf(m) then
				return
			end
			entry.impacted = true
			local speed = col.AssemblyLinearVelocity.Magnitude
			self.hooks.plushImpact({
				objectInstanceId = id,
				serverTime = Workspace:GetServerTimeNow(),
				impactNormal = { x = 0, y = 1, z = 0 },
				impactStrength = math.clamp(speed / 50, 0, 1),
				settleState = "impact",
				model = m,
			})
		end))
	end
end

local function coveredOnAllSides(col: BasePart, params: OverlapParams): boolean
	local s = col.Size
	local probes = {
		{ CFrame.new(0, s.Y / 2 + 1, 0), Vector3.new(s.X * 0.8, 1.5, s.Z * 0.8) },
		{ CFrame.new(s.X / 2 + 1, 0, 0), Vector3.new(1.5, s.Y * 0.8, s.Z * 0.8) },
		{ CFrame.new(-s.X / 2 - 1, 0, 0), Vector3.new(1.5, s.Y * 0.8, s.Z * 0.8) },
		{ CFrame.new(0, 0, s.Z / 2 + 1), Vector3.new(s.X * 0.8, s.Y * 0.8, 1.5) },
		{ CFrame.new(0, 0, -s.Z / 2 - 1), Vector3.new(s.X * 0.8, s.Y * 0.8, 1.5) },
	}
	for _, pr in probes do
		local hits = Workspace:GetPartBoundsInBox(col.CFrame * pr[1], pr[2], params)
		local other = false
		for _, h in hits do
			if not h:IsDescendantOf(col.Parent :: Instance) then
				other = true
				break
			end
		end
		if not other then
			return false
		end
	end
	return true
end

function WaveDirector.consolidate(self)
	local fillParams = OverlapParams.new()
	fillParams.FilterType = Enum.RaycastFilterType.Include
	local fill = {}
	for _, tag in { "FillCollider", "FillAggregate" } do
		for _, inst in CollectionService:GetTagged(tag) do
			table.insert(fill, inst)
		end
	end
	fillParams.FilterDescendantsInstances = fill
	local list = {}
	local byId = {}
	local dynCount = 0
	for m, e in self.objects do
		local col = m.PrimaryPart
		if col == nil then
			continue
		end
		local occupied = playersStandingOn(m)
		local buried = false
		if not col.Anchored then
			dynCount += 1
		elseif not occupied then
			-- buried = top AND all four sides covered by other FILL colliders (architecture, shelves,
			-- ceiling and the exit clearance never count): only then is it unreachable
			buried = e.age > 20 and coveredOnAllSides(col, fillParams)
		end
		table.insert(list, {
			id = e.id,
			dynamic = not col.Anchored,
			settledFor = e.settledFor,
			occupied = occupied,
			routeSupport = col:HasTag("RouteSupport"),
			buried = buried,
			age = e.age,
		})
		byId[e.id] = m
	end
	local plan = Consolidation.plan(list)
	for _, id in plan.anchor do
		local m = byId[id]
		if m and m.PrimaryPart then
			m.PrimaryPart.Anchored = true
			CollectionService:AddTag(m.PrimaryPart, "Stabilizable")
		end
	end
	for _, id in plan.merge do
		local m = byId[id]
		if m and m.PrimaryPart then
			CollectionService:AddTag(m.PrimaryPart, "FillAggregate")
		end
	end
	for _, id in plan.recycle do
		local m = byId[id]
		if m then
			self.objects[m] = nil
			sharedPool:release(m)
		end
	end
	self.allowance = plan.spawnAllowance
end

-- Objects that rolled into the protected exit clearance are recycled (never obstruct the exit).
function WaveDirector.sweepClearance(self)
	local clr = self.index.clearance :: BasePart?
	if not clr then
		return
	end
	local params = OverlapParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { self.model }
	for _, part in Workspace:GetPartsInPart(clr, params) do
		if part.Name == "Collider" and part.Parent and part.Parent:IsA("Model") and not part:HasTag("RouteSupport") then
			local m = part.Parent :: Model
			if self.objects[m] then
				self.objects[m] = nil
				sharedPool:release(m)
				self.hooks.diagnostic("clearance_swept", { id = m:GetAttribute("ObjectInstanceId") })
			end
		end
	end
end

function WaveDirector.step(self, dt: number)
	if not self.running then
		return
	end
	self.simTime += dt
	-- settle tracking
	for m, e in self.objects do
		e.age += dt
		local col = m.PrimaryPart
		if col and not col.Anchored then
			if col.AssemblyLinearVelocity.Magnitude < SETTLE_SPEED then
				e.settledFor += dt
			else
				e.settledFor = 0
			end
		end
	end
	-- announcements, always before impact
	local upcoming = Wave.at(self.schedule, self.nextWave)
	if not self.warned[upcoming.index] and self.simTime >= upcoming.warningTime then
		self.warned[upcoming.index] = true
		self.hooks.warn({
			index = upcoming.index,
			mouthIndex = upcoming.mouthIndex,
			impactIn = upcoming.impactTime - self.simTime,
			drops = upcoming.drops,
		})
	end
	if self.simTime >= upcoming.impactTime then
		for _, drop in upcoming.drops do
			table.insert(self.deferred, drop)
		end
		self.warned[upcoming.index] = nil
		self.nextWave += 1
	end
	if self.simTime - self.lastConsolidate >= CONSOLIDATE_EVERY then
		self.lastConsolidate = self.simTime
		self:consolidate()
		self:sweepClearance()
	end
	local allowance = self.allowance or 40
	while #self.deferred > 0 and (allowance > 0 or self.deferred[1].structural) do
		local drop = table.remove(self.deferred, 1)
		self:spawnDrop(drop, self.simTime)
		allowance -= 1
	end
	self.allowance = allowance
end

function WaveDirector.dynamicCount(self): number
	local n = 0
	for m in self.objects do
		if m.PrimaryPart and not m.PrimaryPart.Anchored then
			n += 1
		end
	end
	return n
end

function WaveDirector.stop(self)
	self.running = false
	self.maid:clean()
end

-- Release everything (room teardown after a committed transition).
function WaveDirector.destroy(self)
	self:stop()
	for m in self.objects do
		sharedPool:release(m)
	end
	table.clear(self.objects)
	table.clear(self.deferred)
end

return WaveDirector
