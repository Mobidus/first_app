# Économie et objets de Filling Up

## 1. Rôle de ce document

Ce document fixe les achats, les récompenses et les renaissances de la version 3. Les valeurs exécutables sont dans `config/economy.json`. Les prix, durées moyennes et résultats de simulation sont des hypothèses de prototype : ils doivent être confrontés aux parties de test avant ouverture commerciale.

Le joueur traverse des salles successives sans limite prédéfinie de profondeur. Des vagues d’objets continuent de remplir chaque salle ; un ensevelissement réel peut provoquer le KO. Il n’existe ni chronomètre arbitraire de défaite, ni mort automatique à une jauge globale de remplissage. Les durées indiquées ici servent uniquement à évaluer le rythme économique.

L’équipement doit offrir de nouvelles décisions : lire une réception, stabiliser un appui, rattraper une chute ou prendre un raccourci. Aucun outil n’est indispensable à la route accessible. Acheter ne doit pas remplacer l’apprentissage du saut.

## 2. Règles non négociables

- Les Coins sont crédités et sauvegardés dès qu’une action éligible est validée. Un KO ne les retire pas.
- Aucun paiement ne dépend du temps de connexion, de l’attente ou du nombre d’objets tombés.
- Aucun plafond de gains par session : cinq heures de jeu actif restent rémunérées.
- Le joueur équipe au maximum un outil actif, un passif et un compagnon cosmétique.
- Les charges d’outils sont remplies gratuitement à l’entrée d’une nouvelle salle. Recharger une sauvegarde de la même salle ne les restaure pas.
- Les achats, leurs améliorations et les droits Robux survivent au KO et à la renaissance.
- La boutique ne vend ni permis de renaissance, ni résurrection, ni saut automatique vers la sortie.
- Le mode compétitif à équipement fixe est une phase ultérieure ; le MVP est solo.

Les Coins achetés avec des Robux peuvent accélérer la possession d’outils et donc aider en aventure. Il faut l’assumer clairement. Ne pas présenter cette économie comme dépourvue de tout avantage payant. Les records comparatifs équitables nécessiteront un équipement standardisé, pas une simple séparation entre payeurs et non-payeurs.

## 3. Acquisition dans les trente premières secondes

L’origine du temps est le moment où l’avatar devient contrôlable, pas le début du chargement réseau.

| Moment cible | Événement | Coins cumulés | Solde après achat |
|---|---|---:|---:|
| 1 à 3 secondes | Découverte du premier objet | 10 | 10 |
| 3 à 5 secondes | Première réception réussie | 15 | 15 |
| 7 à 10 secondes | Sortie du tutoriel | 65 | 65 |
| 10 à 20 secondes | Radar POP proposé à 50 Coins dans le sas | 65 | 15 |
| Avant 30 secondes | Première activation dans la salle suivante | 65, hors nouveaux gains | Variable |

Les trois primes du tutoriel sont uniques par compte. Recommencer, changer de serveur ou restaurer une sauvegarde ne les verse pas une seconde fois.

La borne montre le Radar en grand, une démonstration de deux secondes et deux commandes : « Acheter 50 Coins » et « Continuer ». Aucun achat forcé. Si le joueur passe, l’objet reste au même prix. Il n’existe ni offre expirante ni fenêtre Robux à cet endroit. Le passage de sortie vers la nouvelle salle reste immédiat ; la consultation de la borne est facultative.

## 4. Catalogue fonctionnel permanent

Les déblocages sont calculés sur le nombre total de salles terminées du compte, toutes expéditions confondues. Ils ne sont jamais remis à zéro. Aucune renaissance n’est obligatoire pour acheter un outil. Une brève démonstration peut être lancée dans le sas, sans examen bloquant supplémentaire.

