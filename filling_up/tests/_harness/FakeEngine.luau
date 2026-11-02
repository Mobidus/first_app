--!nocheck
-- FakeEngine: a small, explicit stand-in for the Roblox ENGINE so that the real server scripts
-- (Main.server, ExpeditionService, RoomGenerator, WaveDirector, BurialService, ExitService,
-- Remotes, PropFactory, repositories...) can be EXECUTED end to end under Lune.
--
-- What it emulates: an instance tree (Parent/children, attributes, tags, Destroy, PivotTo),
-- signals (Connect/Once/Wait, handlers in their own threads), Heartbeat driven by `step(dt)`,
-- axis-aligned spatial queries (Raycast, GetPartBoundsInBox, GetPartsInPart), Players with
-- characters, TweenService (completes on the next scheduler tick), CollectionService, HttpService,
-- an in-memory DataStoreService with UpdateAsync semantics, MarketplaceService, RemoteEvents
-- (FireClient is logged) and RemoteFunctions (OnServerInvoke callable by the test).
-- What it does NOT emulate: physics, gravity, collisions, rendering, network, real timing. Results
-- from it are "fake-engine integration" evidence, never a substitute for Roblox Studio.
local roblox = require("@lune/roblox")
local task = require("@lune/task")

local Vector3, CFrame, Enum = roblox.Vector3, roblox.CFrame, roblox.Enum
local ZERO = Vector3.new(0, 0, 0)

local FakeEngine = {}

------------------------------------------------------------------------------------------------
-- Signals
------------------------------------------------------------------------------------------------
local Signal = {}
Signal.__index = Signal

local function newConnection(signal)
	local c = { __fakeConnection = true, Connected = true }
	function c.Disconnect(self)
		self.Connected = false
	end
	return c
end

function Signal.new()
	return setmetatable({ conns = {}, waiting = {} }, Signal)
end

function Signal.Connect(self, fn)
	local c = newConnection(self)
	c.fn = fn
	table.insert(self.conns, c)
	return c
end

function Signal.Once(self, fn)
	local c
	c = self:Connect(function(...)
		c:Disconnect()
		fn(...)
	end)
	return c
end

function Signal.Wait(self)
	table.insert(self.waiting, coroutine.running())
	return coroutine.yield()
end

function Signal.Fire(self, ...)
	local live = {}
	for _, c in self.conns do
		if c.Connected then
			table.insert(live, c)
		end
	end
	self.conns = live
	for _, c in table.clone(live) do
		if c.Connected then
			task.spawn(c.fn, ...)
		end
	end
	local w = self.waiting
	self.waiting = {}
	for _, th in w do
		task.spawn(th, ...)
	end
end

function Signal.liveCount(self)
	local n = 0
	for _, c in self.conns do
		if c.Connected then
			n += 1
		end
	end
	return n
end

FakeEngine.Signal = Signal

------------------------------------------------------------------------------------------------
-- Instances
------------------------------------------------------------------------------------------------
local ISA = {
	Part = { "Part", "BasePart", "PVInstance", "Instance" },
	MeshPart = { "MeshPart", "BasePart", "PVInstance", "Instance" },
	Model = { "Model", "PVInstance", "Instance" },
	Workspace = { "Workspace", "WorldRoot", "Model", "PVInstance", "Instance" },
	Folder = { "Folder", "Instance" },
	Humanoid = { "Humanoid", "Instance" },
	Player = { "Player", "Instance" },
	RemoteEvent = { "RemoteEvent", "Instance" },
	RemoteFunction = { "RemoteFunction", "Instance" },
	WeldConstraint = { "WeldConstraint", "Instance" },
	Decal = { "Decal", "Instance" },
	Bone = { "Bone", "Instance" },
	Highlight = { "Highlight", "Instance" },
}

local Inst = {}
local InstMeta = {}

local function isFake(v)
	return type(v) == "table" and rawget(v, "__fake") == true
end
FakeEngine.isFake = isFake

