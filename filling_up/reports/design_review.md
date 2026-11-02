# Revue de la phase Claude Design (T01) et de la transmission (T02)

Date : 2026-11-02. Rédigé par l'agent exécutant (fork T01/T02). Les statuts proposés ici sont à fusionner par l'agent principal ; `tasks/backlog.json` et `assets/manifest.json` n'ont pas été modifiés par ce fork.

## Ce qui a été fait

- **Canvas Claude Design** : https://claude.ai/artifact/Vb6XnUB54ikWQCQsQ9Twb3. C'est un artifact privé, créé à partir du type « Design », qui correspond à Claude Design dans Claude. Il contient 20 planches, publiées en 24 versions. Il n'est pas partagé : seul son propriétaire peut l'ouvrir tant qu'il n'est pas partagé depuis le menu Share.
- **Sources locales modifiables** (`assets/source/design/`) :
  - `canvas/project/*.dc.html` + `canvas.json` : source exacte de chaque planche publiée.
  - `icons/*_icon.svg` : 12 icônes d'outils vectorielles, également téléversées dans le stockage d'assets du canvas.
  - `design_tokens.json`, `ui_hierarchy.json` (hiérarchie, états, chaînes FR/EN pour une UI Roblox native) et `blob_map.json`.
- **Exports** : `assets/import/ui/icons/<tool>_icon.png`. Ce sont 12 PNG 512 × 512 RGBA à fond transparent, rastérisés localement avec Playwright/Chromium.
- **Contrôles** : `reports/T01/captures/*.png`, soit 20 rendus locaux du HTML statique des planches, et `reports/T01/icons_legibility_64_96.png`.
- **Transmission** : `reports/design_handoff.json` contient l'inventaire des 49 fichiers, chacun ouvert et contrôlé (en-tête PNG et dimensions, parsing SVG et JSON, structure `.dc.html`) avec son sha256. `reports/T02/manifest_updates.json` liste 43 mises à jour de statut proposées.

## Planches produites

| Planche | Contenu | Couverture des prompts |
|---|---|---|
| Main | 8 tokens, 5 matières, 6 balises (couleur + icône), BOB-7 en couleur et en silhouette, règle 60/25/15, typographie | Prompt 01 |
| Gameplay | Écran mobile 16:9. HUD sans chrono, prochaine réception balisée, sortie en arche menthe, alerte de vague, boutons SAUT 132 px et Radar 92 px | Prompt 01 |
| Plush_Mallow / Loppy / Octo | Face, profil, dos, trois-quarts, dessus avec zone d'appui, silhouette noire à côté d'un avatar de 5 studs, 4 poses (repos, chute ×1,12, impact ×0,72 / ×1,18, rebond), rig (racine, 9 contrôles de ventre, 6 secondaires), tableau des dimensions issu de `config/rooms.json`, matières et coutures | Prompt 02 |
| Room_Reception / Toys / Office | Perspective caméra avec avatar, vue de dessus format M, coupe entrée → 3 appuis → sortie, 8 objets avec id, taille, comportement et balise, machine signature, sorties porte / fenêtre / toit avec volume 8 × 8 × 10, gabarits S/M/L/V | Prompt 03 |
| Room_V1 | Planche légère Cuisine / Garage / Giant Bin : palettes, esquisse de la machine, objets **en texte seulement**, sorties | Prompt 03 (partiel) |
| Tools | 12 outils : icône, silhouette, état équipé, statistiques des 3 rangs et coûts des rangs II/III, **prix exacts** de `config/economy.json` (50 … 10 000) | Prompt 04 (vue 3/4 partielle) |
| Screen_* (10) | Borne Radar (65 gagnés, prix 50, reste 15, « Acheter 50 Coins » / « Continuer », sans compte à rebours ni offre Robux) en version 16:9 et compacte. Inventaire, boutique Coins, boutique Robux « Boutique indisponible », KO avec « Recommencer (gratuit) », sauvegarde/reprise, renaissance (326 permis → 4 rangs, 250 dépensés, 76 restants, +16 %) et sa confirmation. États : chargement, erreur réseau, Coins insuffisants, possédé, indisponible, DÉGAGE-TOI | Prompt 04 |

## Contrôles effectués (PASS)