| Identifiant | Objet | Coins | Salles terminées requises | Emplacement | Livraison |
|---|---|---:|---:|---|---|
| `radar_pop` | Radar POP | 50 | 0 et tutoriel terminé | Actif | MVP |
| `aimant_poche` | Aimant de poche | 150 | 1 | Passif | MVP |
| `ventouse_chantier` | Ventouse de chantier | 300 | 3 | Actif | MVP |
| `parapluie_bonbon` | Parapluie bonbon | 650 | 5 | Actif | MVP |
| `coussin_gonflable` | Coussin gonflable | 1 100 | 8 | Actif | V1 |
| `balise_retour` | Balise de retour | 1 800 | 10 | Actif | V1 |
| `pogo_pop` | Pogo POP | 2 600 | 12 | Actif | V1 |
| `bottes_adhesives` | Bottes adhésives | 3 600 | 14 | Actif | V1 |
| `mini_pont` | Mini-pont pliant | 4 800 | 16 | Actif | V1 |
| `gant_air` | Gant à air | 6 200 | 18 | Actif | V1 |
| `drone_eclaireur` | Drone éclaireur | 8 000 | 20 | Actif | V1 |
| `grappin_balancier` | Grappin balancier | 10 000 | 22 | Actif | V1 |

Le catalogue de base coûte 39 250 Coins. Le prix croissant rémunère la nouveauté et la complexité, pas une supériorité systématique. Un Radar doit rester utile après l’acquisition du Grappin. Les outils non implémentés ne sont pas achetables dans le MVP.

### Effets et limites

**Radar POP.** Boîtier cyan, antenne jaune, écran menthe. Il surligne trois surfaces proches momentanément utilisables. Il ne déplace pas l’avatar, ne prédit pas toutes les collisions et ne remplace pas la signalétique normale. La surbrillance disparaît rapidement pour éviter que le joueur suive une information périmée.

**Aimant de poche.** Petit U corail et jaune à la ceinture. Chaque salle propose exactement six jetons facultatifs de 5 Coins, accessibles également à la main. L’Aimant attire ces jetons, sans en créer, sans les faire réapparaître et sans augmenter leur valeur. Maximum : 30 Coins facultatifs par salle. Il ne change pas les récompenses principales.

**Ventouse de chantier.** Manche jaune et coupelle menthe. Elle stabilise un objet petit ou moyen explicitement éligible. La cible reste unique. Les murs, la sortie et les supports structurels ne sont jamais des cibles. L’effet n’arrête ni les vagues ni tous les objets de la salle.

**Parapluie bonbon.** Voûte rose et citron, poignée bleu nuit. Il ralentit une descente afin de corriger sa réception. Il ne pousse jamais vers le haut et ne protège pas d’un ensevelissement. Son modèle reste au-dessus de l’avatar sans masquer le point d’atterrissage.

**Coussin gonflable.** Petit coussin jaune à coutures roses. Il crée une récupération temporaire sous l’avatar dans un volume libre. Jamais au-dessus, jamais dans un solide, jamais après KO. Une pose refusée ne consomme pas la charge.

**Balise de retour.** Fanion menthe dans un socle violet. Un premier appui mémorise la position stable actuelle ; le suivant demande un retour. Le serveur vérifie que le support existe, que la destination est encore libre et qu’elle reste dans la portée. Si les objets ont recouvert la balise, le retour est refusé sans consommation. Une seule utilisation effective par salle.

**Pogo POP.** Ressort citron dans une coque cyan. Une courte compression prépare un rebond plus haut depuis une surface compatible. Aucun double saut dans le vide. Le déplacement horizontal est légèrement réduit pendant l’impulsion : le joueur gagne de la hauteur, mais doit gérer sa réception.

**Bottes adhésives.** Semelles menthe à pastilles rondes. Elles limitent momentanément la dérive sur une surface mobile, avec une réduction de vitesse. Elles ne permettent ni de marcher au plafond ni de résister à un écrasement.

**Mini-pont pliant.** Passerelle jaune à articulations cyan. Deux appuis autorisés et proches sont nécessaires. Le pont ne peut traverser une salle ni viser une sortie hors portée. La prévisualisation devient rouge si l’un des appuis est invalide.

**Gant à air.** Gant rose à évent cyan. Une impulsion décale un objet éligible de quelques studs. Aucun effet sur les avatars ou la structure. Des poussées répétées ne créent ni Coins ni points de progression.

**Drone éclaireur.** Cube violet à turbines cyan. Il annonce brièvement une arrivée utile déjà programmée dans une vague. Il ne crée aucun objet et ne modifie pas l’ordre de génération. Il s’agit d’un outil actif, pas d’un second compagnon équipé.

**Grappin balancier.** Lanceur cyan, crochet jaune et corde rose. Il fonctionne uniquement avec des ancrages dédiés. Le joueur déclenche l’accroche puis choisit le lâcher avec la commande de saut. Aucune traction automatique jusqu’à une porte, aucun enchaînement infini d’accroches en l’air.

