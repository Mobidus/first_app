--!strict
-- Owner-scoped cleanup: every connection, instance, thread or callback created for a room is
-- given to that room's Maid and destroyed with it (no callbacks surviving a transition).
local Maid = {}
Maid.__index = Maid

export type Maid = typeof(setmetatable({} :: { _tasks: { any }, _live: number }, Maid))

Maid.globalLive = 0

function Maid.new(): Maid
	return setmetatable({ _tasks = {}, _live = 0 }, Maid)
end

function Maid.give<T>(self: Maid, task: T): T
	table.insert(self._tasks, task)
	self._live += 1
	Maid.globalLive += 1
	return task
end

function Maid.count(self: Maid): number
	return self._live
end

local function cleanup(task: any)
	local kind = typeof(task)
	if kind == "function" then
		task()
	elseif kind == "RBXScriptConnection" then
		task:Disconnect()
	elseif kind == "Instance" then
		task:Destroy()
	elseif kind == "thread" then
		pcall(coroutine.close, task)
	elseif type(task) == "table" then
		if type(task.Disconnect) == "function" then
			task:Disconnect()
		elseif type(task.Destroy) == "function" then
			task:Destroy()
		elseif type(task.destroy) == "function" then
			task:destroy()
		end
	end
end

function Maid.clean(self: Maid)
	local tasks = self._tasks
	self._tasks = {}
	for i = #tasks, 1, -1 do
		cleanup(tasks[i])
	end
	Maid.globalLive -= self._live
	self._live = 0
end

Maid.Destroy = Maid.clean

return Maid
