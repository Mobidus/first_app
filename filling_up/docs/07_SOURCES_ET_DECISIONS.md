# 07 Sources et décisions de production

## Sources officielles vérifiées le 2 novembre 2026

Les règles de jeu, prix et budgets du dossier sont des choix de conception. Les références ci-dessous documentent les capacités des outils et les contraintes de plateforme. L'IA exécutante doit vérifier les changements éventuels avant l'import, les achats et la publication.

| Référence | Source | Usage dans le dossier |
|---|---|---|
| S1 | https://support.claude.com/en/articles/14604416-get-started-with-claude-design | Exports et passage de Claude Design vers le développement |
| S2 | https://www.anthropic.com/news/claude-for-creative-work | Scripts et outils de fabrication, notamment Blender |
| S3 | https://create.roblox.com/docs/studio/importer | Import des modèles et images dans Studio |
| S4 | https://create.roblox.com/docs/art/modeling/rigging | Rig et skinning, séparation apparence et collision |
| S5 | https://create.roblox.com/docs/reference/engine/classes/Bone | Transformations de bones et réplication |
| S6 | https://create.roblox.com/docs/production/monetization/passes | Droits payants permanents |
| S7 | https://create.roblox.com/docs/production/monetization/developer-products | Achats répétables et délivrance par reçu |
| S8 | https://create.roblox.com/docs/reference/engine/classes/MarketplaceService | API de prix et de transactions |
| S9 | https://create.roblox.com/docs/production/monetization/regional-pricing | Prix applicables au joueur et affichage dynamique |
| S10 | https://create.roblox.com/docs/production/monetization/paid-random-items | Règles du hasard payant, y compris via monnaie achetable |
| S11 | https://create.roblox.com/docs/cloud-services/data-stores | Persistance et séparation des données de test |
| S12 | https://create.roblox.com/docs/workspace/collisions | Collisions et limites des événements de contact |
| S13 | https://rojo.space/docs/v7/project-format/ | Structure d'un projet Rojo |

## Conséquences techniques à appliquer

Les packs de Coins sont des developer products répétables. Les offres cosmétiques permanentes utilisent des passes ou une possession permanente explicitement gérée. L'attribution des packs doit passer par `ProcessReceipt` côté serveur et une écriture durable idempotente ; la fermeture du dialogue d'achat ne constitue pas une preuve de paiement. [S6, S7]

Les prix 49, 99, 149, 199, 249, 299, 399 et 499 Robux sont des prix de base proposés. L'interface de production doit récupérer le prix réellement applicable. L'API consultée indique `GetProductInfoAsync` et marque l'ancienne méthode `GetProductInfo` comme dépréciée. Vérifier l'API de la version utilisée avant implementation. [S8, S9]

Le projet n'inclut aucun achat aléatoire. Acheter des Coins avec des Robux puis les dépenser dans un coffre aléatoire ne contournerait pas les règles du hasard payant. Il n'y a donc ni roulette, ni œuf payant, ni fusion à probabilité dans ce catalogue. [S10]

Les données de Studio doivent utiliser une expérience de test distincte, pas une configuration capable d'écraser les comptes de production. Les objets gagnés et achetés sont persistants ; les événements purement visuels ne font pas autorité. [S11]

## Décisions qui remplacent les anciennes versions

| Ancienne possibilité | Décision V3 |
|---|---|
| Trois salles puis retour au lobby | Expédition continue, arrêt volontaire ou KO |
| Durée limitée et saturation globale mortelle | Vagues continues, KO géométrique local, pas de chrono indépendant |
| Endless comme mode ultérieur | Enchaînement sans dernière salle au cœur du produit |
| Premier achat après plusieurs minutes | Radar financé par le tutoriel et utilisé dans les trente secondes visées |
| Prestige assimilé à un simple niveau XP | Niveau de compte distinct de renaissances volontaires à permis |
| Perte de progression économique | Coins, possessions et permis conservés ; profondeur seule recommence |
| Objets principalement génériques | Catalogue identifiable, trois peluches déformables et six machines signature |
| Coopération immédiate | Solo d'abord ; règles multijoueur définies et testées séparément |

## Ce que le dossier ne prouve pas encore

Les scripts fournis peuvent vérifier la cohérence du catalogue, les coûts, les dépendances et les simulations de Coins. Ils ne prouvent ni la sensation du saut, ni la réussite d'import des peluches, ni les performances sur mobile, ni la rétention commerciale. Ces preuves doivent être produites pendant les tâches du backlog. La livraison d'un cahier des charges n'est pas la livraison d'un jeu déjà testé.

