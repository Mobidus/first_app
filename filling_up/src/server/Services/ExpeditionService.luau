--!strict
-- Expedition orchestrator (docs/05 §3): create, change room, suspend, KO, extract. Owns per-player
-- sessions and wires the pure domain (state machine, rewards, residency, checkpoints) to engine
-- services (RoomGenerator, WaveDirector, BurialService, ExitService, ToolService).
-- Rules enforced here: no room timer, no room cap, exit -> sas -> next room without a menu,
-- KO keeps every possession, free restart at depth 1, rebirth only in the sas.
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.GeneratedConfig)
local Machine = require(Shared.Domain.ExpeditionStateMachine)
local Residency = require(Shared.Domain.RoomResidency)
local RoomPlan = require(Shared.Domain.RoomPlan)
local Rewards = require(Shared.Domain.Rewards)
local Tutorial = require(Shared.Domain.Tutorial)
local Checkpoint = require(Shared.Domain.Checkpoint)
local Rng = require(Shared.Util.Rng)
local Maid = require(Shared.Util.Maid)

local RoomGenerator = require(script.Parent.RoomGenerator)
local WaveDirector = require(script.Parent.WaveDirector)
local ExitService = require(script.Parent.ExitService)
local PropFactory = require(script.Parent.PropFactory)

local ExpeditionService = {}
ExpeditionService.__index = ExpeditionService

local RELEASE_PROFILE = "mvp"
local MILESTONE_HZ = 10
local TOKEN_PICK_RADIUS = 2.5

function ExpeditionService.new(deps: any)
	local self = setmetatable({}, ExpeditionService)
	self.repo = deps.repo
	self.remotes = deps.remotes
	self.rewards = deps.rewards
	self.inventory = deps.inventory
	self.rebirth = deps.rebirth
	self.checkpoints = deps.checkpoints
	self.tools = deps.tools
	self.burial = deps.burial
	self.telemetry = deps.telemetry
	self.sessions = {} :: { [Player]: any }
	self.slots = {} :: { [number]: boolean }
	self.worldFolder = Instance.new("Folder")
	self.worldFolder.Name = "Expeditions"
	self.worldFolder.Parent = Workspace
	return self
end

local function userKeyOf(player: Player): string
	return tostring(player.UserId)
end

function ExpeditionService.push(self, s: any)
	local p = self.repo:get(s.userKey)
	if not p then
		return
	end
	self.remotes.fire(s.player, "State", {
		coins = p.coins,
		permits = p.permits,
		xp = p.xp,
		level = (Rewards.levelForXp(p.xp)),
		rebirthCount = p.rebirthCount,
		bestDepth = p.bestDepth,
		loadout = p.equippedLoadout,
		ownedTools = p.ownedTools,
		toolRanks = p.toolRanks,
		ownedCosmetics = p.ownedCosmetics,
		settings = p.settings,
		phase = s.exp and s.exp.state or "Tutorial",
		depth = s.exp and s.exp.depth or 0,
		family = s.room and s.room.def.familyId or "reception",
		inSas = s.inSas,
		kiosk = s.kiosk,
		charges = self.tools:charges(s.player),
		catalog = if s.inSas or s.kiosk then self.inventory.catalog(p) else nil,
		tutorialComplete = Tutorial.isComplete(p.tutorialFlags),
	})
end

local function spawnAt(player: Player, cf: CFrame)
	local char = player.Character or player.CharacterAdded:Wait()
	local root = char:WaitForChild("HumanoidRootPart", 10) :: BasePart?
	if root then
		root.AssemblyLinearVelocity = Vector3.zero
		char:PivotTo(cf + Vector3.new(0, 3, 0))
	end
end

