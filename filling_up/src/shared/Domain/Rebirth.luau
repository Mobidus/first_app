--!strict
-- Voluntary rebirth arithmetic (docs/03 §7). Permits are never purchasable; only the required
-- permits are consumed; several ranks can be converted in one transaction.

local Config = require(script.Parent.Parent.GeneratedConfig)
local Rng = require(script.Parent.Parent.Util.Rng)

local R = Config.Economy.rebirth

local Rebirth = {}

function Rebirth.costForRank(rank: number): number
	assert(rank >= 1 and rank % 1 == 0, "rank must be a positive integer")
	return math.min(R.base_cost + R.increment * (rank - 1), R.cost_cap)
end

-- Total permits to go from currentRank to currentRank + quantity.
function Rebirth.cumulativeCost(currentRank: number, quantity: number): number
	local total = 0
	for r = currentRank + 1, currentRank + quantity do
		total += Rebirth.costForRank(r)
	end
	return total
end

function Rebirth.maxAffordable(currentRank: number, permits: number): number
	local q, spent = 0, 0
	while true do
		local c = Rebirth.costForRank(currentRank + q + 1)
		if spent + c > permits then
			return q
		end
		spent += c
		q += 1
	end
end

function Rebirth.bonusFraction(rank: number): number
	return math.min(R.coin_bonus_per_rank * rank, R.coin_bonus_cap)
end

function Rebirth.familiesCompleted(profile): number
	local n = 0
	for _, count in profile.roomMastery.families do
		if count > 0 then
			n += 1
		end
	end
	return n
end

function Rebirth.qualifies(profile): (boolean, string?)
	if profile.rebirthCount == 0 and not profile.roomMastery.firstRebirthQualified then
		if Rebirth.familiesCompleted(profile) < R.first_rebirth_required_completed_room_families then
			return false, "families_required"
		end
	end
	return true, nil
end

export type Preview = {
	quantity: number,
	cost: number,
	ranksAfter: number,
	permitsAfter: number,
	bonusAfter: number,
	revision: number,
	token: string,
}

-- Token bound to player, quantity and revision. `secret` is a per-server random salt.
function Rebirth.token(userKey: string, quantity: number, revision: number, secret: string): string
	local h1 = Rng.hash(string.format("%s|%d|%d|%s", userKey, quantity, revision, secret))
	local h2 = Rng.hash(string.format("%s#%d#%d#%s", secret, revision, quantity, userKey))
	return string.format("rb%08x%08x", h1, h2)
end

function Rebirth.preview(profile, userKey: string, quantity: number, secret: string): (boolean, any)
	local ok, why = Rebirth.qualifies(profile)
	if not ok then
		return false, why
	end
	if quantity < 1 or quantity % 1 ~= 0 then
		return false, "bad_quantity"
	end
	local cost = Rebirth.cumulativeCost(profile.rebirthCount, quantity)
	if cost > profile.permits then
		return false, "insufficient_permits"
	end
	return true,
		{
			quantity = quantity,
			cost = cost,
			ranksAfter = profile.rebirthCount + quantity,
			permitsAfter = profile.permits - cost,
			bonusAfter = Rebirth.bonusFraction(profile.rebirthCount + quantity),
			revision = profile.revision,
			token = Rebirth.token(userKey, quantity, profile.revision, secret),
		} :: Preview
end

-- Server-side confirmation check. The cost is RECOMPUTED here; nothing from the client is used
-- except quantity/revision/token which must all match a fresh server computation.
function Rebirth.confirm(
	profile,
	userKey: string,
	req: { quantity: number, expectedRevision: number, previewToken: string },
	secret: string,
	inSas: boolean
): (boolean, any)
	if not inSas then
		return false, "not_in_sas"
	end
	if req.expectedRevision ~= profile.revision then
		return false, "stale_revision"
	end
	if req.previewToken ~= Rebirth.token(userKey, req.quantity, profile.revision, secret) then
		return false, "bad_preview_token"
	end
	return Rebirth.preview(profile, userKey, req.quantity, secret)
end

return Rebirth
