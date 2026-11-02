--!strict
-- reception_foam_crate — Caisse mousse (stable, large réception). Générateur paramétrique T03.
-- Brief : caisse orange souple, poignée creuse purement décorative, dessus large.
local ID = "reception_foam_crate"
local FOAM = "#FF9B47"
local FOAM_DARK = "#E9803A"
local HANDLE = "#203055"

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
		local band = math.min(0.5, h * 0.15)
		local parts = {
			part("Body", { w, h - 2 * band, d }, { 0, h / 2, 0 }, FOAM, "Fabric", false, { "DecorOnly" }),
			-- bourrelets haut et bas légèrement rentrés (aspect mousse), dessus plat à h
			part("RimTop", { w - 0.2, band, d - 0.2 }, { 0, h - band / 2, 0 }, FOAM_DARK, "Fabric", false, { "DecorOnly" }),
			part("RimBottom", { w - 0.2, band, d - 0.2 }, { 0, band / 2, 0 }, FOAM_DARK, "Fabric", false, { "DecorOnly" }),
			-- poignées creuses (visuel seulement, aucune prise de collision)
			part(
				"HandleFront",
				{ w * 0.35, h * 0.18, 0.06 },
				{ 0, h * 0.62, -d / 2 - 0.03 },
				HANDLE,
				"SmoothPlastic",
				false,
				{ "DecorOnly" }
			),
			part(
				"HandleBack",
				{ w * 0.35, h * 0.18, 0.06 },
				{ 0, h * 0.62, d / 2 + 0.03 },
				HANDLE,
				"SmoothPlastic",
				false,
				{ "DecorOnly" }
			),
		}
		return {
			id = ID,
			parts = parts,
			collider = { shape = "box", size = { w, h, d }, offset = { 0, h / 2, 0 }, tags = { "FillCollider" }, canCollide = true },
			walkableTop = { size = { w, d }, height = h, center = { 0, h, 0 }, marker = "stable" },
		}
	end,
}
