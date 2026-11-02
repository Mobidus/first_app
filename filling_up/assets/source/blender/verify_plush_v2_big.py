"""Vérifie les exports des grandes peluches v2 en les ROUVRANT dans une scène vide (Blender headless).

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/verify_plush_v2_big.py [balto|ronron|bobine|all] [--skip-rebuild]

Mesures par peluche (rien n'est déclaré PASS sans avoir été mesuré ; une mesure impossible = NOT_RUN) :
- GLB, GLB LOD1, FBX réimportés : dimensions vs enveloppe (+-2 %), pivot (centre de l'empreinte au sol),
  triangles vs budget, 1 matériau, UV, texture embarquée (et sa taille), armature (Root + 9 Belly + secondaires
  listés), poids (somme = 1, <= 4 influences, aucun sommet orphelin) ;
- axes Roblox lus DANS LE GLB BRUT (accesseurs POSITION/JOINTS_0/WEIGHTS_0) : X = largeur, Y = haut (min 0),
  Z = profondeur, avant = -Z (les sommets dominés par le bone Head ont un Z moyen négatif) ;
- dessus praticable : rayons verticaux tous les 0,25 stud sur le rectangle praticable rentré de 0,25 stud :
  max |dessus visible - dessus collider| <= 0,25 et rien au-dessus de dessus + 0,05 (LOD0 et LOD1) ;
- poses de pose_library.json (relues en espace Roblox, reconverties) appliquées au rig réimporté : boîte
  englobante <= 1,10 x enveloppe, rapports de config/runtime.json (étirement, compression, élargissement),
  jamais sous le sol, aucune échelle de bone, dérive nulle après 50 cycles ;
- déterminisme : reconstruction complète dans un dossier temporaire (sous-processus) puis comparaison des
  SHA-256 des GLB / PNG avec ceux du build officiel (et contrôle que les fichiers sur disque sont ceux du build).

Sorties : reports/T03/plush_v2_big_verify.json et reports/T03/plush_v2_big_verify_log.txt.
L'import Roblox Studio n'est PAS testé ici (aucun Studio dans le conteneur) : NOT_RUN.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import plush_v2_big_specs as specs  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def rel(p):
    return os.path.relpath(p, ROOT)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def runtime_limits():
    with open(os.path.join(ROOT, "config", "runtime.json"), encoding="utf-8") as f:
        return json.load(f)["deformation"]


# ---------------------------------------------------------------------------
# Lecture brute d'un GLB
# ---------------------------------------------------------------------------
def read_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, ver, length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and ver == 2
    off = 12
    js, binc = None, None
    while off < length:
        clen, ctype = struct.unpack_from("<I4s", data, off)
        chunk = data[off + 8:off + 8 + clen]
        if ctype == b"JSON":
            js = json.loads(chunk.decode("utf-8"))
        elif ctype == b"BIN\x00":
            binc = chunk
        off += 8 + clen
    return js, binc


def accessor(js, binc, idx):
    acc = js["accessors"][idx]
    bv = js["bufferViews"][acc["bufferView"]]
    comp = {5126: np.float32, 5121: np.uint8, 5123: np.uint16, 5125: np.uint32}[acc["componentType"]]
    ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    item = np.dtype(comp).itemsize * ncomp
    stride = bv.get("byteStride", item)
    raw = np.frombuffer(binc, dtype=np.uint8, count=stride * (acc["count"] - 1) + item, offset=start)
    rows = np.lib.stride_tricks.as_strided(raw, shape=(acc["count"], item), strides=(stride, 1))
    arr = np.ascontiguousarray(rows).view(comp).reshape(acc["count"], ncomp)
    if acc.get("normalized") and comp != np.float32:
        arr = arr.astype(np.float64) / np.iinfo(comp).max
    return arr


def glb_raw_checks(path, pl):
    js, binc = read_glb(path)
    out = {}
    prims = [p for m in js["meshes"] for p in m["primitives"]]
    out["meshes"] = len(js["meshes"])
    out["primitives"] = len(prims)
    out["materials"] = len(js.get("materials", []))
    pr = prims[0]
    pos = accessor(js, binc, pr["attributes"]["POSITION"]).astype(np.float64)
    mn, mx = pos.min(axis=0), pos.max(axis=0)
    out["position_min_xyz"] = [round(float(v), 3) for v in mn]
    out["position_max_xyz"] = [round(float(v), 3) for v in mx]
    out["extent_xyz"] = [round(float(v), 3) for v in (mx - mn)]
    out["has_texcoord"] = "TEXCOORD_0" in pr["attributes"]
    imgs = js.get("images", [])
    out["images"] = len(imgs)
    out["images_embedded"] = all("bufferView" in im for im in imgs) and len(imgs) > 0
    if imgs and "bufferView" in imgs[0]:
        bv = js["bufferViews"][imgs[0]["bufferView"]]
        b = binc[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
        out["image_mime"] = imgs[0].get("mimeType")
        if b[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", b[16:24])
            out["image_size_px"] = [int(w), int(h)]
    # avant = -Z : sommets dominés par le joint Head
    skin = js["skins"][0]
    names = [js["nodes"][j]["name"] for j in skin["joints"]]
    out["joint_names"] = names
    J = accessor(js, binc, pr["attributes"]["JOINTS_0"]).astype(int)
    Wt = accessor(js, binc, pr["attributes"]["WEIGHTS_0"]).astype(np.float64)
    dom = J[np.arange(len(J)), np.argmax(Wt, axis=1)]
    out["weights_sum_max_error_raw"] = float(np.abs(Wt.sum(axis=1) - 1).max())
    if "Head" in names:
        hv = dom == names.index("Head")
        out["head_dominated_vertices"] = int(hv.sum())
        out["head_centroid_xyz"] = [round(float(v), 3) for v in pos[hv].mean(axis=0)] if hv.any() else None
    return out


# ---------------------------------------------------------------------------
# Réimport Blender
# ---------------------------------------------------------------------------
def import_file(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.endswith(".glb"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    # le réimport glTF ajoute une forme de bone (« Icosphere ») dans la collection glTF_not_exported : ignorée
    meshes = sorted([o for o in bpy.data.objects if o.type == "MESH" and o.users_collection
                     and not any(c.name == "glTF_not_exported" for c in o.users_collection)],
                    key=lambda o: (any(m.type == "ARMATURE" for m in o.modifiers), len(o.data.vertices)), reverse=True)
    return arms, meshes


def world_verts(obj, evaluated=True):
    dg = bpy.context.evaluated_depsgraph_get()
    ob = obj.evaluated_get(dg) if evaluated else obj
    me = ob.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    nr = np.empty(n * 3)
    me.vertices.foreach_get("normal", nr)
    ob.to_mesh_clear()
    M = np.array(obj.matrix_world)
    co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    nr = nr.reshape(-1, 3) @ M[:3, :3].T
    nr /= np.linalg.norm(nr, axis=1, keepdims=True) + 1e-12
    return co, nr


def blender_from_roblox(v):
    return (float(v[0]), float(-v[2]), float(v[1]))


def load_rect(model_dir):
    with open(os.path.join(model_dir, "collision.json"), encoding="utf-8") as f:
        col = json.load(f)
    c = blender_from_roblox(col["walkable_top"]["center_roblox"])
    w, d = col["walkable_top"]["size_studs"]
    return {"cx": c[0], "cy": c[1], "top": col["walkable_top"]["height_studs"], "w": w, "d": d, "collision": col}


def static_checks(path, pl):
    arms, meshes = import_file(path)
    res = {"file": rel(path), "opened": bool(meshes)}
    if not meshes:
        return res, None, None
    mesh = meshes[0]
    co, _ = world_verts(mesh, evaluated=False)
    mn, mx = co.min(axis=0), co.max(axis=0)
    size = mx - mn
    res["bbox_studs_width_depth_height"] = [round(float(v), 3) for v in size]
    res["bbox_center_xy"] = [round(float(0.5 * (mn[0] + mx[0])), 4), round(float(0.5 * (mn[1] + mx[1])), 4)]
    res["bbox_min_z"] = round(float(mn[2]), 4)
    res["envelope_studs"] = pl.envelope
    res["size_rel_error"] = [round(float(abs(a - e) / e), 4) for a, e in zip(size, pl.envelope)]
    res["triangles"] = int(sum(len(p.vertices) - 2 for p in mesh.data.polygons))
    res["mesh_objects"] = len(meshes)
    res["materials"] = len([m for m in mesh.data.materials if m])
    res["uv_layers"] = len(mesh.data.uv_layers)
    texs = []
    for m in mesh.data.materials:
        if m and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    texs.append({"name": n.image.name, "size": list(n.image.size),
                                 "packed_or_embedded": bool(n.image.packed_file) or path.endswith(".glb")})
    res["textures"] = texs
    if arms:
        arm = arms[0]
        names = [b.name for b in arm.data.bones]
        res["bones"] = names
        res["root_present"] = "Root" in names
        res["belly_bones"] = sorted(n for n in names if n.startswith("Belly_"))
        res["secondary_bones"] = sorted(n for n in names if n != "Root" and not n.startswith("Belly_"))
        res["skin_modifier"] = any(m.type == "ARMATURE" for m in mesh.modifiers)
        gid = {g.index: g.name for g in mesh.vertex_groups}
        sums, infl, orphan = [], [], 0
        head_pts = []
        for v in mesh.data.vertices:
            ws = [(gid[g.group], g.weight) for g in v.groups if g.group in gid and g.weight > 0]
            if not ws:
                orphan += 1
            sums.append(sum(w for _, w in ws))
            infl.append(len(ws))
            if ws and max(ws, key=lambda t: t[1])[0] == "Head":
                head_pts.append(v.co[:])
        res["weight_sum_max_error"] = float(max(abs(s - 1) for s in sums))
        res["max_influences"] = int(max(infl))
        res["unweighted_vertices"] = orphan
        if head_pts:
            hp = np.array(head_pts) @ np.array(mesh.matrix_world)[:3, :3].T + np.array(mesh.matrix_world)[:3, 3]
            res["head_centroid_blender_xyz"] = [round(float(v), 3) for v in hp.mean(axis=0)]
        return res, arm, mesh
    return res, None, mesh


def top_profile(mesh, rect, inset=0.25, step=0.25):
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(mesh, dg)
    xs = np.arange(rect["cx"] - rect["w"] / 2 + inset, rect["cx"] + rect["w"] / 2 - inset + 1e-6, step)
    ys = np.arange(rect["cy"] - rect["d"] / 2 + inset, rect["cy"] + rect["d"] / 2 - inset + 1e-6, step)
    devs, misses = [], 0
    for x in xs:
        for y in ys:
            hit = bvh.ray_cast(Vector((float(x), float(y), 60.0)), Vector((0, 0, -1)))
            if hit[0] is None:
                misses += 1
                continue
            devs.append(hit[0].z - rect["top"])
    devs = np.array(devs)
    return {
        "inset_studs": inset, "step_studs": step, "samples": int(len(xs) * len(ys)), "misses": misses,
        "max_abs_dev_studs": round(float(np.max(np.abs(devs))), 4),
        "mean_dev_studs": round(float(np.mean(devs)), 4),
        "max_above_studs": round(float(devs.max()), 4),
        "max_below_studs": round(float(devs.min()), 4),
        "within_0_25_fraction": round(float(np.mean(np.abs(devs) <= 0.25)), 4),
    }


def pose_lib_to_blender(lib):
    poses = {}
    for pname, pose in lib["poses"].items():
        out = {}
        for b, e in pose.items():
            sp = {}
            if "translation" in e:
                sp["t"] = blender_from_roblox(e["translation"])
            if "rotation_axis" in e:
                sp["r"] = (blender_from_roblox(e["rotation_axis"]), float(e["rotation_degrees"]))
            out[b] = sp
        poses[pname] = out
    return poses


def set_pose(arm, pose, scale=1.0):
    W = arm.matrix_world
    Winv3 = W.inverted().to_3x3()
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for bname, sp in pose.items():
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


def body_mask(mesh, secondary):
    gid = {g.index: g.name for g in mesh.vertex_groups}
    sec = np.zeros(len(mesh.data.vertices))
    for v in mesh.data.vertices:
        sec[v.index] = sum(g.weight for g in v.groups if gid.get(g.group) in secondary)
    return sec < 0.05


def mean_top(mesh, rect, inset=1.0):
    """Hauteur moyenne du dessus (rayons verticaux tous les 0,5 stud, rectangle rentré de inset)."""
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(mesh, dg)
    zs = []
    for x in np.arange(rect["cx"] - rect["w"] / 2 + inset, rect["cx"] + rect["w"] / 2 - inset + 1e-6, 0.5):
        for y in np.arange(rect["cy"] - rect["d"] / 2 + inset, rect["cy"] + rect["d"] / 2 - inset + 1e-6, 0.5):
            hit = bvh.ray_cast(Vector((float(x), float(y), 60.0)), Vector((0, 0, -1)))
            if hit[0] is not None:
                zs.append(hit[0].z)
    return float(np.mean(zs))


def pose_checks(arm, mesh, pl, rect, poses, lim):
    P0, N0 = world_verts(mesh)
    body = body_mask(mesh, set(pl.secondary.keys()))
    top_rest = mean_top(mesh, rect)
    wx, wy = np.ptp(P0[body, 0]), np.ptp(P0[body, 1])
    out = {}
    for pname, pose in poses.items():
        set_pose(arm, pose)
        P, _ = world_verts(mesh)
        size = P.max(axis=0) - P.min(axis=0)
        out[pname] = {
            "bbox_studs": [round(float(v), 3) for v in size],
            "bbox_over_envelope": [round(float(a / e), 4) for a, e in zip(size, pl.envelope)],
            "body_top_height_ratio": round(mean_top(mesh, rect) / top_rest, 4),
            "body_width_ratio": round(float(np.ptp(P[body, 0]) / wx), 4),
            "body_depth_ratio": round(float(np.ptp(P[body, 1]) / wy), 4),
            "min_z": round(float(P[:, 2].min()), 4),
        }
    set_pose(arm, {})
    # dérive : impacts d'intensité aléatoire (graine fixe) puis retour à la référence
    rnd = random.Random(specs.SEED)
    worst = 0.0
    for _ in range(50):
        set_pose(arm, poses["impact"], scale=rnd.uniform(0.2, 1.0))
        set_pose(arm, {})
        P, _ = world_verts(mesh)
        worst = max(worst, float(np.abs(P - P0).max()))
    out["_drift_after_50_cycles_studs"] = worst
    out["_top_rest_mean_height_studs"] = round(top_rest, 4)
    return out


# ---------------------------------------------------------------------------
def rebuild_hashes(key, tmp):
    cmd = [sys.executable, "-I", os.path.join(HERE, "build_plush_v2_big.py"), key, "--out-root", tmp]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        return None, r.stderr[-2000:]
    pl = specs.PLUSHES[key]()
    with open(os.path.join(tmp, "assets", "source", "models", "plush_v2", specs.MODEL_DIRS[key], "build_info.json"),
              encoding="utf-8") as f:
        return json.load(f)["sha256"], None


def verify(key, skip_rebuild=False):
    pl = specs.PLUSHES[key]()
    lim = runtime_limits()
    model_dir = os.path.join(ROOT, "assets", "source", "models", "plush_v2", specs.MODEL_DIRS[key])
    with open(os.path.join(model_dir, "build_info.json"), encoding="utf-8") as f:
        info = json.load(f)
    with open(os.path.join(model_dir, "pose_library.json"), encoding="utf-8") as f:
        lib = json.load(f)
    rect = load_rect(model_dir)
    base = os.path.join(ROOT, "assets", "import", "models", pl.asset_id)
    files = {"glb": base + ".glb", "glb_lod1": base + "_lod1.glb", "fbx": base + ".fbx"}
    rep = {"asset_id": pl.asset_id, "name": pl.name_fr, "size_tier": pl.size_tier,
           "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "blender_version": bpy.app.version_string,
           "envelope_studs": pl.envelope, "collider_studs": pl.collider_size, "walkable_rect_blender": rect["collision"]["walkable_top"],
           "files": {}, "raw_glb": {}}
    rects = {}
    for k, p in files.items():
        st, arm, mesh = static_checks(p, pl)
        rep["files"][k] = st
        if k in ("glb", "glb_lod1") and mesh is not None:
            rects[k] = {"inset_0_25": top_profile(mesh, rect, 0.25)}
            if k == "glb":
                rects[k]["inset_0_0"] = top_profile(mesh, rect, 0.0)
        log(f"[{pl.asset_id}] {k}: " + json.dumps({kk: vv for kk, vv in st.items() if kk not in ("bones",)}, ensure_ascii=False))
    for k in ("glb", "glb_lod1"):
        rep["raw_glb"][k] = glb_raw_checks(files[k], pl)
        log(f"[{pl.asset_id}] raw {k}: " + json.dumps({kk: vv for kk, vv in rep['raw_glb'][k].items() if kk != 'joint_names'}))
    rep["top_alignment_rest"] = rects
    log(f"[{pl.asset_id}] top: " + json.dumps(rects))

    poses = pose_lib_to_blender(lib)
    arms, meshes = import_file(files["glb"])
    rep["poses"] = pose_checks(arms[0], meshes[0], pl, rect, poses, lim)
    set_pose(arms[0], poses["player_landing"])
    rep["top_alignment_player_landing"] = top_profile(meshes[0], rect, 0.25)
    set_pose(arms[0], {})
    log(f"[{pl.asset_id}] poses: " + json.dumps(rep["poses"]))

    # déterminisme
    disk = {k: sha256(os.path.join(ROOT, k)) for k in info["sha256"]}
    rep["determinism"] = {"build_info_hashes_match_files_on_disk": {k: disk[k] == v for k, v in info["sha256"].items()}}
    if skip_rebuild:
        rep["determinism"]["rebuild"] = "NOT_RUN (--skip-rebuild)"
    else:
        tmp = tempfile.mkdtemp(prefix="plush_v2_big_rebuild_")
        try:
            h2, err = rebuild_hashes(key, tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if h2 is None:
            rep["determinism"]["rebuild"] = {"error": err}
        else:
            rep["determinism"]["rebuild"] = {k: {"official": info["sha256"][k][:16], "rebuild": h2.get(k, "")[:16],
                                                 "equal": h2.get(k) == info["sha256"][k]} for k in info["sha256"]}
    log(f"[{pl.asset_id}] determinism: " + json.dumps(rep["determinism"]))

    g, g1, fb = rep["files"]["glb"], rep["files"]["glb_lod1"], rep["files"]["fbx"]
    rg, rg1 = rep["raw_glb"]["glb"], rep["raw_glb"]["glb_lod1"]
    W, D, Hh = pl.envelope
    expected_bones = sorted(["Root"] + pl.belly_bone_names() + list(pl.secondary.keys()))
    pr = {k: v for k, v in rep["poses"].items() if not k.startswith("_")}
    t0 = rects.get("glb", {}).get("inset_0_25")
    t1 = rects.get("glb_lod1", {}).get("inset_0_25")
    det = rep["determinism"]["rebuild"]

    def status(v):
        if v is None:
            return "NOT_RUN"
        return "PASS" if v else "FAIL"

    checks = {}
    for k, st in (("glb", g), ("glb_lod1", g1), ("fbx", fb)):
        checks[f"dims_within_envelope_2pct_{k}"] = all(e <= 0.02 for e in st["size_rel_error"])
        # pivot = origine au centre de l'empreinte de la boîte englobante, au sol : tolérance 0,5 % de la dimension
        # (le LOD1 décimé décale ses extrêmes de quelques centièmes sans changer d'origine)
        checks[f"pivot_bottom_center_{k}"] = (abs(st["bbox_center_xy"][0]) <= 0.005 * W and abs(st["bbox_center_xy"][1]) <= 0.005 * D
                                             and abs(st["bbox_min_z"]) <= 0.01)
        checks[f"one_material_{k}"] = st["materials"] == 1 and st["mesh_objects"] == 1
        checks[f"uv_present_{k}"] = st["uv_layers"] >= 1
        checks[f"texture_present_{k}"] = len(st["textures"]) == 1 and st["textures"][0]["packed_or_embedded"]
        checks[f"bones_exact_root_9belly_secondary_{k}"] = sorted(st.get("bones", [])) == expected_bones
        checks[f"weights_sum_1_{k}"] = st.get("weight_sum_max_error", 1) <= 1e-4
        checks[f"max_4_influences_{k}"] = st.get("max_influences", 99) <= 4
        checks[f"no_unweighted_vertex_{k}"] = st.get("unweighted_vertices", 1) == 0
        checks[f"skin_survives_reimport_{k}"] = bool(st.get("skin_modifier"))
    checks["fbx_front_is_plus_y_blender_head_centroid"] = fb.get("head_centroid_blender_xyz", [0, -1, 0])[1] > 0
    checks["lod0_tris_in_budget"] = pl.lod0_range[0] <= g["triangles"] <= pl.lod0_range[1]
    checks["lod1_tris_in_budget"] = g1["triangles"] <= pl.lod1_max
    checks["glb_embedded_png_lod0_size"] = rg.get("images_embedded") and rg.get("image_size_px") == [pl.tex0, pl.tex0]
    checks["glb_embedded_png_lod1_size"] = rg1.get("images_embedded") and rg1.get("image_size_px") == [pl.tex1, pl.tex1]
    checks["glb_one_mesh_one_material"] = rg["primitives"] == 1 and rg["materials"] == 1 and rg1["primitives"] == 1 and rg1["materials"] == 1
    ext = rg["extent_xyz"]
    checks["roblox_axes_glb_x_width_y_up_z_depth"] = (abs(ext[0] - W) <= 0.02 * W and abs(ext[1] - Hh) <= 0.02 * Hh
                                                      and abs(ext[2] - D) <= 0.02 * D and abs(rg["position_min_xyz"][1]) <= 0.01)
    checks["roblox_front_is_minus_z_glb"] = rg.get("head_centroid_xyz") is not None and rg["head_centroid_xyz"][2] < 0
    checks["walkable_top_lod0_max_abs_dev_le_0_25"] = None if t0 is None else (t0["misses"] == 0 and t0["max_abs_dev_studs"] <= 0.25)
    checks["walkable_top_lod0_nothing_above_top_plus_0_05"] = None if t0 is None else t0["max_above_studs"] <= 0.05
    checks["walkable_top_lod1_max_abs_dev_le_0_25"] = None if t1 is None else (t1["misses"] == 0 and t1["max_abs_dev_studs"] <= 0.25)
    checks["walkable_top_lod1_nothing_above_top_plus_0_05"] = None if t1 is None else t1["max_above_studs"] <= 0.05
    checks["player_landing_top_dev_le_0_25"] = rep["top_alignment_player_landing"]["max_abs_dev_studs"] <= 0.25
    checks["poses_bbox_within_110pct_envelope"] = all(max(v["bbox_over_envelope"]) <= 1.10 for v in pr.values())
    checks["fall_stretch_le_limit"] = pr["fall"]["body_top_height_ratio"] <= lim["fall_stretch_y_max"] + 1e-3
    checks["impact_compression_ge_limit"] = pr["impact"]["body_top_height_ratio"] >= lim["impact_scale_y_min"] - 1e-3
    checks["impact_widening_le_limit"] = max(pr["impact"]["body_width_ratio"], pr["impact"]["body_depth_ratio"]) <= lim["impact_scale_xz_max"] + 1e-3
    checks["poses_never_below_floor"] = min(v["min_z"] for v in pr.values()) >= -0.05
    checks["no_drift_after_50_impact_cycles"] = rep["poses"]["_drift_after_50_cycles_studs"] < 1e-4
    checks["secondary_bones_le_6"] = len(pl.secondary) <= lim["secondary_bones_max"]
    checks["files_on_disk_match_build_info_hashes"] = all(rep["determinism"]["build_info_hashes_match_files_on_disk"].values())
    if isinstance(det, dict) and "error" not in det:
        checks["determinism_glb_identical_across_two_builds"] = all(v["equal"] for k, v in det.items() if k.endswith(".glb"))
        checks["determinism_png_identical_across_two_builds"] = all(v["equal"] for k, v in det.items() if k.endswith(".png"))
    else:
        checks["determinism_glb_identical_across_two_builds"] = None if skip_rebuild else False
        checks["determinism_png_identical_across_two_builds"] = None if skip_rebuild else False
    rep["checks"] = {k: status(v) for k, v in checks.items()}
    rep["checks"]["roblox_studio_import"] = "NOT_RUN"
    rep["roblox_studio_import"] = {"status": "NOT_RUN", "reason": "Aucun Roblox Studio ni Open Cloud dans le conteneur ; "
                                   "unité d'import, skin MeshPart et Bones non mesurés dans Roblox.", "roblox_asset_id": None}
    rep["fbx_determinism_note"] = ("Le FBX n'entre pas dans la comparaison d'empreintes : l'exporteur FBX de Blender y écrit "
                                   "l'horodatage de création. Sa géométrie est contrôlée par réimport (dimensions, bones, poids).")
    rep["summary"] = {"pass": sum(1 for v in rep["checks"].values() if v == "PASS"),
                      "fail": sum(1 for v in rep["checks"].values() if v == "FAIL"),
                      "not_run": sum(1 for v in rep["checks"].values() if v == "NOT_RUN")}
    log(f"[{pl.asset_id}] checks: " + json.dumps(rep["checks"]))
    log(f"[{pl.asset_id}] summary: " + json.dumps(rep["summary"]))
    return rep


def write_manifest():
    """reports/T03/manifest_new_plush_v2_big.json : une entrée de manifeste par peluche (mêmes clés qu'une
    peluche de assets/manifest.json, + size_tier). Statut « modeled » : rien n'est importé dans Roblox."""
    entries = []
    for key in specs.PLUSHES:
        pl = specs.PLUSHES[key]()
        md = os.path.join("assets", "source", "models", "plush_v2", specs.MODEL_DIRS[key])
        base = os.path.join("assets", "import", "models", pl.asset_id)
        entries.append({
            "id": pl.asset_id,
            "name": pl.name_fr,
            "category": "room_prop",
            "release_stage": "v1",
            "status": "modeled",
            "roblox_asset_id": None,
            "source_path": os.path.join(md, f"{pl.label}.blend"),
            "export_path": base + ".glb",
            "additional_exports": [base + ".fbx", base + "_lod1.glb"],
            "dimensions_order": "width_depth_height",
            "size_studs": pl.envelope,
            "pivot": "bottom_center",
            "forward_axis": "-Z",
            "visual_brief": pl.visual_brief,
            "collision": {"shape": "box", "size_studs": pl.collider_size, "walkable_top": pl.walkable, "top_visible": True},
            "deformation_profile": "plush_soft",
            "production_method": "blender_mesh_and_optional_rig",
            "requires_external_import": True,
            "max_triangles_near": pl.lod0_range[1],
            "max_materials": 1,
            "image_export_pixels": None,
            "provenance": "generated from code in Blender, no third-party assets",
            "validation_evidence": [
                os.path.join(md, "build_info.json"),
                os.path.join(md, "collision.json"),
                os.path.join(md, "pose_library.json"),
                f"reports/T03/plush_v2_big_verify.json#assets.{pl.asset_id}",
                "reports/T03/plush_v2_big_verify_log.txt",
                f"reports/T03/renders/{pl.asset_id}_3q.png",
                f"reports/T03/renders/{pl.asset_id}_front.png",
                f"reports/T03/renders/{pl.asset_id}_silhouette.png",
                "reports/T03/renders/plush_v2_big_sheet.png",
                "reports/T03/renders/plush_v2_big_lineup.png",
            ],
            "size_tier": pl.size_tier,
        })
    doc = {"task": "T03", "batch": "plush_v2_big", "new_assets": entries}
    out = os.path.join(ROOT, "reports", "T03", "manifest_new_plush_v2_big.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return out


def main():
    args = sys.argv[1:]
    if args and args[0] == "manifest":
        print(write_manifest())
        return
    skip = "--skip-rebuild" in args
    args = [a for a in args if a != "--skip-rebuild"]
    which = args[0] if args else "all"
    keys = list(specs.PLUSHES) if which == "all" else [which]
    out_path = os.path.join(ROOT, "reports", "T03", "plush_v2_big_verify.json")
    doc = {"task": "T03", "batch": "plush_v2_big", "assets": {}}
    if os.path.exists(out_path) and which != "all":
        with open(out_path, encoding="utf-8") as f:
            doc = json.load(f)
    log(f"# verify_plush_v2_big.py {which} — {dt.datetime.now(dt.timezone.utc).isoformat()} — Blender {bpy.app.version_string}")
    for k in keys:
        doc["assets"][specs.PLUSHES[k]().asset_id] = verify(k, skip)
    doc["scope"] = ("Vérification Blender des exports réimportés (GLB, GLB LOD1, FBX) et du GLB brut ; ne remplace pas "
                    "l'import et la mesure dans Roblox Studio (NOT_RUN).")
    doc["units_convention"] = "1 unité Blender = 1 unité glTF/FBX = 1 stud (docs/decisions/0003_unites_import_3d.md)"
    doc["generated_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    doc["totals"] = {a: v["summary"] for a, v in doc["assets"].items()}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ROOT, "reports", "T03", "plush_v2_big_verify_log.txt"), "w" if which == "all" else "a",
              encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
    write_manifest()


if __name__ == "__main__":
    main()
