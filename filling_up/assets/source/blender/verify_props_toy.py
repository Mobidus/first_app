"""Vérification par RÉIMPORT de tous les assets Toy Overflow (5 accessoires, machine, 3 peluches).

Usage : .venv/bin/python -I assets/source/blender/verify_props_toy.py
Sortie : reports/T03/props_toy_verify.json (n'écrit rien d'autre).

Accessoires / machine (GLB, GLB LOD1, FBX rouverts dans une scène vide) : dimensions (enveloppe ± 2 %),
pivot (min z = 0, centre d'empreinte), triangles (LOD0 800-3 000, LOD1 <= 700, machine <= 8 000),
matériaux par maillage (<= 2), UV, textures ; dessus jouable : lancer de rayons verticaux sur une grille
de 0,25 stud couvrant TOUTE l'empreinte walkable_top (marge numérique 0,02 stud au bord) -> écart au
dessus du collider <= 0,25 stud.
Peluches : contrôles de verify_exports.verify (rig, poids, poses, dérive, dimensions) + anneau de bord
de 1 stud de l'empreinte au repos (LOD0 et LOD1) ; valeurs « avant » rappelées depuis
reports/T03/verify_log.txt de la passe précédente.
L'import Roblox Studio n'est pas testé ici (indisponible) : NOT_RUN.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import build_props_toy as T  # noqa: E402
import plush_specs as specs  # noqa: E402
import verify_exports as VE  # noqa: E402

ROOT = T.ROOT
OUT = os.path.join(ROOT, "reports", "T03", "props_toy_verify.json")
TOL = 0.25
ENV_TOL = 0.02

# Valeurs mesurées par la passe T03 précédente (reports/T03/verify_log.txt, GLB LOD0 au repos)
PLUSH_BEFORE = {
    "toy_plush_mallow": {"full_footprint_max_abs_dev": 0.937, "inset_0_5_max_abs_dev": 0.344, "inset_1_0_max_abs_dev": 0.159},
    "toy_plush_loppy": {"full_footprint_max_abs_dev": 3.323, "inset_0_5_max_abs_dev": 0.795, "inset_1_0_max_abs_dev": 0.167,
                        "full_footprint_misses": 55},
    "toy_plush_octo": {"full_footprint_max_abs_dev": 0.78, "inset_0_5_max_abs_dev": 0.359, "inset_1_0_max_abs_dev": 0.128},
}


def import_any(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.endswith(".glb"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o.type == "MESH"]


def world_bvh(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(o.matrix_world)
        me2 = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me2)
        tmp.free()
        bm.from_mesh(me2)
        bpy.data.meshes.remove(me2)
        ev.to_mesh_clear()
    bvh = BVHTree.FromBMesh(bm)
    co = np.array([v.co[:] for v in bm.verts])
    bm.free()
    return bvh, co


def top_grid(bvh, center, size, h, inset=0.02, step=0.25, ring=None):
    """Écarts dessus visible - dessus collider sur la grille ; ring = largeur de l'anneau de bord à isoler."""
    w, d = size
    cx, cy = center
    xs = np.arange(cx - w / 2 + inset, cx + w / 2 - inset + 1e-6, step)
    ys = np.arange(cy - d / 2 + inset, cy + d / 2 - inset + 1e-6, step)
    if xs[-1] < cx + w / 2 - inset - 1e-6:
        xs = np.append(xs, cx + w / 2 - inset)
    if ys[-1] < cy + d / 2 - inset - 1e-6:
        ys = np.append(ys, cy + d / 2 - inset)
    devs, edge, misses = [], [], 0
    worst = (0.0, None)
    for x in xs:
        for y in ys:
            hit = bvh.ray_cast(Vector((x, y, 60.0)), Vector((0, 0, -1)))
            if hit[0] is None:
                misses += 1
                dv = -h
            else:
                dv = hit[0].z - h
            devs.append(dv)
            if abs(dv) > abs(worst[0]):
                worst = (dv, [round(float(x), 2), round(float(y), 2)])
            if ring is not None and (min(x - (cx - w / 2), (cx + w / 2) - x, y - (cy - d / 2), (cy + d / 2) - y) < ring):
                edge.append(dv)
    devs = np.array(devs)
    out = {
        "inset_studs": inset, "step_studs": step, "samples": int(devs.size), "misses": misses,
        "max_abs_dev_studs": round(float(np.max(np.abs(devs))), 3),
        "max_above_studs": round(float(devs.max()), 3), "max_below_studs": round(float(devs.min()), 3),
        "mean_dev_studs": round(float(devs.mean()), 3),
        "within_tolerance_fraction": round(float(np.mean(np.abs(devs) <= TOL)), 4),
        "worst_point_blender_xy": worst[1],
    }
    if ring is not None:
        e = np.array(edge)
        out["edge_ring_width_studs"] = ring
        out["edge_ring_samples"] = int(e.size)
        out["edge_ring_max_abs_dev_studs"] = round(float(np.max(np.abs(e))), 3)
    return out


