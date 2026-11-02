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
1. le carton tombe : +10 ; monte dessus : +5 ; sors : +50 ;
2. dans le sas, achète le Radar (reste 15), puis avance tout droit dans la porte ;
3. salle 1 : bouton Radar, grimpe, sors ; attends ensuite dans une salle pour te faire ensevelir.

Note ce qui ne marche pas : erreurs rouges dans Sortie, sauts impossibles, caméra, objets qui traversent. Une capture
d'écran par problème suffit.

## 4. Laisser Claude piloter ton Studio (facultatif)

Claude ne peut agir sur ton ordinateur qu'à partir d'une session qui y tourne :
- application **Claude Desktop** : Paramètres → Claude Code → Remote Control, ajoute le dossier `first_app` ;
- ou `claude remote-control` lancé dans un terminal, dans ce dossier.

Studio ne s'automatise de l'extérieur qu'avec le plugin Rojo (synchronisation : `rojo serve` dans `filling_up/`) ou
un serveur MCP pour Roblox Studio installé chez toi. Sans eux, on passe par les étapes 2 et 3 ci-dessus.
