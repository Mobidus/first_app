--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local R = Loader.require("src/shared/Domain/RoomResidency")
local Maid = Loader.require("src/shared/Util/Maid")

describe("RoomResidency & owner-scoped cleanup", function()
	it("1000 transitions: <= 3 resident modules, one simulating room, previous released", function()
		local r = R.new()
		R.activate(r, "room-1")
		for i = 1, 1000 do
			R.preloadNext(r, "room-" .. (i + 1))
			R.enterSas(r, "sas")
			expect(r.simulating).toBe(nil) -- no waves while in the sas
			local released = R.commit(r)
			expect(released).toBe("room-" .. i)
			expect(r.simulating).toBe("room-" .. (i + 1))
			expect(R.count(r)).toBe(1)
		end
		expect(r.peak).toBe(3)
		expect(#r.released).toBeAtMost(8)
	end)

	it("next room not ready => commit refused, player stays in the safe sas (no KO path)", function()
		local r = R.new()
		R.activate(r, "a")
		R.enterSas(r, "sas")
		expect(function()
			R.commit(r)
		end).toThrow()
		expect(r.sas).toBe("sas")
	end)

	it("two fixed cells are recycled: coordinates never drift away", function()
		local r = R.new()
		R.activate(r, "room-1")
		local cells = {}
		for i = 1, 50 do
			R.preloadNext(r, "room-" .. (i + 1))
			cells[r.cells["room-" .. (i + 1)]] = true
			R.enterSas(r, "sas")
			R.commit(r)
		end
		local n = 0
		for _ in cells do
			n += 1
		end
		expect(n).toBe(2)
	end)

	it("room maids clean every connection: global live count returns to baseline", function()
		local base = Maid.globalLive
		for _ = 1, 100 do
			local m = Maid.new()
			for _ = 1, 25 do
				local c = { connected = true }
				function c.Disconnect(self)
					self.connected = false
				end
				m:give(c)
			end
			m:give(function() end)
			m:clean()
		end
		expect(Maid.globalLive).toBe(base)
	end)
end)

return true
