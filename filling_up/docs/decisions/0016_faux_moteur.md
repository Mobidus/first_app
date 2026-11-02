# 0016 — Faux moteur d'intégration (sans Studio)

`tests/_harness/FakeEngine.luau` émule, en Luau sous Lune, les parties du moteur Roblox dont dépend le serveur :
* arbre d'instances (parent, attributs, tags, `PivotTo`) ;
* signaux et Heartbeat, ainsi que `task.delay` et `task.wait`, pilotés par une horloge simulée (`E:step`) ;
* requêtes spatiales en boîtes alignées (`Raycast`, `GetPartBoundsInBox`, `GetPartsInPart`) ;
* Players et personnages, TweenService, CollectionService, HttpService, DataStoreService (sémantique
  `UpdateAsync`, pannes injectables), MarketplaceService et Remotes journalisés.

La suite `integration` exécute le **vrai** `src/server/Main.server` et tous ses services. Elle couvre 10 scénarios :
* première session et achat du Radar ;
* 30 transitions sans croissance des connexions ;
* KO par ensevelissement et recommencement ; aucun KO sous une table ouverte ;
* reprise après déconnexion ; départ pendant le chargement ;
* panne de sauvegarde à la sortie ;
* renaissance ;
* deux joueurs isolés ;
* intentions forgées.

Le test de mutation l'a confirmé : réintroduire le défaut de démarrage fait échouer 9 scénarios ; retirer le blocage
de progression sans sauvegarde en fait échouer 1.

**Ce n'est pas Studio.** Pas de physique (les objets ne tombent pas), pas de collisions, pas de rendu, pas de réseau.
Les critères Studio restent NOT_RUN. La preuve apportée : le code moteur s'exécute sans erreur et respecte, dans ces
scénarios, les règles d'économie, de persistance et de transition.
