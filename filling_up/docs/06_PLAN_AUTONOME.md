# Plan de développement autonome de Filling Up

## 1 Résultat attendu et règle de progression

Ce plan organise la réalisation du jeu ; il ne présente aucune tâche comme déjà exécutée. Le fichier `tasks/backlog.json` est le registre initial. Toutes ses tâches commencent à `todo`. Une IA exécutante les transforme en résultats vérifiables, avec le code, les assets, les rapports et les validations correspondants.

L’ordre est volontaire : accès et outils, génération des assets avec Claude Design, conversion en assets Roblox, construction du jeu, tests, puis préparation d’une publication soumise à autorisation. Un environnement manquant doit être signalé précisément. Un script qui vérifie le texte du cahier des charges ne remplace pas un test de jeu.

Le socle T04 peut démarrer après T00, en parallèle de la phase artistique. Cela permet de tester le contrôleur en graybox si un asset est retardé. La première salle livrée T07 attend néanmoins T03 et T06 ; aucun proxy ne vaut validation du lot artistique final.

À chaque tâche, l’IA doit lire les dépendances, annoncer les fichiers concernés, créer les tests appropriés, implémenter, exécuter les contrôles disponibles et consigner les résultats. Elle ne modifie pas silencieusement les exigences pour faire passer un test. Tout arbitrage matériel est enregistré dans `docs/decisions`.

## 2 Préflight et frontières d’autonomie

T00 produit `reports/preflight.json` avec : système, exécutables détectés, versions réellement présentes, accès à Roblox Studio, pont de pilotage disponible, droits d’import, accès à Claude Design, capacité Blender ou autre modeleur retenu, absence ou présence d’un dépôt et statut des permissions.

Les commandes `/design` et `/design-sync` ne sont utilisées que si leur intégration est effectivement disponible dans l’environnement Claude concerné. Ce dossier ne crée pas une API Claude Design imaginaire. Une exportation UI ou une planche de référence ne doit pas être déclarée modèle 3D importable. Le manifeste conserve les `assetId` Roblox à `null` tant que l’import autorisé n’a pas retourné un identifiant réel.

Si Claude Design, Studio ou le modeleur ne sont pas accessibles, la phase dépendante passe à `blocked` et le rapport indique l’accès requis. L’IA peut poursuivre les validations documentaires indépendantes, mais ne remplace pas discrètement la première phase demandée par des images sans provenance ou par une autre direction artistique.

Ne sont pas implicitement autorisés : acheter des services, dépenser des Robux, publier publiquement, créer des offres monétisées en production, changer les accès d’un compte ou contourner une restriction. Les identifiants et secrets ne sont jamais inscrits dans un prompt de design ou un rapport partagé.

## 3 Première phase de génération des assets

### T01 Conception dans Claude Design

**Entrées :** bible d’univers, catalogue des objets, formats des salles, écrans et manifeste attendu. **Sorties :** sources de design, planches des trois premières familles, vues des objets, états du HUD, boutique Coins, inventaire, sas et écran de renaissance. Pour Mallow, Loppy et Octo, fournir quatre vues orthographiques cohérentes et quatre poses de référence : repos, chute étirée, compression à l’impact et rebond.

Les planches doivent montrer l’échelle par rapport à l’avatar, les zones de réception et les codes de fonction. Les éléments d’interface sont séparés du décor. Chaque objet possède un identifiant stable et une fiche ; les noms du design doivent correspondre au manifeste.

**Validation :** palette cohérente, lisibilité mobile, provenance des fichiers, absence de contenu tiers non autorisé et liste exacte des exports. **Retour arrière :** reprendre la planche concernée ; ne pas compenser une silhouette illisible par des collisions invisibles.

### T02 Transmission du design

Réconcilier les exports avec `assets/manifest.json`. Conserver les fichiers sources, les éventuels SVG/PNG, les dimensions, les états UI et les indications de matériaux. Distinguer les références visuelles, les images utilisables directement et les objets 3D restant à construire. Tester la synchronisation disponible sans la supposer.

