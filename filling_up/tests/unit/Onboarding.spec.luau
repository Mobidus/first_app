--!nocheck
-- Vertical slice of the first session at the logic level: tutorial rewards (65), Radar kiosk
-- purchase through the real repository (50 -> 15), equip, entry into room 1, first Radar use.
-- The 30 s target is checked on the NOMINAL script; slow players are never eliminated.
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Repo = Loader.require("src/server/Services/PlayerProfileRepository")
local Tutorial = Loader.require("src/shared/Domain/Tutorial")
local Tools = Loader.require("src/shared/Domain/ToolRules")
local Config = Loader.require("src/shared/GeneratedConfig")

local function firstSession(repo, user, script)
	local s = Tutorial.newSession()
	local tools = Tools.newState()
	local log = {}
	for _, step in script do
		local t, ev = step[1], step[2]
		Tutorial.record(s, ev, t)
		local p = repo:get(user)
		local reward = Tutorial.rewardFor(ev, p.tutorialFlags)
		if reward then
			local ok = repo:mutate(user, { type = "GrantTutorial", rewardId = reward })
			table.insert(log, { t = t, ev = "reward:" .. reward, ok = ok })
		end
		if ev == "kiosk_buy" then
			local ok, res = repo:mutate(user, { type = "CoinPurchase", skuId = Tutorial.FIRST_TOOL })
			table.insert(log, { t = t, ev = "buy", ok = ok, res = res })
			if ok then
				repo:mutate(user, { type = "Equip", itemId = Tutorial.FIRST_TOOL, slot = "active" })
			end
		elseif ev == "enter_room1" then
			tools = Tools.enterRoom(tools, repo:get(user), "run-1:1", nil)
		elseif ev == "radar_use" then
			local ok, eff = Tools.check(tools, "radar_pop", {
				profile = repo:get(user),
				roomState = "Active",
				inSas = false,
				now = t,
				player = { x = 0, y = 0, z = 0, vy = 0, grounded = true },
			})
			table.insert(log, { t = t, ev = "radar", ok = ok, res = eff })
			if ok then
				tools = Tools.commit(tools, eff, t)
			end
		end
	end
	return s, log
end

local NOMINAL = {
	{ 0, "controllable" },
	{ 1.8, "carton_settled" },
	{ 4.1, "landed_on_support" },
	{ 8.6, "exit_reached" },
	{ 12.5, "kiosk_shown" },
	{ 15.2, "kiosk_buy" },
	{ 21.0, "enter_room1" },
	{ 24.4, "radar_use" },
}

describe("Onboarding vertical slice", function()
	it("nominal path: 65 coins, Radar bought for 50, balance 15, used before 30 s", function()
		local store = Repo.MemoryStore.new()
		local repo = Repo.new({
			store = store,
			jobId = "J",
			now = function()
				return 0
			end,
		})
		repo:load("new-player")
		local s, log = firstSession(repo, "new-player", NOMINAL)
		local p = repo:get("new-player")
		expect(p.coins).toBe(15)
		expect(p.ownedTools.radar_pop).toBe(true)
		expect(p.equippedLoadout.active).toBe("radar_pop")
		local m = Tutorial.metrics(s)
		expect(m.radar_use).toBeAtMost(Config.Economy.tutorial.first_use_target_before_seconds)
		local radarOk = false
		for _, l in log do
			if l.ev == "radar" then
				radarOk = l.ok
			end
		end
		expect(radarOk).toBe(true)
	end)

	it("tutorial pays 65 exactly once: replay / reconnect / new server pay nothing more", function()
		local store = Repo.MemoryStore.new()
		local repo = Repo.new({
			store = store,
			jobId = "J",
			now = function()
				return 0
			end,
		})
		repo:load("u")
		firstSession(repo, "u", { { 0, "controllable" }, { 2, "carton_settled" }, { 4, "landed_on_support" }, { 8, "exit_reached" } })
		expect(repo:get("u").coins).toBe(65)
		firstSession(repo, "u", { { 0, "controllable" }, { 2, "carton_settled" }, { 4, "landed_on_support" }, { 8, "exit_reached" } })
		expect(repo:get("u").coins).toBe(65)
		repo:release("u")
		local repo2 = Repo.new({
			store = store,
			jobId = "K",
			now = function()
				return 0
			end,
		})
		repo2:load("u")
		firstSession(repo2, "u", { { 0, "controllable" }, { 2, "carton_settled" }, { 4, "landed_on_support" }, { 8, "exit_reached" } })
		expect(repo2:get("u").coins).toBe(65)
	end)

	it("replayed purchase request is refused (idempotent: owned)", function()
		local store = Repo.MemoryStore.new()
		local repo = Repo.new({
			store = store,
			jobId = "J",
			now = function()
				return 0
			end,
		})
		repo:load("u")
		local _, log = firstSession(repo, "u", {
			{ 0, "controllable" },
			{ 2, "carton_settled" },
			{ 4, "landed_on_support" },
			{ 8, "exit_reached" },
			{ 10, "kiosk_buy" },
			{ 10.05, "kiosk_buy" },
		})
		local buys = {}
		for _, l in log do
			if l.ev == "buy" then
				table.insert(buys, l)
			end
		end
		expect(buys[1].ok).toBe(true)
		expect(buys[2].ok).toBe(false)
		expect(repo:get("u").coins).toBe(15)
	end)

	it("slow learner: no deadline, completing after 10 minutes still pays and the price is unchanged", function()
		local store = Repo.MemoryStore.new()
		local repo = Repo.new({
			store = store,
			jobId = "J",
			now = function()
				return 0
			end,
		})
		repo:load("slow")
		firstSession(repo, "slow", {
			{ 0, "controllable" },
			{ 200, "carton_settled" },
			{ 400, "landed_on_support" },
			{ 600, "exit_reached" },
			{ 900, "kiosk_buy" },
		})
		local p = repo:get("slow")
		expect(p.coins).toBe(15)
		expect(p.ownedTools.radar_pop).toBe(true)
	end)

	it("player may skip the kiosk: no forced purchase, Radar price stays 50", function()
		local store = Repo.MemoryStore.new()
		local repo = Repo.new({
			store = store,
			jobId = "J",
			now = function()
				return 0
			end,
		})
		repo:load("skip")
		firstSession(
			repo,
			"skip",
			{ { 0, "controllable" }, { 2, "carton_settled" }, { 4, "landed_on_support" }, { 8, "exit_reached" }, { 12, "kiosk_continue" } }
		)
		expect(repo:get("skip").coins).toBe(65)
		expect(repo:get("skip").ownedTools.radar_pop).toBe(nil)
		expect(Config.Economy.tools[1].coins).toBe(50)
	end)

	it("no Robux prompt during the tutorial; kiosk has exactly two actions", function()
		expect(Config.Economy.tutorial.robux_prompt_during_tutorial).toBe(false)
		expect(Config.Runtime.paid_shop.tutorial_paid_prompt_enabled).toBe(false)
		expect(#Tutorial.KIOSK_BUTTONS).toBe(2)
	end)

	it("ghost trajectory hint after 5 s of inaction (never moves the avatar)", function()
		local s = Tutorial.newSession()
		Tutorial.record(s, "controllable", 0)
		expect(Tutorial.shouldShowGhostHint(s, 4.9, {})).toBe(false)
		expect(Tutorial.shouldShowGhostHint(s, 5.0, {})).toBe(true)
		Tutorial.record(s, "input", 5.2)
		expect(Tutorial.shouldShowGhostHint(s, 9, {})).toBe(false)
	end)
end)

return true