### Paramètres des trois rangs

Dans les cellules ci-dessous, les valeurs sont données dans l’ordre I / II / III. La portée est en studs, les durées et recharges en secondes. Les charges sont gratuites et constantes entre rangs.

| Outil | Portée | Durée | Recharge | Charges par salle | Effet variable |
|---|---|---|---|---:|---|
| Radar | 20 / 24 / 28 | 2 / 2,5 / 3 | 20 / 18 / 16 | 4 | Trois cibles maximum |
| Aimant | 5 / 6 / 7 | Passif | Aucune | Sans activation | Six jetons existants maximum |
| Ventouse | 12 / 14 / 16 | 1,5 / 2 / 2,5 | 25 / 23 / 21 | 4 | Une cible stabilisée |
| Parapluie | Sur soi | 1,5 / 1,8 / 2,1 | 20 / 18 / 16 | 4 | Vitesse de descente ×0,60 / ×0,55 / ×0,50 |
| Coussin | 12 / 14 / 16 sous soi | 3 / 3,5 / 4 | 25 / 23 / 21 | 2 | Largeur 6 / 6,5 / 7 |
| Balise | 18 / 22 / 26 | Retour instantané après préparation | 1 | 1 | Préparation 0,6 / 0,5 / 0,4 |
| Pogo | Sur soi | Préparation 0,4 | 25 / 23 / 21 | 3 | Hauteur ×1,20 / ×1,25 / ×1,30 |
| Bottes | Sur soi | 3 / 3,5 / 4 | 24 / 22 / 20 | 4 | Dérive réduite de 40 / 50 / 60 % |
| Mini-pont | 8 / 9 / 10 | 4 / 5 / 6 | 30 / 28 / 26 | 2 | Franchissement maximal 4 / 5 / 6 |
| Gant | 10 / 12 / 14 | Impulsion 0,25 | 22 / 20 / 18 | 4 | Déplacement maximal 4 / 5 / 6 |
| Drone | 20 / 24 / 28 | 3 / 3,5 / 4 | 25 / 23 / 21 | 4 | Anticipation 1,5 / 2 / 2,5 |
| Grappin | 10 / 12 / 14 | 1,5 / 1,8 / 2 | 30 / 28 / 26 | 3 | Gain vertical maximal 4 / 5 / 6 |

Le rang II coûte 50 % du prix initial, arrondi au multiple de 50 supérieur, minimum 100 Coins. Le rang III coûte le prix initial, minimum 200 Coins. Ce sont des coûts supplémentaires ; il faut posséder le rang précédent. Trois rangs maximum, soit 98 450 Coins pour tous les outils entièrement améliorés. Aucune statistique d’outil ne croît avec les renaissances.

## 5. Récompenses de progression

| Profondeur | Total de base | Trois jalons | Sortie | Permis à la sortie |
|---|---:|---|---:|---:|
| 1 à 4 | 150 | 10 + 10 + 10 | 120 | 1 |
| 5 à 10 | 225 | 15 + 15 + 15 | 180 | 2 |
| 11 à 20 | 350 | 25 + 25 + 25 | 275 | 3 |
| 21 à 40 | 450 | 30 + 30 + 30 | 360 | 4 |
| 41 et plus | 500 | 35 + 35 + 35 | 395 | 4 |

Les jalons correspondent à des zones de progression de la salle, pas à des secondes écoulées. Un raccourci valide peut les franchir sans atterrir sur un objet précis. Chacun ne paie qu’une fois par instance de salle. Repasser, sauter en boucle et recharger la même instance ne paient rien de plus.

La majeure partie des Coins est versée à la sortie pour que l’abandon volontaire après un premier jalon ne soit pas plus rentable que la réussite. Le KO conserve ce qui a été effectivement gagné. Le serveur valide les passages et rejette une séquence impossible, sans imposer une durée minimale qui pénaliserait les bons joueurs.

Sources secondaires : 50 Coins à la première découverte d’une famille, deux contrats quotidiens de pratique de 50 Coins, 250 Coins pour un défi hebdomadaire terminé. Chaque contrat ne paie qu’une fois. Aucun bonus automatique de connexion, aucune sanction si un jour est manqué. Ces gains ne reçoivent pas le multiplicateur de renaissance.

