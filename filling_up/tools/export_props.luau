--!nocheck
-- Executes the REAL PropFactory and room templates with @lune/roblox instances (engine-lite) and
-- exports every room prop as a Studio-insertable model: assets/import/models/<propId>.rbxm.
-- This validates PropFactory's property names / value types against Roblox's reflection data and
-- produces the primitive exports planned in the manifest. It is not a physics or render test.
-- Usage: lune run tools/export_props.luau
local fs = require("@lune/fs")
local roblox = require("@lune/roblox")
local serde = require("@lune/serde")
local process = require("@lune/process")
local Loader = require("../tests/_harness/Loader")
Loader.enableEngineLite()

local Config = Loader.require("src/shared/GeneratedConfig")
local PropFactory = Loader.require("src/server/Services/PropFactory")
local templates = {
	reception = "Reception",
	toy = "Toys",
	bureau = "Office",
	kitchen = "Kitchen",
	garage = "Garage",
	pool = "Pool",
	bin = "GiantBin",
}

local report = { exported = {}, failures = {}, kind = "engine_lite_build_and_export" }
fs.writeDir("assets/import/models")
for _, fam in Config.Rooms.families do
	local okT, tpl = pcall(Loader.require, "src/server/RoomTemplates/" .. templates[fam.id])
	if not okT then
		table.insert(report.failures, { item = "template " .. fam.id, error = tostring(tpl) })
		tpl = nil
	end
	for _, p in fam.props do
		local ok, model = pcall(PropFactory.create, p.id, tpl)
		if not ok then
			table.insert(report.failures, { item = p.id, error = tostring(model) })
			continue
		end
		-- structural checks on the built instance tree
		local collider = model.PrimaryPart
		local col = p.collider.size_studs
		local sizeOk = collider
			and math.abs(collider.Size.X - col[1]) < 1e-6
			and math.abs(collider.Size.Y - col[3]) < 1e-6
			and math.abs(collider.Size.Z - col[2]) < 1e-6
		local onlyColliderCollides = true
		local parts = 0
		for _, d in model:GetDescendants() do
			if d:IsA("BasePart") then
				parts += 1
				if d ~= collider and d.CanCollide then
					onlyColliderCollides = false
				end
			end
		end
		if not sizeOk then
			table.insert(report.failures, { item = p.id, error = "collider size differs from config collider.size_studs" })
		end
		if not onlyColliderCollides then
			table.insert(report.failures, { item = p.id, error = "a visual part collides (only the simple collider may)" })
		end
		if not collider:HasTag("FillCollider") then
			table.insert(report.failures, { item = p.id, error = "collider not tagged FillCollider" })
		end
		local path = "assets/import/models/" .. p.id .. ".rbxm"
		fs.writeFile(path, roblox.serializeModel({ model }))
		local back = roblox.deserializeModel(fs.readFile(path))
		table.insert(report.exported, {
			id = p.id,
			path = path,
			parts = parts,
			visual = model:GetAttribute("VisualStatus") or "generator",
			roundtrip = back[1].Name == p.id,
		})
	end
end
report.status = #report.failures == 0 and "PASS" or "FAIL"
report.count = #report.exported
fs.writeFile("reports/T03/props_rbxm_export.json", serde.encode("json", report, true))
print(string.format("%s  %d props exported, %d failures", report.status, report.count, #report.failures))
for _, f in report.failures do
	print("FAIL " .. f.item .. ": " .. f.error)
end
process.exit(#report.failures == 0 and 0 or 1)