local function defaults(className)
	local p = { Archivable = true }
	local isa = ISA[className] or { className, "Instance" }
	if table.find(isa, "BasePart") then
		p.Size = Vector3.new(4, 1, 2)
		p.CFrame = CFrame.identity
		p.Anchored = false
		p.CanCollide = true
		p.CanQuery = true
		p.CanTouch = true
		p.Transparency = 0
		p.Massless = false
		p.AssemblyLinearVelocity = ZERO
		p.AssemblyAngularVelocity = ZERO
		p.Material = Enum.Material.Plastic
		p.Shape = Enum.PartType.Block
	end
	if className == "Humanoid" then
		p.FloorMaterial = Enum.Material.Plastic
		p.MoveDirection = ZERO
		p.WalkSpeed = 16
		p.JumpHeight = 7.2
		p.UseJumpPower = false
		p.Health = 100
	end
	return p, isa
end

local engine -- current engine (one at a time)

function Inst.new(className)
	local props, isa = defaults(className)
	local self = setmetatable({
		__fake = true,
		ClassName = className,
		_isa = isa,
		_name = className,
		_parent = nil,
		_children = {},
		_attrs = {},
		_tags = {},
		_props = props,
		_destroyed = false,
		_signals = {},
	}, InstMeta)
	if engine then
		engine.created += 1
		if className == "RemoteFunction" then
			table.insert(engine.remoteFunctions, self)
		end
	end
	return self
end

local function signalOf(self, name)
	local s = rawget(self, "_signals")[name]
	if not s then
		s = Signal.new()
		rawget(self, "_signals")[name] = s
	end
	return s
end

local function setParent(self, parent)
	local old = rawget(self, "_parent")
	if old == parent then
		return
	end
	if isFake(old) then
		local list = rawget(old, "_children")
		local i = table.find(list, self)
		if i then
			table.remove(list, i)
		end
	end
	rawset(self, "_parent", parent)
	if isFake(parent) then
		table.insert(rawget(parent, "_children"), self)
	end
end

local function descendants(self, out)
	for _, c in rawget(self, "_children") do
		table.insert(out, c)
		descendants(c, out)
	end
	return out
end

local function rootOf(self)
	local node = self
	while isFake(node) and rawget(node, "_parent") ~= nil do
		node = rawget(node, "_parent")
	end
	return node
end

local function pivotOf(self)
	if table.find(rawget(self, "_isa"), "BasePart") then
		return rawget(self, "_props").CFrame
	end
	local pp = rawget(self, "_props").PrimaryPart
	if pp then
		return rawget(pp, "_props").CFrame
	end
	for _, d in descendants(self, {}) do
		if table.find(rawget(d, "_isa"), "BasePart") then
			return rawget(d, "_props").CFrame
		end
	end
	return CFrame.identity
end

local METHODS = {}

function METHODS.GetChildren(self)
	return table.clone(rawget(self, "_children"))
end
function METHODS.GetDescendants(self)
	return descendants(self, {})
end
function METHODS.FindFirstChild(self, name, recursive)
	for _, c in (if recursive then descendants(self, {}) else rawget(self, "_children")) do
		if rawget(c, "_name") == name then
			return c
		end
	end
	return nil
end
function METHODS.FindFirstChildOfClass(self, className)
	for _, c in rawget(self, "_children") do
		if c.ClassName == className then
			return c
		end
	end
	return nil
end
function METHODS.FindFirstChildWhichIsA(self, className)
	for _, c in rawget(self, "_children") do
		if table.find(rawget(c, "_isa"), className) then
			return c
		end
	end
	return nil
end
function METHODS.WaitForChild(self, name, timeout)
	local deadline = os.clock() + (timeout or 5)
	while true do
		local c = METHODS.FindFirstChild(self, name)
		if c or os.clock() > deadline then
			return c
		end
		task.wait()
	end
end
function METHODS.IsA(self, className)
	return table.find(rawget(self, "_isa"), className) ~= nil
