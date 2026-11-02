# 02 Production des assets avec Claude Design

## Livrable de la première phase

La première phase produit une direction visuelle exploitable, puis un premier lot d'assets de jeu validé. Elle commence dans Claude Design. Elle ne s'achève pas sur une belle image : les fichiers sources, les dimensions, les matières, les vues utiles à la modélisation et le manifeste doivent permettre à une IA de poursuivre sans réinventer les objets.

Claude Design documente des exports ZIP, HTML, PDF et PPTX, ainsi qu'un passage vers Claude Code. Les commandes `/design` et `/design-sync` sont à vérifier dans l'installation disponible. Le plan ne suppose pas l'existence d'une API publique de génération en lot ni d'un export natif de meshes Roblox. Les images de référence et le prototype d'interface ne sont pas des modèles 3D jouables. [S1]

La production 3D utilise ensuite Blender piloté par scripts ou les primitives Roblox. Les objets identitaires, en particulier les peluches, passent par un vrai mesh, un rig et un contrôle de skinning. Les éléments simples, tels que les murs et les cartons, peuvent être paramétriques. [S2, S3]

## Direction artistique commune

Le monde est une usine de colis impossibles, propre, absurde et lumineuse. Il doit évoquer des jouets physiques que l'on voudrait toucher. Les matières et silhouettes font l'identité ; la quantité d'effets n'est pas un substitut au dessin de l'objet.

| Token | Valeur | Usage |
|---|---|---|
| `canvas_cream` | #FFF5DF | Grands fonds, zones de repos visuel |
| `outline_navy` | #203055 | Contours, texte, structure |
| `brand_cyan` | #16D9FF | Machines, accessoires et contrôles |
| `reward_yellow` | #FFE14D | Coins et accents joyeux |
| `machine_pink` | #FF4CB8 | Pièces mécaniques et objets signature |
| `safe_mint` | #39E68B | Balise de sortie et pictogramme d'appui |
| `danger_coral` | #FF684B | Zones d'impact et triangles de danger |
| `prestige_violet` | #8855FF | Maîtrise, personnalisation, objectifs facultatifs |

Les fonctions sont codées sur les balises et plateaux, pas sur toute la surface des objets. Un ours peut rester crème et un grille-pain menthe. Une petite empreinte menthe indique sa réception sûre. Chaque code couleur possède aussi une forme ou une icône. Les grandes masses du décor restent pâles ; les accessoires et machines portent la saturation.

Les objets jouables doivent rester identifiables en silhouette noire à l'échelle où ils apparaissent. Un test à huit mètres de caméra doit distinguer ours, lapin, pieuvre, canard, carton et marmite sans nom flottant. Éviter les franchises et personnages sous licence : les modèles sont originaux.

## Peluches identitaires

| Asset | Dessin précis | Matière et mouvement |
|---|---|---|
| Mallow | Gros ours allongé, ventre ovale, museau caramel, oreilles rondes, pattes courtes, patch d'étoile cousu ; 12 × 10 × 5 studs | Tissu crème mat, coutures visibles à distance moyenne ; ventre qui s'écrase, tête et pattes avec retard léger |
| Loppy | Lapin lilas, tête poire, une oreille droite et une oreille pliée, pieds crème ; 10 × 8 × 7 studs | Toile douce, intérieur d'oreilles rose ; oreilles qui retardent leur chute, corps qui reprend sa forme en deux oscillations |
| Octo | Pieuvre menthe à huit tentacules épais, dessous corail et yeux brodés ; 12 × 12 × 5 studs | Mousse rembourrée, tentacules qui s'écartent à l'impact ; sommet central large et stable |

Les yeux sont brodés ou en relief simple, sans matériau vitreux réaliste. Les coutures sont des traits intégrés à la texture ou à une géométrie légère ; pas des centaines de petites pièces. Pas de fourrure en fibres simulées, de tissu auto-collisionnant ni d'yeux séparés pouvant se décrocher au hasard.

