--!strict
-- Hybrid physics budget planner (docs/05 §7). Keeps <= 40 dynamic bodies and <= 120 static fill
-- colliders in the active room WITHOUT ever removing an occupied, route-critical or accessible
-- support: settled bodies are anchored; only inaccessible buried statics are merged/recycled;
-- if nothing safe can be reclaimed, new drops are deferred (spawn allowance 0) instead.

local Config = require(script.Parent.Parent.GeneratedConfig)

local S = Config.Runtime.streaming

local C = {}

C.MAX_DYNAMIC = S.max_dynamic_objects
C.MAX_STATIC = S.max_static_fill_colliders
C.SETTLE_SECONDS = 0.75

export type Obj = {
	id: string,
	dynamic: boolean,
	settledFor: number, -- seconds with negligible velocity
	occupied: boolean, -- a player stands on / touches it
	routeSupport: boolean, -- guaranteed route node or protected
	buried: boolean, -- covered on top and sides: not reachable
	age: number,
}

export type Plan = { anchor: { string }, merge: { string }, recycle: { string }, spawnAllowance: number }

function C.plan(objects: { Obj }): Plan
	local dyn, stat = {}, {}
	for _, o in objects do
		if o.dynamic then
			table.insert(dyn, o)
		else
			table.insert(stat, o)
		end
	end
	local anchor, merge, recycle = {}, {}, {}
	-- 1. anchor settled dynamic bodies (oldest first) until within budget; occupied ones wait
	table.sort(dyn, function(a, b)
		return a.age > b.age
	end)
	local dynCount = #dyn
	for _, o in dyn do
		if dynCount <= C.MAX_DYNAMIC - 1 then
			break
		end
		if o.settledFor >= C.SETTLE_SECONDS and not o.occupied then
			table.insert(anchor, o.id)
			dynCount -= 1
		end
	end
	-- anchoring always applies to long-settled bodies too (stabilized supports never roll again)
	for _, o in dyn do
		if o.settledFor >= C.SETTLE_SECONDS * 4 and not o.occupied and not table.find(anchor, o.id) then
			table.insert(anchor, o.id)
			dynCount -= 1
		end
	end
	local statCount = #stat + #anchor
	-- 2. static budget: merge buried, never occupied / route / accessible
	if statCount > C.MAX_STATIC then
		table.sort(stat, function(a, b)
			return a.age > b.age
		end)
		local over = statCount - C.MAX_STATIC
		local buriedIds = {}
		for _, o in stat do
			if o.buried and not o.occupied and not o.routeSupport then
				table.insert(buriedIds, o.id)
			end
		end
		-- merging k buried colliders into one aggregate saves k-1 colliders
		local k = math.min(#buriedIds, over + 1)
		if k >= 2 then
			for i = 1, k do
				table.insert(merge, buriedIds[i])
			end
			statCount -= (k - 1)
		end
		local i = k + 1
		while statCount > C.MAX_STATIC and i <= #buriedIds do
			table.insert(recycle, buriedIds[i])
			statCount -= 1
			i += 1
		end
	end
	local allowance = math.max(0, C.MAX_DYNAMIC - dynCount)
	if statCount >= C.MAX_STATIC then
		allowance = 0 -- defer drops: never delete an accessible support to make room
	end
	return { anchor = anchor, merge = merge, recycle = recycle, spawnAllowance = allowance }
end

return C
