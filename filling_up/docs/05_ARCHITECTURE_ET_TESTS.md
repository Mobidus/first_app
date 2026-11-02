# Architecture et tests de Filling Up

## 1 Contrat de fonctionnement

Filling Up est une expédition de salles successives, conçue d’abord pour un joueur par expédition. Les objets arrivent par vagues temporelles et peuvent ensevelir le personnage. Sortir conduit à la salle suivante ; aucun retour au hub, écran de résultat ni renaissance ne sont imposés entre deux salles. La profondeur de l’expédition peut continuer à augmenter tant que le joueur ne perd pas.

Une salle ne possède **aucune durée maximale de survie**. La logique de défaite ne doit jamais lire un compte à rebours de salle, `elapsedTime >= roomDuration` ou `fillPercent >= 100`. L’écoulement du temps peut déclencher une vague ou le mouvement annoncé d’une plateforme. Le KO résulte ensuite d’une situation physique réelle : ensevelissement confirmé ou franchissement d’un volume de chute mortelle. Une salle très remplie ne tue pas un personnage encore libre de ses mouvements.

La difficulté augmente dans une enveloppe physiquement réalisable, puis varie par combinaison des parcours, objets, formats et sorties. « Quasi illimitée » ne signifie ni une précision infinie des nombres, ni une infinité de modèles 3D, ni une augmentation sans borne de la vitesse des vagues. Aucun joueur n’a besoin d’acheter un outil pour franchir la route principale.

Les 10 secondes de compréhension et 30 secondes de première acquisition sont des objectifs d’expérience utilisateur mesurés, pas des délais imposés au joueur. Les 65 Coins du tutoriel sont attribués une fois ; l’achat du Radar à 50 Coins laisse un solde de 15 Coins.

Les peluches déformables font partie de la première tranche jouable. Mallow doit se comprimer à l’impact et se stabiliser en appui fiable. Il ne s’agit pas d’une simulation intégrale de matière molle : les collisions restent autoritatives côté serveur et la déformation du rig reste visuelle côté client.

### Sources de vérité

| Fichier | Informations autoritatives |
|---|---|
| `config/economy.json` | Prix, gains, plafonds par action, permis, renaissance et offres |
| `config/rooms.json` | Familles, formats, sorties, variantes et compatibilités |
| `config/runtime.json` | Budgets, collisions, contrôleur, vagues et paramètres de difficulté |
| `assets/manifest.json` | Références, livrables, droits, imports et identifiants Roblox |
| `tasks/backlog.json` | Dépendances, livrables et critères de chaque tâche |

Le code et les écrans ne doivent pas recopier des constantes concurrentes. Une étape de compilation valide les fichiers de configuration, puis produit des modules Luau de configuration. Une valeur non encore calibrée reste explicitement identifiée comme hypothèse ; elle ne devient pas un résultat de test par simple intégration au code.

## 2 Projet et chaîne de développement

La chaîne cible associe Luau strict, un projet Rojo et Roblox Studio. Le préflight vérifie les exécutables, versions réellement installées, accès à Studio, extensions ou ponts disponibles et droits du compte. Il inscrit les versions retenues dans un fichier verrouillé. Aucune version ne doit être inventée pour compléter le document.

Rojo synchronise ou construit le projet ; il ne remplace pas Roblox Studio pour tester la physique, les collisions, le rendu ou le comportement des achats. Un interpréteur Luau hors Roblox ne fournit pas automatiquement les services du moteur. Les tests de logique pure sont donc isolés des adaptateurs qui utilisent ces services.

| Emplacement cible | Contenu |
|---|---|
| `src/shared/Types` | Types publics, commandes et événements |
| `src/shared/Domain` | Calculs déterministes et machines à états sans services Roblox |
| `src/shared/GeneratedConfig` | Configuration compilée depuis les fichiers JSON |
| `src/server/Services` | Autorité de jeu, sauvegardes, achats et génération |
| `src/client/Controllers` | Contrôles, présentation, caméra, HUD et effets |
| `tests/unit` | Calculs, transitions, génération et rejouabilité déterministe |
| `tests/studio` | Scènes de physique, réseau, mobile, persistance et achats |
| `assets/source` et `assets/import` | Sources modifiables et exports contrôlés |
| `tools` | Contrôles reproductibles, compilation de configuration et rapports |
| `reports` et `docs/decisions` | Preuves de test et décisions prises pendant l’exécution |

