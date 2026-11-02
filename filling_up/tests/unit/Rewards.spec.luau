--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Rewards = Loader.require("src/shared/Domain/Rewards")
local Config = Loader.require("src/shared/GeneratedConfig")

local function claimAll(depth, rateBp)
	local mask, paid, total = 0, 0, 0
	for i = 1, 4 do
		local c = Rewards.planProgress({ runId = "r", depth = depth, index = i, mask = mask, rateBp = rateBp, paidBaseCumulative = paid })
		mask, paid = c.newMask, c.newPaidBaseCumulative
		total += c.coins
	end
	return total, mask, paid
end

describe("Rewards", function()
	it("each band pays exactly its base total without bonus", function()
		for _, band in Config.Economy.reward_bands do
			local total = claimAll(band.min_depth, 0)
			expect(total).toBe(band.base_total)
		end
	end)

	it("cumulative half-up rounding: displayed total equals credited total for all ranks", function()
		for rank = 0, 15 do
			local bp = Rewards.rebirthBasisPoints(rank)
			for _, depth in { 1, 5, 11, 21, 41, 500 } do
				local total = claimAll(depth, bp)
				local base = Rewards.bandForDepth(depth).base_total
				expect(total).toBe(Rewards.roundedCumulative(base, bp))
			end
		end
	end)

	it("bonus caps at 4000 bp (40%) after rank 10", function()
		expect(Rewards.rebirthBasisPoints(10)).toBe(4000)
		expect(Rewards.rebirthBasisPoints(50)).toBe(4000)
		expect(Rewards.rebirthBasisPoints(1)).toBe(400)
	end)

	it("reaching a higher zone pays skipped lower milestones once, in order", function()
		local c = Rewards.planProgress({ runId = "r", depth = 1, index = 3, mask = 0, rateBp = 0, paidBaseCumulative = 0 })
		expect(#c.lines).toBe(3)
		expect(c.coins).toBe(30)
		local again = Rewards.planProgress({
			runId = "r",
			depth = 1,
			index = 3,
			mask = c.newMask,
			rateBp = 0,
			paidBaseCumulative = c.newPaidBaseCumulative,
		})
		expect(#again.lines).toBe(0)
		expect(again.coins).toBe(0)
	end)

	it("exit grants permits and XP exactly once", function()
		local c = Rewards.planProgress({ runId = "r", depth = 12, index = 4, mask = 0, rateBp = 0, paidBaseCumulative = 0 })
		expect(c.coins).toBe(350)
		expect(c.permits).toBe(3)
		expect(c.xp).toBe(60)
		local again = Rewards.planProgress({
			runId = "r",
			depth = 12,
			index = 4,
			mask = c.newMask,
			rateBp = 0,
			paidBaseCumulative = c.newPaidBaseCumulative,
		})
		expect(again.permits).toBe(0)
	end)

	it("reward identity is derived from runId, depth and milestone", function()
		local c = Rewards.planProgress({ runId = "run-x", depth = 7, index = 1, mask = 0, rateBp = 0, paidBaseCumulative = 0 })
		expect(c.lines[1].rewardId).toBe("run-x:7:m1")
	end)

	it("optional tokens: 6 x 5 coins max, never twice, never multiplied", function()
		local mask, total = 0, 0
		for i = 1, 6 do
			local ok, c = Rewards.planToken("r", 1, i, mask)
			expect(ok).toBe(true)
			mask = c.newMask
			total += c.coins
		end
		expect(total).toBe(30)
		expect((Rewards.planToken("r", 1, 3, mask))).toBe(false)
		expect((Rewards.planToken("r", 1, 7, 0))).toBe(false)
	end)

	it("XP formulas: level cost and exit XP", function()
		expect(Rewards.nextLevelCost(1)).toBe(100)
		expect(Rewards.nextLevelCost(41)).toBe(500)
		expect(Rewards.nextLevelCost(1000)).toBe(500)
		expect(Rewards.exitXp(1)).toBe(50)
		expect(Rewards.exitXp(11)).toBe(60)
		expect(Rewards.exitXp(1000)).toBe(150)
	end)

	it("tutorial rewards come from config and total 65", function()
		local sum = 0
		for _, id in Config.Economy.tutorial.reward_ids do
			sum += Rewards.tutorialReward(id)
		end
		expect(sum).toBe(65)
	end)
end)

return true
