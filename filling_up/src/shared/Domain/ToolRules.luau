--!strict
-- Server-side tool validation (docs/03 §4, docs/05 §5). The client only sends an intent; every
-- check below uses server-known state: possession, equipment slot, charges, cooldown measured in
-- active simulation seconds, range, target eligibility and room state. A refused use never
-- consumes a charge. Charges refill for free when a NEW room instance starts; reloading the same
-- room instance (reconnect) keeps the charge snapshot.

local Config = require(script.Parent.Parent.GeneratedConfig)
local Economy = require(script.Parent.Economy)

local Tools = {}

export type ToolState = {
	roomInstanceId: string,
	charges: { [string]: number },
	cooldownUntil: { [string]: number },
	activeUntil: { [string]: number },
	balise: { x: number, y: number, z: number }?,
	baliseUsed: boolean,
}

function Tools.newState(): ToolState
	return { roomInstanceId = "", charges = {}, cooldownUntil = {}, activeUntil = {}, balise = nil, baliseUsed = false }
end

-- Refill for a new room instance; same instance (reconnect) => unchanged.
function Tools.enterRoom(state: ToolState, profile, roomInstanceId: string, snapshot: { [string]: number }?): ToolState
	if state.roomInstanceId == roomInstanceId then
		return state
	end
	local s = Tools.newState()
	s.roomInstanceId = roomInstanceId
	for toolId in profile.ownedTools do
		local stats = Economy.toolStats(toolId, profile.toolRanks[toolId] or 1)
		s.charges[toolId] = stats.charges_per_room
	end
	if snapshot then
		for toolId, c in snapshot do
			if s.charges[toolId] ~= nil then
				s.charges[toolId] = math.min(s.charges[toolId], c)
			end
		end
	end
	return s
end

export type UseContext = {
	profile: any,
	roomState: string, -- ExpeditionStateMachine phase
	inSas: boolean,
	now: number, -- active simulation seconds
	player: { x: number, y: number, z: number, vy: number, grounded: boolean },
	target: any?, -- server-resolved target or nil
}

local function dist(a, b): number
	local dx, dy, dz = a.x - b.x, a.y - b.y, a.z - b.z
	return math.sqrt(dx * dx + dy * dy + dz * dz)
end

-- Returns (true, effect) or (false, reason). Does not mutate state; call Tools.commit on success.
function Tools.check(state: ToolState, toolId: string, ctx: UseContext): (boolean, any)
	local tool = Economy.tool(toolId)
	if not tool then
		return false, "unknown_tool"
	end
	local p = ctx.profile
	if not p.ownedTools[toolId] then
		return false, "not_owned"
	end
	if tool.slot ~= "active" then
		return false, "passive_tool"
	end
	if p.equippedLoadout.active ~= toolId then
		return false, "not_equipped"
	end
	if ctx.roomState ~= "Active" or ctx.inSas then
		return false, "not_in_active_room"
	end
	if not Economy.IMPLEMENTED_TOOLS[toolId] then
		return false, "unavailable"
	end
	local rank = p.toolRanks[toolId] or 1
	local stats = Economy.toolStats(toolId, rank)
	if (state.charges[toolId] or 0) <= 0 then
		return false, "no_charges"
	end
	if ctx.now < (state.cooldownUntil[toolId] or -math.huge) then
		return false, "cooldown"
	end
	local effect = { toolId = toolId, rank = rank, duration = stats.duration_seconds, stats = stats }
	if toolId == "radar_pop" then
		effect.kind = "highlight"
	elseif toolId == "ventouse_chantier" then
		local t = ctx.target
		if not t then
			return false, "no_target"
		end
		if not t.stabilizable or t.structural or t.isExit or t.protectedRoute then
			return false, "invalid_target"
		end
		if (t.sizeClass or 99) > stats.max_target_size_class then
			return false, "target_too_large"
		end
		if t.buried then
			return false, "target_covered"
		end
		if dist(ctx.player, t) > stats.range_studs then
			return false, "out_of_range"
		end
		effect.kind = "stabilize"
		effect.targetId = t.id
	elseif toolId == "parapluie_bonbon" then
		if ctx.player.grounded or ctx.player.vy >= -1 then
			return false, "not_descending"
		end
		effect.kind = "glide"
		effect.descentMultiplier = stats.descent_speed_multiplier
	else
		return false, "unavailable"
	end
	return true, effect
end

function Tools.commit(state: ToolState, effect, now: number): ToolState
	local s = table.clone(state)
	s.charges = table.clone(state.charges)
	s.cooldownUntil = table.clone(state.cooldownUntil)
	s.activeUntil = table.clone(state.activeUntil)
	s.charges[effect.toolId] -= 1
	s.cooldownUntil[effect.toolId] = now + effect.stats.cooldown_seconds
	s.activeUntil[effect.toolId] = now + effect.duration
	return s
end

-- Radar: up to max_targets usable surfaces within range, nearest first. Usable = settled,
-- anchored, head clearance free, not buried. Information only: it never moves the avatar.
function Tools.radarTargets(player, candidates: { any }, stats): { any }
	local list = {}
	for _, c in candidates do
		if c.usable and not c.buried then
			local dd = dist(player, c)
			if dd <= stats.range_studs then
				table.insert(list, { id = c.id, d = dd })
			end
		end
	end
	table.sort(list, function(a, b)
		return a.d < b.d or (a.d == b.d and a.id < b.id)
	end)
	local out = {}
	for i = 1, math.min(stats.max_targets, #list) do
		table.insert(out, list[i].id)
	end
	return out
end

-- Magnet (passive): tokens within range that exist and are unclaimed. It never creates tokens.
function Tools.magnetPull(profile, player, tokens: { any }, claimedMask: number, tokenBit0: number): { number }
	if profile.equippedLoadout.passive ~= "aimant_poche" or not profile.ownedTools.aimant_poche then
		return {}
	end
	local stats = Economy.toolStats("aimant_poche", profile.toolRanks.aimant_poche or 1)
	local out = {}
	for _, t in tokens do
		local claimed = bit32.band(claimedMask, bit32.lshift(1, tokenBit0 + t.id - 1)) ~= 0
		if not claimed and dist(player, t) <= stats.range_studs and #out < stats.max_tokens_per_room then
			table.insert(out, t.id)
		end
	end
	return out
end

-- Equipment limits from config: 1 active + 1 passive + 1 companion (cosmetic, no power).
function Tools.loadoutPowers(profile): number
	local n = 0
	for _, slot in { "active", "passive" } do
		if profile.equippedLoadout[slot] then
			n += 1
		end
	end
	return n
end
Tools.MAX_POWERS = Config.Economy.equipment_limits.active + Config.Economy.equipment_limits.passive

return Tools