La tâche T04 crée un point d’entrée de contrôle, `tools/game_checks.py`, dont les commandes sont décrites dans le plan. Ce fichier n’est pas fourni comme moteur de test déjà fonctionnel : l’IA doit l’implémenter et le connecter aux outils détectés. Un composant absent produit un résultat `blocked`, jamais un succès vide.

T04 dépend du préflight T00, pas de la fin de fabrication des assets. Le socle et le contrôleur peuvent donc être construits en graybox pendant la phase artistique. T07 reste dépendante de T03 et T06 : cette souplesse ne permet pas de clôturer une première salle habillée ou sa recette artistique sans les assets validés.

## 3 Modules serveur et client

| Module à développer | Responsabilité et frontière |
|---|---|
| `ExpeditionService` | Créer une expédition, changer de salle, suspendre, terminer et extraire |
| `RoomGenerator` | Produire une salle déterministe depuis sa seed et sa profondeur |
| `RouteValidator` | Vérifier appuis, dégagements et accès à la sortie |
| `WaveDirector` | Programmer les vagues et leurs annonces, sans décider d’un KO |
| `ObjectPool` | Acquérir, réinitialiser et restituer les objets réutilisables |
| `BurialService` | Détecter l’ensevelissement et émettre un KO confirmé |
| `ExitService` | Valider une sortie et demander une transition unique |
| `RewardService` | Attribuer les récompenses et journaliser leur identité |
| `InventoryService` | Vérifier possession, équipement, charges et améliorations |
| `RebirthService` | Vérifier une demande volontaire et consommer les permis |
| `PlayerProfileRepository` | Charger, verrouiller, migrer et sauvegarder le profil |
| `PurchaseService` | Valider les reçus et délivrer durablement les achats |
| `TelemetryService` | Produire événements et mesures sans gérer l’économie |

Les contrôleurs clients consomment des états autoritatifs. `HUDController` affiche les gains ; il ne crédite pas le portefeuille. `ToolController` fournit une intention d’utilisation ; le serveur vérifie l’objet possédé, son équipement, sa charge, sa portée et sa cible. `EffectsController` peut déclencher un retour visuel immédiat, mais annule ou corrige l’effet si l’action est refusée.

`PlushDeformationController` reconstruit la réaction visuelle des peluches depuis la pose de référence et les événements d’impact serveur. Il n’émet ni récompense ni KO. La désactivation des déformations sur un appareil modeste ne change pas les collisions ou les résultats de partie.

Le nom `ExpeditionService` évite une confusion avec le service de moteur `RunService`. Le nom `PlayerProfileRepository` désigne un module du projet et ne suppose l’installation d’une bibliothèque tierce portant un nom similaire.

## 4 Contrats persistants et état de session

Les noms ci-dessous définissent le contrat interne à implémenter. Le compilateur de configuration réalise explicitement la correspondance avec les clés des JSON, sans supposer que ces fichiers partagent déjà ce schéma.

### Profil

`PlayerProfile` contient `schemaVersion`, `revision`, `coins`, `xp`, `permits`, `rebirthCount`, `ownedTools`, `toolRanks`, `ownedCosmetics`, `equippedLoadout`, `roomMastery`, `bestDepth`, `tutorialFlags`, `checkpoint` et `settings`.

Les montants sont des entiers non négatifs. Le code refuse les valeurs non finies, les identifiants inconnus et les résultats sortant des limites numériques configurées. Les Coins ne sont pas des Robux et ne sont pas convertibles en argent. Coins, permis, propriétés, niveaux permanents et achats ne sont pas effacés par un KO. Une renaissance ne retire que les permis annoncés et réinitialise les éléments de cycle explicitement prévus.

### Expédition

`ExpeditionState` contient `runId`, `seed`, `configVersion`, `controllerProfileId`, `depth`, `state`, `roomId`, `waveIndex`, `roomRewardMask`, `lastCommittedDepth`, `equippedLoadoutSnapshot` et `checkpointRevision`.

