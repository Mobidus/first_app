--!strict
-- First-session flow (docs/01 "Les trente premières secondes", economy.tutorial).
-- Event driven: there is NO deadline. Times are only recorded (from "controllable") to measure the
-- 10 s comprehension / 30 s first-acquisition UX targets. Rewards are granted once per account
-- through ProfileMutations.GrantTutorial; this module only decides WHICH reward an event earns.

local Config = require(script.Parent.Parent.GeneratedConfig)

local T = Config.Economy.tutorial

local Tutorial = {}

Tutorial.REWARD_IDS = T.reward_ids -- { discovery, first_landing, exit }
Tutorial.FIRST_TOOL = T.first_tool_id
Tutorial.GHOST_HINT_AFTER_IDLE = 5
Tutorial.KIOSK_BUTTONS = { "buy", "continue" } -- no timer, no Robux

export type Session = {
	controllableAt: number?,
	events: { { name: string, t: number } },
	lastInputAt: number,
	hintShown: boolean,
}

function Tutorial.newSession(): Session
	return { controllableAt = nil, events = {}, lastInputAt = 0, hintShown = false }
end

local EVENT_REWARD = {
	carton_settled = T.reward_ids[1],
	landed_on_support = T.reward_ids[2],
	exit_reached = T.reward_ids[3],
}

-- Returns the reward id earned by `event` given the account flags, or nil.
function Tutorial.rewardFor(event: string, flags: { [string]: boolean }): string?
	local id = EVENT_REWARD[event]
	if id and not flags[id] then
		return id
	end
	return nil
end

function Tutorial.isComplete(flags: { [string]: boolean }): boolean
	return flags[T.reward_ids[3]] == true
end

function Tutorial.record(s: Session, name: string, now: number)
	if name == "controllable" and s.controllableAt == nil then
		s.controllableAt = now
	end
	if name == "input" then
		-- called every frame while the player moves: only the timestamp is kept (bounded memory)
		s.lastInputAt = now
		return
	end
	table.insert(s.events, { name = name, t = now })
end

-- Ghost trajectory hint after 5 s of inaction: shows a path, never moves the avatar.
function Tutorial.shouldShowGhostHint(s: Session, now: number, flags): boolean
	if s.controllableAt == nil or Tutorial.isComplete(flags) or s.hintShown then
		return false
	end
	local idleSince = math.max(s.lastInputAt, s.controllableAt :: number)
	return now - idleSince >= Tutorial.GHOST_HINT_AFTER_IDLE
end

-- UX measurement relative to controllable time (nil when the milestone did not happen).
function Tutorial.metrics(s: Session): { [string]: number }
	local out = {}
	if s.controllableAt == nil then
		return out
	end
	for _, e in s.events do
		if out[e.name] == nil then
			out[e.name] = e.t - (s.controllableAt :: number)
		end
	end
	return out
end

return Tutorial
