--!nocheck
-- Validated very large rooms (XL / XV) for review renders (decision 0017).
local fs = require("@lune/fs")
local serde = require("@lune/serde")
local Loader = require("../tests/_harness/Loader")
local Plan = Loader.require("src/shared/Domain/RoomPlan")
local out = { runSeed = 1702, rooms = {} }
local list = {
	{ "reception", "XL", "window", 2 }, { "toy", "XL", "roof", 4 }, { "reception", "XV", "window", 6 }, { "bureau", "XL", "door", 9 },
	{ "toy", "XV", "window", 10 }, { "bureau", "XV", "roof", 35 }, { "garage", "XL", "tailgate", 40 }, { "bin", "XV", "roof", 90 },
}
for i, c in list do
	local spec = { family = c[1], format = c[2], exit = c[3], allowedBehaviors = { "stable", "bounce", "moving", "temporary" } }
	local room = Plan.build(spec, c[4], 1702 + i * 97)
	table.insert(out.rooms, { depth = c[4], profile = "xl", room = room })
end
fs.writeFile("reports/room_previews/rooms.json", serde.encode("json", out))
print(#out.rooms .. " XL/XV rooms dumped")