| État | Entrée autorisée | Sortie autorisée |
|---|---|---|
| `Preparing` | Profil chargé et configuration valide | `Active` après préparation de la salle |
| `Active` | Salle prête, avatar placé et validation serveur acquise | `Transitioning`, `KO` ou suspension contrôlée |
| `Transitioning` | Sortie validée une seule fois | `Active` dans la nouvelle salle, ou `Suspended` |
| `Suspended` | Checkpoint enregistré ou interruption reconnue | `Preparing` à la reprise |
| `KO` | Cause physique confirmée | Fin de cette expédition ; une nouvelle reçoit un autre `runId` |
| `Extracted` | Extraction ou renaissance volontaire dans le sas | Nouvelle expédition éventuelle |

`depth` est incrémenté par une seule transition serveur. Deux contacts avec la sortie, une demande client répétée ou une reconnexion ne créent jamais deux salles gagnées.

### Salle et objet

`RoomDefinition` expose `templateId`, `familyId`, `formatId`, `exitType`, `seed`, `routeGraph`, `spawnZones`, `safeZones`, `exitClearance`, `waveSchedule`, `collisionBudget` et `themeManifestId`.

Chaque objet possède `objectInstanceId`, `assetId`, `behaviorId`, `collisionProxyId`, `supportSockets`, `spawnState`, `ownershipState` et `rewardTags`. Un objet décoratif n’est pas automatiquement une surface jouable. Les objets de pool doivent effacer connexions, vitesses, propriétaires, effets et anciens identifiants de récompense avant réutilisation.

## 5 Autorité réseau et sécurité

Les remotes représentent des intentions bornées. Le serveur ne reçoit jamais « ajoute 500 Coins » ou « cette salle est réussie » comme ordre accepté.

| Intention cliente | Validation serveur obligatoire |
|---|---|
| `RequestToolUse(toolId, targetId, requestId)` | Possession, équipement, charge, portée, cible et état de salle |
| `RequestEquip(itemId, slot, requestId)` | Propriété, compatibilité, emplacement et contexte autorisé |
| `RequestCoinPurchase(skuId, requestId)` | Prix canonique, qualification, solde, propriété et unicité |
| `RequestRebirth(quantity, expectedRevision, previewToken, requestId)` | Présence au sas, quantité entière admissible, révision attendue, aperçu serveur valide et absence de transaction concurrente |
| `RequestSaveExit(requestId)` | Point de sauvegarde disponible et écriture durable |

Chaque requête impose types, taille maximale, liste d’identifiants autorisés et limitation de fréquence. Les événements serveur de sortie utilisent les positions et interactions connues du serveur. Le client ne fournit ni prix faisant autorité ni nombre de permis à consommer.

L’aperçu de renaissance est calculé par le serveur pour une quantité donnée. Son jeton est lié au joueur, à la quantité et à la révision du profil. Lors de la confirmation, le serveur recalcule les coûts cumulés, contrôle le jeton et la révision, puis engage une seule mutation. Une quantité modifiée, un aperçu périmé ou un profil ayant changé exige un nouvel aperçu ; aucun coût transmis par le client n’est utilisé comme autorité.

Les scores impossibles ou mouvements suspects sont journalisés. Une divergence physique isolée ne doit pas provoquer automatiquement un bannissement : elle peut résulter du réseau ou d’un défaut du contrôleur. Les achats et sauvegardes passent par une file de mutations sérialisée par profil, avec protection contre les sessions concurrentes.

## 6 Génération des parcours et progression de difficulté

La génération construit d’abord un graphe de surfaces atteignables, puis habille ses nœuds avec des objets. La physique du spectacle ne décide pas seule si une salle est franchissable. Les routes principales utilisent des supports garantis ; les raccourcis peuvent demander davantage de précision.

Cette garantie décrit un parcours initial franchissable et des appuis mécaniquement prévisibles, pas une immunité permanente contre le remplissage. Des vagues ultérieures peuvent recouvrir une partie du parcours et ensevelir le joueur. Le dernier appui de sortie et son volume protégé restent traités séparément pour éviter une ouverture impossible à franchir.

