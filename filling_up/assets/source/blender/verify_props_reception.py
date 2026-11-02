"""Vérifie les exports de la famille Réception en les ROUVRANT dans une scène vide.

Usage : .venv/bin/python -I assets/source/blender/verify_props_reception.py
Sortie : reports/T03/props_reception_verify.json (+ props_reception_verify_log.txt)

Par asset (GLB LOD0, GLB LOD1, FBX) : dimensions vs size_studs (config/rooms.json, tolérance ±2 %),
pivot bottom_center, triangles, matériaux par maillage, UV et texture embarquée ; en-tête glTF brut
(axes Roblox : X largeur, Y haut, Z profondeur) ; sens avant (-Z Roblox = +Y Blender) vérifié par la
position des décors frontaux ; planéité du dessus praticable par lancers de rayons verticaux sur le
rectangle walkable_top centré, comparée à la hauteur du collider (tolérance 0,25 stud).
L'import Roblox Studio n'est PAS testé ici (bloqué : ni Studio ni Open Cloud dans le conteneur).
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

import reception_atlas as atlas  # noqa: E402
from build_props_reception import BUILDERS, IMPORT_DIR, MACHINE_ID, ROOT, spec  # noqa: E402

TOL_TOP = 0.25
TOL_ENV = 0.02
GRID = 0.25
LOG = []
# décor qui doit se trouver à l'avant (+Y Blender = -Z Roblox) : tuile d'atlas utilisée uniquement en façade
FRONT_TILE = {"reception_carton": "label_carton", "reception_suitcase": "label_small",
              "reception_accordion_parcel": "label_small", MACHINE_ID: "eye"}


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def empty():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_file(path):
    empty()
    if path.endswith(".glb"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o.type == "MESH"]


def world_coords(objs):
    out = []
    for o in objs:
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        M = np.array(o.matrix_world)
        out.append(co @ M[:3, :3].T + M[:3, 3])
    return np.concatenate(out)


def glb_header(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, ver, _ln = struct.unpack_from("<III", data, 0)
    clen, _ctype = struct.unpack_from("<II", data, 12)
    js = json.loads(data[20:20 + clen])
    pos_min = np.array([np.inf] * 3)
    pos_max = np.array([-np.inf] * 3)
    prims = 0
    for m in js.get("meshes", []):
        for p in m["primitives"]:
            prims += 1
            acc = js["accessors"][p["attributes"]["POSITION"]]
            pos_min = np.minimum(pos_min, acc["min"])
            pos_max = np.maximum(pos_max, acc["max"])
    nodes = js.get("nodes", [])
    return {
        "magic_ok": magic == 0x46546C67 and ver == 2,
        "generator": js.get("asset", {}).get("generator"),
        "meshes": len(js.get("meshes", [])), "primitives": prims,
        "materials": [m.get("name") for m in js.get("materials", [])],
        "images_embedded": len(js.get("images", [])),
        "node_translations": [n.get("translation", [0, 0, 0]) for n in nodes],
        "gltf_position_min_xyz": [round(float(v), 4) for v in pos_min],
        "gltf_position_max_xyz": [round(float(v), 4) for v in pos_max],
        "alpha_modes": [m.get("alphaMode", "OPAQUE") for m in js.get("materials", [])],
        "has_metallic_roughness_texture": any("metallicRoughnessTexture" in m.get("pbrMetallicRoughness", {})
                                              for m in js.get("materials", [])),
    }


def static(path, size):
    objs = import_file(path)
    co = world_coords(objs)
    mn, mx = co.min(axis=0), co.max(axis=0)
    dims = mx - mn
    S = np.array(size, dtype=float)
    rel = (dims - S) / S
    mats_per_mesh = [len([m for m in o.data.materials if m]) for o in objs]
    return objs, {
        "file": os.path.relpath(path, ROOT),
        "mesh_objects": len(objs),
        "triangles": int(sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)),
        "dims_studs_wdh": [round(float(v), 4) for v in dims],
        "expected_size_studs_wdh": list(size),
        "dims_rel_error": [round(float(v), 4) for v in rel],
        "bbox_min": [round(float(v), 4) for v in mn],
        "bbox_max": [round(float(v), 4) for v in mx],
        "pivot_offset_xy": [round(float((mn[0] + mx[0]) / 2), 4), round(float((mn[1] + mx[1]) / 2), 4)],
        "materials_per_mesh_max": max(mats_per_mesh) if mats_per_mesh else 0,
        "material_names": sorted({m.name for o in objs for m in o.data.materials if m}),
        "uv_layers": min(len(o.data.uv_layers) for o in objs) if objs else 0,
    }


def bvhs(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    return [BVHTree.FromObject(o, dg) for o in objs]


def top_hit(trees, x, y):
    best = None
    for t in trees:
        h = t.ray_cast(Vector((x, y, 100.0)), Vector((0, 0, -1)))
        if h[0] is not None and (best is None or h[0].z > best):
            best = h[0].z
    return best


def flatness(objs, collider_h, walk, inset, cell_centred=False):
    trees = bvhs(objs)
    w, d = walk
    if cell_centred:
        xs = np.arange(-w / 2 + GRID / 2, w / 2, GRID)
        ys = np.arange(-d / 2 + GRID / 2, d / 2, GRID)
    else:
        xs = np.arange(-w / 2 + inset, w / 2 - inset + 1e-6, GRID)
        ys = np.arange(-d / 2 + inset, d / 2 - inset + 1e-6, GRID)
    devs, misses = [], 0
    for x in xs:
        for y in ys:
            z = top_hit(trees, float(x), float(y))
            if z is None:
                misses += 1
                devs.append(-collider_h)
            else:
                devs.append(z - collider_h)
    devs = np.array(devs)
    return {
        "grid_studs": GRID, "inset_studs": GRID / 2 if cell_centred else inset,
        "sampling": "cell_centred" if cell_centred else "edge_inclusive",
        "samples": int(devs.size), "misses": misses,
        "max_abs_dev_studs": round(float(np.abs(devs).max()), 4),
        "max_above_studs": round(float(devs.max()), 4), "max_below_studs": round(float(devs.min()), 4),
        "mean_dev_studs": round(float(devs.mean()), 4),
        "within_tolerance_fraction": round(float(np.mean(np.abs(devs) <= TOL_TOP)), 4),
    }


def front_check(objs, tile):
    u0, v0, u1, v1 = atlas.tile_uv(tile, 0.0)
    ys = []
    for o in objs:
        uv = o.data.uv_layers.active.data
        for p in o.data.polygons:
            for li in p.loop_indices:
                u, v = uv[li].uv
                if u0 <= u <= u1 and v0 <= v <= v1:
                    ys.append((o.matrix_world @ o.data.vertices[o.data.loops[li].vertex_index].co).y)
    if not ys:
        return {"tile": tile, "found": False}
    m = float(np.mean(ys))
    return {"tile": tile, "found": True, "mean_blender_y": round(m, 3), "roblox_z": round(-m, 3),
            "is_front_minus_z_roblox": m > 0}


def verify(pid):
    s = spec(pid)
    size = [float(v) for v in s["size_studs"]]
    is_machine = pid == MACHINE_ID
    base = os.path.join(IMPORT_DIR, pid)
    rep = {"asset_id": pid, "kind": "machine" if is_machine else "prop",
           "behavior": None if is_machine else s["behavior"], "size_studs_wdh": size}
    rep["gltf_header"] = glb_header(base + ".glb")
    objs, rep["glb_lod0"] = static(base + ".glb", size)
    if not is_machine:
        col = s["collider"]
        h = float(col["size_studs"][2])
        walk = col["walkable_top"]
        rep["collider"] = {"size_studs_wdh": col["size_studs"], "walkable_top": walk, "top_height": h}
        rep["top_lod0"] = {"inset_0_25": flatness(objs, h, walk, 0.25),
                           "full_footprint_cell_centred": flatness(objs, h, walk, 0, cell_centred=True)}
    if pid in FRONT_TILE:
        rep["front_axis"] = front_check(objs, FRONT_TILE[pid])
    objs1, rep["glb_lod1"] = static(base + "_lod1.glb", size)
    if not is_machine:
        rep["top_lod1"] = {"inset_0_25": flatness(objs1, h, walk, 0.25),
                           "full_footprint_cell_centred": flatness(objs1, h, walk, 0, cell_centred=True)}
    _o, rep["fbx_lod0"] = static(base + ".fbx", size)

    g0, g1, fb, hd = rep["glb_lod0"], rep["glb_lod1"], rep["fbx_lod0"], rep["gltf_header"]
    lo, hi = (3000, 8000) if is_machine else (800, 3000)
    checks = {
        "glb_reopened": g0["mesh_objects"] >= 1 and hd["magic_ok"],
        "envelope_lod0_within_2pct": all(abs(r) <= TOL_ENV for r in g0["dims_rel_error"]),
        "envelope_lod1_within_2pct": all(abs(r) <= TOL_ENV for r in g1["dims_rel_error"]),
        "envelope_fbx_within_2pct": all(abs(r) <= TOL_ENV for r in fb["dims_rel_error"]),
        "pivot_bottom_center": abs(g0["bbox_min"][2]) <= 0.01 and max(abs(v) for v in g0["pivot_offset_xy"]) <= 0.05
        and all(max(abs(c) for c in t) < 1e-6 for t in hd["node_translations"]),
        "gltf_axes_x_width_y_up_z_depth": abs((hd["gltf_position_max_xyz"][0] - hd["gltf_position_min_xyz"][0]) - g0["dims_studs_wdh"][0]) < 0.01
        and abs(hd["gltf_position_min_xyz"][1]) < 0.01
        and abs((hd["gltf_position_max_xyz"][1] - hd["gltf_position_min_xyz"][1]) - g0["dims_studs_wdh"][2]) < 0.01
        and abs((hd["gltf_position_max_xyz"][2] - hd["gltf_position_min_xyz"][2]) - g0["dims_studs_wdh"][1]) < 0.01,
        f"tris_lod0_{lo}_{hi}": lo <= g0["triangles"] <= hi,
        "tris_lod1_le_700": g1["triangles"] <= 700,
        "materials_le_2_per_mesh": g0["materials_per_mesh_max"] <= 2 and g1["materials_per_mesh_max"] <= 2,
        "uv_and_embedded_texture": g0["uv_layers"] >= 1 and hd["images_embedded"] >= 1,
    }
    if "front_axis" in rep:
        checks["front_details_face_minus_z_roblox"] = bool(rep["front_axis"].get("is_front_minus_z_roblox"))
    if not is_machine:
        t0, t1 = rep["top_lod0"]["inset_0_25"], rep["top_lod1"]["inset_0_25"]
        checks["walkable_top_flat_lod0_inset0_25_le_0_25"] = t0["misses"] == 0 and t0["max_abs_dev_studs"] <= TOL_TOP
        checks["walkable_top_flat_lod1_inset0_25_le_0_25"] = t1["misses"] == 0 and t1["max_abs_dev_studs"] <= TOL_TOP
        checks["walkable_top_no_part_above_collider_plus_0_05"] = t0["max_above_studs"] <= 0.05 and t1["max_above_studs"] <= 0.05
    rep["checks"] = {k: ("PASS" if v else "FAIL") for k, v in checks.items()}
    rep["informational"] = {
        "full_footprint_note": "Échantillons centrés sur une grille de 0,25 stud jusqu'à 0,125 du bord : inclut l'arrondi "
                               "décoratif du rebord (biseaux ≤ 0,25) ; reporté, non bloquant.",
    }
    rep["roblox_studio_import"] = {"status": "blocked", "roblox_asset_id": None, "studio_checks": "NOT_RUN"}
    log(f"[{pid}] tris {g0['triangles']}/{g1['triangles']} dims {g0['dims_studs_wdh']} "
        + (f"top0 {rep['top_lod0']['inset_0_25']['max_abs_dev_studs']} full {rep['top_lod0']['full_footprint_cell_centred']['within_tolerance_fraction']} "
           if not is_machine else "")
        + json.dumps(rep["checks"]))
    return rep


def main():
    assets = {pid: verify(pid) for pid in BUILDERS}
    allc = [v for a in assets.values() for v in a["checks"].values()]
    doc = {
        "task": "T03", "family": "reception",
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "blender_version": bpy.app.version_string,
        "method": "Réimport de chaque GLB/FBX dans une scène vide (Blender) ; lancers de rayons verticaux pour le dessus.",
        "criteria": {
            "envelope": "dimensions = size_studs (config/rooms.json) à ±2 % sur chaque axe (LOD0, LOD1, FBX)",
            "walkable_top": "rectangle walkable_top centré, grille 0,25, retrait 0,25 stud : aucun raté, |écart| ≤ 0,25 "
                            "au dessus du collider (size_studs[2]) ; aucune pièce > +0,05 au-dessus",
            "triangles": "props LOD0 800–3 000, machine 3 000–8 000, LOD1 ≤ 700",
            "materials": "≤ 2 par maillage",
            "axes": "1 BU = 1 stud ; glTF X largeur, Y haut (min 0), Z profondeur ; avant Roblox -Z (décision 0003)",
        },
        "summary": {"assets": len(assets), "checks": len(allc), "pass": allc.count("PASS"), "fail": allc.count("FAIL")},
        "import_status": "blocked",
        "import_blocker": "Roblox Studio / Open Cloud indisponibles : aucun MeshPart importé, roblox_asset_id = null.",
        "assets": assets,
    }
    out = os.path.join(ROOT, "reports", "T03", "props_reception_verify.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ROOT, "reports", "T03", "props_reception_verify_log.txt"), "w", encoding="utf-8") as f:
        f.write(f"# verify_props_reception.py — {doc['checked_at_utc']}\n" + "\n".join(LOG) + "\n")
    log("summary", json.dumps(doc["summary"]))


if __name__ == "__main__":
    main()
