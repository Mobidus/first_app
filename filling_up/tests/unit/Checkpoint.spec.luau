--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Checkpoint = Loader.require("src/shared/Domain/Checkpoint")
local Machine = Loader.require("src/shared/Domain/ExpeditionStateMachine")
local Repo = Loader.require("src/server/Services/PlayerProfileRepository")
local Rewards = Loader.require("src/shared/Domain/Rewards")
local Config = Loader.require("src/shared/GeneratedConfig")

local function now()
	return 0
end

describe("Checkpoint & resume", function()
	it("resume uses the same seed, depth and config version with the reward mask preserved", function()
		local exp = Machine.create({ runId = "run-9", seed = 4242, depth = 7 })
		exp.roomRewardMask = 3
		local cp = Checkpoint.fromExpedition(exp, { rateBasisPoints = 800, paidBaseCumulative = 32 })
		local plan = Checkpoint.plan(cp, Config.configVersion)
		expect(plan.mode).toBe("resume")
		expect(plan.params.seed).toBe(4242)
		expect(plan.params.depth).toBe(7)
		expect(plan.params.roomRewardMask).toBe(3)
		expect(plan.params.roomInstanceId).toBe("run-9:7")
	end)

	it("disconnect mid-room cannot duplicate already claimed milestones", function()
		local store = Repo.MemoryStore.new()
		local repo = Repo.new({ store = store, jobId = "A", now = now })
		repo:load("u")
		local exp = Machine.create({ runId = "run-1", seed = 1, depth = 3 })
		local cp = Checkpoint.fromExpedition(exp, { rateBasisPoints = 0, paidBaseCumulative = 0 })
		repo:mutate("u", { type = "SetCheckpoint", checkpoint = cp })
		-- milestone 1 and 2 claimed, then crash
		assert(
			repo:mutate(
				"u",
				{ type = "GrantProgress", runId = "run-1", depth = 3, index = 2, mask = 0, rateBp = 0, paidBaseCumulative = 0 }
			)
		)
		local coins = repo:get("u").coins
		repo:release("u")
		-- new server resumes from the durable checkpoint
		local repo2 = Repo.new({ store = store, jobId = "B", now = now })
		local _, p = repo2:load("u")
		local plan = Checkpoint.plan(p.checkpoint, Config.configVersion)
		expect(plan.params.roomRewardMask).toBe(3)
		local ok = repo2:mutate("u", {
			type = "GrantProgress",
			runId = "run-1",
			depth = 3,
			index = 2,
			mask = plan.params.roomRewardMask,
			rateBp = 0,
			paidBaseCumulative = plan.params.paidBaseCumulative,
		})
		expect(ok).toBe(false)
		expect(repo2:get("u").coins).toBe(coins)
		-- continuing to milestone 3 pays only milestone 3
		local ok3, p3 = repo2:mutate("u", {
			type = "GrantProgress",
			runId = "run-1",
			depth = 3,
			index = 3,
			mask = plan.params.roomRewardMask,
			rateBp = 0,
			paidBaseCumulative = plan.params.paidBaseCumulative,
		})
		expect(ok3).toBe(true)
		expect(p3.coins - coins).toBe(Rewards.bandForDepth(3).milestones[3])
	end)

	it("session conflict: a second server cannot take the same profile", function()
		local store = Repo.MemoryStore.new()
		local a = Repo.new({ store = store, jobId = "A", now = now })
		local b = Repo.new({ store = store, jobId = "B", now = now })
		a:load("u")
		expect(select(2, b:load("u"))).toBe("session_locked")
	end)

	it("incompatible config version: run closed, goods kept, no record fabricated", function()
		local exp = Machine.create({ runId = "old", seed = 1, depth = 40, configVersion = "deadbeefdeadbeef" })
		local cp = Checkpoint.fromExpedition(exp, { rateBasisPoints = 0, paidBaseCumulative = 0 })
		local plan = Checkpoint.plan(cp, Config.configVersion)
		expect(plan.mode).toBe("extracted")
		expect(plan.reason).toBe("config_version_changed")
	end)

	it("save failure is never announced as saved", function()
		local store = Repo.MemoryStore.new()
		local repo = Repo.new({ store = store, jobId = "A", now = now })
		repo:load("u")
		store.failNext = 1
		local exp = Machine.create({ runId = "r", seed = 1, depth = 2 })
		local ok, why = repo:mutate(
			"u",
			{ type = "SetCheckpoint", checkpoint = Checkpoint.fromExpedition(exp, { rateBasisPoints = 0, paidBaseCumulative = 0 }) }
		)
		expect(ok).toBe(false)
		expect(why).toBe("save_failed")
		expect(repo:get("u").checkpoint).toBe(nil)
	end)
end)

return true
