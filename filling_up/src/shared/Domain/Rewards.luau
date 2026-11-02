--!strict
-- Reward arithmetic (docs/03 §5, economy.json reward_bands / reward_rules / optional_tokens).
-- All amounts are integers. The rebirth bonus uses integer basis points and CUMULATIVE
-- half-up rounding: each base grant pays round(mult * cumulativeBase) - alreadyPaid.

local Config = require(script.Parent.Parent.GeneratedConfig)

local Econ = Config.Economy
local Rules = Econ.reward_rules
local Rounding = Rules.rounding
local XP = Config.Runtime.account_xp

local Rewards = {}

-- Room reward mask bits: milestones 1..3 -> bits 0..2, exit -> bit 3, tokens 1..6 -> bits 4..9
Rewards.MILESTONE_COUNT = 3
Rewards.EXIT_BIT = 3
Rewards.TOKEN_BIT0 = 4

local function bit(i: number): number
	return bit32.lshift(1, i)
end

function Rewards.hasBit(mask: number, i: number): boolean
	return bit32.band(mask, bit(i)) ~= 0
end

function Rewards.setBit(mask: number, i: number): number
	return bit32.bor(mask, bit(i))
end

function Rewards.bandForDepth(depth: number)
	assert(type(depth) == "number" and depth >= 1 and depth % 1 == 0, "depth must be a positive integer")
	for _, band in Econ.reward_bands do
		if depth >= band.min_depth and (band.max_depth == nil or depth <= band.max_depth) then
			return band
		end
	end
	error("no reward band for depth " .. depth)
end

function Rewards.rebirthBasisPoints(rebirthRank: number): number
	return math.min(Rounding.rebirth_bonus_basis_points_per_rank * math.max(0, rebirthRank), Rounding.rebirth_bonus_basis_points_cap)
end

-- floor((cum * (D + bp) + D/2) / D): exact half-up integer rounding
function Rewards.roundedCumulative(cumulativeBase: number, bp: number): number
	local d = Rounding.basis_point_denominator
	return math.floor((cumulativeBase * (d + bp) + d / 2) / d)
end

-- Ordered base grants of a room: { milestone1, milestone2, milestone3, exit }
function Rewards.baseSchedule(depth: number): { number }
	local band = Rewards.bandForDepth(depth)
	local list = table.clone(band.milestones)
	table.insert(list, band.exit_reward)
	return list
end

-- Index (1..4) -> bit in the room mask
local function gradeBit(index: number): number
	return if index <= Rewards.MILESTONE_COUNT then index - 1 else Rewards.EXIT_BIT
end

export type GrantLine = { rewardId: string, kind: string, amount: number, bit: number }

export type Claim = {
	lines: { GrantLine },
	coins: number,
	permits: number,
	xp: number,
	newMask: number,
	newPaidBaseCumulative: number,
}

-- Plan the grants produced when the player validly reaches milestone `index` (1..3) or the
-- exit (index 4). Reaching a higher zone implies the lower ones (zones are progressive heights,
-- a shortcut may skip landing on them). Already-claimed bits pay nothing.
-- `rateBp` is the rebirth bonus frozen at room start. `paidBaseCumulative` is what the room has
-- already paid from base grants (including bonus) so totals always match.
function Rewards.planProgress(params: {
	runId: string,
	depth: number,
	index: number,
	mask: number,
	rateBp: number,
	paidBaseCumulative: number,
}): Claim
	assert(params.index >= 1 and params.index <= 4 and params.index % 1 == 0, "bad milestone index")
	local schedule = Rewards.baseSchedule(params.depth)
	local band = Rewards.bandForDepth(params.depth)
	local mask = params.mask
	local lines = {}
	local cumulativeBase = 0
	-- cumulative base of grants already claimed (claims are always prefix-ordered)
	for i = 1, 4 do
		if Rewards.hasBit(mask, gradeBit(i)) then
			cumulativeBase += schedule[i]
		end
	end
	local paid = params.paidBaseCumulative
	local coins, permits, xp = 0, 0, 0
	for i = 1, params.index do
		local b = gradeBit(i)
		if not Rewards.hasBit(mask, b) then
			cumulativeBase += schedule[i]
			local target = Rewards.roundedCumulative(cumulativeBase, params.rateBp)
			local amount = target - paid
			paid = target
			mask = Rewards.setBit(mask, b)
			local kind = if i == 4 then "exit" else "milestone"
			table.insert(lines, {
				rewardId = string.format("%s:%d:%s", params.runId, params.depth, if i == 4 then "exit" else "m" .. i),
				kind = kind,
				amount = amount,
				bit = b,
			})
			coins += amount
			if i == 4 then
				permits += band.permits
				xp += Rewards.exitXp(params.depth)
			end
		end
	end
	return { lines = lines, coins = coins, permits = permits, xp = xp, newMask = mask, newPaidBaseCumulative = paid }
end

-- Optional tokens: 6 per room, 5 Coins each, never multiplied, never respawned.
function Rewards.planToken(runId: string, depth: number, tokenIndex: number, mask: number): (boolean, any)
	local tok = Econ.optional_tokens
	if type(tokenIndex) ~= "number" or tokenIndex % 1 ~= 0 or tokenIndex < 1 or tokenIndex > tok.tokens_per_room then
		return false, "bad_token"
	end
	local b = Rewards.TOKEN_BIT0 + tokenIndex - 1
	if Rewards.hasBit(mask, b) then
		return false, "already_claimed"
	end
	return true,
		{
			lines = {
				{ rewardId = string.format("%s:%d:t%d", runId, depth, tokenIndex), kind = "token", amount = tok.coins_per_token, bit = b },
			},
			coins = tok.coins_per_token,
			newMask = Rewards.setBit(mask, b),
		}
end

function Rewards.exitXp(depth: number): number
	local band = math.floor((depth - 1) / XP.depth_band_width)
	return XP.exit_base + XP.exit_increment_per_depth_band * math.min(band, XP.exit_increment_cap)
end

function Rewards.nextLevelCost(level: number): number
	return XP.next_level_base + XP.next_level_increment * math.min(level - 1, XP.next_level_increment_cap)
end

-- XP -> (level, xpIntoLevel). No final level.
function Rewards.levelForXp(xp: number): (number, number)
	local level = 1
	local remaining = xp
	while remaining >= Rewards.nextLevelCost(level) do
		remaining -= Rewards.nextLevelCost(level)
		level += 1
		if level > 1e6 then
			break
		end
	end
	return level, remaining
end

-- Tutorial rewards: ids and amounts from config, once per account.
function Rewards.tutorialReward(rewardId: string): number?
	for i, id in Econ.tutorial.reward_ids do
		if id == rewardId then
			return Econ.tutorial.rewards[i]
		end
	end
	return nil
end

return Rewards
