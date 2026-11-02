# Passation : reprendre FILLING UP sur le Mac (Roblox Studio local)

À lire en premier par toute nouvelle session Claude. Branche : `claude/sleepy-hamilton-49n50g`.

## Où en est le projet

- Le dossier de spécification V3 et le jeu sont dans `filling_up/`. Le cahier de règles est dans `AGENTS.md`, et les
  docs, configs et backlog dans `docs/`, `config/` et `tasks/backlog.json`.
- **Fait** : T00, T02, T04 et T05 sont terminées ; les autres tâches sont `blocked`, presque toutes faute de Studio.
  Elles disposent de 185 tests de logique ou d'intégration qui passent, d'un build Rojo et d'un soak simulé
  (`reports/checks/`).
- **Assets** : planches Claude Design dans `assets/source/design/` ; Mallow, Loppy et Octo riggés en GLB/FBX dans
  `assets/import/models/` ; 48 objets exportés en `.rbxm`. Aucun import Roblox : tous les `roblox_asset_id` valent
  `null`.
- **Limites et prochaines portes** : `reports/known_issues.md` et `reports/release_readiness.md`. Décisions :
  `docs/decisions/0001…0016`.

## Prochaines actions (ordre de priorité)

1. **T06 MovementLab** : ouvrir `build/StudioTests.rbxlx`, attribut `Workspace.FU_TEST_SUITE = "movement"`, puis Run.
   Recopier le tableau `{rise, reach}` mesuré dans `reports/movement_calibration.json`. L'injecter via
   `JumpModel.setMeasuredTable`, puis relancer `python3 tools/game_checks.py unit --suite generation-initial` et
   `generation-full`.
2. Suites `burial`, `plush` et `transitions` (même mécanisme). Consigner les lignes `STUDIO_RESULT_JSON:` dans les
   rapports nommés par le backlog.
3. Importer `toy_plush_mallow.fbx` avec l'importeur 3D (rig conservé). Remplacer le proxy dans `PropFactory`
   (modèle `PlushVisual`). Mesurer la boîte englobante (12 × 5 × 10 studs attendus).
4. Jouer le parcours manuel de `STUDIO_QUICKSTART.md` §3, corriger les erreurs de la fenêtre Sortie, puis relancer
   `python3 tools/game_checks.py build` et `unit --suite all`.
5. Mettre à jour `tasks/backlog.json` avec `python3 tools/write_task_reports.py`, après avoir ajouté les preuves
   Studio dans `TASKS`.

## Règles à respecter (extrait d'AGENTS.md)

- Aucune publication, aucune vente, aucune dépense de Robux sans autorisation explicite de l'utilisateur.
- Un identifiant Roblox absent reste `null`, et un test non exécuté reste `NOT_RUN`, jamais `PASS`.
- Pas de KO lié au temps ni au remplissage global. Les Coins viennent du serveur et de la config.

## Outils sur le Mac

```bash
cd first_app/filling_up
tools/bootstrap_toolchain.sh   # Rojo 7.5.1, Lune 0.10.1, StyLua, Selene (cargo), venv Blender bpy
.toolchain/bin/rojo serve      # synchronisation en direct avec le plugin Rojo dans Studio
```
