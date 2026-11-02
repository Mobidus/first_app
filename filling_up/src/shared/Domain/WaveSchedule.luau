--!strict
-- Deterministic, time-driven wave schedule (docs/05 §7, rooms.json difficulty_bands).
-- Waves keep coming while the player is in the room. Their timing is a function of SIMULATION
-- seconds (never of rendered frames) and of the wave index; nothing here can decide a KO.

local Config = require(script.Parent.Parent.GeneratedConfig)
local Rng = require(script.Parent.Parent.Util.Rng)
local Difficulty = require(script.Parent.Difficulty)

local Wave = {}

local SPAWN_GRACE = Config.Runtime.safety.spawn_invulnerability_seconds

-- Wave fill: stable/bounce props unlocked at this depth, allowed in this room format, and not
-- flagged support-only (`wave_drop = false`, e.g. the giant plush; decision 0019).
local function fillProps(family, depth: number, formatId: string?): { any }
	local out = {}
	for _, p in family.props do
		if
			(p.behavior == "stable" or p.behavior == "bounce")
			and (p.stage or 1) <= depth
			and p.wave_drop ~= false
			and (p.formats == nil or formatId == nil or table.find(p.formats, formatId) ~= nil)
		then
			table.insert(out, p)
		end
	end
	return out
end

-- Fun intruders (rooms.json fun_intruders, decision 0020). Serious objects (desks, cartons, binders,
-- tools) stay in the room as supports and furniture, but what FALLS is fun:
--   * fun_only families: wave drops come only from the fun list;
--   * other families (minus exclusions): a `share` of drops is swapped for a fun prop, drawn from a
--     separate random stream so that the base prop sequence and draw count stay unchanged.
local ALL_PROPS: { [string]: any } = {}
for _, f in Config.Rooms.families do
	for _, p in f.props do
		ALL_PROPS[p.id] = p
	end
end

local function intrudersFor(familyId: string, depth: number, formatId: string?): ({ any }, number, boolean)
	local cfg = (Config.Rooms :: any).fun_intruders
	if cfg == nil or table.find(cfg.exclude_families or {}, familyId) then
		return {}, 0, false
	end
	local funOnly = table.find(cfg.fun_only_families or {}, familyId) ~= nil
	local out = {}
	for _, id in cfg.prop_ids do
		local p = ALL_PROPS[id]
		if
			p
			and (p.behavior == "stable" or p.behavior == "bounce")
			and (p.stage or 1) <= depth
			and p.wave_drop ~= false
			and (p.formats == nil or formatId == nil or table.find(p.formats, formatId) ~= nil)
		then
			table.insert(out, p)
		end
	end
	return out, cfg.share, funOnly and #out > 0
end
Wave.intrudersFor = intrudersFor

export type Drop = { propId: string, x: number, z: number, yaw: number, structural: boolean, nodeId: string? }
export type WaveInfo = {
	index: number,
	warningTime: number,
	impactTime: number,
	mouthIndex: number,
	mouthIndices: { number },
	drops: { Drop },
}

export type Schedule = {
	params: any,
	room: any,
	band: any,
	seed: number,
	firstImpact: number,
	props: { any },
	structural: { any },
	intruders: { any },
	intruderShare: number,
	funOnly: boolean,
}

function Wave.new(room, family, depth: number): Schedule
	local band = Difficulty.bandForDepth(math.max(depth, 1))
	local structural = {}
	for _, n in room.routeGraph.nodes do
		if n.arrival == "wave1" then
			table.insert(structural, n)
		end
	end
	local intruders, share, funOnly = intrudersFor(room.familyId, math.max(depth, 1), room.formatId)
	return {
		-- fun_only: the fun list IS the fill list (no swap needed)
		intruders = if funOnly then {} else intruders,
		intruderShare = if funOnly then 0 else share,
		funOnly = funOnly,
		room = room,
		band = band,
		seed = Rng.derive(room.seed, "waves:" .. room.templateId),
		-- the first impact never lands before the spawn grace and its own warning
		firstImpact = math.max(SPAWN_GRACE + band.warning_seconds, band.wave_interval_seconds * 0.5),
		params = Difficulty.waveParams(band, room.familyId, room.formatId),
		props = if funOnly then intruders else fillProps(family, math.max(depth, 1), room.formatId),
		structural = structural,
	}
end

function Wave.impactTime(s: Schedule, index: number): number
	return s.firstImpact + (index - 1) * s.band.wave_interval_seconds
end

function Wave.at(s: Schedule, index: number): WaveInfo
	assert(index >= 1 and index % 1 == 0, "wave index must be a positive integer")
	local band = s.band
	local mouths = s.room.waveMouths
	local params = s.params
	local usable = math.min(params.mouths, #mouths)
	local perWave = math.max(1, math.min(params.mouthsPerWave, usable))
	-- large rooms open several mouths per wave, rotating through all of them
	local mouthIndices = {}
	for k = 0, perWave - 1 do
		if usable > 0 then
			table.insert(mouthIndices, (((index - 1) * perWave + k) % usable) + 1)
		end
	end
	local mouthIndex = mouthIndices[1] or 0
	local impact = Wave.impactTime(s, index)
	local rng = Rng.new(Rng.derive(s.seed, "wave:" .. index))
	local drops: { Drop } = {}
	local count = params.objectsPerWave
	if index == 1 then
		for _, n in s.structural do
			-- guest / structural support replaces a standard drop and counts toward the budget
			table.insert(drops, { propId = n.topProp, x = n.box.cx, z = n.box.cz, yaw = 0, structural = true, nodeId = n.id })
			count -= 1
		end
	end
	if mouthIndex > 0 and #s.props > 0 then
		local funRng = Rng.new(Rng.derive(s.seed, "fun:" .. index))
		for i = 1, math.max(0, count) do
			local m = mouths[mouthIndices[((i - 1) % #mouthIndices) + 1]]
			local p = rng:pick(s.props)
			if #s.intruders > 0 and funRng:nextNumber() < s.intruderShare then
				p = funRng:pick(s.intruders)
			end
			local half = math.max(0, (m.sx - math.max(p.collider.size_studs[1], p.collider.size_studs[2])) / 2)
			table.insert(drops, {
				propId = p.id,
				x = m.cx + rng:nextRange(-half, half),
				z = m.cz + rng:nextRange(-half, half),
				yaw = rng:nextInt(0, 3) * 90,
				structural = false,
			})
		end
	end
	return {
		index = index,
		warningTime = impact - band.warning_seconds,
		impactTime = impact,
		mouthIndex = mouthIndex,
		mouthIndices = mouthIndices,
		drops = drops,
	}
end

-- Number of waves whose impact time is <= simSeconds (since room activation).
function Wave.countUntil(s: Schedule, simSeconds: number): number
	if simSeconds < s.firstImpact then
		return 0
	end
	return 1 + math.floor((simSeconds - s.firstImpact) / s.band.wave_interval_seconds + 1e-9)
end

return Wave