def mesh_stats(objs):
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    mats = {o.name: [m.name for m in o.data.materials if m] for o in objs}
    uvs = {o.name: len(o.data.uv_layers) for o in objs}
    tex = sorted({n.image.name for o in objs for m in o.data.materials if m and m.use_nodes
                  for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image})
    co = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in objs])
    mn, mx = co.min(0), co.max(0)
    return {"meshes": [o.name for o in objs], "triangles": int(tris), "materials_per_mesh": mats,
            "max_materials_per_mesh": max(len(v) for v in mats.values()), "uv_layers": uvs, "textures": tex,
            "bbox_min": [round(float(v), 3) for v in mn], "bbox_max": [round(float(v), 3) for v in mx],
            "size_wdh": [round(float(v), 3) for v in (mx - mn)]}


def env_ok(size, expected):
    return all(abs(a - e) <= ENV_TOL * e + 1e-6 for a, e in zip(size, expected))


def verify_prop(asset_id, fam):
    props = {p["id"]: p for p in fam["props"]}
    is_machine = asset_id == T.MACHINE_ID
    base = os.path.join(T.IMPORT_DIR, asset_id)
    files = {"glb": base + ".glb", "glb_lod1": base + "_lod1.glb", "fbx": base + ".fbx"}
    rep = {"asset_id": asset_id, "files": {}}
    size = fam["machine"]["size_studs"] if is_machine else props[asset_id]["size_studs"]
    rep["expected_size_wdh"] = size
    for k, p in files.items():
        objs = import_any(p)
        st = mesh_stats(objs)
        st["file"] = os.path.relpath(p, ROOT)
        st["file_bytes"] = os.path.getsize(p)
        st["size_within_2pct"] = env_ok(st["size_wdh"], size)
        if not is_machine and k in ("glb", "glb_lod1"):
            pr = props[asset_id]
            center = T.BUILDERS[asset_id][1]
            bvh, _co = world_bvh(objs)
            h = pr["collider"]["size_studs"][2]
            st["walkable_top"] = top_grid(bvh, center, pr["collider"]["walkable_top"], h, inset=0.02, ring=1.0)
            st["walkable_top"]["collider_top_studs"] = h
            st["walkable_top"]["collider_center_blender_xy"] = list(center)
        rep["files"][k] = st
    g, l1, fb = rep["files"]["glb"], rep["files"]["glb_lod1"], rep["files"]["fbx"]
    checks = {
        "envelope_glb_within_2pct": g["size_within_2pct"],
        "envelope_lod1_within_2pct": l1["size_within_2pct"],
        "envelope_fbx_within_2pct": fb["size_within_2pct"],
        "pivot_bottom_at_z0": abs(g["bbox_min"][2]) <= 0.01,
        "pivot_centered_xy_within_2pct": all(abs((a + b) / 2) <= ENV_TOL * e for a, b, e in zip(g["bbox_min"][:2], g["bbox_max"][:2], size[:2])),
        "materials_le_2_per_mesh": max(g["max_materials_per_mesh"], l1["max_materials_per_mesh"], fb["max_materials_per_mesh"]) <= 2,
        "uv_present": all(v >= 1 for v in g["uv_layers"].values()),
        "lod1_tris_le_700": l1["triangles"] <= 700,
        "fbx_tris_equal_glb": fb["triangles"] == g["triangles"],
    }
    if is_machine:
        checks["lod0_tris_le_8000"] = g["triangles"] <= 8000
        checks["split_parts_mount_spinner_trunks"] = len(g["meshes"]) == 3
    else:
        checks["lod0_tris_800_3000"] = 800 <= g["triangles"] <= 3000
        checks["walkable_top_flat_le_0_25_full_area_lod0"] = g["walkable_top"]["max_abs_dev_studs"] <= TOL and g["walkable_top"]["misses"] == 0
        checks["walkable_top_flat_le_0_25_full_area_lod1"] = l1["walkable_top"]["max_abs_dev_studs"] <= TOL and l1["walkable_top"]["misses"] == 0
    rep["checks"] = {k: ("PASS" if v else "FAIL") for k, v in checks.items()}
    return rep


