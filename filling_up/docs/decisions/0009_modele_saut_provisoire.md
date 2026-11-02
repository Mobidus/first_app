# 0009 — Modèle de saut provisoire (avant T06)

Aucune mesure Studio n'est possible ici. Le générateur utilise un modèle balistique dérivé de `runtime.player`
(16 studs/s, saut 7,2, g 196,2), soit une portée à plat de 8,67 studs. Il est borné deux fois :
* portée requise ≤ `maximum_required_gap_ratio` (0,65 à 0,85) × portée à la hauteur considérée ;
* montée requise ≤ 75 % de la hauteur de saut (5,4 studs).
`JumpModel.setMeasuredTable` remplacera la portée analytique par la table mesurée de MovementLab. Les certifications
de génération devront alors être relancées. Tant que T06 n'est pas fait, aucune distance n'est considérée validée
pour le joueur réel.
