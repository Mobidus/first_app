# Relecture indépendante du code moteur (sans Studio ni vérificateur de types)

Le 2 novembre 2026, un agent séparé a relu en lecture seule `src/server`, `src/client` et `Main`. Il a remonté 17
constats. Chacun a été revérifié dans le code avant d'être corrigé. Tests ajoutés : `profile` (course avec un
stockage qui cède la main, CompleteRoom, UpdateCharges), `onboarding` (journal d'entrées borné) et `routes` (zone
d'apparition).

| # | Gravité | Constat | Correction |
|---|---|---|---|
| 1 | Haute | `CharacterAdded:Wait()` attendait le spawn *suivant* : blocage de tout joueur | attente seulement sans personnage |
| 2 | Haute | La sonde DataStore ne pouvait pas échouer (erreur renvoyée, pas levée) | `error(err)` si la sonde échoue |
| 3 | Haute | Double réclamation de jalons et jetons (boucle à 10 Hz + écriture qui cède la main + masque périmé) | registre `roomClaims` dans le profil (cause racine) + verrou `claiming` ; test de course : 5 requêtes, 1 paiement |
| 4 | Haute | Cellules de monde partagées entre joueurs | une case de 4 000 studs par session (`RoomGenerator.cellsFor`) ; Max Players = 1 recommandé |
| 5 | Moyenne | Salle initiale non préparée : joueur bloqué dans le sas | `continueFromSas` gère `Preparing` et réessaie |
| 6 | Moyenne | Course entre la renaissance et la porte du sas | `txBusy` : porte ignorée pendant l'écriture ; fin de salle créditée d'abord |
| 7 | Moyenne | Sas ouvert au nord ; aucune gestion du respawn | murs de part et d'autre de la porte ; `respawnInPlace` |
| 8 | Moyenne | Départ pendant le chargement : verrou de profil conservé | libération si le joueur est parti |
| 9 | Moyenne | 3 à 4 écritures successives à la sortie avant la téléportation | téléportation d'abord, puis une seule mutation `CompleteRoom` ; nouvel essai bloquant avant de continuer |
| 10 | Moyenne | Charges d'outils rechargées à la reconnexion | `UpdateCharges` après chaque usage ; checkpoint dès la salle 1 |
| 11 | Types | Champs du type `Pool` non déclarés | type complété ; valeur par défaut issue de la config |
| 12 | Types | Accès nil possibles en strict | variables locales vérifiées |
| 13 | Visuel | Rotation des cylindres de générateur ignorée | indices de rotation appliqués, vérifiés sur le `.rbxm` |
| 14 | Basse | Test « enfoui » non filtré (plafond, paliers, volume de sortie comptés) | 5 sondes limitées aux colliders de remplissage |
| 15 | Basse | Tutoriel : mutations et événements à chaque image | une requête par événement ; entrée = horodatage seul ; indice limité à 2 Hz |
| 16 | Basse | Nouvel essai qui survit au départ ; double nettoyage | `removed` posé en premier, session retirée avant toute attente |
| 17 | Basse | Connexion RenderStepped empilée ; rayons touchant des volumes sans collision | une connexion par personnage ; `RespectCanCollide` |

Limite : cette relecture ne remplace ni `luau-analyze` ni Studio. Le code moteur n'a toujours pas été exécuté dans
Roblox.
