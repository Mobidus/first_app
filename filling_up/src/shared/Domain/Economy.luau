--!strict
-- Coin catalog, qualification and purchase planning (docs/03 §4, §6). Prices come ONLY from the
-- compiled economy config. Functions are pure: they inspect a profile and return a plan; the
-- profile mutation itself is applied atomically by ProfileMutations.

local Config = require(script.Parent.Parent.GeneratedConfig)

local Econ = Config.Economy

local Economy = {}

-- Tools actually implemented in this build. Others stay visible but are not purchasable
-- ("Les outils non implémentés ne sont pas achetables dans le MVP").
Economy.IMPLEMENTED_TOOLS = table.freeze({ radar_pop = true, aimant_poche = true, ventouse_chantier = true, parapluie_bonbon = true })

local TOOLS: { [string]: any } = {}
for _, t in Econ.tools do
	TOOLS[t.id] = t
end
local COSMETICS: { [string]: any } = {}
for _, c in Econ.cosmetics do
	COSMETICS[c.id] = c
end
local PREMIUM_GRANTS: { [string]: string } = {}
for _, p in Econ.premium_cosmetics do
	for _, g in p.grants do
		PREMIUM_GRANTS[g] = p.slot
	end
end

function Economy.tool(id: string)
	return TOOLS[id]
end

function Economy.cosmetic(id: string)
	return COSMETICS[id]
end

function Economy.toolStats(id: string, rank: number)
	local t = TOOLS[id]
	assert(t, "unknown tool " .. tostring(id))
	local r = t.ranks[math.clamp(rank, 1, #t.ranks)]
	return r.stats
end

local function completedRooms(profile): number
	return profile.roomMastery and profile.roomMastery.totalCompleted or 0
end

local function tutorialDone(profile): boolean
	return profile.tutorialFlags ~= nil and profile.tutorialFlags.tutorial_exit == true
end

-- Qualification shared by tools and cosmetics (never reset by KO or rebirth).
function Economy.qualifies(profile, unlock): (boolean, string?)
	if unlock.tutorial_complete and not tutorialDone(profile) then
		return false, "tutorial_required"
	end
	if completedRooms(profile) < (unlock.min_completed_rooms or 0) then
		return false, "rooms_required"
	end
	if (profile.rebirthCount or 0) < (unlock.min_rebirth_rank or 0) then
		return false, "rebirth_rank_required"
	end
	if unlock.requires_tool_id and not profile.ownedTools[unlock.requires_tool_id] then
		return false, "tool_required"
	end
	return true, nil
end

export type PurchasePlan = {
	skuId: string,
	kind: "tool" | "upgrade" | "cosmetic",
	itemId: string,
	price: number,
	newRank: number?,
}

-- Parses "tool_id#rankN" upgrade SKUs.
local function parseSku(skuId: string): (string, number?)
	local id, rank = string.match(skuId, "^([%w_]+)#rank(%d)$")
	if id then
		return id, tonumber(rank)
	end
	return skuId, nil
end

-- Returns (true, plan) or (false, reason). Reasons are stable codes for the UI.
function Economy.planCoinPurchase(profile, skuId: string): (boolean, any)
	local id, rank = parseSku(skuId)
	local tool = TOOLS[id]
	if tool then
		if not Economy.IMPLEMENTED_TOOLS[id] then
			return false, "unavailable"
		end
		local ok, why = Economy.qualifies(profile, tool.unlock)
		if not ok then
			return false, why
		end
		if rank == nil then
			if profile.ownedTools[id] then
				return false, "owned"
			end
			return true, { skuId = skuId, kind = "tool", itemId = id, price = tool.coins, newRank = 1 } :: PurchasePlan
		end
		if not profile.ownedTools[id] then
			return false, "tool_required"
		end
		local current = profile.toolRanks[id] or 1
		if rank > #tool.ranks or rank > Econ.upgrade_costs.max_rank then
			return false, "max_rank"
		end
		if rank <= current then
			return false, "owned"
		end
		if rank ~= current + 1 then
			return false, "previous_rank_required"
		end
		return true,
			{ skuId = skuId, kind = "upgrade", itemId = id, price = tool.ranks[rank].upgrade_coins, newRank = rank } :: PurchasePlan
	end
	local cos = COSMETICS[id]
	if cos and rank == nil then
		if profile.ownedCosmetics[id] then
			return false, "owned"
		end
		local ok, why = Economy.qualifies(profile, cos.unlock)
		if not ok then
			return false, why
		end
		return true, { skuId = skuId, kind = "cosmetic", itemId = id, price = cos.coins } :: PurchasePlan
	end
	return false, "unknown_sku"
end

-- Display state for the shop (never authoritative): "owned" | "buyable" | "insufficient" | reason
function Economy.displayState(profile, skuId: string): (string, number?)
	local ok, planOrWhy = Economy.planCoinPurchase(profile, skuId)
	if not ok then
		return planOrWhy, nil
	end
	if profile.coins < planOrWhy.price then
		return "insufficient", planOrWhy.price
	end
	return "buyable", planOrWhy.price
end

function Economy.upgradeCost(toolId: string, rank: number): number
	local t = TOOLS[toolId]
	assert(t and t.ranks[rank], "bad tool/rank")
	return t.ranks[rank].upgrade_coins
end

-- Equipment: 1 active, 1 passive, 1 companion (+ purely visual cosmetic slots).
function Economy.planEquip(profile, itemId: string, slot: string): (boolean, any)
	if itemId == "" then
		return true, { slot = slot, itemId = nil }
	end
	local tool = TOOLS[itemId]
	if tool then
		if not profile.ownedTools[itemId] then
			return false, "not_owned"
		end
		if tool.slot ~= slot then
			return false, "incompatible_slot"
		end
		if not Economy.IMPLEMENTED_TOOLS[itemId] then
			return false, "unavailable"
		end
		return true, { slot = slot, itemId = itemId }
	end
	local cos = COSMETICS[itemId]
	if cos then
		if not profile.ownedCosmetics[itemId] then
			return false, "not_owned"
		end
		if cos.slot ~= slot then
			return false, "incompatible_slot"
		end
		return true, { slot = slot, itemId = itemId }
	end
	local premiumSlot = PREMIUM_GRANTS[itemId]
	if premiumSlot then
		if not profile.purchaseLedger.entitlements[itemId] then
			return false, "not_owned"
		end
		return true, { slot = slot, itemId = itemId }
	end
	return false, "unknown_item"
end

return Economy
