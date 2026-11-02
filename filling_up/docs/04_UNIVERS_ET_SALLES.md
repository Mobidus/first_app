# 04 Univers et salles

## 1 Expédition continue et règles canoniques

FILLING UP se déroule dans Overflow Industries, une usine de tri de colis impossibles. Le joueur progresse de salle en salle en utilisant les objets qui s'accumulent comme marches. L'expédition constitue le mode central : aucune salle finale, aucun retour obligatoire au hub et aucun nombre maximal de salles prévu. The Giant Bin est une famille de salles récurrente, pas un boss terminal.

Le remplissage continue par vagues temporelles. Être recouvert et ne plus pouvoir se dégager peut provoquer un KO selon la règle d'ensevelissement du système de jeu. En revanche, aucun chronomètre indépendant et aucun indicateur global à 100 % ne tue automatiquement le joueur. Une personne habile peut poursuivre une très longue expédition ; cela ne garantit pas que chaque configuration permette d'attendre indéfiniment.

La génération préserve une possibilité de progression au moment où les objets structurants arrivent. Cette route peut ensuite être submergée si le joueur tarde : « route sûre » signifie sauts lisibles et réalisables, non refuge invulnérable permanent. Les surfaces temporaires restent autorisées si leur fonctionnement est visible et si elles ne sont pas introduites avant les compétences élémentaires.

Le MVP est solo. La sortie ouvre directement sur la salle suivante, préparée en avance. Un comptoir facultatif peut occuper un renfoncement de la transition ; aucun menu marchand n'interrompt automatiquement la marche. La mise en pause éventuelle et la sauvegarde d'expédition relèvent de règles explicites distinctes, jamais d'un refuge caché dans chaque salle.

## 2 Direction artistique commune

L'usine ressemble à un immense centre de tri de jouets, agrandi à l'échelle du personnage. Les décors utilisent du plastique satiné, de la mousse dense, du carton peint et du métal émaillé. Les objets ordinaires deviennent extraordinaires par leur taille, pas par une accumulation de particules. Écarter rouille réaliste, saleté détaillée, écrans illisibles et éclairage clignotant.

En cadrage de jeu, viser environ 60 % de fonds pâles, 25 % de couleur de salle et 15 % d'accents saturés. Ces proportions servent à protéger la lisibilité, sans imposer un quota rigide. Les couleurs des corps d'objets suivent leur thème. La signification de gameplay appartient uniquement aux balises du dessus : menthe et empreinte pour stable ; jaune et ressort pour rebond ; cyan et flèches pour mobile ; rose et sablier pour temporaire ; corail et triangle pour danger. Le violet signale un bonus facultatif, jamais une issue obligatoire.

Chaque salle possède une seule machine dominante, un objet géant mémorable et un son signature. Les murs ménagent une ligne de vue vers l'issue, reconnaissable par son arche menthe et son chevron vertical. La sortie conserve ces signes même dans une salle verte. Les signes combinent couleur, silhouette et animation afin de ne pas dépendre uniquement de la perception des couleurs.

BOB-7 est le robot inspecteur : capsule crème, roue noire, bras télescopiques, antenne jaune et écran cyan à deux yeux expressifs. Il mime les instructions avec un seul geste court. Aucun dialogue n'est nécessaire pour comprendre un saut. Son gag récurrent est de paraître assuré juste avant un déversement absurde ; limiter les interventions sonores à une par minute environ, désactivables.

## 3 Hub initial et microtutoriel

Le hall d'Overflow Industries mesure initialement 96 × 80 × 28 studs. Sol crème, tubes cyan, guichets roses, ossature bleu nuit. L'Atelier d'essai se situe à gauche, le départ en face et le Vestiaire à droite. Une vitrine de six emplacements présente les marques de maîtrise obtenues gratuitement par accomplissement. Ces trophées ne s'achètent pas et restent distincts des cosmétiques marchands du catalogue.

