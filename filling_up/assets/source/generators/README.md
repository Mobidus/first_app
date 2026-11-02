# Générateurs paramétriques (T03)

Modules Luau **purs** : aucun service Roblox, aucun `Vector3`/`Color3`. Ils décrivent les pièces ; le jeu
(`RoomGenerator`/`ObjectPool`) les instancie. Exécutables hors Roblox (Lune) pour les contrôles.

API commune :

```luau
local Gen = require(path.to.reception_carton)
local desc = Gen.build({ size = { 10, 8, 4 } })  -- size_studs de config/rooms.json (largeur, profondeur, hauteur)
-- desc = { id, parts = {Part}, collider = Collider?, walkableTop = WalkableTop?, volumes = {Volume}? }
```

- Les dimensions viennent **toujours** de la configuration (`params.size`, ordre JSON largeur × profondeur × hauteur) ;
  le générateur n'embarque aucune taille concurrente et lève une erreur si elle manque.
- `Part.size` et `Part.offset` sont exprimés comme un `Vector3` Roblox : `{ largeur (X), hauteur (Y), profondeur (Z) }`,
  offset depuis le pivot `bottom_center`, avant = `-Z`.
- `Part.color` : hex sRGB ; `Part.material` : nom d'`Enum.Material` ; `Part.shape` : `Block` | `Cylinder` | `Ball` | `Wedge`.
- Tags : `FillCollider` (collision de remplissage, sondée par l'ensevelissement), `Architecture` (structure, exclue
  des sondes), `DecorOnly` (sans collision), `ExitClearance` (volume protégé 8×8×10), `ExitTrigger`.
- Les pièces `DecorOnly` ont `canCollide = false` : la collision jouable est le `collider` simple, séparé du visuel.
- `walkableTop` : zone de réception (taille largeur × profondeur, hauteur, centre) pour la balise menthe « stable ».

Contrôle : `.toolchain/bin/lune run assets/source/generators/_check_generators.luau`
(voir `reports/T03/generators_check.txt`).
