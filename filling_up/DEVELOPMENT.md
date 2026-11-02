# FILLING UP — projet Roblox (exécution du dossier V3)

Le dossier de spécification d'origine reste dans `README.md`, `AGENTS.md`, `docs/`, `config/`, `prompts/`, `tasks/` et
`assets/manifest.json`. Ce fichier décrit le projet construit à partir de lui.

## Démarrer

```bash
tools/bootstrap_toolchain.sh             # Rojo, Lune, StyLua, Selene (cargo) + Blender bpy (pip), versions verrouillées
python3 tools/game_checks.py config      # JSON canoniques -> invariants + modules Luau générés
python3 tools/game_checks.py build       # build/FillingUp.rbxlx + vérification du place construit + lint/format
python3 tools/game_checks.py unit --suite all
python3 tools/game_checks.py soak --simulated-seconds 18000
python3 tools/game_checks.py studio --suite movement   # BLOCKED hors Roblox Studio
```

Ouvrir `build/FillingUp.rbxlx` dans Roblox Studio (ou `rojo serve` + plugin Rojo) pour jouer. Pour la recette :
`rojo build studio-tests.project.json -o build/StudioTests.rbxlx`, puis attribut `Workspace.FU_TEST_SUITE`.

## Architecture

| Dossier | Contenu |
|---|---|
| `src/shared/Domain` | logique pure et déterministe : machine d'expédition, intentions bornées, récompenses (arrondi cumulatif en points de base), économie, renaissance, mutations de profil, génération et validation des salles, vagues, consolidation, ensevelissement, déformation des peluches, outils, tutoriel, checkpoints, résidence des salles |
| `src/shared/GeneratedConfig` | **généré** depuis `config/*.json` (ne pas éditer) |
| `src/server/Services` | adaptateurs moteur : ExpeditionService, RoomGenerator, WaveDirector, ObjectPool, BurialService, ExitService, RewardService, InventoryService, RebirthService, CheckpointService, TutorialService, PlayerProfileRepository, PurchaseService, TelemetryService, Remotes, PropFactory |
| `src/server/Tools` | StarterRadar + ToolService (Radar, Aimant, Ventouse, Parapluie) |
| `src/server/RoomTemplates` | six familles (palettes et machines de la config) |
| `src/client` | contrôleurs : mouvement, caméra, HUD, tutoriel, borne Radar, boutique et renaissance, outils, déformation des peluches, effets, réglages |
| `tests/unit` + `tests/run.luau` | tests de logique exécutés par Lune (`tests/_harness/Loader.luau` émule `script`/`require`) |
| `tests/studio` | scènes et procédures de recette moteur (non exécutées ici) |
| `assets/source` / `assets/import` | planches Claude Design, scripts Blender, .blend, générateurs paramétriques ; exports PNG/GLB/FBX |
| `tools` | préflight, compilateur de config, game_checks, vérification du build, soak, fusion du manifeste, rapports |

## État

Voir `tasks/backlog.json` (statut et critères de chaque tâche), `reports/T00 … T23/summary.json`,
`reports/known_issues.md` et `reports/release_readiness.md`.
