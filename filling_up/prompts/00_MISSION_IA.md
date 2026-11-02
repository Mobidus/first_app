# Mission de développement autonome

Développe le jeu Roblox FILLING UP conformément à ce dossier. Commence par lire AGENTS.md, les sept documents de docs/, les JSON de config/ et tasks/backlog.json. Ne produis pas un nouveau concept : réalise les décisions déjà spécifiées.

Le jeu enchaîne les salles tant que le joueur survit. Des vagues d'objets remplissent chaque salle et un véritable ensevelissement peut provoquer le KO. Aucun chronomètre ni pourcentage global de remplissage ne met automatiquement fin à la salle. Les sorties, tailles et parcours varient ; une expédition peut continuer cinq heures et davantage. Respecte les limites physiques mesurées et les budgets de mémoire.

Ta première phase de production est Claude Design : exécute les prompts 01 à 06, vérifie les exports et fabrique ensuite les assets Roblox. Produis notamment des peluches identifiables, avec coutures, formes originales et déformations visuelles lors des chutes. Ne présente jamais une image de référence comme un modèle 3D importé.

Exécute les tâches dans l'ordre des dépendances. Écris les tests, implémente, vérifie, conserve les preuves puis passe à la suite. Les actions locales réversibles dans le répertoire autorisé peuvent avancer sans demander des choix déjà tranchés. Si un accès, une permission, une dépense ou une publication manque, arrête uniquement la branche concernée et explique le besoin ; ne contourne rien.

Avant toute commande, vérifie que l'outil existe réellement. Les commandes game_checks du backlog sont à créer dans T04 ; elles ne constituent pas un test existant du jeu. La simulation Python fournie valide l'économie proposée, pas la physique Roblox.

N'efface pas de changement utilisateur. Ne réduis pas un test pour masquer un échec. Tous les prix/statistiques viennent des configurations. Tous les achats Robux réels restent désactivés tant que leurs identifiants et autorisations ne sont pas disponibles. Ne publie pas le jeu et ne dépense pas de Robux sans autorisation explicite.

Livraison attendue : projet Roblox constructible, assets sources et importés, tests, rapports réels, états de tâches à jour et limites restantes. Si des essais Studio ou cinq heures d'endurance n'ont pas été réalisés, indique NOT_RUN, jamais PASS.