------------------------------------------------------------------------------------------------
-- Sas (safe transition room): equipment kiosk, save terminal, rebirth machine, exit door.
------------------------------------------------------------------------------------------------
local function buildSas(parent: Instance, cell: CFrame, canRebirth: boolean): (Model, BasePart)
	local m = Instance.new("Model")
	m.Name = "Sas"
	local function part(name: string, size: Vector3, offset: Vector3, color: string, collide: boolean?)
		local p = Instance.new("Part")
		p.Name = name
		p.Anchored = true
		p.Size = size
		p.CFrame = cell * CFrame.new(offset)
		p.Color = Color3.fromHex(color)
		p.CanCollide = collide ~= false
		p.Parent = m
		return p
	end
	part("Floor", Vector3.new(24, 1, 16), Vector3.new(0, -0.5, 0), "#FFF5DF")
	part("WallS", Vector3.new(24, 12, 1), Vector3.new(0, 6, -8.5), "#203055")
	part("WallW", Vector3.new(1, 12, 16), Vector3.new(-12.5, 6, 0), "#203055")
	part("WallE", Vector3.new(1, 12, 16), Vector3.new(12.5, 6, 0), "#203055")
	part("Ceiling", Vector3.new(24, 1, 16), Vector3.new(0, 12.5, 0), "#203055")
	local kiosk = part("EquipKiosk", Vector3.new(3, 5, 2), Vector3.new(-8, 2.5, -4), "#16D9FF")
	kiosk:SetAttribute("Kiosk", "equipment")
	local save = part("SaveTerminal", Vector3.new(2, 4, 2), Vector3.new(8, 2, -4), "#39E68B")
	save:SetAttribute("Kiosk", "save")
	if canRebirth then
		local rb = part("RebirthMachine", Vector3.new(4, 6, 3), Vector3.new(0, 3, -6), "#8855FF")
		rb:SetAttribute("Kiosk", "rebirth")
	end
	-- north wall closed on both sides of the 8-stud door (no way to walk off the floor)
	part("WallN_L", Vector3.new(8, 12, 1), Vector3.new(-8, 6, 8.5), "#203055")
	part("WallN_R", Vector3.new(8, 12, 1), Vector3.new(8, 6, 8.5), "#203055")
	part("Floor_Door", Vector3.new(8, 1, 6), Vector3.new(0, -0.5, 11), "#FFF5DF")
	-- straight ahead: the door to the next room (continuing requires no menu)
	local door = part("ContinueDoor", Vector3.new(8, 10, 1), Vector3.new(0, 5, 8.5), "#39E68B", false)
	door.Transparency = 0.5
	door.Material = Enum.Material.Neon
	m.Parent = parent
	return m, door
end

------------------------------------------------------------------------------------------------
-- Sessions
------------------------------------------------------------------------------------------------
function ExpeditionService.playerAdded(self, player: Player)
	local userKey = userKeyOf(player)
	local ok, profile, notes = self.repo:load(userKey)
	if not ok then
		self.telemetry:event(userKey, "profile_load_failed", { reason = profile })
		player:Kick(
			if profile == "session_locked"
				then "Profil ouvert sur un autre serveur. Réessaie dans un instant."
				else "Sauvegarde indisponible : réessaie plus tard."
		)
		return
	end
	if player.Parent == nil then
		-- left while the profile was loading: release the lock instead of keeping it 30 min
		self.repo:release(userKey)
		return
	end
	local slot = 0
	while self.slots[slot] do
		slot += 1
	end
	self.slots[slot] = true
	local s = {
		player = player,
		userKey = userKey,
		slot = slot,
		cells = RoomGenerator.cellsFor(slot),
		removed = false,
		claiming = false,
		txBusy = false,
		tutorialGranted = {},
		pendingCompletion = nil,
		pendingResume = nil,
		exp = nil,
		residency = Residency.new(),
		rooms = {},
		room = nil,
		roomCtx = nil,
		history = {},
		inSas = false,
		kiosk = false,
		maid = Maid.new(),
		roomMaid = nil,
		tutorial = Tutorial.newSession(),
		sas = nil,
		lastSaveOk = false,
		nextRoom = nil,
	}
	self.sessions[player] = s
	self.telemetry:event(userKey, "session_start", { migration = notes })
	-- the character usually spawned while the profile was loading: never wait for a NEXT spawn
	if not player.Character then
		player.CharacterAdded:Wait()
	end
	if s.removed then
		return
	end
	-- respawn (reset button, fall below the world): back to the current safe place, same room
	s.maid:give(player.CharacterAdded:Connect(function()
		task.defer(function()
			self:respawnInPlace(s)
		end)
	end))
	if not Tutorial.isComplete(profile.tutorialFlags) then
		self:startTutorial(s)
		return
	end
	local plan = Checkpoint.plan(profile.checkpoint, Config.configVersion)
	if plan.mode == "resume" then
		self.telemetry:event(userKey, "resume", { depth = plan.params.depth })
		self:startRun(s, plan.params)
	else
		if plan.mode == "extracted" then
			self.checkpoints:clear(userKey)
			self.remotes.fire(player, "Hud", { type = "notice", key = "checkpoint_incompatible" })
		end
		self:enterSas(s, nil, { fresh = true })
	end
