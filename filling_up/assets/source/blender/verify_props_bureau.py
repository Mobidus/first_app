"""Vérifie les exports des props Bureau perdu en les ROUVRANT dans une scène vide.

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/verify_props_bureau.py

Pour chaque asset (8 props + machine) et chaque fichier (GLB LOD0, GLB LOD1, FBX LOD0) :
dimensions en studs vs size_studs de config/rooms.json (±2 %), pivot bottom_center, triangles,
matériaux, atlas, UV ; lecture brute du JSON glTF (axes Y-up Roblox : hauteur sur Y,
profondeur sur Z, minimum Y = 0) ; dessus praticable : lancer de rayons verticaux sur une
grille (pas 0,25 stud) couvrant walkable_top, écart au sommet du collider <= 0,25 stud,
sur LOD0 et LOD1.

Sorties : reports/T03/props_bureau_verify.json (PASS/FAIL par critère) et
reports/T03/props_bureau_verify_log.txt. L'import Roblox Studio n'est PAS testé (indisponible).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from build_props_bureau import ASSET_ORDER, IMPORT_DIR, ROOT, load_family  # noqa: E402

TOL_DIM = 0.02          # ±2 % de size_studs
TOL_TOP = 0.25          # écart max dessus visible / dessus du collider (docs/02, runtime)
GRID_STEP = 0.25
EDGE_INSET = 0.10       # tolérance de biseau au bord exact de l'empreinte
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


def empty_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_file(path):
    empty_scene()
    if path.endswith(".glb"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o.type == "MESH"]


def world_coords(ob):
    me = ob.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def glb_json(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, ver, length = struct.unpack_from("<III", data, 0)
    clen, ctype = struct.unpack_from("<II", data, 12)
    js = json.loads(data[20:20 + clen].decode("utf-8"))
    return {"magic_ok": magic == 0x46546C67, "version": ver, "json": js}


def gltf_axes(path, size):
    g = glb_json(path)
    js = g["json"]
    mins, maxs = [], []
    for m in js.get("meshes", []):
        for p in m["primitives"]:
            acc = js["accessors"][p["attributes"]["POSITION"]]
            mins.append(acc["min"])
            maxs.append(acc["max"])
    mn = np.min(np.array(mins), axis=0)
    mx = np.max(np.array(maxs), axis=0)
    ext = mx - mn
    nodes = js.get("nodes", [])
    identity = all(not any(k in n for k in ("rotation", "scale", "translation", "matrix")) for n in nodes)
    w, d, h = size
    return {
        "gltf_extent_xyz": [round(float(v), 3) for v in ext],
        "gltf_min_y": round(float(mn[1]), 4),
        "y_is_height": bool(abs(ext[1] - h) <= TOL_DIM * h),
        "z_is_depth": bool(abs(ext[2] - d) <= TOL_DIM * d),
        "x_is_width": bool(abs(ext[0] - w) <= TOL_DIM * w),
        "nodes_identity_transform": identity,
        "images_embedded": len(js.get("images", [])),
        "materials": len(js.get("materials", [])),
        "primitives": sum(len(m["primitives"]) for m in js.get("meshes", [])),
        "generator": js.get("asset", {}).get("generator"),
    }


def static_checks(path, size):
    meshes = import_file(path)
    res = {"file": os.path.relpath(path, ROOT), "opened": bool(meshes), "mesh_objects": len(meshes)}
    if not meshes:
        return res, None
    ob = meshes[0]
    co = world_coords(ob)
    mn, mx = co.min(axis=0), co.max(axis=0)
    ext = mx - mn
    res["bbox_studs_width_depth_height"] = [round(float(v), 3) for v in ext]
    res["bbox_min"] = [round(float(v), 4) for v in mn]
    res["bbox_center_xy"] = [round(float((mn[0] + mx[0]) / 2), 4), round(float((mn[1] + mx[1]) / 2), 4)]
    res["expected_size_studs"] = size
    res["size_rel_error"] = [round(float(abs(a - e) / e), 4) for a, e in zip(ext, size)]
    res["triangles"] = int(sum(len(p.vertices) - 2 for p in ob.data.polygons))
    res["materials"] = len([m for m in ob.data.materials if m])
    res["uv_layers"] = len(ob.data.uv_layers)
    imgs = sorted({(n.image.name, tuple(n.image.size)) for m in ob.data.materials if m and m.use_nodes
                   for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image})
    res["textures"] = [f"{n} {s[0]}x{s[1]}" for n, s in imgs]
    res["atlas_1024"] = any(s == (1024, 1024) for _, s in imgs)
    return res, ob


def top_profile(ob, w, d, h, tw, td, inset):
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(ob, dg)
    x0, x1 = -tw / 2 + inset, tw / 2 - inset
    y0, y1 = -td / 2 + inset, td / 2 - inset
    nx = int(round((x1 - x0) / GRID_STEP))
    ny = int(round((y1 - y0) / GRID_STEP))
    xs = np.linspace(x0, x1, nx + 1)
    ys = np.linspace(y0, y1, ny + 1)
    devs, misses = [], 0
    worst = None
    for x in xs:
        for y in ys:
            hit = bvh.ray_cast(Vector((x, y, h + 10.0)), Vector((0, 0, -1)))
            if hit[0] is None:
                misses += 1
                continue
            dv = hit[0].z - h
            devs.append(dv)
            if worst is None or abs(dv) > abs(worst[2]):
                worst = (round(float(x), 2), round(float(y), 2), round(float(dv), 3))
    devs = np.array(devs) if devs else np.array([np.nan])
    return {
        "inset_studs": inset, "grid_step_studs": GRID_STEP, "samples": int(len(xs) * len(ys)), "misses": misses,
        "max_abs_dev_studs": round(float(np.nanmax(np.abs(devs))), 3),
        "mean_dev_studs": round(float(np.nanmean(devs)), 3),
        "max_above_studs": round(float(np.nanmax(devs)), 3),
        "max_below_studs": round(float(np.nanmin(devs)), 3),
        "within_tolerance_fraction": round(float(np.mean(np.abs(devs) <= TOL_TOP)), 4),
        "worst_sample_x_y_dev": worst,
    }


def facing_ratio(ob):
    """Part des triangles tournés vers l'avant (+Y Blender = -Z Roblox) vs l'arrière : indicatif."""
    fr = sum(p.area for p in ob.data.polygons if p.normal.y > 0.5)
    bk = sum(p.area for p in ob.data.polygons if p.normal.y < -0.5)
    nfr = sum(1 for p in ob.data.polygons if p.normal.y > 0.5)
    nbk = sum(1 for p in ob.data.polygons if p.normal.y < -0.5)
    return {"front_faces": nfr, "back_faces": nbk, "front_area": round(fr, 2), "back_area": round(bk, 2)}


def verify(aid, spec):
    size = spec["size_studs"]
    w, d, h = size
    is_machine = not spec.get("collider")
    base = os.path.join(IMPORT_DIR, aid)
    files = {"glb": base + ".glb", "glb_lod1": base + "_lod1.glb", "fbx": base + ".fbx"}
    rep = {"asset_id": aid, "name": spec.get("name"), "size_studs": size,
           "collider": spec.get("collider") or "separate_architecture_proxy", "files": {}}
    tops = {}
    for k, p in files.items():
        if not os.path.exists(p):
            rep["files"][k] = {"file": os.path.relpath(p, ROOT), "opened": False}
            continue
        res, ob = static_checks(p, size)
        if k.startswith("glb"):
            res["gltf_raw"] = gltf_axes(p, size)
        if k == "glb":
            res["facing"] = facing_ratio(ob)
        if ob is not None and not is_machine and k in ("glb", "glb_lod1"):
            tw, td = spec["collider"]["walkable_top"]
            ch = spec["collider"]["size_studs"][2]
            tops[k] = {"edge_inset_0_10": top_profile(ob, w, d, ch, tw, td, EDGE_INSET),
                       "edge_inset_0_02_info": top_profile(ob, w, d, ch, tw, td, 0.02),
                       "inset_1_0_info": top_profile(ob, w, d, ch, tw, td, 1.0)}
        rep["files"][k] = res
        log(f"[{aid}] {k}: {json.dumps(res, ensure_ascii=False)}")
    if tops:
        rep["walkable_top"] = tops
        log(f"[{aid}] walkable_top: {json.dumps(tops)}")

    g, g1, fb = rep["files"]["glb"], rep["files"]["glb_lod1"], rep["files"]["fbx"]

    def dims_ok(r):
        return r.get("opened") and all(e <= TOL_DIM for e in r["size_rel_error"])

    lo, hi = (3000, 8000) if is_machine else (800, 3000)
    checks = {
        "files_reopen_glb_lod1_fbx": all(r.get("opened") and r.get("mesh_objects") == 1 for r in (g, g1, fb)),
        "dims_within_2pct_glb_lod0": dims_ok(g),
        "dims_within_2pct_glb_lod1": dims_ok(g1),
        "dims_within_2pct_fbx": dims_ok(fb),
        "pivot_bottom_center": abs(g["bbox_min"][2]) <= 0.02 and abs(g["bbox_center_xy"][0]) <= 0.01 * w + 0.02
        and abs(g["bbox_center_xy"][1]) <= 0.01 * d + 0.02,
        "gltf_axes_y_up_height_z_depth": g["gltf_raw"]["y_is_height"] and g["gltf_raw"]["z_is_depth"]
        and g["gltf_raw"]["x_is_width"] and abs(g["gltf_raw"]["gltf_min_y"]) <= 0.02,
        "gltf_nodes_identity_transform": g["gltf_raw"]["nodes_identity_transform"] and g1["gltf_raw"]["nodes_identity_transform"],
        f"tris_lod0_{lo}_{hi}": lo <= g["triangles"] <= hi,
        "tris_lod1_le_700": g1["triangles"] <= 700,
        "materials_le_2_all_files": all(r["materials"] <= 2 for r in (g, g1, fb)),
        "shared_atlas_1024_embedded": g["atlas_1024"] and g1["atlas_1024"] and g["gltf_raw"]["images_embedded"] == 1,
        "uv_present": all(r["uv_layers"] >= 1 for r in (g, g1, fb)),
    }
    if not is_machine:
        t0 = rep["walkable_top"]["glb"]["edge_inset_0_10"]
        t1 = rep["walkable_top"]["glb_lod1"]["edge_inset_0_10"]
        checks["walkable_top_flat_le_0_25_lod0"] = t0["misses"] == 0 and t0["max_abs_dev_studs"] <= TOL_TOP
        checks["walkable_top_flat_le_0_25_lod1"] = t1["misses"] == 0 and t1["max_abs_dev_studs"] <= TOL_TOP
        checks["top_not_above_collider_gt_0_05"] = max(t0["max_above_studs"], t1["max_above_studs"]) <= 0.05
    rep["checks"] = {k: ("PASS" if bool(v) else "FAIL") for k, v in checks.items()}
    rep["roblox_studio_import"] = {"status": "NOT_RUN", "reason": "Roblox Studio / Open Cloud indisponibles dans le conteneur.",
                                   "roblox_asset_id": None}
    log(f"[{aid}] checks: {json.dumps(rep['checks'])}")
    return rep


def main():
    fam, specs = load_family()
    assets = {}
    for aid in ASSET_ORDER:
        assets[aid] = verify(aid, specs[aid])
    total = sum(len(a["checks"]) for a in assets.values())
    passed = sum(v == "PASS" for a in assets.values() for v in a["checks"].values())
    doc = {
        "task": "T03",
        "family": "bureau",
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "blender_version": bpy.app.version_string,
        "scope": "Exports rouverts dans Blender (scène vide). Ne remplace pas l'import et la mesure dans Roblox Studio (NOT_RUN).",
        "method": {
            "dims": "boîte englobante du maillage réimporté vs config/rooms.json size_studs, tolérance ±2 %",
            "walkable_top": f"rayons verticaux sur grille {GRID_STEP} stud couvrant walkable_top (centré), bord exact retiré de "
                            f"{EDGE_INSET} stud (biseaux), écart au sommet du collider <= {TOL_TOP} ; insets 0,02 et 1,0 donnés pour information",
            "tris_budget": "props LOD0 800-3000, machine 3000-8000 (docs/02 machine signature), LOD1 <= 700 (consigne utilisateur)",
            "axes": "JSON glTF brut : étendue Y = hauteur, Z = profondeur, min Y = 0 (Roblox Y-up, avant -Z = +Y Blender)",
        },
        "summary": {"checks_total": total, "checks_passed": passed, "checks_failed": total - passed},
        "assets": assets,
    }
    out = os.path.join(ROOT, "reports", "T03", "props_bureau_verify.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ROOT, "reports", "T03", "props_bureau_verify_log.txt"), "w", encoding="utf-8") as f:
        f.write(f"# verify_props_bureau.py — {doc['checked_at_utc']}\n" + "\n".join(LOG) + "\n")
    log(f"SUMMARY {passed}/{total} PASS")
    write_manifest_updates(assets)


def write_manifest_updates(assets):
    """Propositions de mise à jour du manifeste (appliquées par l'agent principal, jamais ici)."""
    with open(os.path.join(ROOT, "assets", "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    entries = man if isinstance(man, list) else man.get("assets", [])
    if isinstance(entries, dict):
        entries = list(entries.values())
    current = {e.get("id"): e for e in entries if isinstance(e, dict)}
    with open(os.path.join(ROOT, "assets", "source", "models", "bureau", "build_info.json"), encoding="utf-8") as f:
        info = json.load(f)
    blend = "assets/source/models/bureau/bureau_props.blend"
    ups = []
    for aid, rep in assets.items():
        cur = current.get(aid, {})
        failed = [k for k, v in rep["checks"].items() if v != "PASS"]
        g = rep["files"]["glb"]
        e = {
            "id": aid,
            "status": "modeled" if not failed else cur.get("status", "designed"),
            "roblox_asset_id": None,
            "source_path": blend,
            "source_path_manifest_current": cur.get("source_path"),
            "source_path_change_proposed": cur.get("source_path") != blend,
            "export_path": f"assets/import/models/{aid}.glb",
            "export_path_manifest_current": cur.get("export_path"),
            "additional_exports": [f"assets/import/models/{aid}_lod1.glb", f"assets/import/models/{aid}.fbx"],
            "supporting_files": ["assets/source/models/bureau/textures/bureau_atlas_1024.png",
                                 "assets/source/models/bureau/build_info.json"],
            "generator_script": "assets/source/blender/build_props_bureau.py",
            "production_method_proposed": "blender_mesh_static",
            "production_method_manifest_current": cur.get("production_method"),
            "max_triangles_near_proposed": 8000 if aid.startswith("machine") else 3000,
            "max_triangles_near_manifest_current": cur.get("max_triangles_near"),
            "validation_evidence": [
                f"reports/T03/props_bureau_verify.json#assets.{aid}",
                "reports/T03/props_bureau_verify_log.txt",
                f"reports/T03/renders/{aid}_3q.png",
                f"reports/T03/renders/{aid}_silhouette.png",
                f"reports/T03/renders/{aid}_silhouette_low.png",
                "reports/T03/renders/props_bureau_sheet.png",
            ],
            "measured": {
                "bbox_studs_width_depth_height": g["bbox_studs_width_depth_height"],
                "triangles_lod0": g["triangles"],
                "triangles_lod1": rep["files"]["glb_lod1"]["triangles"],
                "materials_per_mesh": g["materials"],
                "walkable_top_max_abs_dev_studs": (rep.get("walkable_top", {}).get("glb", {})
                                                   .get("edge_inset_0_10", {}).get("max_abs_dev_studs")),
                "blender_checks_failed": failed,
            },
            "collision": info["assets"].get(aid, {}).get("collision"),
            "not_validated_because": [
                "Import Roblox Studio non réalisé (Studio/Open Cloud indisponibles) : unités, axes et aspect à mesurer",
                "Test d'identification en silhouette auprès de testeurs non réalisé",
            ],
        }
        ups.append(e)
    doc = {
        "task": "T03",
        "family": "bureau",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "rule": "Statut proposé au plus 'modeled' ; jamais imported/validated sans import Roblox réel. roblox_asset_id reste null.",
        "apply_by": "agent principal (ce lot ne modifie pas assets/manifest.json)",
        "budget_note": "Consigne utilisateur « objets de grande qualité » : LOD0 800-3000 triangles par prop "
                       "(machine <= 8000), LOD1 <= 700 ; remplace le budget initial 100-800 du manifeste.",
        "updates": ups,
    }
    with open(os.path.join(ROOT, "reports", "T03", "manifest_updates_bureau.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
