--!strict
-- Route validator (docs/05 §6, rooms.json validation_rules). Validates a RoomDefinition produced
-- by RoomPlan BEFORE it can be shown to a player:
--   connection entry -> exit, landing size, head clearance, jump arcs free of solids, ceiling,
--   exit clearance 8x8x10 free of solids and of every wave drop corridor, protected last support,
--   spawn never targeted by a mouth, collider budget, solids inside the room.
-- Purely geometric: it certifies the guaranteed route at structural arrival, not invulnerability.

local Config = require(script.Parent.Parent.GeneratedConfig)
local Box = require(script.Parent.Parent.Util.Box)
local Jump = require(script.Parent.JumpModel)

local Rules = Config.Rooms.validation_rules

local V = {}

V.MIN_LANDING = Rules.minimum_required_landing_short_side_studs
V.MAX_STATIC = Rules.maximum_static_colliders_active_room
V.CLEARANCE = Rules.exit_approach_clearance_studs -- {w, d, h}

local function nodeById(room): { [string]: any }
	local map = {}
	for _, n in room.routeGraph.nodes do
		map[n.id] = n
	end
	return map
end

local function topBox(n): any
	return Box.new(n.box.cx, n.topY, n.box.cz, n.walkable.w, 0.01, n.walkable.d)
end

-- point on `a` footprint closest to `b` center (take-off / landing points)
local function closestPoint(a, b): (number, number)
	local hx, hz = a.sx / 2, a.sz / 2
	local x = math.clamp(b.cx, a.cx - hx, a.cx + hx)
	local z = math.clamp(b.cz, a.cz - hz, a.cz + hz)
	return x, z
end

local function isOwn(solid, n1, n2): boolean
	return solid.nodeId ~= nil and (solid.nodeId == n1.id or solid.nodeId == n2.id)
end

-- Ceiling checks are waived only below explicit openings (roof hatch, skylights).
local function underHatch(room, x: number, z: number): boolean
	for _, o in room.ceilingOpenings or {} do
		if math.abs(x - o.cx) * 2 <= o.sx and math.abs(z - o.cz) * 2 <= o.sz then
			return true
		end
	end
	if room.exitType ~= "roof" then
		return false
	end
	local o = room.exitOpening
	return math.abs(x - o.cx) * 2 <= o.sx and math.abs(z - o.cz) * 2 <= o.sz
end

-- Avatar body boxes sampled along the hop a -> b (feet on the arc), excluding take-off sample.
function V.arcBodies(a, b): { any }
	local ta = topBox(a)
	local tb = topBox(b)
	local x0, z0 = closestPoint(ta, tb)
	local x1, z1 = closestPoint(tb, ta)
	local dx, dz = tb.cx - x1, tb.cz - z1
	local len = math.sqrt(dx * dx + dz * dz)
	if len > 1e-6 then
		x1 += dx / len * math.min(1, len)
		z1 += dz / len * math.min(1, len)
	end
	local bodies = {}
	for i, pt in Jump.arc(x0, a.topY, z0, x1, b.topY, z1, 20) do
		if i > 1 then
			table.insert(bodies, Box.onFloor(pt[1], pt[2] + 0.05, pt[3], Jump.AVATAR.width, Jump.AVATAR.height, Jump.AVATAR.depth))
		end
	end
	return bodies
end

function V.underCeilingOpening(room, x: number, z: number): boolean
	return underHatch(room, x, z)
end

