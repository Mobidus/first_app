--!strict
-- Typed, bounded client intents (docs/05 §5). The server never accepts amounts, prices,
-- permit counts or "room completed" from a client: such fields are not part of any schema and
-- any unexpected argument makes the whole intent invalid.

local Config = require(script.Parent.Parent.GeneratedConfig)

local Intent = {}

local MAX_ID_LEN = 64
local MAX_TOKEN_LEN = 128
local MAX_ARGS = 4

local TOOL_IDS: { [string]: boolean } = {}
for _, t in Config.Economy.tools do
	TOOL_IDS[t.id] = true
end
local COSMETIC_SLOTS: { [string]: string } = {}
for _, c in Config.Economy.cosmetics do
	COSMETIC_SLOTS[c.id] = c.slot
end
local SKUS: { [string]: string } = {}
for _, t in Config.Economy.tools do
	SKUS[t.id] = "tool"
	for r = 2, #t.ranks do
		SKUS[t.id .. "#rank" .. r] = "upgrade"
	end
end
for _, c in Config.Economy.cosmetics do
	SKUS[c.id] = "cosmetic"
end
Intent.SKU_KINDS = SKUS

local SLOTS = {
	active = true,
	passive = true,
	companion = true,
	trail = true,
	tool_skin = true,
	landing_fx = true,
	victory_fx = true,
	workshop_skin = true,
}

local function isId(v: any, max: number?): boolean
	return type(v) == "string" and #v > 0 and #v <= (max or MAX_ID_LEN) and string.match(v, "^[%w_#:%-%.]+$") ~= nil
end

local function isPositiveInt(v: any, max: number): boolean
	return type(v) == "number" and v == v and v % 1 == 0 and v >= 1 and v <= max
end

local function isNonNegInt(v: any): boolean
	return type(v) == "number" and v == v and v % 1 == 0 and v >= 0 and v < 2 ^ 53
end

export type Validated = { name: string, args: { [string]: any } }

local SCHEMAS: { [string]: (args: { any }) -> (boolean, any) } = {
	RequestToolUse = function(a)
		if #a ~= 3 or not TOOL_IDS[a[1]] then
			return false, "bad_tool"
		end
		if not (a[2] == "" or isId(a[2])) or not isId(a[3]) then
			return false, "bad_args"
		end
		return true, { toolId = a[1], targetId = a[2], requestId = a[3] }
	end,
	RequestEquip = function(a)
		if #a ~= 3 or not SLOTS[a[2]] or not isId(a[3]) then
			return false, "bad_args"
		end
		local item = a[1]
		if item ~= "" and not (TOOL_IDS[item] or COSMETIC_SLOTS[item] or (isId(item) and string.sub(item, 1, 8) == "premium_")) then
			return false, "unknown_item"
		end
		return true, { itemId = item, slot = a[2], requestId = a[3] }
	end,
	RequestCoinPurchase = function(a)
		if #a ~= 2 or not SKUS[a[1]] or not isId(a[2]) then
			return false, "bad_args"
		end
		return true, { skuId = a[1], requestId = a[2] }
	end,
	RequestRebirthPreview = function(a)
		if #a ~= 2 or not isPositiveInt(a[1], 1000) or not isId(a[2]) then
			return false, "bad_args"
		end
		return true, { quantity = a[1], requestId = a[2] }
	end,
	RequestRebirth = function(a)
		if #a ~= 4 or not isPositiveInt(a[1], 1000) or not isNonNegInt(a[2]) or not isId(a[3], MAX_TOKEN_LEN) or not isId(a[4]) then
			return false, "bad_args"
		end
		return true, { quantity = a[1], expectedRevision = a[2], previewToken = a[3], requestId = a[4] }
	end,
	RequestSaveExit = function(a)
		if #a ~= 1 or not isId(a[1]) then
			return false, "bad_args"
		end
		return true, { requestId = a[1] }
	end,
	RequestRestart = function(a)
		if #a ~= 1 or not isId(a[1]) then
			return false, "bad_args"
		end
		return true, { requestId = a[1] }
	end,
	RequestRobuxPurchase = function(a)
		if #a ~= 2 or not isId(a[1]) or not isId(a[2]) then
			return false, "bad_args"
		end
		return true, { skuId = a[1], requestId = a[2] }
	end,
}
Intent.NAMES = {}
for name in SCHEMAS do
	table.insert(Intent.NAMES, name)
end
table.sort(Intent.NAMES)

-- validate("RequestCoinPurchase", {"radar_pop", "req-1"}) -> (true, {skuId=..., requestId=...})
function Intent.validate(name: string, args: { any }): (boolean, any)
	local schema = SCHEMAS[name]
	if not schema then
		return false, "unknown_intent"
	end
	if type(args) ~= "table" or #args > MAX_ARGS then
		return false, "bad_args"
	end
	for k in args do
		if type(k) ~= "number" then
			return false, "bad_args"
		end
	end
	return schema(args)
end

-- Token-bucket rate limiter; the clock is injected (server: os.clock / workspace time).
export type Limiter = { capacity: number, refillPerSecond: number, buckets: { [string]: { tokens: number, t: number } } }

function Intent.newLimiter(capacity: number, refillPerSecond: number): Limiter
	return { capacity = capacity, refillPerSecond = refillPerSecond, buckets = {} }
end

function Intent.allow(limiter: Limiter, key: string, now: number): boolean
	local b = limiter.buckets[key]
	if not b then
		b = { tokens = limiter.capacity, t = now }
		limiter.buckets[key] = b
	end
	b.tokens = math.min(limiter.capacity, b.tokens + (now - b.t) * limiter.refillPerSecond)
	b.t = now
	if b.tokens >= 1 then
		b.tokens -= 1
		return true
	end
	return false
end

function Intent.forget(limiter: Limiter, keyPrefix: string)
	for k in limiter.buckets do
		if string.sub(k, 1, #keyPrefix) == keyPrefix then
			limiter.buckets[k] = nil
		end
	end
end

return Intent
