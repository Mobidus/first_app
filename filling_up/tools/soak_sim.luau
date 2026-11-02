--!nocheck
-- LOGIC soak (T22, first family of tests). Accelerated: 18 000 simulated seconds, then 80, 200 and
-- 1 000 rooms traversed logically. It drives the real domain modules + repository + object pool +
-- residency + maids with simulated time. It does NOT prove engine physics, network, camera or
-- frame time: the real 5 h Roblox session remains a separate, blocked test.
-- Usage: lune run tools/soak_sim.luau [simulatedSeconds]
local process = require("@lune/process")
local serde = require("@lune/serde")
local fs = require("@lune/fs")
local Loader = require("../tests/_harness/Loader")

local Config = Loader.require("src/shared/GeneratedConfig")
local Machine = Loader.require("src/shared/Domain/ExpeditionStateMachine")
local RoomPlan = Loader.require("src/shared/Domain/RoomPlan")
local Validator = Loader.require("src/shared/Domain/RouteValidator")
local Wave = Loader.require("src/shared/Domain/WaveSchedule")
local Consolidation = Loader.require("src/shared/Domain/Consolidation")
local Residency = Loader.require("src/shared/Domain/RoomResidency")
local Rewards = Loader.require("src/shared/Domain/Rewards")
local Checkpoint = Loader.require("src/shared/Domain/Checkpoint")
local Economy = Loader.require("src/shared/Domain/Economy")
local Maid = Loader.require("src/shared/Util/Maid")
local Repo = Loader.require("src/server/Services/PlayerProfileRepository")
local Pool = Loader.require("src/server/Services/ObjectPool")

local SIM_SECONDS = tonumber(process.args[1] or "") or 18000
local S = Config.Runtime.streaming
local SETTLE_AFTER = 1.5
local STEP = 1.0

local failures, executed = {}, {}
local function check(name, cond, detail)
	table.insert(executed, name)
	if not cond then
		table.insert(failures, name .. (detail and (": " .. detail) or ""))
	end
end

local function bandSeconds(depth)
	return Rewards.bandForDepth(depth).simulation_seconds
end

