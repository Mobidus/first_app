--!strict
-- Network surface. Clients send bounded INTENTS through one RemoteFunction; the server pushes
-- authoritative state through RemoteEvents. Every intent is schema-validated and rate limited.
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Intent = require(Shared.Domain.IntentValidation)

local Remotes = {}

local folder: Folder
local handlers: { [string]: (player: Player, args: any) -> any } = {}
local limiter = Intent.newLimiter(6, 3) -- per player+intent: burst 6, 3/s sustained

Remotes.EVENTS = { "State", "Hud", "WaveWarning", "PlushImpact", "RadarHighlight", "BurialWarning", "ToolEffect", "Transition" }

function Remotes.init()
	folder = Instance.new("Folder")
	folder.Name = "Remotes"
	for _, name in Remotes.EVENTS do
		local ev = Instance.new("RemoteEvent")
		ev.Name = name
		ev.Parent = folder
	end
	local rf = Instance.new("RemoteFunction")
	rf.Name = "Intent"
	rf.Parent = folder
	rf.OnServerInvoke = function(player: Player, name: any, args: any)
		if type(name) ~= "string" or type(args) ~= "table" then
			return { ok = false, error = "bad_request" }
		end
		if not Intent.allow(limiter, tostring(player.UserId) .. ":" .. name, os.clock()) then
			return { ok = false, error = "rate_limited" }
		end
		local ok, parsed = Intent.validate(name, args)
		if not ok then
			return { ok = false, error = parsed }
		end
		local handler = handlers[name]
		if not handler then
			return { ok = false, error = "not_handled" }
		end
		local success, result = pcall(handler, player, parsed)
		if not success then
			warn("[Remotes] handler error", name, result)
			return { ok = false, error = "server_error" }
		end
		return result
	end
	folder.Parent = ReplicatedStorage
end

function Remotes.on(name: string, handler: (player: Player, args: any) -> any)
	handlers[name] = handler
end

function Remotes.fire(player: Player, event: string, payload: any)
	(folder:FindFirstChild(event) :: RemoteEvent):FireClient(player, payload)
end

function Remotes.forget(player: Player)
	Intent.forget(limiter, tostring(player.UserId) .. ":")
end

return Remotes