end

function ExpeditionService.playerRemoving(self, player: Player)
	local s = self.sessions[player]
	if not s then
		return
	end
	-- mark first: pending retries and Heartbeat callbacks must stop before any yield below
	s.removed = true
	s.inSas = false
	self.sessions[player] = nil
	self.slots[s.slot] = nil
	self:teardownRoom(s, s.room)
	if s.nextRoom then
		self:teardownRoom(s, s.nextRoom)
	end
	if s.sas then
		s.sas:Destroy()
	end
	s.maid:clean()
	self.burial:unwatch(player)
	self.tools:forget(player)
	self.remotes.forget(player)
	self.repo:release(s.userKey)
end

function ExpeditionService.respawnInPlace(self, s: any)
	if s.removed then
		return
	end
	if s.inSas then
		spawnAt(s.player, s.cells.sas * CFrame.new(0, 0, -4))
	elseif s.room then
		local sp = s.room.def.spawnZones[1]
		spawnAt(s.player, s.room.cell * CFrame.new(sp.cx, 0, sp.cz))
		self.burial:resetSpawn(s.player)
	end
end

------------------------------------------------------------------------------------------------
-- Tutorial cell (first session only)
------------------------------------------------------------------------------------------------
function ExpeditionService.startTutorial(self, s: any)
	local def = RoomPlan.tutorialCell()
	local cell = s.cells[1]
	local model, index = RoomGenerator.build(def, cell, self.worldFolder)
	s.room = { def = def, model = model, index = index, cell = cell, tutorial = true }
	s.roomMaid = Maid.new()
	spawnAt(s.player, cell * CFrame.new(def.spawnZones[1].cx, 0, def.spawnZones[1].cz))
	Tutorial.record(s.tutorial, "controllable", os.clock())
	self.remotes.fire(s.player, "Hud", { type = "hint", key = "climb_and_exit" })
	local function grant(event: string)
		-- one request per event: Heartbeat would otherwise queue a mutation every frame
		if s.tutorialGranted[event] then
			return
		end
		s.tutorialGranted[event] = true
		Tutorial.record(s.tutorial, event, os.clock())
		local p = self.repo:get(s.userKey)
		local reward = Tutorial.rewardFor(event, p.tutorialFlags)
		if reward then
			local ok = self.repo:mutate(s.userKey, { type = "GrantTutorial", rewardId = reward })
			if ok then
				self.remotes.fire(s.player, "Hud", { type = "reward", rewardId = reward, amount = Rewards.tutorialReward(reward) })
			end
			self:push(s)
		end
	end
	-- 0-3 s: the yellow carton falls and settles (discovery bonus once per account)
	local slot = index.structuralSlots.carton
	local carton = PropFactory.create(slot.propId, RoomGenerator.template("reception"))
	local cartonCol = carton.PrimaryPart :: BasePart
	carton:PivotTo(slot.cframe + Vector3.new(0, 8, 0))
	cartonCol.Anchored = true
	carton.Parent = model
	s.roomMaid:give(carton)
	task.delay(def.structuralDrops[1].atSeconds, function()
		local tween = game:GetService("TweenService")
			:Create(cartonCol, TweenInfo.new(0.6, Enum.EasingStyle.Bounce), { CFrame = slot.cframe })
		tween.Completed:Once(function()
			grant("carton_settled")
		end)
		tween:Play()
	end)
	-- first landing on the carton
	local nextHintCheck = 0
	s.roomMaid:give(RunService.Heartbeat:Connect(function()
		local char = s.player.Character
		local hum = char and char:FindFirstChildOfClass("Humanoid")
		local root = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
		if hum and root and hum.FloorMaterial ~= Enum.Material.Air then
			local rel = cartonCol.CFrame:PointToObjectSpace(root.Position)
			local sz = cartonCol.Size
			if math.abs(rel.X) < sz.X / 2 + 0.5 and math.abs(rel.Z) < sz.Z / 2 + 0.5 and rel.Y > sz.Y / 2 then
				grant("landed_on_support")
			end
		end
		if hum and hum.MoveDirection.Magnitude > 0.05 then
			Tutorial.record(s.tutorial, "input", os.clock())
		end
		if os.clock() < nextHintCheck or s.tutorial.hintShown then
			return
		end
		nextHintCheck = os.clock() + 0.5
		if Tutorial.shouldShowGhostHint(s.tutorial, os.clock(), self.repo:get(s.userKey).tutorialFlags) then
			s.tutorial.hintShown = true
			self.remotes.fire(
				s.player,
				"Hud",
				{ type = "ghost_path", points = { def.routeGraph.nodes[2].box, def.routeGraph.nodes[3].box }, cell = cell }
			)
		end
	end))
	s.roomMaid:give(ExitService.arm(s.player, index, function()
		grant("exit_reached")
		self:enterSas(s, nil, { kiosk = true })
	end))
	self:push(s)
