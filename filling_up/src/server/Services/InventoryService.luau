--!strict
-- Coin purchases and equipment. Full shop purchases only in the sas (or the tutorial kiosk);
-- prices come from config through ProfileMutations.CoinPurchase (debit + ownership atomically).
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Economy = require(Shared.Domain.Economy)

local InventoryService = {}
InventoryService.__index = InventoryService

function InventoryService.new(repo: any, telemetry: any)
	return setmetatable({ repo = repo, telemetry = telemetry, seen = {} :: { [string]: boolean } }, InventoryService)
end

-- context: { inSas: boolean, kiosk: boolean }
function InventoryService.buy(self, userKey: string, skuId: string, requestId: string, context: any): any
	local key = userKey .. "|" .. requestId
	if self.seen[key] then
		return { ok = false, error = "duplicate_request" }
	end
	self.seen[key] = true
	if not (context.inSas or (context.kiosk and skuId == "radar_pop")) then
		return { ok = false, error = "shop_only_in_sas" }
	end
	local ok, res, plan = self.repo:mutate(userKey, { type = "CoinPurchase", skuId = skuId })
	self.telemetry:event(
		userKey,
		ok and "coin_purchase" or "coin_purchase_refused",
		{ skuId = skuId, reason = (not ok) and res or nil, price = ok and plan.price or nil }
	)
	if not ok then
		return { ok = false, error = res }
	end
	return { ok = true, profile = res }
end

function InventoryService.equip(self, userKey: string, itemId: string, slot: string, context: any): any
	if not context.inSas and slot ~= "active" and slot ~= "passive" then
		-- cosmetics can be changed in the sas only; tools may be equipped at the kiosk too
		return { ok = false, error = "equip_only_in_sas" }
	end
	if not (context.inSas or context.kiosk) then
		return { ok = false, error = "equip_only_in_sas" }
	end
	local ok, res = self.repo:mutate(userKey, { type = "Equip", itemId = itemId, slot = slot })
	if not ok then
		return { ok = false, error = res }
	end
	return { ok = true, profile = res }
end

function InventoryService.catalog(profile: any): { any }
	local Config = require(Shared.GeneratedConfig)
	local out = {}
	for _, t in Config.Economy.tools do
		local state, price = Economy.displayState(profile, t.id)
		table.insert(out, {
			skuId = t.id,
			kind = "tool",
			name = t.name,
			state = state,
			price = price or t.coins,
			slot = t.slot,
			minRooms = t.unlock.min_completed_rooms,
			stage = t.stage,
		})
		if profile.ownedTools[t.id] then
			local rank = profile.toolRanks[t.id] or 1
			if rank < #t.ranks then
				local sku = t.id .. "#rank" .. (rank + 1)
				local st, pr = Economy.displayState(profile, sku)
				table.insert(out, { skuId = sku, kind = "upgrade", name = t.name, state = st, price = pr, rank = rank + 1 })
			end
		end
	end
	for _, c in Config.Economy.cosmetics do
		local state, price = Economy.displayState(profile, c.id)
		table.insert(out, {
			skuId = c.id,
			kind = "cosmetic",
			name = c.name,
			state = state,
			price = price or c.coins,
			slot = c.slot,
			minRooms = c.unlock.min_completed_rooms,
		})
	end
	return out
end

return InventoryService
