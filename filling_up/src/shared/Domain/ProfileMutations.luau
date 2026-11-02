--!strict
-- Pure, atomic profile mutations (docs/05 §4, §9). `apply` deep-copies the profile, re-validates
-- the request against canonical config, mutates the copy and validates numeric bounds. The caller
-- (PlayerProfileRepository) commits the copy only after a durable write succeeded.
-- Debit + ownership are a single mutation: there is no state where coins left without the item.

local Config = require(script.Parent.Parent.GeneratedConfig)
local Economy = require(script.Parent.Economy)
local Rebirth = require(script.Parent.Rebirth)
local Rewards = require(script.Parent.Rewards)

local Mut = {}

Mut.SCHEMA_VERSION = Config.Runtime.profile.schema_version
-- Technical bound for integer fields (decision 0005): far above any reachable balance,
-- below 2^53 so that every value stays an exact integer in a double.
Mut.MAX_INT = 1e12
Mut.MAX_RECEIPTS_KEPT = 500

local function deepCopy(v: any): any
	if type(v) ~= "table" then
		return v
	end
	local out = {}
	for k, x in v do
		out[k] = deepCopy(x)
	end
	return out
end
Mut.deepCopy = deepCopy

function Mut.newProfile(): any
	return {
		schemaVersion = Mut.SCHEMA_VERSION,
		revision = 0,
		coins = 0,
		xp = 0,
		permits = 0,
		rebirthCount = 0,
		ownedTools = {},
		toolRanks = {},
		ownedCosmetics = {},
		equippedLoadout = {},
		roomMastery = { totalCompleted = 0, families = {}, firstRebirthQualified = false },
		bestDepth = 0,
		tutorialFlags = {},
		checkpoint = nil,
		settings = { reducedEffects = false, language = "fr", ghostHints = true },
		purchaseLedger = { receipts = {}, receiptOrder = {}, entitlements = {} },
	}
end

local function isInt(v: any): boolean
	return type(v) == "number" and v == v and v % 1 == 0 and v >= 0 and v <= Mut.MAX_INT
end

-- Validates shape, known ids and numeric bounds. Returns (true) or (false, reason).
function Mut.validate(p: any): (boolean, string?)
	if type(p) ~= "table" then
		return false, "not_a_table"
	end
	for _, f in { "revision", "coins", "xp", "permits", "rebirthCount", "bestDepth" } do
		if not isInt(p[f]) then
			return false, "bad_int:" .. f
		end
	end
	for id, owned in p.ownedTools do
		if owned ~= true or not Economy.tool(id) then
			return false, "unknown_tool:" .. tostring(id)
		end
		local r = p.toolRanks[id] or 1
		if not isInt(r) or r < 1 or r > Config.Economy.upgrade_costs.max_rank then
			return false, "bad_rank:" .. id
		end
	end
	for id in p.toolRanks do
		if not p.ownedTools[id] then
			return false, "rank_without_tool:" .. tostring(id)
		end
	end
	for id, owned in p.ownedCosmetics do
		if owned ~= true or not Economy.cosmetic(id) then
			return false, "unknown_cosmetic:" .. tostring(id)
		end
	end
	if not isInt(p.roomMastery.totalCompleted) then
		return false, "bad_int:totalCompleted"
	end
	return true, nil
end

-- Conservative migrations: never drop coins, permits or possessions (docs/05 §9).
function Mut.migrate(raw: any): (any, { string })
	local notes = {}
	if raw == nil then
		return Mut.newProfile(), { "new_profile" }
	end
	local p = deepCopy(raw)
	local v = p.schemaVersion or 1
	if v > Mut.SCHEMA_VERSION then
		error("profile schema " .. v .. " is newer than this server (" .. Mut.SCHEMA_VERSION .. "); refusing to downgrade")
	end
	local base = Mut.newProfile()
	if v < 2 then
		-- v1 stored tools as a list and had no roomMastery
		if type(p.tools) == "table" then
			p.ownedTools = {}
			for _, id in p.tools do
				if Economy.tool(id) then
					p.ownedTools[id] = true
				else
					table.insert(notes, "dropped_unknown_tool:" .. tostring(id))
				end
			end
			p.tools = nil
		end
		table.insert(notes, "migrated_v1_to_v2")
	end
	if v < 3 then
		-- v2 had no purchase ledger and no first-rebirth qualification flag
		p.purchaseLedger = p.purchaseLedger or base.purchaseLedger
		p.roomMastery = p.roomMastery or base.roomMastery
		if p.roomMastery.firstRebirthQualified == nil then
			p.roomMastery.firstRebirthQualified = false
		end
		-- checkpoints of older rule sets cannot be resumed with new rules: extracted conservatively
		if p.checkpoint then
			table.insert(notes, "incompatible_checkpoint_extracted")
			p.checkpoint = nil
		end
		table.insert(notes, "migrated_v2_to_v3")
	end
	for k, dv in base do
		if p[k] == nil and k ~= "checkpoint" then
			p[k] = dv
		end
	end
	p.schemaVersion = Mut.SCHEMA_VERSION
	return p, notes
end

local function updateCheckpointMask(p: any, runId: string, depth: number, mask: number, paid: number)
	local cp = p.checkpoint
	if cp and cp.runId == runId and cp.depth == depth then
		cp.roomRewardMask = mask
		cp.paidBaseCumulative = paid
	end
end

local HANDLERS: { [string]: (p: any, m: any, ctx: any) -> (boolean, any) } = {}

HANDLERS.GrantProgress = function(p, m)
	-- m: { runId, depth, index, mask, rateBp, paidBaseCumulative }
	local claim = Rewards.planProgress(m)
	if #claim.lines == 0 then
		return false, "already_claimed"
	end
	p.coins += claim.coins
	p.permits += claim.permits
	p.xp += claim.xp
	updateCheckpointMask(p, m.runId, m.depth, claim.newMask, claim.newPaidBaseCumulative)
	return true, claim
