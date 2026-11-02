--!strict
-- Tutorial hints: one short message and, after 5 s of inaction, a ghost trajectory (dotted beam
-- from the carton to the exit). It never teleports the avatar nor validates a jump.
local Net = require(script.Parent.Parent.Net)

local TutorialController = {}

function TutorialController.start()
	Net.on("Hud", function(e)
		if e.type ~= "ghost_path" then
			return
		end
		local cell: CFrame = e.cell
		local folder = Instance.new("Folder")
		folder.Name = "GhostPath"
		local prev: Vector3? = nil
		for _, b in e.points do
			local p = (cell * CFrame.new(b.cx, b.cy + b.sy / 2 + 0.5, b.cz)).Position
			if prev then
				for i = 1, 8 do
					local t = i / 9
					local dot = Instance.new("Part")
					dot.Shape = Enum.PartType.Ball
					dot.Size = Vector3.new(0.5, 0.5, 0.5)
					dot.Anchored = true
					dot.CanCollide = false
					dot.CanQuery = false
					dot.Material = Enum.Material.Neon
					dot.Color = Color3.fromHex("#39E68B")
					dot.Transparency = 0.3
					dot.Position = prev:Lerp(p, t) + Vector3.new(0, math.sin(t * math.pi) * 3, 0)
					dot.Parent = folder
				end
			end
			prev = p
		end
		folder.Parent = workspace
		task.delay(4, function()
			folder:Destroy()
		end)
	end)
end

return TutorialController
