--!strict
-- exit_door — Sortie « Porte » (MVP). Générateur paramétrique T03.
-- Repère : origine = centre bas de l'ouverture, dans le plan du mur ; la salle est du côté -Z (avant).
-- Collision : périmètre seulement, centre ouvert. Balise : arche menthe + chevron vertical (forme + couleur).
-- Volume protégé : params.clearance = approach_clearance_studs de config/rooms.json (largeur, profondeur, hauteur).
local ID = "exit_door"
local FRAME = "#203055"
local MINT = "#39E68B"
local WALL_T = 1 -- épaisseur de mur du kit (géométrie d'architecture, pas une règle de jeu)

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
		local ow, oh = cw - 2, ch - 2 -- ouverture franchissable 6 x 8 pour un dégagement 8 x 10
		local parts = {
			part("JambL", { 1, oh + 1, WALL_T }, { -ow / 2 - 0.5, (oh + 1) / 2, 0 }, FRAME, "SmoothPlastic", true, { "Architecture" }),
			part("JambR", { 1, oh + 1, WALL_T }, { ow / 2 + 0.5, (oh + 1) / 2, 0 }, FRAME, "SmoothPlastic", true, { "Architecture" }),
			part("Lintel", { ow + 2, 1, WALL_T }, { 0, oh + 0.5, 0 }, FRAME, "SmoothPlastic", true, { "Architecture" }),
			-- seuil affleurant (sol de passage)
			part("Threshold", { ow, 0.2, WALL_T + 2 }, { 0, 0.1, 1 }, FRAME, "SmoothPlastic", true, { "Architecture" }),
			-- balisage : arche menthe (lumineuse) + chevron vertical au-dessus
			part(
				"MintArchL",
				{ 0.3, oh, 0.2 },
				{ -ow / 2 - 0.15, oh / 2, -WALL_T / 2 - 0.1 },
				MINT,
				"Neon",
				false,
				{ "DecorOnly", "ExitMarker" }
			),
			part(
				"MintArchR",
				{ 0.3, oh, 0.2 },
				{ ow / 2 + 0.15, oh / 2, -WALL_T / 2 - 0.1 },
				MINT,
				"Neon",
				false,
				{ "DecorOnly", "ExitMarker" }
			),
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
			exitType = "door",
			parts = parts,
			chevronRotationDeg = { ChevronL = { 0, 0, -35 }, ChevronR = { 0, 0, 35 } },
			opening = { width = ow, height = oh },
			volumes = {
				-- approche protégée côté salle : aucun spawn, trajectoire de chute ni décor solide
				{
					name = "ExitClearance",
					size = { cw, ch, cd },
					offset = { 0, ch / 2, -WALL_T / 2 - cd / 2 },
					tags = { "ExitClearance" },
					canCollide = false,
				},
				-- déclencheur de sortie dans l'épaisseur du passage (validé côté serveur)
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
