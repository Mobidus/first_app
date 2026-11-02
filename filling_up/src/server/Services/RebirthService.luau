--!strict
-- Voluntary rebirth in the sas: server-issued preview token bound to player, quantity and profile
-- revision; confirmation recomputes the cumulative cost and commits ONE mutation.
local HttpService = game:GetService("HttpService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Rebirth = require(Shared.Domain.Rebirth)

local RebirthService = {}
RebirthService.__index = RebirthService

function RebirthService.new(repo: any, telemetry: any)
	return setmetatable(
		{ repo = repo, telemetry = telemetry, secret = HttpService:GenerateGUID(false), busy = {} :: { [string]: boolean } },
		RebirthService
	)
end

function RebirthService.preview(self, userKey: string, quantity: number, inSas: boolean): any
	if not inSas then
		return { ok = false, error = "not_in_sas" }
	end
	local profile = self.repo:get(userKey)
	local ok, res = Rebirth.preview(profile, userKey, quantity, self.secret)
	if not ok then
		return { ok = false, error = res, maxAffordable = Rebirth.maxAffordable(profile.rebirthCount, profile.permits) }
	end
	return { ok = true, preview = res }
end

function RebirthService.confirm(self, userKey: string, req: any, inSas: boolean): any
	if self.busy[userKey] then
		return { ok = false, error = "transaction_in_progress" }
	end
	self.busy[userKey] = true
	local ok, res, info = self.repo:mutate(userKey, {
		type = "Rebirth",
		quantity = req.quantity,
		expectedRevision = req.expectedRevision,
		previewToken = req.previewToken,
		inSas = inSas,
	}, { userKey = userKey, secret = self.secret })
	self.busy[userKey] = nil
	self.telemetry:event(userKey, ok and "rebirth" or "rebirth_refused", { quantity = req.quantity, reason = (not ok) and res or nil })
	if not ok then
		return { ok = false, error = res }
	end
	return { ok = true, profile = res, result = info }
end

return RebirthService
