# 0019 — Peluches de plusieurs tailles (demande de l'utilisateur, 2 novembre 2026)

**Demande** : « refais d'autres modèles, plein de peluches de tailles différentes, de haute qualité ». Une
instruction explicite de l'utilisateur prime sur la spécification (AGENTS.md).

**Ce qui change (config/rooms.json, famille Jouets)** : 8 peluches s'ajoutent aux 3 existantes, réparties en quatre
tailles (`size_tier`).

| Taille | Peluches | Collider (l × p × h) | Rôle |
|---|---|---|---|
| mini | Poussin Pipou, Hamster Mochi, Poisson Bulle | 4×4×3, 5×4×3, 5×3×3 | remplissage des vagues seulement |
| medium | Dino Grumf, Mouton Nuage (rebond ×1,12) | 8×8×4, 8×7×4 | remplissage et appuis |
| large | Morse Balto, Chat Ronron | 12×12×6, 12×10×6 | appuis et remplissage, formats L/V/XL/XV |
| giant | Baleine Bobine | 18×16×8 | appui seulement, formats XL/XV, `wave_drop: false` |

**Règles** :
* **Minis.** Leur dessus est sous `minimum_required_landing_short_side_studs` (7). Le générateur ne les choisit
  donc jamais comme appui requis : ce sont des objets de remplissage.
* **Champ facultatif `formats`.** Il limite un objet à certains formats de salle : une baleine de 18 studs n'a pas
  sa place dans une salle S.
* **Champ facultatif `wave_drop: false`.** Il réserve un objet aux appuis : la baleine n'est jamais lâchée par une
  bouche de 8 studs.
* **Nombre d'objets par famille.** La règle « 8 objets par famille » devient un minimum (`compile_config.py`).
* **Budget physique inchangé** : 40 corps dynamiques. Les minis remplissent donc moins vite par corps simulé. La
  densité perçue est à juger en playtest.
* **Modèles.** Ils sont construits dans Blender à partir de code (`assets/source/blender/build_plush_v2_*.py`), avec
  le même rig que Mallow : `Root` + 9 bones `Belly_xz` + bones secondaires. La déformation côté client fonctionne
  donc sans changement.
* **Import Studio.** Un modèle importé dans `ServerStorage/ImportedMeshes/<id>` remplace automatiquement le bloc
  de remplacement (`PropFactory`). Voir STUDIO_QUICKSTART.md, section 3 bis.

**Vérifié hors Studio** : tests `plush-tiers` :
* jamais de mini comme appui ;
* grandes peluches seulement en L/V/XL/XV ;
* baleine seulement en XL/XV, présente au moins une fois et jamais lâchée par une vague ;
* minis présentes dans les vagues dès les premières salles Jouets.

**NON vérifié** : rendu et déformation dans Roblox, coût mobile, lisibilité des minis à la caméra par défaut, test
d'identification à 8 sur 10.
