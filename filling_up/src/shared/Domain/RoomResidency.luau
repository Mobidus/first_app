--!strict
-- Resident room modules bookkeeping (docs/05 §10): at most 3 modules (active room, preloaded
-- next room, transition sas). Only the active room simulates waves. The previous room is released
-- as soon as the transition is committed. Coordinates are recycled from fixed local cells.

local Config = require(script.Parent.Parent.GeneratedConfig)

local MAX = Config.Runtime.streaming.max_resident_room_modules

local R = {}

export type Residency = {
	sas: string?,
	active: string?,
	next: string?,
	simulating: string?,
	released: { string },
	peak: number,
	cells: { [string]: number },
}

function R.new(): Residency
	return { sas = nil, active = nil, next = nil, simulating = nil, released = {}, peak = 0, cells = {} }
end

local function count(r: Residency): number
	local n = 0
	for _, v in { r.sas, r.active, r.next } do
		if v then
			n += 1
		end
	end
	return n
end
R.count = count

local function bump(r: Residency)
	r.peak = math.max(r.peak, count(r))
	assert(count(r) <= MAX, "resident module budget exceeded")
end

-- Two fixed cells alternate for rooms; the sas has its own cell.
local function freeCell(r: Residency): number
	local used = {}
	for _, cell in r.cells do
		used[cell] = true
	end
	return if used[1] then 2 else 1
end

function R.activate(r: Residency, roomId: string)
	assert(r.active == nil, "a room is already active")
	r.active = roomId
	r.cells[roomId] = r.cells[roomId] or freeCell(r)
	r.simulating = roomId
	bump(r)
end

function R.preloadNext(r: Residency, roomId: string): boolean
	if r.next ~= nil then
		return false
	end
	r.next = roomId
	r.cells[roomId] = freeCell(r)
	bump(r)
	return true
end

-- Player reached the exit: waves of the old room stop, the player stands in the sas.
function R.enterSas(r: Residency, sasId: string)
	r.sas = sasId
	r.simulating = nil
	bump(r)
end

-- Commit: release the previous active room, the preloaded room becomes active, sas released
-- once the player stepped in. Returns the released room id.
function R.commit(r: Residency): string?
	assert(r.next ~= nil, "next room not ready: player stays in the safe sas")
	local old = r.active
	if old then
		table.insert(r.released, old)
		r.cells[old] = nil
		if #r.released > 8 then
			table.remove(r.released, 1)
		end
	end
	r.active = r.next
	r.next = nil
	r.sas = nil
	r.simulating = r.active
	return old
end

return R