-- One logical expedition. opts: { maxRooms?, maxSeconds?, buyTools?, tokens? }
local function expedition(label, opts)
	local store = Repo.MemoryStore.new()
	local repo = Repo.new({
		store = store,
		jobId = "soak",
		now = function()
			return 0
		end,
	})
	repo:load("soak-user")
	for _, id in Config.Economy.tutorial.reward_ids do
		repo:mutate("soak-user", { type = "GrantTutorial", rewardId = id })
	end
	local clock = Config.Economy.simulation.intro_seconds
	if opts.buyTools then
		repo:mutate("soak-user", { type = "CoinPurchase", skuId = "radar_pop" })
	end
	local pool = Pool.new({
		factory = function(kind)
			return { kind = kind, anchored = false, age = 0, rewardId = nil }
		end,
		reset = function(o)
			o.anchored, o.age, o.rewardId = false, 0, nil
		end,
		maxFreeTotal = S.max_fill_colliders_active_room,
	})
	local residency = Residency.new()
	local exp = Machine.create({ runId = "soak-" .. label, seed = 1337 })
	local history = {}
	local stats = {
		peakResident = 0,
		peakDynamic = 0,
		peakStatic = 0,
		peakMaidLive = 0,
		fallbacks = 0,
		rooms = 0,
		waves = 0,
		drops = 0,
		peakPoolCreated = 0,
		rejectedRooms = 0,
		mergeEvents = 0,
		deferredDrops = 0,
	}
	local series = {}
	local nextSample = 0
	local maidBaseline = Maid.globalLive
	local currentMaid = nil
	local function sample(force)
		if not force and clock < nextSample then
			return
		end
		nextSample = clock + 600
		local p = repo:get("soak-user")
		table.insert(series, {
			t = clock,
			depth = exp.depth,
			coins = p.coins,
			permits = p.permits,
			resident = Residency.count(residency),
			poolInUse = pool:inUseCount(),
			poolFree = pool:freeCount(),
			poolCreated = pool.created,
			maidLive = Maid.globalLive - maidBaseline,
			profileBytes = #serde.encode("json", p),
		})
	end
	local ok
	ok, exp = Machine.apply(exp, { type = "RoomReady", roomId = "boot" })
	exp.roomId = Checkpoint.roomInstanceId(exp.runId, exp.depth)
	local earned = 0
	local function profileCoins()
		return repo:get("soak-user").coins
	end
	while true do
		if opts.maxRooms and stats.rooms >= opts.maxRooms then
			break
		end
		local depth = exp.depth
		local roomSeconds = bandSeconds(depth)
		if opts.maxSeconds and clock + roomSeconds > opts.maxSeconds then
			break
		end
		-- plan + validate this room (never an unvalidated room)
		local spec = RoomPlan.selectSpec(depth, exp.seed, history, "mvp")
		local seed = bit32.bxor(exp.seed, depth * 2654435761 % 4294967296)
		local room = RoomPlan.build(spec, depth, seed)
		if room == nil then
			stats.rejectedRooms += 1
			table.insert(failures, "room unbuildable at depth " .. depth)
			break
		end
		assert(Validator.validate(room, { gapRatio = room.gapRatio }), "unvalidated room reached the player")
		if room.fallback then
			stats.fallbacks += 1
		end
		table.insert(history, spec)
		if #history > S.recent_room_history_size then
			table.remove(history, 1)
		end
		-- residency: activate (first) / commit handled at exit; owner-scoped maid per room
		if residency.active == nil then
			Residency.activate(residency, exp.roomId)
		end
		currentMaid = Maid.new()
		for i = 1, 25 do
			local conn = { connected = true }
			function conn.Disconnect(c)
				c.connected = false
			end
			currentMaid:give(conn)
		end
		local schedule = Wave.new(room, RoomPlan.FAMILIES[room.familyId], depth)
		local objects = {}
		local p0 = repo:get("soak-user")
		local roomCtx =
			{ runId = exp.runId, depth = depth, mask = 0, rateBp = Rewards.rebirthBasisPoints(p0.rebirthCount), paidBaseCumulative = 0 }
		local t = 0
		local nextWave = 1
		local claimed = 0
		local deferred = 0
		while t < roomSeconds do
			t += STEP
			-- waves (time-driven; continue while the player is in the room)
			while Wave.impactTime(schedule, nextWave) <= t do
				local w = Wave.at(schedule, nextWave)
				stats.waves += 1
				deferred += #w.drops
				nextWave += 1
			end
			-- consolidation with the real planner
			local list = {}
			local dyn, stat = 0, 0
			for i, o in objects do
				o.age += STEP
				if not o.anchored and o.age >= SETTLE_AFTER then
					o.settled = true
				end
				table.insert(list, {
					id = tostring(i),
					dynamic = not o.anchored,
					settledFor = if o.settled then o.age else 0,
					occupied = false,
					routeSupport = false,
					buried = o.anchored and o.age > 20,
					age = o.age,
				})
			end
			local plan = Consolidation.plan(list)
			for _, id in plan.anchor do
				objects[tonumber(id)].anchored = true
			end
			if #plan.merge > 0 then
				stats.mergeEvents += 1
				-- merged colliders become one aggregate: keep the first, recycle the others
				for k = 2, #plan.merge do
					local idx = tonumber(plan.merge[k])
					pool:release(objects[idx].obj)
					objects[idx] = nil
				end
			end
			for _, id in plan.recycle do
				local idx = tonumber(id)
				if objects[idx] then
					pool:release(objects[idx].obj)
					objects[idx] = nil
				end
			end
			-- compact
			local compact = {}
			for _, o in objects do
				if o then
					table.insert(compact, o)
				end
			end
			objects = compact
			local allowance = plan.spawnAllowance
			while deferred > 0 and allowance > 0 do
				local obj = pool:acquire("fill")
				table.insert(objects, { obj = obj, anchored = false, age = 0 })
				deferred -= 1
				allowance -= 1
				stats.drops += 1
			end
			if deferred > 0 then
				stats.deferredDrops += 1
			end
			for _, o in objects do
				if o.anchored then
					stat += 1
				else
					dyn += 1
				end
			end
			stats.peakDynamic = math.max(stats.peakDynamic, dyn)
			stats.peakStatic = math.max(stats.peakStatic, stat)
			-- milestones at 25/50/75 % of the room time (zones are heights, timing is only the pace model)
			local zone = math.min(3, math.floor(t / roomSeconds * 4))
			if zone > claimed then
				local okM = repo:mutate("soak-user", {
					type = "GrantProgress",
					runId = roomCtx.runId,
					depth = depth,
					index = zone,
					mask = roomCtx.mask,
					rateBp = roomCtx.rateBp,
					paidBaseCumulative = roomCtx.paidBaseCumulative,
				})
				if okM then
					local c = Rewards.planProgress({
						runId = roomCtx.runId,
						depth = depth,
						index = zone,
						mask = roomCtx.mask,
						rateBp = roomCtx.rateBp,
						paidBaseCumulative = roomCtx.paidBaseCumulative,
					})
					roomCtx.mask, roomCtx.paidBaseCumulative = c.newMask, c.newPaidBaseCumulative
				end
				claimed = zone
			end
		end
		-- exit: one transition, exit reward, mastery, checkpoint
		local before = profileCoins()
		local okE, res = repo:mutate("soak-user", {
			type = "GrantProgress",
			runId = roomCtx.runId,
			depth = depth,
			index = 4,
			mask = roomCtx.mask,
			rateBp = roomCtx.rateBp,
			paidBaseCumulative = roomCtx.paidBaseCumulative,
		})
		check(label .. " exit reward granted at depth " .. depth, okE == true, tostring(res))
		local okT, nextExp = Machine.apply(exp, { type = "ExitReached", roomId = exp.roomId, depth = depth })
		check(label .. " single transition at depth " .. depth, okT == true, tostring(nextExp))
		local dup = Machine.apply(nextExp, { type = "ExitReached", roomId = exp.roomId, depth = depth })
		if dup then
			table.insert(failures, "duplicate exit accepted at depth " .. depth)
		end
		exp = nextExp
		repo:mutate("soak-user", { type = "RoomCompleted", familyId = room.familyId, depth = depth })
		earned += profileCoins() - before
		-- sas: preload, checkpoint, buy tools in catalog order (MVP-implemented only)
		local nextId = Checkpoint.roomInstanceId(exp.runId, exp.depth)
		Residency.preloadNext(residency, nextId)
		Residency.enterSas(residency, "sas")
		stats.peakResident = math.max(stats.peakResident, Residency.count(residency))
		local cp = Checkpoint.fromExpedition(exp, { rateBasisPoints = 0, paidBaseCumulative = 0 })
		repo:mutate("soak-user", { type = "SetCheckpoint", checkpoint = cp })
		if opts.buyTools then
			for _, tdef in Config.Economy.tools do
				if Economy.IMPLEMENTED_TOOLS[tdef.id] then
					repo:mutate("soak-user", { type = "CoinPurchase", skuId = tdef.id })
				end
			end
		end
		-- commit: previous room released, its pool objects returned, maid cleaned
		for _, o in objects do
			pool:release(o.obj)
		end
		currentMaid:clean()
		stats.peakMaidLive = math.max(stats.peakMaidLive, Maid.globalLive - maidBaseline + 25)
		Residency.commit(residency)
		local okN
		okN, exp = Machine.apply(exp, { type = "NextRoomActive", roomId = nextId })
		assert(okN)
		stats.rooms += 1
		stats.peakPoolCreated = math.max(stats.peakPoolCreated, pool.created)
		clock += roomSeconds
		sample(false)
	end
	sample(true)
	local p = repo:get("soak-user")
	return {
		label = label,
		stats = stats,
		series = series,
		finalDepth = exp.depth,
		simulatedSeconds = clock,
		coins = p.coins,
		permits = p.permits,
		earnedFromRooms = earned,
		completedRooms = p.roomMastery.totalCompleted,
		maidLeak = Maid.globalLive - maidBaseline,
		poolInUse = pool:inUseCount(),
		profileBytes = #serde.encode("json", p),
	}