### Arrondi et affichage

Le bonus de renaissance s’applique uniquement au total de base : jalons et sortie. Il exclut tutoriel, jetons facultatifs, contrats, découvertes et Coins achetés.

Utiliser des points de base entiers : 400 par rang, maximum 4 000, sur un dénominateur de 10 000. À chaque nouveau jalon, calculer le montant arrondi du cumul de base, puis retirer le cumul déjà payé. Ne pas arrondir chaque paiement séparément. Ainsi le total affiché correspond toujours au total effectivement crédité. Le taux est figé à l’entrée de la salle ; une renaissance ne s’effectue que dans le sas.

## 6. Vingt-quatre achats cosmétiques en Coins

Tous sont fixes, prévisualisables, permanents et sans bonus de puissance. Le détail des conditions, identifiants et visuels est dans la configuration.

| Famille | Objets et prix Coins | Intention visuelle |
|---|---|---|
| Traces | Ruban citron 75 ; Bulles menthe 250 ; Confettis POP 750 ; Ruban aurore 2 500 | Effets courts derrière les pieds, jamais devant une réception |
| Habillages d’outil | Radar citron 100 ; Parapluie pastèque 500 ; Grappin chrome doux 1 500 ; Habillage holographique 5 000 | Silhouette et repères fonctionnels inchangés |
| Compagnons | BOB papier 500 ; Canard mousse 1 500 ; BOB chantier 4 000 ; BOB cosmique 12 000 | Un seul compagnon, hors de la visée, sans récolte automatique |
| Réceptions | Anneau menthe 150 ; POP étoiles 600 ; Disque vinyle 1 800 ; Anneau prisme 6 000 | Effets bas, courts et sans flash |
| Sorties réussies | Confettis citron 300 ; Envol de canards 1 200 ; Feu d’artifice mousse 3 500 ; Orbite de mini-planètes 10 000 | Célébrations surtout visibles dans le sas |
| Sas personnel | Hublot cyan 1 000 ; Atelier fête rose 3 000 ; Atelier lavande 8 000 ; Atelier aurore 20 000 | Personnalisation durable sans changer la géométrie jouable |

Le mode confort réduit ces effets sans masquer les informations de danger. Posséder un habillage ne suffit pas à obtenir l’outil correspondant. Une entrée déjà possédée affiche « Possédé » ; elle ne peut pas être achetée deux fois.

## 7. Renaissances et longues expéditions

La renaissance remet la profondeur à 1 et renouvelle les contrats de cycle. Elle ne remet pas le compte à zéro. Elle est facultative et disponible uniquement dans un sas sécurisé. Le joueur peut continuer son expédition cinq heures ou davantage s’il reste en vie.

Les permis sont permanents entre les vies. Les premières salles permettent donc aussi aux débutants de préparer une renaissance. Pour la première seulement, terminer trois familles différentes constitue une qualification supplémentaire. Elle reste acquise. Aucun achat de Coins ne compte comme qualification ou permis.

Le coût du prochain rang R est `min(40 + 15 × (R − 1), 160)` permis. Il n’y a aucun frais Coins. Le bonus de Coins est de 4 % par rang, plafonné à 40 %. Aucun bonus de saut, vitesse, résistance ou recharge.

| Rang obtenu | Coût du rang | Coût cumulé depuis zéro | Bonus de base |
|---|---:|---:|---:|
| 1 | 40 | 40 | 4 % |
| 2 | 55 | 95 | 8 % |
| 5 | 100 | 350 | 20 % |
| 10 | 160 | 1 060 | 40 % |
| Au-delà | 160 chacun | Progression continue | Reste à 40 % |

Les permis excédentaires sont conservés. Si le solde finance plusieurs rangs, une renaissance multiple les attribue en une seule transaction et une seule transition. Exemple : 326 permis financent quatre rangs pour 250 permis ; il en reste 76. Cela évite de pousser le joueur à interrompre chaque belle expédition dès le premier seuil atteint.

L’écran de confirmation indique le coût exact, les rangs gagnés, le nouveau bonus, le solde restant et « Tu repars à la salle 1 ». Il liste les achats conservés. Le serveur applique l’opération de façon atomique et évite une double consommation sur double clic ou reconnexion.

