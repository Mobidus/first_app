"""Vérifie les exports de la famille Piscine Gonflable en les ROUVRANT dans une scène vide.

Usage : .venv/bin/python -I assets/source/blender/verify_props_pool.py [--no-determinism]
Sortie : reports/T03/props_pool_verify.json (+ props_pool_verify_log.txt)

Par asset (GLB LOD0, GLB LOD1, FBX) : dimensions vs enveloppe (SPECS de build_props_pool.py, ±2 %), pivot
(origine au sol = centre du bas du collider de jeu ; décalage de la boîte englobante rapporté), triangles,
matériaux par maillage, UV et textures embarquées (couleur + metallicRoughness) ; en-tête glTF brut (axes
Roblox : X largeur, Y haut, Z profondeur) ; avant (-Z Roblox = +Y Blender) vérifié par la position moyenne des
décors frontaux ; planéité du dessus praticable par lancers de rayons verticaux sur le rectangle walkable_top
centré (grille 0,25, retrait 0,25) sur LOD0 ET LOD1 ; déterminisme : seconde construction complète dans un
dossier temporaire et comparaison des empreintes SHA-256 des GLB.
Copie autonome de verify_props_reception.py (aucun import croisé). L'import Roblox Studio n'est PAS testé.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import pool_atlas as atlas  # noqa: E402
from build_props_pool import BUILDERS, DEFLATED_ID, IMPORT_DIR, MACHINE_ID, ROOT, SPECS  # noqa: E402

TOL_TOP = 0.25
TOL_ABOVE = 0.05
TOL_ENV = 0.02
GRID = 0.25
LOG = []
FRONT_TILE = {"pool_inflatable_duck": "duck_face", "pool_flamingo_float": "eye", "pool_beach_ball": "badge_sun",
              "pool_donut_ring": "donut_face", "pool_unicorn_float": "unicorn_face", "pool_cooler": "cooler_face",
              "pool_croc_float": "croc_face", "pool_air_mattress": "valve_label", MACHINE_ID: "pump_face"}


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
    mats = js.get("materials", [])
    return {
        "magic_ok": magic == 0x46546C67 and ver == 2,
        "generator": js.get("asset", {}).get("generator"),
        "meshes": len(js.get("meshes", [])), "primitives": prims,
        "materials": [m.get("name") for m in mats],
        "images_embedded": len(js.get("images", [])),
        "images_in_buffer": all("bufferView" in im for im in js.get("images", [])),
        "node_translations": [n.get("translation", [0, 0, 0]) for n in nodes],
        "gltf_position_min_xyz": [round(float(v), 4) for v in pos_min],
        "gltf_position_max_xyz": [round(float(v), 4) for v in pos_max],
        "alpha_modes": [m.get("alphaMode", "OPAQUE") for m in mats],
        "has_base_color_texture": any("baseColorTexture" in m.get("pbrMetallicRoughness", {}) for m in mats),
        "has_metallic_roughness_texture": any("metallicRoughnessTexture" in m.get("pbrMetallicRoughness", {})
                                              for m in mats),
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
        "bbox_center_offset_xy_blender": [round(float((mn[0] + mx[0]) / 2), 4), round(float((mn[1] + mx[1]) / 2), 4)],
        "materials_per_mesh_max": max(mats_per_mesh) if mats_per_mesh else 0,
        "material_names": sorted({m.name for o in objs for m in o.data.materials if m}),
        "uv_layers": min(len(o.data.uv_layers) for o in objs) if objs else 0,
    }


def top_hit(trees, x, y):
    best = None
    for t in trees:
        h = t.ray_cast(Vector((x, y, 100.0)), Vector((0, 0, -1)))
        if h[0] is not None and (best is None or h[0].z > best):
            best = h[0].z
    return best


def flatness(objs, collider_h, walk, inset):
    dg = bpy.context.evaluated_depsgraph_get()
    trees = [BVHTree.FromObject(o, dg) for o in objs]
    w, d = walk
    xs = np.arange(-w / 2 + inset, w / 2 - inset + 1e-6, GRID)
    ys = np.arange(-d / 2 + inset, d / 2 - inset + 1e-6, GRID)
    devs, misses, worst = [], 0, None
    for x in xs:
        for y in ys:
            z = top_hit(trees, float(x), float(y))
            dv = -collider_h if z is None else z - collider_h
            misses += z is None
            devs.append(dv)
            if worst is None or abs(dv) > abs(worst[2]):
                worst = (round(float(x), 3), round(float(y), 3), round(float(dv), 4))
    devs = np.array(devs)
    return {
        "grid_studs": GRID, "inset_studs": inset, "samples": int(devs.size), "misses": misses,
        "max_abs_dev_studs": round(float(np.abs(devs).max()), 4),
        "max_above_studs": round(float(devs.max()), 4), "max_below_studs": round(float(devs.min()), 4),
        "mean_dev_studs": round(float(devs.mean()), 4),
        "worst_sample_blender_xy_dev": worst,
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
    return {"tile": tile, "found": True, "loops": len(ys), "mean_blender_y": round(m, 3), "roblox_z": round(-m, 3),
            "is_front_minus_z_roblox": m > 0}


def verify(pid):
    s = SPECS[pid]
    size = [float(v) for v in s["envelope"]]
    is_machine = pid == MACHINE_ID
    walk = s["walkable"]
    base = os.path.join(IMPORT_DIR, pid)
    rep = {"asset_id": pid, "kind": "machine" if is_machine else "prop", "behavior": s["behavior"],
           "envelope_studs_wdh": size}
    if s.get("brief_envelope"):
        rep["brief_envelope_studs_wdh"] = s["brief_envelope"]
        rep["envelope_note"] = s["envelope_note"]
    rep["gltf_header"] = glb_header(base + ".glb")
    objs, rep["glb_lod0"] = static(base + ".glb", size)
    if walk:
        h = float(s["collider"][2])
        rep["collider"] = {"size_studs_wdh": s["collider"], "walkable_top": walk, "top_height": h}
        rep["top_lod0"] = flatness(objs, h, walk, 0.25)
    if pid in FRONT_TILE:
        rep["front_axis"] = front_check(objs, FRONT_TILE[pid])
    objs1, rep["glb_lod1"] = static(base + "_lod1.glb", size)
    if walk:
        rep["top_lod1"] = flatness(objs1, h, walk, 0.25)
    _o, rep["fbx_lod0"] = static(base + ".fbx", size)

    g0, g1, fb, hd = rep["glb_lod0"], rep["glb_lod1"], rep["fbx_lod0"], rep["gltf_header"]
    lo, hi = (3000, 8000) if is_machine else (800, 3000)
    l1 = 1200 if is_machine else 700
    if walk:  # pivot = centre du bas du collider : la boîte englobante peut déborder (têtes) dans l'enveloppe
        ox, oy = g0["bbox_center_offset_xy_blender"]
        cw, cd = s["collider"][0], s["collider"][1]
        pivot_ok = (abs(g0["bbox_min"][2]) <= 0.01
                    and g0["bbox_min"][0] <= -cw / 2 + 0.01 and g0["bbox_max"][0] >= cw / 2 - 0.01
                    and g0["bbox_min"][1] <= -cd / 2 + 0.01 and g0["bbox_max"][1] >= cd / 2 - 0.01)
        rep["pivot"] = {"definition": "origine = centre du bas du collider ; collider contenu dans la boîte du maillage",
                        "mesh_bbox_center_from_pivot_roblox": [ox, round((g0["bbox_min"][2] + g0["bbox_max"][2]) / 2, 4),
                                                               round(-oy, 4)]}
    else:
        pivot_ok = abs(g0["bbox_min"][2]) <= 0.01 and max(abs(v) for v in g0["bbox_center_offset_xy_blender"]) <= 0.05
        rep["pivot"] = {"definition": "origine = centre du bas de la boîte englobante"}
    pivot_ok = pivot_ok and all(max(abs(c) for c in t) < 1e-6 for t in hd["node_translations"])
    checks = {
        "glb_reopened": g0["mesh_objects"] >= 1 and hd["magic_ok"],
        "envelope_lod0_within_2pct": all(abs(r) <= TOL_ENV for r in g0["dims_rel_error"]),
        "envelope_lod1_within_2pct": all(abs(r) <= TOL_ENV for r in g1["dims_rel_error"]),
        "envelope_fbx_within_2pct": all(abs(r) <= TOL_ENV for r in fb["dims_rel_error"]),
        "pivot_bottom_center": pivot_ok,
        "gltf_axes_x_width_y_up_z_depth": abs((hd["gltf_position_max_xyz"][0] - hd["gltf_position_min_xyz"][0]) - g0["dims_studs_wdh"][0]) < 0.01
        and abs(hd["gltf_position_min_xyz"][1]) < 0.01
        and abs((hd["gltf_position_max_xyz"][1] - hd["gltf_position_min_xyz"][1]) - g0["dims_studs_wdh"][2]) < 0.01
        and abs((hd["gltf_position_max_xyz"][2] - hd["gltf_position_min_xyz"][2]) - g0["dims_studs_wdh"][1]) < 0.01,
        f"tris_lod0_{lo}_{hi}": lo <= g0["triangles"] <= hi,
        f"tris_lod1_le_{l1}": g1["triangles"] <= l1,
        ("materials_le_2_per_mesh" if is_machine else "materials_eq_1_per_mesh"):
            (g0["materials_per_mesh_max"] <= 2 and g1["materials_per_mesh_max"] <= 2) if is_machine
            else (g0["materials_per_mesh_max"] == 1 and g1["materials_per_mesh_max"] == 1
                  and fb["materials_per_mesh_max"] == 1),
        "uv_and_embedded_textures": g0["uv_layers"] >= 1 and g1["uv_layers"] >= 1 and hd["images_embedded"] >= 2
        and hd["images_in_buffer"] and hd["has_base_color_texture"] and hd["has_metallic_roughness_texture"],
    }
    if "front_axis" in rep:
        checks["front_decals_face_minus_z_roblox"] = bool(rep["front_axis"].get("is_front_minus_z_roblox"))
    if walk:
        t0, t1 = rep["top_lod0"], rep["top_lod1"]
        checks["walkable_top_flat_lod0_le_0_25"] = t0["misses"] == 0 and t0["max_abs_dev_studs"] <= TOL_TOP
        checks["walkable_top_flat_lod1_le_0_25"] = t1["misses"] == 0 and t1["max_abs_dev_studs"] <= TOL_TOP
        checks["walkable_top_nothing_above_plus_0_05"] = (t0["max_above_studs"] <= TOL_ABOVE
                                                          and t1["max_above_studs"] <= TOL_ABOVE)
    rep["checks"] = {k: ("PASS" if v else "FAIL") for k, v in checks.items()}
    if s.get("brief_envelope"):
        b = np.array(s["brief_envelope"], dtype=float)
        rep["informational"] = {"dims_rel_error_vs_brief_envelope": [round(float(v), 4) for v in
                                                                      (np.array(g0["dims_studs_wdh"]) - b) / b],
                                "note": s["envelope_note"]}
    rep["roblox_studio_import"] = {"status": "blocked", "roblox_asset_id": None, "studio_checks": "NOT_RUN"}
    log(f"[{pid}] tris {g0['triangles']}/{g1['triangles']} dims {g0['dims_studs_wdh']} "
        + (f"top0 {rep['top_lod0']['max_abs_dev_studs']} (+{rep['top_lod0']['max_above_studs']}) "
           f"top1 {rep['top_lod1']['max_abs_dev_studs']} (+{rep['top_lod1']['max_above_studs']}) " if walk else "")
        + json.dumps(rep["checks"]))
    return rep


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def determinism():
    tmp = tempfile.mkdtemp(prefix="pool_det_")
    try:
        env = dict(os.environ, POOL_IMPORT_DIR=tmp)
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "build_props_pool.py")], env=env, cwd=ROOT,
                           capture_output=True, text=True, timeout=1200)
        files = {}
        for pid in BUILDERS:
            for suf in (".glb", "_lod1.glb"):
                a, b = os.path.join(IMPORT_DIR, pid + suf), os.path.join(tmp, pid + suf)
                ha = sha(a)
                hb = sha(b) if os.path.exists(b) else None
                files[pid + suf] = {"sha256": ha, "rebuild_sha256": hb, "identical": ha == hb}
        fbx = {pid + ".fbx": sha(os.path.join(IMPORT_DIR, pid + ".fbx")) == sha(os.path.join(tmp, pid + ".fbx"))
               for pid in BUILDERS if os.path.exists(os.path.join(tmp, pid + ".fbx"))}
        return {"method": "seconde exécution complète de build_props_pool.py (POOL_IMPORT_DIR temporaire), SHA-256",
                "rebuild_returncode": r.returncode, "glb": files,
                "all_glb_identical": r.returncode == 0 and all(v["identical"] for v in files.values()),
                "fbx_identical_informational": fbx}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def manifest_entries(assets):
    """Entrées de manifeste (mêmes clés que reception_carton dans assets/manifest.json)."""
    out = []
    for pid in BUILDERS:
        s = SPECS[pid]
        machine = pid == MACHINE_ID
        ev = [f"reports/T03/props_pool_verify.json#assets.{pid}", "reports/T03/props_pool_verify_log.txt",
              "assets/source/models/pool/build_info.json", "assets/source/models/pool/collision_pool.json",
              f"reports/T03/renders/{pid}_3q.png", f"reports/T03/renders/{pid}_silhouette.png",
              "reports/T03/renders/props_pool_sheet.png", "reports/T03/renders/props_pool_silhouettes_sheet.png",
              "reports/T03/renders/props_pool_lineup.png"]
        if machine:
            col = {"shape": "separate_architecture_proxy",
                   "note": "Décor seulement (alcôve) : aucune collision de parcours portée par le maillage."}
        elif s["collider"]:
            col = {"shape": "box", "size_studs": s["collider"], "walkable_top": s["walkable"], "top_visible": True,
                   "mesh_bbox_center_from_pivot_roblox": assets[pid]["pivot"]["mesh_bbox_center_from_pivot_roblox"]}
        else:
            col = {"shape": "none_visual_only",
                   "note": "Visuel d'effondrement de pool_air_mattress (comportement temporary) ; la collision reste "
                           "celle gérée par le comportement, pas ce maillage."}
        e = {
            "id": pid, "name": s["name"], "category": s["category"], "release_stage": "MVP", "status": "modeled",
            "roblox_asset_id": None,
            "source_path": "assets/source/models/pool/pool_props.blend",
            "export_path": f"assets/import/models/{pid}.glb",
            "additional_exports": [f"assets/import/models/{pid}_lod1.glb", f"assets/import/models/{pid}.fbx"],
            "dimensions_order": "width_depth_height",
            "size_studs": s["envelope"],
            "pivot": "bottom_center",
            "forward_axis": "-Z",
            "visual_brief": s["visual"],
            "collision": col,
            "deformation_profile": None,
            "production_method": "blender_mesh_and_optional_rig",
            "requires_external_import": True,
            "max_triangles_near": 8000 if machine else 3000,
            "max_materials": 2 if machine else 1,
            "image_export_pixels": None,
            "provenance": "generated from code in Blender, no third-party assets",
            "validation_evidence": ev,
            "design_reference_paths": [],
        }
        if s.get("brief_envelope"):
            e["brief_size_studs"] = s["brief_envelope"]
            e["size_note"] = s["envelope_note"]
        if s.get("note"):
            e["note"] = s["note"]
        out.append(e)
    return out


def main():
    assets = {pid: verify(pid) for pid in BUILDERS}
    det = None
    if "--no-determinism" not in sys.argv:
        det = determinism()
        log("determinism", "PASS" if det["all_glb_identical"] else "FAIL")
    allc = [v for a in assets.values() for v in a["checks"].values()]
    if det is not None:
        allc.append("PASS" if det["all_glb_identical"] else "FAIL")
    doc = {
        "task": "T03", "family": "pool",
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "blender_version": bpy.app.version_string,
        "method": "Réimport de chaque GLB/FBX dans une scène vide (Blender) ; lancers de rayons verticaux pour le dessus.",
        "criteria": {
            "envelope": "dimensions = enveloppe (SPECS) à ±2 % sur chaque axe (LOD0, LOD1, FBX)",
            "pivot": "origine au sol ; props : centre du bas du collider (collider contenu dans la boîte du maillage, "
                     "décalage rapporté) ; machine et variante dégonflée : centre du bas de la boîte englobante",
            "walkable_top": "rectangle walkable centré, grille 0,25, retrait 0,25 : aucun raté, |écart| ≤ 0,25 au collider, "
                            "rien au-dessus de +0,05 (LOD0 et LOD1)",
            "triangles": "props LOD0 800–3 000, LOD1 ≤ 700 ; machine LOD0 3 000–8 000, LOD1 ≤ 1 200",
            "materials": "props : 1 matériau par maillage ; machine ≤ 2",
            "textures": "UV + images embarquées dans le GLB (couleur de base + metallicRoughness)",
            "front": "décor frontal (tuile d'atlas réservée) en moyenne côté +Y Blender = -Z Roblox",
            "determinism": "seconde construction complète : empreintes SHA-256 identiques de tous les GLB",
            "axes": "1 BU = 1 stud ; glTF X largeur, Y haut (min 0), Z profondeur ; avant Roblox -Z (décision 0003)",
        },
        "summary": {"assets": len(assets), "checks": len(allc), "pass": allc.count("PASS"), "fail": allc.count("FAIL")},
        "determinism": det if det is not None else "NOT_RUN",
        "import_status": "blocked",
        "import_blocker": "Roblox Studio / Open Cloud indisponibles : aucun MeshPart importé, roblox_asset_id = null.",
        "assets": assets,
    }
    out = os.path.join(ROOT, "reports", "T03", "props_pool_verify.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ROOT, "reports", "T03", "props_pool_verify_log.txt"), "w", encoding="utf-8") as f:
        f.write(f"# verify_props_pool.py — {doc['checked_at_utc']}\n" + "\n".join(LOG) + "\n")
    man = {"task": "T03", "batch": "pool", "new_assets": manifest_entries(assets)}
    with open(os.path.join(ROOT, "reports", "T03", "manifest_new_pool.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    log("summary", json.dumps(doc["summary"]))


if __name__ == "__main__":
    main()
