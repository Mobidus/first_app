--!strict
-- Client network wrapper: sends intents (never amounts), receives authoritative state.
local HttpService = game:GetService("HttpService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = {}

local remotes = ReplicatedStorage:WaitForChild("Remotes")
local intent = remotes:WaitForChild("Intent") :: RemoteFunction

Net.state = {} :: any
local listeners: { [string]: { (any) -> () } } = {}

function Net.requestId(): string
	return HttpService:GenerateGUID(false):sub(1, 18)
end

-- Returns the server answer table ({ ok = bool, ... }); network errors are reported honestly.
function Net.intent(name: string, ...: any): any
	local args = { ... }
	local ok, res = pcall(function()
		return intent:InvokeServer(name, args)
	end)
	if not ok then
		return { ok = false, error = "network_error" }
	end
	return res
end

function Net.on(event: string, fn: (any) -> ())
	listeners[event] = listeners[event] or {}
	table.insert(listeners[event], fn)
end

local function dispatch(event: string, payload: any)
	for _, fn in listeners[event] or {} do
		task.spawn(fn, payload)
	end
end

for _, name in { "State", "Hud", "WaveWarning", "PlushImpact", "RadarHighlight", "BurialWarning", "ToolEffect", "Transition" } do
	local ev = remotes:WaitForChild(name) :: RemoteEvent
	ev.OnClientEvent:Connect(function(payload)
		if name == "State" then
			Net.state = payload
		end
		dispatch(name, payload)
	end)
end

return Net
