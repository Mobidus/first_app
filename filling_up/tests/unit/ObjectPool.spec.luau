--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Pool = Loader.require("src/server/Services/ObjectPool")

local function fakeObj(kind)
	return { kind = kind, connections = {}, velocity = 0, owner = nil, effects = {}, rewardId = nil, anchored = false, tags = {} }
end

local function reset(o)
	for _, c in o.connections do
		c.connected = false
	end
	table.clear(o.connections)
	o.velocity = 0
	o.owner = nil
	table.clear(o.effects)
	o.rewardId = nil
	o.anchored = false
	table.clear(o.tags)
end

describe("ObjectPool", function()
	it("reuses objects and fully resets them on release", function()
		local p = Pool.new({ factory = fakeObj, reset = reset })
		local a = p:acquire("carton")
		a.velocity = 50
		a.owner = "player1"
		a.rewardId = "run:1:m1"
		a.anchored = true
		table.insert(a.effects, "dust")
		local conn = { connected = true }
		table.insert(a.connections, conn)
		p:release(a)
		expect(conn.connected).toBe(false)
		local b = p:acquire("carton")
		expect(b).toBe(a)
		expect(b.velocity).toBe(0)
		expect(b.owner).toBe(nil)
		expect(b.rewardId).toBe(nil)
		expect(b.anchored).toBe(false)
		expect(#b.effects).toBe(0)
	end)

	it("100 drop/release cycles of Mallow create a bounded number of objects", function()
		local p = Pool.new({ factory = fakeObj, reset = reset })
		for _ = 1, 100 do
			local m = p:acquire("toy_plush_mallow")
			p:release(m)
		end
		expect(p.created).toBe(1)
		expect(p.acquired).toBe(100)
		expect(p:inUseCount()).toBe(0)
	end)

	it("1000 rooms worth of waves keep the pool bounded", function()
		local destroyed = 0
		local p = Pool.new({
			factory = fakeObj,
			reset = reset,
			destroy = function()
				destroyed += 1
			end,
			maxFreeTotal = 120,
		})
		for _ = 1, 1000 do
			local live = {}
			for i = 1, 40 do
				table.insert(live, p:acquire("k" .. (i % 5)))
			end
			p:releaseAll()
		end
		expect(p:inUseCount()).toBe(0)
		expect(p:freeCount()).toBeAtMost(120)
		expect(p.created).toBeAtMost(40)
	end)

	it("double release is an error (no ghost objects)", function()
		local p = Pool.new({ factory = fakeObj, reset = reset })
		local a = p:acquire("x")
		p:release(a)
		expect(function()
			p:release(a)
		end).toThrow()
	end)
end)

return true