**Validation :** chaque asset du lot activé possède le fichier attendu pour son statut ou un manque explicite ; aucun lien mort n’est traité comme un export. Les entrées futures du manifeste maître peuvent rester `planned` sans fichier et ne bloquent pas à elles seules la livraison du premier lot. **Retour arrière :** réexporter seulement les éléments invalides et conserver les sources précédentes.

### T03 Construction des assets Roblox

Construire le lot minimal de Réception, Jouets et Bureau depuis les références validées, avec Blender ou des primitives Roblox selon la forme. Générer les meshes, UV, matériaux, pivots, colliders simples et points d’appui. Importer uniquement dans l’environnement autorisé.

Inclure Mallow avant les variantes de peluches : racine non déformante, neuf contrôles du ventre, six contrôles secondaires au maximum, poids de skin normalisés, poses d’impact et colliders serveur séparés. L’export et l’import doivent conserver le rig ; une image de l’ours ou un mesh rigide ne clôt cette livraison.

**Validation :** gabarits, orientations, visibilité des réceptions, budgets, collisions et noms. Les plafonds décoratifs ne participent pas aux tests d’ensevelissement. **Retour arrière :** utiliser un proxy de prototype clairement identifié pour diagnostiquer ; un proxy ne clôt pas une livraison artistique finale.

## 4 Construction du socle

| Tâche | Livrables et contrôle de sortie | Retour arrière |
|---|---|---|
| T04 Projet reproductible | Projet Rojo, structure Luau, versions verrouillées, compilateur de configuration et `tools/game_checks.py` | Revenir à une construction vide valide ; conserver les logs d’échec |
| T05 Contrats et états | Types, validation des intentions, machine d’expédition et tests purs | Corriger les contrats avant de développer leurs consommateurs |
| T06 Contrôleur | Déplacement, caméra, accès mobile et mesures des sauts | Réduire aux primitives ; désactiver les effets qui masquent les mesures |
| T07 Première salle | Réception avec parcours garanti et sortie protégée | Reprendre le graphe, pas augmenter artificiellement la portée du saut |
| T08 Vagues hybrides et peluches | Dépôts, alertes, consolidation, pool et `PlushDeformationController` alimenté par événements d’impact | Réduire la scène, vérifier pose de référence et reproduire la seed défaillante |
| T09 KO physique | Ensevelissement 10 Hz, grâce locale et chute mortelle | Désactiver l’envoi du KO pour examiner les sondes ; ne pas remplacer par un timer |
| T10 Continuité | Passage direct, sas, prochaine salle préchargée et nettoyage | Revenir à deux salles fixes pour isoler le défaut de transition |
| T11 Profil | Migrations, mutations sérialisées, journal des gains et achats Coins atomiques | Bloquer les nouvelles mutations si la sauvegarde est indisponible |

T06 doit être réalisée avant de fixer les distances des parcours. T09 est validée sur des scènes connues : vrai ensevelissement, sous une table ouverte, objet qui passe au-dessus, plateforme mobile et sortie dégagée. Une seule vidéo de KO réussi ne suffit pas.

T08 teste les déformations de Mallow sur cent chutes sans dérive, puis six peluches proches simultanées avec quarante objets dynamiques. Les animations utilisent les valeurs de `config/runtime.json` : neuf contrôles de ventre, six secondaires au maximum, compression verticale jusqu’à ×0,72 et étirement de chute jusqu’à ×1,12. Le rythme compression 0,09 seconde, rebond 0,18 seconde et amortissement principal 0,65 seconde doit respecter le plafond total configuré. L’écart dessus visible/collision est au plus 0,25 stud quand l’appui est actif. Ne pas tenter de mettre une échelle sur `Bone.Transform` : reconstruire la pose avec translations et rotations depuis un événement d’impact, sans changer les décisions serveur de KO ou récompense.