- **Palette** : les seules couleurs de base sont les 8 tokens de `docs/02`, plus les palettes de salle de `config/rooms.json`. Chaque balise combine une couleur et une forme.
- **Contraste WCAG** (calculé) :
  - Bleu nuit sur crème 12,0 ; sur blanc 13,0 ; sur jaune 9,98 ; sur menthe 7,96 ; sur cyan 7,68 ; sur corail 4,54. Crème sur bleu nuit 12,0.
  - Le rose (4,32 avec du bleu nuit) n'est jamais un fond de texte.
  - Le blanc sur violet (4,38) est réservé à l'étoile graphique.
- **Cibles tactiles** : tous les boutons des maquettes font au moins 48 px de haut (CTA principaux de 64 à 80 px, SAUT 132 px, outil 92 px). Les écrans compacts laissent la zone de saut libre.
- **Lisibilité des icônes à 64 et 96 px** : vérifiée visuellement sur `icons_legibility_64_96.png`. Les silhouettes du Mini-pont et du Grappin sont les plus faibles, mais restent distinctes. À retravailler si le test d'identification échoue.
- **Règles respectées** : aucun chrono de défaite, aucune offre Robux dans le tutoriel, aucune résurrection payante, aucun hasard payant. Les produits Robux sont tous marqués « Indisponible » et leurs prix sont présentés comme des prix de base proposés.
- **Prix et statistiques** : recopiés depuis `config/economy.json` (outils, rangs, coûts II/III, coûts de renaissance 40/55/70/85/100) et `config/rooms.json` (tailles, colliders, comportements, palettes, gabarits).
- **Contenu tiers** : tous les dessins sont des SVG/HTML originaux écrits pour ce projet. Aucune franchise ni personnage sous licence. Polices Google Fonts (Fredoka, Nunito, licence OFL), chargées par lien et non embarquées.
- **Existence des fichiers** : chacun des 49 fichiers de `design_handoff.json` a été ouvert et contrôlé par script ; une erreur aurait fait échouer le script.

## Écarts et limites (pas de PASS)

1. **Aucun modèle 3D** : les planches sont des références 2D. Les statuts proposés plafonnent à `designed`, et `roblox_asset_id` reste `null` partout.
2. **Vues 3/4 des outils** : il s'agit de l'icône inclinée par CSS, pas d'une vraie vue de modèle. Les 12 assets `tool` (3D) restent `planned`.
3. **Familles V1** : la planche est légère. Les 24 objets Cuisine/Garage/Giant Bin ne sont décrits qu'en texte et restent `planned`. Les 3 machines V1 n'ont qu'une esquisse et restent `planned`.
4. **Icônes d'état `ui_*` et cosmétiques** : les icônes d'état sont dessinées dans les planches, mais aucun fichier séparé n'existe. Elles restent `planned`.
5. **Rendu des captures** : les captures de `reports/T01/captures` sont des rendus locaux du HTML statique, sans le moteur du canvas. Elles correspondent au contenu publié, mais ne sont pas des captures du canvas en ligne.
6. **Export ZIP natif de Claude Design** : non utilisé. Les sources exactes du canvas sont conservées localement, ce qui couvre le besoin de transmission.
7. **Proportions des peluches** : les vues sont cohérentes avec l'échelle de 20 px par stud, mais dessinées à la main. Les profils et les 3/4 sont approximatifs. Le modeleur doit s'appuyer sur `size_studs` et `collider`, pas sur des mesures relevées dans l'image.
8. **Interprétation de posture à confirmer** : Mallow, Loppy et Octo sont couchés, avec le dos ou le sommet jouable à h = 4. Les vues présentent l'avant en −Z, conformément au manifeste.

## NOT_RUN

- Test d'identification des silhouettes (au moins 8 testeurs sur 10 reconnaissent l'ours, le lapin et la pieuvre) : **NOT_RUN**, il faut des testeurs humains.
- Revue humaine de la direction artistique et validation des planches : **NOT_RUN**.
- Lisibilité sur appareils mobiles réels : **NOT_RUN** (seules les maquettes ont été contrôlées).

## Statut proposé

- **T01** : `blocked`, pas `done`. Les livrables de conception existent avec leur provenance, mais deux critères ne sont pas remplis :
  - Les vues 3/4 réelles des outils et les planches complètes V1 manquent ; c'est réparable par une nouvelle passe Claude Design.
  - La revue humaine (identification, validation de la direction artistique) n'a pas été faite ; c'est le blocage réel.
- **T02** : `done` pour le lot activé, à condition que l'agent principal fusionne `reports/T02/manifest_updates.json` :
  - Chaque fichier inventorié existe et a été ouvert.
  - Les références et les modèles sont distingués.
  - `assetId` reste `null`.
  - Les entrées futures restent `planned`.
