--!strict
-- Set dressing for (very) large rooms (decision 0018). Runs AFTER a room has been validated and
-- never changes its layout: it uses its own random stream ("dressing:<templateId>"), so a room's
-- route, mouths and tokens are byte-identical with or without dressing.
--
-- What it adds, all decorative, all inside the decor budget (validation_rules.maximum_decorative_blocks_active_room):
--   * wall-hugging furniture per family (benches, bookcases, fridges, tyre stacks...), multi-part
--     blocks with a manifest-style asset key for a later mesh swap (no Roblox ID, ever invented);
--   * floor rugs (no collision, 0.1 stud) that break up very large floors;
--   * ceiling light panels (no collision, glow) between the wave mouths.
-- Safety rules (re-checked by RouteValidator.validateDecor): never in the spawn sas, never in the
-- exit clearance or in front of the exit opening, never under a wave mouth, never within 1.5 studs
-- (XZ) of a route support, never in a jump arc or a landing headroom, never out of the room.

local Config = require(script.Parent.Parent.GeneratedConfig)
local Box = require(script.Parent.Parent.Util.Box)
local Rng = require(script.Parent.Parent.Util.Rng)
local Jump = require(script.Parent.JumpModel)
local Validator = require(script.Parent.RouteValidator)

local Dressing = {}

local Rules = Config.Rooms.validation_rules
Dressing.BLOCK_BUDGET = Rules.maximum_decorative_blocks_active_room
Dressing.SUPPORT_MARGIN = 1.5
Dressing.HEADROOM = Jump.AVATAR.height + 1.5

-- Part = local box: x along the wall (centred), y from floor (centre), z away from the wall
-- (centre, 0 = wall face). role -> colour mapping is done by RoomGenerator / render tools.
type PartDef = { x: number, y: number, z: number, sx: number, sy: number, sz: number, role: string }
type ItemDef = { key: string, w: number, h: number, d: number, parts: { PartDef }, wallMounted: boolean? }

local function P(x, y, z, sx, sy, sz, role): PartDef
	return { x = x, y = y, z = z, sx = sx, sy = sy, sz = sz, role = role }
end

