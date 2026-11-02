--!strict
-- Server bootstrap. Data: a SEPARATE test DataStore by default (S11). In Studio without API
-- access, an in-memory store is used and the HUD is told that progress is NOT persistent.
local RunService = game:GetService("RunService")
local Players = game:GetService("Players")

local Services = script.Parent:WaitForChild("Services")
local Tools = script.Parent:WaitForChild("Tools")

local Remotes = require(Services.Remotes)
local Repository = require(Services.PlayerProfileRepository)
local Telemetry = require(Services.TelemetryService)
local RewardService = require(Services.RewardService)
local InventoryService = require(Services.InventoryService)
local RebirthService = require(Services.RebirthService)
local CheckpointService = require(Services.CheckpointService)
local BurialService = require(Services.BurialService)
local ExpeditionService = require(Services.ExpeditionService)
local PurchaseService = require(Services.PurchaseService)
local ToolService = require(Tools.ToolService)

local DATASTORE_NAME = "FillingUp_Profiles_TEST_v3" -- production name is set only at release (T23)

Remotes.init()

local telemetry = Telemetry.new(function(e)
	if RunService:IsStudio() then
		print("[telemetry]", e.name, e.user)
	end
end)

local store
local persistent = true
local okStore = pcall(function()
	store = Repository.dataStoreAdapter(DATASTORE_NAME)
	-- probe API access once (Studio without "Enable Studio Access to API Services" fails here)
	store:update("probe_" .. game.JobId, function(_old)
		return nil
	end)
end)
if not okStore then
	warn("[FillingUp] DataStore unavailable: using NON-PERSISTENT memory store (test only)")
	store = Repository.MemoryStore.new()
	persistent = false
end

local repo = Repository.new({ store = store, jobId = game.JobId ~= "" and game.JobId or "studio", now = os.time })

local expedition = ExpeditionService.new({
	repo = repo,
	remotes = Remotes,
	rewards = RewardService.new(repo, telemetry),
	inventory = InventoryService.new(repo, telemetry),
	rebirth = RebirthService.new(repo, telemetry),
	checkpoints = CheckpointService.new(repo, telemetry),
	tools = ToolService.new(telemetry),
	burial = BurialService.new(),
	telemetry = telemetry,
})

local purchases = PurchaseService.new({
	repository = repo,
	userKeyFor = function(playerId: number)
		local plr = Players:GetPlayerByUserId(playerId)
		return plr and tostring(playerId) or nil
	end,
	log = function(msg)
		warn("[PurchaseService]", msg)
	end,
})
purchases:bind()

Players.PlayerAdded:Connect(function(p)
	if not persistent then
		p:SetAttribute("NonPersistentProgress", true)
	end
end)

expedition:start()

game:BindToClose(function()
	for _, p in Players:GetPlayers() do
		expedition:playerRemoving(p)
	end
end)
