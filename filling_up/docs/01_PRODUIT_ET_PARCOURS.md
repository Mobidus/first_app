# 01 Produit et règles canoniques

## Objectif de développement

Développer FILLING UP, un jeu Roblox d'adresse dans une usine qui se remplit d'objets. Le joueur utilise les objets comme appuis, choisit son trajet et rejoint une sortie située dans un mur, une fenêtre, le toit ou un autre élément du décor. Cette sortie mène à une nouvelle salle. L'expédition continue tant que le joueur n'est pas KO ou ne décide pas de s'arrêter.

La réussite dépend d'abord de la lecture des formes, du placement et du saut. Les outils donnent des options supplémentaires. Les Coins et les collections rendent visibles les progrès entre plusieurs expéditions. Les achats Robux peuvent accélérer l'acquisition d'outils via les Coins : cet avantage en aventure doit être assumé, et non présenté comme une absence totale d'avantage payant.

Le présent dossier consolide les anciennes spécifications. Il remplace leurs durées limites, leur fin de run après trois salles, leur mort automatique à 100 % de saturation et leur mode Endless séparé. Les paramètres sont des valeurs de prototype à éprouver ; les objectifs de rétention et de vente ne sont pas des résultats mesurés.

## Règles non négociables

| Sujet | Règle de développement |
|---|---|
| Remplissage | Vagues régulières, objets solides et progression visible de l'amas |
| Défaite | Ensevelissement local confirmé ou chute dans un volume dangereux clairement signalé |
| Temps | Aucun compte à rebours de fin de salle ; aucun KO fondé uniquement sur le temps écoulé |
| Continuité | La sortie ouvre la salle suivante ; pas de retour au hub, de résultats plein écran ou de relance obligatoires |
| Durée d'expédition | Aucun plafond de durée ni dernière salle définie ; cinq heures sont un scénario d'endurance à valider |
| Difficulté | Elle augmente jusqu'à une enveloppe réalisable, puis se renouvelle par combinaisons |
| Matériel | Aucune route obligatoire n'exige un outil acheté |
| Propriété | Coins, permis, outils, rangs, cosmétiques et achats permanents survivent au KO et aux renaissances |
| Accueil | Principe compris en moins de dix secondes visées ; objet réellement achetable et utilisable avant trente secondes visées |

Il est possible de perdre parce qu'on est resté trop bas pendant que les objets s'accumulaient. Cela résulte de la situation physique. Ce n'est pas un délai arbitraire ajouté à la salle. L'interface montre la profondeur, les appuis, le danger local et la sortie ; elle ne montre pas de minuterie de survie.

## Déroulement d'une salle

1. Le joueur entre depuis un sas protégé. La prochaine sortie est signalée par un pictogramme et une lumière menthe. La famille de salle et son numéro apparaissent brièvement sans bloquer les commandes.
2. Les premières surfaces utiles sont déjà présentes ou arrivent dans la première vague. Aucune vague ne vise directement l'apparition.
3. Des annonces visuelles et sonores localisent les arrivées. Le joueur monte, attend le bon mouvement ou emprunte un raccourci. Une chute ordinaire peut le renvoyer à un niveau inférieur encore jouable ; elle n'est pas systématiquement mortelle.
4. L'amas continue à monter. Les appuis de la route basse peuvent devenir inutilisables : il faut progresser. La porte elle-même reste dégagée, mais son accessibilité ne donne pas une immunité à tout le parcours.
5. L'arrivée dans la sortie valide les récompenses une seule fois et charge la prochaine salle. Un compteur bref annonce les gains dans le sas. Le joueur peut continuer tout droit sans ouvrir de menu.

Les sas contiennent une borne d'équipement, une commande de sauvegarde et, si éligible, la machine de renaissance. Ils n'ont ni danger ni durée maximale. En salle active, ouvrir un menu ne suspend pas implicitement les objets : les écrans d'achat complets ne s'ouvrent que dans les sas. Un bouton discret permet seulement d'épingler un objet pour plus tard.

## Les trente premières secondes

Le chronométrage commence quand le personnage est contrôlable, pas au clic sur la vignette Roblox. Le chargement est mesuré séparément. Aucune étape ne ferme ses portes si le joueur est plus lent.

| Temps cible | Action concrète | Résultat |
|---|---|---|
| 0 à 3 s | Un carton jaune tombe et se pose ; la sortie est au-dessus | Prime de découverte de 10 Coins, une fois par compte |
| 3 à 5 s | Le joueur saute sur un gros appui | 5 Coins ; pictogramme « GRIMPE » |
| 5 à 10 s | Il rejoint la première issue | 50 Coins ; solde total 65 |
| 10 à 20 s | Une borne montre le Radar POP et deux boutons | Achat volontaire à 50 Coins ou continuer ; solde 15 après achat |
| 20 à 30 s | Première vraie salle, premier usage du Radar | Trois appuis possibles deviennent lisibles ; une grosse peluche arrive dans une baie de démonstration |

Le tutoriel ne monétise pas l'urgence. Le prix du Radar reste identique si le joueur l'ignore. L'effet de la peluche montre le niveau de qualité des objets : silhouette reconnaissable, compression à l'impact, reprise de forme. Aucun texte long ni boutique Robux automatique.

