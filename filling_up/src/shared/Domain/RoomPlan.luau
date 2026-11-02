--!strict
-- Deterministic room planning (docs/04 §4-§13, docs/05 §6).
--   selectSpec(depth, runSeed, history, profile) -> family/format/exit for that depth
--   generate(spec, depth, seed)                  -> RoomDefinition (route graph FIRST, then dressing)
--   build(spec, depth, seed)                     -> validated room, or certified fallback + diagnostic
-- A room = an architecture shell, a protected exit ledge with its 8x8x10 clearance, a backward-
-- built chain of supports (structural pedestal + 1-2 stable props), optional mechanism props,
-- wave mouths placed outside protected corridors, 3 milestone heights and 6 optional tokens.
-- Same (spec, depth, seed) => same room on every machine (Rng is bit32-based).

local Config = require(script.Parent.Parent.GeneratedConfig)
local Box = require(script.Parent.Parent.Util.Box)
local Rng = require(script.Parent.Parent.Util.Rng)
local Jump = require(script.Parent.JumpModel)
local Difficulty = require(script.Parent.Difficulty)
local Validator = require(script.Parent.RouteValidator)
local Dressing = require(script.Parent.SetDressing)

local Rooms = Config.Rooms
local Rules = Rooms.validation_rules

local Plan = {}

local FAMILIES: { [string]: any } = {}
for _, f in Rooms.families do
	FAMILIES[f.id] = f
end
Plan.FAMILIES = FAMILIES

local PROPS: { [string]: any } = {}
for _, f in Rooms.families do
	for _, p in f.props do
		PROPS[p.id] = p
	end
end
Plan.PROPS = PROPS

local EXIT_SILL_RATIO = { door = 0.35, window = 0.55, duct = 0.35, roof = nil, tailgate = 0, floor_hatch = 0 }
local LEVER_RATIO = 0.45
local CLEAR = Rules.exit_approach_clearance_studs
local MOUTH_SIZE = 8
local WALL_MARGIN = 0.5
local MAX_NODES = 48

Plan.MAX_ATTEMPTS = 12

------------------------------------------------------------------------------------------------
-- Spec selection
------------------------------------------------------------------------------------------------
function Plan.releaseProfile(name: string?)
	return Rooms.release_profiles[name or "mvp"]
end

local function inList(list: { string }, v: string): boolean
	return table.find(list, v) ~= nil
end

-- Certified combinations (filled by tools/certify_rooms.luau output when present).
local certified: { [string]: boolean }? = nil
function Plan.setCertified(map: { [string]: boolean }?)
	certified = map
end
function Plan.comboKey(family: string, format: string, exit: string): string
	return family .. "/" .. format .. "/" .. exit
end

function Plan.candidateCombos(depth: number, profileName: string?): { { family: string, format: string, exit: string } }
	local prof = Plan.releaseProfile(profileName)
	local out = {}
	for _, famId in prof.families do
		local fam = FAMILIES[famId]
		if fam.minimum_depth <= depth then
			for _, fmt in prof.formats do
				for _, ex in prof.exits do
					if inList(fam.exits, ex) then
						local key = Plan.comboKey(famId, fmt, ex)
						if certified == nil or (certified :: any)[key] then
							table.insert(out, { family = famId, format = fmt, exit = ex })
						end
					end
				end
			end
		end
	end
	return out
end

