# 0002 — Emplacement et structure du projet

Le dépôt autorisé (`first_app`) contient une application Rails sans rapport. Pour ne rien écraser, le jeu est créé
dans le sous-dossier `filling_up/`, qui contient aussi la copie du dossier de spécification V3 (docs, config, prompts,
backlog, manifeste, scripts). Les chemins des docs (`src/shared/...`, `tests/unit`, `reports/`...) sont relatifs à ce
sous-dossier. Rojo : `default.project.json` (jeu) et `studio-tests.project.json` (jeu + scènes de recette Studio).
Le dossier `src/shared/Domain` ne dépend d'aucun service moteur : il est testé hors Roblox par Lune via
`tests/_harness/Loader.luau`, qui émule `script`/`require(instance)` et `game:GetService` limité aux racines du projet.