Si le joueur n'a pas compris après cinq secondes d'inaction, montrer une courte trajectoire fantôme. Ne pas téléporter son avatar ni valider un saut qu'il n'a pas effectué.

## Adresse et apprentissage

Le contrôleur reste identique entre joueurs : déplacement horizontal, saut, légère tolérance de bord de 0,12 seconde, mémorisation d'appui de 0,12 seconde et rattrapage de rebord de base. Ces valeurs sont à régler dans le prototype. Elles ne sont pas des avantages vendus.

Les surfaces de réception ordinaires sont larges et les prochains appuis sont visibles. Un joueur avancé progresse davantage en choisissant mieux et en enchaînant, pas parce qu'il clique sur un bouton de saut plus cher. Les routes optionnelles peuvent utiliser un rebond, un objet mobile ou un grappin, mais une trajectoire sans outil reste disponible lorsque la salle est abordée normalement.

La règle de construction n'est pas « distance inférieure à X » indépendamment de la hauteur. Le validateur emploie une table de trajectoires mesurées avec le vrai contrôleur, selon différence de hauteur, distance, taille d'appui, vitesse de plateforme et dégagement de tête. Une combinaison de hauteur maximale et de distance maximale séparément autorisées peut être impossible.

## Difficulté sans dernier niveau

Les premières salles enseignent une compétence à la fois. À partir des profondeurs avancées, la cadence des objets, la portée des sauts et le temps minimal d'annonce cessent de durcir. Les familles, formats, sorties, routes et mouvements continuent à varier.

La difficulté n'est pas strictement monotone d'une salle à l'autre : des respirations permettent de conserver l'envie de continuer. La tendance progresse par bandes, sans punition automatique quand un joueur atteint un certain rang. La grande cuve est une famille récurrente, pas le niveau final.

Les profondeurs élevées ne débloquent pas une vitesse de chute physiquement impraticable, une plateforme microscopique ou un nombre sans limite de corps physiques. Une progression quasi illimitée signifie que le système peut produire de nouvelles combinaisons sans terminer l'expédition, pas qu'il existe une infinité de modèles 3D faits à la main.

## KO et reprise

Un KO met fin à l'expédition en cours. Les gains déjà validés, le meilleur niveau atteint et les permis restent acquis. La commande gratuite « Recommencer » démarre une nouvelle expédition à la profondeur 1. Il n'y a pas de résurrection payante dans cette version.

La première erreur de saut n'est pas nécessairement un KO : des appuis de rattrapage et un sol inférieur permettent de remonter. Les volumes de chute éliminatoire sont réservés à des passages clairement signalés et jamais confondus avec une sortie en trappe.

Le sas permet de sauvegarder et quitter. Une reprise continue l'expédition enregistrée. Une déconnexion en salle redémarre la même salle et la même seed, avec les récompenses déjà réclamées marquées ; elle ne doit pas permettre de dupliquer des Coins. Les reprises sont identifiées dans les futurs classements qui exigent une expédition ininterrompue.

## Trois progressions distinctes

| Progression | Ce qui l'augmente | Ce qui la remet à zéro |
|---|---|---|
| Profondeur d'expédition | Chaque salle réellement franchie | KO ou renaissance volontaire |
| Compte et collection | XP, outils, achats et maîtrise | Rien lors d'un KO ou d'une renaissance |
| Renaissances | Permis gagnés par sorties, puis conversion choisie dans un sas | Le rang ne baisse jamais ; seuls les permis consommés sont déduits |

La progression XP peut continuer sans niveau final : coût du niveau suivant = 100 + 10 × min(niveau − 1, 40). Une sortie rapporte 50 + 10 × min(entier((profondeur − 1) / 10), 10) XP. Les niveaux donnent des titres et variantes de cadres, pas des Coins supplémentaires non prévus dans l'économie. Après épuisement des titres écrits à la main, un rang numérique et des variantes de palette continuent à évoluer.

## Univers lisible et objets mémorables

Overflow Industries trie des colis impossibles. Des objets de la vie quotidienne surdimensionnés encombrent ses départements : peluches cousues, grille-pain, ramettes, valises, pneus et instruments. BOB-7, robot crème à écran cyan, accompagne le joueur sans dialogue imposé.

Une salle possède une machine dominante, une palette propre et un objet signature. Les formes et matières doivent permettre d'identifier un objet même sans sa couleur. Les fonds restent suffisamment calmes pour lire les appuis ; rendre toutes les surfaces fluorescentes ferait perdre ce contraste.

## Périmètre de réalisation

Le premier livrable jouable est solo. Il valide une salle plaisante, les déformations des objets, le KO et la transition avant d'ajouter beaucoup de contenu. Le jeu complet conserve une architecture compatible avec la coopération, mais cette dernière nécessite un contrat distinct sur les joueurs séparés entre salles et n'est pas simulée par une simple option « quatre joueurs ».

Le plan n'engage pas de publication automatique. Les achats réels, la mise en vente, les permissions et les comptes sont des étapes de validation séparées. Les chiffres d'économie et de performance ne sont acceptés qu'après les tests indiqués dans le backlog.

