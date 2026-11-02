--!nocheck
-- Offline module loader emulating Rojo/Roblox `script` + `require(instance)` semantics so that
-- game modules written for Roblox (require(script.Parent.X)) run unchanged under Lune.
-- This only provides the module graph; engine services (Workspace, physics, DataStore) are NOT
-- emulated: code needing them must receive adapters/fakes by injection.

local fs = require("@lune/fs")
local luau = require("@lune/luau")
local roblox = require("@lune/roblox")

local Loader = {}

local ROOTS = {
	-- mirrors default.project.json
	ReplicatedStorage = { Shared = "src/shared" },
	ServerScriptService = { Server = "src/server" },
	StarterPlayerScripts = { Client = "src/client" },
	ServerStorage = { AssetGenerators = "assets/source/generators" },
}

local cache: { [string]: any } = {}
local loading: { [string]: boolean } = {}
local nodes: { [string]: any } = {}

local NodeMeta = {}

-- fs calls yield in Lune and cannot run inside __index metamethods: index the tree eagerly.
local DIRS: { [string]: boolean } = {}
local FILES: { [string]: string } = {}
local function scan(dir: string)
	DIRS[dir] = true
	for _, name in fs.readDir(dir) do
		local p = dir .. "/" .. name
		if fs.isDir(p) then
			scan(p)
		elseif string.match(name, "%.luau?$") then
			FILES[p] = fs.readFile(p)
		end
	end
end
for _, map in ROOTS do
	for _, dir in map do
		if fs.isDir(dir) then
			scan(dir)
		end
	end
end

local function moduleFile(path: string, kind: string): string?
	if kind == "dir" then
		for _, name in { "init.luau", "init.lua" } do
			if FILES[path .. "/" .. name] then
				return path .. "/" .. name
			end
		end
		return nil
	end
	return path
end

local function makeNode(path: string, kind: string, name: string, parent: any)
	local key = kind .. ":" .. path
	if nodes[key] then
		return nodes[key]
	end
	local node = setmetatable({ __path = path, __kind = kind, Name = name, Parent = parent }, NodeMeta)
	nodes[key] = node
	return node
end

local function childOf(node, name: string)
	local base: string
	if node.__kind == "dir" then
		base = node.__path
	else
		-- a file module has no children unless a sibling folder with the same stem exists (not used)
		return nil
	end
	local candidate = base .. "/" .. name
	if DIRS[candidate] then
		return makeNode(candidate, "dir", name, node)
	end
	for _, ext in { ".luau", ".lua", ".server.luau", ".client.luau" } do
		if FILES[candidate .. ext] then
			return makeNode(candidate .. ext, "file", name, node)
		end
	end
	return nil
end

NodeMeta.__index = function(node, key)
	if key == "FindFirstChild" then
		return function(self, name)
			return childOf(self, name)
		end
	elseif key == "WaitForChild" then
		return function(self, name)
			local c = childOf(self, name)
			assert(c, "WaitForChild: missing " .. tostring(name) .. " under " .. self.__path)
			return c
		end
	elseif key == "GetFullName" then
		return function(self)
			return self.__path
		end
	elseif key == "IsA" then
		return function(self, class)
			return class == "ModuleScript" and (self.__kind == "file" or FILES[self.__path .. "/init.luau"] ~= nil)
		end
	end
	local c = childOf(node, key)
	if c == nil then
		error(string.format("%s is not a valid member of %s", tostring(key), node.__path), 2)
	end
	return c
end
NodeMeta.__tostring = function(node)
	return node.__path
end

local requireNode

