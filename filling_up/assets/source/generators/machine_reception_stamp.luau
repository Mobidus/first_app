--!strict
-- machine_reception_stamp — « Le Tamponneur », machine signature de Réception. Générateur T03 (PROXY).
-- Le manifeste prévoit un mesh Blender (3 000 à 8 000 triangles) : cette version primitives est un
-- proxy de prototype clairement identifié ; elle ne clôt pas la livraison artistique.
-- Brief : presse corail à deux yeux mécaniques, pied arrondi, gros tampon jaune ; chaîne cyan derrière une vitre.
-- Collision : proxy d'architecture séparé (hors parcours, non sondé par l'ensevelissement).
local ID = "machine_reception_stamp"
local CORAL = "#FF8C78" -- corail doux (le corail danger #FF684B est réservé aux balises de danger)
local YELLOW = "#FFE14D"
local CYAN = "#16D9FF"
local NAVY = "#203055"
local WHITE = "#FFF5DF"
local GLASS = "#DFF7FF"

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
	assert(type(params) == "table" and type(params.size) == "table", ID .. " : params.size (config/rooms.json machine.size_studs) requis")
	local w, d, h = params.size[1], params.size[2], params.size[3]
	assert(type(w) == "number" and w > 0 and type(d) == "number" and d > 0 and type(h) == "number" and h > 0, ID .. " : size invalide")
	return w, d, h
end

return {
	id = ID,
	isPrototypeProxy = true,
	build = function(params: any)
		local w, d, h = readSize(params)
		local footH = h * 0.12
		local bodyH = h * 0.45
		local bodyY = footH + bodyH / 2
		local parts = {
			part("Foot", { footH, w * 0.7, w * 0.7 }, { 0, footH / 2, 0 }, CORAL, "SmoothPlastic", false, { "DecorOnly" }, "Cylinder"),
			part("Body", { w * 0.8, bodyH, d * 0.7 }, { 0, bodyY, 0 }, CORAL, "SmoothPlastic", false, { "DecorOnly" }),
			part(
				"EyeL",
				{ 2.4, 2.4, 2.4 },
				{ -w * 0.18, bodyY + bodyH * 0.2, -d * 0.35 },
				WHITE,
				"SmoothPlastic",
				false,
				{ "DecorOnly" },
				"Ball"
			),
			part(
				"EyeR",
				{ 2.4, 2.4, 2.4 },
				{ w * 0.18, bodyY + bodyH * 0.2, -d * 0.35 },
				WHITE,
				"SmoothPlastic",
				false,
				{ "DecorOnly" },
				"Ball"
			),
			part(
				"PupilL",
				{ 1.0, 1.0, 1.0 },
				{ -w * 0.18, bodyY + bodyH * 0.2, -d * 0.35 - 1.0 },
				NAVY,
				"SmoothPlastic",
				false,
				{ "DecorOnly" },
				"Ball"
			),
			part(
				"PupilR",
				{ 1.0, 1.0, 1.0 },
				{ w * 0.18, bodyY + bodyH * 0.2, -d * 0.35 - 1.0 },
				NAVY,
				"SmoothPlastic",
				false,
				{ "DecorOnly" },
				"Ball"
			),
			-- bras de presse et gros tampon jaune au-dessus
			part("Arm", { w * 0.15, h * 0.2, d * 0.15 }, { 0, footH + bodyH + h * 0.1, 0 }, NAVY, "Metal", false, { "DecorOnly" }),
			part(
				"Stamp",
				{ h * 0.12, w * 0.45, w * 0.45 },
				{ 0, h - h * 0.06 - h * 0.1, 0 },
				YELLOW,
				"SmoothPlastic",
				false,
				{ "DecorOnly" },
				"Cylinder"
			),
			part("StampPad", { w * 0.5, h * 0.05, d * 0.5 }, { 0, h - h * 0.025, 0 }, NAVY, "Fabric", false, { "DecorOnly" }),
			-- vitre arrière et chaîne cyan visible derrière
			part("Glass", { w * 0.8, h * 0.5, 0.2 }, { 0, footH + h * 0.25, d * 0.42 }, GLASS, "Glass", false, { "DecorOnly" }),
		}
		parts[#parts].transparency = 0.6
		for i = 0, 5 do
			table.insert(
				parts,
				part(
					"ChainLink" .. i,
					{ 0.8, 1.2, 0.3 },
					{ -w * 0.3 + i * w * 0.12, footH + h * 0.3, d * 0.46 },
					CYAN,
					"SmoothPlastic",
					false,
					{ "DecorOnly" }
				)
			)
		end
		return {
			id = ID,
			isPrototypeProxy = true,
			parts = parts,
			stampRotationDeg = { 0, 0, 90 },
			collider = {
				shape = "box",
				size = { w, h, d },
				offset = { 0, h / 2, 0 },
				tags = { "Architecture" },
				canCollide = true,
				walkable = false,
			},
		}
	end,
}
