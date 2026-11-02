--!strict
-- Comfort settings: reduced effects (plush deformation & cosmetic FX off, danger info kept),
-- language FR/EN, ghost hints. Stored locally for the session; gameplay results never depend on
-- them (deformation is visual only).
local Net = require(script.Parent.Parent.Net)

local SettingsController = {}

SettingsController.values = { reducedEffects = false, language = "fr", ghostHints = true }

function SettingsController.start()
	Net.on("State", function(s)
		if s.settings then
			for k, v in s.settings do
				SettingsController.values[k] = v
			end
		end
	end)
end

function SettingsController.reducedEffects(): boolean
	return SettingsController.values.reducedEffects == true
end

return SettingsController
