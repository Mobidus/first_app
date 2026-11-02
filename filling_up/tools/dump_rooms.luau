--!nocheck
-- Dumps validated RoomDefinitions (first ten rooms of an expedition + deep samples) to JSON for
-- visual review renders (tools/render_rooms.py). Same planner as the game (RoomGenerator.plan).
local fs = require("@lune/fs")
local serde = require("@lune/serde")
local Loader = require("../tests/_harness/Loader")
local Plan = Loader.require("src/shared/Domain/RoomPlan")

local RUN_SEED = 20261102
local out = { runSeed = RUN_SEED, rooms = {} }
local history = {}
local function add(depth, profile)
	local spec = Plan.selectSpec(depth, RUN_SEED, history, profile)
	table.insert(history, spec)
	local seed = bit32.bxor(RUN_SEED, depth * 2654435761 % 4294967296)
	local room = Plan.build(spec, depth, seed)
	table.insert(out.rooms, { depth = depth, profile = profile, room = room })
end
for d = 1, 10 do
	add(d, "mvp")
end
for _, d in { 25, 60, 150 } do
	add(d, "mvp")
end
for _, d in { 30, 90 } do
	add(d, "v1")
end
local tut = Plan.tutorialCell()
table.insert(out.rooms, 1, { depth = 0, profile = "tutorial", room = tut })
fs.writeFile("reports/room_previews/rooms.json", serde.encode("json", out))
print(#out.rooms .. " rooms dumped")