La première connexion commence toutefois dans une cellule jouable de 24 × 24 × 16 studs, sans visite obligatoire du hall. Un carton de 10 × 10 × 4 et une seconde marche permettent d'atteindre une issue à 8 studs. Message unique : « GRIMPE ET SORS ». Récompense, démonstration et achat de départ utilisent les règles économiques du projet ; aucune manipulation de caméra ne doit effectuer le saut à la place du joueur.

L'atelier placé après cette cellule permet d'essayer puis d'équiper le premier achat avant de poursuivre. Le passage reste ouvert. Les futurs changements de salle ne répètent pas le tutoriel et ne renvoient pas le joueur dans le hall.

## 4 Formats et échelles

Toutes les dimensions suivantes sont des gabarits de maquette en studs, notés largeur × profondeur × hauteur. Elles nécessitent des tests avec le contrôleur réel et sa caméra mobile. Une grande salle n'est pas nécessairement plus difficile : largeur des appuis, hauteur des sauts et nombre de décisions se règlent séparément.

| Famille | S | M | L | V |
|---|---|---|---|---|
| Réception | 36 × 32 × 20 | 56 × 48 × 30 | 72 × 60 × 36 | 40 × 40 × 56 |
| Toy Overflow | 40 × 36 × 24 | 64 × 56 × 36 | 80 × 72 × 44 | 44 × 44 × 64 |
| Bureau perdu | 40 × 32 × 24 | 64 × 48 × 36 | 80 × 64 × 44 | 40 × 40 × 60 |
| Kitchen Disaster | 40 × 36 × 24 | 64 × 56 × 36 | 80 × 72 × 44 | 44 × 40 × 60 |
| Garage Mayhem | 44 × 40 × 26 | 72 × 56 × 38 | 88 × 72 × 48 | 48 × 44 × 64 |
| The Giant Bin | 48 × 44 × 28 | 72 × 64 × 42 | 96 × 88 × 56 | 52 × 48 × 72 |