-- Minimal `game` stand-in: only GetService(...) returning the project roots, so idiomatic
-- `game:GetService("ReplicatedStorage"):WaitForChild("Shared")` resolves offline.
local services = {}
local FakeGame = {}
-- Engine-lite mode: real Roblox DOM instances from @lune/roblox (property names and value types
-- are validated against Roblox's reflection database) + a CollectionService shim mapping to the
-- instance tag API. No physics, no signals, no PivotTo: only code that builds instances can run.
local engineLite = false
local CollectionShim = {}
function CollectionShim.AddTag(_, inst, tag)
	inst:AddTag(tag)
end
function CollectionShim.RemoveTag(_, inst, tag)
	inst:RemoveTag(tag)
end
function CollectionShim.HasTag(_, inst, tag)
	return inst:HasTag(tag)
end
function Loader.enableEngineLite()
	engineLite = true
end

function FakeGame.GetService(_, name: string)
	if services[name] then
		return services[name]
	end
	if name == "CollectionService" and engineLite then
		return CollectionShim
	end
	local map = ROOTS[name]
	if not map then
		error("service " .. name .. " is not available offline (engine-only)")
	end
	local svc = { Name = name }
	local children = {}
	for childName, dir in map do
		children[childName] = makeNode(dir, "dir", childName, svc)
	end
	setmetatable(svc, {
		__index = function(_, k)
			if k == "WaitForChild" or k == "FindFirstChild" then
				return function(_, n)
					return children[n]
				end
			end
			return children[k]
		end,
	})
	services[name] = svc
	return svc
end
Loader.game = FakeGame

-- Fake-engine mode (tests/_harness/FakeEngine.luau): overrides `game`, `Instance`, `workspace`...
local engineEnv: { [string]: any }? = nil
function Loader.setEngine(env)
	engineEnv = env
end

local function makeEnv(node)
	local env = Loader._baseEnv(node)
	if engineEnv then
		for k, v in engineEnv do
			env[k] = v
		end
	end
	return env
end

function Loader._baseEnv(node)
	return {
		script = node,
		require = requireNode,
		game = FakeGame,
		task = require("@lune/task"),
		-- Roblox datatypes are available offline through @lune/roblox (no engine behaviour).
		Vector3 = roblox.Vector3,
		CFrame = roblox.CFrame,
		Color3 = roblox.Color3,
		Instance = if engineLite then roblox.Instance else nil,
		Enum = if engineLite then roblox.Enum else nil,
		PhysicalProperties = if engineLite then roblox.PhysicalProperties else nil,
	}
end

requireNode = function(target)
	if type(target) == "string" then
		return require(target)
	end
	assert(type(target) == "table" and target.__path, "require expects a module node")
	local file = moduleFile(target.__path, target.__kind)
	assert(file, "not a ModuleScript: " .. target.__path)
	if cache[file] ~= nil then
		return cache[file]
	end
	assert(not loading[file], "cyclic require: " .. file)
	loading[file] = true
	local source = FILES[file]
	local chunk = luau.load(source, { debugName = file, environment = makeEnv(target) })
	local result = chunk()
	loading[file] = nil
	assert(result ~= nil, "module returned nil: " .. file)
	cache[file] = result
	return result
end

-- Loader.node("src/shared/Domain/Rewards") -> module node usable as `script` or with require.
function Loader.node(path: string)
	local parts = string.split(path, "/")
	local root
	for svc, map in ROOTS do
		for name, dir in map do
			if string.sub(path, 1, #dir) == dir then
				root = makeNode(dir, "dir", name, { Name = svc })
				local rest = string.sub(path, #dir + 2)
				local node = root
				if rest ~= "" then
					for _, seg in string.split(rest, "/") do
						node = childOf(node, seg)
						assert(node, "no module at " .. path)
					end
				end
				return node
			end
		end
	end
	error("path outside project roots: " .. path .. " (" .. #parts .. ")")
end

function Loader.require(path: string)
	return requireNode(Loader.node(path))
end

-- Execute a Script (e.g. src/server/Main.server) in its own thread; scripts return nothing.
function Loader.runScript(path: string)
	local node = Loader.node(path)
	local file = node.__path
	local source = FILES[file]
	assert(source, "no script at " .. path)
	local chunk = luau.load(source, { debugName = file, environment = makeEnv(node) })
	return chunk()
end

function Loader.reset()
	table.clear(cache)
end

return Loader
