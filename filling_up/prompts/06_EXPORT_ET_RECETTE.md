# Prompt de transfert et de contrôle des assets

Exporte les sources disponibles dans un ZIP et produis un inventaire exact. Pour chaque fichier, indiquer son asset logique, sa nature (référence, source modifiable, modèle, texture, icône ou prototype), son format, ses dimensions et son statut. Ne compte pas deux fois une planche et les objets qu'elle représente comme modèles terminés.

Compare chaque élément à assets/manifest.json. Les assets non produits restent planned. Les images de référence peuvent être designed. Un modèle importé mais sans test de collision reste imported, jamais validated. Vérifie les fichiers réellement ouverts, pas seulement les noms annoncés.

Écris reports/design_handoff.json et reports/design_review.md avec les écarts et corrections. Ne publie rien et ne partage pas un lien publiquement sans instruction. Transmets le projet à l'agent de développement disponible, ou fournis les sources locales si le handoff direct n'est pas accessible.

Critère d'achèvement : le prochain agent peut reconstruire le premier lot sans demander la couleur d'une salle, la taille d'un objet, le type de sortie ou l'emplacement du dessus jouable. Les arbitrages de rig et d'import sont documentés, et les limites restantes sont explicites.

