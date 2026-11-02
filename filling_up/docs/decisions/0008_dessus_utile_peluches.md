# 0008 — Zone d'appui utile des peluches

Mesure T03 : l'écart dessus visible / collider reste ≤ 0,25 stud dans l'empreinte réduite de 1 stud. Il atteint
0,34 (Mallow), 0,80 (Loppy) et 0,36 (Octo) dans l'anneau de bord, à cause des formes arrondies.
**Décision provisoire** : la balise de réception est centrée et dimensionnée sur l'empreinte réduite de 1 stud. Le
validateur fait atterrir le saut 1 stud à l'intérieur. Les colliders et les `walkable_top` de la config restent
inchangés. **À trancher en Studio (PlushLab)** : soit réduire `walkable_top` dans la config, soit rendre les
silhouettes plus carrées. Loppy reste la silhouette la plus fragile.
