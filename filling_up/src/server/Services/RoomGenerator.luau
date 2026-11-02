--!strict
-- Turns a validated RoomDefinition (shared/Domain/RoomPlan) into Instances inside a fixed local
-- cell. Never builds a room that RouteValidator rejected: RoomPlan.build returns validated rooms
-- or a certified fallback (with a diagnostic event).
local CollectionService = game:GetService("CollectionService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local RoomPlan = require(Shared.Domain.RoomPlan)
local Templates = script.Parent.Parent.RoomTemplates
local PropFactory = require(script.Parent.PropFactory)

local RoomGenerator = {}

local TEMPLATE_BY_FAMILY = {
	reception = "Reception",
	toy = "Toys",
	bureau = "Office",
	kitchen = "Kitchen",
	garage = "Garage",
	bin = "GiantBin",
}

-- Two room cells + one sas cell, far enough apart, reused forever (no drifting chain).
RoomGenerator.CELLS = {
	[1] = CFrame.new(0, 0, 0),
	[2] = CFrame.new(400, 0, 0),
	sas = CFrame.new(200, 0, 300),
}

function RoomGenerator.template(familyId: string)
	return require(Templates:WaitForChild(TEMPLATE_BY_FAMILY[familyId]) :: ModuleScript)
end

local function block(
	parent: Instance,
	name: string,
	origin: CFrame,
	box: any,
	color: Color3,
	material: Enum.Material,
	tag: string?,
	transparency: number?
): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Anchored = true
	p.Size = Vector3.new(box.sx, box.sy, box.sz)
	p.CFrame = origin * CFrame.new(box.cx, box.cy, box.cz)
	p.Color = color
	p.Material = material
	p.Transparency = transparency or 0
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	if tag then
		CollectionService:AddTag(p, tag)
	end
	p.Parent = parent
	return p
end

local function shell(model: Model, origin: CFrame, room: any, tpl: any)
	local w, d, h = room.size.w, room.size.d, room.size.h
	local pal = tpl.palette
	block(
		model,
		"Floor",
		origin,
		{ cx = 0, cy = -0.5, cz = 0, sx = w, sy = 1, sz = d },
		Color3.fromHex("#FFF5DF"),
		tpl.floorMaterial,
		"Architecture"
	)
	local t = 1
	-- walls; the exit wall gets an opening cut as 4 blocks around room.exitOpening when needed
	local walls = {
		{ name = "WallN", cx = 0, cz = d / 2 + t / 2, sx = w + 2 * t, sz = t, axis = "z", sign = 1 },
		{ name = "WallS", cx = 0, cz = -d / 2 - t / 2, sx = w + 2 * t, sz = t, axis = "z", sign = -1 },
		{ name = "WallE", cx = w / 2 + t / 2, cz = 0, sx = t, sz = d, axis = "x", sign = 1 },
		{ name = "WallW", cx = -w / 2 - t / 2, cz = 0, sx = t, sz = d, axis = "x", sign = -1 },
	}
	local o = room.exitOpening
	for _, wall in walls do
		local cutsThis = (room.exitType ~= "roof" and room.exitType ~= "floor_hatch")
			and (
				(wall.axis == "z" and math.abs(o.cz - wall.sign * d / 2) < 1)
				or (wall.axis == "x" and math.abs(o.cx - wall.sign * w / 2) < 1)
			)
		if not cutsThis then
			block(
				model,
				wall.name,
				origin,
				{ cx = wall.cx, cy = h / 2, cz = wall.cz, sx = wall.sx, sy = h, sz = wall.sz },
				pal.background,
				tpl.wallMaterial,
				"Architecture"
			)
		else
			local along = if wall.axis == "z" then o.cx else o.cz
			local len = if wall.axis == "z" then wall.sx else wall.sz
			local half = (if wall.axis == "z" then o.sx else o.sz) / 2
			local lo, hi = along - half, along + half
			local segs = {
				{ a = -len / 2, b = lo, y0 = 0, y1 = h },
				{ a = hi, b = len / 2, y0 = 0, y1 = h },
				{ a = lo, b = hi, y0 = 0, y1 = o.cy - o.sy / 2 },
				{ a = lo, b = hi, y0 = o.cy + o.sy / 2, y1 = h },
			}
			for i, s in segs do
				if s.b - s.a > 0.05 and s.y1 - s.y0 > 0.05 then
					local mid, size = (s.a + s.b) / 2, s.b - s.a
					local box = if wall.axis == "z"
						then { cx = mid, cy = (s.y0 + s.y1) / 2, cz = wall.cz, sx = size, sy = s.y1 - s.y0, sz = t }
						else { cx = wall.cx, cy = (s.y0 + s.y1) / 2, cz = mid, sx = t, sy = s.y1 - s.y0, sz = size }
					block(model, wall.name .. "_" .. i, origin, box, pal.background, tpl.wallMaterial, "Architecture")
				end
			end
		end
	end
	-- ceiling (decorative architecture: excluded from burial probes) with openings left open
	local openings = table.clone(room.ceilingOpenings or {})
	if room.exitType == "roof" then
		table.insert(openings, room.exitOpening)
	end
	if #openings == 0 then
		block(
			model,
			"Ceiling",
			origin,
			{ cx = 0, cy = h + 0.5, cz = 0, sx = w, sy = 1, sz = d },
			pal.structure,
			Enum.Material.SmoothPlastic,
			"Architecture",
			0.2
		)
	else
		-- coarse grid of ceiling tiles skipping openings
		local tile = 4
		for x = -w / 2, w / 2 - tile, tile do
			for z = -d / 2, d / 2 - tile, tile do
				local cx, cz = x + tile / 2, z + tile / 2
				local open = false
				for _, op in openings do
					if math.abs(cx - op.cx) * 2 < op.sx + tile and math.abs(cz - op.cz) * 2 < op.sz + tile then
						open = true
					end
				end
				if not open then
					block(
						model,
						"CeilingTile",
						origin,
						{ cx = cx, cy = h + 0.5, cz = cz, sx = tile, sy = 1, sz = tile },
						pal.structure,
						Enum.Material.SmoothPlastic,
						"Architecture",
						0.2
					)
				end
			end
		end
	end
end

-- Build the room. Returns model + lookup tables used by the services.
function RoomGenerator.build(room: any, cell: CFrame, parent: Instance): (Model, any)
	local tpl = RoomGenerator.template(room.familyId)
	local model = Instance.new("Model")
	model.Name = string.format("Room_%s_d%d", room.templateId, room.depth)
	model:SetAttribute("TemplateId", room.templateId)
	model:SetAttribute("Depth", room.depth)
	model:SetAttribute("Seed", room.seed)
	model:SetAttribute("Fallback", room.fallback == true)
	shell(model, cell, room, tpl)
	local index = {
		supports = {},
		structuralSlots = {},
		optional = {},
		tokens = {},
		mouths = {},
		exitZone = nil :: BasePart?,
		clearance = nil :: BasePart?,
	}

	-- supports: pedestals/shelves are Architecture, props are FillCollider pre-settled & anchored
	for _, n in room.routeGraph.nodes do
		if n.kind == "column" or n.kind == "shelf" then
			for i, part in n.stack do
				if part.kind == "pedestal" or part.kind == "shelf" then
					block(
						model,
						n.id .. "_" .. part.kind,
						cell,
						part.box,
						tpl.palette.structure,
						Enum.Material.SmoothPlastic,
						"Architecture"
					)
				elseif part.propId then
					if n.arrival == "wave1" and i == #n.stack then
						-- structural guest (e.g. Mallow): delivered by WaveDirector at wave 1
						index.structuralSlots[n.id] =
							{ propId = part.propId, cframe = cell * CFrame.new(part.box.cx, part.box.cy, part.box.cz), nodeId = n.id }
					else
						local prop = PropFactory.create(part.propId, tpl)
						prop:PivotTo(cell * CFrame.new(part.box.cx, part.box.cy, part.box.cz))
						local col = prop.PrimaryPart :: BasePart
						col.Anchored = true
						prop:SetAttribute("RouteNode", n.id)
						CollectionService:AddTag(col, "RouteSupport")
						if n.optional then
							prop:SetAttribute("Optional", true)
							table.insert(index.optional, { model = prop, node = n })
						end
						prop.Parent = model
						table.insert(index.supports, { model = prop, node = n })
					end
				end
			end
		elseif n.kind == "exit_ledge" and n.topY > 0 then
			local p = block(model, n.id, cell, n.box, tpl.palette.structure, Enum.Material.SmoothPlastic, "Architecture")
			-- mint arch + vertical chevron on the opening (colour + shape + motion)
			p:SetAttribute("ExitLedge", true)
		end
	end

	-- exit clearance (protected volume, not collidable) and exit trigger
	local c = room.exitClearance
	local clr = block(model, "ExitClearance", cell, c, Color3.fromHex("#39E68B"), Enum.Material.ForceField, "ExitClearance", 0.92)
	clr.CanCollide = false
	clr.CanQuery = true
	clr.CanTouch = false
	index.clearance = clr
	local o = room.exitOpening
	local trig = block(
		model,
		"ExitTrigger",
		cell,
		{ cx = o.cx, cy = o.cy, cz = o.cz, sx = math.max(o.sx, 2), sy = math.max(o.sy, 2), sz = math.max(o.sz, 2) },
		Color3.fromHex("#39E68B"),
		Enum.Material.Neon,
		"ExitTrigger",
		0.6
	)
	trig.CanCollide = false
	trig.CanQuery = false
	trig.CanTouch = false
	index.exitZone = trig
	if room.leverId then
		for _, n in room.routeGraph.nodes do
			if n.id == room.leverId then
				local lever = block(
					model,
					"Lever",
					cell,
					{ cx = n.box.cx, cy = n.topY + 1.5, cz = n.box.cz, sx = 1, sy = 3, sz = 1 },
					Color3.fromHex("#FFE14D"),
					Enum.Material.SmoothPlastic,
					"Lever"
				)
				lever.CanCollide = false
				index.lever = lever
			end
		end
	end

	-- wave mouths (ceiling chutes, decor) with coral danger triangles drawn by the client
	for i, m in room.waveMouths do
		local mouth = block(
			model,
			"Mouth" .. i,
			cell,
			{ cx = m.cx, cy = room.size.h - 0.25, cz = m.cz, sx = m.sx, sy = 0.5, sz = m.sz },
			Color3.fromHex("#FF684B"),
			Enum.Material.SmoothPlastic,
			"DecorOnly",
			0.3
		)
		mouth.CanCollide = false
		mouth.CanQuery = false
		index.mouths[i] = mouth
	end

	-- optional tokens (violet star, bonus only)
	for _, tk in room.tokens do
		local p = Instance.new("Part")
		p.Name = "Token" .. tk.id
		p.Shape = Enum.PartType.Ball
		p.Size = Vector3.new(1.4, 1.4, 1.4)
		p.Color = Color3.fromHex("#8855FF")
		p.Material = Enum.Material.Neon
		p.Anchored = true
		p.CanCollide = false
		p.CanQuery = false
		p.CFrame = cell * CFrame.new(tk.x, tk.y, tk.z)
		p:SetAttribute("TokenIndex", tk.id)
		CollectionService:AddTag(p, "OptionalToken")
		p.Parent = model
		index.tokens[tk.id] = p
	end

	model:SetAttribute("Cell", tostring(cell.Position))
	model.Parent = parent
	return model, index
end

-- Plan + validate + build for a depth. Diagnostics of rejected attempts are returned.
function RoomGenerator.plan(depth: number, runSeed: number, history: { any }, profileName: string?)
	local spec = RoomPlan.selectSpec(depth, runSeed, history, profileName)
	local seed = bit32.bxor(runSeed, depth * 2654435761 % 4294967296)
	local room, diags = RoomPlan.build(spec, depth, seed)
	return room, spec, diags
end

return RoomGenerator
