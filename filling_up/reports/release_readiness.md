# Préparation de livraison (T23)

**Verdict : non publiable.** Le projet se construit et sa logique est testée, mais les portes qualité moteur, mobile
et 5 h ne sont pas franchies. Aucune publication n'est demandée tant que T06 à T22 n'ont pas leurs preuves Studio.

## Ce qui est livré

| Élément | Emplacement | Preuve |
|---|---|---|
| Fichier de jeu construit | `build/FillingUp.rbxlx` | `reports/checks/build.json` (Rojo 7.5.1, 74 scripts compilés) |
| Place de recette Studio | `rojo build studio-tests.project.json -o build/StudioTests.rbxlx` | scènes `tests/studio/*` |
| Configurations | `config/*.json` → `src/shared/GeneratedConfig` | `reports/checks/config.json` |
| Sources jeu | `src/` | 16 suites de logique PASS (`reports/checks/unit_*.json`) |
| Assets sources | `assets/source/{design,blender,models,generators}` | `reports/design_handoff.json`, `reports/asset_import.json` |
| Exports | `assets/import/{ui/icons,models}` | idem ; aucun import Roblox |
| Manifeste d'assets | `assets/manifest.json` | 9 modeled, 34 designed, 138 planned, 0 ID inventé |
| Certification salles | `reports/room_certification_{initial,full}.json` | 3 240 + 17 280 salles |
| Endurance logique | `reports/soak_simulated.json`, `reports/performance_timeseries.json` | PASS (simulation) |
| Décisions | `docs/decisions/0001…0014` | — |
| Retour arrière | `docs/operations/rollback.md` | — |
| Problèmes connus | `reports/known_issues.md` | — |

## Portes restantes avant toute demande de publication

1. Lancer `build/StudioTests.rbxlx` dans Studio et exécuter chaque suite (`FU_TEST_SUITE`). Consigner les résultats.
2. Importer Mallow, Loppy et Octo (et le lot initial). Renseigner les `roblox_asset_id` réels. Valider les collisions.
3. Mesurer le contrôleur (T06), injecter la table mesurée et relancer `generation-initial` et `generation-full`.
4. Faire les essais mobiles sur des appareils nommés, et le test d'identification des peluches.
5. Faire tourner une session réelle de 5 h avec un pilote de test, avec des relevés périodiques.
6. Créer les produits Robux de test dans une expérience **de test** autorisée, puis T20.
7. Seulement ensuite, demander l'autorisation explicite de publier et d'activer les ventes.

Coopération et classements à kit standardisé : exclus du MVP (non approuvés).