local CATALOG: { [string]: { ItemDef } } = {
	reception = {
		{
			key = "decor_reception_bench",
			w = 12,
			h = 4,
			d = 4,
			parts = {
				P(0, 1.75, 2, 12, 0.5, 3.6, "soft"),
				P(0, 3.2, 0.4, 12, 2.4, 0.6, "soft"),
				P(-5, 0.75, 2, 1, 1.5, 3, "dark"),
				P(5, 0.75, 2, 1, 1.5, 3, "dark"),
			},
		},
		{
			key = "decor_reception_plant",
			w = 4,
			h = 8,
			d = 4,
			parts = {
				P(0, 1.25, 2, 3, 2.5, 3, "structure"),
				P(0, 4.5, 2, 4, 4, 4, "plant"),
				P(0, 7, 2, 2.6, 2, 2.6, "plant"),
			},
		},
		{
			key = "decor_reception_cooler",
			w = 3,
			h = 7,
			d = 3,
			parts = {
				P(0, 2, 1.5, 3, 4, 3, "background"),
				P(0, 5.5, 1.5, 2.4, 3, 2.4, "glass"),
			},
		},
		{
			key = "decor_reception_sofa",
			w = 14,
			h = 5,
			d = 5,
			parts = {
				P(0, 1.25, 2.5, 14, 2.5, 5, "accent"),
				P(0, 3.5, 0.75, 14, 3, 1.5, "accent"),
				P(-6.25, 2.75, 2.5, 1.5, 1.5, 5, "accent"),
				P(6.25, 2.75, 2.5, 1.5, 1.5, 5, "accent"),
			},
		},
		{
			key = "decor_reception_noticeboard",
			w = 9,
			h = 6,
			d = 0.6,
			wallMounted = true,
			parts = {
				P(0, 8, 0.3, 9, 6, 0.4, "structure"),
				P(0, 8, 0.45, 8, 5, 0.3, "soft"),
			},
		},
	},
	toy = {
		{
			key = "decor_toy_shelf",
			w = 14,
			h = 12,
			d = 3,
			parts = {
				P(0, 6, 0.25, 14, 12, 0.5, "structure"),
				P(0, 4, 1.75, 14, 0.5, 2.5, "background"),
				P(0, 8, 1.75, 14, 0.5, 2.5, "background"),
				P(-3, 5.75, 1.75, 4, 3, 2, "accent"),
				P(3, 9.5, 1.75, 5, 2.5, 2, "accent"),
			},
		},
		{
			key = "decor_toy_block_stack",
			w = 6,
			h = 9,
			d = 6,
			parts = {
				P(0, 2, 3, 6, 4, 6, "accent"),
				P(0.5, 5.5, 3, 4.5, 3, 4.5, "structure"),
				P(-0.4, 8, 3, 3, 2, 3, "glow"),
			},
		},
		{
			key = "decor_toy_crate",
			w = 8,
			h = 4,
			d = 6,
			parts = {
				P(0, 1.75, 3, 8, 3.5, 6, "structure"),
				P(0, 3.75, 3.1, 8.4, 0.5, 6.2, "dark"),
				P(0, 4.5, 3, 5, 1, 3, "accent"),
			},
		},
		{
			key = "decor_toy_poster",
			w = 7,
			h = 9,
			d = 0.5,
			wallMounted = true,
			parts = {
				P(0, 9, 0.25, 7, 9, 0.3, "accent"),
				P(0, 9, 0.42, 5.5, 7.5, 0.1, "soft"),
			},
		},
	},
	bureau = {
		{
			key = "decor_bureau_bookcase",
			w = 10,
			h = 14,
			d = 3,
			parts = {
				P(0, 7, 0.25, 10, 14, 0.5, "structure"),
				P(0, 4.5, 1.75, 10, 0.5, 2.5, "background"),
				P(0, 9, 1.75, 10, 0.5, 2.5, "background"),
				P(-1, 6.5, 1.75, 7, 3.5, 2, "accent"),
				P(1, 11, 1.75, 6, 3.5, 2, "soft"),
			},
		},
		{
			key = "decor_bureau_filing",
			w = 4,
			h = 8,
			d = 3,
			parts = {
				P(0, 4, 1.5, 4, 8, 3, "background"),
				P(0, 2.5, 3.05, 3, 0.4, 0.1, "dark"),
				P(0, 5.5, 3.05, 3, 0.4, 0.1, "dark"),
			},
		},
		{
			key = "decor_bureau_printer_table",
			w = 7,
			h = 6,
			d = 4,
			parts = {
				P(0, 2.75, 2, 7, 0.5, 4, "structure"),
				P(-3, 1.25, 2, 0.6, 2.5, 3.4, "dark"),
				P(3, 1.25, 2, 0.6, 2.5, 3.4, "dark"),
				P(0, 4, 2, 4.5, 2, 3, "background"),
			},
		},
		{
			key = "decor_bureau_plant",
			w = 4,
			h = 9,
			d = 4,
			parts = {
				P(0, 1.5, 2, 3, 3, 3, "dark"),
				P(0, 5, 2, 4, 4, 4, "plant"),
				P(0, 7.75, 2, 2.4, 2.5, 2.4, "plant"),
			},
		},
		{
			key = "decor_bureau_whiteboard",
			w = 12,
			h = 6,
			d = 0.5,
			wallMounted = true,
			parts = {
				P(0, 8, 0.25, 12, 6, 0.3, "dark"),
				P(0, 8, 0.42, 11.2, 5.2, 0.1, "soft"),
			},
		},
	},
	kitchen = {
		{
			key = "decor_kitchen_counter",
			w = 16,
			h = 6,
			d = 4,
			parts = {
				P(0, 2.75, 2, 16, 5.5, 4, "background"),
				P(0, 5.75, 2.1, 16.4, 0.5, 4.2, "structure"),
				P(-4, 6.25, 2, 4, 0.5, 3, "dark"),
				P(4, 2.75, 4.05, 6, 3, 0.1, "accent"),
			},
		},
		{
			key = "decor_kitchen_fridge",
			w = 6,
			h = 14,
			d = 5,
			parts = {
				P(0, 7, 2.5, 6, 14, 5, "soft"),
				P(2.2, 8.5, 5.05, 0.4, 4, 0.2, "dark"),
				P(0, 13.5, 2.6, 6.2, 1, 5.2, "accent"),
			},
		},
		{
			key = "decor_kitchen_jar_shelf",
			w = 10,
			h = 4,
			d = 2.5,
			wallMounted = true,
			parts = {
				P(0, 8, 1.25, 10, 0.5, 2.5, "structure"),
				P(-2.5, 9.5, 1.25, 2, 2.5, 2, "glass"),
				P(2, 9.25, 1.25, 2.5, 2, 2, "accent"),
			},
		},
	},
	garage = {
		{
			key = "decor_garage_tyre_stack",
			w = 5,
			h = 6,
			d = 5,
			parts = {
				P(0, 1, 2.5, 5, 2, 5, "dark"),
				P(0, 3, 2.5, 5, 2, 5, "dark"),
				P(0, 5, 2.5, 5, 2, 5, "dark"),
			},
		},
		{
			key = "decor_garage_shelving",
			w = 12,
			h = 12,
			d = 4,
			parts = {
				P(0, 6, 0.3, 12, 12, 0.6, "structure"),
				P(0, 4, 2, 12, 0.5, 4, "background"),
				P(0, 8, 2, 12, 0.5, 4, "background"),
				P(-3, 5.5, 2, 4, 2.5, 3, "accent"),
				P(3, 9.75, 2, 4.5, 3, 3, "soft"),
			},
		},
		{
			key = "decor_garage_drums",
			w = 7,
			h = 5,
			d = 3.5,
			parts = {
				P(-1.8, 2.5, 1.75, 3, 5, 3, "accent"),
				P(1.8, 2.5, 1.75, 3, 5, 3, "structure"),
			},
		},
		{
			key = "decor_garage_pegboard",
			w = 12,
			h = 7,
			d = 0.6,
			wallMounted = true,
			parts = {
				P(0, 8, 0.3, 12, 7, 0.4, "background"),
				P(-3, 8, 0.6, 1, 4, 0.3, "dark"),
				P(2, 8.5, 0.6, 3, 1, 0.3, "accent"),
			},
		},
	},
	pool = {
		{
			key = "decor_pool_lounger",
			w = 6,
			h = 3,
			d = 12,
			parts = {
				P(0, 1.25, 6, 5, 0.5, 11, "background"),
				P(0, 2.5, 1.6, 5, 2.4, 0.6, "background"),
				P(-2, 0.5, 6, 0.5, 1, 10, "structure"),
				P(2, 0.5, 6, 0.5, 1, 10, "structure"),
				P(0, 1.6, 9, 4, 0.3, 4, "accent"),
			},
		},
		{
			key = "decor_pool_parasol",
			w = 9,
			h = 12,
			d = 9,
			parts = {
				P(0, 0.5, 4.5, 3, 1, 3, "dark"),
				P(0, 6, 4.5, 0.6, 11, 0.6, "soft"),
				P(0, 11.2, 4.5, 9, 0.8, 9, "accent"),
				P(0, 11.8, 4.5, 5, 0.6, 5, "structure"),
			},
		},
		{
			key = "decor_pool_palm",
			w = 6,
			h = 14,
			d = 6,
			parts = {
				P(0, 1.25, 3, 4, 2.5, 4, "accent"),
				P(0, 7, 3, 1.4, 10, 1.4, "soft"),
				P(0, 12.6, 3, 7, 1.2, 7, "plant"),
				P(0, 13.6, 3, 4, 1, 4, "plant"),
			},
		},
		{
			key = "decor_pool_lifeguard_chair",
			w = 5,
			h = 12,
			d = 5,
			parts = {
				P(-2, 5, 2.5, 0.6, 10, 0.6, "soft"),
				P(2, 5, 2.5, 0.6, 10, 0.6, "soft"),
				P(0, 9.5, 2.5, 4.6, 0.6, 4, "accent"),
				P(0, 11, 0.8, 4.6, 2.4, 0.5, "accent"),
			},
		},
		{
			key = "decor_pool_ring_rack",
			w = 8,
			h = 8,
			d = 0.8,
			wallMounted = true,
			parts = {
				P(-2, 8, 0.4, 3.5, 3.5, 0.6, "accent"),
				P(2, 8, 0.4, 3.5, 3.5, 0.6, "structure"),
				P(0, 10.5, 0.3, 8, 0.4, 0.4, "dark"),
			},
		},
	},
	bin = {
		{
			key = "decor_bin_crushed_can",
			w = 5,
			h = 9,
			d = 5,
			parts = {
				P(0, 2, 2.5, 5, 4, 5, "accent"),
				P(0.3, 6, 2.5, 4.6, 4, 4.6, "structure"),
				P(0, 8.5, 2.5, 3.5, 1, 3.5, "soft"),
			},
		},
		{
			key = "decor_bin_cardboard_pile",
			w = 9,
			h = 6,
			d = 6,
			parts = {
				P(-1.5, 1.75, 3, 6, 3.5, 5, "background"),
				P(1.5, 4.5, 3, 5, 2.5, 4, "background"),
				P(2, 1.25, 3, 4, 2.5, 6, "soft"),
			},
		},
		{
			key = "decor_bin_bag_cluster",
			w = 8,
			h = 5,
			d = 5,
			parts = {
				P(-2, 2, 2.5, 4, 4, 4, "dark"),
				P(2, 1.75, 2.5, 4, 3.5, 4, "dark"),
				P(0, 4, 2.5, 3, 2, 3, "structure"),
			},
		},
	},
}
Dressing.CATALOG = CATALOG

