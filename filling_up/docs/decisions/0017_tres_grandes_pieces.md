# 0017 — Très grandes pièces (demande de l'utilisateur, 2 novembre 2026)

**Demande** : « de très grandes pièces et des objets de grande qualité ». Une instruction explicite de l'utilisateur
prime sur la spécification (AGENTS.md). La spécification d'origine reste valable pour tout le reste.

**Ce qui change (config/rooms.json, source unique) :**
* Deux formats nouveaux par famille, en plus de S/M/L/V :
  * **XL** (grande halle) : environ 1,4 × l'emprise de L et 1,35 × sa hauteur. Exemples : Réception 104 × 88 × 48 ;
    Giant Bin 136 × 124 × 72.
  * **XV** (verticale géante) : environ 1,5 × l'emprise de V et 1,6 × sa hauteur. Exemples : Réception 60 × 60 × 88 ;
    Giant Bin 76 × 72 × 112.
* Les profils de sortie pondèrent la sélection (`format_weights`) : XL ×3, XV ×2, S ×0,5. Les grandes pièces
  dominent l'expédition.
* Les salles pédagogiques passent en XL/XV dès la salle 2 (2, 4, 6, 7, 9 et 10). **La salle 1 et la cellule tutoriel
  restent petites** : l'objectif « compris en moins de 10 secondes » n'est pas négociable.
* **Débit des vagues indexé sur la surface** (`wave_area_scaling`) : facteur = surface ÷ surface du format M, borné
  à 3. Le nombre d'objets par vague est multiplié par ce facteur, et une vague ouvre plusieurs bouches (6 au maximum).
  Sans cela, une pièce ×3 mettrait trois fois plus de temps à se remplir et la pression disparaîtrait.
* **Budget physique inchangé** : 40 corps dynamiques, 120 à 160 colliders. Le surplus de chutes est différé par la
  consolidation. Une pièce géante se remplit donc en partie avec des appuis consolidés, pas avec plus de physique.
* Plafond découpé en tuiles de 8 studs (au lieu de 4) dans les pièces de plus de 4 000 studs² de surface.

**Certifié** : générateur et validateur inchangés. Les formats XL/XV passent la certification (voir
`reports/room_certification_*.json`).

**Risques à mesurer en Studio et sur mobile (non vérifiés)** :
* distance d'affichage et nombre d'instances sur téléphone ;
* caméra (zoom maximal de 28 studs) : le joueur ne voit pas toute la pièce. La sortie reste signalée par sa lumière
  menthe, mais il faudra peut-être un indicateur à l'écran ;
* temps de montée : une sortie de toit en XV fait 25 sauts ou plus. C'est un vrai défi, mais il faut des paliers de
  repos ;
* densité perçue du remplissage malgré le débit indexé. Si elle reste faible, il faudra des « objets XXL »,
  c'est-à-dire des variantes ×2 des objets de remplissage, à décider en playtest.
