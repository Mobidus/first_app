--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Rebirth = Loader.require("src/shared/Domain/Rebirth")
local Mut = Loader.require("src/shared/Domain/ProfileMutations")
local Config = Loader.require("src/shared/GeneratedConfig")

local SECRET = "test-secret"
local function qualified(permits)
	local p = Mut.newProfile()
	p.permits = permits
	p.coins = 1234
	p.ownedTools.radar_pop = true
	p.toolRanks.radar_pop = 2
	p.ownedCosmetics.trace_ruban_citron = true
	p.purchaseLedger.entitlements.premium_skin_cerise = true
	p.roomMastery.families = { reception = 2, toy = 1, bureau = 1 }
	p.roomMastery.firstRebirthQualified = true
	p.checkpoint = { runId = "r", depth = 30 }
	return p
end

describe("Rebirth", function()
	it("rank cost formula and table examples from config", function()
		for _, ex in Config.Economy.rebirth.rank_examples do
			expect(Rebirth.costForRank(ex.rank)).toBe(ex.cost)
			expect(Rebirth.cumulativeCost(0, ex.rank)).toBe(ex.cumulative_cost_from_zero)
			expect(Rebirth.bonusFraction(ex.rank)).toBeNear(ex.coin_bonus, 1e-12)
		end
		expect(Rebirth.costForRank(25)).toBe(160)
	end)

	it("326 permits buy four ranks for 250 and keep 76", function()
		expect(Rebirth.maxAffordable(0, 326)).toBe(4)
		local p = qualified(326)
		local _, prev = Rebirth.preview(p, "u", 4, SECRET)
		expect(prev.cost).toBe(250)
		expect(prev.permitsAfter).toBe(76)
	end)

	it("exact threshold passes, one permit short fails", function()
		local p = qualified(40)
		expect((Rebirth.preview(p, "u", 1, SECRET))).toBe(true)
		p.permits = 39
		expect(select(2, Rebirth.preview(p, "u", 1, SECRET))).toBe("insufficient_permits")
	end)

	it("first rebirth requires three different families; qualification persists", function()
		local p = qualified(100)
		p.roomMastery.firstRebirthQualified = false
		p.roomMastery.families = { reception = 5 }
		expect(select(2, Rebirth.preview(p, "u", 1, SECRET))).toBe("families_required")
	end)

	it("confirmation recomputes cost, preserves coins, tools, ranks, cosmetics and entitlements", function()
		local p = qualified(326)
		local _, prev = Rebirth.preview(p, "u", 4, SECRET)
		local ok, p2, info = Mut.apply(
			p,
			{ type = "Rebirth", quantity = 4, expectedRevision = p.revision, previewToken = prev.token, inSas = true },
			{ userKey = "u", secret = SECRET }
		)
		expect(ok).toBe(true)
		expect(info.cost).toBe(250)
		expect(p2.permits).toBe(76)
		expect(p2.rebirthCount).toBe(4)
		expect(p2.coins).toBe(1234)
		expect(p2.ownedTools.radar_pop).toBe(true)
		expect(p2.toolRanks.radar_pop).toBe(2)
		expect(p2.ownedCosmetics.trace_ruban_citron).toBe(true)
		expect(p2.purchaseLedger.entitlements.premium_skin_cerise).toBe(true)
		expect(p2.checkpoint).toBe(nil)
	end)

	it("double validation is refused (revision moved on)", function()
		local p = qualified(326)
		local _, prev = Rebirth.preview(p, "u", 2, SECRET)
		local req = { type = "Rebirth", quantity = 2, expectedRevision = p.revision, previewToken = prev.token, inSas = true }
		local ok, p2 = Mut.apply(p, req, { userKey = "u", secret = SECRET })
		expect(ok).toBe(true)
		local ok2, why = Mut.apply(p2, req, { userKey = "u", secret = SECRET })
		expect(ok2).toBe(false)
		expect(why).toBe("stale_revision")
	end)

	it("modified quantity or forged token requires a new preview", function()
		local p = qualified(326)
		local _, prev = Rebirth.preview(p, "u", 1, SECRET)
		local ok, why = Mut.apply(
			p,
			{ type = "Rebirth", quantity = 4, expectedRevision = p.revision, previewToken = prev.token, inSas = true },
			{ userKey = "u", secret = SECRET }
		)
		expect(ok).toBe(false)
		expect(why).toBe("bad_preview_token")
		local ok2 = Mut.apply(
			p,
			{ type = "Rebirth", quantity = 1, expectedRevision = p.revision, previewToken = prev.token, inSas = true },
			{ userKey = "other-user", secret = SECRET }
		)
		expect(ok2).toBe(false)
	end)

	it("rebirth outside the sas is refused (never automatic)", function()
		local p = qualified(326)
		local _, prev = Rebirth.preview(p, "u", 1, SECRET)
		local ok, why = Mut.apply(
			p,
			{ type = "Rebirth", quantity = 1, expectedRevision = p.revision, previewToken = prev.token, inSas = false },
			{ userKey = "u", secret = SECRET }
		)
		expect(ok).toBe(false)
		expect(why).toBe("not_in_sas")
	end)

	it("permits are not purchasable: no coin SKU or Robux pack grants permits", function()
		for _, pack in Config.Economy.coin_packs do
			expect(pack.permits == nil).toBe(true)
		end
		expect(Config.Economy.currencies.permits.purchasable).toBe(false)
		expect(Config.Economy.monetization.paid_coins_grant_permits).toBe(false)
	end)

	it("continuing without rebirth has no hidden penalty: rewards ignore eligibility", function()
		local Rewards = Loader.require("src/shared/Domain/Rewards")
		local a = Rewards.planProgress({ runId = "r", depth = 30, index = 4, mask = 0, rateBp = 0, paidBaseCumulative = 0 })
		expect(a.coins).toBe(450)
	end)
end)

return true