end

------------------------------------------------------------------------------------------------
-- Runs and rooms
------------------------------------------------------------------------------------------------
function ExpeditionService.newRunParams(_self): any
	local seed = Rng.hash(HttpService:GenerateGUID(false))
	return { runId = HttpService:GenerateGUID(false):sub(1, 12), seed = seed, depth = 1 }
end

function ExpeditionService.prepareRoom(self, s: any, depth: number, cellIndex: number): any
	local def, spec, diags = RoomGenerator.plan(depth, s.exp.seed, s.history, RELEASE_PROFILE)
	if def == nil then
		-- never show an unvalidated room; the player waits in the safe sas
		self.telemetry:event(s.userKey, "room_generation_failed", { depth = depth, diags = diags })
		return nil
	end
	if def.fallback then
		self.telemetry:event(s.userKey, "room_fallback", { depth = depth, template = def.templateId })
	end
	local cell = s.cells[cellIndex]
	local model, index = RoomGenerator.build(def, cell, self.worldFolder)
	return {
		def = def,
		spec = spec,
		model = model,
		index = index,
		cell = cell,
		cellIndex = cellIndex,
		id = Checkpoint.roomInstanceId(s.exp.runId, depth),
	}
end

function ExpeditionService.startRun(self, s: any, params: any)
	local p = self.repo:get(s.userKey)
	s.exp = Machine.create({
		runId = params.runId,
		seed = params.seed,
		depth = params.depth,
		roomRewardMask = params.roomRewardMask,
		lastCommittedDepth = params.lastCommittedDepth,
		checkpointRevision = params.checkpointRevision,
		resumed = params.resumed,
		loadout = p.equippedLoadout,
		configVersion = params.configVersion,
	})
	s.history = {}
	s.pendingResume = params
	if params.resumed ~= true then
		-- durable checkpoint of the starting room: resume, claim ledger and tool charges need it
		-- (CheckpointService updates s.exp.checkpointRevision on success; a failure is retried at exit)
		self.checkpoints:save(s.userKey, s.exp, { rateBp = Rewards.rebirthBasisPoints(p.rebirthCount), paidBaseCumulative = 0 }, nil)
	end
	local room = self:prepareRoom(s, s.exp.depth, 1)
	if not room then
		-- honest waiting state in the safe sas; continueFromSas retries (state stays Preparing)
		self:enterSas(s, nil, { waitingForRoom = true })
		return
	end
	self:activateRoom(s, room, if params.resumed then params else nil)
end

