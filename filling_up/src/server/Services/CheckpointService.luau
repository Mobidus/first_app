--!strict
-- Durable checkpoint at every room exit (runtime.profile.snapshot_at_every_room_exit) and resume
-- planning. "Sauvegardé" is only reported after the repository confirmed the durable write.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Checkpoint = require(Shared.Domain.Checkpoint)

local CheckpointService = {}
CheckpointService.__index = CheckpointService

function CheckpointService.new(repo: any, telemetry: any)
	return setmetatable({ repo = repo, telemetry = telemetry }, CheckpointService)
end

function CheckpointService.save(self, userKey: string, expedition: any, roomCtx: any, charges: { [string]: number }?): (boolean, string?)
	local cp = Checkpoint.fromExpedition(
		expedition,
		{ rateBasisPoints = roomCtx.rateBp, paidBaseCumulative = roomCtx.paidBaseCumulative, charges = charges }
	)
	local ok, err = self.repo:mutate(userKey, { type = "SetCheckpoint", checkpoint = cp })
	self.telemetry:event(
		userKey,
		ok and "checkpoint_saved" or "checkpoint_failed",
		{ depth = expedition.depth, error = (not ok) and err or nil }
	)
	if ok then
		expedition.checkpointRevision = cp.checkpointRevision
		return true, nil
	end
	return false, err
end

function CheckpointService.clear(self, userKey: string): boolean
	return (self.repo:mutate(userKey, { type = "ClearCheckpoint" }))
end

function CheckpointService.plan(profile: any)
	return Checkpoint.plan(profile.checkpoint, nil)
end

return CheckpointService
