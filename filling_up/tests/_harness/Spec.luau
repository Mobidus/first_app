--!nocheck
-- Minimal BDD harness (describe / it / expect) for offline Luau unit tests run with Lune.
local Spec = {}

local results = { passed = 0, failed = 0, cases = {} }
local prefix = {}

local function fmt(v)
	if type(v) == "table" then
		local ok, s = pcall(function()
			local parts = {}
			for k, x in v do
				table.insert(parts, tostring(k) .. "=" .. tostring(x))
			end
			table.sort(parts)
			return "{" .. table.concat(parts, ",") .. "}"
		end)
		return ok and s or tostring(v)
	end
	return tostring(v)
end

function Spec.describe(name: string, fn: () -> ())
	table.insert(prefix, name)
	fn()
	table.remove(prefix)
end

function Spec.it(name: string, fn: () -> ())
	local full = table.concat(prefix, " > ") .. " > " .. name
	local ok, err = xpcall(fn, function(e)
		return tostring(e) .. "\n" .. debug.traceback(nil, 2)
	end)
	if ok then
		results.passed += 1
		table.insert(results.cases, { name = full, status = "PASS" })
	else
		results.failed += 1
		table.insert(results.cases, { name = full, status = "FAIL", error = err })
		print("FAIL  " .. full .. "\n      " .. string.gsub(tostring(err), "\n", "\n      "))
	end
end

local function deepEqual(a, b): boolean
	if type(a) ~= type(b) then
		return false
	end
	if type(a) ~= "table" then
		return a == b
	end
	for k, v in a do
		if not deepEqual(v, b[k]) then
			return false
		end
	end
	for k in b do
		if a[k] == nil then
			return false
		end
	end
	return true
end
Spec.deepEqual = deepEqual

function Spec.expect(actual)
	local e = {}
	function e.toBe(expected)
		if actual ~= expected then
			error(string.format("expected %s to be %s", fmt(actual), fmt(expected)), 2)
		end
	end
	function e.toEqual(expected)
		if not deepEqual(actual, expected) then
			error(string.format("expected %s to deep-equal %s", fmt(actual), fmt(expected)), 2)
		end
	end
	function e.toBeTruthy()
		if not actual then
			error("expected truthy, got " .. fmt(actual), 2)
		end
	end
	function e.toBeFalsy()
		if actual then
			error("expected falsy, got " .. fmt(actual), 2)
		end
	end
	function e.toBeNear(expected, tol)
		tol = tol or 1e-9
		if type(actual) ~= "number" or math.abs(actual - expected) > tol then
			error(string.format("expected %s to be within %s of %s", fmt(actual), fmt(tol), fmt(expected)), 2)
		end
	end
	function e.toBeAtMost(limit)
		if not (actual <= limit) then
			error(string.format("expected %s <= %s", fmt(actual), fmt(limit)), 2)
		end
	end
	function e.toBeAtLeast(limit)
		if not (actual >= limit) then
			error(string.format("expected %s >= %s", fmt(actual), fmt(limit)), 2)
		end
	end
	function e.toThrow()
		local ok = pcall(actual)
		if ok then
			error("expected function to throw", 2)
		end
	end
	return e
end

function Spec.results()
	return results
end

return Spec