function ExpeditionService.activateRoom(self, s: any, room: any, resume: any?)
	local p = self.repo:get(s.userKey)
	s.room = room
	s.inSas = false
	s.kiosk = false
	if s.exp.state == "Preparing" then
		local ok, nextExp = Machine.apply(s.exp, { type = "RoomReady", roomId = room.id })
		assert(ok, "RoomReady rejected: " .. tostring(nextExp))
		s.exp = nextExp
	end
	assert(s.exp.state == "Active" and s.exp.roomId == room.id, "room activation out of sync with the state machine")
	if not s.residency.active then
		Residency.activate(s.residency, room.id)
	end
	table.insert(s.history, room.spec)
	if #s.history > Config.Runtime.streaming.recent_room_history_size then
		table.remove(s.history, 1)
	end
	-- rebirth rate frozen at room start; resume keeps the stored values
	s.roomCtx = {
		runId = s.exp.runId,
		depth = s.exp.depth,
		mask = (resume and resume.roomRewardMask) or 0,
		rateBp = (resume and resume.rateBasisPoints) or Rewards.rebirthBasisPoints(p.rebirthCount),
		paidBaseCumulative = (resume and resume.paidBaseCumulative) or 0,
	}
	s.exp.roomRewardMask = s.roomCtx.mask
	self.tools:enterRoom(s.player, p, room.id, resume and resume.chargesSnapshot)
	s.roomMaid = Maid.new()
	room.director = WaveDirector.new(room.def, room.index, room.cell, room.model, s.exp.depth, {
		warn = function(info)
			-- one warning per mouth opened by this wave (several in very large rooms)
			for _, mi in info.mouthIndices or { info.mouthIndex } do
				local m = room.def.waveMouths[mi]
				if m then
					self.remotes.fire(s.player, "WaveWarning", {
						mouth = room.cell * CFrame.new(m.cx, room.def.size.h, m.cz),
						impactIn = info.impactIn,
						size = Vector3.new(m.sx, 1, m.sz),
					})
				end
			end
		end,
		plushImpact = function(ev)
			self.remotes.fire(s.player, "PlushImpact", ev)
		end,
		diagnostic = function(name, data)
			self.telemetry:event(s.userKey, name, data)
		end,
	})
	room.director:start()
	local spawn = room.def.spawnZones[1]
	spawnAt(s.player, room.cell * CFrame.new(spawn.cx, 0, spawn.cz))
	self.burial:resetSpawn(s.player)
	self.burial:watch(s.player, function()
		return s.exp ~= nil and s.exp.state == "Active" and not s.inSas
	end, function(ev, sample)
		self:onBurialEvent(s, ev, sample)
	end)
	s.roomMaid:give(ExitService.arm(s.player, room.index, function()
		self:onExit(s)
	end, function()
		self.remotes.fire(s.player, "Hud", { type = "lever_opened" })
	end))
	-- milestones and tokens at 10 Hz from server-known positions
	local acc = 0
	s.roomMaid:give(RunService.Heartbeat:Connect(function(dt)
		acc += dt
		if acc < 1 / MILESTONE_HZ then
			return
		end
		acc = 0
		self:checkProgress(s)
	end))
	self.remotes.fire(
		s.player,
		"Hud",
		{ type = "room_enter", family = room.def.familyId, depth = s.exp.depth, fallback = room.def.fallback }
	)
	self.telemetry:event(s.userKey, "room_enter", { depth = s.exp.depth, template = room.def.templateId })
	-- preload the next room now (resident: active + next; sas appears at exit)
	task.defer(function()
		if s.exp and s.exp.state == "Active" and s.nextRoom == nil then
			local nextDepth = s.exp.depth + 1
			local cellIndex = if room.cellIndex == 1 then 2 else 1
			local nr = self:prepareRoom(s, nextDepth, cellIndex)
			if nr then
				s.nextRoom = nr
				Residency.preloadNext(s.residency, nr.id)
			end
		end
	end)
	self:push(s)
end