end

HANDLERS.GrantToken = function(p, m)
	local ok, claim = Rewards.planToken(m.runId, m.depth, m.tokenIndex, m.mask)
	if not ok then
		return false, claim
	end
	p.coins += claim.coins
	updateCheckpointMask(p, m.runId, m.depth, claim.newMask, m.paidBaseCumulative or 0)
	return true, claim
end

HANDLERS.GrantTutorial = function(p, m)
	local amount = Rewards.tutorialReward(m.rewardId)
	if amount == nil then
		return false, "unknown_reward"
	end
	if p.tutorialFlags[m.rewardId] then
		return false, "already_claimed"
	end
	p.tutorialFlags[m.rewardId] = true
	p.coins += amount
	return true, { coins = amount, rewardId = m.rewardId }
end

HANDLERS.GrantOnce = function(p, m)
	-- secondary rewards keyed per account (family discovery, contracts, weekly challenge)
	local sec = Config.Economy.secondary_rewards
	local amount
	if m.kind == "family_discovery" then
		amount = sec.first_room_family_discovery.coins
	elseif m.kind == "practice_contract" then
		amount = sec.practice_contract.coins
	elseif m.kind == "weekly_challenge" then
		amount = sec.weekly_challenge.coins
	else
		return false, "unknown_kind"
	end
	local key = m.kind .. ":" .. tostring(m.key)
	if p.tutorialFlags[key] then
		return false, "already_claimed"
	end
	p.tutorialFlags[key] = true
	p.coins += amount
	return true, { coins = amount, key = key }
end

HANDLERS.CoinPurchase = function(p, m)
	-- the plan is recomputed from the profile being mutated, never taken from the caller
	local ok, plan = Economy.planCoinPurchase(p, m.skuId)
	if not ok then
		return false, plan
	end
	if p.coins < plan.price then
		return false, "insufficient_coins"
	end
	p.coins -= plan.price
	if plan.kind == "tool" then
		p.ownedTools[plan.itemId] = true
		p.toolRanks[plan.itemId] = 1
	elseif plan.kind == "upgrade" then
		p.toolRanks[plan.itemId] = plan.newRank
	else
		p.ownedCosmetics[plan.itemId] = true
	end
	return true, plan
end

HANDLERS.Equip = function(p, m)
	local ok, plan = Economy.planEquip(p, m.itemId, m.slot)
	if not ok then
		return false, plan
	end
	p.equippedLoadout[m.slot] = plan.itemId
	return true, plan
end

HANDLERS.RoomCompleted = function(p, m)
	p.roomMastery.totalCompleted += 1
	p.roomMastery.families[m.familyId] = (p.roomMastery.families[m.familyId] or 0) + 1
	p.bestDepth = math.max(p.bestDepth, m.depth)
	if Rebirth.familiesCompleted(p) >= Config.Economy.rebirth.first_rebirth_required_completed_room_families then
		p.roomMastery.firstRebirthQualified = true -- qualification persists
	end
	return true, nil
end

HANDLERS.SetCheckpoint = function(p, m)
	p.checkpoint = deepCopy(m.checkpoint)
	return true, nil
end

HANDLERS.ClearCheckpoint = function(p)
	p.checkpoint = nil
	return true, nil
end

HANDLERS.Rebirth = function(p, m, ctx)
	local ok, preview = Rebirth.confirm(p, ctx.userKey, m, ctx.secret, m.inSas == true)
	if not ok then
		return false, preview
	end
	p.permits -= preview.cost
	p.rebirthCount += preview.quantity
	p.checkpoint = nil -- depth restarts at 1; coins, tools, ranks, cosmetics, entitlements untouched
	return true, preview
end

HANDLERS.GrantReceipt = function(p, m)
	local ledger = p.purchaseLedger
	if ledger.receipts[m.receiptId] then
		return false, "already_granted"
	end
	if m.coins then
		p.coins += m.coins
	end
	for _, ent in m.entitlements or {} do
		ledger.entitlements[ent] = true
	end
	ledger.receipts[m.receiptId] = true
	table.insert(ledger.receiptOrder, m.receiptId)
	-- bounded ledger: very old consumable receipts are forgotten (Roblox stops retrying them)
	while #ledger.receiptOrder > Mut.MAX_RECEIPTS_KEPT do
		local old = table.remove(ledger.receiptOrder, 1)
		ledger.receipts[old] = nil
	end
	return true, { coins = m.coins or 0 }
end

HANDLERS.Settings = function(p, m)
	if type(m.reducedEffects) == "boolean" then
		p.settings.reducedEffects = m.reducedEffects
	end
	if m.language == "fr" or m.language == "en" then
		p.settings.language = m.language
	end
	if type(m.ghostHints) == "boolean" then
		p.settings.ghostHints = m.ghostHints
	end
	return true, nil
end

Mut.TYPES = {}
for k in HANDLERS do
	table.insert(Mut.TYPES, k)
end
table.sort(Mut.TYPES)

-- apply(profile, mutation, ctx?) -> (true, newProfile, info) | (false, reason)
function Mut.apply(profile: any, mutation: any, ctx: any?): (boolean, any, any)
	local handler = HANDLERS[mutation.type]
	if not handler then
		return false, "unknown_mutation", nil
	end
	local p = deepCopy(profile)
	local ok, info = handler(p, mutation, ctx or {})
	if not ok then
		return false, info, nil
	end
	p.revision += 1
	local valid, why = Mut.validate(p)
	if not valid then
		return false, "invalid_result:" .. tostring(why), nil
	end
	return true, p, info
end

return Mut
