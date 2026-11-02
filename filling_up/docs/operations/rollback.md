# Procédure de retour arrière

1. **Code** : chaque tâche validée correspond à un commit. Revenir avec `git revert <commit>` (jamais de reset destructif
   global). Reconstruire avec `python tools/game_checks.py build`.
2. **Configuration** : modifier les JSON de `config/`, puis lancer `python tools/compile_config.py`. Le `configVersion`
   change, et les checkpoints de l'ancienne version passent en extraction conservatrice (biens gardés).
3. **Boutique fautive** : retirer le SKU de `Economy.IMPLEMENTED_TOOLS` (ou mettre son `product_id` à null). La
   propriété des joueurs n'est jamais supprimée.
4. **Produits Robux** : `robux_shop_enabled = false` coupe tout prompt. Le journal `purchaseLedger.receipts` est
   conservé : ne pas supprimer un reçu pour « retenter ».
5. **Sauvegarde indisponible** : le dépôt refuse les nouvelles mutations (`save_failed`) et garde la dernière révision
   engagée.
6. **Salle défaillante** : noter la seed (rapport de certification), désactiver la combinaison via
   `RoomPlan.setCertified` dans une nouvelle version, et ajouter la seed aux régressions.
7. **Publication** : rien n'est publié par ce dépôt. Toute publication ou dépublication passe par une personne
   autorisée dans le Creator Dashboard.
