# T01/T02 — commandes et preuves

1. Création du canvas Claude Design : `Artifact publish type_url=https://claude.ai/artifact/QKN21svewxgyPb6SYRqWnd title="FILLING UP — Planches Claude Design"`. Résultat : https://claude.ai/artifact/Vb6XnUB54ikWQCQsQ9Twb3.
2. Téléversement des 12 SVG d'icônes dans le stockage d'assets du canvas. Les identifiants obtenus sont listés dans `assets/source/design/blob_map.json`.
3. Publication de `canvas.json`, puis des 20 planches une par une. Version finale : 24, id `1793612803-9345`.
4. Rastérisation : `node raster_icons.js assets/source/design/icons assets/import/ui/icons reports/T01/icons_legibility_64_96.png`. Le script vit dans le scratchpad de session et utilise Playwright/Chromium préinstallé. Sortie : `rasterized 12`, puis contrôle des PNG (512 × 512, color type 6 RGBA).
5. Captures de contrôle : `node capture_boards.js assets/source/design/canvas/project reports/T01/captures assets/source/design/blob_map.json`. Sortie : 20 captures.
6. Transmission : `python3 -I handoff.py <projet>`. Sortie : `files 49 updates 43`. Le script ouvre chaque fichier et échoue sur tout fichier manquant ou illisible.
7. Contrastes WCAG calculés : résultats dans `reports/design_review.md`.

PASS : existence et format des fichiers, prix et dimensions recopiés depuis les configs, contrastes.
NOT_RUN : test d'identification humain, revue artistique humaine, mobile réel.