Le contrôleur est mesuré dans une scène dédiée : distance horizontale, hauteur, contrôle aérien, réception, rebond et accrochage. Les dimensions des sauts sont exprimées en ratios de ces mesures et vérifiées pour les formes d’avatar admises. Les colliders du personnage sont normalisés ; acheter une apparence ne doit pas modifier la capacité à franchir une fenêtre.

Le validateur contrôle : connexion entrée-sortie, surface minimale de réception, espace au-dessus de la tête, absence de collision dans l’arc du saut, support du dernier appui et compatibilité des mouvements. Une distance réalisable sur le papier ne suffit pas si une poutre intercepte le saut.

Chaque sortie dispose d’un volume dégagé d’au moins **8 × 8 × 10 studs**, orienté selon l’ouverture. Ce volume, son approche et le dernier appui sont exclus des dépôts susceptibles d’obturer le passage. Il ne suffit pas de préserver uniquement la porte si le carton permettant de l’atteindre disparaît.

La difficulté est calculée à partir de la profondeur, mais ses paramètres physiques restent bornés. Après le palier supérieur de maîtrise, le directeur alterne familles, formats, sorties et combinaisons certifiées. Il évite une longue série de salles nécessitant le même geste. Un échec de validation déclenche une variante de secours certifiée, avec un événement de diagnostic ; il n’envoie pas la salle non vérifiée au joueur.

## 7 Vagues et simulation hybride

Les vagues continuent à arriver pendant la présence du joueur. Leurs annonces précèdent les impacts. Elles ne sont pas remplacées par trois lots seulement déclenchés à l’avancement : cette variante supprimerait la pression du remplissage voulue pour le jeu.

La salle active utilise au plus **40 objets dynamiques** au point de départ du prototype. Les autres volumes deviennent des assemblages stables, des collisions simplifiées ou des éléments visuels locaux. Les supports garantis s’immobilisent après installation et ne sont pas renversés par une collision décorative.

Le budget ne peut pas supprimer silencieusement un objet sous les pieds du joueur. La consolidation vérifie les appuis occupés et les interactions critiques. Les objets mobiles utiles au parcours sont pilotés par une trajectoire déterministe ; ils ne reposent pas sur une pile physique laissée libre.

Les cadences et annonces utilisent le temps de simulation, pas le nombre d’images rendues. Les budgets serveur et client sont mesurés séparément. Un ralentissement mobile ne doit pas accélérer les vagues ou attribuer deux fois un contact.

### Peluches et déformations

Le lot initial comprend le rig de Mallow, une racine physique non déformante et des colliders serveur séparés du mesh visuel. Le ventre possède neuf contrôles de déformation et au plus six contrôles secondaires pour tête, oreilles et membres. Les poses partent de la référence et ne s’additionnent pas impact après impact. Le visuel suit la racine côté client ; il ne doit pas être soudé en état ancré à une racine qui doit tomber.

Le serveur transmet au minimum `objectInstanceId`, `serverTime`, `impactNormal`, `impactStrength` et `settleState`. Le client reconstruit la pose à partir de ces données. Il utilise des translations coordonnées et rotations de bones, pas une propriété d’échelle supposée sur `Bone.Transform`, qui est un CFrame. Il ne réplique pas une transformation de chaque bone à chaque image.

Les réglages initiaux de `config/runtime.json` sont : six peluches proches animées au maximum ; étirement apparent vertical de chute au plus ×1,12 ; compression verticale jusqu’à ×0,72 ; compression en 0,09 seconde, rebond en 0,18 seconde et amortissement principal en 0,65 seconde. La pose totale doit respecter le plafond de 0,90 seconde défini par la configuration ; ces phases ne doivent pas être additionnées naïvement si leur composition dépasse ce plafond.

Les grandes compressions précèdent l’activation de l’appui garanti. Une fois cet appui actif, le dessus visible et la surface de collision restent à moins de 0,25 stud l’un de l’autre. La balise de réception apparaît lorsque le support est stabilisé. Un contact précoce conserve une réponse physique cohérente ; le joueur ne doit ni traverser l’ours ni flotter au-dessus d’un mesh fortement écrasé.