**Mise à jour du 2 novembre 2026 (décision 0017, demande de l'utilisateur)** : deux formats géants s'ajoutent par
famille, **XL** (grande halle, environ 1,4 × L) et **XV** (verticale géante, environ 1,6 × la hauteur de V). Leurs
dimensions sont dans `config/rooms.json`. Ils dominent la sélection à partir de la salle 2 ; la salle 1 reste petite.
Le volume des vagues suit la surface de la pièce, avec un budget physique inchangé.
Les grandes pièces reçoivent un habillage (décision 0018) : mobilier collé aux murs selon la famille, tapis et
panneaux lumineux. Il est posé après la validation, sans toucher au parcours, et vérifié par un contrôle indépendant.

Les variantes V multiplient les étages et paliers de récupération ; elles ne réduisent pas automatiquement les surfaces d'atterrissage. Les volumes L offrent plusieurs itinéraires visibles. Le sol et le plafond ne sont pas étirés arbitrairement : les modules de murs, machines et appuis sont recomposés sur une grille.

## 5 Six familles de sorties

Les identifiants techniques sont door, window, roof, duct, tailgate et floor_hatch. Une seule issue principale est active par salle. Les autres ouvertures éventuelles sont fermées et ne portent pas le balisage de sortie.

| Famille | Porte | Fenêtre | Toit | Conduit | Hayon | Trappe basse |
|---|---|---|---|---|---|---|
| Réception | Quai surélevé | Guichet | Auvent | Tunnel de colis | Camion jouet | Réserve de colis |
| Jouets | Théâtre | Maison géante | Boîte géante | Toboggan | Fourgon jouet | Coffre à jouets |
| Bureau | Archives | Atrium | Velux | Classement XXL | Chariot couvert | Réserve papier |
| Cuisine | Garde-manger | Passe-plat | Hotte | Livraison | Food-truck jouet | Cellier |
| Garage | Atelier | Bureau vitré | Toiture | Lavage | Fourgon | Fosse sécurisée |
| Giant Bin | Inspection | Hublot | Écoutille | Transfert | Benne | Collecte |

La dernière approche réserve un volume de 8 × 8 × 10 studs dans le repère de l'issue. Aucun spawn, trajectoire de chute ou décoration solide ne doit l'obstruer. Cette protection locale ne transforme pas le reste de la salle en refuge. La dernière plateforme doit rester atteignable depuis le graphe de parcours courant.

Hayon et trappe basse nécessitent d'abord un levier placé en hauteur. Leur ouverture révèle ensuite un passage avec sol ou réception amortie explicitement visible. Ne jamais demander au joueur de deviner qu'une fosse normalement mortelle est devenue une sortie. Le conduit est suffisamment large pour traverser sans nouvelle commande d'accroupissement. Une sortie de toit protège aussi la caméra, pas seulement la capsule du personnage.

## 6 Réception

**Palette :** fond bleu glacier #DFF7FF, structure bleu nuit #203055, accent cyan #16D9FF. Sol crème et machine corail doux. **Machine :** le Tamponneur, presse à deux yeux qui tamponne un coussin puis éjecte un carton intact.

La variante M comporte des paliers structurants vers 4, 8, 12 et 16 studs. Le chemin débutant monte en zigzag sur cartons et palettes. Un raccourci peut utiliser le chariot puis le colis oreiller ; ces fonctions apparaissent uniquement après leur introduction. Une valise ne roule pas sous les pieds une fois installée.

| ID | Objet | Fonction |
|---|---|---|
| reception_carton | Carton standard | Stable, appui de référence |
| reception_foam_crate | Caisse mousse | Stable, large réception |
| reception_suitcase | Valise orange | Stable, poignée décorative |
| reception_pallet | Palette turquoise | Stable, palier de repos |
| reception_tape_reel | Bobine de ruban | Stable, centre visiblement plein |
| reception_pillow_parcel | Colis oreiller | Rebond doux |
| reception_mail_cart | Chariot postal | Translation avec arrêts |
| reception_accordion_parcel | Colis accordéon | Affaissement annoncé |

Le premier lot de la première vraie salle accueille l'ourson Mallow comme objet invité, vers 20 secondes de première session selon la vitesse du joueur. Il remplace un objet prévu, reste un appui stable et compte dans tous les budgets. Le tutoriel conserve son carton lisible. Plus tard, un colis géant ouvre un ruban-escalier latéral. Sons de tampon et carton. Cosmétiques associés : Ruban citron (trace_ruban_citron), Radar citron (skin_radar_citron) et BOB papier (compagnon_bob_papier). Prix et conditions : config/economy.json, sans SKU supplémentaire.

## 7 Toy Overflow

**Palette :** fond lavande #EEE7FF, structure violet #8855FF, accent rose #FF4CB8. **Machine :** Toupie Trieuse, immense toupie suspendue dotée de trois trompes. Ses mouvements restent derrière les volumes jouables.

La route principale utilise l'ourson, la pieuvre, le cube et le dos plat du canard. Le tambour propose un raccourci de rebond, facultatif à sa découverte. Le train permet ensuite de combiner rebond et timing. Les surfaces porteuses sont visibles : jamais de collision donnant l'impression de marcher au-dessus d'une silhouette arrondie.

| ID | Objet | Fonction |
|---|---|---|
| toy_plush_mallow | Ourson Mallow | Stable, déformation plush_soft |
| toy_plush_loppy | Lapin Loppy | Rebond doux, déformation plush_soft |
| toy_flat_duck | Canard à dos plat | Stable |
| toy_train | Petit train | Mobile sur rail |
| toy_drum | Tambour | Rebond vertical |
| toy_domino | Domino couché | Passerelle stable |
| toy_shape_cube | Cube à formes | Stable |
| toy_plush_octo | Pieuvre Octo | Stable, déformation plush_soft |

Mallow mesure 12 × 10 × 5 : ours crème allongé, museau caramel, oreilles rondes, coutures de couverture et ventre dodu. Loppy mesure 10 × 8 × 7 : lapin lilas, longues oreilles retombantes, nez corail et pattes cousues ; son dos rebondit doucement. Octo mesure 12 × 12 × 5 : tête menthe, huit bras courts corail et grandes broderies faciales. Les silhouettes doivent rester reconnaissables en miniature.

Ces trois peluches utilisent plush_soft : pelage stylisé par texture et volumes simples, sans fourrure coûteuse. Chute, compression et petit retour souple se voient sur leur silhouette ; les détails d'animation et le plafond de six héros animés relèvent de la spécification de déformation. Les colliders restent simples. Tester l'alignement pieds/surface pendant la compression et l'absence de flottement après réception.

Un Mega Canard peut ponctuer une rencontre. Marimba et ressorts ronds composent le son. Cosmétiques associés : Canard mousse (compagnon_canard_mousse), Confettis POP (trace_confettis_pop) et Envol de canards (victoire_canards). Prix et conditions : config/economy.json.

## 8 Bureau perdu

**Palette :** fond #EDF3F8, structure lavande #B9A4EE, accent turquoise #2ACBC7. **Machine :** Copieur Panique, photocopieuse jaune qui produit des blocs de papier solides.

La variante M organise une diagonale entre l'entrée et une fenêtre haute. Des bureaux fournissent des surfaces de décision larges. Une chaise sur rail introduit le premier mouvement horizontal ; son premier usage dispose d'arrêts prolongés. Le téléphone à ressort constitue un raccourci, pas un nouveau mouvement obligatoire lors de la même première rencontre.

| ID | Objet | Fonction |
|---|---|---|
| bureau_paper_ream | Ramette géante | Stable |
| bureau_binder_stack | Classeurs empilés | Stable |
| bureau_desk | Bureau | Grand palier stable |
| bureau_locker | Casier couché | Stable |
| bureau_keyboard | Clavier géant | Stable |
| bureau_rail_chair | Chaise sur rail | Mobile horizontal |
| bureau_spring_phone | Téléphone à ressort | Rebond |
| bureau_loose_files | Dossiers libres | Tassement annoncé |

Une rafale de feuilles forme un avion géant derrière la vitre. Ces feuilles n'ont aucune collision et ne traversent pas la caméra. Sons d'imprimante et de touches. Cosmétiques associés : BOB papier (compagnon_bob_papier), Atelier lavande (atelier_lavande) et Disque vinyle (reception_vinyle). Prix et conditions : config/economy.json.

## 9 Kitchen Disaster

**Palette :** fond crème #FFF5DF, structure menthe #A9EDD0, accent turquoise #24BFC4. **Machine :** Toast-O-Matic, grille-pain rotatif qui lance ses objets sur des arcs annoncés.

Boîtes, marmite et biscuitière forment les appuis ordinaires. La gelée ajoute un rebond visuellement évident. Le plateau de service rejoint la logique des mobiles déjà apprise. Les pains temporaires se ramollissent après une annonce visuelle au contact ; cette règle n'apparaît pas simultanément avec un autre mécanisme inédit.

| ID | Objet | Fonction |
|---|---|---|
| kitchen_cereal_box | Boîte de céréales | Stable |
| kitchen_closed_pot | Marmite fermée | Couvercle stable |
| kitchen_flat_lemon | Demi-citron aplati | Stable |
| kitchen_biscuit_tin | Boîte à biscuits | Stable |
| kitchen_jelly | Gelée | Rebond constant |
| kitchen_serving_tray | Plateau de service | Mobile |
| kitchen_toast | Pain géant | Ramollissement annoncé |
| kitchen_pancake_stack | Pancakes | Tassement annoncé |

Une casserole latérale remplit sa fenêtre de pop-corn ; les particules de premier plan sont rares et ne masquent pas les balises. Sons de grille-pain et petits « plop ». Cosmétiques associés : Parapluie pastèque (skin_parapluie_pasteque), Bulles menthe (trace_bulles_menthe) et Feu d'artifice mousse (victoire_mousse). Prix et conditions : config/economy.json. Aucun effet ne ressemble à une plateforme exploitable.

## 10 Garage Mayhem

**Palette :** fond #EAF5FF, structure violet #8855FF, accent orange #FF9B47. **Machine :** Assembleur Bric-à-Brac, bras industriels construisant des voitures-jouets absurdes.

Les établis et caisses constituent des paliers ; les voitures ont un toit volontairement plat. Le cric introduit un déplacement vertical prévisible, avec arrêt en haut et en bas. Le ressort permet aux experts de l'intercepter en mouvement. Les roues décoratives ne peuvent pas libérer un véhicule porteur après la réception du joueur.

| ID | Objet | Fonction |
|---|---|---|
| garage_wheel_stack | Roues pleines | Stable |
| garage_tool_chest | Caisse à outils | Stable |
| garage_flat_car | Voiture à toit plat | Stable |
| garage_barrier_block | Bloc de balisage | Stable |
| garage_square_can | Bidon carré fermé | Stable |
| garage_lift_jack | Cric élévateur | Mobile vertical |
| garage_spring_plate | Plateau à ressort | Rebond |
| garage_hinged_ramp | Rampe articulée | Inclinaison annoncée |

Une voiture à quatre volants défile derrière une vitre puis perd ses accessoires sans toucher le parcours. Sons pneumatiques doux et klaxon jouet rare. Cosmétiques associés : BOB chantier (compagnon_bob_chantier), Grappin chrome doux (skin_grappin_chrome) et Hublot cyan (atelier_hublot_cyan). Prix et conditions : config/economy.json.

## 11 The Giant Bin

**Palette :** fond bleu ardoise #26364D, structure crème #F6EEDC, accent cyan #16D9FF ; touches jaunes et violettes. **Machine :** Tri-Cœur, trois canons disposés autour d'un compacteur transparent.

La salle se divise en quatre secteurs, afin de ne pas présenter une masse incompréhensible. Les conteneurs, poutres et blocs composent la route périphérique ; les mobiles et rebonds permettent de traverser. L'issue peut être un hublot, une écoutille ou une sortie basse à levier selon le modèle. La couleur sombre du fond n'assombrit jamais les surfaces de réception.

| ID | Objet | Fonction |
|---|---|---|
| bin_compact_container | Conteneur compact | Stable |
| bin_foam_beam | Poutre de mousse | Liaison stable |
| bin_hex_block | Bloc hexagonal | Stable |
| bin_spring_piano | Piano à ressorts | Rebond sur touches balisées |
| bin_conveyor_bucket | Godet de convoyeur | Arc mobile connu |
| bin_satellite_parcel | Colis satellite | Translation horizontale |
| bin_air_ring | Bouée à plateau | Rebond doux |
| bin_compressible_barrel | Baril compressible | Affaissement annoncé |

Le compacteur forme un BOB-7 géant derrière sa vitre puis le défait en confettis sans terminer l'expédition. Cosmétiques associés : BOB cosmique (compagnon_bob_cosmique), Habillage holographique (skin_outil_holographique) et Orbite de mini-planètes (victoire_planetes). Prix et conditions : config/economy.json. Aucun ne protège contre l'ensevelissement.

## 12 Les dix premières salles

La première séquence est pédagogique et déterministe. Elle introduit au plus une compétence nouvelle par salle ; la variété thématique n'ajoute pas automatiquement une nouvelle règle.

| Rang | Version complète | Introduction | Substitution MVP |
|---|---|---|---|
| 1 | Réception S porte | Sauts stables larges | Identique |
| 2 | Réception M fenêtre | Deux itinéraires lisibles | Identique |
| 3 | Jouets S porte | Rebond facultatif | Identique |
| 4 | Jouets M toit | Réutilisation du rebond | Identique |
| 5 | Bureau S porte | Mobile horizontal avec arrêts | Identique |
| 6 | Réception V fenêtre | Montée sur plusieurs étages | Identique |
| 7 | Bureau M fenêtre | Un appui temporaire annoncé | Identique |
| 8 | Cuisine S fenêtre | Nouveau décor, règles connues | Jouets S fenêtre |
| 9 | Garage M porte | Mobile vertical | Bureau M porte avec chaise en lift |
| 10 | Giant Bin M fenêtre | Combinaison des acquis | Jouets V fenêtre |

La chaise en lift du MVP emploie la variante de mouvement autorisée dans la configuration, pas une propriété inventée à l'exécution. À partir de la salle 11, les combinaisons certifiées prennent le relais ; éviter de répéter famille, taille et sortie à l'identique plus de deux fois de suite.

## 13 Difficulté et génération certifiée

| Profondeur | Intervalle | Bouches | Objets par vague | Annonce | Rapport de portée maximal |
|---|---:|---:|---:|---:|---:|
| 1 à 4 | 12 s | 1 | 3 | 1,5 s | 0,65 |
| 5 à 10 | 10 s | 2 alternées | 4 | 1,5 s | 0,70 |
| 11 à 20 | 9 s | 2 alternées | 4 | 1,4 s | 0,75 |
| 21 à 40 | 8 s | 3 alternées | 5 | 1,4 s | 0,80 |
| 41 à 80 | 7,5 s | 3 alternées | 5 | 1,3 s | 0,85 |
| 81 et plus | 7,5 s | 3 alternées | 5 | 1,3 s | 0,85 |

Le rapport porte sur la distance de saut mesurée avec l'écart de hauteur et le contrôleur réels ; ce n'est pas un pourcentage appliqué à une valeur théorique unique. La progression au-delà de 80 renouvelle les agencements, objectifs et combinaisons, sans exiger de sauts physiquement impossibles.

Avant chaque chute structurante, valider empreinte de réception, appui inférieur, espace du personnage, trajectoire et liaison au graphe. Les chutes décoratives ne doivent ni pousser arbitrairement un appui figé, ni obstruer l'approche finale. Le volume protégé de l'issue n'empêche pas le KO ailleurs.

Budget cible : 40 corps dynamiques, 120 colliders statiques et 80 blocs décoratifs au maximum dans la salle active. Les appuis stabilisés utilisent des collisions simples ; la compression des couches enfouies ne doit jamais supprimer un support accessible, occupé ou nécessaire. Les salles quittées sont libérées après transfert sécurisé. La pression se maintient sans accumuler indéfiniment des corps simulés.

## 14 Périmètre et recette

Le MVP livre Réception, Toy Overflow et Bureau perdu, avec formats S, M et V et sorties porte/fenêtre/toit. Chaque combinaison réellement livrée exige des essais ; déclarer une possibilité dans le catalogue ne la rend pas certifiée. Cuisine, Garage, Giant Bin, format L et trois autres sorties constituent le périmètre V1.

Tester chaque combinaison sur mobile : issue identifiable dès l'entrée, prochain appui visible depuis les paliers principaux, absence de collision décorative inattendue, chute annoncée, route initialement réalisable, passage final libre. Provoquer une attente longue pour vérifier que l'ensevelissement peut causer un KO réel sans qu'un seuil global ou un chrono caché ne décide du résultat. Tester aussi une succession de plusieurs centaines de salles pour mesurer mémoire, recyclage et répétition des modèles.

Les champs de config sont la source opérationnelle : stage indique la profondeur minimale d'introduction d'un objet ; release indique le périmètre de livraison ; size_studs décrit l'enveloppe visuelle ; collider décrit la collision de jeu. Toutes les dimensions suivent l'ordre largeur, profondeur, hauteur ; les convertir en Vector3 largeur, hauteur, profondeur. Les réglages physiques sont des points de départ de prototype, pas des mesures déjà validées en production.
