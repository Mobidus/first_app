# 0010 — Générateur de salles

* Le graphe est construit **à rebours** depuis le rebord de sortie protégé (8 × 8, volume dégagé de 8 × 8 × 10 au-dessus)
  jusqu'au sol. Chaque appui est soit une colonne (socle structurel + 1 à 2 objets stables), soit un **palier suspendu**
  (dalle d'1 stud + objet) pour les salles hautes. Les paliers suspendus correspondent aux « paliers de récupération »
  des formats V.
* Occupation testée en 3D (solides + espace de tête de 6,5 studs). Les arcs de saut sont testés **pendant** la pose,
  puis revalidés par `RouteValidator`.
* Hauteur des sorties : porte et conduit à 0,35 h, fenêtre à 0,55 h (bornées à `h − 10`), toit à `h − 6`.
  Un auvent de 20 × 20 au-dessus de la trappe de toit protège les arcs et la caméra.
* Les sorties basses (hayon, trappe) exigent un levier haut (0,45 h) : arête `gate` levier → sortie.
* Les bouches de vagues (8 × 8) évitent le volume de sortie, les appuis protégés et le sas d'apparition.
* Échec : 12 tentatives, puis repli certifié (lui aussi validé). Une salle non validée n'est jamais renvoyée.
* Certification : 3 240 salles MVP (27 combinaisons × 120 seeds), toutes construites sans repli. 17 280 salles V1
  (144 combinaisons), 0 impossible, 159 replis (0,9 %) listés dans `reports/room_certification_full.json`.
