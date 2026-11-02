--!strict
-- Axis-aligned boxes in room-local studs (y = up). Pure math for generation and validation.
local Types = require(script.Parent.Parent.Types)
type Box = Types.Box

local Box = {}

function Box.new(cx: number, cy: number, cz: number, sx: number, sy: number, sz: number): Box
	return { cx = cx, cy = cy, cz = cz, sx = sx, sy = sy, sz = sz }
end

-- Box resting on y = bottom
function Box.onFloor(cx: number, bottom: number, cz: number, sx: number, sy: number, sz: number): Box
	return { cx = cx, cy = bottom + sy / 2, cz = cz, sx = sx, sy = sy, sz = sz }
end

function Box.top(b: Box): number
	return b.cy + b.sy / 2
end

function Box.bottom(b: Box): number
	return b.cy - b.sy / 2
end

-- Strict interior overlap (touching faces do not count), shrunk by eps on every axis.
function Box.intersects(a: Box, b: Box, eps: number?): boolean
	local e = eps or 1e-6
	return math.abs(a.cx - b.cx) * 2 < (a.sx + b.sx) - 2 * e
		and math.abs(a.cy - b.cy) * 2 < (a.sy + b.sy) - 2 * e
		and math.abs(a.cz - b.cz) * 2 < (a.sz + b.sz) - 2 * e
end

-- Footprint (x/z) overlap only
function Box.overlapsXZ(a: Box, b: Box, eps: number?): boolean
	local e = eps or 1e-6
	return math.abs(a.cx - b.cx) * 2 < (a.sx + b.sx) - 2 * e and math.abs(a.cz - b.cz) * 2 < (a.sz + b.sz) - 2 * e
end

function Box.expand(b: Box, dx: number, dy: number, dz: number): Box
	return { cx = b.cx, cy = b.cy, cz = b.cz, sx = b.sx + 2 * dx, sy = b.sy + 2 * dy, sz = b.sz + 2 * dz }
end

-- Is footprint of `inner` inside footprint of `outer` (x/z)?
function Box.footprintInside(inner: Box, outer: Box, eps: number?): boolean
	local e = eps or 1e-6
	return inner.cx - inner.sx / 2 >= outer.cx - outer.sx / 2 - e
		and inner.cx + inner.sx / 2 <= outer.cx + outer.sx / 2 + e
		and inner.cz - inner.sz / 2 >= outer.cz - outer.sz / 2 - e
		and inner.cz + inner.sz / 2 <= outer.cz + outer.sz / 2 + e
end

-- Edge-to-edge horizontal gap between two footprints (0 when touching/overlapping).
function Box.gapXZ(a: Box, b: Box): number
	local dx = math.max(0, math.abs(a.cx - b.cx) - (a.sx + b.sx) / 2)
	local dz = math.max(0, math.abs(a.cz - b.cz) - (a.sz + b.sz) / 2)
	return math.sqrt(dx * dx + dz * dz)
end

function Box.containsPoint(b: Box, x: number, y: number, z: number): boolean
	return math.abs(x - b.cx) * 2 <= b.sx and math.abs(y - b.cy) * 2 <= b.sy and math.abs(z - b.cz) * 2 <= b.sz
end

-- Is box fully inside the room volume [-w/2,w/2] x [0,h] x [-d/2,d/2]?
function Box.insideRoom(b: Box, w: number, d: number, h: number, eps: number?): boolean
	local e = eps or 1e-6
	return b.cx - b.sx / 2 >= -w / 2 - e
		and b.cx + b.sx / 2 <= w / 2 + e
		and b.cz - b.sz / 2 >= -d / 2 - e
		and b.cz + b.sz / 2 <= d / 2 + e
		and b.cy - b.sy / 2 >= -e
		and b.cy + b.sy / 2 <= h + e
end

return Box
