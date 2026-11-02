--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local serde = require("@lune/serde")
local fs = require("@lune/fs")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Config = Loader.require("src/shared/GeneratedConfig")

describe("Generated config", function()
	it("matches the canonical JSON values (no manual duplication)", function()
		local econ = serde.decode("json", fs.readFile("config/economy.json"))
		expect(Config.Economy.tools[1].coins).toBe(econ.tools[1].coins)
		expect(#Config.Economy.cosmetics).toBe(#econ.cosmetics)
		expect(Config.Economy.rebirth.base_cost).toBe(econ.rebirth.base_cost)
	end)

	it("canonical invariants: no room timer, no room cap, no fill KO", function()
		expect(Config.Runtime.room_time_limit_seconds).toBe(nil)
		expect(Config.Runtime.max_rooms_per_run).toBe(nil)
		expect(Config.Runtime.fill_percentage_causes_ko).toBe(false)
		expect(Config.Runtime.paid_shop.automatic_prompts_enabled).toBe(false)
		expect(Config.Runtime.safety.paid_revive_enabled).toBe(false)
	end)

	it("game code never hard-codes a coin price", function()
		local function walk(dir, out)
			for _, name in fs.readDir(dir) do
				local p = dir .. "/" .. name
				if fs.isDir(p) then
					if name ~= "GeneratedConfig" then
						walk(p, out)
					end
				elseif string.match(name, "%.luau$") then
					table.insert(out, p)
				end
			end
			return out
		end
		for _, f in walk("src", {}) do
			local src = string.gsub(fs.readFile(f), "%-%-[^\n]*", "")
			for _, price in { "= 650", "= 1100", "= 1800", "= 2600" } do
				expect(string.find(src, price, 1, true) == nil).toBe(true)
			end
		end
	end)

	it("config version is a stable content hash", function()
		expect(#Config.configVersion).toBe(16)
	end)
end)

return true
