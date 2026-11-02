--!strict
-- reception_pallet — Palette turquoise (stable, palier de repos). Générateur paramétrique T03.
-- Brief : palette plastique turquoise, plateau FERMÉ sans fentes piégeuses.
local ID = "reception_pallet"
local DECK = "#2ACBC7"
local RUNNER = "#1FA7A4"

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
		local deckT = h * 0.4
		local runnerH = h - deckT
		local parts = {
			part("Deck", { w, deckT, d }, { 0, h - deckT / 2, 0 }, DECK, "Plastic", false, { "DecorOnly" }),
		}
		-- trois patins sous le plateau ; leurs côtés sont visuellement fermés par des plinthes
		for i, x in { -w / 2 + 0.8, 0, w / 2 - 0.8 } do
			table.insert(parts, part("Runner" .. i, { 1.6, runnerH, d }, { x, runnerH / 2, 0 }, RUNNER, "Plastic", false, { "DecorOnly" }))
		end
		table.insert(
			parts,
			part("SkirtFront", { w, runnerH, 0.2 }, { 0, runnerH / 2, -d / 2 + 0.1 }, RUNNER, "Plastic", false, { "DecorOnly" })
		)
		table.insert(
			parts,
			part("SkirtBack", { w, runnerH, 0.2 }, { 0, runnerH / 2, d / 2 - 0.1 }, RUNNER, "Plastic", false, { "DecorOnly" })
		)
		return {
			id = ID,
			parts = parts,
			-- collision pleine : pas de fente où un pied pourrait se coincer
			collider = { shape = "box", size = { w, h, d }, offset = { 0, h / 2, 0 }, tags = { "FillCollider" }, canCollide = true },
			walkableTop = { size = { w, d }, height = h, center = { 0, h, 0 }, marker = "stable" },
		}
	end,
}
