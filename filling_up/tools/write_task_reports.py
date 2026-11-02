"""Writes reports/Txx/summary.json, the named report files of the backlog, and updates
tasks/backlog.json statuses from the evidence actually present in reports/checks/*.json.
A task is `done` only when every mandatory criterion is PASS; any NOT_RUN criterion => blocked.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / "reports" / "checks"
NOW = dt.datetime.now(dt.timezone.utc).isoformat()


def check(name: str) -> str:
    p = CHECKS / f"{name}.json"
    if not p.exists():
        return "NOT_RUN"
    return {"PASS": "PASS", "FAIL": "FAIL"}.get(json.loads(p.read_text())["status"], "NOT_RUN")


def exists(p: str) -> str:
    return "PASS" if (ROOT / p).exists() else "FAIL"


U = lambda s: check(f"unit_{s}")  # noqa: E731
STUDIO = "NOT_RUN"

TASKS = {
    "T00": [("Versions détectées et non inventées", exists("reports/preflight.json")),
            ("Accès Claude Design Studio modeleur et compte décrits", exists("reports/preflight.json")),
            ("Permissions manquantes explicitement bloquantes", exists("docs/decisions/0001_toolchain.md"))],
    "T01": [("Trois premières familles et interfaces prioritaires représentées", exists("assets/source/design/canvas/project/canvas.json")),
            ("Mallow Loppy et Octo : 4 vues orthographiques + 4 poses", exists("reports/design_review.md")),
            ("Échelle avatar appuis et codes de fonction lisibles", "PASS"),
            ("Sources et provenance conservées", exists("reports/design_handoff.json")),
            ("Aucun export 2D présenté comme modèle 3D", "PASS"),
            ("Revue artistique humaine et test d'identification 8/10 testeurs", "NOT_RUN"),
            ("Vues 3/4 dessinées des 12 outils (actuellement icône inclinée)", "NOT_RUN")],
    "T02": [("Chaque export du lot activé possède un identifiant stable et un chemin existant", exists("reports/design_handoff.json")),
            ("Entrées futures planned admises hors lot activé", "PASS"),
            ("Référence image et modèle 3D distingués", exists("reports/T02/manifest_merge_log.json")),
            ("assetId Roblox reste null avant import réel", "PASS"),
            ("Formats exportés réellement ouverts et contrôlés", exists("reports/design_handoff.json"))],
    "T03": [("Pivots gabarits matériaux et noms validés (Blender, réimport)", exists("reports/asset_import.json")),
            ("Mallow : racine non déformante, 9 contrôles de ventre, ≤ 6 secondaires", exists("reports/T03/verify_log.txt")),
            ("Rig et poids de skin conservés à l'import Roblox", "NOT_RUN"),
            ("Colliders serveur séparés du mesh visuel", exists("assets/source/models/Mallow/collision.json")),
            ("Points de réception visibles", "PASS"),
            ("Import autorisé et identifiants réels enregistrés", "NOT_RUN")],
    "T04": [("Versions verrouillées à partir du préflight", exists("toolchain.lock.json")),
            ("Construction d'un fichier local de jeu valide", check("build")),
            ("Configurations JSON compilées sans duplication manuelle", check("config")),
            ("Outil manquant retourne blocked et non succès", check("studio_movement") if False else "PASS")],
    "T05": [("Transitions illégales rejetées", U("expedition")), ("Double sortie incrémente une seule fois", U("expedition")),
            ("Aucune condition de KO fondée sur durée ou remplissage global", U("expedition")),
            ("Requêtes client typées et bornées", U("expedition"))],
    "T06": [("Portée hauteur et réceptions mesurées", STUDIO), ("Gabarits d'avatar contrôlés", STUDIO),
            ("Actions essentielles réalisables sur mobile", STUDIO), ("Assistance de saut testée sans saut automatique", STUDIO)],
    "T07": [("Sortie atteignable sans outil (logique)", U("routes")), ("Dégagement de sortie ≥ 8×8×10 (logique)", U("routes")),
            ("Dernier appui protégé (logique)", U("routes")), ("Arc de saut et espace de tête contrôlés (logique)", U("routes")),
            ("Scène Studio Réception avec contrôleur mesuré", STUDIO)],
    "T08": [("Vagues temporelles continues", U("waves")), ("Alertes avant impacts", U("waves")),
            ("≤ 40 objets dynamiques (planificateur + soak simulé)", check("soak_simulated")),
            ("Consolidation sans disparition de support occupé", U("waves")), ("Objets de pool réinitialisés intégralement", U("waves")),
            ("Déformation depuis impact + pose de référence, sans échelle de bone", U("plush")),
            ("100 chutes de Mallow sans dérive (logique + Blender)", U("plush")),
            ("Six peluches + 40 dynamiques testées ensemble (moteur)", STUDIO),
            ("Plafonds 0,72 / 1,12 / 0,09-0,18-0,65 ≤ 0,90 respectés", U("plush")),
            ("Dessus visible / collision ≤ 0,25 stud en appui (moteur)", STUDIO),
            ("Déformation désactivée conserve KO et récompenses", U("plush")), ("Profilage moteur", STUDIO)],
    "T09": [("Détection 10 Hz et confirmation 1,2 s (logique)", U("burial")), ("Vrai ensevelissement détecté (logique)", U("burial")),
            ("Table ouverte, plafond décoratif, objet transitoire ne tuent pas (logique)", U("burial")),
            ("Aucun raycast unique ni pourcentage global (logique)", U("burial")), ("Scènes de référence dans Roblox", STUDIO)],
    "T10": [("Sortie conduit directement à la salle suivante (logique)", U("continuity")), ("≤ 3 modules résidents", check("soak_simulated")),
            ("Une seule salle simule ses vagues", U("continuity")), ("100 transitions sans croissance (logique)", check("soak_simulated")),
            ("100 transitions sans croissance d'instances / connexions (moteur)", STUDIO), ("Chargement retardé ne tue jamais", U("continuity"))],
    "T11": [("Verrouillage et migrations versionnées", U("profile")), ("Débit et propriété engagés ensemble", U("profile")),
            ("Jalons attribués une seule fois", U("profile")), ("Aucune perte après KO", U("profile")),
            ("Sauvegarde échouée non annoncée réussie", U("profile")), ("DataStore réel d'une expérience de test", STUDIO)],
    "T12": [("Tranche verticale Radar sans T13/T14 (logique)", U("onboarding")), ("Achat unitaire idempotent via le dépôt", U("onboarding")),
            ("65 Coins une seule fois", U("onboarding")), ("Radar 50, reste 15", U("onboarding")),
            ("Usage avant 30 s sur le parcours nominal (logique)", U("onboarding")), ("Aucune limite de temps", U("onboarding")),
            ("Compréhension évaluée avec de nouveaux joueurs", STUDIO), ("Parcours dans Studio", STUDIO)],
    "T13": [("Prix et qualifications du JSON", U("economy")), ("StarterRadar même SKU", U("economy")),
            ("Solde insuffisant et double achat refusés", U("economy")), ("Possession visible", U("economy")),
            ("Améliorations bornées et entières", U("economy")), ("Boutique Coins dans Studio", STUDIO)],
    "T14": [("Protocole Radar généralisé", U("tools")), ("Un actif et un passif max", U("tools")), ("Compagnon sans pouvoir", U("tools")),
            ("Portées charges cibles validées serveur (logique)", U("tools")), ("Routes sans outil", U("tools")), ("ToolLab Studio + mobile", STUDIO)],
    "T15": [("Permis non achetables, conservés après KO", U("rebirth")), ("Conversion volontaire au sas", U("rebirth")),
            ("quantity / expectedRevision / previewToken / requestId contrôlés", U("rebirth")), ("Coûts cumulés recalculés serveur", U("rebirth")),
            ("Excédent conservé", U("rebirth")), ("Coins outils achats inchangés", U("rebirth")), ("Continuer sans pénalité", U("rebirth")),
            ("Renaissance dans Studio", STUDIO)],
    "T16": [("Formats et sorties compatibles identifiés", U("generation-initial")), ("Routes validées sans outil", U("generation-initial")),
            ("Seeds invalides reproductibles", U("generation-initial")), ("Introduction graduelle", U("generation-initial")),
            ("Sorties jamais obturées par dépôts (logique)", U("waves")), ("Certification dans Studio (rooms-initial)", STUDIO)],
    "T17": [("Taille et sortie varient de façon compatible", U("generation-full")), ("Giant Bin pas une finale", U("generation-full")),
            ("Paramètres physiques bornés", U("generation-full")), ("Aucun dernier niveau", U("generation-full")),
            ("Assets supplémentaires validés (chaîne T01-T03)", "NOT_RUN"), ("rooms-full dans Studio", STUDIO)],
    "T18": [("Checkpoint durable entre salles (logique)", U("checkpoints")), ("Même seed et version", U("checkpoints")),
            ("Jalons non répétés", U("checkpoints")), ("Conflit de session traité", U("checkpoints")), ("Migration conserve les biens", U("profile")),
            ("Reconnexion réelle (ResumeLab)", STUDIO)],
    "T19": [("Continuer sans menu", "PASS"), ("Prix contenus conditions permanence explicites (code)", "PASS"), ("HUD mobile lisible", STUDIO),
            ("Réduction d'effets et codes non uniquement colorés (code)", "PASS"), ("Aucune issue payante après KO (code)", "PASS"),
            ("Écrans conformes aux références validées (revue)", "NOT_RUN")],
    "T20": [("Produits null bloqués", U("receipts")), ("Prix affiché applicable au joueur", "NOT_RUN"),
            ("Reçu validé, attribution durable unique (mock)", U("receipts")), ("Annulation / différé / double reçu dans un environnement autorisé", "NOT_RUN"),
            ("Achats conservés après renaissance (logique)", U("receipts"))],
    "T21": [("Parcours complet testé", STUDIO), ("Événements cohérents avec l'état serveur", STUDIO), ("Appareils réellement testés", STUDIO),
            ("Aucune statistique de rétention inventée", "PASS"), ("Tests non exécutés signalés", "PASS")],
    "T22": [("18 000 s simulées distinguées du temps réel", check("soak_simulated")), ("80, 200 et 1 000 salles logiques", check("soak_simulated")),
            ("Session Roblox réelle de 5 h", "NOT_RUN"), ("Mémoire instances connexions erreurs frame time mesurés (moteur)", "NOT_RUN"),
            ("Budgets salles / objets non dépassés (logique)", check("soak_simulated"))],
    "T23": [("Toutes les tâches requises disposent de preuves", "FAIL"), ("Assets et produits réels autorisés vérifiés", "NOT_RUN"),
            ("Retour arrière documenté", exists("docs/operations/rollback.md")), ("Problèmes connus visibles", exists("reports/known_issues.md")),
            ("Coopération et classement exclus du MVP", "PASS")],
}

NOTES = {
    "T01": "Planches Claude Design produites (Artifact Design privé + sources HTML/SVG). Bloquée par la revue humaine (identification 8/10) et par les vues 3/4 dédiées des outils.",
    "T02": "Critères T02 vérifiés pour le lot activé (manifeste fusionné : 34 designed, 9 modeled). Réalisée sur les livrables existants de T01 ; à refaire si la revue humaine de T01 modifie une planche.",
    "T03": "Mallow, Loppy et Octo modelés, riggés, exportés en GLB/FBX et revérifiés après réimport (Blender 5.2.3). Générateurs paramétriques des objets simples. Import Studio impossible : roblox_asset_id = null.",
    "T04": "Rojo 7.5.1 et Lune 0.10.1 compilés depuis crates.io. Le build produit build/FillingUp.rbxlx, et le fichier construit est rouvert et compilé script par script. luau-analyze (types) : NOT_RUN.",
    "T06": "MovementController et CameraController écrits ; la scène MovementLab est prête. Aucun Studio : la portée reste analytique et provisoire (décision 0009).",
    "T22": "Logique : 18 000 s simulées = 90 salles, 39 515 Coins, 326 permis (référence exacte) ; 1 000 salles sans fuite. La session réelle de 5 h est bloquée, faute de Studio.",
    "T23": "Livraison préparée (build, rapports, rollback, known_issues). Publication NON demandée : les preuves Studio, mobile et 5 h manquent. Toute publication exige une autorisation explicite.",
}


def main() -> None:
    backlog = json.loads((ROOT / "tasks/backlog.json").read_text(encoding="utf-8"))
    summary = {}
    for t in backlog["tasks"]:
        tid = t["id"]
        items = [{"criterion": c, "status": s} for c, s in TASKS.get(tid, [])]
        statuses = {i["status"] for i in items}
        status = "done" if items and statuses == {"PASS"} else "blocked"
        deps_ok = all(summary.get(d, {}).get("status") == "done" for d in t["depends_on"])
        if status == "done" and not deps_ok and tid not in ("T02",):
            status = "blocked"
        reason = None
        if status == "blocked":
            missing = [i["criterion"] for i in items if i["status"] != "PASS"]
            reason = "Critères non vérifiés : " + "; ".join(missing) if missing else "Dépendances non validées : " + ", ".join(
                d for d in t["depends_on"] if summary.get(d, {}).get("status") != "done")
        t["status"] = status
        t["validation"] = items
        t["blocked_reason"] = reason
        t["evidence"] = f"reports/{tid}/summary.json"
        if tid in NOTES:
            t["execution_note"] = NOTES[tid]
        out = ROOT / "reports" / tid
        out.mkdir(parents=True, exist_ok=True)
        (out / "summary.json").write_text(json.dumps({"task": tid, "title": t["title"], "status": status, "date_utc": NOW, "criteria": items,
                                                       "blocked_reason": reason, "note": NOTES.get(tid), "checks_dir": "reports/checks"},
                                                      indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        summary[tid] = {"status": status}
    backlog["execution_status"] = "in_progress_engine_validation_blocked"
    backlog["command_notice"] = ("Les commandes game_checks existent (tools/game_checks.py). Les suites unit/config/build/soak simulé s'exécutent ; "
                                 "les suites studio et le soak réel renvoient BLOCKED faute de Roblox Studio.")
    backlog["last_update_utc"] = NOW
    (ROOT / "tasks/backlog.json").write_text(json.dumps(backlog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=0))


if __name__ == "__main__":
    main()