Le prototype doit inclure Mallow avant de produire toutes les peluches. Il apparaît dans la première vraie salle, autour de la première utilisation du Radar, si le joueur suit le parcours nominal. Le tutoriel conserve un carton simple pour expliquer le saut sans ambiguïté. L'arrivée de l'ours fournit le premier spectacle, pas une deuxième règle à apprendre.

## Déformation sous gravité et à l'impact

Le déplacement de l'objet suit une racine physique. Son apparence réagit à la vitesse, à la normale et à l'intensité de l'impact. On vise une illusion crédible de rembourrage, pas une simulation intégrale de matière molle.

| État | Comportement visuel | Valeurs initiales |
|---|---|---|
| Chute | Étirement modéré selon la vitesse, membres et oreilles en retard | Hauteur apparente jusqu'à ×1,12 ; aucun étirement à vitesse nulle |
| Premier impact | Compression rapide sur l'axe de contact et élargissement du ventre | Hauteur minimale ×0,72 ; largeur maximale ×1,18 ; compression 0,09 s |
| Rebond | Retour légèrement au-delà de la pose de repos | Phase 0,18 s ; intensité dépendant de l'impact |
| Amortissement | Une ou deux oscillations décroissantes | Retour principal en 0,65 s ; totalité en 0,90 s maximum |
| Réception du joueur | Petite dépression autour des pattes ou du ventre | Déplacement du dessus utile limité à 0,25 stud |
| Repos | Pose lisible et support stable | Aucune respiration qui déplace la réception en continu |

Ces nombres sont des réglages d'animation, pas des garanties physiques mesurées. `config/runtime.json` en est la source. Un faible contact ne doit pas produire le même écrasement qu'une grande chute. La déformation ne change ni le montant d'une récompense ni la décision d'ensevelissement.

## Contrat du rig et des collisions

Le modèle comporte une racine non déformante et un réseau de neuf contrôles du ventre, avec au plus six contrôles secondaires de tête, oreilles ou membres. Le poids du skin est normalisé et chaque pose est calculée depuis la pose de référence ; aucune transformation cumulative qui dérive au fil des impacts.

Dans Roblox, les bones animent l'apparence mais pas les collisions. `Bone.Transform` est un CFrame non répliqué : le serveur transmet un événement d'impact et les clients reconstruisent la pose. Le contrôleur utilise des translations coordonnées des bones et des rotations, pas une propriété d'échelle inexistante sur un CFrame. [S4, S5]

Le mesh visuel n'est pas un collider et n'est pas soudé en état ancré à une racine physique, ce qui immobiliserait l'assemblage. Il suit la racine côté client. Le serveur conserve un proxy simple de l'objet, ses appuis et son état de pose. Une interface d'événement minimale transmet `objectInstanceId`, `serverTime`, `impactNormal`, `impactStrength` et `settleState`.

Les grands écrasements surviennent pendant la pose, avant l'activation de l'appui garanti. La balise d'appui devient visible une fois le dessus stabilisé. Si un joueur touche la peluche trop tôt, un rattrapage vers une surface voisine ou un contact physique cohérent doit empêcher de traverser le mesh. Une grande différence entre le dessus visible et la collision fait échouer la recette : il ne faut pas voir les pieds flotter au-dessus d'un ours écrasé.

Une projection simplifiée du rig peut servir pour les objets éloignés. Aucun changement de niveau de détail ne doit faire apparaître une nouvelle plateforme ou modifier la collision serveur.

## Budgets de fabrication

| Catégorie | Budget interne initial | Contraintes |
|---|---|---|
| Objet répété simple | 100 à 800 triangles visibles | Un à deux matériaux, collision en boîtes |
| Peluche proche | 1 500 à 3 500 triangles | Rig contrôlé, atlas 1 024 px maximum par ensemble initial |
| Peluche lointaine | 300 à 700 triangles ou pose simplifiée | Pas de détails de couture géométriques fins |
| Machine signature | 3 000 à 8 000 triangles, découpée en éléments utiles | Animations mécaniques simples, collision du parcours séparée |
| Outil tenu | 300 à 1 500 triangles | Silhouette identifiable dans une icône 64 px |
| Icône de catalogue | Source modifiable et PNG transparent 512 × 512 | Vérifier la lisibilité à 64 et 96 px |
| Famille de salle | Kit modulaire, textures partagées | Éviter un matériau unique par petit objet |

