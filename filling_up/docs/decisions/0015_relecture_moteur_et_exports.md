# 0015 — Relecture moteur, registre des réclamations, exports `.rbxm`, rendus de revue

* **Registre `roomClaims`** (extension du profil, en plus de la décision 0005) : `{ runId, depth, mask, paid }` pour la
  salle en cours. `GrantProgress` et `GrantToken` combinent le masque fourni par l'appelant avec ce registre :
  une requête construite sur un masque périmé ne paie jamais deux fois.
* **`CompleteRoom`** : récompense de sortie, maîtrise, bonus de découverte et checkpoint suivant tiennent en une seule
  écriture durable. Le joueur est téléporté au sas avant cette écriture. Tant qu'elle n'a pas réussi, il ne peut pas
  continuer, et « Sauvegardé » ne s'affiche pas.
* **`UpdateCharges`** : charges d'outils de la salle courante écrites dans le checkpoint après chaque usage. Un
  checkpoint est aussi écrit au démarrage d'une expédition (salle 1).
* **Cases de monde par session**, espacées de 4 000 studs. Le MVP reste solo : régler Max Players à 1 dans les
  paramètres du jeu à la publication.
* **Mode « moteur léger » de Lune** (`Loader.enableEngineLite`) : instances Roblox réelles de `@lune/roblox`, sans
  physique ni signaux. `tools/export_props.luau` exécute le vrai `PropFactory` sur les 48 objets et exporte
  `assets/import/models/<id>.rbxm`. Seuls les 4 objets issus d'un générateur voient leur export compté au manifeste ;
  les autres sont des exports de proxy, signalés `proxy_export_path`.
* **Rendus de revue** (`tools/dump_rooms.luau` + `tools/render_rooms.py`, Blender Cycles CPU) : 16 salles validées,
  dans `reports/room_previews/`. Ils ont révélé que le carton du tutoriel empiétait sur la zone d'apparition : le
  validateur refuse désormais tout solide dans une zone d'apparition (`spawn_obstructed`).
* **`luau-analyze` non disponible** : le compiler depuis les sources officielles (fichiers de `raw.githubusercontent`
  listés par `Sources.cmake`) a été **refusé par la politique de permissions** de la session (exécution de code
  externe). Rien n'a été contourné. Cela demande une autorisation de l'utilisateur.
