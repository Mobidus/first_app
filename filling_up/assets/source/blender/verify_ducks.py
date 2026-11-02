"""Vérifie les exports des canards gonflables en les ROUVRANT dans une scène vide.

Usage : .venv/bin/python -I assets/source/blender/verify_ducks.py [--no-determinism]
Sorties : reports/T03/ducks_verify.json (+ ducks_verify_log.txt)

Par variante (GLB LOD0, GLB LOD1, FBX) :
  * dimensions vs enveloppe (duck_kit.FORMS, ±2 %) ; pivot bottom_center ; en-tête glTF brut (axes Roblox
    X largeur, Y haut, Z profondeur) ; un seul matériau ; UV + texture embarquée (+ carte metallicRoughness) ;
    budgets de triangles par forme ;
  * dessus praticable : lancers de rayons verticaux sur le rectangle praticable centré (grille 0,25, retrait
    0,25 stud), comparés à la hauteur du collider : |écart| ≤ 0,25 et rien au-dessus de +0,05 (LOD0 et LOD1) ;
  * tête et accessoires à l'avant : AUCUN sommet plus haut que dessus + 0,05 dans le rectangle échantillonné
    (contrôle exhaustif, pas seulement la grille) ; la tête (tuile « face » de l'atlas) est dans la bande avant
    (-Z Roblox), ou au bout +X pour le matelas (voir rapport) ; répartition des sommets hors-dessus par zone ;
  * déterminisme : seconde construction complète dans un dossier temporaire -> empreintes SHA-256 des GLB.
L'import Roblox Studio n'est PAS testé ici (ni Studio ni Open Cloud dans le conteneur).
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

import duck_atlas as atlas  # noqa: E402
import duck_kit as K  # noqa: E402
from build_ducks import BUDGETS, ROOT, VARIANTS, form_of  # noqa: E402

IMPORT_DIR = os.path.join(ROOT, "assets", "import", "models")
TOL_TOP = 0.25
TOL_ABOVE = 0.05
TOL_ENV = 0.02
GRID = 0.25
INSET = 0.25
LOG = []


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
        "images_in_buffer": all("bufferView" in im for im in js.get("images", [])),
        "node_translations": [n.get("translation", [0, 0, 0]) for n in nodes],
        "gltf_position_min_xyz": [round(float(v), 4) for v in pos_min],
        "gltf_position_max_xyz": [round(float(v), 4) for v in pos_max],
        "has_base_color_texture": any("baseColorTexture" in m.get("pbrMetallicRoughness", {}) for m in js.get("materials", [])),
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


def top_hit(trees, x, y):
    best = None
    for t in trees:
        h = t.ray_cast(Vector((x, y, 100.0)), Vector((0, 0, -1)))
        if h[0] is not None and (best is None or h[0].z > best):
            best = h[0].z
    return best


def flatness(objs, collider_h, walk, inset, cell_centred=False):
    dg = bpy.context.evaluated_depsgraph_get()
    trees = [BVHTree.FromObject(o, dg) for o in objs]
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


def above_deck_audit(objs, T, walk, head_axis):
    """Tous les sommets au-dessus de T + 0,05 : aucun dans le rectangle échantillonné ; répartition par zone."""
    co = world_coords(objs)
    w, d = walk
    hi = co[co[:, 2] > T + TOL_ABOVE]
    in_sampled = (np.abs(hi[:, 0]) <= w / 2 - INSET) & (np.abs(hi[:, 1]) <= d / 2 - INSET)
    in_rect = (np.abs(hi[:, 0]) < w / 2) & (np.abs(hi[:, 1]) < d / 2)
    if head_axis == "y":
        front = hi[:, 1] > d / 2 - INSET
        back = hi[:, 1] < -(d / 2 - INSET)
    else:
        front = hi[:, 0] > w / 2 - INSET
        back = hi[:, 0] < -(w / 2 - INSET)
    side = ~front & ~back
    # pénétration maximale dans le rectangle complet (marge non échantillonnée de 0,25)
    if in_rect.any():
        pen = np.minimum(w / 2 - np.abs(hi[in_rect, 0]), d / 2 - np.abs(hi[in_rect, 1])).max()
    else:
        pen = 0.0
    return {
        "vertices_above_top_plus_0_05": int(len(hi)),
        "in_sampled_rect": int(in_sampled.sum()),
        "in_full_rect_margin": int(in_rect.sum()),
        "max_penetration_into_full_rect_studs": round(float(pen), 4),
        "front_band": int(front.sum()), "back_band_tail": int(back.sum()), "side_bands": int(side.sum()),
        "front_fraction": round(float(front.sum() / max(len(hi), 1)), 4),
    }


def face_position(objs):
    """Position moyenne des sommets dont l'UV tombe dans la tuile « face » (visage de la tête)."""
    u0, v0, u1, v1 = atlas.tile_uv("face", 0.0)
    pts = []
    for o in objs:
        uv = o.data.uv_layers.active.data
        for p in o.data.polygons:
            for li in p.loop_indices:
                u, v = uv[li].uv
                if u0 <= u <= u1 and v0 <= v <= v1:
                    pts.append(tuple(o.matrix_world @ o.data.vertices[o.data.loops[li].vertex_index].co))
    if not pts:
        return None
    a = np.array(pts)
    return {"mean_blender_xyz": [round(float(v), 3) for v in a.mean(axis=0)], "n": len(pts)}


