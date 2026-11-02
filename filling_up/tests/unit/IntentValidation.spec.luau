--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Intent = Loader.require("src/shared/Domain/IntentValidation")

describe("IntentValidation", function()
	it("accepts a well-formed coin purchase intent without any price field", function()
		local ok, v = Intent.validate("RequestCoinPurchase", { "radar_pop", "req-1" })
		expect(ok).toBe(true)
		expect(v.skuId).toBe("radar_pop")
	end)
	it("rejects extra arguments such as a client price or amount", function()
		expect((Intent.validate("RequestCoinPurchase", { "radar_pop", "req-1", 0 }))).toBe(false)
		expect((Intent.validate("RequestCoinPurchase", { "radar_pop", "req-1", price = 0 }))).toBe(false)
	end)
	it("rejects unknown intents (no 'AddCoins' or 'RoomCompleted')", function()
		expect((Intent.validate("AddCoins", { 500 }))).toBe(false)
		expect((Intent.validate("RoomCompleted", { 3 }))).toBe(false)
	end)
	it("bounds ids: type, length and charset", function()
		expect((Intent.validate("RequestSaveExit", { string.rep("a", 65) }))).toBe(false)
		expect((Intent.validate("RequestSaveExit", { "bad id with spaces" }))).toBe(false)
		expect((Intent.validate("RequestSaveExit", { 12 }))).toBe(false)
		expect((Intent.validate("RequestSaveExit", { "ok-1" }))).toBe(true)
	end)
	it("rebirth intent needs integer quantity, revision, server token and request id", function()
		expect((Intent.validate("RequestRebirth", { 2, 10, "tok", "r1" }))).toBe(true)
		expect((Intent.validate("RequestRebirth", { 2.5, 10, "tok", "r1" }))).toBe(false)
		expect((Intent.validate("RequestRebirth", { 0, 10, "tok", "r1" }))).toBe(false)
		expect((Intent.validate("RequestRebirth", { 2, -1, "tok", "r1" }))).toBe(false)
		expect((Intent.validate("RequestRebirth", { 0 / 0, 10, "tok", "r1" }))).toBe(false)
		expect((Intent.validate("RequestRebirth", { 2, 10, "tok" }))).toBe(false)
	end)
	it("tool use requires a known tool id", function()
		expect((Intent.validate("RequestToolUse", { "radar_pop", "", "r1" }))).toBe(true)
		expect((Intent.validate("RequestToolUse", { "laser_god", "", "r1" }))).toBe(false)
	end)
	it("equip validates slot names and item ids", function()
		expect((Intent.validate("RequestEquip", { "radar_pop", "active", "r" }))).toBe(true)
		expect((Intent.validate("RequestEquip", { "radar_pop", "third_power", "r" }))).toBe(false)
		expect((Intent.validate("RequestEquip", { "", "active", "r" }))).toBe(true) -- unequip
	end)
	it("rate limiter caps bursts and refills over time", function()
		local lim = Intent.newLimiter(3, 1)
		local allowed = 0
		for _ = 1, 10 do
			if Intent.allow(lim, "p1:buy", 0) then
				allowed += 1
			end
		end
		expect(allowed).toBe(3)
		expect(Intent.allow(lim, "p1:buy", 1.01)).toBe(true)
		expect(Intent.allow(lim, "p2:buy", 0)).toBe(true)
	end)
end)

return true
