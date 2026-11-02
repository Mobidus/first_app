# 0007 — Composition des phases de déformation

`runtime.json` : compression 0,09 s, rebond 0,18 s, amortissement 0,65 s, plafond total 0,90 s. La somme naïve
(0,92 s) dépasse le plafond. L'amortissement est donc ramené à `min(0,65 ; 0,90 − 0,09 − 0,18) = 0,63 s` : l'enveloppe
vaut exactement 1 à 0,90 s, et l'état `supporting` (balise d'appui) n'apparaît qu'ensuite.
Réglages à calibrer dans PlushLab (hypothèses) : vitesse d'étirement maximal 60 studs/s, vitesse d'impact maximal
50 studs/s, dépassement au rebond 6 %, enfoncement sous le joueur 0,15 stud (< 0,25 de tolérance).
La pose est toujours recalculée depuis la référence (translations + rotations, jamais d'échelle de bone). Le serveur
ne lit jamais `PlushPose` (test automatique `plush`).