T10 doit franchir 100 transitions sans croissance permanente des objets, connexions ou tâches. La salle active, la suivante et le sas sont les seuls modules résidents de parcours ; la précédente n’est pas conservée en souvenir.

## 5 Première session et économie

### T12 Tutoriel et première acquisition

Intégrer la séquence de découverte, les trois gains uniques totalisant 65 Coins, le Radar à 50 Coins, son équipement et son utilisation. Ne pas imposer une fenêtre d’achat Robux. L’utilisateur lent conserve la possibilité d’apprendre sans être éliminé par un délai de tutoriel.

T12 livre une tranche verticale complète : `StarterRadar`, `TutorialShopController`, achat unitaire idempotent utilisant le dépôt de profil de T11, équipement et retour visuel. Elle n’attend pas le catalogue général de T13 ni les autres outils de T14 pour fonctionner. T13 reprend le même SKU dans le catalogue sans faire repayer l’objet ; T14 généralise son protocole aux autres outils.

**Recette :** scénario nominal vers une utilisation avant 30 secondes ; achat rejoué refusé ; reconnexion sans nouvelle prime ; solde final correct. Un playtest vérifie la compréhension en moins de 10 secondes, distinctement du temps nécessaire pour terminer. **Retour arrière :** réduire les écrans et les gestes ; ne pas simuler une récompense qui n’est pas créditée.

### T13 Catalogue et achats Coins

Compiler l’économie, afficher les conditions de maîtrise et développer propriété, améliorations et équipement. Une vente déjà possédée devient « Possédé ». Les contenus et prix proviennent de la configuration canonique.

**Recette :** solde insuffisant, double clic, achat simultané, changement de session et équipement incompatible. **Retour arrière :** arrêter la boutique et conserver les propriétés ; ne pas annuler des biens pour corriger l’affichage.

### T14 Outils

Généraliser le protocole du `StarterRadar` déjà livré en T12, puis construire les autres outils dans l’ordre du catalogue. Un seul actif et un seul passif sont équipables ; les compagnons purement visuels ne fournissent pas un troisième pouvoir. Les outils ne rendent pas la route principale dépendante d’un achat.

**Recette :** portée, charge, mauvais support, cible invalide, répétition des demandes et comportement sur mobile. **Retour arrière :** désactiver le SKU défectueux dans la version suivante, sans supprimer sa propriété chez les joueurs.

### T15 Permis et renaissance

Appliquer exactement les formules de `config/economy.json`. Les permis sont gagnés par le jeu, non achetables. La renaissance est proposée dans le sas, ne se déclenche jamais automatiquement et préserve les excédents prévus. Elle conserve Coins, outils et achats.

La confirmation envoie `quantity`, `expectedRevision`, `previewToken` et `requestId`. Le serveur émet l’aperçu, contrôle sa correspondance au joueur et à la révision, puis recalcule les coûts cumulés avant mutation. Une quantité modifiée ou une révision périmée impose un nouvel aperçu ; le client n’est jamais autorité sur le coût.

**Recette :** seuil exact, seuil insuffisant, double validation, conversion de plusieurs rangs si prévue, KO avant demande et refus de renaître pour continuer cinq heures. **Retour arrière :** suspendre les conversions ; conserver le solde de permis et le dernier profil engagé.

## 6 Contenu extensible et persistance

T16 livre trois familles complètes et leurs variantes certifiées. T17 ajoute les trois suivantes avec leurs formats et sorties. Les règles de compatibilité priment sur la combinatoire brute : toutes les fenêtres ne conviennent pas à tous les gabarits. Chaque variante garde une route principale sans outil, un dernier appui protégé et une sortie identifiable.

Le validateur conserve les seeds qui échouent comme cas de régression. L’IA ne résout pas un taux d’échec en supprimant les seeds du rapport. Elle corrige le générateur ou marque une combinaison indisponible avant de la présenter au joueur.

