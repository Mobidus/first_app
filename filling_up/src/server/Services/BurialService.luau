--!strict
-- Server burial detection at 10 Hz (docs/05 §8). Probes ONLY FillCollider/FillAggregate parts:
-- 5 overhead rays, 8 lateral rays, then a gabarit-compatible escape test (GetPartBoundsInBox at
-- several free-direction offsets). The decision itself is BurialLogic (pure, unit-tested).
local CollectionService = game:GetService("CollectionService")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.GeneratedConfig)
local Burial = require(Shared.Domain.BurialLogic)
local Maid = require(Shared.Util.Maid)

local B = Config.Runtime.burial

local BurialService = {}
BurialService.__index = BurialService

local AVATAR = Vector3.new(2, 5, 1.5)

local function fillInstances(): { Instance }
	local list = {}
	for _, tag in B.valid_tags do
		for _, inst in CollectionService:GetTagged(tag) do
			table.insert(list, inst)
		end
	end
	return list
end

export type Watch = { player: Player, tracker: any, spawnedAt: number, isActive: () -> boolean, onEvent: (string, any) -> () }

function BurialService.new()
	local self = setmetatable({}, BurialService)
	self.watches = {} :: { [Player]: Watch }
	self.maid = Maid.new()
	self.accum = 0
	self.rayParams = RaycastParams.new()
	self.rayParams.FilterType = Enum.RaycastFilterType.Include
	self.overlap = OverlapParams.new()
	self.overlap.FilterType = Enum.RaycastFilterType.Include
	self.dirty = true
	for _, tag in B.valid_tags do
		self.maid:give(CollectionService:GetInstanceAddedSignal(tag):Connect(function()
			self.dirty = true
		end))
		self.maid:give(CollectionService:GetInstanceRemovedSignal(tag):Connect(function()
			self.dirty = true
		end))
	end
	self.maid:give(RunService.Heartbeat:Connect(function(dt)
		self.accum += dt
		while self.accum >= Burial.SAMPLE_DT do
			self.accum -= Burial.SAMPLE_DT
			self:sampleAll()
		end
	end))
	return self
end

function BurialService.watch(self, player: Player, isActive: () -> boolean, onEvent: (string, any) -> ())
	self.watches[player] =
		{ player = player, tracker = Burial.new(), spawnedAt = Workspace:GetServerTimeNow(), isActive = isActive, onEvent = onEvent }
end

function BurialService.resetSpawn(self, player: Player)
	local w = self.watches[player]
	if w then
		w.tracker = Burial.new()
		w.spawnedAt = Workspace:GetServerTimeNow()
	end
end

function BurialService.unwatch(self, player: Player)
	self.watches[player] = nil
end

function BurialService.probe(self, root: BasePart): any
	local head = root.Position + Vector3.new(0, 1.5, 0)
	local over, lat = 0, 0
	local reach = B.near_clearance_studs
	-- overhead: centre + 4 offsets
	for i = 0, B.overhead_probe_count - 1 do
		local offset = if i == 0 then Vector3.zero else Vector3.new(math.cos(i * math.pi / 2) * 0.8, 0, math.sin(i * math.pi / 2) * 0.8)
		local origin = head + offset
		if Workspace:Raycast(origin, Vector3.new(0, 1 + reach, 0), self.rayParams) then
			over += 1
		end
	end
	-- lateral ring around the torso
	for i = 0, B.lateral_probe_count - 1 do
		local a = i * 2 * math.pi / B.lateral_probe_count
		local dir = Vector3.new(math.cos(a), 0, math.sin(a))
		if Workspace:Raycast(root.Position, dir * (1 + reach), self.rayParams) then
			lat += 1
		end
	end
	-- escape: is there a gabarit-sized free box next to / above the avatar?
	local escape = false
	for _, off in
		{ Vector3.new(0, 2.5, 0), Vector3.new(2.2, 0.5, 0), Vector3.new(-2.2, 0.5, 0), Vector3.new(0, 0.5, 2.2), Vector3.new(0, 0.5, -2.2) }
	do
		local parts = Workspace:GetPartBoundsInBox(CFrame.new(root.Position + off), AVATAR, self.overlap)
		if #parts == 0 then
			escape = true
			break
		end
	end
	return {
		overheadProbes = B.overhead_probe_count,
		overheadHits = over,
		lateralProbes = B.lateral_probe_count,
		lateralHits = lat,
		escapeAvailable = escape,
	}
end

local function inKillVolume(root: BasePart): boolean
	for _, v in CollectionService:GetTagged("KillVolume") do
		if v:IsA("BasePart") then
			local rel = v.CFrame:PointToObjectSpace(root.Position)
			if math.abs(rel.X) <= v.Size.X / 2 and math.abs(rel.Y) <= v.Size.Y / 2 and math.abs(rel.Z) <= v.Size.Z / 2 then
				return true
			end
		end
	end
	return false
end

function BurialService.sampleAll(self)
	if self.dirty then
		local list = fillInstances()
		self.rayParams.FilterDescendantsInstances = list
		self.overlap.FilterDescendantsInstances = list
		self.dirty = false
	end
	for player, w in self.watches do
		local char = player.Character
		local root = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
		if not root then
			continue
		end
		local s = self:probe(root :: BasePart)
		s.inKillVolume = inKillVolume(root :: BasePart)
		s.roomActive = w.isActive()
		s.secondsSinceSpawn = Workspace:GetServerTimeNow() - w.spawnedAt
		local ev = Burial.step(w.tracker, s, Burial.SAMPLE_DT)
		if ev then
			w.onEvent(ev, s)
		end
	end
end

function BurialService.destroy(self)
	self.maid:clean()
end

return BurialService