function ExpeditionService.checkProgress(self, s: any)
	local room = s.room
	if not room or not s.exp or s.exp.state ~= "Active" or s.claiming or s.removed then
		return
	end
	-- one claim pass at a time: the writes yield and the next 10 Hz tick must not reuse a stale mask
	-- (the profile's claim ledger also refuses duplicates: decision 0005)
	s.claiming = true
	local ok, err = pcall(self.checkProgressUnsafe, self, s, room)
	s.claiming = false
	if not ok then
		warn("[ExpeditionService] checkProgress failed:", err)
	end
end

function ExpeditionService.checkProgressUnsafe(self, s: any, room: any)
	local char = s.player.Character
	local root = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if not root or not hum then
		return
	end
	local localPos = room.cell:PointToObjectSpace(root.Position)
	local feetY = localPos.Y - 3
	if hum.FloorMaterial ~= Enum.Material.Air then
		local best = 0
		for k, hgt in room.def.milestoneHeights do
			if feetY >= hgt - 0.25 then
				best = k
			end
		end
		if best > 0 and not Rewards.hasBit(s.roomCtx.mask, best - 1) then
			local ok, res = self.rewards:progress(s.userKey, s.roomCtx, best)
			if ok then
				s.exp.roomRewardMask = s.roomCtx.mask
				self.remotes.fire(s.player, "Hud", { type = "milestone", index = best, coins = res.claim.coins })
				self:push(s)
			end
		end
	end
	local p = self.repo:get(s.userKey)
	local magnet = self.tools.magnetTokens(
		p,
		root.Position,
		(function()
			local list = {}
			for _, tk in room.def.tokens do
				local w = room.cell * CFrame.new(tk.x, tk.y, tk.z)
				table.insert(list, { id = tk.id, x = w.X, y = w.Y, z = w.Z })
			end
			return list
		end)(),
		s.roomCtx.mask,
		Rewards.TOKEN_BIT0
	)
	for _, tk in room.def.tokens do
		local part = room.index.tokens[tk.id]
		if part and part.Parent then
			local near = (part.Position - root.Position).Magnitude <= TOKEN_PICK_RADIUS
			if near or table.find(magnet, tk.id) then
				local ok = self.rewards:token(s.userKey, s.roomCtx, tk.id)
				if ok then
					s.exp.roomRewardMask = s.roomCtx.mask
					part:Destroy()
					self:push(s)
				end
			end
		end
	end
end

function ExpeditionService.onBurialEvent(self, s: any, ev: string, sample: any)
	if ev == "warning_on" or ev == "warning_off" then
		self.remotes.fire(s.player, "BurialWarning", { on = ev == "warning_on", lateralHits = sample.lateralHits })
		return
	end
	local cause = if ev == "ko_burial" then "confirmed_burial" else "marked_kill_volume"
	local ok, ko = Machine.apply(s.exp, { type = "KOConfirmed", cause = cause })
	if not ok then
		return
	end
	s.exp = ko
	if s.room and s.room.director then
		s.room.director:stop()
	end
	self.checkpoints:clear(s.userKey) -- the run is over; possessions stay in the profile
	self.telemetry:event(s.userKey, "ko", { cause = cause, depth = ko.depth })
	self.remotes.fire(s.player, "Hud", { type = "ko", depth = ko.depth, cause = cause })
	self:push(s)
end

function ExpeditionService.onExit(self, s: any)
	local room = s.room
	local depth = s.exp.depth
	local ok, t = Machine.apply(s.exp, { type = "ExitReached", roomId = room.id, depth = depth })
	if not ok then
		return -- duplicate / stale exit: never a second room gained
	end
	s.exp = t
	room.director:stop() -- only the active room simulates waves; none in the sas
	local p = self.repo:get(s.userKey)
	-- next room checkpoint (depth already incremented by the machine, fresh claim mask)
	local nextExp = table.clone(t)
	nextExp.roomRewardMask = 0
	local nextCp =
		Checkpoint.fromExpedition(nextExp, { rateBasisPoints = Rewards.rebirthBasisPoints(p.rebirthCount), paidBaseCumulative = 0 })
	s.pendingCompletion = {
		type = "CompleteRoom",
		runId = s.roomCtx.runId,
		depth = depth,
		mask = s.roomCtx.mask,
		rateBp = s.roomCtx.rateBp,
		paidBaseCumulative = s.roomCtx.paidBaseCumulative,
		familyId = room.def.familyId,
		nextCheckpoint = nextCp,
	}
	self.telemetry:event(s.userKey, "room_exit", { depth = depth, template = room.def.templateId })
	-- the player is moved to the safe sas first; the single durable write happens there
	self:enterSas(s, nil, {})
	self:commitCompletion(s)
end

-- Commits the pending room completion (exit reward + mastery + discovery + checkpoint) in ONE
-- write. On failure nothing is announced as saved and continuing waits for a successful retry.
function ExpeditionService.commitCompletion(self, s: any): boolean
	local m = s.pendingCompletion
	if m == nil then
		return true
	end
	local ok, res, info = self.repo:mutate(s.userKey, m)
	if ok or res == "already_claimed" then
		s.pendingCompletion = nil
		s.lastSaveOk = true
		if s.exp then
			s.exp.checkpointRevision = m.nextCheckpoint.checkpointRevision
		end
		if ok then
			local c = info.claim
			self.remotes.fire(s.player, "Hud", { type = "gains", coins = c.coins + info.familyDiscovery, permits = c.permits, xp = c.xp })
		end
		self.remotes.fire(s.player, "Hud", { type = "save_status", ok = true })
		self:push(s)
		return true
	end
	s.lastSaveOk = false
	self.remotes.fire(s.player, "Hud", { type = "save_status", ok = false })
	return false
end

function ExpeditionService.enterSas(self, s: any, claim: any?, opts: any)
	local p = self.repo:get(s.userKey)
	if s.sas then
		s.sas:Destroy()
	end
	local Rebirth = require(Shared.Domain.Rebirth)
	local eligible = (Rebirth.qualifies(p)) and Rebirth.maxAffordable(p.rebirthCount, p.permits) > 0
	local sas, door = buildSas(self.worldFolder, s.cells.sas, eligible)
	s.sas = sas
	s.inSas = true
	s.kiosk = opts.kiosk == true
	if s.exp and s.exp.state == "Transitioning" then
		Residency.enterSas(s.residency, "sas")
		-- durable checkpoint for the NEXT room start (depth already incremented by the machine)
		s.roomCtx = {
			runId = s.exp.runId,
			depth = s.exp.depth,
			mask = 0,
			rateBp = Rewards.rebirthBasisPoints(p.rebirthCount),
			paidBaseCumulative = 0,
		}
		s.exp.roomRewardMask = 0
		-- the durable checkpoint is part of the pending CompleteRoom write (commitCompletion)
	end
	spawnAt(s.player, s.cells.sas * CFrame.new(0, 0, -4))
	if claim then
		self.remotes.fire(s.player, "Hud", { type = "gains", coins = claim.coins, permits = claim.permits, xp = claim.xp })
	end
	-- walking straight through the door continues; no menu is required
	local doorMaid = Maid.new()
	s.maid:give(doorMaid)
	local fired = false
	doorMaid:give(RunService.Heartbeat:Connect(function()
		if fired or s.txBusy or s.removed then
			return
		end
		local char = s.player.Character
		local root = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
		if root and (root.Position - door.Position).Magnitude < 5 then
			fired = true
			doorMaid:clean()
			self:continueFromSas(s)
		end
	end))
	self:push(s)
end

function ExpeditionService.teardownRoom(_self, s: any, room: any?)
	if not room then
		return
	end
	if room.director then
		room.director:destroy()
	end
	if s.roomMaid and s.room == room then
		s.roomMaid:clean()
	end
	if room.model then
		room.model:Destroy()
	end
end

function ExpeditionService.continueFromSas(self, s: any)
	-- tutorial finished, KO restart, or fresh start: begin a new run at depth 1
	if s.exp == nil or s.exp.state == "KO" or s.exp.state == "Extracted" then
		if s.room and s.room.tutorial then
			s.roomMaid:clean()
			s.room.model:Destroy()
			s.room = nil
		end
		self:teardownRoom(s, s.room)
		self:teardownRoom(s, s.nextRoom)
		s.room, s.nextRoom = nil, nil
		s.residency = Residency.new()
		self:startRun(s, self:newRunParams())
		return
	end
	if s.removed then
		return
	end
	local function retryLater(key: string)
		self.remotes.fire(s.player, "Hud", { type = key })
		task.delay(1, function()
			if s.inSas and not s.removed then
				self:continueFromSas(s)
			end
		end)
	end
	if s.exp.state == "Preparing" then
		-- the first room of the run could not be prepared yet: retry from the safe sas
		local room = self:prepareRoom(s, s.exp.depth, 1)
		if room == nil then
			retryLater("loading_next")
			return
		end
		if s.sas then
			s.sas:Destroy()
			s.sas = nil
		end
		self:activateRoom(s, room, if s.pendingResume and s.pendingResume.resumed then s.pendingResume else nil)
		return
	end
	if s.exp.state ~= "Transitioning" then
		return
	end
	-- the previous room must be durably completed before progressing (no unsaved progression)
	if s.pendingCompletion and not self:commitCompletion(s) then
		retryLater("save_failed_retry")
		return
	end
	if s.nextRoom == nil then
		local cellIndex = if s.room and s.room.cellIndex == 1 then 2 else 1
		s.nextRoom = self:prepareRoom(s, s.exp.depth, cellIndex)
		if s.nextRoom == nil then
			-- honest loading state in the safe sas: no failure can come from waiting here
			retryLater("loading_next")
			return
		end
		Residency.preloadNext(s.residency, s.nextRoom.id)
	end
	local nextRoom = s.nextRoom
	local ok, n = Machine.apply(s.exp, { type = "NextRoomActive", roomId = nextRoom.id })
	if not ok then
		return
	end
	s.exp = n
	-- previous room released after the committed transition (<= 3 resident modules)
	local old = s.room
	if s.roomMaid then
		s.roomMaid:clean()
	end
	self:teardownRoom(s, old)
	Residency.commit(s.residency)
	s.nextRoom = nil
	if s.sas then
		s.sas:Destroy()
		s.sas = nil
	end
	-- the machine is already Active in the new room (NextRoomActive)
	self:activateRoom(s, nextRoom, nil)
end

------------------------------------------------------------------------------------------------
-- Intent handlers (wired by Main)
------------------------------------------------------------------------------------------------
function ExpeditionService.bindIntents(self)
	local R = self.remotes
	R.on("RequestCoinPurchase", function(player, a)
		local s = self.sessions[player]
		if not s then
			return { ok = false, error = "no_session" }
		end
		local res = self.inventory:buy(s.userKey, a.skuId, a.requestId, { inSas = s.inSas, kiosk = s.kiosk })
		self:push(s)
		return res
	end)
	R.on("RequestEquip", function(player, a)
		local s = self.sessions[player]
		if not s then
			return { ok = false, error = "no_session" }
		end
		local res = self.inventory:equip(s.userKey, a.itemId, a.slot, { inSas = s.inSas, kiosk = s.kiosk })
		self:push(s)
		return res
	end)
	R.on("RequestToolUse", function(player, a)
		local s = self.sessions[player]
		if not s or not s.room or not s.room.director then
			return { ok = false, error = "not_in_active_room" }
		end
		local res = self.tools:use(player, a.toolId, a.targetId, {
			profile = self.repo:get(s.userKey),
			roomState = s.exp and s.exp.state or "",
			inSas = s.inSas,
			now = s.room.director.simTime,
			roomModel = s.room.model,
		})
		if res.ok then
			self.remotes.fire(player, "ToolEffect", res)
			-- persist the remaining charges of this room instance (a reconnect never refills them)
			task.spawn(function()
				self.repo:mutate(
					s.userKey,
					{ type = "UpdateCharges", runId = s.exp.runId, depth = s.exp.depth, charges = self.tools:charges(player) }
				)
			end)
		end
		return res
	end)
	R.on("RequestRebirthPreview", function(player, a)
		local s = self.sessions[player]
		return if s then self.rebirth:preview(s.userKey, a.quantity, s.inSas) else { ok = false, error = "no_session" }
	end)
	R.on("RequestRebirth", function(player, a)
		local s = self.sessions[player]
		if not s then
			return { ok = false, error = "no_session" }
		end
		if not s.inSas or s.txBusy then
			return { ok = false, error = if s.txBusy then "transaction_in_progress" else "not_in_sas" }
		end
		-- the completed room must be durably credited before the run can end by rebirth
		if s.pendingCompletion and not self:commitCompletion(s) then
			return { ok = false, error = "save_failed" }
		end
		-- the sas door is ignored while the rebirth write is in flight (no race to the next room)
		s.txBusy = true
		local okCall, res = pcall(function()
			return self.rebirth:confirm(s.userKey, a, s.inSas)
		end)
		s.txBusy = false
		if not okCall then
			return { ok = false, error = "server_error" }
		end
		if res.ok and s.exp and s.exp.state == "Transitioning" then
			local okX, x = Machine.apply(s.exp, { type = "Extract", inSas = true })
			if okX then
				s.exp = x
			end
			self:teardownRoom(s, s.nextRoom)
			s.nextRoom = nil
		end
		self:push(s)
		return res
	end)
	R.on("RequestSaveExit", function(player, _a)
		local s = self.sessions[player]
		if not s or not s.inSas then
			return { ok = false, error = "only_in_sas" }
		end
		if s.pendingCompletion then
			self:commitCompletion(s)
		elseif not s.lastSaveOk and s.exp and s.exp.state == "Transitioning" then
			s.lastSaveOk = self.checkpoints:save(s.userKey, s.exp, s.roomCtx, nil)
		end
		if not s.lastSaveOk then
			return { ok = false, error = "save_failed" }
		end
		task.delay(0.5, function()
			player:Kick("Sauvegardé. À bientôt !")
		end)
		return { ok = true }
	end)
	R.on("RequestRestart", function(player, _a)
		local s = self.sessions[player]
		if not s or not s.exp or s.exp.state ~= "KO" then
			return { ok = false, error = "not_ko" }
		end
		-- free restart: a new run id at depth 1 (no paid revive)
		self:teardownRoom(s, s.room)
		self:teardownRoom(s, s.nextRoom)
		s.room, s.nextRoom = nil, nil
		s.residency = Residency.new()
		self:startRun(s, self:newRunParams())
		return { ok = true }
	end)
	R.on("RequestRobuxPurchase", function(_player, _a)
		return { ok = false, error = "shop_disabled" } -- product ids are null: no real prompt
	end)
end

function ExpeditionService.start(self)
	self:bindIntents()
	Players.PlayerAdded:Connect(function(p)
		self:playerAdded(p)
	end)
	Players.PlayerRemoving:Connect(function(p)
		self:playerRemoving(p)
	end)
	for _, p in Players:GetPlayers() do
		task.spawn(function()
			self:playerAdded(p)
		end)
	end
end

return ExpeditionService
