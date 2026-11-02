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
