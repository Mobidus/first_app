--!strict
-- Difficulty bands (rooms.json difficulty_bands). Physical parameters are bounded: beyond the
-- last band nothing escalates any more, only combinations vary.
local Config = require(script.Parent.Parent.GeneratedConfig)

local Difficulty = {}

function Difficulty.bandForDepth(depth: number)
	assert(type(depth) == "number" and depth >= 1, "depth must be >= 1")
	for _, b in Config.Rooms.difficulty_bands do
		if depth >= b.depth_min and (b.depth_max == nil or depth <= b.depth_max) then
			return b
		end
	end
	error("no difficulty band for depth " .. depth)
end

-- Wave volume scaled by floor area (rooms.json wave_area_scaling, decision 0017): very large rooms
-- keep the same filling pressure per floor area. The physics budget (40 dynamic bodies) is not
-- raised: excess drops are deferred by the consolidation planner.
function Difficulty.waveParams(band, familyId: string, formatId: string)
	local scaling = Config.Rooms.wave_area_scaling
	local fam
	for _, f in Config.Rooms.families do
		if f.id == familyId then
			fam = f
		end
	end
	local factor = 1
	if scaling and fam and fam.formats[formatId] and fam.formats[scaling.reference_format] then
		local a = fam.formats[formatId]
		local r = fam.formats[scaling.reference_format]
		factor = math.clamp((a[1] * a[2]) / (r[1] * r[2]), 1, scaling.max_factor)
	end
	local maxMouths = if scaling then scaling.max_mouths else band.mouths
	local mouthsPerWave = math.ceil(factor - 1e-9)
	return {
		factor = factor,
		objectsPerWave = math.floor(band.physical_objects_per_wave * factor + 0.5),
		mouths = math.min(band.mouths * mouthsPerWave, math.max(maxMouths, band.mouths)),
		mouthsPerWave = mouthsPerWave,
	}
end

-- Bounds that hold for EVERY depth (used by tests and the soak simulation).
function Difficulty.bounds()
	local minInterval, maxRatio, maxObjects, minWarning = math.huge, 0, 0, math.huge
	for _, b in Config.Rooms.difficulty_bands do
		minInterval = math.min(minInterval, b.wave_interval_seconds)
		maxRatio = math.max(maxRatio, b.maximum_required_gap_ratio)
		maxObjects = math.max(maxObjects, b.physical_objects_per_wave)
		minWarning = math.min(minWarning, b.warning_seconds)
	end
	return { minInterval = minInterval, maxRatio = maxRatio, maxObjectsPerWave = maxObjects, minWarning = minWarning }
end

return Difficulty