-- local part -> room box on a given wall. wall: "N" (+Z), "S" (-Z), "E" (+X), "W" (-X)
local function toRoom(wall: string, w: number, d: number, along: number, p: PartDef): any
	if wall == "N" then
		return Box.new(along + p.x, p.y, d / 2 - p.z, p.sx, p.sy, p.sz)
	elseif wall == "S" then
		return Box.new(along - p.x, p.y, -d / 2 + p.z, p.sx, p.sy, p.sz)
	elseif wall == "E" then
		return Box.new(w / 2 - p.z, p.y, along - p.x, p.sz, p.sy, p.sx)
	else
		return Box.new(-w / 2 + p.z, p.y, along + p.x, p.sz, p.sy, p.sx)
	end
end
Dressing.toRoom = toRoom

-- Union of the item's parts in room space (the placement test uses the real geometry).
local function footprint(wall: string, w: number, d: number, along: number, item: ItemDef): any
	local x0, y0, z0, x1, y1, z1 = math.huge, math.huge, math.huge, -math.huge, -math.huge, -math.huge
	for _, p in item.parts do
		local b = toRoom(wall, w, d, along, p)
		x0, x1 = math.min(x0, b.cx - b.sx / 2), math.max(x1, b.cx + b.sx / 2)
		y0, y1 = math.min(y0, b.cy - b.sy / 2), math.max(y1, b.cy + b.sy / 2)
		z0, z1 = math.min(z0, b.cz - b.sz / 2), math.max(z1, b.cz + b.sz / 2)
	end
	return Box.new((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2, x1 - x0, y1 - y0, z1 - z0)
end

-- Boxes that decor must never touch, computed from the final (validated) room.
function Dressing.keepOut(room): { volumes: { any }, footprints: { any }, wallZones: { any } }
	local h = room.size.h
	local volumes, footprints = {}, {}
	local nodes = {}
	for _, n in room.routeGraph.nodes do
		nodes[n.id] = n
		if n.kind ~= "floor" then
			table.insert(footprints, Box.expand(n.box, Dressing.SUPPORT_MARGIN, 0, Dressing.SUPPORT_MARGIN))
			table.insert(volumes, Box.onFloor(n.box.cx, n.topY, n.box.cz, n.walkable.w, Dressing.HEADROOM, n.walkable.d))
			if n.sweep then
				table.insert(footprints, Box.expand(n.sweep, Dressing.SUPPORT_MARGIN, 0, Dressing.SUPPORT_MARGIN))
			end
		end
	end
	for _, s in room.solids do
		table.insert(footprints, Box.expand(s.box, Dressing.SUPPORT_MARGIN, 0, Dressing.SUPPORT_MARGIN))
	end
	for _, e in room.routeGraph.edges do
		local a, b = nodes[e.from], nodes[e.to]
		if e.kind == "jump" and a and b and a.kind ~= "floor" then
			for _, body in Validator.arcBodies(a, b) do
				table.insert(volumes, Box.expand(body, 0.5, 0.5, 0.5))
			end
		end
	end
	for _, sz in room.spawnZones do
		table.insert(footprints, Box.expand(sz, 3, 0, 3))
	end
	table.insert(footprints, Box.expand(room.exitClearance, 2, 0, 2))
	-- the exit opening and its approach (door, window, tailgate) stay visually clear
	local o = room.exitOpening
	table.insert(footprints, Box.new(o.cx, h / 2, o.cz, math.max(o.sx, 1) + 8, h, math.max(o.sz, 1) + 8))
	for _, m in room.waveMouths do
		table.insert(footprints, Box.new(m.cx, h / 2, m.cz, m.sx + 2, h, m.sz + 2))
	end
	return { volumes = volumes, footprints = footprints, wallZones = {} }
end

local function blocked(box, keep, placed): boolean
	for _, fp in keep.footprints do
		if Box.overlapsXZ(box, fp) then
			return true
		end
	end
	for _, v in keep.volumes do
		if Box.intersects(box, v, 0.01) then
			return true
		end
	end
	for _, o in placed do
		if Box.overlapsXZ(box, Box.expand(o, 1, 0, 1)) and Box.intersects(Box.expand(box, 0, 0.5, 0), o) then
			return true
		end
	end
	return false
end

-- Returns the decor list for a validated room. Deterministic for (room.seed, room.templateId).
function Dressing.dress(room): { any }
	local items = CATALOG[room.familyId]
	if not items then
		return {}
	end
	local w, d, h = room.size.w, room.size.d, room.size.h
	local rng = Rng.new(Rng.derive(room.seed, "dressing:" .. room.templateId))
	local keep = Dressing.keepOut(room)
	local budget = Dressing.BLOCK_BUDGET - #room.waveMouths
	local used = 0
	local decor = {}
	local placedBoxes = {}

	local perimeter = 2 * (w + d)
	local target = math.clamp(math.floor(perimeter / 26), 3, 16)
	local walls = { { id = "N", len = w }, { id = "S", len = w }, { id = "E", len = d }, { id = "W", len = d } }
	local placedCount = 0
	for _ = 1, target * 10 do
		if placedCount >= target then
			break
		end
		local item = rng:pick(items)
		if used + #item.parts > budget then
			continue
		end
		local wall = walls[rng:nextInt(1, 4)]
		local half = wall.len / 2 - item.w / 2 - 1
		if half <= 0 then
			continue
		end
		local along = rng:nextRange(-half, half)
		local bbox = footprint(wall.id, w, d, along, item)
		if not Box.insideRoom(bbox, w, d, h, 1e-6) or blocked(bbox, keep, placedBoxes) then
			continue
		end
		local parts = {}
		for i, p in item.parts do
			parts[i] = { box = toRoom(wall.id, w, d, along, p), role = p.role }
		end
		table.insert(decor, {
			id = "decor" .. (placedCount + 1),
			kind = if item.wallMounted then "wall" else "furniture",
			assetKey = item.key,
			wall = wall.id,
			collide = not item.wallMounted,
			bbox = bbox,
			parts = parts,
		})
		table.insert(placedBoxes, bbox)
		used += #item.parts
		placedCount += 1
	end

	-- floor rugs: one per ~1800 studs^2 of floor (max 3), never collide, never under the spawn sas
	local rugs = math.clamp(math.floor(w * d / 1800), 0, 3)
	for i = 1, rugs do
		if used + 1 > budget then
			break
		end
		for _ = 1, 20 do
			local rw, rd = rng:nextRange(14, 24), rng:nextRange(10, 18)
			local cx = rng:nextRange(-w / 2 + rw / 2 + 4, w / 2 - rw / 2 - 4)
			local cz = rng:nextRange(-d / 2 + rd / 2 + 10, d / 2 - rd / 2 - 4)
			local rug = Box.new(cx, 0.05, cz, rw, 0.1, rd)
			if not Box.overlapsXZ(rug, Box.expand(room.spawnZones[1], 2, 0, 2)) and not Box.overlapsXZ(rug, room.exitClearance) then
				table.insert(decor, {
					id = "rug" .. i,
					kind = "rug",
					assetKey = "decor_" .. room.familyId .. "_rug",
					collide = false,
					bbox = rug,
					parts = { { box = rug, role = if i % 2 == 1 then "accent" else "structure" } },
				})
				used += 1
				break
			end
		end
	end

	-- ceiling light panels on a coarse grid, skipping mouths and ceiling openings
	local lights = math.clamp(math.floor(w * d / 1200), 2, 6)
	local cols = math.max(1, math.ceil(math.sqrt(lights * w / d)))
	local rows = math.max(1, math.ceil(lights / cols))
	local n = 0
	for r = 1, rows do
		for c = 1, cols do
			if n >= lights or used + 1 > budget then
				break
			end
			local cx = -w / 2 + (c - 0.5) * w / cols
			local cz = -d / 2 + (r - 0.5) * d / rows
			local panel = Box.new(cx, h - 0.15, cz, 8, 0.3, 3)
			local clash = false
			for _, m in room.waveMouths do
				clash = clash or Box.overlapsXZ(panel, Box.expand(m, 2, 0, 2))
			end
			for _, op in room.ceilingOpenings or {} do
				clash = clash or Box.overlapsXZ(panel, op)
			end
			if room.exitType == "roof" then
				clash = clash or Box.overlapsXZ(panel, Box.expand(room.exitOpening, 2, 0, 2))
			end
			if not clash then
				n += 1
				table.insert(decor, {
					id = "light" .. n,
					kind = "light",
					assetKey = "decor_ceiling_light",
					collide = false,
					bbox = panel,
					parts = { { box = panel, role = "glow" } },
				})
				used += 1
			end
		end
	end
	return decor
end

function Dressing.blockCount(decor: { any }): number
	local n = 0
	for _, item in decor do
		n += #item.parts
	end
	return n
end

return Dressing
