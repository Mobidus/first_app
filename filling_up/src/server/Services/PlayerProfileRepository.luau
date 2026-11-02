--!strict
-- Profile repository: load + session lock + migrations + SERIALIZED atomic mutations.
-- Storage is injected (DataStoreAdapter in Roblox, MemoryStore in offline tests) so the logic is
-- testable without the engine. A mutation is committed in memory only after the durable write
-- succeeded; a failed write is reported as failure ("save_failed") and never as "Sauvegardé".
--
-- Store contract:  store.update(key, transform: (old: any?) -> any?) -> (ok: boolean, result: any)
--   transform returns the new value, or nil to cancel (result is then the old value).

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Mut = require(Shared.Domain.ProfileMutations)

local Repository = {}
Repository.__index = Repository

export type Store = { update: (self: any, key: string, transform: (any?) -> any?) -> (boolean, any) }

type Session = {
	userKey: string,
	profile: any,
	queue: { { mutation: any, ctx: any?, done: (boolean, any, any) -> () } },
	busy: boolean,
	released: boolean,
	failures: number,
}

function Repository.new(opts: { store: any, jobId: string, now: () -> number, lockTimeoutSeconds: number? })
	local self = setmetatable({}, Repository)
	self.store = opts.store
	self.jobId = opts.jobId
	self.now = opts.now
	self.lockTimeout = opts.lockTimeoutSeconds or 1800
	self.sessions = {} :: { [string]: Session }
	return self
end

local function keyFor(userKey: string): string
	return "profile_" .. userKey
end

-- Returns (true, profile, notes) or (false, reason). Refuses a profile locked by another live
-- session (no simultaneous ownership of the same profile).
function Repository.load(self, userKey: string): (boolean, any, any)
	if self.sessions[userKey] then
		return false, "already_loaded", nil
	end
	local notes = {}
	local lockedBy: string? = nil
	local ok, result = self.store:update(keyFor(userKey), function(old)
		local doc = old or { profile = nil, lock = nil }
		if doc.lock and doc.lock.jobId ~= self.jobId and (self.now() - doc.lock.time) < self.lockTimeout then
			lockedBy = doc.lock.jobId
			return nil
		end
		local migrated, migrationNotes = Mut.migrate(doc.profile)
		notes = migrationNotes
		return { profile = migrated, lock = { jobId = self.jobId, time = self.now() } }
	end)
	if not ok then
		return false, "store_unavailable", nil
	end
	if lockedBy then
		return false, "session_locked", nil
	end
	local valid, why = Mut.validate(result.profile)
	if not valid then
		return false, "corrupt_profile:" .. tostring(why), nil
	end
	self.sessions[userKey] = {
		userKey = userKey,
		profile = result.profile,
		queue = {},
		busy = false,
		released = false,
		failures = 0,
	}
	return true, Mut.deepCopy(result.profile), notes
end

-- Read-only snapshot (copy) of the committed profile.
function Repository.get(self, userKey: string): any?
	local s = self.sessions[userKey]
	return s and Mut.deepCopy(s.profile)
end

function Repository._commit(self, s: Session, mutation: any, ctx: any?): (boolean, any, any)
	if s.released then
		return false, "session_released", nil
	end
	local ok, newProfile, info = Mut.apply(s.profile, mutation, ctx)
	if not ok then
		return false, newProfile, nil -- domain refusal: nothing written
	end
	local expectedRevision = s.profile.revision
	local conflict = false
	local wrote, result = self.store:update(keyFor(s.userKey), function(old)
		if old == nil or old.lock == nil or old.lock.jobId ~= self.jobId or old.profile.revision ~= expectedRevision then
			conflict = true
			return nil
		end
		return { profile = newProfile, lock = { jobId = self.jobId, time = self.now() } }
	end)
	if not wrote then
		s.failures += 1
		return false, "save_failed", nil
	end
	if conflict then
		s.failures += 1
		return false, "session_conflict", nil
	end
	s.failures = 0
	s.profile = result.profile
	return true, Mut.deepCopy(result.profile), info
end

-- Serialized per profile: concurrent callers are queued FIFO. With a yielding store (Roblox
-- UpdateAsync) the first caller drains the queue and later callers receive their own result.
function Repository.mutate(self, userKey: string, mutation: any, ctx: any?): (boolean, any, any)
	local s = self.sessions[userKey]
	if not s then
		return false, "not_loaded", nil
	end
	local resultOk, resultValue, resultInfo
	local finished = false
	local waiting: thread? = nil
	table.insert(s.queue, {
		mutation = mutation,
		ctx = ctx,
		done = function(a, b, c)
			resultOk, resultValue, resultInfo = a, b, c
			finished = true
			if waiting and coroutine.status(waiting) == "suspended" then
				task.spawn(waiting)
			end
		end,
	})
	if not s.busy then
		s.busy = true
		while #s.queue > 0 do
			local job = table.remove(s.queue, 1)
			local ok, v, info = self:_commit(s, job.mutation, job.ctx)
			job.done(ok, v, info)
		end
		s.busy = false
	end
	if not finished then
		waiting = coroutine.running()
		coroutine.yield()
	end
	return resultOk, resultValue, resultInfo
end

-- Final durable write releasing the lock. Returns false when the write failed.
function Repository.release(self, userKey: string): boolean
	local s = self.sessions[userKey]
	if not s then
		return true
	end
	s.released = true
	local ok = self.store:update(keyFor(userKey), function(old)
		if old == nil or old.lock == nil or old.lock.jobId ~= self.jobId then
			return nil
		end
		return { profile = s.profile, lock = nil }
	end)
	self.sessions[userKey] = nil
	return ok
end

------------------------------------------------------------------------------------------------
-- In-memory store (offline tests / Studio without API access). Supports failure injection.
------------------------------------------------------------------------------------------------
local MemoryStore = {}
MemoryStore.__index = MemoryStore

function MemoryStore.new()
	return setmetatable({ data = {}, failNext = 0, failAll = false, writes = 0 }, MemoryStore)
end

function MemoryStore.update(self, key: string, transform: (any?) -> any?): (boolean, any)
	if self.failAll or self.failNext > 0 then
		self.failNext = math.max(0, self.failNext - 1)
		return false, "injected_failure"
	end
	local old = self.data[key] and Mut.deepCopy(self.data[key]) or nil
	local new = transform(old)
	if new == nil then
		return true, old
	end
	self.data[key] = Mut.deepCopy(new)
	self.writes += 1
	return true, Mut.deepCopy(new)
end

Repository.MemoryStore = MemoryStore

------------------------------------------------------------------------------------------------
-- Roblox DataStore adapter (engine only; NOT exercised offline).
------------------------------------------------------------------------------------------------
function Repository.dataStoreAdapter(dataStoreName: string)
	local DataStoreService = game:GetService("DataStoreService")
	local ds = DataStoreService:GetDataStore(dataStoreName)
	return {
		update = function(_, key: string, transform: (any?) -> any?): (boolean, any)
			local result
			local ok, err = pcall(function()
				result = ds:UpdateAsync(key, function(old)
					return transform(old)
				end)
			end)
			if not ok then
				warn("[PlayerProfileRepository] UpdateAsync failed:", err)
				return false, err
			end
			return true, result
		end,
	}
end

return Repository
