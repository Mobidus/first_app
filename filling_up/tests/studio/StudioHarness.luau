--!strict
-- Minimal Studio test harness: each lab registers checks; results are printed as one JSON line
-- ("STUDIO_RESULT_JSON:") to copy into reports/. Statuses: PASS | FAIL | NOT_RUN.
local HttpService = game:GetService("HttpService")

local Harness = {}

export type Suite = { name: string, results: { any } }

function Harness.suite(name: string): Suite
	return { name = name, results = {} }
end

function Harness.record(s: Suite, check: string, status: string, data: any?)
	table.insert(s.results, { check = check, status = status, data = data })
	print(string.format("[%s] %s  %s", s.name, status, check))
end

function Harness.expect(s: Suite, check: string, cond: boolean, data: any?)
	Harness.record(s, check, if cond then "PASS" else "FAIL", data)
end

function Harness.finish(s: Suite)
	local failed = 0
	for _, r in s.results do
		if r.status == "FAIL" then
			failed += 1
		end
	end
	local out = {
		suite = s.name,
		status = if failed == 0 then "PASS" else "FAIL",
		results = s.results,
		placeVersion = game.PlaceVersion,
		date = DateTime.now():ToIsoDate(),
	}
	print("STUDIO_RESULT_JSON:" .. HttpService:JSONEncode(out))
	workspace:SetAttribute("FU_TEST_DONE_" .. s.name, out.status)
end

-- Labs only run when the place is started with workspace attribute FU_TEST_SUITE = "<suite>".
function Harness.selected(name: string): boolean
	return workspace:GetAttribute("FU_TEST_SUITE") == name
end

return Harness
