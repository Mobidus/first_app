# Instructions de réalisation de FILLING UP

Tu exécutes un cahier des charges de développement, pas une demande de nouvelles idées. Lis les fichiers canoniques avant d'écrire le jeu. Prends les décisions techniques réversibles et locales nécessaires ; consigne-les dans `docs/decisions/`. Ne demande pas à l'utilisateur de choisir à nouveau des prix, couleurs ou règles déjà fixés.

## Autorité des documents

Les dernières instructions explicites de l'utilisateur priment. Ensuite : règles de sécurité et permissions de l'environnement, `docs/01_PRODUIT_ET_PARCOURS.md`, configurations JSON, contrat technique, backlog, briefs visuels. En cas de contradiction détectée, crée une décision explicite et corrige les fichiers concernés avant de continuer. Ne réintroduis jamais une ancienne règle de durée limite ou de mort à 100 % de remplissage.

## Invariants obligatoires

- Les vagues dépendent du temps et continuent à remplir la salle ; ce n'est pas une salle statique attendant des leviers pour exister.
- Le KO dépend d'un ensevelissement physique confirmé ou d'un danger local documenté. Pas de `elapsedTime >= roomLimit` ni de `fillPercent >= 100` comme cause de KO.
- Aucun nombre maximal de salles ne termine normalement une expédition.
- Les sauts requis sont possibles sans outil acheté ; l'entraînement améliore le résultat.
- Première acquisition permanente ciblée dans les trente secondes après prise de contrôle : Radar à 50 Coins, tutoriel rapportant 65 Coins. C'est un objectif d'ergonomie, pas un délai éliminatoire.
- Coins, outils, améliorations, cosmétiques, permis et achats ne sont pas effacés par un KO ou une renaissance.
- Une renaissance est volontaire dans un sas et ne s'achète pas en Robux. Les permis excédentaires restent acquis.
- Les objets ont une identité lisible. Les peluches ont une déformation visible à la chute ; une simple sphère recolorée ne satisfait pas ce brief.
- La collision jouable reste maîtrisée même si le mesh se déforme.
- Les valeurs Coins viennent du serveur et de la configuration. Le client ne peut pas choisir un montant ou valider sa propre victoire.

## Boucle de travail

1. Choisir la première tâche `todo` dont les dépendances sont validées.
2. Écrire ses tests ou scènes de recette avant les comportements critiques.
3. Implémenter le minimum couvrant ses critères, sans ajouter un système hors périmètre.
4. Exécuter les contrôles disponibles. Noter séparément PASS, FAIL et NOT_RUN.
5. Sauvegarder les preuves dans `reports/Txx/` : commandes, sorties, captures utiles, versions, limites.
6. Corriger les échecs. Au troisième échec identique, isoler la cause, réduire le cas et documenter ; ne pas supprimer le test pour passer.
7. Marquer `done` seulement si tous les critères obligatoires de la tâche sont vérifiés. Sinon `blocked` avec une cause précise, puis travailler sur une tâche indépendante autorisée.
8. Mettre à jour `tasks/backlog.json` et le journal de décisions. Préserver les fichiers et changements existants de l'utilisateur.

## Autonomie et arrêts obligatoires

Tu peux écrire et tester le projet dans le répertoire autorisé. Respecte les demandes d'approbation d'installation et d'exécution de l'environnement. Ne cherche pas de mots de passe dans les fichiers. Ne contourne ni authentification ni limite d'accès à Claude Design, Blender ou Roblox.

Si Claude Design est accessible, commence la phase assets avec les prompts fournis. Sinon prépare les fichiers d'entrée et indique le blocage ; ne prétends pas avoir généré les planches. Un greybox local peut avancer en parallèle, mais ne vaut pas validation artistique.

Si Roblox Studio ou un accès de test autorisé n'est pas disponible, exécute les tests de logique et laisse les critères Studio en NOT_RUN. Aucune simulation Python ne prouve la qualité de la physique, des achats réels, du tactile ou d'une session de cinq heures.

Un ID Roblox absent reste `null`. Ne remplace jamais un ID manquant par un nombre plausible. Les boutons Robux restent désactivés tant que les produits réels ne sont pas configurés et testés.

Publication, mise en vente et dépenses nécessitent une autorisation explicite. Aucune bibliothèque payante ou asset tiers non licencié n'est nécessaire au prototype.

## Définition finale de terminé

Un projet constructible, les assets sources et importés, des configs cohérentes, les tests de logique passants, les scènes Studio validées, une preuve d'endurance réelle, un rapport mobile et une liste exhaustive des limites restantes. Ne pas livrer un simple prototype HTML à la place d'un jeu Roblox.