Ce sont des budgets du projet, non des limites générales de Roblox. Le plafond initial de six peluches proches animées est un objectif de profilage. Prioriser celle sous le joueur puis les plus proches ; simplifier les suivantes. Les niveaux de détail visent 30 mises à jour visuelles par seconde près du joueur, 15 à moyenne distance et une pose fixe loin. La trajectoire physique ne ralentit pas avec le rendu.

## Livrables Claude Design

1. Un système de couleurs, matières, formes, typographie et pictogrammes avec noms de tokens.
2. Une planche par famille de salle : perspective de jeu, vue de dessus et détail de la sortie.
3. Une planche des douze outils, avec face, profil, trois-quarts et silhouette de l'icône.
4. Une planche séparée pour Mallow, Loppy et Octo : quatre vues et quatre poses d'impact.
5. Les états HUD, borne de premier achat, boutique Coins, boutique Robux, inventaire, KO, reprise et renaissance.
6. Un prototype de l'accueil et de l'achat initial. Les valeurs et mouvements y sont démonstratifs ; aucun bouton ne prétend exécuter un achat Roblox réel.
7. Un ZIP des sources effectivement exportées, une liste des fichiers et leurs correspondances aux identifiants du manifeste.

Les prompts fournis dans `prompts/` sont à exécuter dans l'ordre. Il faut inspecter les fichiers du ZIP : la disponibilité d'un export ZIP ne garantit pas que chaque icône existe déjà comme PNG individuel. La rasterisation, le détourage et la reconstruction de l'UI Roblox font partie de la fabrication suivante.

## Fabrication et import

Les formes simples sont produites par des générateurs déterministes Roblox. Les peluches et formes signature passent par Blender : modèle, UV, matériaux, rig, poids du skin, poses de référence, export FBX ou glTF adapté, puis import dans Studio. La documentation Roblox décrit ces formats ; l'inspection du modèle importé reste obligatoire. [S3]

Chaque asset doit posséder : `id`, catégorie, source, export, dimensions en studs, pivot, orientation avant, collision, sockets d'appui, matériaux, profil de déformation, budgets, licence/provenance, ID Roblox après import et statut. Les statuts sont `planned`, `designed`, `modeled`, `imported`, `validated`. Aucun passage automatique de `planned` à `validated` sur la seule existence d'un fichier image.

Le manifeste initial recense les modèles, icônes, modules d'architecture et sons à produire. Tous les IDs Roblox sont initialement absents. Pour les formes produites en primitives, le générateur paramétrique remplace un fichier mesh externe, mais les tests de dimension et collision restent obligatoires.

## Porte de validation du premier lot

Avant la production complète des quarante-huit objets de salle, valider : quatre objets simples, Mallow, une machine de livraison, les trois ouvertures MVP et le Radar. Le lot doit fonctionner dans une micro-salle réelle, avec les sauts du contrôleur final.

| Essai | Critère de passage |
|---|---|
| Identification | Au moins huit testeurs sur dix reconnaissent ours, lapin et pieuvre sans lire de nom ; protocole et résultats conservés |
| Chute de Mallow | Trois hauteurs et trois orientations ; intensité d'écrasement croissante, pas d'explosion du rig |
| Collision | Pieds et dessus visible à moins de 0,25 stud lorsque l'appui est actif |
| Pose | Pas de dérive après 100 chutes et remises dans le pool |
| Charge | Six peluches animées et quarante objets dynamiques dans la scène de charge, sur appareils de référence |
| Comparaison | Déformations activées puis désactivées : les résultats de KO et récompenses sont identiques |
| Faible qualité | Réduction des effets sans masquer la sortie, la cible de saut ou l'alerte d'impact |

