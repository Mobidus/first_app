# Problèmes connus et contrôles bloqués

État au 2 novembre 2026. Les mentions PASS / NOT_RUN / BLOCKED proviennent de `reports/checks/*.json`.

## Bloquants pour une recette jeu

1. **Aucun test moteur (Roblox Studio indisponible).** 17 suites `studio` sont BLOCKED : physique, collisions,
   caméra, mobile, DataStore réel, achats. Les scènes sont prêtes dans `tests/studio/*` (4 automatisées, 8 avec une
   procédure).
2. **Le code moteur n'a jamais été exécuté.** Services serveur et contrôleurs client : les 74 scripts du `.rbxlx`
   compilent en Luau et Selene ne remonte aucune erreur. Mais sans `luau-analyze`, les types ne sont pas vérifiés. Il
   faut s'attendre à des corrections au premier lancement dans Studio (API, timings, ergonomie).
3. **Contrôleur non mesuré (T06).** Les distances des parcours viennent d'un modèle balistique provisoire (décision
   0009). Après MovementLab, il faudra injecter la table mesurée et relancer la certification.
4. **Assets non importés (T03).** Mallow, Loppy et Octo existent en GLB/FBX riggés, mais aucun import Studio n'a été
   fait : tous les `roblox_asset_id` sont `null`. En jeu, les peluches sont des **proxys de diagnostic** (blocs
   colorés marqués `VisualStatus = proxy_not_final_art`), pas l'art final.
5. **Endurance réelle de 5 h : BLOCKED.** Seule la simulation logique (18 000 s, 1 000 salles) passe.
6. **Achats Robux : BLOCKED.** Pas d'identifiant réel, boutique désactivée, aucun prompt possible. Le mock ne valide que
   la logique.

## Écarts et risques identifiés

- **Bords des peluches.** L'écart dessus visible / collider dépasse 0,25 stud dans l'anneau de bord de 1 stud
  (Mallow 0,34 ; Loppy 0,80 ; Octo 0,36). Décision provisoire 0008 : balise sur l'empreinte réduite.
- **Silhouette de Loppy** fragile : son dos plat de 8 × 7 impose un corps cubique.
- **Valise et machine de Réception** : générateur ou proxy au lieu du mesh Blender prévu. Décision à prendre.
- **Doc 04 / config.** Le carton du tutoriel fait 10 × 10 × 4 dans la doc, 10 × 8 × 4 dans la config (la config
  fait foi, décision 0006).
- **Jalons.** Ils sont validés par la hauteur des pieds posés (≥ 25/50/75 % de la cible). Le seuil exact est à
  ajuster en Studio.
- **Détection de l'occupation** des supports dans `WaveDirector` : approximation par position, à profiler.
- **Écritures DataStore.** Chaque mutation est écrite durablement (≈ 4 à 10 écritures par salle). C'est sous les
  quotas pour un joueur, mais à mesurer avec plusieurs joueurs.
- **Repli de génération.** 0,9 % des salles V1 utilisent le repli certifié, surtout `kitchen/V/floor_hatch`,
  `kitchen/S/tailgate` et `garage/S/door`. Elles restent valides, mais le générateur est à améliorer.
- **Outils V1** (8 outils) : visibles mais non achetables, faute d'implémentation.
- **Coopération et classements** : hors MVP, non commencés.
- **Revue humaine des planches (T01) et test d'identification à 8/10** : NOT_RUN.

## Contrôles NON exécutés (jamais PASS)

`luau-analyze --strict` · ouverture du place dans Studio · MovementLab · ReceptionRoom · WaveLab · PlushLab ·
BurialFixtures · TransitionLab · ProfileLab · FirstSessionLab · ToolLab · ResumeLab · PurchaseLab · EndToEndLab ·
mobile · 5 h réelles · revue artistique.