T18 implémente sauvegarde et reprise : checkpoint au sas, même seed à la reprise, version de configuration verrouillée et masque des gains déjà reçus. La déconnexion en salle ne doit pas permettre de répéter une prime. La nouvelle session ne prend pas simultanément possession d’un profil déjà verrouillé ailleurs.

**Retour arrière :** garder un checkpoint précédent cohérent avec les gains engagés et inscrire l’échec. Ne jamais annoncer « Sauvegardé » si l’écriture a échoué. Prévoir une migration ou une extraction conservatrice lorsqu’une ancienne version de salle n’est plus disponible.

## 7 Boutique Robux et expérience complète

T19 termine les écrans, paramètres de confort et parcours d’achat Coins. Le joueur peut continuer tout droit dans le sas sans ouvrir un menu. La boutique indique contenu, prix, permanence et conditions. Aucun bouton payant n’est affiché comme seule issue après KO.

T20 implémente les adaptateurs d’achat Roblox, uniquement avec identifiants réels autorisés pour les essais. Les prix affichés doivent être cohérents avec le prix effectif applicable. Les reçus sont délivrés une fois après persistance durable, et les achats permanents restent possédés après renaissance.

**Retour arrière :** désactiver les produits dans la configuration de test et garder leur journal de reçu. Ne pas supprimer un reçu pour « retenter » une attribution. Des produits avec `productId: null` bloquent les transactions réelles ; un mock valide la logique, pas le paiement Roblox.

T21 réunit les tests de parcours complet, accessibilité, télémétrie et mobile. Les contrôles doivent montrer ce que font réellement les joueurs : compréhension, première action, première acquisition, KO, sortie, reprise et renaissance. Les mesures ne servent pas à inventer un taux de rétention avant lancement.

## 8 Validation longue durée et clôture

T22 réalise deux familles de tests distinctes. La première accélère la logique sur 18 000 secondes simulées et sur 80, 200 puis 1 000 salles. La seconde fait fonctionner réellement un client et un serveur Roblox pendant cinq heures avec un pilote de test. Elle relève régulièrement mémoire, nombre d’instances, connexions, frame time, erreurs et progression.

Une simulation Python de gains ne prouve ni le réseau, ni la caméra, ni le maintien des performances. Un test de cinq minutes extrapolé ne devient pas un test de cinq heures. Si l’environnement ne permet pas le test réel, cette partie reste `blocked` et la publication ne franchit pas la porte de qualité correspondante.

T23 prépare le dossier de livraison : fichier de jeu construit, configurations, sources, manifeste d’assets, rapports, problèmes connus et procédure de retour arrière. La publication effective demande une autorisation explicite. La coopération, les classements à kit standardisé et les offres supplémentaires restent hors du MVP tant que leurs règles et leur périmètre ne sont pas approuvés.

## 9 Protocole des commandes et états

Les commandes `python tools/game_checks.py ...` inscrites au backlog sont **à créer dans T04**. Les options prévues sont `config`, `build`, `unit --suite <nom>`, `studio --suite <nom>`, `soak --simulated-seconds 18000` et `soak --real-hours 5`. Ce contrat de commande n’affirme pas qu’un pont Studio est déjà installé. Le programme vérifie la capacité requise et produit un rapport JSON avec état, date, version, contrôles exécutés, échecs et contrôles non exécutés.

Les états admis du registre sont `todo`, `in_progress`, `blocked` et `done`. `done` exige les fichiers attendus et toutes les preuves de validation de la tâche. Une commande manquante, une permission refusée ou un test non exécuté interdisent de marquer la tâche terminée.

L’IA effectue un commit local cohérent après chaque tâche validée si un dépôt autorisé est présent. Elle ne pousse ni ne publie automatiquement. Pour revenir en arrière, elle restaure uniquement ses propres modifications identifiées par un commit ou une copie de sauvegarde, et préserve les changements de l’utilisateur. Aucun reset destructif global n’est permis.

