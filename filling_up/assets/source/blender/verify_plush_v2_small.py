"""Vérifie les exports du lot plush_v2_small en les ROUVRANT (scène vide) et en lisant les fichiers bruts.

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/verify_plush_v2_small.py [all|pipou,...] [--root DIR]
        [--skip-determinism] [--report PATH]

Contrôles (PASS / FAIL / NOT_RUN ; rien n'est PASS sans mesure) :
  dims_vs_envelope       boîte englobante réimportée (GLB, LOD1, FBX) = enveloppe visuelle à ±2 % par axe
  top_flatness           raycasts verticaux sur le rectangle utile, à 0,25 stud du bord (pas 0,25) :
                         |dessus visible - dessus collider| <= 0,25 ; et grille dense (pas 0,1, bord inclus) :
                         rien au-dessus de dessus + 0,05
  pivot_bottom_center    min hauteur = 0 (±0,01), centre de la boîte en plan à l'origine (±0,1)
  roblox_axes            GLB brut : Y = hauteur, X = largeur, Z = profondeur ; repère avant (broderie de l'œil
                         ou museau) retrouvé côté -Z avec la bonne couleur dans la texture embarquée
  materials / uv_texture 1 matériau par maillage, UV présentes, texture embarquée (GLB : bufferView PNG ;
                         FBX : PNG présent dans le binaire), tailles 1024 / 256
  triangles              LOD0 / LOD1 dans le budget du gabarit (mini / medium)
  armature               Root + 9 Belly_ij + secondaires attendus, rien d'autre
  skin_weights           somme = 1 (±1e-3) et <= 4 influences (GLB brut WEIGHTS_0 + import Blender)
  poses                  pose_library.json appliquée au rig réimporté : enveloppe dépassée de <= 10 %,
                         jamais sous le sol ; rapports d'étirement / compression mesurés
  collision_json         collider et walkable_top conformes à config/rooms.json
  determinism            reconstruction complète dans un dossier temporaire : SHA-256 identiques (GLB, LOD1,
                         textures) ; FBX comparé en masquant uniquement les champs d'horodatage
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import math
import os
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

import plush_v2_small_specs as specs  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


def chk(ok, measured, limit, note=None):
    out = {"status": "PASS" if ok else "FAIL", "measured": measured, "limit": limit}
    if note:
        out["note"] = note
    return out


def r4(v):
    if isinstance(v, (list, tuple, np.ndarray)):
        return [r4(x) for x in v]
    return round(float(v), 4)


# ---------------------------------------------------------------------------
# GLB brut
# ---------------------------------------------------------------------------
COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, _ver, _length = struct.unpack_from("<III", data, 0)
    assert magic == 0x46546C67, "not a GLB"
    off = 12
    js = None
    binc = b""
    while off < len(data):
        clen, ctype = struct.unpack_from("<II", data, off)
        chunk = data[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode("utf-8"))
        elif ctype == 0x004E4942:
            binc = chunk
        off += 8 + clen
    return js, binc


def accessor(js, binc, idx):
    a = js["accessors"][idx]
    bv = js["bufferViews"][a["bufferView"]]
    dtype = COMP[a["componentType"]]
    nc = NCOMP[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 0)
    count = a["count"]
    itemsize = np.dtype(dtype).itemsize * nc
    if stride and stride != itemsize:
        raw = np.frombuffer(binc, dtype=np.uint8, count=stride * count, offset=start).reshape(count, stride)
        arr = raw[:, :itemsize].copy().view(dtype).reshape(count, nc)
    else:
        arr = np.frombuffer(binc, dtype=dtype, count=count * nc, offset=start).reshape(count, nc)
    arr = arr.astype(np.float64)
    if a.get("normalized"):
        arr = arr / float(np.iinfo(dtype).max)
    return arr, a


def glb_checks(path, pl, tex_size):
    from PIL import Image
    js, binc = read_glb(path)
    res = {}
    meshes = js.get("meshes", [])
    prims = [p for m in meshes for p in m["primitives"]]
    res["mesh_count"] = len(meshes)
    res["primitive_count"] = len(prims)
    pr = prims[0]
    pos, pa = accessor(js, binc, pr["attributes"]["POSITION"])
    # transformations de nœud des maillages (doivent être identité pour un modèle en espace modèle)
    node_tf = [{k: n[k] for k in ("translation", "rotation", "scale", "matrix") if k in n}
               for n in js.get("nodes", []) if "mesh" in n]
    res["mesh_node_transforms"] = node_tf
    mn, mx = pos.min(axis=0), pos.max(axis=0)
    res["position_min_xyz"] = r4(mn)
    res["position_max_xyz"] = r4(mx)
    res["accessor_minmax_present"] = "min" in pa and "max" in pa
    W, D, H = pl.envelope
    ext = mx - mn
    axes_ok = (abs(ext[0] / W - 1) <= 0.02 and abs(ext[1] / H - 1) <= 0.02 and abs(ext[2] / D - 1) <= 0.02
               and abs(mn[1]) <= 0.01 and not any(node_tf_has_rot(t) for t in node_tf))
    # repère avant : rayon tiré depuis l'avant Roblox (-Z) vers +Z en (x, hauteur) du repère du visage ; le
    # premier triangle touché doit porter la couleur attendue (œil / museau) dans la texture embarquée.
    px, pz = pl.face_probe["xz"]
    uv, _ = accessor(js, binc, pr["attributes"]["TEXCOORD_0"])
    idx, _ = accessor(js, binc, pr["indices"])
    tri = idx.astype(np.int64).reshape(-1, 3)
    orig = np.array([px, pz, -100.0])
    dirv = np.array([0.0, 0.0, 1.0])
    A, B, C = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    e1, e2 = B - A, C - A
    pv = np.cross(dirv, e2)
    det = np.einsum("ij,ij->i", e1, pv)
    ok_det = np.abs(det) > 1e-12
    inv = np.where(ok_det, 1.0 / np.where(ok_det, det, 1.0), 0.0)
    tv = orig - A
    uu = np.einsum("ij,ij->i", tv, pv) * inv
    qv = np.cross(tv, e1)
    vv = (qv @ dirv) * inv
    tt = np.einsum("ij,ij->i", e2, qv) * inv
    hit = ok_det & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (tt > 0)
    mat = js["materials"][pr["material"]]
    tex_idx = mat["pbrMetallicRoughness"]["baseColorTexture"]["index"]
    img_idx = js["textures"][tex_idx]["source"]
    img_js = js["images"][img_idx]
    embedded = "bufferView" in img_js and "uri" not in img_js
    bv = js["bufferViews"][img_js["bufferView"]]
    png = binc[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]]
    im = Image.open(io.BytesIO(png)).convert("RGB")
    a = np.asarray(im).astype(float) / 255.0
    exp = specs.linear_to_srgb(specs.lin(pl.face_probe["expect"]))
    thr = 0.16 if tex_size >= 1024 else 0.33

    def ray_color(o, dv):
        tvv = o - A
        pvv = np.cross(dv, e2)
        dt = np.einsum("ij,ij->i", e1, pvv)
        okd = np.abs(dt) > 1e-12
        iv = np.where(okd, 1.0 / np.where(okd, dt, 1.0), 0.0)
        u_ = np.einsum("ij,ij->i", tvv, pvv) * iv
        qq = np.cross(tvv, e1)
        v_ = (qq @ dv) * iv
        t_ = np.einsum("ij,ij->i", e2, qq) * iv
        h_ = okd & (u_ >= 0) & (v_ >= 0) & (u_ + v_ <= 1) & (t_ > 0)
        if not h_.any():
            return None, None
        jj = int(np.argmin(np.where(h_, t_, np.inf)))
        ww = np.array([1 - u_[jj] - v_[jj], u_[jj], v_[jj]])
        uu_, vv_ = (uv[tri[jj]] * ww[:, None]).sum(axis=0)
        y_, x_ = min(int(vv_ * im.size[1]), im.size[1] - 1), min(int(uu_ * im.size[0]), im.size[0] - 1)
        return o + t_[jj] * dv, a[max(y_ - 1, 0):y_ + 2, max(x_ - 1, 0):x_ + 2].reshape(-1, 3).mean(axis=0)
    back_hit, back_col = ray_color(np.array([px, pz, 100.0]), np.array([0.0, 0.0, -1.0]))
    back_diff = float(np.abs(back_col - exp).max()) if back_col is not None else 9.0
    if hit.any():
        j = int(np.argmin(np.where(hit, tt, np.inf)))
        hp = orig + tt[j] * dirv
        w = np.array([1 - uu[j] - vv[j], uu[j], vv[j]])
        u, v = (uv[tri[j]] * w[:, None]).sum(axis=0)
        yy, xx = min(int(v * im.size[1]), im.size[1] - 1), min(int(u * im.size[0]), im.size[0] - 1)
        col = a[max(yy - 1, 0):yy + 2, max(xx - 1, 0):xx + 2].reshape(-1, 3).mean(axis=0)
        cdist = float(np.abs(col - exp).max())
        res["front_probe"] = {"what": pl.face_probe["what"], "ray_origin_roblox": r4(orig), "ray_dir": [0, 0, 1],
                              "hit_roblox_xyz": r4(hp), "texel_rgb": r4(col), "expected_rgb": r4(exp),
                              "max_channel_diff": round(cdist, 3), "threshold": thr,
                              "back_ray_hit_roblox_xyz": r4(back_hit) if back_hit is not None else None,
                              "back_ray_texel_rgb": r4(back_col) if back_col is not None else None,
                              "back_ray_max_channel_diff": round(back_diff, 3)}
        front_ok = hp[2] < 0 and cdist <= thr and back_diff > cdist + 0.1
        hit_z = hp[2]
    else:
        res["front_probe"] = {"what": pl.face_probe["what"], "hit": None}
        front_ok = False
        hit_z = None
    res["roblox_axes"] = chk(bool(axes_ok and front_ok),
                             {"extent_xyz": r4(ext), "expected_xyz": [W, H, D], "y_min": r4(mn[1]),
                              "front_probe_hit_z": r4(hit_z) if hit_z is not None else None},
                             "X = largeur, Y = hauteur (min 0), Z = profondeur (±2 %) ; rayon depuis -Z : couleur du "
                             "visage attendue (écart canal <= 0,16 LOD0 / 0,33 LOD1) et rayon depuis +Z nettement "
                             "différent (dos)")
    res["embedded_texture"] = chk(bool(embedded and im.size == (tex_size, tex_size) and img_js.get("mimeType") == "image/png"),
                                  {"embedded_bufferView": embedded, "size": list(im.size), "mime": img_js.get("mimeType")},
                                  f"PNG embarqué {tex_size} px")
    res["materials"] = chk(len(js.get("materials", [])) == 1 and len(prims) == 1,
                           {"materials": len(js.get("materials", [])), "primitives": len(prims)}, "1 matériau, 1 primitive")
    # poids bruts
    if "WEIGHTS_0" in pr["attributes"]:
        wts, _ = accessor(js, binc, pr["attributes"]["WEIGHTS_0"])
        s = wts.sum(axis=1)
        nz = (wts > 1e-6).sum(axis=1)
        res["raw_weights"] = chk(bool(np.abs(s - 1).max() <= 1e-3 and nz.max() <= 4),
                                 {"sum_max_error": float(np.abs(s - 1).max()), "max_influences": int(nz.max()),
                                  "vertices": int(len(s))}, "somme 1 ±1e-3, <= 4 influences")
    else:
        res["raw_weights"] = chk(False, "WEIGHTS_0 absent", "présent")
    skins = js.get("skins", [])
    res["joint_names"] = [js["nodes"][j]["name"] for j in skins[0]["joints"]] if skins else []
    return res


def node_tf_has_rot(t):
    if "rotation" in t and np.abs(np.array(t["rotation"]) - np.array([0, 0, 0, 1])).max() > 1e-6:
        return True
    if "scale" in t and np.abs(np.array(t["scale"]) - 1).max() > 1e-6:
        return True
    if "translation" in t and np.abs(np.array(t["translation"])).max() > 1e-6:
        return True
    return False


# ---------------------------------------------------------------------------
# Import Blender
# ---------------------------------------------------------------------------
def import_file(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.endswith(".glb"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = sorted([o for o in bpy.data.objects if o.type == "MESH"],
                    key=lambda o: (any(m.type == "ARMATURE" for m in o.modifiers), len(o.data.vertices)), reverse=True)
    return arms, meshes


def world_mesh(obj, evaluated=True):
    dg = bpy.context.evaluated_depsgraph_get()
    ob = obj.evaluated_get(dg) if evaluated else obj
    me = ob.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(obj.matrix_world)
    co = co @ M[:3, :3].T + M[:3, 3]
    me.calc_loop_triangles()
    tris = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tris)
    tris = tris.reshape(-1, 3)
    ob.to_mesh_clear()
    return co, tris


def top_flatness(co, tris, pl):
    bvh = BVHTree.FromPolygons([tuple(v) for v in co], [tuple(int(i) for i in t) for t in tris])
    x0, x1, y0, y1 = pl.rect
    top = pl.top

    def cast(x, y):
        hit = bvh.ray_cast(Vector((x, y, top + 20.0)), Vector((0, 0, -1)))
        return None if hit[0] is None else hit[0].z

    inset = []
    xs = np.arange(x0 + 0.25, x1 - 0.25 + 1e-6, 0.25)
    ys = np.arange(y0 + 0.25, y1 - 0.25 + 1e-6, 0.25)
    miss = 0
    for x in xs:
        for y in ys:
            z = cast(float(x), float(y))
            if z is None:
                miss += 1
            else:
                inset.append(z)
    inset = np.array(inset)
    dense = []
    for x in np.linspace(x0, x1, int(round((x1 - x0) / 0.1)) + 1):
        for y in np.linspace(y0, y1, int(round((y1 - y0) / 0.1)) + 1):
            z = cast(float(x), float(y))
            if z is not None:
                dense.append(z)
    dense = np.array(dense)
    # sommets dans le rectangle (preuve complémentaire)
    inside = (co[:, 0] >= x0) & (co[:, 0] <= x1) & (co[:, 1] >= y0) & (co[:, 1] <= y1)
    vmax = float(co[inside, 2].max()) if inside.any() else None
    dev = float(np.abs(inset - top).max()) if len(inset) else 9.0
    above = float(dense.max() - top) if len(dense) else 9.0
    return {
        "samples_inset": int(len(inset)), "misses": miss,
        "max_abs_deviation": round(dev, 4), "mean_top": round(float(inset.mean()), 4) if len(inset) else None,
        "min_top": round(float(inset.min()), 4) if len(inset) else None,
        "dense_samples": int(len(dense)), "max_above_top_dense": round(above, 4),
        "max_vertex_z_in_rect": round(vmax, 4) if vmax is not None else None,
    }, (dev <= 0.25 and miss == 0 and above <= 0.05)


def tex_info(obj):
    imgs = []
    for slot in obj.material_slots:
        m = slot.material
        if m and m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    imgs.append(n.image)
    return imgs


def static_blender_checks(path, pl, kind):
    arms, meshes = import_file(path)
    res = {"file": os.path.relpath(path, ROOT) if path.startswith(ROOT) else path}
    if not meshes:
        res["opened"] = chk(False, "aucun maillage", "maillage présent")
        return res, None, None
    ob = meshes[0]
    res["opened"] = chk(True, ob.name, "maillage présent")
    co, tris = world_mesh(ob, evaluated=False)
    mn, mx = co.min(axis=0), co.max(axis=0)
    ext = mx - mn
    W, D, H = pl.envelope
    ratio = [ext[0] / W, ext[1] / D, ext[2] / H]
    res["dims_vs_envelope"] = chk(all(abs(r - 1) <= 0.02 for r in ratio),
                                  {"width_x": r4(ext[0]), "depth": r4(ext[1]), "height": r4(ext[2]),
                                   "ratios_w_d_h": r4(ratio)}, f"enveloppe {W} x {D} x {H} ±2 %")
    ctr = (mn + mx) / 2
    res["pivot_bottom_center"] = chk(abs(mn[2]) <= 0.01 and abs(ctr[0]) <= 0.1 and abs(ctr[1]) <= 0.1,
                                     {"min_height": r4(mn[2]), "bbox_center_plan": r4(ctr[:2])},
                                     "min hauteur 0 ±0,01 ; centre en plan ±0,1")
    ntri = len(tris)
    bud = specs.BUDGETS[pl.tier]
    if kind == "lod1":
        ok = ntri <= bud["lod1_max"]
        lim = f"<= {bud['lod1_max']}"
    else:
        ok = bud["lod0_min"] <= ntri <= bud["lod0_max"]
        lim = f"{bud['lod0_min']}..{bud['lod0_max']}"
    res["triangles"] = chk(ok, ntri, lim)
    nmat = len([s for s in ob.material_slots if s.material])
    res["materials"] = chk(nmat == 1, nmat, "1 matériau")
    imgs = tex_info(ob)
    has_uv = len(ob.data.uv_layers) >= 1
    tex_ok = bool(imgs) and imgs[0].size[0] > 0
    if kind == "fbx":
        with open(path, "rb") as f:
            raw = f.read()
        embedded = raw.count(b"\x89PNG\r\n\x1a\n")
        tex_ok = tex_ok and embedded >= 1
        res["uv_texture"] = chk(has_uv and tex_ok, {"uv_layers": len(ob.data.uv_layers), "image_nodes": len(imgs),
                                                    "image_size": list(imgs[0].size) if imgs else None,
                                                    "png_streams_in_fbx": embedded}, "UV + texture PNG embarquée")
    else:
        res["uv_texture"] = chk(has_uv and tex_ok, {"uv_layers": len(ob.data.uv_layers), "image_nodes": len(imgs),
                                                    "image_size": list(imgs[0].size) if imgs else None,
                                                    "packed": bool(imgs and imgs[0].packed_file)},
                                "UV + texture embarquée")
    exp_bones = set(pl.bone_names())
    got = set(arms[0].data.bones.keys()) if arms else set()
    res["armature"] = chk(bool(arms) and got == exp_bones and any(m.type == "ARMATURE" for m in ob.modifiers),
                          {"bones": sorted(got), "missing": sorted(exp_bones - got), "extra": sorted(got - exp_bones),
                           "armature_modifier": any(m.type == "ARMATURE" for m in ob.modifiers)},
                          "Root + Belly_00..22 + " + ", ".join(pl.secondary))
    # poids (groupes de sommets)
    names = {g.index: g.name for g in ob.vertex_groups}
    sums = np.zeros(len(ob.data.vertices))
    infl = np.zeros(len(ob.data.vertices), int)
    for v in ob.data.vertices:
        for g in v.groups:
            if g.group in names and g.weight > 1e-6:
                sums[v.index] += g.weight
                infl[v.index] += 1
    res["skin_weights"] = chk(bool(np.abs(sums - 1).max() <= 1e-3 and infl.max() <= 4 and (infl == 0).sum() == 0),
                              {"sum_max_error": float(np.abs(sums - 1).max()), "max_influences": int(infl.max()),
                               "unweighted": int((infl == 0).sum())}, "somme 1 ±1e-3, <= 4 influences, aucun orphelin")
    flat, ok = top_flatness(co, tris, pl)
    res["top_flatness"] = chk(ok, flat, "|dessus - collider| <= 0,25 (retrait 0,25) ; rien > dessus + 0,05")
    return res, arms[0] if arms else None, ob


def roblox_to_blender(v):
    return Vector((v[0], -v[2], v[1]))


def apply_pose_world(arm, pose_rbx, heads_world):
    """Applique une pose (espace modèle Roblox, autour de la tête du bone au repos) au rig réimporté."""
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    Mw = arm.matrix_world.copy()
    Mi = Mw.inverted()
    for bname, sp in pose_rbx.items():
        h = heads_world[bname]
        G = Matrix.Identity(4)
        if "rotation_axis" in sp:
            ax = roblox_to_blender(sp["rotation_axis"]).normalized()
            R = Matrix.Rotation(math.radians(sp["rotation_degrees"]), 4, ax)
            G = Matrix.Translation(h) @ R @ Matrix.Translation(-h)
        if "translation" in sp:
            G = Matrix.Translation(roblox_to_blender(sp["translation"])) @ G
        rest_world = Mw @ arm.data.bones[bname].matrix_local
        arm.pose.bones[bname].matrix = Mi @ G @ rest_world
        bpy.context.view_layer.update()


def pose_checks(arm, ob, pl, lib):
    res = {}
    Mw = arm.matrix_world
    heads_world = {b.name: (Mw @ b.head_local) for b in arm.data.bones}
    # cohérence têtes de bones réimportées <-> pose_library (Roblox)
    errs = []
    for b, hr in lib["bone_rest_heads"].items():
        if b in heads_world:
            errs.append((heads_world[b] - roblox_to_blender(hr)).length)
    res["bone_heads_match_library"] = chk(max(errs) <= 0.01, {"max_error_studs": r4(max(errs))}, "<= 0,01 stud")
    co0, tris = world_mesh(ob)
    x0, x1, y0, y1 = pl.rect
    grid = [(float(x), float(y)) for x in np.linspace(x0 + 0.5, x1 - 0.5, 5) for y in np.linspace(y0 + 0.5, y1 - 0.5, 5)]

    def top_mean(co):
        bvh = BVHTree.FromPolygons([tuple(v) for v in co], [tuple(int(i) for i in t) for t in tris])
        zs = []
        for x, y in grid:
            hit = bvh.ray_cast(Vector((x, y, 50.0)), Vector((0, 0, -1)))
            if hit[0] is not None:
                zs.append(hit[0].z)
        return float(np.mean(zs))
    top0 = top_mean(co0)
    body = (co0[:, 2] > 0.3) & (co0[:, 2] < pl.top) & (co0[:, 0] > x0 - 0.8) & (co0[:, 0] < x1 + 0.8) & \
           (co0[:, 1] > y0 - 0.2) & (co0[:, 1] < y1 + 0.2)
    w0 = np.ptp(co0[body, 0])
    d0 = np.ptp(co0[body, 1])
    W, D, H = pl.envelope
    lim = specs.RUNTIME_LIMITS
    for pname, pose in lib["poses"].items():
        apply_pose_world(arm, pose, heads_world)
        co, _ = world_mesh(ob)
        ext = co.max(axis=0) - co.min(axis=0)
        ctr_ext = np.maximum(np.abs(co.max(axis=0)), np.abs(co.min(axis=0)))
        env_ratio = [2 * ctr_ext[0] / W, 2 * ctr_ext[1] / D, co[:, 2].max() / H]
        sy = top_mean(co) / top0
        sw = np.ptp(co[body, 0]) / w0
        sd = np.ptp(co[body, 1]) / d0
        ext_ratio = [ext[0] / W, ext[1] / D, ext[2] / H]
        ok = max(ext_ratio) <= 1.10 and co[:, 2].min() >= -0.02
        rot_max = max([sp.get("rotation_degrees", 0) for sp in pose.values()] + [0])
        ok = ok and rot_max <= lim["max_secondary_angle_degrees"]
        if pname == "fall":
            ok = ok and sy <= lim["fall_stretch_y_max"] + 0.01
        if pname == "impact":
            ok = ok and sy >= lim["impact_scale_y_min"] - 0.01 and max(sw, sd) <= lim["impact_scale_xz_max"]
        res[pname] = chk(bool(ok), {"bbox_extent": r4(ext), "extent_ratio_w_d_h": r4(ext_ratio),
                                    "envelope_ratio_about_pivot_w_d_h": r4(env_ratio),
                                    "top_scale_y": r4(sy), "body_scale_x": r4(sw), "body_scale_depth": r4(sd),
                                    "min_height": r4(co[:, 2].min()), "max_rotation_deg": rot_max},
                         "boîte englobante <= 110 % de l'enveloppe ; jamais sous le sol ; chute <= 1,12 ; impact >= 0,72 et "
                         "élargissement <= 1,18 ; rotations <= 18°")
    apply_pose_world(arm, {}, heads_world)
    co, _ = world_mesh(ob)
    res["return_to_reference_drift"] = chk(float(np.abs(co - co0).max()) <= 1e-5,
                                           r4(float(np.abs(co - co0).max())), "<= 1e-5 stud")
    return res


def collision_checks(pl, root):
    p = os.path.join(root, "assets", "source", "models", "plush_v2", specs.MODEL_DIRS[pl.key], "collision.json")
    with open(p, encoding="utf-8") as f:
        cj = json.load(f)
    with open(os.path.join(ROOT, "config", "rooms.json"), encoding="utf-8") as f:
        rooms = json.load(f)
    cfg = None

    def walk(o):
        nonlocal cfg
        if isinstance(o, dict):
            if o.get("id") == pl.asset_id and "collider" in o:
                cfg = o
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(rooms)
    ok = (cfg is not None and cj["collider"]["size_studs_config"] == cfg["collider"]["size_studs"]
          and cj["walkable_top"]["size_studs"] == cfg["collider"]["walkable_top"]
          and list(pl.envelope) == cfg["size_studs"] and cj["walkable_top"]["height_studs"] == pl.top)
    return chk(bool(ok), {"collision_json": cj["collider"]["size_studs_config"], "walkable": cj["walkable_top"]["size_studs"],
                          "config": cfg["collider"] if cfg else None, "config_size_studs": cfg["size_studs"] if cfg else None},
               "collider, walkable_top et enveloppe = config/rooms.json")


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def fbx_masked_equal(a, b):
    with open(a, "rb") as f:
        A = f.read()
    with open(b, "rb") as f:
        B = f.read()
    if A == B:
        return True, {"identical_bytes": True}
    if len(A) != len(B):
        return False, {"identical_bytes": False, "size_a": len(A), "size_b": len(B)}
    diff = np.nonzero(np.frombuffer(A, np.uint8) != np.frombuffer(B, np.uint8))[0]
    keys = []
    for kw in (b"CreationTimeStamp", b"CreationTime", b"LastSaved|DateTime_GMT", b"FileId"):
        s = 0
        while True:
            i = A.find(kw, s)
            if i < 0:
                break
            keys.append(i)
            s = i + 1
    near = all(any(0 <= d - k <= 400 for k in keys) for d in diff)
    return near, {"identical_bytes": False, "differing_bytes": int(len(diff)),
                  "all_diffs_within_timestamp_fields": bool(near)}


def determinism(keys, root):
    """Deux reconstructions complètes dans le MÊME chemin temporaire (le FBX embarque le chemin absolu de la
    texture : comparer des racines différentes mesurerait le chemin, pas le déterminisme), plus comparaison des
    GLB / textures du dépôt avec une reconstruction fraîche."""
    import shutil
    base = tempfile.mkdtemp(prefix="plush_v2_det_")
    run_dir = os.path.join(base, "run")
    first = os.path.join(base, "first")
    cmd = [sys.executable, "-I", os.path.join(HERE, "build_plush_v2_small.py"), ",".join(keys), "--out-root", run_dir]
    log("determinism: build #1 into", run_dir)
    r1 = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    shutil.move(run_dir, first)
    log("determinism: build #2 into the same path", run_dir)
    r2 = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    out = {}
    for k in keys:
        pl = specs.PLUSHES[k]()
        files = {}
        allok = r1.returncode == 0 and r2.returncode == 0
        rels = [f"assets/import/models/{pl.asset_id}.glb", f"assets/import/models/{pl.asset_id}_lod1.glb",
                f"assets/source/models/plush_v2/{specs.MODEL_DIRS[k]}/textures/{pl.asset_id}_albedo_1024.png",
                f"assets/source/models/plush_v2/{specs.MODEL_DIRS[k]}/textures/{pl.asset_id}_albedo_256.png"]
        for rel in rels:
            a, b, c = os.path.join(first, rel), os.path.join(run_dir, rel), os.path.join(root, rel)
            ha = sha(a) if os.path.exists(a) else None
            hb = sha(b) if os.path.exists(b) else None
            hc = sha(c) if os.path.exists(c) else None
            same = ha is not None and ha == hb == hc
            files[rel] = {"sha256_repo": hc, "sha256_fresh_build_1": ha, "sha256_fresh_build_2": hb, "equal": same}
            allok &= same
        rel = f"assets/import/models/{pl.asset_id}.fbx"
        eq, info = fbx_masked_equal(os.path.join(first, rel), os.path.join(run_dir, rel))
        info["compared"] = "build #1 vs build #2, même chemin de sortie"
        files[rel] = info
        allok &= eq
        out[k] = chk(bool(allok), files, "SHA-256 identiques (dépôt = reconstruction 1 = reconstruction 2) pour GLB, "
                     "LOD1 et textures ; FBX identique hors champs d'horodatage",
                     note=("FBX : " + ("octets identiques" if info.get("identical_bytes") else
                                       ("identique hors horodatage" if eq else "DIFFÉRENT hors horodatage"))))
        out[k]["fbx_equal_masked"] = bool(eq)
    out["_build_returncode"] = [r1.returncode, r2.returncode]
    out["_tmp_root"] = base
    return out


def verify(key, root, det=None):
    pl = specs.PLUSHES[key]()
    base = os.path.join(root, "assets", "import", "models", pl.asset_id)
    lib_p = os.path.join(root, "assets", "source", "models", "plush_v2", specs.MODEL_DIRS[key], "pose_library.json")
    with open(lib_p, encoding="utf-8") as f:
        lib = json.load(f)
    rep = {"asset_id": pl.asset_id, "size_tier": pl.tier, "envelope_wdh": pl.envelope,
           "collider_wdh": pl.collider_size, "collider_center_blender_xy": list(pl.collider_center)}
    log(f"== {pl.asset_id}")
    rep["glb_raw"] = glb_checks(base + ".glb", pl, 1024)
    rep["glb_lod1_raw"] = glb_checks(base + "_lod1.glb", pl, 256)
    r0, arm, ob = static_blender_checks(base + ".glb", pl, "lod0")
    r0["poses"] = pose_checks(arm, ob, pl, lib) if arm else {"status": "FAIL", "measured": "no armature"}
    rep["glb_lod0"] = r0
    r1, arm1, ob1 = static_blender_checks(base + "_lod1.glb", pl, "lod1")
    r1["poses"] = pose_checks(arm1, ob1, pl, lib) if arm1 else {"status": "FAIL", "measured": "no armature"}
    rep["glb_lod1"] = r1
    rf, _a, _o = static_blender_checks(base + ".fbx", pl, "fbx")
    rep["fbx"] = rf
    rep["collision_json"] = collision_checks(pl, root)
    rep["determinism"] = det.get(key) if det else {"status": "NOT_RUN", "measured": None,
                                                   "limit": "SHA-256 identiques sur deux constructions"}
    # synthèse
    summary = {}

    def walk(prefix, d):
        if isinstance(d, dict):
            if "status" in d and "limit" in d:
                summary[prefix] = d["status"]
                return
            for k, v in d.items():
                walk(f"{prefix}.{k}" if prefix else k, v)
    walk("", rep)
    rep["summary"] = summary
    rep["all_pass"] = all(v == "PASS" for v in summary.values())
    for k, v in summary.items():
        log(f"  {v:7s} {k}")
    return rep


def manifest_entries(out, report_path):
    """Entrées « manifest » (mêmes clés qu'une peluche de assets/manifest.json) + size_tier ; preuves liées."""
    entries = []
    rel_report = os.path.relpath(report_path, ROOT)
    for k in specs.PLUSHES:
        if k not in out["assets"]:
            continue
        pl = specs.PLUSHES[k]()
        d = specs.MODEL_DIRS[k]
        bud = specs.BUDGETS[pl.tier]
        e = {
            "id": pl.asset_id,
            "name": pl.name_fr,
            "category": "room_prop",
            "release_stage": "v1",
            "status": "modeled",
            "roblox_asset_id": None,
            "source_path": f"assets/source/models/plush_v2/{d}/{pl.label}.blend",
            "export_path": f"assets/import/models/{pl.asset_id}.glb",
            "additional_exports": [f"assets/import/models/{pl.asset_id}.fbx",
                                   f"assets/import/models/{pl.asset_id}_lod1.glb"],
            "dimensions_order": "width_depth_height",
            "size_studs": list(pl.envelope),
            "pivot": "bottom_center",
            "forward_axis": "-Z",
            "visual_brief": pl.visual_brief,
            "collision": {"shape": "box", "size_studs": list(pl.collider_size),
                          "walkable_top": list(pl.collider_size[:2]), "top_visible": True},
            "deformation_profile": "plush_soft",
            "production_method": "blender_mesh_and_rig_generated_from_code",
            "requires_external_import": True,
            "max_triangles_near": bud["lod0_max"],
            "max_materials": 1,
            "image_export_pixels": None,
            "provenance": "generated from code in Blender, no third-party assets",
            "validation_evidence": [
                f"{rel_report}#assets.{k}",
                os.path.splitext(rel_report)[0] + "_log.txt",
                f"assets/source/models/plush_v2/{d}/build_info.json",
                f"assets/source/models/plush_v2/{d}/collision.json",
                f"assets/source/models/plush_v2/{d}/pose_library.json",
                f"reports/T03/renders/{pl.asset_id}_v2_3q.png",
                f"reports/T03/renders/{pl.asset_id}_v2_front.png",
                f"reports/T03/renders/{pl.asset_id}_v2_silhouette.png",
                "reports/T03/renders/plush_v2_small_sheet.png",
                "reports/T03/renders/plush_v2_small_lineup.png",
            ],
            "size_tier": pl.tier,
            "verification_all_pass": out["assets"][k]["all_pass"],
        }
        if pl.behavior_params:
            e["behavior_params"] = pl.behavior_params
        entries.append(e)
    return {"task": "T03", "batch": "plush_v2_small", "new_assets": entries}


if __name__ == "__main__":
    args = sys.argv[1:]
    root = ROOT
    report = os.path.join(ROOT, "reports", "T03", "plush_v2_small_verify.json")
    skip_det = "--skip-determinism" in args
    args = [a for a in args if a != "--skip-determinism"]
    if "--root" in args:
        i = args.index("--root")
        root = os.path.abspath(args[i + 1])
        args = args[:i] + args[i + 2:]
    if "--report" in args:
        i = args.index("--report")
        report = os.path.abspath(args[i + 1])
        args = args[:i] + args[i + 2:]
    which = args[0] if args else "all"
    keys = list(specs.PLUSHES) if which == "all" else which.split(",")
    det = None if skip_det else determinism(keys, root)
    out = {"task": "T03", "batch": "plush_v2_small", "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
           "blender_version": bpy.app.version_string, "root": root, "roblox_studio_import": "NOT_RUN (Studio indisponible)",
           "assets": {}}
    for k in keys:
        out["assets"][k] = verify(k, root, det)
    if det:
        out["determinism_run"] = {"returncode": det["_build_returncode"], "tmp_root": det["_tmp_root"]}
    out["all_pass"] = all(a["all_pass"] for a in out["assets"].values())
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    man = manifest_entries(out, report)
    with open(os.path.join(os.path.dirname(report), "manifest_new_plush_v2_small.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    log("ALL PASS" if out["all_pass"] else "SOME FAIL")
    with open(os.path.splitext(report)[0] + "_log.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