Les tests comprennent cent chutes et réinitialisations dans le pool sans dérive du rig, puis une scène de six peluches proches et quarante objets dynamiques. Comparer déformations activées et désactivées : récompenses, KO et collisions doivent produire les mêmes résultats. Un changement de niveau de détail ne crée ni ne supprime un appui.

## 8 Ensevelissement et causes de KO

`BurialService` examine les joueurs actifs à **10 Hz**. Un objet passant au-dessus de l’avatar n’est pas une preuve suffisante. Le test utilise seulement les collisions pertinentes des objets de remplissage et leurs proxies ; il exclut les effets visuels, le plafond architectural, les volumes de sortie et les objets sans collision.

La détection suit quatre étapes : recherche spatiale des candidats proches ; mesure de l’espace libre autour du haut du corps ; vérification des possibilités de dégagement compatibles avec le gabarit ; confirmation temporelle avec hystérésis. Une situation bloquée doit persister **1,2 seconde** avant KO. Cette valeur est une grâce locale à calibrer, pas un chronomètre de salle.

Le prototype peut combiner plusieurs sondes autour de la tête et du torse avec des tests de passage du collider. Il ne doit pas conclure sur un seul raycast ou sur le chevauchement des grandes bounding boxes de meshes creux. L’immobilité du joueur ne suffit jamais : rester volontairement sous une table ouverte doit être permis.

Quand un dégagement redevient disponible, l’alerte est annulée. Les valeurs exactes de couverture et de dégagement sont calibrées sur les scènes de recette. Le HUD indique « DÉGAGE-TOI » et la direction libre lorsque celle-ci existe, sans afficher une barre globale de temps avant défaite.

Les autres KO admis sont listés explicitement dans la configuration, notamment franchissement d’un volume de chute mortelle. Un raté récupéré sur un palier inférieur ne compte pas comme un KO. Aucune fonction de KO n’est appelée depuis un simple seuil de remplissage.

## 9 Sauvegardes et attribution unique

Une récompense possède une identité stable, dérivée de `runId`, profondeur et jalon. Le masque de récompenses de la salle en cours et la dernière profondeur engagée empêchent la répétition des gains. Les anciens niveaux déjà engagés peuvent être rejetés par une borne monotone ; il n’est pas nécessaire de garder un événement de chaque saut en mémoire pendant cinq heures.

L’achat en Coins effectue ensemble la vérification du solde, le débit et l’ajout de la propriété dans la mutation de profil. Une panne ne doit pas laisser le joueur débité sans objet. Une renaissance consomme les permis, augmente le rang et termine volontairement le run dans une transition idempotente. Elle conserve les excédents de permis prévus par l’économie.

Les achats Robux utilisent une attribution durable par identifiant de reçu. Le signal de fermeture d’une fenêtre de paiement n’est pas une preuve de paiement. La délivrance ne devient définitive qu’après sauvegarde réussie ; les retries ne délivrent pas deux fois. Les identifiants de produits restent `null` tant qu’ils ne sont pas créés dans un environnement autorisé ; un placeholder ne doit jamais déclencher une vente réelle.

Un checkpoint est enregistré entre les salles. « Sauvegarder et quitter » termine uniquement après confirmation durable. Une déconnexion en salle reprend au début de cette salle avec la même seed et les jalons déjà récompensés marqués ; cela évite de devoir sérialiser chaque corps rigide tout en empêchant de récolter plusieurs fois les mêmes gains. Les classements futurs distingueront les reprises des runs continus selon leurs règles propres.

Une expédition verrouille sa version de configuration. Toute migration d’un checkpoint devenu incompatible doit préserver les biens et expliquer la reprise proposée, sans fabriquer un record correspondant à des règles différentes.

## 10 Sessions de cinq heures et mémoire bornée

Le runtime conserve au maximum **trois modules résidents** : salle active, salle suivante préchargée et sas de transition. Une seule salle simule ses vagues. La salle précédente est libérée après engagement de la transition. Les modèles source réutilisables du pool ne doivent pas être confondus avec des salles actives supplémentaires.

