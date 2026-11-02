--!strict
-- Jump capability table used by generation and validation.
--
-- STATUS: analytic, PROVISIONAL. docs/01 requires a table MEASURED with the real controller in
-- Studio (T06 MovementLab). Until reports/movement_calibration.json carries measured values, the
-- ballistic model below (config runtime.player: walk 16 studs/s, jump height 7.2, g 196.2) is used
-- and every route is additionally constrained by the band's maximum_required_gap_ratio. When the
-- measured table exists, `Jump.setMeasuredTable` replaces the analytic reach (no other change).

local Config = require(script.Parent.Parent.GeneratedConfig)

local P = Config.Runtime.player

local Jump = {}

Jump.WALK = P.walk_speed_studs_s
Jump.HEIGHT = P.jump_height_studs
Jump.GRAVITY = P.gravity_studs_s2
Jump.V0 = math.sqrt(2 * Jump.GRAVITY * Jump.HEIGHT)
-- Normalized gameplay body (R15_normalized_gameplay_body): collider used for clearance checks.
Jump.AVATAR = { width = 2, height = 5, depth = 1.5 }
-- A required route never asks for more than this fraction of the theoretical maximum rise.
Jump.REQUIRED_RISE_FRACTION = 0.75
Jump.source = "analytic_provisional"

local measured: { { rise: number, reach: number } }? = nil

-- Air time until the feet come back to `rise` studs above take-off (nil if unreachable).
function Jump.airTime(rise: number): number?
	local disc = Jump.V0 * Jump.V0 - 2 * Jump.GRAVITY * rise
	if disc < 0 then
		return nil
	end
	return (Jump.V0 + math.sqrt(disc)) / Jump.GRAVITY
end

-- Max horizontal edge-to-edge distance for a landing `rise` studs higher (negative = lower).
function Jump.reach(rise: number): number
	if measured then
		-- linear interpolation in the measured table (sorted by rise)
		local m = measured :: { { rise: number, reach: number } }
		if rise <= m[1].rise then
			return m[1].reach
		end
		for i = 2, #m do
			if rise <= m[i].rise then
				local a, b = m[i - 1], m[i]
				local t = (rise - a.rise) / (b.rise - a.rise)
				return a.reach + (b.reach - a.reach) * t
			end
		end
		return 0
	end
	local t = Jump.airTime(rise)
	return if t then Jump.WALK * t else 0
end

function Jump.maxRequiredRise(): number
	return Jump.HEIGHT * Jump.REQUIRED_RISE_FRACTION
end

-- Is a REQUIRED hop feasible under the band ratio?
function Jump.requiredHopOk(gap: number, rise: number, gapRatio: number): boolean
	if rise > Jump.maxRequiredRise() + 1e-9 then
		return false
	end
	return gap <= gapRatio * Jump.reach(math.max(rise, 0)) + 1e-9
end

-- Sampled positions of the avatar's feet along a hop from (x0,y0,z0) leaving the edge toward
-- (x1,y1,z1). Horizontal speed = walk speed. Returns { {x,y,z} } including apex.
function Jump.arc(x0: number, y0: number, z0: number, x1: number, y1: number, z1: number, samples: number?): { { number } }
	local n = samples or 16
	local dx, dz = x1 - x0, z1 - z0
	local dist = math.sqrt(dx * dx + dz * dz)
	local rise = y1 - y0
	local t = Jump.airTime(math.max(rise, -1e9)) or (2 * Jump.V0 / Jump.GRAVITY)
	local T = math.max(t, dist / Jump.WALK)
	local pts = {}
	for i = 0, n do
		local tt = T * i / n
		local frac = if dist > 0 then math.min(1, (Jump.WALK * tt) / dist) else 0
		local y = y0 + Jump.V0 * tt - 0.5 * Jump.GRAVITY * tt * tt
		if tt >= T then
			y = y1
		end
		table.insert(pts, { x0 + dx * frac, math.max(y, math.min(y0, y1)), z0 + dz * frac })
	end
	return pts
end

function Jump.setMeasuredTable(rows: { { rise: number, reach: number } })
	table.sort(rows, function(a, b)
		return a.rise < b.rise
	end)
	measured = rows
	Jump.source = "measured"
end

return Jump