end

local started = os.clock()
local results = {}

-- 1) 18 000 simulated seconds with the economy reference assumptions (no purchases, no tokens)
local timeRun = expedition("time", { maxSeconds = SIM_SECONDS, buyTools = false })
results.time = timeRun
local ref = Config.Economy.simulation.checkpoints[#Config.Economy.simulation.checkpoints]
if SIM_SECONDS == ref.elapsed_seconds then
	check(
		"18000 s: completed rooms match economy reference (" .. ref.completed_rooms .. ")",
		timeRun.completedRooms == ref.completed_rooms,
		tostring(timeRun.completedRooms)
	)
	-- no purchase in the time run: balance = everything earned (tutorial 65 + milestones + exits)
	check(
		"18000 s: coins earned (tutorial + rooms) match reference (" .. ref.coins_earned .. ")",
		timeRun.coins == ref.coins_earned,
		tostring(timeRun.coins)
	)
	check(
		"18000 s: permits match reference (" .. ref.permits_earned .. ")",
		timeRun.permits == ref.permits_earned,
		tostring(timeRun.permits)
	)
end

-- 2) 80 / 200 / 1000 logical rooms (with MVP tool purchases)
for _, n in { 80, 200, 1000 } do
	results["rooms_" .. n] = expedition("rooms" .. n, { maxRooms = n, buyTools = true })