La scène se recentre sur un repère local à chaque transition ; elle ne construit pas une chaîne de milliers de pièces éloignée de l’origine. La seed et la profondeur suffisent à reconstruire un historique ; il n’est pas conservé sous forme de géométrie. Les connexions, tâches différées et effets sont rattachés à un propriétaire de salle puis nettoyés lors de sa destruction.

La transition conserve les contrôles et évite un écran de victoire bloquant. Si la prochaine salle n’est pas prête, le joueur reste dans le sas sûr avec un état de chargement honnête. Aucun échec ne résulte de ce chargement. Le sas permet l’achat, l’équipement, la sauvegarde ou une renaissance ; continuer reste l’action principale.

## 11 Matrice de tests et preuves attendues

| Suite | Exemples obligatoires | Preuve attendue |
|---|---|---|
| Configuration | Références, prix, identifiants, compatibilités et bornes | Rapport de validation et erreurs bloquantes |
| Économie pure | Tutoriel 65, Radar 50, solde 15 ; doublons ; permis insuffisants | Assertions et simulation reproductible |
| Machine à états | Double sortie, KO pendant transition, reprise et renaissance | Traces de transitions attendues |
| Génération | Milliers de seeds et toutes les combinaisons certifiées | Liste des seeds testées et échecs reproduisibles |
| Peluches Studio | Mallow sous plusieurs orientations ; 100 chutes ; six peluches proches et 40 objets dynamiques | Absence de dérive, écarts de réception dans 0,25 stud et mesures de charge |
| Ensevelissement Studio | Sous table ouverte, vrai ensevelissement, objet transitoire, sortie | Captures et résultats des scènes de référence |
| Réseau Studio | Latence, requêtes répétées, reconnexion et client incohérent | Aucun gain dupliqué et erreurs contrôlées |
| Achats | Annulation, reçu différé, double reçu, sauvegarde indisponible | Attribution durable unique dans un environnement autorisé |
| Endurance | 80, 200 puis 1 000 salles simulées ; session réelle de cinq heures | Mesures mémoire, instances, connexions et erreurs |
| Mobile | Saut, caméra, taille HUD, utilisation Radar et achats | Essais sur appareils définis, pas seulement émulateur |

La simulation accélérée de **18 000 secondes** vérifie les états et budgets logiques. Elle ne prouve pas cinq heures de stabilité physique ou réseau. Le test réel de cinq heures doit être exécuté dans Roblox avec un pilote de test et des relevés périodiques. La suppression du besoin d’intervention humaine n’autorise pas à remplacer cette preuve par une estimation.

Les scripts `validate_pack.py` et `simulate_economy.py` du dossier de spécification valident la cohérence du dossier et de ses hypothèses. Ils ne sont pas des tests du jeu construit. Leur réussite ne clôt aucune tâche de physique, caméra, réseau ou achat.

## 12 Limites et autorisations

La coopération et les classements à équipement standardisé sont postérieurs au MVP. Aucune implémentation coopérative ne commence avant décision explicite sur l’attente du groupe, les joueurs séparés, les KO, les récompenses et les reprises. Un kit standardisé doit neutraliser les avantages des outils personnels ; le simple fait d’appeler un classement « équitable » ne le réalise pas.

L’IA peut préparer les exports, générer du code, construire un fichier local et exécuter les tests dont l’environnement est disponible. Elle s’arrête aux étapes nécessitant une autorisation manquante : compte, installation protégée, publication, import externe restreint ou produit payant. Elle ne déduit pas d’une demande d’autonomie une autorisation de dépenser des Robux, de publier le jeu ou d’accepter des conditions tierces.

### Références techniques

- Requêtes spatiales : https://create.roblox.com/docs/workspace/raycasting
- Opérations de scène : https://create.roblox.com/docs/reference/engine/classes/WorldRoot
- Synchronisation Rojo : https://rojo.space/docs/v7/sync-details/
- Achats répétables : https://create.roblox.com/docs/production/monetization/developer-products
- Service de transactions : https://create.roblox.com/docs/reference/engine/classes/MarketplaceService