def verify(vid):
    form = form_of(vid)
    P = K.FORMS[form]
    size = [float(v) for v in P["envelope"]]
    cw, cd, T = (float(v) for v in P["collider"])
    walk = [float(v) for v in P["walkable"]]
    head_axis = "x" if form == "lilo" else "y"
    lo, hi, l1 = BUDGETS[form]
    base = os.path.join(IMPORT_DIR, vid)
    rep = {"asset_id": vid, "duck_form": form, "accessories": VARIANTS[vid]["acc"], "size_studs_wdh": size,
           "collider": {"size_studs_wdh": [cw, cd, T], "walkable_top": walk, "top_height": T},
           "head_end": "+X (Roblox +X, bout du matelas)" if head_axis == "x" else "-Z Roblox (+Y Blender)"}
    rep["gltf_header"] = glb_header(base + ".glb")
    rep["gltf_header_lod1"] = glb_header(base + "_lod1.glb")
    objs, rep["glb_lod0"] = static(base + ".glb", size)
    rep["top_lod0"] = {"inset_0_25": flatness(objs, T, walk, INSET),
                       "full_footprint_cell_centred": flatness(objs, T, walk, 0, cell_centred=True)}
    rep["above_deck_lod0"] = above_deck_audit(objs, T, walk, head_axis)
    rep["face_lod0"] = face_position(objs)
    objs1, rep["glb_lod1"] = static(base + "_lod1.glb", size)
    rep["top_lod1"] = {"inset_0_25": flatness(objs1, T, walk, INSET),
                       "full_footprint_cell_centred": flatness(objs1, T, walk, 0, cell_centred=True)}
    rep["above_deck_lod1"] = above_deck_audit(objs1, T, walk, head_axis)
    rep["face_lod1"] = face_position(objs1)
    _o, rep["fbx_lod0"] = static(base + ".fbx", size)

    g0, g1, fb, hd = rep["glb_lod0"], rep["glb_lod1"], rep["fbx_lod0"], rep["gltf_header"]
    t0, t1 = rep["top_lod0"]["inset_0_25"], rep["top_lod1"]["inset_0_25"]
    a0, a1 = rep["above_deck_lod0"], rep["above_deck_lod1"]

    def face_front(f):
        if f is None:
            return False
        x, y, _z = f["mean_blender_xyz"]
        return (y > cd / 2 - INSET) if head_axis == "y" else (x > cw / 2 - INSET)

    checks = {
        "glb_reopened": g0["mesh_objects"] == 1 and hd["magic_ok"] and g1["mesh_objects"] == 1,
        "envelope_lod0_within_2pct": all(abs(r) <= TOL_ENV for r in g0["dims_rel_error"]),
        "envelope_lod1_within_2pct": all(abs(r) <= TOL_ENV for r in g1["dims_rel_error"]),
        "envelope_fbx_within_2pct": all(abs(r) <= TOL_ENV for r in fb["dims_rel_error"]),
        "pivot_bottom_center": abs(g0["bbox_min"][2]) <= 0.01 and max(abs(v) for v in g0["pivot_offset_xy"]) <= 0.05
        and abs(g1["bbox_min"][2]) <= 0.01 and max(abs(v) for v in g1["pivot_offset_xy"]) <= 0.05
        and all(max(abs(c) for c in t) < 1e-6 for t in hd["node_translations"]),
        "gltf_axes_x_width_y_up_z_depth": abs((hd["gltf_position_max_xyz"][0] - hd["gltf_position_min_xyz"][0]) - g0["dims_studs_wdh"][0]) < 0.01
        and abs(hd["gltf_position_min_xyz"][1]) < 0.01
        and abs((hd["gltf_position_max_xyz"][1] - hd["gltf_position_min_xyz"][1]) - g0["dims_studs_wdh"][2]) < 0.01
        and abs((hd["gltf_position_max_xyz"][2] - hd["gltf_position_min_xyz"][2]) - g0["dims_studs_wdh"][1]) < 0.01,
        "head_front_gltf_minus_z" if head_axis == "y" else "head_end_gltf_plus_x":
            (rep["face_lod0"] is not None and face_front(rep["face_lod0"]) and face_front(rep["face_lod1"])),
        "above_deck_only_head_band_or_tail_band": a0["side_bands"] == 0 and a1["side_bands"] == 0,
        f"tris_lod0_{lo}_{hi}": lo <= g0["triangles"] <= hi,
        f"tris_lod1_le_{l1}": g1["triangles"] <= l1,
        "one_material_per_mesh": g0["materials_per_mesh_max"] == 1 and g1["materials_per_mesh_max"] == 1
        and fb["materials_per_mesh_max"] == 1 and len(hd["materials"]) == 1,
        "uv_and_embedded_textures": g0["uv_layers"] >= 1 and g1["uv_layers"] >= 1 and hd["images_embedded"] >= 2
        and hd["images_in_buffer"] and hd["has_base_color_texture"] and hd["has_metallic_roughness_texture"]
        and rep["gltf_header_lod1"]["images_embedded"] >= 2,
        "walkable_top_flat_lod0_le_0_25": t0["misses"] == 0 and t0["max_abs_dev_studs"] <= TOL_TOP,
        "walkable_top_flat_lod1_le_0_25": t1["misses"] == 0 and t1["max_abs_dev_studs"] <= TOL_TOP,
        "nothing_above_top_plus_0_05_rays": t0["max_above_studs"] <= TOL_ABOVE and t1["max_above_studs"] <= TOL_ABOVE,
        "no_vertex_above_top_in_sampled_rect": a0["in_sampled_rect"] == 0 and a1["in_sampled_rect"] == 0,
    }
    rep["checks"] = {k: ("PASS" if v else "FAIL") for k, v in checks.items()}
    rep["informational"] = {
        "full_footprint_note": "Échantillons centrés (grille 0,25 jusqu'à 0,125 du bord) : inclut l'arrondi du rebord "
                               "gonflé ; reporté, non bloquant.",
        "head_margin_note": "Le dos de la tête est placé 0,12 stud à l'intérieur du bord du rectangle praticable "
                            "(dans la marge non échantillonnée de 0,25) ; voir max_penetration_into_full_rect_studs.",
        "fbx_triangles": fb["triangles"],
    }
    rep["roblox_studio_import"] = {"status": "blocked", "roblox_asset_id": None, "studio_checks": "NOT_RUN"}
    log(f"[{vid}] tris {g0['triangles']}/{g1['triangles']} dims {g0['dims_studs_wdh']} top0 {t0['max_abs_dev_studs']} "
        f"(+{t0['max_above_studs']}) top1 {t1['max_abs_dev_studs']} (+{t1['max_above_studs']}) "
        f"pen {a0['max_penetration_into_full_rect_studs']} front {a0['front_fraction']} " + json.dumps(rep["checks"]))
    return rep


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def determinism():
    tmp = tempfile.mkdtemp(prefix="ducks_determinism_")
    try:
        cmd = [sys.executable, "-I", os.path.join(HERE, "build_ducks.py"), "--out-root", tmp]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
        res = {"command": " ".join([".venv/bin/python", "-I", "assets/source/blender/build_ducks.py", "--out-root", "<tmp>"]),
               "returncode": r.returncode, "files": {}}
        same = r.returncode == 0
        for vid in VARIANTS:
            for suf in (".glb", "_lod1.glb"):
                a = os.path.join(IMPORT_DIR, vid + suf)
                b = os.path.join(tmp, "assets", "import", "models", vid + suf)
                ha, hb = sha(a), (sha(b) if os.path.exists(b) else None)
                res["files"][vid + suf] = {"sha256_build1": ha, "sha256_build2": hb, "identical": ha == hb}
                same = same and ha == hb
        for name in ("duck_atlas_1024.png", "duck_atlas_rough_1024.png"):
            a = os.path.join(ROOT, "assets", "source", "models", "ducks", "textures", name)
            b = os.path.join(tmp, "assets", "source", "models", "ducks", "textures", name)
            ha, hb = sha(a), (sha(b) if os.path.exists(b) else None)
            res["files"][name] = {"sha256_build1": ha, "sha256_build2": hb, "identical": ha == hb}
            same = same and ha == hb
        res["all_identical"] = same
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    assets = {vid: verify(vid) for vid in VARIANTS}
    det = None
    if "--no-determinism" not in sys.argv:
        log("determinism: second full build ...")
        det = determinism()
        log("determinism all_identical:", det["all_identical"])
        for vid in VARIANTS:
            ok = det["files"][vid + ".glb"]["identical"] and det["files"][vid + "_lod1.glb"]["identical"]
            assets[vid]["checks"]["determinism_glb_hashes_identical"] = "PASS" if ok else "FAIL"
    allc = [v for a in assets.values() for v in a["checks"].values()]
    doc = {
        "task": "T03", "batch": "ducks",
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "blender_version": bpy.app.version_string,
        "method": "Réimport de chaque GLB/FBX dans une scène vide (Blender) ; lancers de rayons verticaux pour le dessus ; "
                  "audit exhaustif des sommets au-dessus du dessus ; seconde construction complète pour le déterminisme.",
        "criteria": {
            "envelope": "dimensions = enveloppe de la forme à ±2 % sur chaque axe (LOD0, LOD1, FBX)",
            "walkable_top": "rectangle praticable centré, grille 0,25, retrait 0,25 : aucun raté, |écart| ≤ 0,25 au "
                            "dessus du collider ; rien > +0,05 (rayons ET sommets)",
            "front": "tuile visage dans la bande avant (-Z Roblox ; matelas : bout +X) ; tout sommet plus haut que le "
                     "dessus + 0,05 est dans la bande de la tête ou dans celle de la queue (aucun sur les côtés, aucun "
                     "dans le rectangle échantillonné)",
            "triangles": {f: {"lod0": [b[0], b[1]], "lod1_max": b[2]} for f, b in BUDGETS.items()},
            "materials": "1 par maillage ; textures (couleur + metallicRoughness) embarquées dans le GLB",
            "axes": "1 BU = 1 stud ; glTF X largeur, Y haut (min 0), Z profondeur ; avant Roblox -Z (décision 0003)",
        },
        "summary": {"assets": len(assets), "checks": len(allc), "pass": allc.count("PASS"), "fail": allc.count("FAIL")},
        "determinism": det,
        "import_status": "blocked",
        "import_blocker": "Roblox Studio / Open Cloud indisponibles : aucun MeshPart importé, roblox_asset_id = null.",
        "assets": assets,
    }
    out = os.path.join(ROOT, "reports", "T03", "ducks_verify.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ROOT, "reports", "T03", "ducks_verify_log.txt"), "w", encoding="utf-8") as f:
        f.write(f"# verify_ducks.py — {doc['checked_at_utc']}\n" + "\n".join(LOG) + "\n")
    log("summary", json.dumps(doc["summary"]))


if __name__ == "__main__":
    main()
