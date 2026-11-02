--!nocheck
-- Shared certification sweep used by generation-initial / generation-full suites.
local serde = require("@lune/serde")
local fs = require("@lune/fs")
local process = require("@lune/process")
local Loader = require("./Loader")
local Plan = Loader.require("src/shared/Domain/RoomPlan")
local V = Loader.require("src/shared/Domain/RouteValidator")
local Config = Loader.require("src/shared/GeneratedConfig")

local SEEDS_PER_COMBO = tonumber(process.env.FU_SEEDS or "") or 120
local DEPTHS = { 1, 5, 12, 25, 45, 90 }

local function certify(profileName, outPath)
	local prof = Config.Rooms.release_profiles[profileName]
	local report = {
		profile = profileName,
		seeds_per_combo = SEEDS_PER_COMBO,
		combos = {},
		failing_seeds = {},
		total = 0,
		primary_ok = 0,
		fallback = 0,
		unbuildable = 0,
	}
	for _, famId in prof.families do
		local fam = Plan.FAMILIES[famId]
		for _, fmt in prof.formats do
			for _, ex in prof.exits do
				if table.find(fam.exits, ex) then
					local key = Plan.comboKey(famId, fmt, ex)
					local c = { key = key, tested = 0, primary_ok = 0, fallback = 0, unbuildable = 0 }
					for i = 1, SEEDS_PER_COMBO do
						local depth = math.max(fam.minimum_depth, DEPTHS[(i % #DEPTHS) + 1])
						local seed = i * 7919 + #key * 31
						local spec =
							{ family = famId, format = fmt, exit = ex, allowedBehaviors = { "stable", "bounce", "moving", "temporary" } }
						local room, diags = Plan.build(spec, depth, seed)
						c.tested += 1
						if room == nil then
							c.unbuildable += 1
							table.insert(report.failing_seeds, { combo = key, depth = depth, seed = seed, reason = diags[#diags] })
						else
							local ok = V.validate(room, { gapRatio = room.gapRatio })
							assert(ok, "build() returned an invalid room for " .. key .. " seed " .. seed)
							if room.fallback then
								c.fallback += 1
								table.insert(
									report.failing_seeds,
									{ combo = key, depth = depth, seed = seed, reason = "primary_rejected_fallback_used" }
								)
							else
								c.primary_ok += 1
							end
						end
					end
					c.certified = c.unbuildable == 0
					report.combos[key] = c
					report.total += c.tested
					report.primary_ok += c.primary_ok
					report.fallback += c.fallback
					report.unbuildable += c.unbuildable
				end
			end
		end
	end
	if #report.failing_seeds > 200 then
		report.failing_seeds_truncated = #report.failing_seeds
		local keep = {}
		for i = 1, 200 do
			keep[i] = report.failing_seeds[i]
		end
		report.failing_seeds = keep
	end
	fs.writeFile(outPath, serde.encode("json", report, true))
	return report
end

return { certify = certify, SEEDS_PER_COMBO = SEEDS_PER_COMBO }
