# 0021 — Budget de triangles « haute qualité » (2 novembre 2026)

**Contexte** : l'utilisateur a demandé des « objets de grande qualité » (décision 0017). `docs/02` fixait 100 à 800
triangles pour un objet simple répété. Ce plafond ne permet ni biseaux, ni détails modelés, ni lisibilité de près.

**Décision** :

| Catégorie | LOD0 (proche) | LOD1 (loin) |
|---|---|---|
| Objet de salle (props, canards, gonflables) | 800 à 3 000 tris | ≤ 700 |
| Peluche mini / moyenne | jusqu'à 1 600 / 3 400 tris | ≤ 400 / ≤ 700 |
| Peluche grande / géante, canard géant | jusqu'à 5 000 / 7 000 tris | ≤ 900 / ≤ 1 200 |
| Machine signature (décor) | jusqu'à 8 000 tris | ≤ 1 200 |

* Chaque objet a un LOD1 léger, exporté à part (`<id>_lod1.glb`). Le LOD1 doit vérifier les mêmes contrôles de taille et
  de dessus marchable que le LOD0.
* `max_triangles_near` dans le manifeste porte la valeur de cette décision. Les entrées issues des passes qualité le
  précisent.
* Les objets d'une même famille partagent un atlas de 1 024 px : 1 matériau par objet, 2 au plus pour une vitre.

**Risque NON vérifié** : le coût sur mobile. Une salle XL peut afficher 40 corps dynamiques, environ 120 appuis et
jusqu'à 80 blocs de décor. Si le budget de rendu sur téléphone est dépassé, la première mesure sera de forcer le
LOD1 au-delà de 40 studs (`RenderFidelity` / maillages LOD), avant de toucher aux modèles. À mesurer en Studio
(Microprofiler, appareil réel).
