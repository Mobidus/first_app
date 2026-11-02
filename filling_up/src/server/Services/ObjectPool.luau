--!strict
-- Reusable object pool. Engine-agnostic: the factory and the reset routine are injected
-- (Roblox: clone a template Model; tests: plain tables). Release ALWAYS runs the full reset:
-- connections, velocities, network owner, effects, reward identifiers, tags, anchoring.

local Pool = {}
Pool.__index = Pool

export type Pool = typeof(setmetatable(
	{} :: {
		factory: (kind: string) -> any,
		reset: (obj: any) -> (),
		free: { [string]: { any } },
		inUse: { [any]: string },
		created: number,
		acquired: number,
		released: number,
		maxFreePerKind: number,
		destroy: ((obj: any) -> ())?,
	},
	Pool
))

function Pool.new(
	opts: { factory: (kind: string) -> any, reset: (obj: any) -> (), destroy: ((obj: any) -> ())?, maxFreePerKind: number? }
): Pool
	return setmetatable({
		factory = opts.factory,
		reset = opts.reset,
		destroy = opts.destroy,
		free = {},
		inUse = {},
		created = 0,
		acquired = 0,
		released = 0,
		maxFreePerKind = opts.maxFreePerKind or math.huge,
		maxFreeTotal = opts.maxFreeTotal or 160,
		freeTotal = 0,
	}, Pool)
end

function Pool.acquire(self: Pool, kind: string): any
	local list = self.free[kind]
	local obj
	if list and #list > 0 then
		obj = table.remove(list)
		self.freeTotal -= 1
	else
		obj = self.factory(kind)
		self.created += 1
	end
	self.inUse[obj] = kind
	self.acquired += 1
	return obj
end

function Pool.release(self: Pool, obj: any)
	local kind = self.inUse[obj]
	assert(kind, "releasing an object that is not in use")
	self.inUse[obj] = nil
	self.reset(obj)
	self.released += 1
	local list = self.free[kind]
	if not list then
		list = {}
		self.free[kind] = list
	end
	if #list < self.maxFreePerKind and self.freeTotal < self.maxFreeTotal then
		table.insert(list, obj)
		self.freeTotal += 1
	elseif self.destroy then
		self.destroy(obj)
	end
end

function Pool.inUseCount(self: Pool): number
	local n = 0
	for _ in self.inUse do
		n += 1
	end
	return n
end

function Pool.freeCount(self: Pool): number
	local n = 0
	for _, list in self.free do
		n += #list
	end
	return n
end

-- Release everything still in use (room teardown).
function Pool.releaseAll(self: Pool)
	local all = {}
	for obj in self.inUse do
		table.insert(all, obj)
	end
	for _, obj in all do
		self:release(obj)
	end
end

return Pool
