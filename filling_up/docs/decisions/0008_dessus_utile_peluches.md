# 0008 — Zone d'appui utile des peluches

Mesure T03 : l'écart dessus visible / collider reste ≤ 0,25 stud dans l'empreinte réduite de 1 stud. Il atteint
0,34 (Mallow), 0,80 (Loppy) et 0,36 (Octo) dans l'anneau de bord, à cause des formes arrondies.
**Décision provisoire** : la balise de réception est centrée et dimensionnée sur l'empreinte réduite de 1 stud. Le
validateur fait atterrir le saut 1 stud à l'intérieur. Les colliders et les `walkable_top` de la config restent
inchangés. **À trancher en Studio (PlushLab)** : soit réduire `walkable_top` dans la config, soit rendre les
silhouettes plus carrées. Loppy reste la silhouette la plus fragile.

**Mise à jour du 2 novembre 2026 (passe qualité Jouets) : décision close.** Les silhouettes ont été rendues plus
carrées : ventre de Mallow, tête d'Octo, panneau dorsal plat à liseré pour Loppy. L'écart dessus visible / collider,
mesuré sur toute l'empreinte (anneau de bord compris), est maintenant de 0,148 (Mallow), 0,114 (Loppy) et 0,130
(Octo) au repos en LOD0, et de 0,128 à 0,153 en LOD1. C'est sous la tolérance de 0,25
(`reports/T03/props_toy_verify.json`). Les `walkable_top` de la config restent inchangés. La balise de réception
peut revenir à l'empreinte complète ; la vérification en Studio (PlushLab) reste à faire.