end
function METHODS.IsDescendantOf(self, other)
	local node = rawget(self, "_parent")
	while node ~= nil do
		if node == other then
			return true
		end
		node = if isFake(node) then rawget(node, "_parent") else nil
	end
	return false
end
function METHODS.Destroy(self)
	if rawget(self, "_destroyed") then
		return
	end
	for _, c in table.clone(rawget(self, "_children")) do
		METHODS.Destroy(c)
	end
	setParent(self, nil)
	rawset(self, "_destroyed", true)
	for tag in rawget(self, "_tags") do
		if engine then
			engine.CollectionService:RemoveTag(self, tag)
		end
	end
	for _, s in rawget(self, "_signals") do
		for _, c in s.conns do
			c.Connected = false
		end
	end
	if engine then
		engine.destroyed += 1
	end
end
function METHODS.ClearAllChildren(self)
	for _, c in table.clone(rawget(self, "_children")) do
		METHODS.Destroy(c)
	end
end
function METHODS.SetAttribute(self, k, v)
	rawget(self, "_attrs")[k] = v
end
function METHODS.GetAttribute(self, k)
	return rawget(self, "_attrs")[k]
end
function METHODS.GetAttributes(self)
	return table.clone(rawget(self, "_attrs"))
end
function METHODS.AddTag(self, tag)
	engine.CollectionService:AddTag(self, tag)
end
function METHODS.RemoveTag(self, tag)
	engine.CollectionService:RemoveTag(self, tag)
end
function METHODS.HasTag(self, tag)
	return rawget(self, "_tags")[tag] == true
end
function METHODS.GetTags(self)
	local out = {}
	for t in rawget(self, "_tags") do
		table.insert(out, t)
	end
	return out
end
function METHODS.GetFullName(self)
	local parts = {}
	local node = self
	while isFake(node) do
		table.insert(parts, 1, rawget(node, "_name"))
		node = rawget(node, "_parent")
	end
	return table.concat(parts, ".")
end
function METHODS.GetPivot(self)
	return pivotOf(self)
end
function METHODS.PivotTo(self, cf)
	local delta = cf * pivotOf(self):Inverse()
	if table.find(rawget(self, "_isa"), "BasePart") then
		rawget(self, "_props").CFrame = cf
	end
	for _, d in descendants(self, {}) do
		if table.find(rawget(d, "_isa"), "BasePart") then
			local p = rawget(d, "_props")
			p.CFrame = delta * p.CFrame
		end
	end
end
function METHODS.SetNetworkOwner(self, _owner)
	if rawget(self, "_props").Anchored then
		error("SetNetworkOwner: cannot be called on anchored parts")
	end
end
function METHODS.GetPropertyChangedSignal(self, prop)
	return signalOf(self, "Changed:" .. prop)
end
function METHODS.Clone(self)
	local c = Inst.new(self.ClassName)
	rawset(c, "_name", rawget(self, "_name"))
	for k, v in rawget(self, "_props") do
		rawget(c, "_props")[k] = v
	end
	for k, v in rawget(self, "_attrs") do
		rawget(c, "_attrs")[k] = v
	end
	for _, ch in rawget(self, "_children") do
		METHODS.Clone(ch).Parent = c
	end
	return c
end
-- Player / RemoteEvent helpers
function METHODS.Kick(self, message)
	rawset(self, "kickMessage", message or "")
	if engine then
		engine:removePlayer(self)
	end
end
function METHODS.FireClient(self, player, payload)
	table.insert(engine.remoteLog, { event = rawget(self, "_name"), player = player, payload = payload })
end
function METHODS.FireAllClients(self, payload)
	table.insert(engine.remoteLog, { event = rawget(self, "_name"), player = "all", payload = payload })
end
function METHODS.ChangeState(_self, _state) end

local SIGNAL_NAMES = {
	Touched = true,
	CharacterAdded = true,
	Changed = true,
	Destroying = true,
	StateChanged = true,
	OnClientEvent = true,
	OnServerEvent = true,
}

