--!strict
-- Telemetry: structured events and counters for first-session UX, KO, exits, resumes and
-- rebirths. It never touches the economy and never invents retention statistics.
local TelemetryService = {}
TelemetryService.__index = TelemetryService

TelemetryService.MAX_BUFFER = 2000

function TelemetryService.new(sink: ((any) -> ())?)
	return setmetatable({ buffer = {}, counters = {}, sink = sink }, TelemetryService)
end

function TelemetryService.event(self, userKey: string, name: string, data: any?)
	local e = { t = os.time(), clock = os.clock(), user = userKey, name = name, data = data }
	table.insert(self.buffer, e)
	if #self.buffer > TelemetryService.MAX_BUFFER then
		table.remove(self.buffer, 1)
	end
	self.counters[name] = (self.counters[name] or 0) + 1
	if self.sink then
		self.sink(e)
	end
end

function TelemetryService.snapshot(self): any
	return { counters = table.clone(self.counters), buffered = #self.buffer }
end

return TelemetryService
