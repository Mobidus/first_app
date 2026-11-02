# 0005 — Précisions du contrat PlayerProfile

* `roomMastery = { totalCompleted, families = {familyId: count}, firstRebirthQualified }` : le nombre total de salles
  terminées (déblocages du catalogue) et la qualification « trois familles » de la première renaissance, qui reste
  acquise.
* Extension `purchaseLedger = { receipts, receiptOrder, entitlements }` : journal durable des reçus Robux (idempotence
  par PurchaseId, borné à 500 entrées) et droits permanents. Nécessaire à l'attribution unique ; absent du contrat
  initial.
* Le masque de récompenses de la salle en cours vit dans `checkpoint` (même document que les Coins) : une panne
  fait revenir ensemble Coins et masque, sans duplication possible.
* Borne technique des entiers : `1e12` (< 2^53). Valeur non économique, documentée ici plutôt que dans la config.
* Toutes les mutations passent par `ProfileMutations.apply` (copie profonde, recalcul depuis la config, validation),
  puis le dépôt les écrit avant de les engager en mémoire. Une écriture échouée renvoie `save_failed`.
