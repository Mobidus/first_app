--!strict
-- Checkpoints between rooms and resume rules (docs/05 §9, runtime.profile).
-- Resume = same seed, same depth, same config version, room reward mask preserved; the room
-- instance id is derived from runId+depth, so tool charges are NOT refilled by reconnecting.

local Config = require(script.Parent.Parent.GeneratedConfig)

local Checkpoint = {}

function Checkpoint.roomInstanceId(runId: string, depth: number): string
	return runId .. ":" .. tostring(depth)
end

function Checkpoint.fromExpedition(exp, extra: { rateBasisPoints: number, paidBaseCumulative: number, charges: { [string]: number }? }): any
	return {
		runId = exp.runId,
		seed = exp.seed,
		configVersion = exp.configVersion,
		depth = exp.depth,
		roomRewardMask = exp.roomRewardMask,
		lastCommittedDepth = exp.lastCommittedDepth,
		checkpointRevision = exp.checkpointRevision + 1,
		roomInstanceId = Checkpoint.roomInstanceId(exp.runId, exp.depth),
		chargesSnapshot = extra.charges,
		rateBasisPoints = extra.rateBasisPoints,
		paidBaseCumulative = extra.paidBaseCumulative,
	}
end

export type ResumePlan = { mode: "resume" | "extracted" | "none", reason: string?, params: any? }

-- Decide how to resume a stored checkpoint with the running server's config version.
function Checkpoint.plan(cp: any?, currentConfigVersion: string?): ResumePlan
	if cp == nil then
		return { mode = "none" }
	end
	local version = currentConfigVersion or Config.configVersion
	if cp.configVersion ~= version then
		-- incompatible rules: goods are kept (they live in the profile), the run is closed and the
		-- player is told why; no record is fabricated under different rules.
		return { mode = "extracted", reason = "config_version_changed" }
	end
	return {
		mode = "resume",
		params = {
			runId = cp.runId,
			seed = cp.seed,
			depth = cp.depth,
			roomRewardMask = cp.roomRewardMask,
			lastCommittedDepth = cp.lastCommittedDepth,
			checkpointRevision = cp.checkpointRevision,
			resumed = true,
			configVersion = cp.configVersion,
			rateBasisPoints = cp.rateBasisPoints,
			paidBaseCumulative = cp.paidBaseCumulative,
			roomInstanceId = cp.roomInstanceId,
			chargesSnapshot = cp.chargesSnapshot,
		},
	}
end

return Checkpoint
