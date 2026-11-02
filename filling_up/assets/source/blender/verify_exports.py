"""Vérifie les exports des peluches en les ROUVRANT dans une scène vide.

Usage : .venv/bin/python -I assets/source/blender/verify_exports.py [mallow|loppy|octo|all]

Mesures (par fichier réimporté) : dimensions en studs, triangles, bones, poids
(normalisation, influences, sommets orphelins), matériaux, skin présent ; puis
sur le GLB principal : rapports d'échelle des poses vs config/runtime.json,
dérive après 100 cycles impact -> retour à la pose de référence, écart entre le
dessus visible et le dessus du collider (raycasts sur une grille de l'empreinte).

Sorties : reports/asset_import.json (cumulatif par asset) et
reports/T03/verify_log.txt. L'import Roblox Studio n'est PAS testé ici (bloqué).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import plush_specs as specs  # noqa: E402
from build_plush import ROOT  # noqa: E402

LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


def runtime_limits():
    with open(os.path.join(ROOT, "config", "runtime.json"), encoding="utf-8") as f:
        d = json.load(f)["deformation"]
    return d


def empty_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_file(path):
    empty_scene()
    if path.endswith(".glb"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    # le réimport glTF peut créer des maillages de forme de bone : garder le maillage skinné le plus dense
    meshes = sorted([o for o in bpy.data.objects if o.type == "MESH" and o.users_collection],
                    key=lambda o: (any(m.type == "ARMATURE" for m in o.modifiers), len(o.data.vertices)), reverse=True)
    return arms, meshes


def world_verts(obj, evaluated=True):
    dg = bpy.context.evaluated_depsgraph_get()
    ob = obj.evaluated_get(dg) if evaluated else obj
    me = ob.to_mesh()
    co = np.array([obj.matrix_world @ v.co for v in me.vertices])
    nrm = np.array([(obj.matrix_world.to_3x3() @ v.normal).normalized() for v in me.vertices])
    ob.to_mesh_clear()
    return co, nrm


def static_checks(path, cr):
    arms, meshes = import_file(path)
    res = {"file": os.path.relpath(path, ROOT), "opened": True}
    if not meshes:
        res["opened"] = False
        return res
    mesh = meshes[0]
    co, _ = world_verts(mesh, evaluated=False)
    mn, mx = co.min(axis=0), co.max(axis=0)
    size = (mx - mn)
    res["bbox_studs_width_depth_height"] = [round(float(size[0]), 3), round(float(size[1]), 3), round(float(size[2]), 3)]
    res["bbox_min_z"] = round(float(mn[2]), 4)
    res["expected_size_studs"] = cr.size_studs
    res["size_max_abs_error_studs"] = round(float(np.max(np.abs(size - np.array(cr.size_studs)))), 3)
    res["triangles"] = int(sum(len(p.vertices) - 2 for p in mesh.data.polygons))
    res["materials"] = len(mesh.data.materials)
    res["uv_layers"] = len(mesh.data.uv_layers)
    res["textures"] = sorted({n.image.name for m in mesh.data.materials if m and m.use_nodes
                              for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image})
    if arms:
        arm = arms[0]
        names = [b.name for b in arm.data.bones]
        res["armature_object_matrix_identity"] = bool(np.allclose(np.array(arm.matrix_world), np.eye(4), atol=1e-5))
        res["bones"] = names
        res["bone_count"] = len(names)
        belly = [n for n in names if n.startswith("Belly_")]
        secondary = [n for n in names if n != "Root" and not n.startswith("Belly_")]
        res["root_present"] = "Root" in names
        res["belly_bones"] = len(belly)
        res["secondary_bones"] = len(secondary)
        res["skin_modifier"] = any(m.type == "ARMATURE" for m in mesh.modifiers)
        gid = {g.index: g.name for g in mesh.vertex_groups}
        sums, infl, orphan = [], [], 0
        for v in mesh.data.vertices:
            ws = [g.weight for g in v.groups if g.group in gid and g.weight > 0]
            if not ws:
                orphan += 1
            sums.append(sum(ws))
            infl.append(len(ws))
        res["weight_sum_max_error"] = float(max(abs(s - 1) for s in sums))
        res["max_influences"] = int(max(infl))
        res["unweighted_vertices"] = orphan
    return res


def set_pose(arm, pose, scale=1.0):
    W = arm.matrix_world
    Winv3 = W.inverted().to_3x3()
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for bname, sp in pose.items():
        if bname not in arm.pose.bones:
            raise KeyError(bname)
        rest = arm.data.bones[bname].matrix_local.copy()
        h = Vector(rest.translation)
        M = rest
        if sp.get("r"):
            axis, ang = sp["r"]
            ax = (Winv3 @ Vector(axis)).normalized()
            R = Matrix.Rotation(math.radians(ang * scale), 4, ax)
            M = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ M
        if sp.get("t"):
            M = Matrix.Translation(Winv3 @ (Vector(sp["t"]) * scale)) @ M
        arm.pose.bones[bname].matrix = M
    bpy.context.view_layer.update()
    for pb in arm.pose.bones:
        if not np.allclose(np.array(pb.matrix_basis.to_scale()), 1.0, atol=1e-4):
            raise AssertionError(f"échelle détectée sur {pb.name}")


def top_profile(mesh, cr, inset):
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(mesh, dg)
    w, d, h = cr.collider["size_studs"]
    cx, cy = cr.collider_center_xy
    step = 0.25
    xs = np.arange(cx - w / 2 + inset, cx + w / 2 - inset + 1e-6, step)
    ys = np.arange(cy - d / 2 + inset, cy + d / 2 - inset + 1e-6, step)
    devs = []
    misses = 0
    for x in xs:
        for y in ys:
            hit = bvh.ray_cast(Vector((x, y, 50.0)), Vector((0, 0, -1)))
            if hit[0] is None:
                misses += 1
                continue
            devs.append(hit[0].z - h)
    devs = np.array(devs)
    tol = 0.25
    return {
        "inset_studs": inset,
        "samples": int(len(xs) * len(ys)),
        "misses": misses,
        "max_abs_dev_studs": round(float(np.max(np.abs(devs))), 3),
        "mean_dev_studs": round(float(np.mean(devs)), 3),
        "within_tolerance_fraction": round(float(np.mean(np.abs(devs) <= tol)), 3),
        "max_above_studs": round(float(devs.max()), 3),
        "max_below_studs": round(float(devs.min()), 3),
    }


def body_mask(cr, P_rest):
    g = cr.owner_memberships(P_rest)
    total = sum(g.values()) + 1e-12
    return (g.get("body", 0) / total) > 0.9


def pose_ratios(arm, mesh, cr, P_rest, N_rest):
    w, d, h = cr.collider["size_studs"]
    cx, cy = cr.collider_center_xy
    body = body_mask(cr, P_rest)
    inner = (np.abs(P_rest[:, 0] - cx) < w / 2 - 1.0) & (np.abs(P_rest[:, 1] - cy) < d / 2 - 1.0) & (N_rest[:, 2] > 0.6) & body
    top_rest = P_rest[inner, 2].mean()
    wx_rest = np.ptp(P_rest[body, 0])
    wy_rest = np.ptp(P_rest[body, 1])
    out = {}
    for pname, pose in cr.poses.items():
        set_pose(arm, pose)
        P, _ = world_verts(mesh)
        out[pname] = {
            "body_top_height_ratio": round(float(P[inner, 2].mean() / top_rest), 4),
            "body_width_ratio": round(float(np.ptp(P[body, 0]) / wx_rest), 4),
            "body_depth_ratio": round(float(np.ptp(P[body, 1]) / wy_rest), 4),
            "min_z": round(float(P[:, 2].min()), 4),
        }
    set_pose(arm, {})
    return out


def drift_test(arm, mesh, cr, P_ref, cycles=100):
    rnd = random.Random(specs_seed())
    worst = 0.0
    worst_during = 0.0
    for i in range(cycles):
        s = rnd.uniform(0.2, 1.0)
        set_pose(arm, cr.poses["impact"], scale=s)
        P_imp, _ = world_verts(mesh)
        worst_during = max(worst_during, float(np.abs(P_imp - P_ref).max()))
        set_pose(arm, {})
        P, _ = world_verts(mesh)
        worst = max(worst, float(np.abs(P - P_ref).max()))
    return {"cycles": cycles, "max_vertex_drift_after_reset_studs": worst,
            "max_displacement_during_impact_studs": round(worst_during, 3),
            "method": "pose absolue recalculée depuis la référence à chaque cycle (intensité aléatoire 0.2-1.0, graine fixe)"}


def specs_seed():
    return 7


def verify(key):
    cr = specs.CREATURES[key]()
    lim = runtime_limits()
    base = os.path.join(ROOT, "assets", "import", "models", cr.asset_id)
    files = {"glb": base + ".glb", "glb_lod1": base + "_lod1.glb", "fbx": base + ".fbx"}
    report = {"asset_id": cr.asset_id, "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "blender_version": bpy.app.version_string, "files": {}}
    for k, p in files.items():
        report["files"][k] = static_checks(p, cr) if os.path.exists(p) else {"file": p, "opened": False}
        log(f"[{cr.asset_id}] {k}: {json.dumps(report['files'][k], ensure_ascii=False)}")

    # tests dynamiques sur le GLB principal réimporté
    arms, meshes = import_file(files["glb"])
    arm, mesh = arms[0], meshes[0]
    set_pose(arm, {})
    P_ref, N_ref = world_verts(mesh)
    report["pose_ratios"] = pose_ratios(arm, mesh, cr, P_ref, N_ref)
    log(f"[{cr.asset_id}] pose_ratios: {json.dumps(report['pose_ratios'])}")
    report["drift"] = drift_test(arm, mesh, cr, P_ref)
    log(f"[{cr.asset_id}] drift: {json.dumps(report['drift'], ensure_ascii=False)}")
    set_pose(arm, {})
    report["top_alignment_rest"] = {"full_footprint": top_profile(mesh, cr, 0.0),
                                    "inset_0_5": top_profile(mesh, cr, 0.5),
                                    "inset_1_0": top_profile(mesh, cr, 1.0)}
    set_pose(arm, cr.poses["player_landing"])
    report["top_alignment_player_landing"] = {"inset_1_0": top_profile(mesh, cr, 1.0)}
    set_pose(arm, {})
    log(f"[{cr.asset_id}] top_rest: {json.dumps(report['top_alignment_rest'])}")
    log(f"[{cr.asset_id}] top_landing: {json.dumps(report['top_alignment_player_landing'])}")

    g = report["files"]["glb"]
    pr = report["pose_ratios"]
    tol = lim["walkable_top_alignment_tolerance_studs"]
    checks = {
        # enveloppe visuelle : ne jamais dépasser size_studs (+0.05), ni être plus petit de plus de 0.3 stud
        "dimensions_within_envelope": all(-0.3 <= a - e <= 0.05 for a, e in zip(g["bbox_studs_width_depth_height"], cr.size_studs)),
        "near_tris_1500_3500": 1500 <= g["triangles"] <= 3500,
        "far_tris_300_700": 300 <= report["files"]["glb_lod1"]["triangles"] <= 700,
        "root_plus_9_belly": g.get("root_present") and g.get("belly_bones") == lim["plush_lattice_bones"],
        "secondary_le_6": g.get("secondary_bones", 99) <= lim["secondary_bones_max"],
        "weights_normalized_1e-4": g.get("weight_sum_max_error", 1) <= 1e-4,
        "max_4_influences": g.get("max_influences", 99) <= 4,
        "no_unweighted_vertex": g.get("unweighted_vertices", 1) == 0,
        "materials_le_2": g["materials"] <= 2,
        "skin_survives_reimport_glb": bool(g.get("skin_modifier")),
        "skin_survives_reimport_fbx": bool(report["files"]["fbx"].get("skin_modifier")),
        "fall_stretch_le_limit": pr["fall"]["body_top_height_ratio"] <= lim["fall_stretch_y_max"] + 1e-3,
        "impact_compression_ge_limit": pr["impact"]["body_top_height_ratio"] >= lim["impact_scale_y_min"] - 1e-3,
        "impact_widening_le_limit": max(pr["impact"]["body_width_ratio"], pr["impact"]["body_depth_ratio"]) <= lim["impact_scale_xz_max"] + 1e-3,
        "no_drift_after_100_cycles": report["drift"]["max_vertex_drift_after_reset_studs"] < 1e-4,
        "top_alignment_rest_inset1_le_tol": report["top_alignment_rest"]["inset_1_0"]["max_abs_dev_studs"] <= tol,
        "top_alignment_landing_inset1_le_tol": report["top_alignment_player_landing"]["inset_1_0"]["max_abs_dev_studs"] <= tol,
        "never_below_floor": min(v["min_z"] for v in pr.values()) >= -0.05,
    }
    report["checks"] = {k: ("PASS" if v else "FAIL") for k, v in checks.items()}
    report["roblox_studio_import"] = {
        "status": "blocked",
        "reason": "Aucun Roblox Studio ni accès Open Cloud autorisé dans le conteneur ; rig, skin, unités et collisions non mesurés dans Roblox.",
        "roblox_asset_id": None,
        "studio_checks": "NOT_RUN",
    }
    log(f"[{cr.asset_id}] checks: {json.dumps(report['checks'])}")
    return report


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    keys = list(specs.CREATURES) if which == "all" else [which]
    out_path = os.path.join(ROOT, "reports", "asset_import.json")
    existing = {}
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            existing = json.load(f)
    assets = existing.get("assets", {})
    for k in keys:
        cr = specs.CREATURES[k]()
        model_dir = os.path.join(ROOT, "assets", "source", "models", {"mallow": "Mallow", "loppy": "Loppy", "octo": "Octo"}[k])
        if not os.path.exists(os.path.join(model_dir, "build_info.json")):
            log(f"[{cr.asset_id}] non construit : ignoré")
            continue
        assets[cr.asset_id] = verify(k)
    doc = {
        "task": "T03",
        "scope": "Vérification Blender des exports réimportés ; ne remplace pas l'import et la mesure dans Roblox Studio.",
        "import_status": "blocked",
        "import_blocker": "Roblox Studio / Open Cloud indisponibles dans l'environnement d'exécution ; aucun identifiant Roblox obtenu.",
        "units_convention": "1 unité Blender = 1 unité glTF/FBX = 1 stud (voir docs/decisions/0003_unites_import_3d.md)",
        "assets": assets,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    os.makedirs(os.path.join(ROOT, "reports", "T03"), exist_ok=True)
    mode = "a" if which != "all" else "w"
    with open(os.path.join(ROOT, "reports", "T03", "verify_log.txt"), mode, encoding="utf-8") as f:
        f.write(f"# verify_exports.py {which} — {dt.datetime.now(dt.timezone.utc).isoformat()}\n")
        f.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
