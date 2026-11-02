--!strict
-- Short in-game strings FR / EN (texts are never baked into icons).
local Strings = {
	fr = {
		climb_and_exit = "GRIMPE ET SORS",
		climb = "GRIMPE",
		dig_out = "DÉGAGE-TOI",
		buy_coins = "Acheter %d Coins",
		continue = "Continuer",
		owned = "Possédé",
		insufficient = "Il manque %d Coins",
		locked_rooms = "Après %d salles terminées",
		unavailable = "Bientôt",
		robux_unavailable = "Boutique indisponible",
		ko_title = "KO",
		ko_kept = "Coins, outils, permis et achats conservés",
		restart = "Recommencer",
		saving = "Sauvegarde…",
		saved = "Sauvegardé",
		save_failed = "Sauvegarde impossible : réessaie",
		save_and_quit = "Sauvegarder et quitter",
		loading_next = "Préparation de la salle suivante…",
		rebirth = "Renaissance",
		rebirth_restart = "Tu repars à la salle 1",
		rebirth_kept = "Conservés : Coins, outils, améliorations, cosmétiques et achats",
		rebirth_confirm = "Confirmer",
		network_error = "Connexion instable : action non effectuée",
		room_label = "%s · salle %d",
		radar = "Radar",
		permanent = "Permanent",
	},
	en = {
		climb_and_exit = "CLIMB AND EXIT",
		climb = "CLIMB",
		dig_out = "DIG OUT",
		buy_coins = "Buy %d Coins",
		continue = "Continue",
		owned = "Owned",
		insufficient = "%d Coins missing",
		locked_rooms = "After %d completed rooms",
		unavailable = "Coming soon",
		robux_unavailable = "Shop unavailable",
		ko_title = "KO",
		ko_kept = "Coins, tools, permits and purchases kept",
		restart = "Restart",
		saving = "Saving…",
		saved = "Saved",
		save_failed = "Save failed: try again",
		save_and_quit = "Save and quit",
		loading_next = "Preparing the next room…",
		rebirth = "Rebirth",
		rebirth_restart = "You restart at room 1",
		rebirth_kept = "Kept: Coins, tools, upgrades, cosmetics and purchases",
		rebirth_confirm = "Confirm",
		network_error = "Unstable connection: action not done",
		room_label = "%s · room %d",
		radar = "Radar",
		permanent = "Permanent",
	},
}

function Strings.get(lang: string?, key: string, ...: any): string
	local t = (Strings :: any)[lang or "fr"] or Strings.fr
	local s = t[key] or Strings.fr[key] or key
	if select("#", ...) > 0 then
		return string.format(s, ...)
	end
	return s
end

return Strings
