--!strict
-- Deterministic PRNG (xorshift32 + FNV-1a seed derivation) implemented with bit32 so that
-- Roblox servers and the offline test runner (Lune) produce identical sequences for a seed.
-- Roblox's Random is not used in domain code because it is unavailable outside the engine.

local Rng = {}
Rng.__index = Rng

export type Rng = typeof(setmetatable({} :: { state: number }, Rng))

local function fnv1a(text: string): number
	local hash = 2166136261
	for i = 1, #text do
		hash = bit32.bxor(hash, string.byte(text, i))
		-- multiply by FNV prime 16777619 = 2^24 + 403 modulo 2^32 (exact in doubles: < 2^53)
		hash = (bit32.lshift(hash, 24) + hash * 403) % 4294967296
	end
	return hash
end

function Rng.hash(text: string): number
	return fnv1a(text)
end

-- Derive a child seed from a parent seed and a salt (e.g. "room:12" or "wave:3").
function Rng.derive(seed: number, salt: string): number
	local h = fnv1a(tostring(math.floor(seed)) .. "|" .. salt)
	if h == 0 then
		h = 0x9E3779B9
	end
	return h
end

function Rng.new(seed: number): Rng
	local s = bit32.band(math.floor(seed), 0xFFFFFFFF)
	if s == 0 then
		s = 0x6D2B79F5
	end
	local self = setmetatable({ state = s }, Rng)
	-- warm up
	for _ = 1, 4 do
		self:nextU32()
	end
	return self
end

function Rng.nextU32(self: Rng): number
	local x = self.state
	x = bit32.bxor(x, bit32.lshift(x, 13))
	x = bit32.bxor(x, bit32.rshift(x, 17))
	x = bit32.bxor(x, bit32.lshift(x, 5))
	self.state = x
	return x
end

-- Uniform number in [0, 1)
function Rng.nextNumber(self: Rng): number
	return self:nextU32() / 4294967296
end

-- Uniform integer in [lo, hi]
function Rng.nextInt(self: Rng, lo: number, hi: number): number
	assert(hi >= lo, "Rng.nextInt: empty range")
	return lo + (self:nextU32() % (hi - lo + 1))
end

function Rng.nextRange(self: Rng, lo: number, hi: number): number
	return lo + (hi - lo) * self:nextNumber()
end

function Rng.pick<T>(self: Rng, list: { T }): T
	assert(#list > 0, "Rng.pick: empty list")
	return list[self:nextInt(1, #list)]
end

function Rng.shuffle<T>(self: Rng, list: { T }): { T }
	local copy = table.clone(list)
	for i = #copy, 2, -1 do
		local j = self:nextInt(1, i)
		copy[i], copy[j] = copy[j], copy[i]
	end
	return copy
end

return Rng