end

for key, r in results do
	local st = r.stats
	check(key .. ": resident modules <= 3", st.peakResident <= S.max_resident_room_modules, tostring(st.peakResident))
	check(key .. ": dynamic bodies <= 40", st.peakDynamic <= S.max_dynamic_objects, tostring(st.peakDynamic))
	check(key .. ": static fill colliders <= 120", st.peakStatic <= S.max_static_fill_colliders, tostring(st.peakStatic))
	check(key .. ": no maid/connection leak", r.maidLeak == 0, tostring(r.maidLeak))
	check(key .. ": pool returns every object", r.poolInUse == 0, tostring(r.poolInUse))
	check(
		key .. ": pool creation bounded by one room budget",
		st.peakPoolCreated <= S.max_fill_colliders_active_room + S.max_dynamic_objects,
		tostring(st.peakPoolCreated)
	)
	check(key .. ": profile size bounded (< 64 KB)", r.profileBytes < 65536, tostring(r.profileBytes))
	check(key .. ": no unbuildable room", st.rejectedRooms == 0, tostring(st.rejectedRooms))
end
check("1000 rooms reached depth 1001 (no last room)", results.rooms_1000.finalDepth == 1001, tostring(results.rooms_1000.finalDepth))
-- pool must not grow between 200 and 1000 rooms
check(
	"pool created count stable from 200 to 1000 rooms",
	results.rooms_1000.stats.peakPoolCreated == results.rooms_200.stats.peakPoolCreated,
	results.rooms_200.stats.peakPoolCreated .. " vs " .. results.rooms_1000.stats.peakPoolCreated
)

local summary = {}
for key, r in results do
	summary[key] = {
		simulatedSeconds = r.simulatedSeconds,
		completedRooms = r.completedRooms,
		finalDepth = r.finalDepth,
		coins = r.coins,
		permits = r.permits,
		stats = r.stats,
		profileBytes = r.profileBytes,
	}
end
local out = {
	status = #failures == 0 and "PASS" or "FAIL",
	kind = "logic_simulation_not_engine",
	simulated_seconds_requested = SIM_SECONDS,
	wall_clock_seconds = os.clock() - started,
	assumptions = {
		"room durations = economy reward_bands simulation_seconds (pace model, not deadlines)",
		"no KO in the time run",
		"objects settle after 1.5 s (engine physics not simulated)",
		"single solo player",
	},
	executed_count = #executed,
	executed = executed,
	failures = failures,
	summary = summary,
}
fs.writeFile(
	"reports/performance_timeseries.json",
	serde.encode("json", { kind = "simulated_logic_timeseries", time = results.time.series, rooms_1000 = results.rooms_1000.series }, true)
)
print(string.format("%s  %d checks, %d failures, %.1f s wall clock", out.status, #executed, #failures, out.wall_clock_seconds))
for _, f in failures do
	print("FAIL " .. f)
end
print("RESULT_JSON:" .. serde.encode("json", out))
process.exit(#failures == 0 and 0 or 1)
