# FILLING UP

## Dossier de développement autonome V3

Ce dossier spécifie un jeu Roblox à développer. Il contient les règles, les catalogues chiffrés, les briefs d'assets, les prompts Claude Design, le contrat technique et les tâches de réalisation. Il ne contient pas encore un jeu terminé ni des assets importés dans Roblox.

La règle centrale est définitive : les objets continuent à remplir la salle ; être réellement enseveli peut mettre le joueur KO. Aucun chronomètre indépendant ni pourcentage global de remplissage ne provoque la défaite. Sortir conduit immédiatement à une nouvelle salle, sans dernière salle programmée. Une expédition peut durer cinq heures et plus si le joueur survit.

## Ordre de lecture

1. `AGENTS.md` : instructions à l'IA exécutante et limites d'autorité.
2. `docs/01_PRODUIT_ET_PARCOURS.md` : règles canoniques et premiers instants.
3. `docs/02_ASSETS_ET_CLAUDE_DESIGN.md` : première phase de conception et fabrication des assets.
4. `docs/03_ECONOMIE_ET_OBJETS.md` : tous les outils, achats, gains et renaissances.
5. `docs/04_UNIVERS_ET_SALLES.md` : univers, objets, tailles et sorties.
6. `docs/05_ARCHITECTURE_ET_TESTS.md` : contrats logiciels et tests Roblox.
7. `docs/06_PLAN_AUTONOME.md` et `tasks/backlog.json` : exécution par dépendances.
8. `docs/07_SOURCES_ET_DECISIONS.md` : références officielles et décisions de cette version.

Les valeurs structurées de `config/` font autorité pour l'équilibrage. `assets/manifest.json` fait autorité sur les identifiants logiques et l'état de production des assets. Aucun identifiant Roblox n'est inventé. Les valeurs nulles signifient « non importé / non configuré ».

## Démarrage de l'IA

Ouvrir ce dossier dans Claude Code ou un agent capable de modifier des fichiers. Lui transmettre `prompts/00_MISSION_IA.md`. L'agent commence par T00 puis la phase Claude Design. Il consigne les outils disponibles, crée le projet de jeu dans un sous-dossier de travail et complète le backlog au fur et à mesure. Une tâche n'est pas terminée parce que son code a été écrit : ses preuves de validation doivent exister.

Les commandes suivantes vérifient uniquement la cohérence de ce dossier, pas le jeu Roblox :

```bash
python3 scripts/validate_pack.py
python3 scripts/simulate_economy.py
```

Le plan distingue explicitement les tests de logique, les tests de physique dans Studio, les essais sur mobile et l'endurance réelle de cinq heures. Ces derniers restent à exécuter pendant le développement.

## Périmètre retenu

Prototype : une salle, quatre objets, un ours en peluche animé, un Radar, un KO et une transition.

MVP : solo, trois familles de salles, tailles variées, trois sorties au minimum, quatre outils et leurs améliorations, Coins, permis, renaissances, sauvegarde et reprise.

V1 : six familles, douze outils, vingt-quatre achats cosmétiques en Coins, offres Robux déterministes, variations profondes et qualité complète des assets. Coopération et compétition standardisée viennent après validation du cœur solo.

## Ce qui n'est pas autorisé par le dossier seul

Publier publiquement le jeu, activer des produits payants, dépenser des Robux, acheter des services ou assets, installer un connecteur privilégié, fournir des identifiants, modifier un jeu existant de production. L'agent prépare ces opérations puis demande l'autorisation appropriée.

