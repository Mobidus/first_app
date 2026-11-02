--!strict
-- Tutorial rewards/kiosk rules shared by ExpeditionService.startTutorial (the cell flow) and the
-- sas kiosk. Kept separate for the T12 contract: rewards are granted once per account through
-- PlayerProfileRepository; the kiosk sells exactly the configured first tool at its config price.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.GeneratedConfig)
local Tutorial = require(Shared.Domain.Tutorial)

local TutorialService = {}

TutorialService.FIRST_TOOL = Config.Economy.tutorial.first_tool_id

function TutorialService.grant(repo: any, userKey: string, event: string): (boolean, string?)
	local p = repo:get(userKey)
	local reward = Tutorial.rewardFor(event, p.tutorialFlags)
	if not reward then
		return false, nil
	end
	local ok = repo:mutate(userKey, { type = "GrantTutorial", rewardId = reward })
	return ok, reward
end

-- Kiosk offer as displayed (never authoritative): price from config, two actions, no timer.
function TutorialService.kioskOffer(profile: any): any
	local tool = Config.Economy.tools[1]
	assert(tool.id == TutorialService.FIRST_TOOL, "first catalogue tool must be the tutorial tool")
	return {
		skuId = tool.id,
		name = tool.name,
		price = tool.coins,
		balance = profile.coins,
		after = profile.coins - tool.coins,
		owned = profile.ownedTools[tool.id] == true,
		actions = Tutorial.KIOSK_BUTTONS,
		countdown = nil,
		robuxOffer = nil,
	}
end

return TutorialService
