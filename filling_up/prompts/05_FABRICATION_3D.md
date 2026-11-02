# Prompt de fabrication pour Claude Code et Blender

Utilise les exports Claude Design validés et assets/manifest.json. Fabrique le lot initial : carton, caisse mousse, palette, valise, ourson Mallow, Radar, machine de Réception et ouvertures porte/fenêtre/toit. Les quatre objets simples peuvent être construits en primitives Roblox paramétriques. Mallow exige un mesh skinné de qualité, pas une pile de cubes présentée comme produit final.

Vérifie la disponibilité de Blender et de son automatisation autorisée. Crée des scripts Python de génération reproductibles, puis des sources .blend et des exports .glb ou .fbx compatibles avec l'importeur disponible. Mesure les objets après import dans Roblox : aucune convention d'unités implicite ne doit changer le gabarit.

Pour Mallow, prépare neuf contrôles de volume et jusqu'à six contrôles secondaires. Normalise le skinning ; sauvegarde une pose de référence. Les animations de compression déplacent et tournent les bones. Ne crée pas de Bone.Transform.Scale. La collision est séparée du visuel et reste simple. Les grandes compressions ont lieu avant que l'appui garanti soit activé.

Respecte les budgets du dossier. Ajoute pivot, sockets, dessus utile, colliders, LOD et matériau. Conserve les sources originales. Ne renseigne un ID Roblox qu'après un import réel et autorisé. Si l'import est bloqué, livre les sources et marque le statut bloqué, sans inventer la réussite.

Teste trois hauteurs de chute, trois orientations, cent réutilisations du pool et une réception de joueur. Les pieds ne doivent pas flotter de plus de 0,25 stud au-dessus du dessus visible. La déformation doit être liée à l'impact, pas une boucle de gonflement constante.

