# 0003 — Unités et axes des exports 3D (T03)

- **Statut** : retenue pour la production ; **mesure dans Roblox Studio NON effectuée** (import bloqué).
- **Date** : 2026-11-02 · **Tâche** : T03 · **Réversible** : oui (ré-export par script).

## Contexte

Les gabarits de `config/rooms.json` sont exprimés en studs (largeur × profondeur × hauteur). Les peluches sont
fabriquées dans Blender 5.2.3 (module `bpy`, headless) puis exportées en GLB (glTF 2.0) et FBX. glTF déclare le
mètre comme unité ; l'importeur 3D de Roblox Studio propose un réglage d'unité du fichier au moment de l'import.
La convention souvent citée « 1 stud ≈ 0,28 m » sert à l'échelle physique et avatar de Roblox ; elle n'a **pas pu
être revérifiée** ici : la documentation `create.roblox.com` est refusée par le proxy réseau du conteneur (403).

## Décision

1. **1 unité Blender = 1 unité glTF/FBX = 1 stud.** Les fichiers sont produits à l'échelle du jeu : Mallow mesure
   11,84 × 9,81 × 4,91 unités pour une enveloppe de 12 × 10 × 5 studs.
2. À l'import dans Studio, choisir l'unité de fichier **Studs** (ou l'équivalent « pas de conversion »). Ne pas
   appliquer de facteur 0,28 ou 3,57 implicite.
3. **Axes** : Blender Z = hauteur, X = largeur, Y = profondeur. Le glTF convertit (x, y, z) → (x, z, −y), donc
   l'avant Roblox (−Z, `LookVector`) correspond à **+Y Blender**. Le FBX est exporté avec `axis_forward = -Z`,
   `axis_up = Y`. Pivot `bottom_center` : origine au centre de l'empreinte, au sol.
4. **Contrôle obligatoire après import réel** (critère T03 encore `NOT_RUN`) : la boîte englobante du MeshPart
   importé doit valoir (X, Y, Z) ≈ (12,10 ; 4,95 ; 10,07) pour Mallow, (10,14 ; 7,02 ; 8,14) pour Loppy et
   (12,00 ; 4,98 ; 12,00) pour Octo (passe qualité du 2 novembre 2026), à ±0,05 stud. Un facteur ×0,28 ou ×3,57 indique une mauvaise unité
   d'import : corriger le réglage, pas le modèle.

## Ce qui est prouvé et ce qui ne l'est pas

- Prouvé (Blender) : les exports rouverts dans une scène vide gardent les dimensions, le rig (15 ou 14 bones), les
  poids normalisés et ≤ 4 influences (`reports/asset_import.json`).
- Non prouvé : l'interprétation de l'unité par l'importeur Roblox, la conservation du skin dans un MeshPart,
  l'orientation finale et la création des `Bone`. Ces points restent à mesurer dans Studio.
