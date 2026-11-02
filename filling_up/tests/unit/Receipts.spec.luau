--!nocheck
-- Receipt logic with mocks. A mock validates the LOGIC only, not a Roblox payment (T20 stays
-- blocked until real product ids exist in an authorised test experience).
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Purchase = Loader.require("src/server/Services/PurchaseService")
local Repo = Loader.require("src/server/Services/PlayerProfileRepository")
local Config = Loader.require("src/shared/GeneratedConfig")

local function setup(fakeProductId)
	local store = Repo.MemoryStore.new()
	local repo = Repo.new({
		store = store,
		jobId = "J",
		now = function()
			return 0
		end,
	})
	repo:load("u1")
	local svc = Purchase.new({
		repository = repo,
		userKeyFor = function(pid)
			return if pid == 1 then "u1" else nil
		end,
	})
	if fakeProductId then
		-- test-only injection of a fake product mapping; config ids remain null
		svc.products[fakeProductId] = { sku_id = "coins_800", coins = 800 }
	end
	return svc, repo, store
end

describe("PurchaseService receipts", function()
	it("delivery shipped with every product/gamepass id null and the shop disabled", function()
		for _, p in Config.Economy.coin_packs do
			expect(p.product_id).toBe(nil)
			expect((Purchase.canPrompt(p.sku_id))).toBe(false)
		end
		for _, p in Config.Economy.premium_cosmetics do
			expect(p.gamepass_id).toBe(nil)
			expect((Purchase.canPrompt(p.sku_id))).toBe(false)
		end
	end)

	it("unknown product (null id never matches) is not granted", function()
		local svc = setup(nil)
		expect(svc:processReceipt({ PurchaseId = "p1", ProductId = 123, PlayerId = 1 })).toBe(Purchase.NOT_YET)
	end)

	it("grants once per PurchaseId after a durable write; double receipt is idempotent", function()
		local svc, repo = setup(999)
		expect(svc:processReceipt({ PurchaseId = "p1", ProductId = 999, PlayerId = 1 })).toBe(Purchase.GRANTED)
		expect(svc:processReceipt({ PurchaseId = "p1", ProductId = 999, PlayerId = 1 })).toBe(Purchase.GRANTED)
		expect(repo:get("u1").coins).toBe(800)
	end)

	it("save unavailable => NotProcessedYet, nothing granted; the retry grants exactly once", function()
		local svc, repo, store = setup(999)
		store.failNext = 1
		expect(svc:processReceipt({ PurchaseId = "p2", ProductId = 999, PlayerId = 1 })).toBe(Purchase.NOT_YET)
		expect(repo:get("u1").coins).toBe(0)
		expect(svc:processReceipt({ PurchaseId = "p2", ProductId = 999, PlayerId = 1 })).toBe(Purchase.GRANTED)
		expect(repo:get("u1").coins).toBe(800)
	end)

	it("deferred receipt for an offline player stays unprocessed (retried later)", function()
		local svc = setup(999)
		expect(svc:processReceipt({ PurchaseId = "p3", ProductId = 999, PlayerId = 77 })).toBe(Purchase.NOT_YET)
	end)

	it("purchased coins and entitlements survive a rebirth", function()
		local svc, repo = setup(999)
		svc:processReceipt({ PurchaseId = "p4", ProductId = 999, PlayerId = 1 })
		repo:mutate("u1", { type = "GrantReceipt", receiptId = "gp1", entitlements = { "premium_skin_cerise" } })
		local p = repo:get("u1")
		expect(p.coins).toBe(800)
		expect(p.purchaseLedger.entitlements.premium_skin_cerise).toBe(true)
	end)
end)

return true
