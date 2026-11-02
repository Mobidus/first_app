--!strict
-- Deterministic, time-driven wave schedule (docs/05 §7, rooms.json difficulty_bands).
-- Waves keep coming while the player is in the room. Their timing is a function of SIMULATION
-- seconds (never of rendered frames) and of the wave index; nothing here can decide a KO.

local Config = require(script.Parent.Parent.GeneratedConfig)
local Rng = require(script.Parent.Parent.Util.Rng)
local Difficulty = require(script.Parent.Difficulty)

local Wave = {}

local SPAWN_GRACE = Config.Runtime.safety.spawn_invulnerability_seconds

local function fillProps(family, depth: number): { any }
	local out = {}
	for _, p in family.props do
		if (p.behavior == "stable" or p.behavior == "bounce") and (p.stage or 1) <= depth then
			table.insert(out, p)
		end
	end
	return out
end

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
}

function Wave.new(room, family, depth: number): Schedule
	local band = Difficulty.bandForDepth(math.max(depth, 1))
	local structural = {}
	for _, n in room.routeGraph.nodes do
		if n.arrival == "wave1" then
			table.insert(structural, n)
		end
	end
	return {
		room = room,
		band = band,
		seed = Rng.derive(room.seed, "waves:" .. room.templateId),
		-- the first impact never lands before the spawn grace and its own warning
		firstImpact = math.max(SPAWN_GRACE + band.warning_seconds, band.wave_interval_seconds * 0.5),
		params = Difficulty.waveParams(band, room.familyId, room.formatId),
		props = fillProps(family, math.max(depth, 1)),
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
		for i = 1, math.max(0, count) do
			local m = mouths[mouthIndices[((i - 1) % #mouthIndices) + 1]]
			local p = rng:pick(s.props)
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
