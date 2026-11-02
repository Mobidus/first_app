--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Mut = Loader.require("src/shared/Domain/ProfileMutations")

describe("ProfileMutations", function()
	it("new profile validates and has schema version from config", function()
		local p = Mut.newProfile()
		expect((Mut.validate(p))).toBe(true)
		expect(p.schemaVersion).toBe(3)
	end)

	it("every successful mutation increments revision; failures never mutate input", function()
		local p = Mut.newProfile()
		local ok, p2 = Mut.apply(p, { type = "GrantTutorial", rewardId = "tutorial_discovery" })
		expect(ok).toBe(true)
		expect(p2.revision).toBe(1)
		expect(p.revision).toBe(0)
		expect(p.coins).toBe(0)
	end)

	it("tutorial rewards are once per account", function()
		local p = Mut.newProfile()
		local _, p1 = Mut.apply(p, { type = "GrantTutorial", rewardId = "tutorial_exit" })
		local ok, why = Mut.apply(p1, { type = "GrantTutorial", rewardId = "tutorial_exit" })
		expect(ok).toBe(false)
		expect(why).toBe("already_claimed")
		expect((Mut.apply(p1, { type = "GrantTutorial", rewardId = "made_up" }))).toBe(false)
	end)

	it("milestones are granted once and the checkpoint mask follows atomically", function()
		local p = Mut.newProfile()
		p.checkpoint = { runId = "r1", depth = 2, roomRewardMask = 0, paidBaseCumulative = 0 }
		local ok, p1 =
			Mut.apply(p, { type = "GrantProgress", runId = "r1", depth = 2, index = 1, mask = 0, rateBp = 0, paidBaseCumulative = 0 })
		expect(ok).toBe(true)
		expect(p1.coins).toBe(10)
		expect(p1.checkpoint.roomRewardMask).toBe(1)
		local again = Mut.apply(p1, {
			type = "GrantProgress",
			runId = "r1",
			depth = 2,
			index = 1,
			mask = p1.checkpoint.roomRewardMask,
			rateBp = 0,
			paidBaseCumulative = 10,
		})
		expect(again).toBe(false)
	end)

	it("KO does not touch coins, permits or inventory (no KO mutation exists)", function()
		for _, t in Mut.TYPES do
			expect(string.find(string.lower(t), "ko") == nil).toBe(true)
		end
	end)

	it("rejects non-finite or out-of-bounds numbers", function()
		local p = Mut.newProfile()
		p.coins = 0 / 0
		expect((Mut.validate(p))).toBe(false)
		p.coins = -1
		expect((Mut.validate(p))).toBe(false)
		p.coins = 1.5
		expect((Mut.validate(p))).toBe(false)
		p.coins = 2e12
		expect((Mut.validate(p))).toBe(false)
	end)

	it("rejects unknown item identifiers", function()
		local p = Mut.newProfile()
		p.ownedTools.hack_tool = true
		expect((Mut.validate(p))).toBe(false)
	end)

	it("migrates v1 profiles without losing coins or tools", function()
		local v1 = {
			schemaVersion = 1,
			revision = 4,
			coins = 777,
			xp = 10,
			permits = 9,
			rebirthCount = 0,
			tools = { "radar_pop", "ghost_tool" },
			toolRanks = { radar_pop = 2 },
			ownedCosmetics = {},
			equippedLoadout = {},
			bestDepth = 3,
			tutorialFlags = { tutorial_exit = true },
			checkpoint = { runId = "old", depth = 3 },
			settings = { reducedEffects = false, language = "fr", ghostHints = true },
		}
		local p, notes = Mut.migrate(v1)
		expect(p.coins).toBe(777)
		expect(p.permits).toBe(9)
		expect(p.ownedTools.radar_pop).toBe(true)
		expect(p.ownedTools.ghost_tool).toBe(nil)
		expect(p.checkpoint).toBe(nil)
		expect(p.schemaVersion).toBe(3)
		expect((Mut.validate(p))).toBe(true)
		local found = false
		for _, n in notes do
			if n == "incompatible_checkpoint_extracted" then
				found = true
			end
		end
		expect(found).toBe(true)
	end)

	it("refuses to downgrade a profile from a newer schema", function()
		expect(function()
			Mut.migrate({ schemaVersion = 99 })
		end).toThrow()
	end)

	it("receipt grants are idempotent and the ledger is bounded", function()
		local p = Mut.newProfile()
		local ok, p1 = Mut.apply(p, { type = "GrantReceipt", receiptId = "rcpt-1", coins = 800 })
		expect(ok).toBe(true)
		expect(p1.coins).toBe(800)
		expect((Mut.apply(p1, { type = "GrantReceipt", receiptId = "rcpt-1", coins = 800 }))).toBe(false)
		local q = p1
		for i = 2, Mut.MAX_RECEIPTS_KEPT + 10 do
			local _, nq = Mut.apply(q, { type = "GrantReceipt", receiptId = "rcpt-" .. i, coins = 0 })
			q = nq
		end
		expect(#q.purchaseLedger.receiptOrder).toBe(Mut.MAX_RECEIPTS_KEPT)
	end)

	it("room completion persists family qualification", function()
		local p = Mut.newProfile()
		for _, fam in { "reception", "toy", "bureau" } do
			local _, np = Mut.apply(p, { type = "RoomCompleted", familyId = fam, depth = 4 })
			p = np
		end
		expect(p.roomMastery.firstRebirthQualified).toBe(true)
		expect(p.roomMastery.totalCompleted).toBe(3)
		expect(p.bestDepth).toBe(4)
	end)
end)

return true
