--!nocheck
-- Offline unit-test entry point:  lune run tests/run.luau <suite|all>
-- Must be launched with the project root (filling_up/) as working directory.
local process = require("@lune/process")
local serde = require("@lune/serde")
local Spec = require("./_harness/Spec")

local SUITES = {
	expedition = { "./unit/ExpeditionStateMachine.spec", "./unit/IntentValidation.spec" },
	routes = { "./unit/RouteValidator.spec" },
	profile = { "./unit/ProfileMutations.spec", "./unit/PlayerProfileRepository.spec" },
	onboarding = { "./unit/Onboarding.spec" },
	economy = { "./unit/Economy.spec", "./unit/Rewards.spec" },
	tools = { "./unit/Tools.spec" },
	rebirth = { "./unit/Rebirth.spec" },
	["generation-initial"] = { "./unit/GenerationInitial.spec" },
	["generation-full"] = { "./unit/GenerationFull.spec" },
	checkpoints = { "./unit/Checkpoint.spec" },
	receipts = { "./unit/Receipts.spec" },
	waves = { "./unit/WaveSchedule.spec", "./unit/Consolidation.spec", "./unit/ObjectPool.spec" },
	burial = { "./unit/BurialLogic.spec" },
	plush = { "./unit/PlushPose.spec" },
	continuity = { "./unit/RoomResidency.spec" },
	dressing = { "./unit/SetDressing.spec" },
	config = { "./unit/Config.spec" },
	integration = { "./integration/ServerFlow.spec" },
}

local ORDER = {
	"config",
	"expedition",
	"routes",
	"profile",
	"onboarding",
	"economy",
	"tools",
	"rebirth",
	"generation-initial",
	"generation-full",
	"checkpoints",
	"receipts",
	"waves",
	"burial",
	"plush",
	"continuity",
	"integration",
}

local suite = process.args[1] or "all"
local selected = {}
if suite == "all" then
	selected = ORDER
elseif SUITES[suite] then
	selected = { suite }
else
	print("RESULT_JSON:" .. serde.encode("json", { status = "BLOCKED", error = "unknown suite " .. suite }))
	process.exit(2)
end

local started = os.clock()
for _, name in selected do
	Spec.describe(name, function()
		for _, file in SUITES[name] do
			local ok, err = pcall(require, file)
			if not ok then
				Spec.it("load " .. file, function()
					error(err)
				end)
			end
		end
	end)
end

local r = Spec.results()
local summary = {
	status = (r.failed == 0 and r.passed > 0) and "PASS" or "FAIL",
	suite = suite,
	passed = r.passed,
	failed = r.failed,
	seconds = os.clock() - started,
	cases = r.cases,
}
print(string.format("%s  %d passed, %d failed (%s)", summary.status, r.passed, r.failed, suite))
print("RESULT_JSON:" .. serde.encode("json", summary))
process.exit(r.failed == 0 and 0 or 1)
