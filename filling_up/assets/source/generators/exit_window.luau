--!strict
-- exit_window — Sortie « Fenêtre » (MVP). Générateur paramétrique T03.
-- Repère : origine = centre de l'appui (rebord) visible, dans le plan du mur ; la salle est côté -Z.
-- Franchissement : step_through_visible_sill. Le rebord dépasse dans la salle et sert de dernier appui protégé.
local ID = "exit_window"
local FRAME = "#203055"
local SILL = "#FFF5DF"
local MINT = "#39E68B"
local GLASS = "#DFF7FF"
local WALL_T = 1

local function part(
	name: string,
	size: { number },
	offset: { number },
	color: string,
	material: string,
	canCollide: boolean,
	tags: { string },
	shape: string?
)
	return {
		name = name,
		size = size,
		offset = offset,
		color = color,
		material = material,
		materialFallback = "SmoothPlastic",
		canCollide = canCollide,
		tags = tags,
		shape = shape or "Block",
	}
end

local function readClearance(params: any): (number, number, number)
	assert(type(params) == "table" and type(params.clearance) == "table", ID .. " : params.clearance (config/rooms.json exit_types) requis")
	local w, d, h = params.clearance[1], params.clearance[2], params.clearance[3]
	assert(
		type(w) == "number" and w >= 8 and type(d) == "number" and d >= 8 and type(h) == "number" and h >= 10,
		ID .. " : dégagement minimal 8x8x10"
	)
	return w, d, h
end

return {
	id = ID,
	build = function(params: any)
		local cw, cd, ch = readClearance(params)
		local ow, oh = cw - 2, ch - 2
		local sillDepth = 2.5
		local parts = {
			part("FrameL", { 1, oh + 1, WALL_T }, { -ow / 2 - 0.5, (oh + 1) / 2, 0 }, FRAME, "SmoothPlastic", true, { "Architecture" }),
			part("FrameR", { 1, oh + 1, WALL_T }, { ow / 2 + 0.5, (oh + 1) / 2, 0 }, FRAME, "SmoothPlastic", true, { "Architecture" }),
			part("FrameTop", { ow + 2, 1, WALL_T }, { 0, oh + 0.5, 0 }, FRAME, "SmoothPlastic", true, { "Architecture" }),
			-- rebord large, crème, plat : réception visible (balise stable posée par le jeu)
			part(
				"Sill",
				{ ow + 2, 0.5, WALL_T + sillDepth },
				{ 0, -0.25, -sillDepth / 2 },
				SILL,
				"SmoothPlastic",
				true,
				{ "Architecture" }
			),
			-- vitre ouverte : battant relevé, sans collision dans l'ouverture
			part("OpenSash", { ow, 0.2, 2 }, { 0, oh - 0.1, 1.2 }, GLASS, "Glass", false, { "DecorOnly" }),
			part("MintSillEdge", { ow + 2, 0.12, 0.3 }, { 0, 0.06, -sillDepth - 0.05 }, MINT, "Neon", false, { "DecorOnly", "ExitMarker" }),
			part(
				"MintArchTop",
				{ ow + 0.6, 0.3, 0.2 },
				{ 0, oh + 0.15, -WALL_T / 2 - 0.1 },
				MINT,
				"Neon",
				false,
				{ "DecorOnly", "ExitMarker" }
			),
			part(
				"ChevronL",
				{ 0.35, 1.4, 0.2 },
				{ -0.45, oh + 1.6, -WALL_T / 2 - 0.1 },
				MINT,
				"Neon",
				false,
				{ "DecorOnly", "ExitMarker" }
			),
			part("ChevronR", { 0.35, 1.4, 0.2 }, { 0.45, oh + 1.6, -WALL_T / 2 - 0.1 }, MINT, "Neon", false, { "DecorOnly", "ExitMarker" }),
		}
		return {
			id = ID,
			exitType = "window",
			parts = parts,
			chevronRotationDeg = { ChevronL = { 0, 0, -35 }, ChevronR = { 0, 0, 35 } },
			opening = { width = ow, height = oh },
			walkableTop = {
				size = { ow + 2, sillDepth + WALL_T },
				height = 0,
				center = { 0, 0, -sillDepth / 2 },
				marker = "stable",
				protected = true,
			},
			volumes = {
				{
					name = "ExitClearance",
					size = { cw, ch, cd },
					offset = { 0, ch / 2, -WALL_T / 2 - cd / 2 },
					tags = { "ExitClearance" },
					canCollide = false,
				},
				{
					name = "ExitTrigger",
					size = { ow, oh, WALL_T + 2 },
					offset = { 0, oh / 2, 1 },
					tags = { "ExitTrigger" },
					canCollide = false,
				},
			},
		}
	end,
}
