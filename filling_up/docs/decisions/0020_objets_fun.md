# 0020 — Ce qui tombe doit être fun (demande de l'utilisateur, 2 novembre 2026)

**Demande** :
* « Mets des objets plus fun, comme les canards gonflables ; les bureaux, cartons et classeurs, ce n'est pas fun. »
* Précision : « les objets type bureau peuvent être dans la salle, mais pas dans ceux qui tombent. »

Une instruction explicite de l'utilisateur prime sur la spécification (AGENTS.md).

**Décisions** :
1. **Nouvelle famille « Piscine Gonflable » (`pool`)**, en MVP et en V1, à partir de la salle 3.
   * **8 objets gonflables** :
     * canard à chevaucher (stable) ;
     * flamant rose, ballon de plage écrasé et bouée donut avec filet trampoline (rebond) ;
     * licorne et glacière qui sourit (stables) ;
     * crocodile qui dérive (mobile) ;
     * matelas qui se dégonfle (éphémère).
   * **Machine** : La Pompe à Bouées.
   * **Habillage** : transats, parasols, palmiers, chaise de maître-nageur, bouées au mur.
   * **Salle 8 MVP** : elle devient Piscine S / fenêtre, au lieu de Jouets S / fenêtre.
2. **Ce qui tombe est fun** (`fun_intruders` dans config/rooms.json) :
   * Réception, Bureau, Garage, Giant Bin (`fun_only_families`) : les vagues ne lâchent que des objets fun, c'est-à-dire
     les gonflables de la piscine, les peluches de toutes tailles, le canard plat et le tambour. Les objets de la
     famille (bureaux, cartons, classeurs, outils) restent dans la salle comme appuis du parcours et comme mobilier.
   * Cuisine : 30 % des objets de vague sont remplacés par un objet fun. Le reste, ce sont des aliments (gelée,
     crêpes, toasts).
   * Jouets et Piscine gardent leurs propres objets, déjà fun.
   * Le remplacement utilise un flux aléatoire séparé : la séquence de base et le nombre de tirages ne changent pas.
     Les règles de taille de la décision 0019 s'appliquent : grandes peluches seulement en L/V/XL/XV, baleine jamais
     lâchée.
3. **Tutoriel** : le premier objet qui tombe est le **canard gonflable**, au lieu du carton
   (`rooms.json tutorial.falling_prop_id`). Son collider passe à 9 × 8 × 4 pour tenir dans les 8 studs entre le sas et
   le rebord, comme le carton. Les clés d'économie (`carton_settled`) ne changent pas : seul l'objet change.

**Vérifié hors Studio** (suite `fun`, plus les suites touchées) :
* les familles sérieuses ne lâchent que des objets fun et gardent leurs objets comme appuis ;
* la part mixte de la Cuisine est d'environ 30 % ;
* Jouets et Piscine ne sont pas modifiées ;
* chaque format et chaque sortie de la Piscine génère des salles valides ;
* le flux intrus ne déplace pas les objets non remplacés.

**Risques NON vérifiés** :
* La lisibilité de la salle. Avec des gonflables qui tombent dans un bureau, l'identité de la famille repose
  surtout sur l'architecture, le mobilier et les appuis. À juger en playtest.
* Les silhouettes. Beaucoup d'objets fun tombent à plat sur le dos : vérifier en Studio qu'ils se posent dans une
  orientation jouable.
* Les ID de souvenirs (`compagnon_canard_gonflable`…) ne sont pas encore définis dans economy.json : ce sont des
  cosmétiques à concevoir.
