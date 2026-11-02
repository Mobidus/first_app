# 0006 — Cellule tutoriel

docs/04 décrit « un carton de 10 × 10 × 4 », alors que `config/rooms.json` fixe `reception_carton` à 10 × 8 × 4.
**La config fait autorité** : le carton du tutoriel est le `reception_carton` 10 × 8 × 4. Cellule 24 × 24 × 16,
issue (rebord protégé) à 8 studs, montée sol → carton (4) → rebord (8). Un saut complet depuis le carton monterait la
tête à 16,2 studs, au-dessus d'un plafond de 16 : la cellule a donc une verrière au-dessus du carton et du rebord
(`ceilingOpenings`). Pas de vagues dans la cellule : le carton est une chute structurante scriptée à 0,5 s.
Docs à corriger dans une révision du dossier : 10 × 10 × 4 → 10 × 8 × 4.

**Mise à jour (revue des rendus)** : le carton est centré en z = 0, à 1 stud de la zone d'apparition et collé au rebord.
Le validateur refuse tout solide dans une zone d'apparition (`spawn_obstructed`).
