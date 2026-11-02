--!nocheck
-- Plush size tiers (decision 0019): mini = wave fill only, large = big formats, giant = XL/XV
-- support only (never dropped by a wave). Validated rooms only.
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Plan = Loader.require("src/shared/Domain/RoomPlan")
local Wave = Loader.require("src/shared/Domain/WaveSchedule")
local V = Loader.require("src/shared/Domain/RouteValidator")
local Config = Loader.require("src/shared/GeneratedConfig")

local TIER = {}
for _, p in Plan.FAMILIES.toy.props do
	TIER[p.id] = p.size_tier
end

local function supportsOf(room)
	local out = {}
	for _, n in room.routeGraph.nodes do
		if n.topProp then
			out[n.topProp] = (out[n.topProp] or 0) + 1
		end
		for _, st in n.stack or {} do
			if st.propId then
				out[st.propId] = (out[st.propId] or 0) + 1
			end
		end
	end
	return out
end

describe("Plush size tiers", function()
	it("config: 4 tiers of plush in the toy family, mini tops below the landing minimum", function()
		local count = { mini = 0, medium = 0, large = 0, giant = 0 }
		for _, p in Plan.FAMILIES.toy.props do
			if p.size_tier then
				count[p.size_tier] += 1
				expect(p.deformation_profile).toBe("plush_soft")
				if p.size_tier == "mini" then
					expect(math.min(p.collider.walkable_top[1], p.collider.walkable_top[2]) < V.MIN_LANDING).toBe(true)
				end
			end
		end
		expect(count.mini).toBe(3)
		expect(count.medium).toBe(2)
		expect(count.large).toBe(2)
		expect(count.giant).toBe(1)
		expect(Plan.PROPS.toy_plush_bobine.wave_drop).toBe(false)
	end)

	it("supports: never a mini; large only in L/V/XL/XV; giant only in XL/XV; the giant does appear", function()
		local giantSeen, largeSeen = 0, 0
		for _, format in Config.Rooms.release_profiles.v1.formats do
			for seed = 1, 25 do
				local room =
					Plan.build({ family = "toy", format = format, exit = "window", allowedBehaviors = { "stable" } }, 40, seed * 17)
				local ok = V.validate(room, { gapRatio = room.gapRatio })
				expect(ok).toBe(true)
				for propId in supportsOf(room) do
					local tier = TIER[propId]
					expect(tier ~= "mini").toBe(true)
					if tier == "large" then
						largeSeen += 1
						expect(table.find({ "L", "V", "XL", "XV" }, format) ~= nil).toBe(true)
					elseif tier == "giant" then
						giantSeen += 1
						expect(format == "XL" or format == "XV").toBe(true)
					end
				end
			end
		end
		expect(giantSeen).toBeAtLeast(1)
		expect(largeSeen).toBeAtLeast(1)
	end)

	it("waves: minis fall from the first toy rooms; the giant never falls; large never in S/M rooms", function()
		local minis, giants = 0, 0
		for _, c in { { "S", 3 }, { "M", 3 }, { "XL", 12 }, { "XV", 12 } } do
			local room = Plan.build({ family = "toy", format = c[1], exit = "window", allowedBehaviors = { "stable" } }, c[2], 5)
			local s = Wave.new(room, Plan.FAMILIES.toy, c[2])
			for i = 1, 40 do
				for _, dr in Wave.at(s, i).drops do
					if not dr.structural then
						local tier = TIER[dr.propId]
						if tier == "mini" then
							minis += 1
						elseif tier == "giant" then
							giants += 1
						elseif tier == "large" then
							expect(c[1] == "XL" or c[1] == "XV").toBe(true)
						end
					end
				end
			end
		end
		expect(minis).toBeAtLeast(10)
		expect(giants).toBe(0)
	end)
end)

return true
