--!strict
-- reception_suitcase — Valise orange couchée (stable). Générateur paramétrique T03.
-- NOTE : le manifeste prévoit un mesh Blender (production_method = blender_mesh_and_optional_rig) ;
-- ce générateur fournit une version primitives jouable et fidèle au gabarit, en attendant ce mesh.
-- Brief : valise couchée orange à nervures peu profondes ; poignée et roues SANS collision.
local ID = "reception_suitcase"
local SHELL = "#FF8A3D"
local RIB = "#E8732B"
local TRIM = "#203055"

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
		local parts = {
			part("Shell", { w, h, d }, { 0, h / 2, 0 }, SHELL, "SmoothPlastic", false, { "DecorOnly" }),
			-- jonction des deux coques, à mi-hauteur
			part("Seam", { w + 0.04, 0.18, d + 0.04 }, { 0, h / 2, 0 }, TRIM, "SmoothPlastic", false, { "DecorOnly" }),
		}
		-- nervures peu profondes sur le dessus (0.05 stud : dessus visible ≈ collision)
		for i = 1, 4 do
			local x = -w / 2 + i * w / 5
			table.insert(
				parts,
				part("Rib" .. i, { 0.35, 0.05, d - 0.6 }, { x, h + 0.025, 0 }, RIB, "SmoothPlastic", false, { "DecorOnly" })
			)
		end
		-- poignée (face avant -Z) et roues (côté droit), décoratives et hors collision
		table.insert(
			parts,
			part("Handle", { w * 0.3, 0.35, 0.5 }, { 0, h * 0.55, -d / 2 - 0.25 }, TRIM, "SmoothPlastic", false, { "DecorOnly" })
		)
		for _, z in { -d / 2 + 0.8, d / 2 - 0.8 } do
			table.insert(
				parts,
				part("Wheel", { 0.4, 0.9, 0.9 }, { w / 2 + 0.2, 0.45, z }, TRIM, "Rubber", false, { "DecorOnly" }, "Cylinder")
			)
		end
		return {
			id = ID,
			parts = parts,
			collider = { shape = "box", size = { w, h, d }, offset = { 0, h / 2, 0 }, tags = { "FillCollider" }, canCollide = true },
			walkableTop = { size = { w, d }, height = h, center = { 0, h, 0 }, marker = "stable" },
			-- une valise posée ne roule jamais : ancrage après stabilisation (rooms.json behavior_defaults.stable)
			anchorAfterSettle = true,
		}
	end,
}