Après le rang 10, le compteur reste ouvert, mais la puissance économique ne croît plus. Les récompenses viennent des rangs visuels, titres, palettes et variantes de contrats. « Infini » signifie absence de dernier rang ou dernière profondeur, pas promesse d’une infinité d’assets artisanaux.

## 8. Simulations de référence

Hypothèses : 30 secondes d’introduction ; 60 secondes en moyenne par salle 1–4 ; 90 secondes aux 5–10 ; 150 secondes aux 11–20 ; 180 secondes aux 21–40 ; 240 secondes ensuite. Ces valeurs ne sont pas des délais de défaite. Simulation du catalogue V1, sans KO, renaissance, jetons facultatifs, bonus, amélioration ou Robux. Seules les salles terminées sont comptées ; les éventuels jalons déjà payés de la salle en cours sont exclus de ce tableau.

| Temps | Salles terminées | Coins gagnés | Permis | Outils achetables dans l’ordre | Coins restants |
|---|---:|---:|---:|---:|---:|
| 30 secondes | 0 | 65 | 0 | 1 | 15 |
| 5 minutes | 4 | 665 | 4 | 3 | 165 |
| 20 minutes | 12 | 2 715 | 22 | 5 | 465 |
| 1 heure | 27 | 8 665 | 74 | 7 | 2 015 |
| 5 heures | 90 | 39 515 | 326 | 12 | 265 |

Dans le MVP limité aux quatre premiers outils, les achats suivants sont des améliorations ou cosmétiques ; ne pas annoncer les acquisitions V1 comme déjà disponibles. Un joueur réel peut préférer économiser, améliorer un outil ou personnaliser son avatar. Les décès et achats différents changent ces chiffres. Il faut mesurer les distributions de gains, pas seulement une moyenne idéale.

## 9. Boutique Robux et mode désactivé

| Offre fixe | Prix de base proposé |
|---|---:|
| Peinture signature | 49 Robux |
| Ensemble assorti : habillage, trace, réception | 149 Robux |
| BOB miniature cosmétique | 199 Robux |
| Machine personnelle dans le sas | 299 Robux |
| Grand ensemble fête, cinq éléments indiqués | 399 Robux |

Packs de Coins proposés : 800 pour 99 Robux ; 2 400 pour 249 ; 5 500 pour 499. Aucun permis inclus. Les quantités et prix sont des valeurs de test, pas une offre déjà publiée.

La boutique premium est volontairement accessible depuis le sas ; aucune fenêtre après KO, aucun compte à rebours artificiel, aucune remise fictive, aucune récompense aléatoire. Chaque contenu est visible avant achat. Le joueur peut fermer immédiatement et poursuivre.

Tous les `product_id` et `gamepass_id` sont livrés à `null`. `robux_shop_enabled` vaut `false`. Dans cet état, aucun bouton ne déclenche un achat réel ; les aperçus de développement portent « Boutique indisponible ». Un identifiant absent doit désactiver son offre, jamais déclencher un faux achat réussi. Les prix affichés en production proviendront de la plateforme ; les prix de base du fichier ne doivent pas contredire ceux du dialogue officiel.

Les droits doivent être accordés par validation serveur, avec traitement idempotent des achats et restauration des éléments possédés. Un échec réseau ne doit ni débiter des Coins locaux ni afficher une livraison non confirmée. L’activation commerciale est une étape distincte après configuration et tests.

## 10. Recette et rééquilibrage

Vérifier avant lancement : somme exacte des jalons et de la sortie ; tutoriel payé une seule fois ; achat du Radar réalisable avant 30 secondes contrôlables ; impossibilité de double récompense ; charges préservées après rechargement ; aucun retrait d’inventaire à la renaissance ; transaction multiple correcte ; KO sans suppression des Coins ou permis.

Tester également chaque famille de salle sans outil. Une voie sûre devenue impossible signifie un problème de génération, pas une opportunité de vendre un gadget. Les premiers outils doivent rester utilisés tard ; sinon ils sont devenus des taxes de progression sans intérêt.

Mesurer les acquisitions à 30 secondes, 5 minutes et 20 minutes, les Coins gagnés par salle, les soldes avant achat, les objets réellement équipés, la fréquence des activations utiles et les abandons après KO. Rééquilibrer d’abord les récompenses, prix et scénarios de salle. Ne pas allonger artificiellement les attentes ou réduire le plaisir de base pour rendre les Robux nécessaires.
