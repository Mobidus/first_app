# 0011 — Dimensionnement du pool d'objets

La simulation d'endurance a révélé un défaut : avec 24 objets libres par type, recycler une salle détruisait des
objets que la salle suivante recréait (94 416 créations sur 1 000 salles). Le pool garde désormais jusqu'à
`runtime.streaming.max_fill_colliders_active_room` (160) objets libres au total. Après correction, les créations
plafonnent à moins de 200 et ne croissent plus entre 200 et 1 000 salles (`reports/soak_simulated.json`).