function V.validate(room, opts: { gapRatio: number }): (boolean, { errors: { string }, checks: { [string]: number } })
	local errors: { string } = {}
	local checks: { [string]: number } = {}
	local function fail(msg: string)
		table.insert(errors, msg)
	end
	local function count(k: string)
		checks[k] = (checks[k] or 0) + 1
	end
	local w, d, h = room.size.w, room.size.d, room.size.h
	local nodes = nodeById(room)
	local solids = room.solids

	-- 1. solids inside the room, no interpenetration between different nodes
	for i, s in solids do
		if not Box.insideRoom(s.box, w, d, h, 1e-6) then
			fail("solid_outside_room:" .. tostring(s.nodeId or i))
		end
		-- the player must never appear inside (or under) a support or a structural drop
		for _, sz in room.spawnZones do
			if Box.intersects(s.box, sz, 0.01) then
				fail("spawn_obstructed:" .. tostring(s.nodeId or i))
			end
		end
		for j = i + 1, #solids do
			local o = solids[j]
			if Box.intersects(s.box, o.box, 0.01) then
				fail(string.format("solids_overlap:%s/%s", tostring(s.nodeId or i), tostring(o.nodeId or j)))
			end
		end
		count("solids")
	end
	if #solids + 6 > V.MAX_STATIC then
		fail("static_collider_budget")
	end

	-- 2. connectivity along required edges from floor to the exit target
	local adj: { [string]: { any } } = {}
	for _, e in room.routeGraph.edges do
		adj[e.from] = adj[e.from] or {}
		table.insert(adj[e.from], e)
	end
	local target = room.exitTargetId
	local seen = { floor = true }
	local queue = { "floor" }
	local reachedLever = room.leverId == nil
	while #queue > 0 do
		local id = table.remove(queue, 1)
		for _, e in adj[id] or {} do
			if not seen[e.to] then
				seen[e.to] = true
				table.insert(queue, e.to)
			end
		end
	end
	if not seen[target] then
		fail("exit_unreachable")
	end
	if room.leverId and not seen[room.leverId] then
		fail("lever_unreachable")
	end
	if room.leverId then
		reachedLever = seen[room.leverId] == true
	end
	checks.leverReached = reachedLever and 1 or 0

	-- 3. each required edge: hop feasibility, landing size, head clearance, arc
	for _, e in room.routeGraph.edges do
		local a, b = nodes[e.from], nodes[e.to]
		if not a or not b then
			fail("edge_unknown_node:" .. e.from .. "->" .. e.to)
			continue
		end
		local rise = b.topY - a.topY
		local gap = if a.kind == "floor" then 0 else Box.gapXZ(topBox(a), topBox(b))
		if e.kind == "jump" then
			if not Jump.requiredHopOk(gap, rise, opts.gapRatio) then
				fail(string.format("hop_infeasible:%s->%s gap=%.2f rise=%.2f", a.id, b.id, gap, rise))
			end
			count("hops")
		elseif e.kind == "gate" then
			-- lever opens a low exit; walking/dropping down to it must be safe and short
			if rise > 0.5 then
				fail("gate_requires_climb:" .. b.id)
			end
		end
		if b.kind ~= "floor" and math.min(b.walkable.w, b.walkable.d) < V.MIN_LANDING - 1e-9 then
			fail("landing_too_small:" .. b.id)
		end
		-- head clearance above landing centre (avatar + margin)
		local head = Box.onFloor(b.box.cx, b.topY + 0.02, b.box.cz, Jump.AVATAR.width + 1, Jump.AVATAR.height + 0.5, Jump.AVATAR.width + 1)
		for _, s in solids do
			if s.nodeId ~= b.id and Box.intersects(head, s.box, 0.01) then
				fail("head_clearance:" .. b.id)
				break
			end
		end
		if b.topY + Jump.AVATAR.height + 0.5 > h and not underHatch(room, b.box.cx, b.box.cz) then
			fail("ceiling_over_landing:" .. b.id)
		end
		-- arc obstruction (jump edges only)
		if e.kind == "jump" and a.kind ~= "floor" then
			local blocked = false
			for _, body in V.arcBodies(a, b) do
				for _, s in solids do
					if not isOwn(s, a, b) and Box.intersects(body, s.box, 0.02) then
						fail(string.format("arc_blocked:%s->%s by %s", a.id, b.id, tostring(s.nodeId)))
						blocked = true
						break
					end
				end
				if Box.top(body) > h and not underHatch(room, body.cx, body.cz) then
					fail(string.format("arc_hits_ceiling:%s->%s", a.id, b.id))
					blocked = true
				end
				if blocked then
					break
				end
			end
			count("arcs")
		end
	end

	-- 4. exit clearance volume: free of solids and of drop corridors
	local clr = room.exitClearance
	if math.abs(clr.sx - V.CLEARANCE[1]) > 1e-6 or math.abs(clr.sz - V.CLEARANCE[2]) > 1e-6 or math.abs(clr.sy - V.CLEARANCE[3]) > 1e-6 then
		fail("exit_clearance_size")
	end
	for _, s in solids do
		if Box.intersects(clr, s.box, 0.01) then
			fail("exit_clearance_obstructed:" .. tostring(s.nodeId))
		end
	end
	local protectedBoxes = {}
	for _, n in room.routeGraph.nodes do
		if n.protected then
			table.insert(protectedBoxes, n)
		end
	end
	for mi, m in room.waveMouths do
		local corridor = Box.new(m.cx, h / 2, m.cz, m.sx + 2, h * 2, m.sz + 2)
		if Box.overlapsXZ(corridor, clr) then
			fail("mouth_over_exit_clearance:" .. mi)
		end
		for _, n in protectedBoxes do
			if Box.overlapsXZ(corridor, n.box) then
				fail(string.format("mouth_over_protected:%d/%s", mi, n.id))
			end
		end
		for _, sz in room.spawnZones do
			if Box.overlapsXZ(Box.expand(corridor, 2, 0, 2), sz) then
				fail("mouth_over_spawn:" .. mi)
			end
		end
		count("mouths")
	end

	-- 5. last support before the exit target must be protected
	for _, e in room.routeGraph.edges do
		if e.to == target then
			local last = nodes[e.from]
			if last and last.kind ~= "floor" and not last.protected then
				fail("last_support_not_protected:" .. last.id)
			end
		end
	end
	if not (nodes[target] and nodes[target].protected) then
		fail("exit_target_not_protected")
	end

	return #errors == 0, { errors = errors, checks = checks }
end

return V
