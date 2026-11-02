--!nocheck
-- Set dressing (decision 0018): furniture fills very large rooms without touching the gameplay.
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Plan = Loader.require("src/shared/Domain/RoomPlan")
local Dressing = Loader.require("src/shared/Domain/SetDressing")
local V = Loader.require("src/shared/Domain/RouteValidator")
local Box = Loader.require("src/shared/Util/Box")
local Config = Loader.require("src/shared/GeneratedConfig")

local function strip(room)
	local c = table.clone(room)
	c.decor = nil
	return c
end

describe("SetDressing", function()
	it("every family has a catalog and every format/exit of a sample is dressed and passes the independent check", function()
		local rejected, total, furniture = 0, 0, 0
		for _, fam in Config.Rooms.families do
			expect(Dressing.CATALOG[fam.id] ~= nil).toBe(true)
			for _, format in Config.Rooms.release_profiles.v1.formats do
				for i, exit in fam.exits do
					for seed = 1, 3 do
						local room, diags = Plan.build(
							{ family = fam.id, format = format, exit = exit, allowedBehaviors = { "stable" } },
							20 + i,
							seed * 31 + i
						)
						total += 1
						for _, dg in diags do
							if string.find(dg, "decor_rejected", 1, true) then
								rejected += 1
							end
						end
						local ok, errs = V.validateDecor(room, Dressing.BLOCK_BUDGET)
						if not ok then
							print(room.templateId, table.concat(errs, ","))
						end
						expect(ok).toBe(true)
						expect(Dressing.blockCount(room.decor) + #room.waveMouths).toBeAtMost(
							Config.Rooms.validation_rules.maximum_decorative_blocks_active_room
						)
						for _, item in room.decor do
							if item.kind == "furniture" then
								furniture += 1
							end
						end
					end
				end
			end
		end
		expect(rejected).toBe(0)
		expect(furniture > total).toBe(true)
	end)

	it("very large rooms get more furniture than small ones", function()
		local function count(format)
			local n = 0
			for seed = 1, 8 do
				local room = Plan.build({ family = "bureau", format = format, exit = "door", allowedBehaviors = { "stable" } }, 12, seed)
				for _, item in room.decor do
					if item.kind == "furniture" or item.kind == "wall" then
						n += 1
					end
				end
			end
			return n / 8
		end
		local s, xl = count("S"), count("XL")
		expect(xl > s * 1.5).toBe(true)
		expect(xl).toBeAtLeast(6)
	end)

	it("dressing never changes the validated layout and is deterministic", function()
		local spec = { family = "toy", format = "XL", exit = "roof", allowedBehaviors = { "stable", "bounce" } }
		local a = Plan.build(spec, 4, 99)
		local b = Plan.build(spec, 4, 99)
		expect(Spec.deepEqual(a.decor, b.decor)).toBe(true)
		local ok = V.validate(strip(a), { gapRatio = a.gapRatio })
		expect(ok).toBe(true)
		-- re-dressing the stripped room gives exactly the same decor (own random stream)
		expect(Spec.deepEqual(Dressing.dress(strip(a)), a.decor)).toBe(true)
	end)

	it("the independent check catches decor placed in a jump arc, the spawn sas or the exit clearance", function()
		local room = Plan.build({ family = "reception", format = "XL", exit = "window", allowedBehaviors = { "stable" } }, 2, 7)
		local function with(box)
			local c = table.clone(room)
			c.decor = { { id = "bad", kind = "furniture", collide = true, bbox = box, parts = { { box = box, role = "accent" } } } }
			local ok, errs = V.validateDecor(c, Dressing.BLOCK_BUDGET)
			return ok, table.concat(errs, ",")
		end
		local sz = room.spawnZones[1]
		local ok1, e1 = with(Box.onFloor(sz.cx, 0, sz.cz, 3, 3, 3))
		expect(ok1).toBe(false)
		expect(string.find(e1, "decor_in_spawn", 1, true) ~= nil).toBe(true)
		local c = room.exitClearance
		local ok2 = with(Box.new(c.cx, c.cy, c.cz, 2, 2, 2))
		expect(ok2).toBe(false)
		-- a box on the first arc body of a hop between two supports
		local nodes = {}
		for _, n in room.routeGraph.nodes do
			nodes[n.id] = n
		end
		local arcBox
		for _, e in room.routeGraph.edges do
			local a, b = nodes[e.from], nodes[e.to]
			if e.kind == "jump" and a.kind ~= "floor" then
				local bodies = V.arcBodies(a, b)
				arcBox = bodies[math.ceil(#bodies / 2)]
				break
			end
		end
		expect(arcBox ~= nil).toBe(true)
		local ok3 = with(arcBox)
		expect(ok3).toBe(false)
	end)

	it("non-colliding dressing (rugs, ceiling lights) stays inside the room and the budget", function()
		local room = Plan.build({ family = "bin", format = "XL", exit = "window", allowedBehaviors = { "stable" } }, 40, 3)
		local rugs, lights = 0, 0
		for _, item in room.decor do
			if item.kind == "rug" then
				rugs += 1
				expect(item.collide).toBe(false)
			elseif item.kind == "light" then
				lights += 1
				expect(item.collide).toBe(false)
			end
		end
		expect(rugs).toBeAtLeast(1)
		expect(lights).toBeAtLeast(2)
	end)
end)

return true
