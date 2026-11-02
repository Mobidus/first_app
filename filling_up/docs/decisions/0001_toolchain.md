# 0001 — Chaîne d'outils (T00 / T04)

**Contexte.** Conteneur Linux cloud (Ubuntu 24.04, Python 3.13, Rust 1.97, Node 22). Pas de Roblox Studio
(Windows/macOS uniquement), pas de compte Roblox ni clé Open Cloud. L'API GitHub est bloquée par le proxy ; les
téléchargements de releases passent, mais l'exécution de binaires précompilés téléchargés a été **refusée** par la
politique de permissions de la session.

**Décision.** Outils compilés depuis les sources publiées sur crates.io (`cargo install --locked`) et paquets PyPI :

| Outil | Version | Méthode | Usage |
|---|---|---|---|
| Rojo | 7.5.1 | `cargo install --locked rojo --version 7.5.1` | construction du `.rbxlx` |
| Lune | 0.10.1 | `cargo install --locked lune --version 0.10.1` | exécution Luau hors moteur (tests de logique, soak, vérif du build) |
| StyLua | 2.1.0 | `cargo install --locked stylua --version 2.1.0 --features luau` | formatage |
| Selene | 0.28.0 | `cargo install --locked selene --version 0.28.0 --no-default-features --features roblox` | lint (std `roblox_min.yml`, le dump d'API Roblox n'est pas téléchargeable) |
| Blender (bpy) | 5.2.3 LTS | `pip install bpy==5.2.3` (venv projet) | modèles, rigs, exports GLB/FBX |
| lupa | 2.8 | pip | non utilisé (pas de Luau) — conservé au lock pour traçabilité |

Versions réellement détectées : `reports/preflight.json`. Verrou : `toolchain.lock.json`. Script : `tools/bootstrap_toolchain.sh`.

**Non disponible.** `luau-analyze` (vérification de types `--!strict`) : pas de crate ni de binaire exécutable autorisé →
NOT_RUN, signalé par `game_checks.py build`. Roblox Studio : toutes les suites `studio` → BLOCKED.

**Conséquence.** Les tests passants prouvent la logique pure et la constructibilité, jamais la physique, le réseau, les
achats ou le mobile.
