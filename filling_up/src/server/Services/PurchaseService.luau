--!strict
-- Robux purchases (docs/03 §9, docs/05 §9, sources S6-S9).
-- * Real purchases are impossible while economy.monetization.robux_shop_enabled == false or while
--   a SKU's product_id / gamepass_id is null: no prompt is ever opened, no fake success is shown.
-- * ProcessReceipt grants coins ONCE per PurchaseId, and returns PurchaseGranted only after the
--   durable profile write succeeded (otherwise NotProcessedYet => Roblox retries later).
-- * Closing the purchase dialog is never treated as a proof of payment.
-- Engine wiring (MarketplaceService) is isolated in `bind`; the decision logic is offline-testable.

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.GeneratedConfig)

local Econ = Config.Economy

local Purchase = {}
Purchase.__index = Purchase

Purchase.GRANTED = "PurchaseGranted"
Purchase.NOT_YET = "NotProcessedYet"

local function packsByProduct(): { [number]: any }
	local map = {}
	for _, p in Econ.coin_packs do
		if p.product_id ~= nil then
			map[p.product_id] = p
		end
	end
	return map
end

function Purchase.new(opts: { repository: any, userKeyFor: (playerId: number) -> string?, log: ((string) -> ())? })
	local self = setmetatable({}, Purchase)
	self.repo = opts.repository
	self.userKeyFor = opts.userKeyFor
	self.log = opts.log or function() end
	self.products = packsByProduct()
	return self
end

-- Can the UI open a real purchase prompt for this SKU? (always false in this delivery)
function Purchase.canPrompt(skuId: string): (boolean, string)
	if Econ.monetization.robux_shop_enabled ~= true then
		return false, "shop_disabled"
	end
	for _, p in Econ.coin_packs do
		if p.sku_id == skuId then
			return p.product_id ~= nil, if p.product_id then "ok" else "product_id_missing"
		end
	end
	for _, p in Econ.premium_cosmetics do
		if p.sku_id == skuId then
			return p.gamepass_id ~= nil, if p.gamepass_id then "ok" else "gamepass_id_missing"
		end
	end
	return false, "unknown_sku"
end

-- receipt: { PurchaseId: string, ProductId: number, PlayerId: number }
function Purchase.processReceipt(self, receipt: any): string
	local pack = self.products[receipt.ProductId]
	if pack == nil then
		self.log("receipt for unknown product " .. tostring(receipt.ProductId) .. " left unprocessed")
		return Purchase.NOT_YET
	end
	local userKey = self.userKeyFor(receipt.PlayerId)
	if userKey == nil then
		return Purchase.NOT_YET -- player offline / profile not loaded on this server: retry later
	end
	local profile = self.repo:get(userKey)
	if profile and profile.purchaseLedger.receipts[receipt.PurchaseId] then
		return Purchase.GRANTED -- already durably granted: idempotent acknowledgement
	end
	local ok, why = self.repo:mutate(userKey, { type = "GrantReceipt", receiptId = tostring(receipt.PurchaseId), coins = pack.coins })
	if ok then
		return Purchase.GRANTED
	end
	if why == "already_granted" then
		return Purchase.GRANTED
	end
	self.log("receipt " .. tostring(receipt.PurchaseId) .. " not granted yet: " .. tostring(why))
	return Purchase.NOT_YET
end

-- Engine binding (Studio / live only).
function Purchase.bind(self)
	local MarketplaceService = game:GetService("MarketplaceService")
	MarketplaceService.ProcessReceipt = function(receiptInfo)
		return Enum.ProductPurchaseDecision[self:processReceipt(receiptInfo)]
	end
end

return Purchase
