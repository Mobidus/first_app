--!nocheck
-- Opens the BUILT place file (not the sources) with @lune/roblox and checks:
--   * expected services/containers and script classes exist,
--   * every Script/LocalScript/ModuleScript compiles with the Luau compiler,
--   * no ModuleScript is empty, GeneratedConfig matches the expected modules.
-- Usage: lune run tools/verify_build.luau build/FillingUp.rbxlx
local fs = require("@lune/fs")
local luau = require("@lune/luau")
local process = require("@lune/process")
local roblox = require("@lune/roblox")
local serde = require("@lune/serde")

local path = process.args[1] or "build/FillingUp.rbxlx"
local game = roblox.deserializePlace(fs.readFile(path))

local report = { file = path, checks = {}, errors = {}, scripts = 0, modules = 0, compiled = 0 }
local function check(name, cond, detail)
	table.insert(report.checks, { name = name, status = cond and "PASS" or "FAIL", detail = detail })
	if not cond then
		table.insert(report.errors, name .. (detail and (": " .. detail) or ""))
	end
end

local rs = game:GetService("ReplicatedStorage")
local sss = game:GetService("ServerScriptService")
local sp = game:GetService("StarterPlayer")
local shared = rs:FindFirstChild("Shared")
check("ReplicatedStorage.Shared exists", shared ~= nil)
check(
	"Shared.GeneratedConfig is a ModuleScript",
	shared and shared:FindFirstChild("GeneratedConfig") and shared.GeneratedConfig.ClassName == "ModuleScript"
)
for _, m in { "Economy", "Rooms", "Runtime" } do
	check("GeneratedConfig." .. m, shared and shared.GeneratedConfig:FindFirstChild(m) ~= nil)
end
local server = sss:FindFirstChild("Server")
check("Server.Main is a Script", server and server:FindFirstChild("Main") and server.Main.ClassName == "Script")
local sps = sp:FindFirstChild("StarterPlayerScripts")
local client = sps and sps:FindFirstChild("Client")
check("Client.Main is a LocalScript", client and client:FindFirstChild("Main") and client.Main.ClassName == "LocalScript")
for _, svc in
	{
		"ExpeditionService",
		"RoomGenerator",
		"WaveDirector",
		"ObjectPool",
		"BurialService",
		"ExitService",
		"RewardService",
		"InventoryService",
		"RebirthService",
		"PlayerProfileRepository",
		"PurchaseService",
		"TelemetryService",
		"CheckpointService",
		"TutorialService",
	}
do
	check("Server.Services." .. svc, server and server.Services:FindFirstChild(svc) ~= nil)
end
for _, ctl in
	{
		"MovementController",
		"CameraController",
		"HUDController",
		"ShopController",
		"SettingsController",
		"ToolController",
		"PlushDeformationController",
		"TutorialController",
		"TutorialShopController",
	}
do
	check("Client.Controllers." .. ctl, client and client.Controllers:FindFirstChild(ctl) ~= nil)
end
for _, fam in { "Reception", "Toys", "Office", "Kitchen", "Garage", "GiantBin" } do
	check("RoomTemplates." .. fam, server and server.RoomTemplates:FindFirstChild(fam) ~= nil)
end
check("Server.Tools.StarterRadar", server and server.Tools:FindFirstChild("StarterRadar") ~= nil)
local gens = game:GetService("ServerStorage"):FindFirstChild("AssetGenerators")
check("ServerStorage.AssetGenerators (T03 parametric generators)", gens ~= nil and #gens:GetChildren() >= 4)

for _, inst in game:GetDescendants() do
	if inst:IsA("LuaSourceContainer") then
		local src = inst.Source
		if inst.ClassName == "ModuleScript" then
			report.modules += 1
		else
			report.scripts += 1
		end
		if #src == 0 then
			check("non-empty " .. inst:GetFullName(), false)
		else
			local ok, err = pcall(luau.compile, src)
			if ok then
				report.compiled += 1
			else
				check("compile " .. inst:GetFullName(), false, tostring(err))
			end
		end
	end
end
report.status = #report.errors == 0 and "PASS" or "FAIL"
print("RESULT_JSON:" .. serde.encode("json", report))
process.exit(#report.errors == 0 and 0 or 1)
