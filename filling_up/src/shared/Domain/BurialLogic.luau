--!strict
-- Burial confirmation logic (docs/05 §8, runtime.burial). Fed at 10 Hz by BurialService with
-- the results of MULTIPLE probes (5 overhead, 8 lateral) restricted to FillCollider/FillAggregate
-- parts plus an escape-clearance test. One raycast, a Touched event, immobility, elapsed time or
-- a global fill percentage are never enough: they are not even inputs of this module.

local Config = require(script.Parent.Parent.GeneratedConfig)

local B = Config.Runtime.burial
local SAFE = Config.Runtime.safety

local Burial = {}

Burial.SAMPLE_DT = 1 / B.sample_hz
Burial.CONFIRM = B.confirmation_seconds
Burial.RELEASE = B.release_hysteresis_seconds

export type Sample = {
	overheadProbes: number,
	overheadHits: number,
	lateralProbes: number,
	lateralHits: number,
	escapeAvailable: boolean?, -- result of the gabarit-compatible clearance test; nil = not run
	inKillVolume: boolean,
	roomActive: boolean,
	secondsSinceSpawn: number,
}

export type Tracker = { blockedFor: number, freeFor: number, warning: boolean, done: boolean }

function Burial.new(): Tracker
	return { blockedFor = 0, freeFor = 0, warning = false, done = false }
end

function Burial.isBlocked(s: Sample): boolean
	assert(
		s.overheadProbes == B.overhead_probe_count and s.lateralProbes == B.lateral_probe_count,
		"probe set does not match runtime.burial"
	)
	if s.escapeAvailable == nil then
		return false -- clearance test is mandatory to confirm (requires_escape_clearance_test)
	end
	return s.overheadHits >= B.min_overhead_hits and s.lateralHits >= B.min_lateral_hits and s.escapeAvailable == false
end

-- Advances the tracker by dt seconds. Returns nil or one of:
--   "warning_on" | "warning_off" | "ko_burial" | "ko_kill_volume"
function Burial.step(t: Tracker, s: Sample, dt: number): string?
	if t.done or not s.roomActive then
		return nil
	end
	if s.inKillVolume then
		t.done = true
		return "ko_kill_volume"
	end
	local grace = s.secondsSinceSpawn < SAFE.spawn_invulnerability_seconds
	if Burial.isBlocked(s) then
		t.blockedFor += dt
		t.freeFor = 0
		if not t.warning then
			t.warning = true
			return "warning_on"
		end
		if t.blockedFor >= Burial.CONFIRM - 1e-9 and not grace then
			t.done = true
			return "ko_burial"
		end
		return nil
	end
	t.freeFor += dt
	if t.freeFor >= Burial.RELEASE - 1e-9 then
		t.blockedFor = 0
		if t.warning then
			t.warning = false
			return "warning_off"
		end
	end
	return nil
end

return Burial
