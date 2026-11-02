-- Contrôle hors Roblox des générateurs T03 (Lune). Tailles lues dans config/rooms.json et
-- assets/manifest.json : aucune dimension codée ici.
-- Usage (depuis filling_up/) : .toolchain/bin/lune run assets/source/generators/_check_generators.luau
local fs = require("@lune/fs")
local serde = require("@lune/serde")

local rooms = serde.decode("json", fs.readFile("config/rooms.json"))
local manifest = serde.decode("json", fs.readFile("assets/manifest.json"))
local byId = {}
for _, a in manifest.assets do
	byId[a.id] = a
end
local exitClear = {}
for _, e in rooms.exit_types do
	exitClear[e.id] = e.approach_clearance_studs
end
local machineSize
for _, f in rooms.families do
	if f.machine and f.machine.id == "machine_reception_stamp" then
		machineSize = f.machine.size_studs
	end
end

local failures, passes = 0, 0
local function check(cond: boolean, msg: string)
	if cond then
		passes += 1
	else
		failures += 1
		print("FAIL " .. msg)
	end
end

local function validParts(id, desc)
	check(desc.id == id, id .. " : id")
	check(type(desc.parts) == "table" and #desc.parts > 0, id .. " : parts")
	for _, p in desc.parts do
		check(#p.size == 3 and p.size[1] > 0 and p.size[2] > 0 and p.size[3] > 0, id .. "/" .. p.name .. " : size > 0")
		check(type(p.color) == "string" and string.match(p.color, "^#%x%x%x%x%x%x$") ~= nil, id .. "/" .. p.name .. " : couleur hex")
		check(type(p.tags) == "table" and #p.tags > 0, id .. "/" .. p.name .. " : tags")
		for _, t in p.tags do
			if t == "DecorOnly" then
				check(p.canCollide == false, id .. "/" .. p.name .. " : DecorOnly sans collision")
			end
		end
	end
end

local props = { "reception_carton", "reception_foam_crate", "reception_pallet", "reception_suitcase" }
for _, id in props do
	local gen = require("./" .. id)
	local a = byId[id]
	local desc = gen.build({ size = a.size_studs })
	validParts(id, desc)
	local w, d, h = a.size_studs[1], a.size_studs[2], a.size_studs[3]
	local c = desc.collider
	check(
		c.size[1] == a.collision.size_studs[1] and c.size[2] == a.collision.size_studs[3] and c.size[3] == a.collision.size_studs[2],
		id .. " : collider = manifest.collision (Vector3 l,h,p)"
	)
	check(c.tags[1] == "FillCollider", id .. " : collider FillCollider")
	check(
		desc.walkableTop.size[1] == a.collision.walkable_top[1] and desc.walkableTop.size[2] == a.collision.walkable_top[2],
		id .. " : walkable_top"
	)
	check(desc.walkableTop.height == h, id .. " : dessus utile à la hauteur du collider")
	-- dessus visible : la pièce visuelle la plus haute dans l'empreinte ne dépasse pas h de plus de 0.25
	local topVisible = 0
	for _, p in desc.parts do
		if math.abs(p.offset[1]) < w / 2 and math.abs(p.offset[3]) < d / 2 then
			topVisible = math.max(topVisible, p.offset[2] + p.size[2] / 2)
		end
	end
	check(math.abs(topVisible - h) <= 0.25, id .. string.format(" : écart dessus visible/collision %.3f <= 0.25", topVisible - h))
	local ok = pcall(gen.build, {})
	check(not ok, id .. " : refuse l'absence de taille de config")
end

for _, ex in { "door", "window", "roof" } do
	local id = "exit_" .. ex
	local gen = require("./" .. id)
	local desc = gen.build({ clearance = exitClear[ex] })
	validParts(id, desc)
	check(desc.exitType == ex, id .. " : exitType")
	local found = false
	for _, v in desc.volumes do
		if v.name == "ExitClearance" then
			found = true
			check(v.size[1] >= 8 and v.size[2] >= 10 and v.size[3] >= 8, id .. " : volume protégé >= 8x8x10")
			check(v.canCollide == false, id .. " : volume protégé non solide")
		end
	end
	check(found, id .. " : ExitClearance présent")
	check(desc.opening.width >= 6, id .. " : ouverture franchissable (>= 6 studs)")
	local hasMarker = false
	for _, p in desc.parts do
		for _, t in p.tags do
			if t == "ExitMarker" then
				hasMarker = true
			end
		end
	end
	check(hasMarker, id .. " : balise menthe")
	local ok = pcall(gen.build, { clearance = { 6, 6, 8 } })
	check(not ok, id .. " : refuse un dégagement < 8x8x10")
end

do
	local gen = require("./machine_reception_stamp")
	local desc = gen.build({ size = machineSize })
	validParts("machine_reception_stamp", desc)
	check(desc.isPrototypeProxy == true, "machine : marquée proxy de prototype")
	check(
		desc.collider.tags[1] == "Architecture" and desc.collider.walkable == false,
		"machine : collision d'architecture séparée, non jouable"
	)
end

print(string.format("generators check: %d PASS, %d FAIL", passes, failures))
if failures > 0 then
	error("échecs")
end