InstMeta.__index = function(self, k)
	if k == "Name" then
		return rawget(self, "_name")
	elseif k == "Parent" then
		return rawget(self, "_parent")
	end
	local m = METHODS[k]
	if m then
		return m
	end
	if SIGNAL_NAMES[k] then
		return signalOf(self, k)
	end
	local props = rawget(self, "_props")
	if k == "Position" and props.CFrame then
		return props.CFrame.Position
	end
	local v = props[k]
	if v ~= nil then
		return v
	end
	-- child lookup (Roblox: instance.ChildName)
	for _, c in rawget(self, "_children") do
		if rawget(c, "_name") == k then
			return c
		end
	end
	if engine then
		engine.unknownReads[rawget(self, "ClassName") .. "." .. tostring(k)] = true
	end
	return nil
end

InstMeta.__newindex = function(self, k, v)
	if k == "Parent" then
		assert(not rawget(self, "_destroyed"), "The Parent property of " .. rawget(self, "_name") .. " is locked (destroyed)")
		setParent(self, v)
	elseif k == "Name" then
		rawset(self, "_name", v)
	elseif k == "Position" then
		local p = rawget(self, "_props")
		local cf = p.CFrame or CFrame.identity
		p.CFrame = CFrame.new(v) * (cf - cf.Position)
	else
		local p = rawget(self, "_props")
		p[k] = v
		local s = rawget(self, "_signals")["Changed:" .. k]
		if s then
			s:Fire()
		end
	end
end
InstMeta.__tostring = function(self)
	return rawget(self, "_name")
end

------------------------------------------------------------------------------------------------
-- Spatial queries (axis-aligned bounding boxes of oriented parts)
------------------------------------------------------------------------------------------------
local function aabb(cf, size)
	local hx = math.abs(cf.XVector.X) * size.X / 2 + math.abs(cf.YVector.X) * size.Y / 2 + math.abs(cf.ZVector.X) * size.Z / 2
	local hy = math.abs(cf.XVector.Y) * size.X / 2 + math.abs(cf.YVector.Y) * size.Y / 2 + math.abs(cf.ZVector.Y) * size.Z / 2
	local hz = math.abs(cf.XVector.Z) * size.X / 2 + math.abs(cf.YVector.Z) * size.Y / 2 + math.abs(cf.ZVector.Z) * size.Z / 2
	local c = cf.Position
	return c.X - hx, c.Y - hy, c.Z - hz, c.X + hx, c.Y + hy, c.Z + hz
end

local function newParams()
	return { FilterType = Enum.RaycastFilterType.Exclude, FilterDescendantsInstances = {}, RespectCanCollide = false, MaxParts = 0 }
end
FakeEngine.RaycastParams = { new = newParams }
FakeEngine.OverlapParams = { new = newParams }

local function passes(part, params)
	local p = rawget(part, "_props")
	if not p.CanQuery then
		return false
	end
	if params and params.RespectCanCollide and not p.CanCollide then
		return false
	end
	if not params then
		return true
	end
	local inList = false
	for _, inst in params.FilterDescendantsInstances or {} do
		if inst == part or (isFake(inst) and METHODS.IsDescendantOf(part, inst)) then
			inList = true
			break
		end
	end
	if params.FilterType == Enum.RaycastFilterType.Include then
		return inList
	end
	return not inList
end

local function worldParts(ws)
	local out = {}
	for _, d in descendants(ws, {}) do
		if table.find(rawget(d, "_isa"), "BasePart") then
			table.insert(out, d)
		end
	end
	return out
end

local function rayBox(o, d, x0, y0, z0, x1, y1, z1)
	local tmin, tmax = 0, 1
	for axis = 1, 3 do
		local oo = if axis == 1 then o.X elseif axis == 2 then o.Y else o.Z
		local dd = if axis == 1 then d.X elseif axis == 2 then d.Y else d.Z
		local lo = if axis == 1 then x0 elseif axis == 2 then y0 else z0
		local hi = if axis == 1 then x1 elseif axis == 2 then y1 else z1
		if math.abs(dd) < 1e-12 then
			if oo < lo or oo > hi then
				return nil
			end
		else
			local t1, t2 = (lo - oo) / dd, (hi - oo) / dd
			if t1 > t2 then
				t1, t2 = t2, t1
			end
			tmin = math.max(tmin, t1)
			tmax = math.min(tmax, t2)
			if tmin > tmax then
				return nil
			end
		end
	end
	return tmin
