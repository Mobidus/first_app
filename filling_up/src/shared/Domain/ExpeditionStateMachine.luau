--!strict
-- Pure expedition state machine (docs/05 §4). No engine service, no clock, no fill percentage.
-- Every transition returns a NEW state table; illegal transitions are rejected with a code.
--
-- KO is accepted only for causes listed in config runtime.ko_causes. There is deliberately no
-- event carrying elapsed time or fill percentage: a KO can never be derived from them here.

local Types = require(script.Parent.Parent.Types)
local Config = require(script.Parent.Parent.GeneratedConfig)

type State = Types.ExpeditionState

local Machine = {}

local ALLOWED_KO: { [string]: boolean } = {}
for _, cause in Config.Runtime.ko_causes do
	ALLOWED_KO[cause] = true
end

local TRANSITIONS: { [string]: { [string]: boolean } } = {
	Preparing = { Active = true },
	Active = { Transitioning = true, KO = true, Suspended = true },
	Transitioning = { Active = true, Suspended = true, Extracted = true },
	Suspended = { Preparing = true },
	KO = {},
	Extracted = {},
}
Machine.TRANSITIONS = TRANSITIONS

local function copy(state: State): State
	local s = table.clone(state)
	s.equippedLoadoutSnapshot = table.clone(state.equippedLoadoutSnapshot)
	return s
end

function Machine.create(params: {
	runId: string,
	seed: number,
	controllerProfileId: string?,
	loadout: Types.EquippedLoadout?,
	depth: number?,
	roomRewardMask: number?,
	lastCommittedDepth: number?,
	checkpointRevision: number?,
	resumed: boolean?,
	configVersion: string?,
}): State
	assert(type(params.runId) == "string" and #params.runId > 0, "runId required")
	local depth = params.depth or 1
	assert(depth >= 1 and depth % 1 == 0, "depth must be a positive integer")
	return {
		runId = params.runId,
		seed = params.seed,
		configVersion = params.configVersion or Config.configVersion,
		controllerProfileId = params.controllerProfileId or "R15_normalized_gameplay_body",
		depth = depth,
		state = "Preparing",
		roomId = "",
		waveIndex = 0,
		roomRewardMask = params.roomRewardMask or 0,
		lastCommittedDepth = params.lastCommittedDepth or (depth - 1),
		equippedLoadoutSnapshot = params.loadout and table.clone(params.loadout) or {},
		checkpointRevision = params.checkpointRevision or 0,
		koCause = nil,
		transitionsCommitted = 0,
		resumed = params.resumed == true,
	}
end

export type Event =
	{ type: "RoomReady", roomId: string }
	| { type: "ExitReached", roomId: string, depth: number }
	| { type: "NextRoomActive", roomId: string }
	| { type: "KOConfirmed", cause: string }
	| { type: "Suspend", checkpointRevision: number? }
	| { type: "Resume" }
	| { type: "Extract", inSas: boolean }
	| { type: "WaveAdvanced", waveIndex: number }

local function reject(code: string): (boolean, any)
	return false, code
end

function Machine.can(from: string, to: string): boolean
	local row = TRANSITIONS[from]
	return row ~= nil and row[to] == true
end

-- Returns (true, newState) or (false, errorCode). The input state is never mutated.
function Machine.apply(state: State, event: Event): (boolean, any)
	local kind = event.type
	if kind == "RoomReady" then
		if state.state ~= "Preparing" then
			return reject("illegal_transition")
		end
		local s = copy(state)
		s.state = "Active"
		s.roomId = (event :: any).roomId
		s.waveIndex = 0
		return true, s
	elseif kind == "WaveAdvanced" then
		if state.state ~= "Active" then
			return reject("not_active")
		end
		local idx = (event :: any).waveIndex
		if type(idx) ~= "number" or idx <= state.waveIndex then
			return reject("non_monotonic_wave")
		end
		local s = copy(state)
		s.waveIndex = idx
		return true, s
	elseif kind == "ExitReached" then
		local e = event :: any
		-- a second contact / repeated request is rejected: depth increments exactly once
		if state.state ~= "Active" then
			return reject(state.state == "Transitioning" and "duplicate_exit" or "illegal_transition")
		end
		if e.roomId ~= state.roomId or e.depth ~= state.depth then
			return reject("stale_exit")
		end
		if state.depth <= state.lastCommittedDepth then
			return reject("already_committed")
		end
		local s = copy(state)
		s.state = "Transitioning"
		s.lastCommittedDepth = state.depth
		s.depth = state.depth + 1
		s.transitionsCommitted += 1
		return true, s
	elseif kind == "NextRoomActive" then
		if state.state ~= "Transitioning" then
			return reject("illegal_transition")
		end
		local s = copy(state)
		s.state = "Active"
		s.roomId = (event :: any).roomId
		s.waveIndex = 0
		s.roomRewardMask = 0 -- new room instance: fresh milestones
		return true, s
	elseif kind == "KOConfirmed" then
		local cause = (event :: any).cause
		if not ALLOWED_KO[cause] then
			return reject("ko_cause_not_allowed")
		end
		if state.state ~= "Active" then
			-- the sas (Transitioning) has no hazard; KO there is impossible by contract
			return reject("ko_outside_active_room")
		end
		local s = copy(state)
		s.state = "KO"
		s.koCause = cause
		return true, s
	elseif kind == "Suspend" then
		if not (state.state == "Active" or state.state == "Transitioning") then
			return reject("illegal_transition")
		end
		local s = copy(state)
		s.state = "Suspended"
		s.checkpointRevision = (event :: any).checkpointRevision or state.checkpointRevision
		return true, s
	elseif kind == "Resume" then
		if state.state ~= "Suspended" then
			return reject("illegal_transition")
		end
		local s = copy(state)
		s.state = "Preparing"
		s.resumed = true
		return true, s
	elseif kind == "Extract" then
		if state.state ~= "Transitioning" or (event :: any).inSas ~= true then
			return reject("extract_only_in_sas")
		end
		local s = copy(state)
		s.state = "Extracted"
		return true, s
	end
	return reject("unknown_event")
end

function Machine.isTerminal(state: State): boolean
	return state.state == "KO" or state.state == "Extracted"
end

return Machine
