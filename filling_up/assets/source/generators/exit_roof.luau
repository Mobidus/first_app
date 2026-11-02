--!strict
-- exit_roof — Sortie « Toit » (MVP). Générateur paramétrique T03.
-- Repère : origine = centre de la trappe, dans le plan du plafond (y = 0) ; la salle est sous la trappe (y < 0).
-- Franchissement : reach_platform_then_step_through_hatch. camera_headroom_required : puits dégagé au-dessus.
local ID = "exit_roof"
local FRAME = "#203055"
local MINT = "#39E68B"
local DECK = "#FFF5DF"

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
		local ow, od = cw - 2, cd - 2 -- trappe 6 x 6
		local t = 1
		local parts = {
			-- cadre de trappe (collision) dans le plafond
			part("RimL", { 1, t, od + 2 }, { -ow / 2 - 0.5, t / 2, 0 }, FRAME, "SmoothPlastic", true, { "Architecture" }),
			part("RimR", { 1, t, od + 2 }, { ow / 2 + 0.5, t / 2, 0 }, FRAME, "SmoothPlastic", true, { "Architecture" }),
			part("RimF", { ow, t, 1 }, { 0, t / 2, -od / 2 - 0.5 }, FRAME, "SmoothPlastic", true, { "Architecture" }),
			part("RimB", { ow, t, 1 }, { 0, t / 2, od / 2 + 0.5 }, FRAME, "SmoothPlastic", true, { "Architecture" }),
			-- pont de sortie au-dessus : on prend pied à côté de la trappe
			part(
				"RoofDeck",
				{ cw + 4, 0.5, cd + 4 },
				{ 0, t + 0.25, cd / 2 + 2 + od / 2 },
				DECK,
				"SmoothPlastic",
				true,
				{ "Architecture" }
			),
			-- balisage : anneau menthe autour de la trappe + chevron vertical pointant vers le haut
			part("MintRingF", { ow + 0.6, 0.2, 0.3 }, { 0, -0.1, -od / 2 - 0.15 }, MINT, "Neon", false, { "DecorOnly", "ExitMarker" }),
			part("MintRingB", { ow + 0.6, 0.2, 0.3 }, { 0, -0.1, od / 2 + 0.15 }, MINT, "Neon", false, { "DecorOnly", "ExitMarker" }),
			part("MintRingL", { 0.3, 0.2, od }, { -ow / 2 - 0.15, -0.1, 0 }, MINT, "Neon", false, { "DecorOnly", "ExitMarker" }),
			part("MintRingR", { 0.3, 0.2, od }, { ow / 2 + 0.15, -0.1, 0 }, MINT, "Neon", false, { "DecorOnly", "ExitMarker" }),
		}
		return {
			id = ID,
			exitType = "roof",
			parts = parts,
			opening = { width = ow, depth = od },
			volumes = {
				-- dégagement sous la trappe (approche par le dernier appui)
				{
					name = "ExitClearance",
					size = { cw, ch, cd },
					offset = { 0, -ch / 2, 0 },
					tags = { "ExitClearance" },
					canCollide = false,
				},
				-- espace de tête et de caméra au-dessus de la trappe
				{ name = "CameraHeadroom", size = { ow, 8, od }, offset = { 0, t + 4, 0 }, tags = { "ExitClearance" }, canCollide = false },
				{ name = "ExitTrigger", size = { ow, 3, od }, offset = { 0, t + 1.5, 0 }, tags = { "ExitTrigger" }, canCollide = false },
			},
		}
	end,
}
