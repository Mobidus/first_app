--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Economy = Loader.require("src/shared/Domain/Economy")
local Mut = Loader.require("src/shared/Domain/ProfileMutations")
local Config = Loader.require("src/shared/GeneratedConfig")

local function profileWith(coins, rooms)
	local p = Mut.newProfile()
	p.coins = coins
	p.tutorialFlags.tutorial_exit = true
	p.roomMastery.totalCompleted = rooms or 0
	return p
end

describe("Economy catalog", function()
	it("prices come from the canonical JSON", function()
		for _, t in Config.Economy.tools do
			if Economy.IMPLEMENTED_TOOLS[t.id] then
				local p = profileWith(1e6, 100)
				local ok, plan = Economy.planCoinPurchase(p, t.id)
				expect(ok).toBe(true)
				expect(plan.price).toBe(t.coins)
			end
		end
	end)

	it("radar is buyable after tutorial with 65 coins and leaves 15", function()
		local p = profileWith(65, 0)
		local ok, p2 = Mut.apply(p, { type = "CoinPurchase", skuId = "radar_pop" })
		expect(ok).toBe(true)
		expect(p2.coins).toBe(15)
		expect(p2.ownedTools.radar_pop).toBe(true)
	end)

	it("insufficient balance is refused and nothing changes", function()
		local p = profileWith(49, 0)
		local ok, why = Mut.apply(p, { type = "CoinPurchase", skuId = "radar_pop" })
		expect(ok).toBe(false)
		expect(why).toBe("insufficient_coins")
		expect(p.coins).toBe(49)
	end)

	it("double purchase is refused: owned stays owned", function()
		local p = profileWith(500, 0)
		local _, p2 = Mut.apply(p, { type = "CoinPurchase", skuId = "radar_pop" })
		local ok, why = Mut.apply(p2, { type = "CoinPurchase", skuId = "radar_pop" })
		expect(ok).toBe(false)
		expect(why).toBe("owned")
		expect(Economy.displayState(p2, "radar_pop")).toBe("owned")
	end)

	it("room qualification gates tools without any rebirth requirement", function()
		local p = profileWith(10000, 2)
		expect(select(2, Economy.planCoinPurchase(p, "ventouse_chantier"))).toBe("rooms_required")
		p.roomMastery.totalCompleted = 3
		expect((Economy.planCoinPurchase(p, "ventouse_chantier"))).toBe(true)
	end)

	it("V1 tools are visible but not purchasable in this build", function()
		local p = profileWith(1e6, 100)
		expect(select(2, Economy.planCoinPurchase(p, "grappin_balancier"))).toBe("unavailable")
	end)

	it("upgrades need the previous rank and cost the configured additional price", function()
		local p = profileWith(10000, 10)
		local _, p1 = Mut.apply(p, { type = "CoinPurchase", skuId = "parapluie_bonbon" })
		expect(select(2, Economy.planCoinPurchase(p1, "parapluie_bonbon#rank3"))).toBe("previous_rank_required")
		local ok, p2 = Mut.apply(p1, { type = "CoinPurchase", skuId = "parapluie_bonbon#rank2" })
		expect(ok).toBe(true)
		expect(p1.coins - p2.coins).toBe(350)
		local _, p3 = Mut.apply(p2, { type = "CoinPurchase", skuId = "parapluie_bonbon#rank3" })
		expect(p2.coins - p3.coins).toBe(650)
		expect(p3.toolRanks.parapluie_bonbon).toBe(3)
		expect(select(2, Economy.planCoinPurchase(p3, "parapluie_bonbon#rank4"))).toBeTruthy()
	end)

	it("full catalog totals match the economy reference (39 250 / 98 450)", function()
		local base, all = 0, 0
		for _, t in Config.Economy.tools do
			base += t.coins
			all += t.coins + t.ranks[2].upgrade_coins + t.ranks[3].upgrade_coins
		end
		expect(base).toBe(Config.Economy.simulation.full_catalog_base_cost)
		expect(all).toBe(Config.Economy.simulation.full_catalog_all_ranks_total_cost)
	end)

	it("cosmetics: tool skin requires the tool, owned shows Possédé state", function()
		local p = profileWith(1000, 0)
		expect(select(2, Economy.planCoinPurchase(p, "skin_radar_citron"))).toBe("tool_required")
		local _, p1 = Mut.apply(p, { type = "CoinPurchase", skuId = "radar_pop" })
		local ok, p2 = Mut.apply(p1, { type = "CoinPurchase", skuId = "skin_radar_citron" })
		expect(ok).toBe(true)
		expect(Economy.displayState(p2, "skin_radar_citron")).toBe("owned")
	end)

	it("equip: one active, one passive; slot compatibility enforced", function()
		local p = profileWith(1000, 1)
		local _, p1 = Mut.apply(p, { type = "CoinPurchase", skuId = "radar_pop" })
		local _, p2 = Mut.apply(p1, { type = "CoinPurchase", skuId = "aimant_poche" })
		expect((Mut.apply(p2, { type = "Equip", itemId = "radar_pop", slot = "passive" }))).toBe(false)
		local _, p3 = Mut.apply(p2, { type = "Equip", itemId = "radar_pop", slot = "active" })
		local _, p4 = Mut.apply(p3, { type = "Equip", itemId = "aimant_poche", slot = "passive" })
		expect(p4.equippedLoadout.active).toBe("radar_pop")
		expect(p4.equippedLoadout.passive).toBe("aimant_poche")
		expect((Mut.apply(p4, { type = "Equip", itemId = "ventouse_chantier", slot = "active" }))).toBe(false)
	end)

	it("amounts stay integers: no fractional price can appear", function()
		for _, t in Config.Economy.tools do
			for _, r in t.ranks do
				expect(r.upgrade_coins % 1).toBe(0)
			end
		end
	end)
end)

return true
