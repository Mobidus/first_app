# 0018 — Habillage des grandes pièces (2 novembre 2026)

**Constat** : les premiers rendus XL/XV (`reports/room_previews/xl/`, avant habillage) montraient de très grandes
pièces dont le parcours occupe un coin. Le reste du sol et des murs était vide. Une pièce immense et vide donne une
impression de prototype, pas de qualité.

**Décision** : un module d'habillage, `src/shared/Domain/SetDressing.luau`, intervient **après** la validation de
la salle. Il pose trois types d'éléments.
* **Du mobilier collé aux murs**, propre à chaque famille. Réception : banc, plante, fontaine, canapé, panneau
  d'affichage. Jouets : étagère, pile de cubes, caisse, affiche. Bureau : bibliothèque, classeurs, table
  d'imprimante, plante, tableau blanc. Cuisine : plan de travail, frigo, étagère à bocaux. Garage : pneus,
  rayonnages, fûts, panneau à outils. Giant Bin : canette écrasée, cartons, sacs.
  * Chaque meuble compte 2 à 5 blocs et porte une clé `assetKey` (par exemple `decor_bureau_bookcase`), pour être
    remplacé plus tard par un mesh. Aucun ID Roblox n'est créé.
  * Le nombre de meubles suit le périmètre : 3 au minimum, 16 au maximum.
* **Des tapis au sol**, au maximum 3, sans collision.
* **Des panneaux lumineux au plafond**, de 2 à 6, sans collision et placés entre les bouches de vague.

**Garanties** :
* **La disposition ne change pas.** L'habillage utilise son propre flux aléatoire
  (`dressing:<templateId>`). Le parcours, les bouches et les jetons d'une salle restent identiques au bit près.
  Un test le vérifie.
* **Contrôle indépendant.** `RouteValidator.validateDecor` ne réutilise pas la logique de placement. Il vérifie
  qu'aucun élément n'est hors de la pièce, ni dans le sas d'apparition, ni dans le dégagement de sortie 8×8×10. Il
  vérifie aussi qu'aucun élément n'est à moins d'un stud d'un support, ni dans l'espace de tête d'un palier, ni sur
  une trajectoire de saut, ni sous une bouche de vague. Il contrôle enfin le budget de blocs décoratifs
  (`maximum_decorative_blocks_active_room`, bouches comprises).
* **Repli.** Si le contrôle refusait un habillage, la salle sortirait **sans décor**, avec un diagnostic. Elle ne
  sortirait jamais cassée. Sur l'échantillon testé (6 familles × 6 formats × toutes les sorties × 3 graines), il n'y a
  aucun refus.
* **Collisions.**
  * Les meubles sont solides et marqués `Architecture`. Ils sont donc exclus des sondes d'ensevelissement et vus
    comme structurels par les outils.
  * Les éléments muraux, les tapis et les lumières n'ont aucune collision et `CanQuery = false`.
  * Un meuble peut offrir un raccourci mineur : le validateur ne certifie que le parcours requis, qui reste intact.

**Limites (non vérifiées)** :
* L'habillage est fait de blocs colorés à la palette de la famille. C'est un niveau « greybox soigné ». La qualité
  finale viendra des meshes modélisés, qui remplaceront les blocs grâce à `assetKey`.
* Coût sur mobile (instances et ombres) : à mesurer en Studio. Les tapis et les lumières ne projettent pas d'ombre.
* Caméra : un meuble haut collé au mur peut gêner la caméra près d'un mur. Il faudra peut-être exclure ces meubles
  de l'occlusion caméra, à décider en playtest.