-- history: list of previous specs (most recent last)
function Plan.selectSpec(depth: number, runSeed: number, history: { any }, profileName: string?): any
	local prof = Plan.releaseProfile(profileName)
	local first = Rooms.first_rooms[depth]
	if first then
		local spec = {
			family = first.family,
			format = first.format,
			exit = first.exit,
			guestProps = first.guest_props,
			allowedBehaviors = first.allowed_behaviors,
			propVariant = nil,
			scripted = true,
		}
		if not inList(prof.families, first.family) and prof.use_first_room_substitutions and first.mvp_substitution then
			local sub = first.mvp_substitution
			spec.family, spec.format, spec.exit = sub.family, sub.format, sub.exit
			spec.propVariant = sub.prop_behavior_variant
		end
		return spec
	end
	local rng = Rng.new(Rng.derive(runSeed, "spec:" .. depth))
	local combos = Plan.candidateCombos(depth, profileName)
	assert(#combos > 0, "no certified combination available")
	local n = #history
	local last, prev = history[n], history[n - 1]
	local maxSame = Rules.maximum_identical_family_format_exit_in_a_row
	local filtered = {}
	for _, c in combos do
		local same = 0
		for k = n, math.max(1, n - maxSame + 1), -1 do
			local hk = history[k]
			if hk and hk.family == c.family and hk.format == c.format and hk.exit == c.exit then
				same += 1
			else
				break
			end
		end
		-- avoid >2 identical in a row; also avoid same family three times in a row (variety)
		local famRun = last and prev and last.family == c.family and prev.family == c.family
		if same < maxSame and not famRun then
			table.insert(filtered, c)
		end
	end
	if #filtered == 0 then
		filtered = combos
	end
	-- weighted pick (release_profiles.format_weights): very large formats come up more often
	local weights = prof.format_weights or {}
	local total = 0
	for _, cc in filtered do
		total += weights[cc.format] or 1
	end
	local roll = rng:nextNumber() * total
	local c = filtered[#filtered]
	for _, cc in filtered do
		roll -= weights[cc.format] or 1
		if roll <= 0 then
			c = cc
			break
		end
	end
	local band = Difficulty.bandForDepth(depth)
	return {
		family = c.family,
		format = c.format,
		exit = c.exit,
		guestProps = nil,
		allowedBehaviors = { "stable", "bounce", "moving", "temporary" },
		propVariant = nil,
		scripted = false,
		bandId = band.id,
	}
end

------------------------------------------------------------------------------------------------
-- Geometry helpers
------------------------------------------------------------------------------------------------
local function stableProps(fam, depth: number, minTop: number?): { any }
	local out = {}
	for _, p in fam.props do
		if p.behavior == "stable" and (p.stage or 1) <= depth then
			local wt = p.collider.walkable_top
			if minTop == nil or math.min(wt[1], wt[2]) >= minTop then
				table.insert(out, p)
			end
		end
	end
	return out
end

local function sillHeight(exit: string, h: number): number
	if exit == "roof" then
		return h - 6
	end
	local ratio = EXIT_SILL_RATIO[exit] or 0.35
	if ratio == 0 then
		return 0
	end
	return math.clamp(math.floor(ratio * h + 0.5), 6, h - CLEAR[3])
end

-- Column = structural pedestal (navy architecture block) + optional lower prop + top prop.
-- Returns stack list (bottom->top) of { propId?, box, kind } and actual top, or nil.
local function buildColumn(rng, fam, depth: number, cx: number, cz: number, rotate: boolean, targetTop: number, forcedTopProp: string?)
	local tops = stableProps(fam, depth, Validator.MIN_LANDING)
	if forcedTopProp then
		tops = { PROPS[forcedTopProp] }
	end
	if #tops == 0 then
		return nil
	end
	for _ = 1, 8 do
		local top = rng:pick(tops)
		local tw, td, th = top.collider.size_studs[1], top.collider.size_studs[2], top.collider.size_studs[3]
		if rotate then
			tw, td = td, tw
		end
		local stack = {}
		local height = th
		local lower = nil
		if rng:nextNumber() < 0.45 then
			-- a lower prop whose top fully supports the upper collider footprint
			local cands = {}
			for _, p in stableProps(fam, depth, nil) do
				local lw, ld = p.collider.walkable_top[1], p.collider.walkable_top[2]
				if rotate then
					lw, ld = ld, lw
				end
				if lw >= tw and ld >= td and p.id ~= top.id then
					table.insert(cands, p)
				end
			end
			if #cands > 0 then
				lower = rng:pick(cands)
				height += lower.collider.size_studs[3]
			end
		end
		local pedestal = targetTop - height
		if pedestal < -1e-9 then
			if lower then
				lower = nil
				height = th
				pedestal = targetTop - height
			end
			if pedestal < -1e-9 then
				continue
			end
		end
		local y = 0
		local baseW, baseD = tw, td
		if lower then
			baseW, baseD = lower.collider.size_studs[1], lower.collider.size_studs[2]
			if rotate then
				baseW, baseD = baseD, baseW
			end
		end
		if pedestal > 0.05 then
			table.insert(stack, { propId = nil, kind = "pedestal", box = Box.onFloor(cx, 0, cz, baseW, pedestal, baseD) })
			y = pedestal
		else
			pedestal = 0
		end
		if lower then
			local lh = lower.collider.size_studs[3]
			table.insert(stack, { propId = lower.id, kind = "prop", box = Box.onFloor(cx, y, cz, baseW, lh, baseD) })
			y += lh
		end
		table.insert(stack, { propId = top.id, kind = "prop", box = Box.onFloor(cx, y, cz, tw, th, td) })
		y += th
		local wt = top.collider.walkable_top
		local ww, wd = wt[1], wt[2]
		if rotate then
			ww, wd = wd, ww
		end
		return {
			stack = stack,
			topY = y,
			footprint = { w = math.max(baseW, tw), d = math.max(baseD, td) },
			walkable = { w = ww, d = wd },
			topProp = top.id,
		}
	end
	return nil
end

local function footprintBox(cx: number, cz: number, w: number, d: number, top: number): any
	return Box.onFloor(cx, 0, cz, w, math.max(top, 0.01), d)
end

------------------------------------------------------------------------------------------------
-- Generation
------------------------------------------------------------------------------------------------
function Plan.generate(spec, depth: number, seed: number, attempt: number?): any
	local fam = FAMILIES[spec.family]
	assert(fam, "unknown family " .. tostring(spec.family))
	local dims = fam.formats[spec.format]
	local w, d, h = dims[1], dims[2], dims[3]
	local band = Difficulty.bandForDepth(depth)
	local ratio = band.maximum_required_gap_ratio
	local rng = Rng.new(Rng.derive(seed, string.format("layout:%s:%d", spec.family, attempt or 0)))
	local diagnostics = {}
	local nodes, edges, solids = {}, {}, {}

	local floor = {
		id = "floor",
		kind = "floor",
		box = Box.new(0, -0.5, 0, w, 1, d),
		topY = 0,
		walkable = { w = w, d = d },
		stack = {},
		arrival = "present",
		behavior = "stable",
		protected = false,
	}
	table.insert(nodes, floor)

	-- spawn: protected sas mouth on the -Z wall
	local spawn = Box.onFloor(0, 0, -d / 2 + 3.5, 8, 6, 7)

	-- exit ledge (protected pillar) + clearance + opening
	local exit = spec.exit
	local sill = sillHeight(exit, h)
	local lever = nil
	local ledgeX, ledgeZ
	local opening
	local roofCanopy = nil
	if exit == "door" or exit == "duct" then
		local wallZ = if exit == "door" then d / 2 else -d / 2
		ledgeX = rng:nextRange(-w / 2 + 6, w / 2 - 6)
		if exit == "duct" then
			ledgeX = if rng:nextNumber() < 0.5 then -w / 2 + 6 else w / 2 - 6
		end
		ledgeZ = wallZ - math.sign(wallZ) * CLEAR[2] / 2
		opening = Box.new(ledgeX, sill + CLEAR[3] / 2, wallZ, CLEAR[1], CLEAR[3], 1)
	elseif exit == "window" then
		ledgeX = w / 2 - CLEAR[1] / 2
		ledgeZ = rng:nextRange(-d / 2 + 12, d / 2 - 6)
		opening = Box.new(w / 2, sill + CLEAR[3] / 2, ledgeZ, 1, CLEAR[3], CLEAR[2])
	elseif exit == "roof" then
		ledgeX = (if rng:nextNumber() < 0.5 then -1 else 1) * (w / 2 - CLEAR[1] / 2)
		ledgeZ = d / 2 - CLEAR[2] / 2
		opening = Box.new(ledgeX, h, ledgeZ, CLEAR[1], 1, CLEAR[2])
		-- raised canopy ("auvent") over the hatch and its approach: protects jump arcs and camera
		roofCanopy = Box.new(ledgeX - math.sign(ledgeX) * 6, h, ledgeZ - 6, 20, 1, 20)
	else -- tailgate / floor_hatch: low exit opened by a high lever
		ledgeX = rng:nextRange(-w / 2 + 6, w / 2 - 6)
		ledgeZ = d / 2 - CLEAR[2] / 2
		opening = if exit == "tailgate"
			then Box.new(ledgeX, CLEAR[3] / 2, d / 2, CLEAR[1], CLEAR[3], 1)
			else Box.new(ledgeX, 0, ledgeZ, CLEAR[1], 1, CLEAR[2])
	end

	local ledge = {
		id = "exit_ledge",
		kind = "exit_ledge",
		box = footprintBox(ledgeX, ledgeZ, CLEAR[1], CLEAR[2], sill),
		topY = sill,
		walkable = { w = CLEAR[1], d = CLEAR[2] },
		stack = {},
		arrival = "present",
		behavior = "stable",
		protected = true,
	}
	table.insert(nodes, ledge)
	if sill > 0 then
		table.insert(solids, { nodeId = "exit_ledge", kind = "architecture", box = ledge.box })
	end
	local clearance = Box.onFloor(ledgeX, sill, ledgeZ, CLEAR[1], CLEAR[3], CLEAR[2])

	local exitTargetId = "exit_ledge"
	local climbTarget = ledge
	if exit == "tailgate" or exit == "floor_hatch" then
		-- lever pillar placed on the opposite half; the climb goes to the lever, then a gate edge
		local lt = math.clamp(math.floor(LEVER_RATIO * h + 0.5), 8, h - 10)
		local lx = -ledgeX
		local lz = -d / 2 + 14
		lever = {
			id = "lever",
			kind = "exit_ledge",
			box = footprintBox(lx, lz, 8, 8, lt),
			topY = lt,
			walkable = { w = 8, d = 8 },
			stack = {},
			arrival = "present",
			behavior = "stable",
			protected = true,
		}
		table.insert(nodes, lever)
		table.insert(solids, { nodeId = "lever", kind = "architecture", box = lever.box })
		climbTarget = lever
		table.insert(edges, { from = "lever", to = "exit_ledge", gap = 0, rise = -lt, kind = "gate" })
	end

	-- backward chain from the climb target down to the floor
	local maxRise = Jump.maxRequiredRise()
	local current = climbTarget
	local guestQueue = {}
	for _, g in spec.guestProps or {} do
		table.insert(guestQueue, g)
	end
	local idx = 0
	local spawnBlock = Box.expand(spawn, 2, 0, 2)
	local clearanceBlock = Box.expand(clearance, 1, 0.5, 1)
	local HEADROOM = Jump.AVATAR.height + 1.5
	local headrooms = {
		{
			nodeId = climbTarget.id,
			box = Box.onFloor(
				climbTarget.box.cx,
				climbTarget.topY,
				climbTarget.box.cz,
				climbTarget.walkable.w,
				HEADROOM,
				climbTarget.walkable.d
			),
		},
	}
	-- 3D occupancy test for a candidate support (all its solids + its own headroom)
	local function free(parts, cx: number, cz: number, topY: number, walk, isColumn: boolean): boolean
		local head = Box.onFloor(cx, topY, cz, walk.w, HEADROOM, walk.d)
		if topY + Jump.AVATAR.height + 0.5 > h and exit ~= "roof" then
			return false
		end
		for _, part in parts do
			local b = part
			if not Box.insideRoom(Box.expand(b, WALL_MARGIN, 0, WALL_MARGIN), w, d, h) then
				return false
			end
			if (isColumn and Box.overlapsXZ(b, spawnBlock)) or Box.intersects(b, Box.expand(spawn, 1, 1, 1)) then
				return false
			end
			if Box.intersects(b, clearanceBlock) then
				return false
			end
			local grown = Box.expand(b, 0.5, 0, 0.5)
			for _, s2 in solids do
				if Box.intersects(grown, s2.box) then
					return false
				end
			end
			for _, hr in headrooms do
				if Box.intersects(b, hr.box) then
					return false
				end
			end
		end
		if Box.intersects(head, clearanceBlock) then
			return false
		end
		for _, s2 in solids do
			if Box.intersects(head, s2.box) then
				return false
			end
		end
		return true
	end
	local arcBodies = {}
	local roomStub = { exitType = exit, exitOpening = opening, ceilingOpenings = if roofCanopy then { roofCanopy } else {} }
	-- incremental arc test for the hop newNode -> current (and new solids vs earlier arcs)
	local function arcOk(newNode, target, newParts): (boolean, { any }?)
		if newNode.kind == "floor" then
			return true, {}
		end
		local bodies = Validator.arcBodies(newNode, target)
		for _, body in bodies do
			if Box.top(body) > h and not Validator.underCeilingOpening(roomStub, body.cx, body.cz) then
				return false, nil
			end
			for _, s2 in solids do
				if s2.nodeId ~= target.id and Box.intersects(body, s2.box, 0.02) then
					return false, nil
				end
			end
		end
		for _, part in newParts do
			for _, ab in arcBodies do
				if ab.owner ~= target.id and Box.intersects(part, ab.box, 0.02) then
					return false, nil
				end
			end
		end
		return true, bodies
	end
	local function freeFootprint(fp): boolean
		-- optional floor props: 2D test against everything already on the floor plan
		if not Box.insideRoom(Box.expand(fp, WALL_MARGIN, 0, WALL_MARGIN), w, d, h + 100) then
			return false
		end
		if Box.overlapsXZ(fp, spawnBlock) or Box.overlapsXZ(fp, clearanceBlock) then
			return false
		end
		for _, s2 in solids do
			if Box.overlapsXZ(Box.expand(fp, 0.5, 0, 0.5), s2.box) then
				return false
			end
		end
		return true
	end
	local function shelfAt(top, targetTop: number, rotate: boolean)
		-- suspended structural shelf (1-stud slab, hung by non-colliding chains) carrying one prop
		local tw, td, th = top.collider.size_studs[1], top.collider.size_studs[2], top.collider.size_studs[3]
		if rotate then
			tw, td = td, tw
		end
		local slabTop = targetTop - th
		if slabTop < 3 then
			return nil
		end
		local wt = top.collider.walkable_top
		local ww, wd = wt[1], wt[2]
		if rotate then
			ww, wd = wd, ww
		end
		return {
			stack = {
				{ propId = nil, kind = "shelf", box = Box.onFloor(0, slabTop - 1, 0, tw + 1, 1, td + 1) },
				{ propId = top.id, kind = "prop", box = Box.onFloor(0, slabTop, 0, tw, th, td) },
			},
			topY = targetTop,
			footprint = { w = tw + 1, d = td + 1 },
			walkable = { w = ww, d = wd },
			topProp = top.id,
		}
	end
	while current.topY > maxRise + 1e-9 do
		idx += 1
		if idx > MAX_NODES then
			table.insert(diagnostics, "too_many_nodes")
			return nil, diagnostics
		end
		local placed = false
		local guest = guestQueue[1]
		for _ = 1, 40 do
			local rise = rng:nextRange(2.0, maxRise)
			local targetTop = math.max(current.topY - rise, 0)
			local rotate = rng:nextNumber() < 0.5
			local col
			local isColumn = true
			if guest == nil and targetTop > 9 and (targetTop > 12 or rng:nextNumber() < 0.65) then
				local tops = stableProps(fam, depth, Validator.MIN_LANDING)
				if #tops > 0 then
					col = shelfAt(rng:pick(tops), targetTop, rotate)
					isColumn = false
				end
			end
			if col == nil then
				isColumn = true
				col = buildColumn(rng, fam, depth, 0, 0, rotate, targetTop, guest and guest.prop_id or nil)
			end
			if col == nil then
				continue
			end
			local actualRise = current.topY - col.topY
			if actualRise > maxRise + 1e-9 or actualRise < 0.5 then
				continue
			end
			local maxGap = ratio * Jump.reach(actualRise) * 0.92
			local gap = rng:nextRange(math.min(1.0, maxGap), maxGap)
			-- try directions, preferring toward the room centre and the spawn side
			local dirs = rng:shuffle({
				{ 1, 0 },
				{ -1, 0 },
				{ 0, 1 },
				{ 0, -1 },
				{ 0.7071, 0.7071 },
				{ -0.7071, 0.7071 },
				{ 0.7071, -0.7071 },
				{ -0.7071, -0.7071 },
			})
			for _, dv in dirs do
				local cw, cd = col.walkable.w, col.walkable.d
				local curTop = Box.new(current.box.cx, current.topY, current.box.cz, current.walkable.w, 0.01, current.walkable.d)
				-- distance between centres so that the edge gap along dv equals `gap`
				local cx, cz = curTop.cx, curTop.cz
				local step = 0
				local candidate
				for _ = 1, 40 do
					step += 0.5
					cx = curTop.cx + dv[1] * step
					cz = curTop.cz + dv[2] * step
					local tb = Box.new(cx, col.topY, cz, cw, 0.01, cd)
					local gg = Box.gapXZ(tb, curTop)
					if gg >= gap then
						candidate = { cx = cx, cz = cz, gap = gg }
						break
					end
				end
				if candidate and candidate.gap <= maxGap + 1e-9 then
					local fp = footprintBox(candidate.cx, candidate.cz, col.footprint.w, col.footprint.d, col.topY)
					local parts = {}
					for _, part in col.stack do
						local b = part.box
						table.insert(parts, Box.new(b.cx + candidate.cx, b.cy, b.cz + candidate.cz, b.sx, b.sy, b.sz))
					end
					if not isColumn then
						local bottom = Box.bottom(parts[1])
						fp = Box.new(
							candidate.cx,
							(bottom + col.topY) / 2,
							candidate.cz,
							col.footprint.w,
							col.topY - bottom,
							col.footprint.d
						)
					end
					local probe = {
						id = "probe",
						kind = "column",
						box = Box.new(candidate.cx, col.topY, candidate.cz, col.walkable.w, 0.01, col.walkable.d),
						topY = col.topY,
						walkable = col.walkable,
					}
					local okArc, bodies = false, nil
					if free(parts, candidate.cx, candidate.cz, col.topY, col.walkable, isColumn) then
						okArc, bodies = arcOk(probe, current, parts)
					end
					if okArc then
						for _, b in bodies :: { any } do
							table.insert(arcBodies, { owner = current.id, box = b })
						end
						local id = string.format("n%02d", idx)
						local stack = {}
						for _, part in col.stack do
							local b = part.box
							local moved = Box.new(b.cx + candidate.cx, b.cy, b.cz + candidate.cz, b.sx, b.sy, b.sz)
							table.insert(stack, { propId = part.propId, kind = part.kind, box = moved })
							table.insert(solids, { nodeId = id, kind = part.kind, propId = part.propId, box = moved })
						end
						table.insert(headrooms, {
							nodeId = id,
							box = Box.onFloor(candidate.cx, col.topY, candidate.cz, col.walkable.w, HEADROOM, col.walkable.d),
						})
						local node = {
							id = id,
							kind = if isColumn then "column" else "shelf",
							box = fp,
							topY = col.topY,
							walkable = col.walkable,
							stack = stack,
							arrival = if guest then "wave1" else "present",
							behavior = "stable",
							protected = (current == climbTarget),
							topProp = col.topProp,
						}
						table.insert(nodes, node)
						table.insert(edges, 1, { from = id, to = current.id, gap = candidate.gap, rise = actualRise, kind = "jump" })
						current = node
						placed = true
						if guest then
							table.remove(guestQueue, 1)
						end
						break
					end
				end
			end
			if placed then
				break
			end
		end
		if not placed then
			table.insert(diagnostics, "placement_failed_at_node_" .. idx)
			return nil, diagnostics
		end
	end
	table.insert(edges, 1, { from = "floor", to = current.id, gap = 0, rise = current.topY, kind = "jump" })

	-- optional mechanism props on the floor (never on the required path)
	local allowed = spec.allowedBehaviors or { "stable" }
	local optionalCount = 0
	for _, beh in { "bounce", "moving", "temporary" } do
		if inList(allowed, beh) then
			local cands = {}
			for _, p in fam.props do
				if p.behavior == beh and (p.stage or 1) <= depth then
					table.insert(cands, p)
				end
			end
			if #cands > 0 then
				local p = rng:pick(cands)
				local sw, sd = p.collider.size_studs[1], p.collider.size_studs[2]
				local params = p.behavior_params or {}
				local sweepW, sweepD = sw, sd
				if beh == "moving" and params.axis == "width" then
					sweepW += params.travel_studs or 0
				elseif beh == "moving" and params.axis == "depth" then
					sweepD += params.travel_studs or 0
				end
				for _ = 1, 25 do
					local cx = rng:nextRange(-w / 2 + sweepW / 2 + 1, w / 2 - sweepW / 2 - 1)
					local cz = rng:nextRange(-d / 2 + sweepD / 2 + 1, d / 2 - sweepD / 2 - 1)
					local sweep = footprintBox(cx, cz, sweepW, sweepD, p.collider.size_studs[3])
					if freeFootprint(Box.expand(sweep, 1.5, 0, 1.5)) then
						optionalCount += 1
						local id = "opt" .. optionalCount
						local box = Box.onFloor(cx, 0, cz, sw, p.collider.size_studs[3], sd)
						table.insert(nodes, {
							id = id,
							kind = "column",
							box = box,
							topY = Box.top(box),
							walkable = { w = p.collider.walkable_top[1], d = p.collider.walkable_top[2] },
							stack = { { propId = p.id, kind = "prop", box = box } },
							arrival = "present",
							behavior = beh,
							protected = false,
							optional = true,
							sweep = sweep,
							behaviorParams = params,
						})
						table.insert(solids, { nodeId = id, kind = "optional", propId = p.id, box = sweep })
						break
					end
				end
			end
		end
	end

	-- wave mouths (ceiling chutes): outside exit clearance, protected supports and spawn
	local mouths = {}
	local protectedNodes = {}
	for _, n in nodes do
		if n.protected then
			table.insert(protectedNodes, n)
		end
	end
	local waveParams = Difficulty.waveParams(band, spec.family, spec.format)
	for _ = 1, waveParams.mouths do
		local ok = false
		for _ = 1, 200 do
			local mx = rng:nextRange(-w / 2 + MOUTH_SIZE / 2 + 1, w / 2 - MOUTH_SIZE / 2 - 1)
			local mz = rng:nextRange(-d / 2 + MOUTH_SIZE / 2 + 1, d / 2 - MOUTH_SIZE / 2 - 1)
			local m = Box.new(mx, h - 0.5, mz, MOUTH_SIZE, 1, MOUTH_SIZE)
			local corridor = Box.expand(m, 1, 0, 1)
			local bad = Box.overlapsXZ(corridor, clearance) or Box.overlapsXZ(Box.expand(corridor, 2, 0, 2), spawn)
			for _, n in protectedNodes do
				bad = bad or Box.overlapsXZ(corridor, n.box)
			end
			for _, other in mouths do
				bad = bad or Box.overlapsXZ(Box.expand(corridor, 2, 0, 2), other)
			end
			if not bad then
				table.insert(mouths, m)
				ok = true
				break
			end
		end
		if not ok then
			table.insert(diagnostics, "mouth_placement_failed")
			return nil, diagnostics
		end
	end

	-- milestones: progressive zones between floor and climb target
	local milestoneHeights = { climbTarget.topY * 0.25, climbTarget.topY * 0.5, climbTarget.topY * 0.75 }

	-- optional tokens (6): above route node tops, then on the floor near the route
	local tokens = {}
	local tokenCount = Config.Economy.optional_tokens.tokens_per_room
	local routeNodes = {}
	for _, n in nodes do
		if (n.kind == "column" or n.kind == "shelf") and not n.optional then
			table.insert(routeNodes, n)
		end
	end
	for i = 1, tokenCount do
		local n = routeNodes[((i - 1) % math.max(1, #routeNodes)) + 1]
		if n and i <= #routeNodes then
			table.insert(
				tokens,
				{ id = i, x = n.box.cx + rng:nextRange(-1.5, 1.5), y = n.topY + 2.5, z = n.box.cz + rng:nextRange(-1.5, 1.5) }
			)
		else
			local x = rng:nextRange(-w / 2 + 3, w / 2 - 3)
			local z = rng:nextRange(-d / 2 + 10, d / 2 - 3)
			table.insert(tokens, { id = i, x = x, y = 2.5, z = z })
		end
	end

	local templateId = string.format("%s_%s_%s", spec.family, spec.format, exit)
	return {
		templateId = templateId,
		familyId = spec.family,
		formatId = spec.format,
		exitType = exit,
		seed = seed,
		depth = depth,
		size = { w = w, d = d, h = h },
		routeGraph = { nodes = nodes, edges = edges },
		solids = solids,
		spawnZones = { spawn },
		safeZones = { spawn, clearance },
		exitClearance = clearance,
		exitOpening = opening,
		exitTargetId = exitTargetId,
		leverId = lever and lever.id or nil,
		waveMouths = mouths,
		ceilingOpenings = if roofCanopy then { roofCanopy } else {},
		collisionBudget = {
			dynamic = Config.Runtime.streaming.max_dynamic_objects,
			static = Rules.maximum_static_colliders_active_room,
			decor = Rules.maximum_decorative_blocks_active_room,
		},
		themeManifestId = "theme_" .. spec.family,
		tokens = tokens,
		milestoneHeights = milestoneHeights,
		fallback = false,
		diagnostics = diagnostics,
		bandId = band.id,
		gapRatio = ratio,
		propVariant = spec.propVariant,
	},
		diagnostics
end

-- Certified fallback: a straight staircase of structural shelves along the -X wall toward the
-- exit, built so every hop is a 4-stud rise with a 1-stud gap. Used when random layouts fail.
function Plan.fallback(spec, depth: number, seed: number): any
	local fbSpec = table.clone(spec)
	fbSpec.guestProps = nil
	fbSpec.allowedBehaviors = { "stable" }
	-- deterministic attempt index far from normal attempts; layout with smaller rises/gaps
	for attempt = 100, 140 do
		local room = Plan.generate(fbSpec, depth, seed, attempt)
		if room then
			local ok = Validator.validate(room, { gapRatio = room.gapRatio })
			if ok then
				room.fallback = true
				return room
			end
		end
	end
	return nil
end

-- Set dressing after validation (decision 0018): it cannot change the layout; if the independent
-- decor check ever refuses it, the room ships undressed with a diagnostic (never a broken room).
local function dress(room, diags: { string })
	room.decor = Dressing.dress(room)
	local ok, errs = Validator.validateDecor(room, Dressing.BLOCK_BUDGET)
	if not ok then
		table.insert(diags, "decor_rejected: " .. table.concat(errs, ","))
		room.decor = {}
	end
end

-- Validated room or certified fallback, with diagnostics. Never returns an unvalidated room.
function Plan.build(spec, depth: number, seed: number): (any, { string })
	local diags = {}
	for attempt = 0, Plan.MAX_ATTEMPTS - 1 do
		local room, d = Plan.generate(spec, depth, seed, attempt)
		if room then
			local ok, report = Validator.validate(room, { gapRatio = room.gapRatio })
			if ok then
				room.attempt = attempt
				dress(room, diags)
				return room, diags
			end
			table.insert(diags, string.format("attempt %d rejected: %s", attempt, table.concat(report.errors, ",")))
		else
			table.insert(diags, string.format("attempt %d failed: %s", attempt, table.concat(d or {}, ",")))
		end
	end
	local fb = Plan.fallback(spec, depth, seed)
	table.insert(diags, "fallback_used")
	if fb then
		dress(fb, diags)
	end
	return fb, diags
end

------------------------------------------------------------------------------------------------
-- Tutorial cell (24 x 24 x 16): falling carton then a step to an exit at 8 studs.
------------------------------------------------------------------------------------------------
function Plan.tutorialCell(): any
	local w, d, h = 24, 24, 16
	local carton = PROPS.reception_carton
	local cs = carton.collider.size_studs
	local nodes, solids = {}, {}
	table.insert(nodes, {
		id = "floor",
		kind = "floor",
		box = Box.new(0, -0.5, 0, w, 1, d),
		topY = 0,
		walkable = { w = w, d = d },
		stack = {},
		arrival = "present",
		behavior = "stable",
		protected = false,
	})
	-- carton 10 x 8 x 4 centred at z = 0: 1 stud clear of the spawn sas (z <= -5), touching the
	-- 8-stud exit ledge (z >= 4) so the second step is a plain 4-stud rise
	local cbox = Box.onFloor(0, 0, 0, cs[1], cs[3], cs[2])
	table.insert(nodes, {
		id = "carton",
		kind = "column",
		box = cbox,
		topY = Box.top(cbox),
		walkable = { w = cs[1], d = cs[2] },
		stack = { { propId = carton.id, kind = "prop", box = cbox } },
		arrival = "wave1",
		behavior = "stable",
		protected = true,
		topProp = carton.id,
	})
	table.insert(solids, { nodeId = "carton", kind = "prop", propId = carton.id, box = cbox })
	local lz = d / 2 - CLEAR[2] / 2
	local ledgeBox = Box.onFloor(0, 0, lz, CLEAR[1], 8, CLEAR[2])
	table.insert(nodes, {
		id = "exit_ledge",
		kind = "exit_ledge",
		box = ledgeBox,
		topY = 8,
		walkable = { w = CLEAR[1], d = CLEAR[2] },
		stack = {},
		arrival = "present",
		behavior = "stable",
		protected = true,
	})
	table.insert(solids, { nodeId = "exit_ledge", kind = "architecture", box = ledgeBox })
	-- clearance above the 8-stud sill would exceed a 16-stud ceiling: the tutorial door opening
	-- is cut through the wall and the ceiling above the ledge is open (skylight), see decision 0006.
	local clearance = Box.onFloor(0, 8, lz, CLEAR[1], CLEAR[3], CLEAR[2])
	return {
		templateId = "tutorial_cell",
		familyId = "reception",
		formatId = "T",
		exitType = "door",
		seed = 0,
		depth = 0,
		size = { w = w, d = d, h = h },
		routeGraph = {
			nodes = nodes,
			edges = {
				{ from = "floor", to = "carton", gap = 0, rise = 4, kind = "jump" },
				{ from = "carton", to = "exit_ledge", gap = Box.gapXZ(cbox, ledgeBox), rise = 4, kind = "jump" },
			},
		},
		solids = solids,
		spawnZones = { Box.onFloor(0, 0, -d / 2 + 3.5, 8, 6, 7) },
		safeZones = {},
		exitClearance = clearance,
		exitOpening = Box.new(0, 13, d / 2, CLEAR[1], CLEAR[3], 1),
		exitTargetId = "exit_ledge",
		-- no fill waves in the tutorial cell: the carton is a scripted structural drop (0-3 s)
		waveMouths = {},
		structuralDrops = { { nodeId = "carton", propId = carton.id, atSeconds = 0.5 } },
		collisionBudget = { dynamic = 40, static = 120, decor = 80 },
		themeManifestId = "theme_reception",
		tokens = {},
		milestoneHeights = { 2, 4, 6 },
		fallback = false,
		diagnostics = {},
		gapRatio = 0.65,
		-- skylight over the carton and the exit ledge: a full jump never bumps the 16-stud ceiling
		ceilingOpenings = { Box.new(0, h, 3, 12, 1, 18) },
	}
end

return Plan
