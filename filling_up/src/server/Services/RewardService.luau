--!strict
-- Grants progression rewards through the profile repository. The rebirth rate is frozen at room
-- start; milestone/exit/token identities derive from runId + depth + milestone. All amounts come
-- from config via the pure Rewards module; the client never supplies an amount.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Rewards = require(Shared.Domain.Rewards)

local RewardService = {}
RewardService.__index = RewardService

function RewardService.new(repo: any, telemetry: any)
	return setmetatable({ repo = repo, telemetry = telemetry }, RewardService)
end

-- room: { runId, depth, mask, rateBp, paidBaseCumulative } (mutated on success)
function RewardService.progress(self, userKey: string, room: any, index: number): (boolean, any)
	local ok, profileOrErr, claim = self.repo:mutate(userKey, {
		type = "GrantProgress",
		runId = room.runId,
		depth = room.depth,
		index = index,
		mask = room.mask,
		rateBp = room.rateBp,
		paidBaseCumulative = room.paidBaseCumulative,
	})
	if ok then
		room.mask = claim.newMask
		room.paidBaseCumulative = claim.newPaidBaseCumulative
		for _, line in claim.lines do
			self.telemetry:event(userKey, "reward", { rewardId = line.rewardId, amount = line.amount, kind = line.kind })
		end
		return true, { profile = profileOrErr, claim = claim }
	end
	return false, profileOrErr
end

function RewardService.token(self, userKey: string, room: any, tokenIndex: number): (boolean, any)
	local ok, profileOrErr, claim = self.repo:mutate(userKey, {
		type = "GrantToken",
		runId = room.runId,
		depth = room.depth,
		tokenIndex = tokenIndex,
		mask = room.mask,
		paidBaseCumulative = room.paidBaseCumulative,
	})
	if ok then
		room.mask = claim.newMask
		return true, { profile = profileOrErr, claim = claim }
	end
	return false, profileOrErr
end

function RewardService.rateForProfile(profile: any): number
	return Rewards.rebirthBasisPoints(profile.rebirthCount)
end

return RewardService
