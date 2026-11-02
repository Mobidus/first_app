# Lancer FILLING UP et ses tests dans ton Roblox Studio

## 0. Récupérer les fichiers

Sur ton ordinateur, dans un terminal :

```bash
git clone -b claude/sleepy-hamilton-49n50g https://github.com/mobidus/first_app.git
```

Les fichiers à ouvrir sont dans `first_app/filling_up/build/` :
- `FillingUp.rbxlx` : le jeu ;
- `StudioTests.rbxlx` : le jeu avec les scènes de recette.

## 1. Préparer Studio (une seule fois)

1. Ouvre `StudioTests.rbxlx` (Fichier → Ouvrir depuis un fichier).
2. Pour tester les sauvegardes réelles, il faut publier ce fichier comme **expérience de test privée**, distincte de
   tout futur jeu publié. Sinon le jeu bascule seul sur une mémoire non persistante, et l'écran l'indique.
3. Accueil → Paramètres du jeu → Sécurité → **Activer l'accès de Studio aux services API**.
4. Paramètres du jeu → Joueurs → **Nombre max. de joueurs = 1**.

## 2. Tests automatiques (de 2 à 10 minutes chacun)

Dans l'Explorateur, sélectionne **Workspace**. Dans Propriétés → Attributs, ajoute un attribut texte
`FU_TEST_SUITE` avec l'une de ces valeurs, puis clique sur **Lancer (Run, F8)**. Le jeu ne démarre pas pendant ces
scènes.

| Valeur | Ce que ça mesure |
|---|---|
| `movement` | portée réelle du saut (indispensable : tous les parcours en dépendent) |
| `burial` | ensevelissement : vrai KO, table ouverte, objet qui passe, bords libres |
| `plush` | Mallow : 9 chutes, 100 réutilisations, 6 peluches + 40 objets |
| `transitions` | 100 changements de salle : instances et connexions |

À la fin, la fenêtre **Sortie** (Affichage → Sortie) affiche une ligne qui commence par `STUDIO_RESULT_JSON:`.
Copie cette ligne et colle-la dans la conversation avec Claude. Copie aussi toute ligne rouge (erreur).

## 3. Jouer (test manuel)

Retire l'attribut `FU_TEST_SUITE`, puis **Jouer (F5)** :
1. le canard gonflable tombe (il remplace le carton, décision 0020) : +10 ; monte dessus : +5 ; sors : +50 ;
2. dans le sas, achète le Radar (reste 15), puis avance tout droit dans la porte ;
3. salle 1 : bouton Radar, grimpe, sors ; attends ensuite dans une salle pour te faire ensevelir.

Note ce qui ne marche pas : erreurs rouges dans Sortie, sauts impossibles, caméra, objets qui traversent. Une capture
d'écran par problème suffit.

## 3 bis. Mettre les vrais modèles 3D dans le jeu (facultatif)

Les objets et peluches modélisés dans Blender sont dans `filling_up/assets/import/models/` (`<id>.glb`). Tant qu'ils ne
sont pas importés, le jeu affiche des blocs de remplacement.
1. Dans ServerStorage, crée un dossier **`ImportedMeshes`** (une seule fois).
2. Avatar → **Importer 3D** → choisis `<id>.glb`. Échelle : laisse 1 (1 unité Blender = 1 stud). Pour une peluche,
   coche l'import du rig.
3. Range le modèle importé dans `ServerStorage/ImportedMeshes` et renomme-le exactement comme l'id, par exemple
   `toy_plush_bobine`. Son pivot doit être au centre de la base.
4. Lance le jeu : `PropFactory` utilise ce modèle à la place du bloc. La collision de jeu ne change pas. L'attribut
   `VisualStatus = imported_mesh` sur l'objet confirme le remplacement.

Rien n'est publié par cette étape : les maillages restent dans ta place locale tant que tu ne publies pas.

## 4. Laisser Claude piloter ton Studio (facultatif)

Claude ne peut agir sur ton ordinateur qu'à partir d'une session qui y tourne :
- application **Claude Desktop** : Paramètres → Claude Code → Remote Control, ajoute le dossier `first_app` ;
- ou `claude remote-control` lancé dans un terminal, dans ce dossier.

Studio ne s'automatise de l'extérieur qu'avec le plugin Rojo (synchronisation : `rojo serve` dans `filling_up/`) ou
un serveur MCP pour Roblox Studio installé chez toi. Sans eux, on passe par les étapes 2 et 3 ci-dessus.
