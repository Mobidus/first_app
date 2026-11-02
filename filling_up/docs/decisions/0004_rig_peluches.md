# 0004 — Rig et déformation des peluches (Mallow, Loppy, Octo)

- **Statut** : retenue ; vérifiée dans Blender ; **non testée dans Roblox** (import bloqué).
- **Date** : 2026-11-02 · **Tâche** : T03 · **Sources** : docs/02 §Contrat du rig, docs/05 §7, `config/runtime.json` → `deformation`.

## Hiérarchie et nommage

Tous les bones sont enfants directs de `Root` (aucune chaîne) : chaque pose se calcule indépendamment depuis la
pose de référence.

| Bone | Rôle | Mallow | Loppy | Octo |
|---|---|---|---|---|
| `Root` | Ancrage à l'origine (pivot bottom_center), **jamais posé** | ✓ | ✓ | ✓ |
| `Belly_ij` (i = colonne X 0..2, j = rangée Y Blender 0..2) | Grille 3 × 3 du plateau/ventre : 9 contrôles de volume | 9 | 9 | 9 |
| Secondaires (≤ 6) | Retard et écartement | `Head`, `Arm_L`, `Arm_R`, `Leg_L`, `Leg_R` (5) | `Head`, `Ear_L`, `Ear_R`, `Feet`, `Tail` (5) | `Arms_N`, `Arms_E`, `Arms_S`, `Arms_W` (4, deux bras chacun) |

`Belly_11` est le contrôle central, sous la balise de réception.

## Interprétation de « racine non déformante »

`Root` porte des poids de skin (les sommets proches du sol) mais **sa transformation reste l'identité en
permanence** : elle ne déforme jamais le maillage et suit la racine physique. C'est ce qui permet d'écraser le
volume en gardant le dessous au sol : un sommet du corps de hauteur z reçoit `(1 − z/4)` sur `Root` et `z/4` sur
la grille de ventre. Une translation verticale `d` des bones de ventre produit donc une échelle verticale uniforme
`1 − d/4` sans enfoncer le dessous dans le sol, avec des translations seulement. Alternative écartée : `Root`
sans poids. Il faudrait alors un bone d'ancrage supplémentaire (au-delà de 9 + 6) ou accepter que la compression
enfonce la peluche dans le sol.

Les sommets des groupes secondaires à moins de 0,6 stud du sol sont aussi partiellement liés à `Root` : pattes et
bras ne traversent jamais le sol. Le test `never_below_floor` passe pour toutes les poses.

## Poids

- Ventre : interpolation barycentrique sur la grille triangulée (3 bones au plus) plus `Root`, soit **4 influences
  au plus**, linéaire par morceaux et continue.
- Groupes secondaires : appartenance douce aux primitives de modélisation (tête, oreilles, membres), mélangée aux
  jonctions, élaguée à 4 influences puis normalisée. Erreur de somme mesurée après réimport : < 2 × 10⁻⁷. Aucun
  sommet orphelin.

## Pourquoi aucune échelle sur `Bone.Transform`

`Bone.Transform` est un `CFrame` : il n'a pas de composante d'échelle, et il n'est pas répliqué. Les
compressions sont obtenues par **translations coordonnées** des 9 bones de ventre (descente, écartement radial
des bones de bord) et par **rotations** des secondaires. Les poses de `pose_library.json` ne contiennent que
`translation`, `rotation_axis` et `rotation_degrees`. `verify_exports.py` lève une erreur si une échelle
apparaît sur un bone posé.

## Poses de démonstration (référence = repos, jamais cumulées)

Valeurs mesurées après réimport du GLB : rapport de hauteur du dessus, largeur et profondeur du corps.

| Pose | Mallow | Loppy | Octo | Limite runtime.json |
|---|---|---|---|---|
| Chute (étirement) | 1,114 | 1,115 | 1,115 | ≤ 1,12 |
| Impact (compression) | 0,727 / 1,066 / 1,100 | 0,726 / 1,094 / 1,059 | 0,726 / 1,037 / 1,055 | hauteur ≥ 0,72 ; élargissement ≤ 1,18 |
| Rebond | 1,050 | 1,055 | 1,050 | (dépassement léger) |
| Appui joueur | 0,978 | 0,978 | 0,978 | dessus ≤ 0,25 stud du collider |

L'intensité est mise à l'échelle par impact (`scale` de 0,2 à 1) : un contact faible n'écrase pas autant qu'une
grande chute. Les durées 0,09 / 0,18 / 0,65 s (plafond 0,90 s) relèvent du `PlushDeformationController`. Elles
ne sont pas incluses dans les fichiers.

## Dérive

100 cycles impact (intensité aléatoire, graine 7) puis retour à la référence : dérive maximale des sommets =
**0,0 stud** sur les trois peluches. Chaque pose est une affectation absolue depuis la référence.

## Collision et dessus utile

Le collider serveur est une boîte simple, séparée du mesh visuel (voir `collision.json` de chaque peluche). Le
mesh visuel est `CanCollide = false`. Il suit la racine côté client et n'est pas soudé ancré à une racine qui
tombe. L'écart entre le dessus visible et le dessus du collider a été mesuré par raycasts sur une grille de
0,25 stud :

- Zone intérieure (1 stud de retrait du bord) : ≤ 0,17 stud au repos et ≤ 0,25 stud en appui joueur (Loppy :
  0,244) → **PASS**.
- Anneau extérieur de 0,5 à 1 stud : jusqu'à 0,34 (Mallow), 0,80 (Loppy) et 0,36 (Octo) stud. Les silhouettes
  arrondies et la tête de Loppy entrent dans le bord de l'empreinte.

**Point ouvert pour T07/T08** : avec les dimensions actuelles de `walkable_top` (8 × 8 et 8 × 7), le bord de 1 stud
de l'empreinte ne respecte pas 0,25 stud. Options : (a) placer la balise de réception et les sockets garantis dans
la zone intérieure ; (b) réduire `walkable_top` dans la config après décision ; (c) carrer davantage les
silhouettes, au détriment de leur lisibilité. Je n'ai pas modifié la configuration.

## Limites

- L'identification par 8 testeurs sur 10 n'a pas été réalisée (NOT_RUN). Loppy reste la silhouette la plus faible :
  le plateau plat de 8 × 7 à hauteur 4 impose un corps très cubique.
- Modélisation faite d'après les briefs textuels canoniques, car les planches Claude Design (T01) étaient produites
  en parallèle. Un rapprochement avec les planches validées est nécessaire.
