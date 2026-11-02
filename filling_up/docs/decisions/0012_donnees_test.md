# 0012 — Données de test

Par défaut, le DataStore se nomme `FillingUp_Profiles_TEST_v3`, ce qui sépare le test de la production (S11).
Le nom de production ne sera fixé qu'à la publication autorisée (T23). En Studio sans accès aux API, le serveur bascule
sur un stockage mémoire et le HUD l'annonce : « progression non persistante ». Aucun « Sauvegardé » ne s'affiche alors
comme une sauvegarde durable de production.