def verify_plush(key):
    cr = specs.CREATURES[key]()
    rep = VE.verify(key)  # rig, poids, poses, dérive, dimensions (aucune écriture de fichier)
    out = {"asset_id": cr.asset_id, "verify_exports": rep}
    w, d, h = cr.collider["size_studs"]
    ring = {}
    for k, suffix in (("glb", ".glb"), ("glb_lod1", "_lod1.glb")):
        path = os.path.join(T.IMPORT_DIR, cr.asset_id + suffix)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=path)
        arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
        meshes = sorted([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices), reverse=True)
        if arms:
            VE.set_pose(arms[0], {})  # repos = pose de référence
        bvh, _ = world_bvh(meshes[:1])
        ring[k] = {
            "full_footprint_inset_0_02": top_grid(bvh, cr.collider_center_xy, (w, d), h, inset=0.02, ring=1.0),
            "inset_0_5": top_grid(bvh, cr.collider_center_xy, (w, d), h, inset=0.5),
            "inset_1_0": top_grid(bvh, cr.collider_center_xy, (w, d), h, inset=1.0),
        }
    out["top_alignment_rest"] = ring
    after = ring["glb"]
    out["edge_gap_before_after"] = {
        "before": PLUSH_BEFORE[cr.asset_id],
        "after": {"full_footprint_max_abs_dev": after["full_footprint_inset_0_02"]["max_abs_dev_studs"],
                  "edge_ring_1_stud_max_abs_dev": after["full_footprint_inset_0_02"]["edge_ring_max_abs_dev_studs"],
                  "inset_0_5_max_abs_dev": after["inset_0_5"]["max_abs_dev_studs"],
                  "inset_1_0_max_abs_dev": after["inset_1_0"]["max_abs_dev_studs"],
                  "full_footprint_misses": after["full_footprint_inset_0_02"]["misses"]},
    }
    checks = dict(rep["checks"])
    checks["edge_ring_rest_lod0_le_0_25"] = "PASS" if after["full_footprint_inset_0_02"]["max_abs_dev_studs"] <= TOL and \
        after["full_footprint_inset_0_02"]["misses"] == 0 else "FAIL"
    checks["edge_ring_rest_lod1_le_0_25"] = "PASS" if ring["glb_lod1"]["full_footprint_inset_0_02"]["max_abs_dev_studs"] <= TOL else "FAIL"
    out["checks"] = checks
    return out


def main():
    fam = T.load_family()
    doc = {"task": "T03 (passe qualité famille toy)", "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
           "blender_version": bpy.app.version_string,
           "method": "Exports rouverts dans une scène Blender vide (glTF/FBX) ; dessus jouable mesuré par lancer de rayons "
                     "verticaux (grille 0,25 stud, bord inclus à 0,02 stud près) ; tolérance 0,25 stud.",
           "roblox_studio_import": {"status": "NOT_RUN", "reason": "Roblox Studio / Open Cloud indisponibles dans le conteneur ; roblox_asset_id = null."},
           "assets": {}}
    for aid in list(T.BUILDERS) + [T.MACHINE_ID]:
        doc["assets"][aid] = verify_prop(aid, fam)
        print(aid, json.dumps(doc["assets"][aid]["checks"]))
    for key in ("mallow", "loppy", "octo"):
        r = verify_plush(key)
        doc["assets"][r["asset_id"]] = r
        print(r["asset_id"], json.dumps(r["checks"]))
        print("  edge", json.dumps(r["edge_gap_before_after"]))
    fails = {a: [k for k, v in r["checks"].items() if v != "PASS"] for a, r in doc["assets"].items()}
    doc["summary"] = {"all_pass": not any(fails.values()), "failed_checks": {a: f for a, f in fails.items() if f}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("summary", json.dumps(doc["summary"]))


if __name__ == "__main__":
    main()
