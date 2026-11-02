--!nocheck
-- Logic-level burial fixtures. The geometric probe results below stand for the Studio scenes of
-- tests/studio/BurialFixtures; this suite proves the DECISION rules, not engine physics.
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local fs = require("@lune/fs")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Burial = Loader.require("src/shared/Domain/BurialLogic")

local function sample(over, lat, escape, extra)
	local s = {
		overheadProbes = 5,
		overheadHits = over,
		lateralProbes = 8,
		lateralHits = lat,
		escapeAvailable = escape,
		inKillVolume = false,
		roomActive = true,
		secondsSinceSpawn = 100,
	}
	for k, v in extra or {} do
		s[k] = v
	end
	return s
end

local function run(seconds, sampleFn)
	local t = Burial.new()
	local events = {}
	local steps = math.floor(seconds / Burial.SAMPLE_DT + 0.5)
	for i = 1, steps do
		local ev = Burial.step(t, sampleFn(i * Burial.SAMPLE_DT), Burial.SAMPLE_DT)
		if ev then
			table.insert(events, { ev = ev, t = i * Burial.SAMPLE_DT })
		end
	end
	return events, t
end

local function koTime(events)
	for _, e in events do
		if string.sub(e.ev, 1, 3) == "ko_" then
			return e.t, e.ev
		end
	end
	return nil
end

describe("BurialLogic", function()
	it("samples at 10 Hz and confirms a true burial after 1.2 s", function()
		expect(Burial.SAMPLE_DT).toBeNear(0.1, 1e-12)
		local events = run(3, function()
			return sample(5, 8, false)
		end)
		local t, ev = koTime(events)
		expect(ev).toBe("ko_burial")
		expect(t).toBeNear(1.2, 1e-6)
	end)

	it("open table (roof hits, sides open) never kills, even standing still for minutes", function()
		local events = run(300, function()
			return sample(5, 2, true)
		end)
		expect(koTime(events)).toBe(nil)
	end)

	it("an object passing overhead (transient) does not kill", function()
		local events = run(10, function(t)
			local passing = t > 2 and t < 2.9
			return sample(passing and 5 or 0, passing and 7 or 1, not passing)
		end)
		expect(koTime(events)).toBe(nil)
	end)

	it("surrounded but an escape gap exists: no KO", function()
		local events = run(10, function()
			return sample(5, 8, true)
		end)
		expect(koTime(events)).toBe(nil)
	end)

	it("a single overhead raycast is never sufficient", function()
		local events = run(10, function()
			return sample(1, 8, false)
		end)
		expect(koTime(events)).toBe(nil)
	end)

	it("clearance test not run => cannot confirm", function()
		local events = run(10, function()
			return sample(5, 8, nil)
		end)
		expect(koTime(events)).toBe(nil)
	end)

	it("release hysteresis: a 0.1 s flicker does not reset, a 0.2 s release does", function()
		local flicker = run(3, function(t)
			local free = t > 0.55 and t < 0.65
			return sample(5, 8, free)
		end)
		local tk = koTime(flicker)
		expect(tk ~= nil).toBe(true)
		local released = run(3, function(t)
			local free = t > 0.55 and t < 0.85
			return sample(5, 8, free)
		end)
		local tr = koTime(released)
		expect(tr ~= nil and tr > tk).toBe(true)
	end)

	it("exit / sas: not active => no KO", function()
		local events = run(5, function()
			return sample(5, 8, false, { roomActive = false })
		end)
		expect(koTime(events)).toBe(nil)
	end)

	it("spawn invulnerability delays (but does not cancel) confirmation", function()
		local events = run(6, function(t)
			return sample(5, 8, false, { secondsSinceSpawn = t })
		end)
		local t = koTime(events)
		expect(t >= 3 - 1e-6).toBe(true)
	end)

	it("marked kill volume is the only other KO cause", function()
		local events = run(1, function()
			return sample(0, 0, true, { inKillVolume = true })
		end)
		local _, ev = koTime(events)
		expect(ev).toBe("ko_kill_volume")
	end)

	it("module has no fill-percentage / room-timer inputs", function()
		local src = string.gsub(fs.readFile("src/shared/Domain/BurialLogic.luau"), "%-%-[^\n]*", "")
		for _, w in { "fill", "elapsed", "roomTime", "timeout", "Touched" } do
			expect(string.find(src, w) == nil).toBe(true)
		end
	end)
end)

return true
