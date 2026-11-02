--!strict
-- reception_carton — Carton standard (stable). Générateur paramétrique T03 (primitives Roblox).
-- Brief : carton jaune, ruban cyan, coins arrondis, plateau supérieur plat. Taille : config/rooms.json.
local ID = "reception_carton"
local CARTON = "#F2C94C"
local CARTON_EDGE = "#E0B43C"
local TAPE = "#16D9FF"

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

local function readSize(params: any): (number, number, number)
	assert(type(params) == "table" and type(params.size) == "table", ID .. " : params.size (config/rooms.json) requis")
	local w, d, h = params.size[1], params.size[2], params.size[3]
	assert(type(w) == "number" and w > 0 and type(d) == "number" and d > 0 and type(h) == "number" and h > 0, ID .. " : size invalide")
	return w, d, h
end

return {
	id = ID,
	build = function(params: any)
		local w, d, h = readSize(params)
		local r = math.min(0.35, w * 0.05, d * 0.05) -- rayon des arêtes verticales arrondies
		local parts = {
			-- corps en croix (deux blocs) + 4 cylindres d'arête = coins arrondis, dessus plat à h
			part("BodyX", { w, h, d - 2 * r }, { 0, h / 2, 0 }, CARTON, "Cardboard", false, { "DecorOnly" }),
			part("BodyZ", { w - 2 * r, h, d }, { 0, h / 2, 0 }, CARTON, "Cardboard", false, { "DecorOnly" }),
		}
		for _, sx in { -1, 1 } do
			for _, sz in { -1, 1 } do
				table.insert(
					parts,
					part(
						"Edge",
						{ h, 2 * r, 2 * r },
						{ sx * (w / 2 - r), h / 2, sz * (d / 2 - r) },
						CARTON_EDGE,
						"Cardboard",
						false,
						{ "DecorOnly" },
						"Cylinder"
					)
				)
			end
		end
		-- ruban cyan affleurant (épaisseur 0.04 : écart visuel/collision << 0.25 stud)
		table.insert(parts, part("TapeTop", { w, 0.04, 1.2 }, { 0, h + 0.02, 0 }, TAPE, "SmoothPlastic", false, { "DecorOnly" }))
		table.insert(parts, part("TapeFront", { 1.2, h, 0.04 }, { 0, h / 2, -d / 2 - 0.02 }, TAPE, "SmoothPlastic", false, { "DecorOnly" }))
		table.insert(parts, part("TapeBack", { 1.2, h, 0.04 }, { 0, h / 2, d / 2 + 0.02 }, TAPE, "SmoothPlastic", false, { "DecorOnly" }))
		return {
			id = ID,
			parts = parts,
			-- les cylindres d'arête ont l'axe X dans Roblox : rotation à appliquer par l'instanciateur
			edgeCylinderRotationDeg = { 0, 0, 90 },
			collider = { shape = "box", size = { w, h, d }, offset = { 0, h / 2, 0 }, tags = { "FillCollider" }, canCollide = true },
			walkableTop = { size = { w, d }, height = h, center = { 0, h, 0 }, marker = "stable" },
		}
	end,
}