end

------------------------------------------------------------------------------------------------
-- Engine
------------------------------------------------------------------------------------------------
function FakeEngine.new(opts)
	opts = opts or {}
	local E = {
		clock = 0,
		created = 0,
		destroyed = 0,
		remoteLog = {},
		unknownReads = {},
		players = {},
		nextUser = 1,
		closeHandlers = {},
		datastore = {},
		datastoreFail = false,
		warnings = {},
		remoteFunctions = {},
	}
	engine = E
	local function service(className)
		local s = Inst.new(className)
		rawset(s, "_name", className)
		return s
	end

	-- Workspace
	local ws = service("Workspace")
	ws.Gravity = 196.2
	function ws.GetServerTimeNow()
		return E.clock
	end
	function ws.Raycast(_, origin, direction, params)
		local best, bestT
		for _, part in worldParts(ws) do
			if passes(part, params) then
				local p = rawget(part, "_props")
				local t = rayBox(origin, direction, aabb(p.CFrame, p.Size))
				if t and (bestT == nil or t < bestT) then
					best, bestT = part, t
				end
			end
		end
		if best then
			return {
				Instance = best,
				Position = origin + direction * bestT,
				Distance = direction.Magnitude * bestT,
				Normal = Vector3.new(0, 1, 0),
			}
		end
		return nil
	end
	function ws.GetPartBoundsInBox(_, cf, size, params)
		local qx0, qy0, qz0, qx1, qy1, qz1 = aabb(cf, size)
		local out = {}
		for _, part in worldParts(ws) do
			if passes(part, params) then
				local p = rawget(part, "_props")
				local x0, y0, z0, x1, y1, z1 = aabb(p.CFrame, p.Size)
				if x0 < qx1 and x1 > qx0 and y0 < qy1 and y1 > qy0 and z0 < qz1 and z1 > qz0 then
					table.insert(out, part)
				end
			end
		end
		return out
	end
	function ws.GetPartsInPart(self, part, params)
		local p = rawget(part, "_props")
		local out = {}
		for _, other in ws.GetPartBoundsInBox(self, p.CFrame, p.Size, params) do
			if other ~= part then
				table.insert(out, other)
			end
		end
		return out
	end
	E.Workspace = ws

	-- RunService
	local run = service("RunService")
	rawget(run, "_props").Heartbeat = Signal.new()
	rawget(run, "_props").RenderStepped = Signal.new()
	rawget(run, "_props").Stepped = Signal.new()
	function run.IsStudio()
		return true
	end
	function run.IsServer()
		return true
	end
	E.RunService = run

	-- CollectionService
	local cs = { tagged = {}, added = {}, removed = {} }
	local function sig(map, tag)
		map[tag] = map[tag] or Signal.new()
		return map[tag]
	end
	function cs.AddTag(_, inst, tag)
		if rawget(inst, "_tags")[tag] then
			return
		end
		rawget(inst, "_tags")[tag] = true
		cs.tagged[tag] = cs.tagged[tag] or {}
		cs.tagged[tag][inst] = true
		sig(cs.added, tag):Fire(inst)
	end
	function cs.RemoveTag(_, inst, tag)
		if not rawget(inst, "_tags")[tag] then
			return
		end
		rawget(inst, "_tags")[tag] = nil
		if cs.tagged[tag] then
			cs.tagged[tag][inst] = nil
		end
		sig(cs.removed, tag):Fire(inst)
	end
	function cs.HasTag(_, inst, tag)
		return rawget(inst, "_tags")[tag] == true
	end
	function cs.GetTagged(_, tag)
		local out = {}
		for inst in cs.tagged[tag] or {} do
			-- like Roblox: only instances inside the DataModel (parented under a service)
			if not rawget(inst, "_destroyed") and rootOf(inst) == ws then
				table.insert(out, inst)
			end
		end
		return out
	end
	function cs.GetInstanceAddedSignal(_, tag)
		return sig(cs.added, tag)
	end
	function cs.GetInstanceRemovedSignal(_, tag)
		return sig(cs.removed, tag)
	end
	E.CollectionService = cs

	-- TweenService: completes on the next scheduler tick
	local tweens = {
		Create = function(_, inst, _info, goal)
			local tw = { Completed = Signal.new() }
			function tw.Play()
				task.defer(function()
					for k, v in goal do
						inst[k] = v
					end
					tw.Completed:Fire(Enum.PlaybackState.Completed)
				end)
			end
			function tw.Cancel() end
			return tw
		end,
	}

	-- HttpService
	local guid = 0
	local http = {
		GenerateGUID = function(_, _wrap)
			guid += 1
			return string.format("%08x-0000-4000-8000-%012x", 0xA0000000 + guid, guid)
		end,
		JSONEncode = function(_, v)
			return require("@lune/serde").encode("json", v)
		end,
	}

	-- DataStoreService (UpdateAsync semantics: transform returning nil cancels)
	local function deepCopy(v)
		if type(v) ~= "table" then
			return v
		end
		local o = {}
		for k, x in v do
			o[k] = deepCopy(x)
		end
		return o
	end
	local dss = {
		GetDataStore = function(_, name)
			return {
				UpdateAsync = function(_, key, transform)
					if E.datastoreFail then
						error("502: API Services rejected request (fake outage)")
					end
					task.wait() -- the real call yields
					local full = name .. "/" .. key
					local new = transform(deepCopy(E.datastore[full]))
					if new ~= nil then
						E.datastore[full] = deepCopy(new)
					end
					return deepCopy(E.datastore[full])
				end,
			}
		end,
	}

	-- MarketplaceService
	local market = { ProcessReceipt = nil }

	-- Players
	local players = service("Players")
	rawget(players, "_props").PlayerAdded = Signal.new()
	rawget(players, "_props").PlayerRemoving = Signal.new()
	function players.GetPlayers()
		local out = {}
		for _, p in E.players do
			table.insert(out, p)
		end
		return out
	end
	function players.GetPlayerByUserId(_, id)
		for _, p in E.players do
			if p.UserId == id then
				return p
			end
		end
		return nil
	end
	E.Players = players

	E.services = {
		Workspace = ws,
		RunService = run,
		CollectionService = cs,
		TweenService = tweens,
		HttpService = http,
		DataStoreService = dss,
		MarketplaceService = market,
		Players = players,
	}
	E.Marketplace = market

	local base = opts.baseGame
	E.game = {
		JobId = "fake-engine-job",
		PlaceVersion = 0,
		Workspace = ws,
		GetService = function(_, name)
			return E.services[name] or base:GetService(name)
		end,
		BindToClose = function(_, fn)
			table.insert(E.closeHandlers, fn)
		end,
	}

	local function fakeTypeof(v)
		if isFake(v) then
			return "Instance"
		elseif type(v) == "table" and rawget(v, "__fakeConnection") then
			return "RBXScriptConnection"
		end
		return typeof(v)
	end

	-- task library on the SIMULATED clock (delay / wait advance with step(), not wall time)
	E.timers = {}
	local simTask = {
		spawn = task.spawn,
		defer = task.defer,
		cancel = task.cancel,
		delay = function(t, fn, ...)
			local args = { ... }
			table.insert(E.timers, { at = E.clock + (t or 0), fn = fn, args = args })
		end,
		wait = function(t)
			if t == nil or t <= 0 then
				task.wait()
				return 0
			end
			table.insert(E.timers, { at = E.clock + t, thread = coroutine.running() })
			return coroutine.yield()
		end,
	}
	E.task = simTask

	E.env = {
		task = simTask,
		game = E.game,
		workspace = ws,
		Instance = { new = Inst.new },
		Enum = Enum,
		PhysicalProperties = roblox.PhysicalProperties,
		TweenInfo = {
			new = function(t, style, dir)
				return { Time = t or 1, EasingStyle = style, EasingDirection = dir }
			end,
		},
		RaycastParams = FakeEngine.RaycastParams,
		OverlapParams = FakeEngine.OverlapParams,
		typeof = fakeTypeof,
		warn = function(...)
			table.insert(E.warnings, table.concat({ ... }, " "))
		end,
	}

	-- driver -------------------------------------------------------------------------------
	function E.step(self, seconds, dt)
		dt = dt or 1 / 30
		local n = math.max(1, math.floor(seconds / dt + 0.5))
		for _ = 1, n do
			self.clock += dt
			local due, keep = {}, {}
			for _, t in self.timers do
				if t.at <= self.clock then
					table.insert(due, t)
				else
					table.insert(keep, t)
				end
			end
			self.timers = keep
			for _, t in due do
				if t.thread then
					task.spawn(t.thread, dt)
				else
					task.spawn(t.fn, table.unpack(t.args))
				end
			end
			rawget(run, "_props").Heartbeat:Fire(dt)
			task.wait() -- let deferred work and resumed threads run
		end
	end

	function E.addPlayer(self, userId)
		local p = Inst.new("Player")
		rawset(p, "_name", "Player" .. userId)
		rawget(p, "_props").UserId = userId
		rawget(p, "_props").Character = nil
		p.Parent = players
		table.insert(self.players, p)
		self:spawnCharacter(p)
		rawget(players, "_props").PlayerAdded:Fire(p)
		return p
	end

	function E.spawnCharacter(_self, player)
		local char = Inst.new("Model")
		rawset(char, "_name", player.Name)
		local root = Inst.new("Part")
		rawset(root, "_name", "HumanoidRootPart")
		root.Size = Vector3.new(2, 2, 1)
		root.CFrame = CFrame.new(0, 3, 0)
		root.Parent = char
		local hum = Inst.new("Humanoid")
		hum.Parent = char
		char.PrimaryPart = root
		char.Parent = ws
		rawget(player, "_props").Character = char
		signalOf(player, "CharacterAdded"):Fire(char)
		return char
	end

	function E.removePlayer(self, player)
		local i = table.find(self.players, player)
		if not i then
			return
		end
		table.remove(self.players, i)
		rawget(players, "_props").PlayerRemoving:Fire(player)
		local char = player.Character
		if char then
			char:Destroy()
		end
		setParent(player, nil)
	end

	-- place a character so that its FEET are at world position `feet` (root is 3 studs above)
	function E.placeFeet(_self, player, feet, grounded)
		local char = player.Character
		char:PivotTo(CFrame.new(feet + Vector3.new(0, 3, 0)))
		local hum = char:FindFirstChildOfClass("Humanoid")
		hum.FloorMaterial = if grounded == false then Enum.Material.Air else Enum.Material.Plastic
	end

	function E.events(self, player, name)
		local out = {}
		for _, e in self.remoteLog do
			if e.player == player and (name == nil or e.event == name) then
				table.insert(out, e.payload)
			end
		end
		return out
	end

	function E.lastState(self, player)
		local states = self:events(player, "State")
		return states[#states]
	end

	function E.hud(self, player, kind)
		local out = {}
		for _, p in self:events(player, "Hud") do
			if kind == nil or p.type == kind then
				table.insert(out, p)
			end
		end
		return out
	end

	function E.invoke(self, player, name, ...)
		for _, rf in self.remoteFunctions do
			if rawget(rf, "_name") == "Intent" then
				return rawget(rf, "_props").OnServerInvoke(player, name, { ... })
			end
		end
		error("Intent RemoteFunction not created")
	end

	function E.heartbeatConnections(_self)
		return rawget(run, "_props").Heartbeat:liveCount()
	end

	return E
end

return FakeEngine
