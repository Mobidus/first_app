"""Construit le lot de peluches « plush_v2_small » (Pipou, Mochi, Bulle, Grumf, Nuage) dans Blender headless.

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/build_plush_v2_small.py [pipou|mochi|bulle|grumf|nuage|all]
        [--out-root DIR]   # écrit ailleurs (contrôle de déterminisme) au lieu du dépôt

Pipeline par peluche (indépendant de build_plush.py, édité en parallèle par un autre lot) :
 1. champ de distance signée (plush_v2_small_specs) échantillonné sur une grille -> « surface nets »
    + projection de Newton = maillage haute définition (union lisse des volumes, dessus plat garanti) ;
 2. LOD0 / LOD1 par décimation (symétrique quand la peluche l'est), découpe du maillage sur le bord du
    rectangle utile puis plafonnement : rien ne dépasse le dessus du collider + 0,03 dans le rectangle ;
 3. UV (smart project) puis peinture procédurale TEXEL PAR TEXEL : chaque texel est replacé sur la surface
    SDF et reçoit couleurs de régions, coutures, broderies, occlusion douce et grain de velours
    (1024 px LOD0, 256 px LOD1) ; 1 matériau par maillage ;
 4. rig : Root (statique) + Belly_00..Belly_22 + secondaires ; poids normalisés, <= 4 influences ;
 5. poses (repos, chute, impact, rebond, appui joueur) en translations/rotations de bones ;
 6. .blend, GLB (LOD0, LOD1), FBX, collision.json, pose_library.json, build_info.json.
Tout est déterministe (graines fixes, aucun échantillonnage aléatoire au rendu/cuisson).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import plush_v2_small_specs as specs  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # filling_up/
NEAR_TEX = 1024
FAR_TEX = 256
TOP_EPS = 0.03  # plafond des sommets dans le rectangle utile : dessus + 0,03 (limite contrôlée : + 0,05)


# ---------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0  # 1 BU = 1 stud (décision 0003)
    return sc


def activate(obj, others=()):
    bpy.ops.object.select_all(action="DESELECT")
    for o in others:
        o.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def eval_chunked(fn, P, chunk=200000):
    out = np.empty(len(P))
    for s in range(0, len(P), chunk):
        out[s:s + chunk] = fn(P[s:s + chunk])
    return out


def sdf_grad(pl, P, e=0.01):
    k = np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], float)
    g = np.zeros_like(P)
    for kk in k:
        g += np.outer(pl.sdf(P + e * kk), kk)
    return g / (4 * e)


# ---------------------------------------------------------------------------
# Surface nets (maillage d'iso-surface à partir de la grille SDF)
# ---------------------------------------------------------------------------
def surface_nets(pl, h):
    W, D, H = pl.envelope
    lo = np.array([-W / 2 - 0.4, -D / 2 - 0.4, -0.3])
    hi = np.array([W / 2 + 0.4, D / 2 + 0.4, H + 0.4])
    xs = np.arange(lo[0], hi[0] + h, h)
    ys = np.arange(lo[1], hi[1] + h, h)
    zs = np.arange(lo[2], hi[2] + h, h)
    nx, ny, nz = len(xs), len(ys), len(zs)
    F = np.empty((nx, ny, nz), np.float32)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    X = X.ravel()
    Y = Y.ravel()
    step = max(1, 400000 // (nx * ny))
    for k0 in range(0, nz, step):
        kk = zs[k0:k0 + step]
        P = np.stack([np.tile(X, len(kk)), np.tile(Y, len(kk)), np.repeat(kk, nx * ny)], axis=1)
        vals = pl.sdf(P).reshape(len(kk), nx, ny)
        F[:, :, k0:k0 + len(kk)] = np.transpose(vals, (1, 2, 0))
    inside = F < 0
    cshape = (nx - 1, ny - 1, nz - 1)
    acc = np.zeros(cshape + (3,), np.float64)
    cnt = np.zeros(cshape, np.int32)

    def add_axis(axis):
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[axis] = slice(None, -1)
        sl1[axis] = slice(1, None)
        F0 = F[tuple(sl0)]
        F1 = F[tuple(sl1)]
        cross = (F0 < 0) != (F1 < 0)
        t = np.where(cross, F0 / np.where(cross, F0 - F1, 1.0), 0.0)
        others = [a for a in range(3) if a != axis]
        for a in (0, 1):
            for b in (0, 1):
                sl = [slice(None)] * 3
                sl[others[0]] = slice(a, a + cshape[others[0]])
                sl[others[1]] = slice(b, b + cshape[others[1]])
                c = cross[tuple(sl)]
                tt = t[tuple(sl)]
                acc[..., axis] += np.where(c, tt, 0.0)
                acc[..., others[0]] += np.where(c, a, 0.0)
                acc[..., others[1]] += np.where(c, b, 0.0)
                cnt[...] += c
        return cross, others

    crosses = [add_axis(ax) for ax in range(3)]
    active = cnt > 0
    idx = -np.ones(cshape, np.int64)
    ii, jj, kk_ = np.nonzero(active)
    idx[ii, jj, kk_] = np.arange(len(ii))
    loc = acc[ii, jj, kk_] / cnt[ii, jj, kk_][:, None]
    verts = np.stack([xs[ii], ys[jj], zs[kk_]], axis=1) + loc * h

    faces = []
    for axis, (cross, others) in enumerate(crosses):
        e = np.array(np.nonzero(cross)).T  # (m, 3) indices de l'arête (i, j, k) le long de axis
        o0, o1 = others
        ok = (e[:, o0] >= 1) & (e[:, o0] <= cshape[o0] - 1) & (e[:, o1] >= 1) & (e[:, o1] <= cshape[o1] - 1)
        e = e[ok]

        def cell(da, db):
            c = e.copy()
            c[:, o0] -= da
            c[:, o1] -= db
            return idx[c[:, 0], c[:, 1], c[:, 2]]

        q = np.stack([cell(1, 1), cell(0, 1), cell(0, 0), cell(1, 0)], axis=1)
        start_inside = inside[e[:, 0], e[:, 1], e[:, 2]]
        if axis == 1:
            start_inside = ~start_inside
        q = np.where(start_inside[:, None], q, q[:, ::-1])
        q = q[(q >= 0).all(axis=1)]
        faces.append(q)
    faces = np.concatenate(faces, axis=0)
    return verts, faces


def newton_project(pl, V, iters=2, max_step=None):
    for _ in range(iters):
        f = eval_chunked(pl.sdf, V)
        g = np.concatenate([sdf_grad(pl, V[s:s + 100000]) for s in range(0, len(V), 100000)])
        gn = np.maximum(np.einsum("ij,ij->i", g, g), 1e-8)
        step = (f / gn)[:, None] * g
        if max_step:
            L = np.linalg.norm(step, axis=1)
            step *= np.minimum(1.0, max_step / np.maximum(L, 1e-9))[:, None]
        V = V - step
    return V


def build_highres(pl, h):
    V, Fq = surface_nets(pl, h)
    V = newton_project(pl, V, iters=2, max_step=h)
    V[:, 2] = np.maximum(V[:, 2], 0.0)
    me = bpy.data.meshes.new(f"{pl.label}_HI")
    me.from_pydata([tuple(v) for v in V], [], [tuple(int(i) for i in q) for q in Fq])
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(f"{pl.label}_HI", me)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return ob


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def rect_sd_np(P, rect):
    return specs.rect_sd(P, rect)


def enforce_top(ob, pl):
    """Découpe le maillage sur le bord du rectangle utile (là où il dépasse le dessus) puis plafonne les
    sommets du rectangle à dessus + TOP_EPS : aucune facette du rectangle ne dépasse ensuite."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    x0, x1, y0, y1 = pl.rect
    top = pl.top
    lim = top + TOP_EPS
    planes = [((x0, 0, 0), (1, 0, 0), 0), ((x1, 0, 0), (1, 0, 0), 0), ((0, y0, 0), (0, 1, 0), 1), ((0, y1, 0), (0, 1, 0), 1)]
    for co, no, ax in planes:
        bm.faces.ensure_lookup_table()
        sel = []
        for f in bm.faces:
            zs = [v.co.z for v in f.verts]
            if max(zs) <= lim:
                continue
            cs = [v.co[ax] for v in f.verts]
            if min(cs) < co[ax] < max(cs):
                other = 1 - ax
                os_ = [v.co[other] for v in f.verts]
                lo_o, hi_o = (y0, y1) if ax == 0 else (x0, x1)
                if max(os_) >= lo_o - 0.05 and min(os_) <= hi_o + 0.05:
                    sel.append(f)
        if not sel:
            continue
        geom = list(set([v for f in sel for v in f.verts])) + list(set([e for f in sel for e in f.edges])) + sel
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, dist=1e-6)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    moved = 0
    for v in bm.verts:
        P = np.array([[v.co.x, v.co.y, v.co.z]])
        if rect_sd_np(P, pl.rect)[0] <= 1e-5 and v.co.z > lim:
            v.co.z = lim
            moved += 1
        if v.co.z < 0:
            v.co.z = 0.0
    bm.to_mesh(me)
    bm.free()
    me.update()
    return moved


def top_ok(ob, pl, tol=0.2):
    """Contrôle interne (même échantillonnage que le vérificateur, marge plus stricte) du dessus utile."""
    from mathutils.bvhtree import BVHTree
    me = ob.data
    bvh = BVHTree.FromPolygons([tuple(v.co) for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    x0, x1, y0, y1 = pl.rect
    worst = 0.0
    for x in np.arange(x0 + 0.25, x1 - 0.25 + 1e-6, 0.25):
        for y in np.arange(y0 + 0.25, y1 - 0.25 + 1e-6, 0.25):
            hit = bvh.ray_cast(Vector((float(x), float(y), pl.top + 20.0)), Vector((0, 0, -1)))
            if hit[0] is None:
                return False, 9.0
            worst = max(worst, abs(hit[0].z - pl.top))
    return worst <= tol, worst


def decimate_once(hi, pl, name, target_tris, symmetric):
    me = hi.data.copy()
    me.name = name
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    activate(ob)
    cur = tri_count(ob)
    d = ob.modifiers.new("decimate", "DECIMATE")
    d.decimate_type = "COLLAPSE"
    d.ratio = min(1.0, target_tris / max(cur, 1))
    d.use_collapse_triangulate = True
    if symmetric:
        d.use_symmetry = True
        d.symmetry_axis = "X"
    bpy.ops.object.modifier_apply(modifier=d.name)
    t = ob.modifiers.new("tri", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=t.name)
    moved = enforce_top(ob, pl)
    return ob, moved


def make_lod(hi, pl, name, target_tris, max_tris):
    """Décimation déterministe ; si le dessus utile se creuse (> 0,2) ou si le budget est dépassé après découpe,
    on recommence avec une cible légèrement différente (suite fixe d'essais)."""
    tries = []
    for k in range(8):
        tgt = target_tris - 12 * k
        for sym in ((True, False) if pl.symmetric else (False,)):
            ob, moved = decimate_once(hi, pl, name, tgt, sym)
            ok, worst = top_ok(ob, pl)
            ntri = tri_count(ob)
            tries.append({"target": tgt, "symmetric": sym, "tris": ntri, "top_worst": round(worst, 4)})
            if ok and ntri <= max_tris:
                activate(ob)
                bpy.ops.object.shade_smooth()
                return ob, moved, tries
            me = ob.data
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(me)
    raise RuntimeError(f"{name}: aucun essai de décimation ne garde le dessus utile : {tries}")


def unwrap(ob, margin):
    activate(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(62), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


# ---------------------------------------------------------------------------
# Peinture texel par texel
# ---------------------------------------------------------------------------
def rasterize(ob, size):
    me = ob.data
    nv = len(me.vertices)
    V = np.empty(nv * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    nl = len(me.loops)
    UV = np.empty(nl * 2)
    me.uv_layers.active.data.foreach_get("uv", UV)
    UV = UV.reshape(-1, 2)
    LV = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", LV)
    npoly = len(me.polygons)
    LS = np.empty(npoly, np.int64)
    me.polygons.foreach_get("loop_start", LS)
    pos = np.zeros((size, size, 3))
    filled = np.zeros((size, size), bool)
    area3 = 0.0
    area_uv = 0.0
    for p in range(npoly):
        ls = LS[p]
        uv = UV[ls:ls + 3] * size - 0.5
        A, B, C = V[LV[ls]], V[LV[ls + 1]], V[LV[ls + 2]]
        area3 += 0.5 * np.linalg.norm(np.cross(B - A, C - A))
        v0 = uv[1] - uv[0]
        v1 = uv[2] - uv[0]
        den = v0[0] * v1[1] - v1[0] * v0[1]
        area_uv += 0.5 * abs(den)
        if abs(den) < 1e-12:
            continue
        xmin = max(int(math.floor(uv[:, 0].min())), 0)
        xmax = min(int(math.ceil(uv[:, 0].max())), size - 1)
        ymin = max(int(math.floor(uv[:, 1].min())), 0)
        ymax = min(int(math.ceil(uv[:, 1].max())), size - 1)
        if xmax < xmin or ymax < ymin:
            continue
        gx, gy = np.meshgrid(np.arange(xmin, xmax + 1), np.arange(ymin, ymax + 1))
        px = gx.ravel() - uv[0, 0]
        py = gy.ravel() - uv[0, 1]
        l1 = (px * v1[1] - v1[0] * py) / den
        l2 = (v0[0] * py - px * v0[1]) / den
        l0 = 1 - l1 - l2
        m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not m.any():
            continue
        X = gx.ravel()[m]
        Y = gy.ravel()[m]
        pos[Y, X] = l0[m, None] * A + l1[m, None] * B + l2[m, None] * C
        filled[Y, X] = True
    texel_studs = math.sqrt(area3 / max(area_uv, 1e-9))
    return pos, filled, texel_studs


def shade_points(pl, P, texel_studs):
    """Projection sur la SDF + couleur (peinture de la peluche) + occlusion douce + grain de tissu."""
    out = np.zeros((len(P), 3))
    scale = 0.75 if pl.tier == "mini" else 1.0
    hs = np.array([0.06, 0.14, 0.26, 0.42]) * scale
    for s in range(0, len(P), 60000):
        p = P[s:s + 60000]
        f0 = pl.sdf(p)
        g = sdf_grad(pl, p)
        n = g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)
        p1 = p - np.clip(f0, -0.12, 0.12)[:, None] * n
        D = pl.eval_parts(p1)
        cx = specs.Ctx(p1, n, D, texel_studs)
        pl.paint(cx)
        C = cx.C
        occ = np.zeros(len(p))
        for i, hh in enumerate(hs):
            occ += (hh - pl.sdf(p1 + n * hh)) / hh * (0.5 ** i)
        ao = np.clip(1.0 - 0.42 * np.clip(occ, 0, None), 0.6, 1.0)
        n1 = specs.value_noise(p1, 1.8, salt=1)
        n2 = specs.value_noise(p1, 26.0, salt=2)
        n3 = specs.value_noise(p1 * np.array([1.0, 1.0, 3.0]), 14.0, salt=3)
        grain = 1.0 + 0.05 * (n1 - 0.5) + 0.07 * (n2 - 0.5) + 0.04 * (n3 - 0.5)
        out[s:s + 60000] = C * (ao * grain)[:, None]
    return out


def dilate(img, filled, iters):
    img = img.copy()
    filled = filled.copy()
    for _ in range(iters):
        acc = np.zeros_like(img)
        cnt = np.zeros(filled.shape)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            sh_f = np.roll(np.roll(filled, dy, axis=0), dx, axis=1)
            sh_i = np.roll(np.roll(img, dy, axis=0), dx, axis=1)
            acc += sh_i * sh_f[..., None]
            cnt += sh_f
        new = (~filled) & (cnt > 0)
        img[new] = acc[new] / cnt[new][:, None]
        filled = filled | new
        if filled.all():
            break
    if not filled.all():
        img[~filled] = img[filled].mean(axis=0)
    return img


def paint_texture(ob, pl, size, out_png, name):
    pos, filled, texel = rasterize(ob, size)
    P = pos[filled]
    C = shade_points(pl, P, texel)
    img = np.zeros((size, size, 3))
    img[filled] = specs.linear_to_srgb(C)
    img = dilate(img, filled, 24 if size >= 512 else 8)
    img = np.round(np.clip(img, 0, 1) * 255.0) / 255.0  # quantification explicite (PNG 8 bits)
    rgba = np.concatenate([img, np.ones((size, size, 1))], axis=2).astype(np.float32)
    im = bpy.data.images.new(name, width=size, height=size, alpha=False)
    im.colorspace_settings.name = "sRGB"
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = out_png
    im.file_format = "PNG"
    im.save()
    return im, float(filled.mean()), texel


def lod_material(ob, label, img):
    mat = bpy.data.materials.new(f"M_{label}_fabric")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.93
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
    nt.nodes.active = tex
    ob.data.materials.clear()
    ob.data.materials.append(mat)


# ---------------------------------------------------------------------------
# Rig, poses
# ---------------------------------------------------------------------------
def build_rig(pl, lods):
    arm_data = bpy.data.armatures.new(f"{pl.label}_Rig")
    arm = bpy.data.objects.new(f"{pl.label}_Rig", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    activate(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    root = eb.new("Root")
    root.head = (0, 0, 0)
    root.tail = (0, 0, 1.0)
    root.use_deform = True  # ancre les sommets du dessous ; jamais posé (décision 0004)
    heads = dict(pl.belly_bone_heads())
    for k, (h, _o) in pl.secondary.items():
        heads[k] = h
    for name in pl.bone_names()[1:]:
        h = heads[name]
        b = eb.new(name)
        b.head = tuple(h)
        b.tail = tuple(h + np.array([0, 0, 0.6 if pl.tier == "mini" else 0.8]))
        b.parent = root
        b.use_deform = True
    bpy.ops.object.mode_set(mode="OBJECT")
    stats = {}
    for lo in lods:
        me = lo.data
        n = len(me.vertices)
        P = np.empty(n * 3)
        me.vertices.foreach_get("co", P)
        P = P.reshape(-1, 3)
        D = pl.eval_parts(P)
        names, W = pl.skin_weights(P, D)
        for j, bn in enumerate(names):
            vg = lo.vertex_groups.new(name=bn)
            for i in np.nonzero(W[:, j] > 0)[0]:
                vg.add([int(i)], float(W[i, j]), "REPLACE")
        mod = lo.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        lo.parent = arm
        stats[lo.name] = {
            "vertices": n,
            "max_influences": int((W > 0).sum(axis=1).max()),
            "weight_sum_max_error": float(np.abs(W.sum(axis=1) - 1).max()),
            "unweighted_vertices": int(((W > 0).sum(axis=1) == 0).sum()),
        }
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return arm, stats


def pose_matrix(arm, bone_name, spec):
    rest = arm.data.bones[bone_name].matrix_local.copy()
    h = Vector(rest.translation)
    M = rest
    if spec.get("r"):
        axis, ang = spec["r"]
        R = Matrix.Rotation(math.radians(ang), 4, Vector(axis).normalized())
        M = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ M
    if spec.get("t"):
        M = Matrix.Translation(Vector(spec["t"])) @ M
    return M


def apply_pose(arm, pose, scale=1.0):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for bname, sp in pose.items():
        sp2 = {"t": tuple(scale * x for x in sp["t"]) if sp.get("t") else None,
               "r": (sp["r"][0], scale * sp["r"][1]) if sp.get("r") else None}
        arm.pose.bones[bname].matrix = pose_matrix(arm, bname, sp2)
        bpy.context.view_layer.update()


def store_pose_actions(arm, pl):
    arm.animation_data_create()
    for pname, pose in pl.poses.items():
        apply_pose(arm, pose)
        act = bpy.data.actions.new(f"{pl.label}_pose_{pname}")
        act.use_fake_user = True
        arm.animation_data.action = act
        for pb in arm.pose.bones:
            pb.keyframe_insert("location", frame=1)
            pb.keyframe_insert("rotation_quaternion", frame=1)
    arm.animation_data.action = None
    apply_pose(arm, {})


def to_roblox(v):
    """Blender (x, y, z) -> Roblox (x, y = z, z = -y)."""
    return [round(float(v[0]) + 0.0, 4), round(float(v[2]) + 0.0, 4), round(float(-v[1]) + 0.0, 4)]


def pose_library(pl):
    heads = dict(pl.belly_bone_heads())
    for k, (h, _o) in pl.secondary.items():
        heads[k] = h
    lib = {
        "asset_id": pl.asset_id,
        "axes": "roblox_model_space (X largeur, Y haut, Z profondeur ; avant = -Z)",
        "units": "studs",
        "usage": "Pose = translation et rotation (axe, angle en degrés, autour de la tête du bone au repos) "
                 "exprimées en espace modèle Roblox, à convertir dans l'espace parent de chaque Bone. "
                 "Toujours recalculer depuis la pose de référence (Transform = identité) ; ne jamais cumuler. "
                 "Aucune échelle : Bone.Transform est un CFrame.",
        "reference_pose": "rest (toutes transformations identité)",
        "static_bones": ["Root"],
        "lattice_bones": pl.belly_bone_names(),
        "secondary_bones": list(pl.secondary.keys()),
        "side_convention": "*_L côté -X, *_R côté +X (le personnage regarde -Z)",
        "bone_rest_heads": {"Root": [0, 0, 0], **{k: to_roblox(heads[k]) for k in pl.bone_names()[1:]}},
        "poses": {},
    }
    for pname, pose in pl.poses.items():
        out = {}
        for b, sp in pose.items():
            e = {}
            if sp.get("t"):
                e["translation"] = to_roblox(sp["t"])
            if sp.get("r"):
                e["rotation_axis"] = to_roblox(sp["r"][0])
                e["rotation_degrees"] = sp["r"][1]
            out[b] = e
        lib["poses"][pname] = out
    return lib


def collision_json(pl):
    w, d, h = pl.collider_size
    cx, cy = pl.collider_center
    out = {
        "asset_id": pl.asset_id,
        "authority": "server_collider_separate_from_visual_mesh",
        "pivot": "bottom_center",
        "forward_axis": "-Z",
        "dimensions_order_config": "width_depth_height",
        "collider": {
            "shape": "box",
            "size_studs_config": [w, d, h],
            "size_vector3_roblox": [w, h, d],
            "offset_from_pivot_roblox": to_roblox((cx, cy, h / 2.0)),
            "tags": ["FillCollider"],
            "can_collide": True,
            "anchor_after_settle": True,
        },
        "walkable_top": {
            "size_studs": [w, d],
            "height_studs": h,
            "center_roblox": to_roblox((cx, cy, h)),
            "marker": "safe_mint_footprint (affiché après stabilisation)",
        },
        "support_sockets_roblox": [to_roblox((cx + sx * w / 4, cy + sy * d / 4, h)) for sx in (-1, 1) for sy in (-1, 1)]
        + [to_roblox((cx, cy, h))],
        "visual_mesh": {"can_collide": False, "can_query": False, "can_touch": False,
                        "follows_root_client_side": True, "anchored_weld_to_falling_root": False},
        "behavior": pl.behavior,
        "deformation_profile": "plush_soft",
        "size_tier": pl.tier,
        "notes": "Les grandes compressions précèdent l'activation de l'appui garanti ; le visuel déformé n'altère "
                 "jamais ce collider.",
    }
    if pl.behavior_params:
        out["behavior_params"] = pl.behavior_params
    return out


def stable_fbx_uuids():
    """L'exporteur FBX dérive les UID d'objets de hash(str), aléatoire à chaque processus (et `python -I`
    ignore PYTHONHASHSEED). On remplace, dans ce processus seulement, la fonction par un hachage SHA-256
    stable ; la logique de raccourcissement / unicité de l'exporteur est conservée."""
    import io_scene_fbx.fbx_utils as fu

    def _key_to_uuid(uuids, key):
        if isinstance(key, int) and 0 <= key < 2 ** 63:
            uuid = key
        else:
            uuid = int.from_bytes(hashlib.sha256(repr(key).encode("utf-8")).digest()[:8], "little") >> 1
        if uuid > int(1e9):
            t_uuid = uuid % int(1e9)
            if t_uuid not in uuids:
                uuid = t_uuid
        if uuid in uuids:
            inc = 1 if uuid < 2 ** 62 else -1
            while uuid in uuids:
                uuid += inc
                if 0 > uuid >= 2 ** 63:
                    raise ValueError("Unable to generate an UUID for key {}".format(key))
        return fu.UUID(uuid)

    fu._key_to_uuid = _key_to_uuid


def export(pl, arm, near, far, out_import):
    os.makedirs(out_import, exist_ok=True)
    base = os.path.join(out_import, pl.asset_id)
    apply_pose(arm, {})

    def sel(objs):
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]

    common = dict(export_format="GLB", use_selection=True, export_skins=True, export_animations=False,
                  export_yup=True, export_apply=False, export_influence_nb=4, export_all_influences=False,
                  export_def_bones=False, export_texcoords=True, export_normals=True, export_materials="EXPORT")
    sel([arm, near])
    bpy.ops.export_scene.gltf(filepath=base + ".glb", **common)
    sel([arm, far])
    bpy.ops.export_scene.gltf(filepath=base + "_lod1.glb", **common)
    sel([arm, near])
    stable_fbx_uuids()
    bpy.ops.export_scene.fbx(filepath=base + ".fbx", use_selection=True, object_types={"ARMATURE", "MESH"},
                             add_leaf_bones=False, axis_forward="-Z", axis_up="Y", apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0, bake_anim=False,
                             path_mode="COPY", embed_textures=True, mesh_smooth_type="FACE",
                             use_armature_deform_only=False, primary_bone_axis="Y", secondary_bone_axis="X")
    return [base + ".glb", base + "_lod1.glb", base + ".fbx"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mesh_bbox(ob):
    co = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return co.min(axis=0), co.max(axis=0)


def build(key, out_root=ROOT, preview=False):
    pl = specs.PLUSHES[key]()
    bud = dict(specs.BUDGETS[pl.tier])
    tex_near = NEAR_TEX
    if preview:  # itération rapide (jamais utilisée pour les livrables)
        bud["voxel"] *= 1.35
        tex_near = 512
    reset_scene()
    model_dir = os.path.join(out_root, "assets", "source", "models", "plush_v2", specs.MODEL_DIRS[key])
    tex_dir = os.path.join(model_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    hi = build_highres(pl, bud["voxel"])
    hi_tris = 2 * len(hi.data.polygons)
    lo_hi, hi_hi = mesh_bbox(hi)
    lods = []
    moved = {}
    lod_tries = {}
    for name, target, mx in ((f"{pl.label}_LOD0", bud["lod0_target"], bud["lod0_max"]),
                             (f"{pl.label}_LOD1", bud["lod1_target"], bud["lod1_max"])):
        ob, mv, tries = make_lod(hi, pl, name, target, mx)
        lods.append(ob)
        moved[name] = mv
        lod_tries[name] = tries
    near, far = lods
    hi_mesh = hi.data
    bpy.data.objects.remove(hi)
    bpy.data.meshes.remove(hi_mesh)
    unwrap(near, 0.006)
    unwrap(far, 0.016)
    p0 = os.path.join(tex_dir, f"{pl.asset_id}_albedo_1024.png")
    p1 = os.path.join(tex_dir, f"{pl.asset_id}_albedo_256.png")
    img0, cov0, tx0 = paint_texture(near, pl, tex_near, p0, f"{pl.label}_LOD0_albedo")
    img1, cov1, tx1 = paint_texture(far, pl, FAR_TEX, p1, f"{pl.label}_LOD1_albedo")
    lod_material(near, pl.label, img0)
    lod_material(far, pl.label + "_far", img1)

    arm, wstats = build_rig(pl, [near, far])
    store_pose_actions(arm, pl)

    with open(os.path.join(model_dir, "collision.json"), "w", encoding="utf-8") as f:
        json.dump(collision_json(pl), f, ensure_ascii=False, indent=2)
    with open(os.path.join(model_dir, "pose_library.json"), "w", encoding="utf-8") as f:
        json.dump(pose_library(pl), f, ensure_ascii=False, indent=2)

    exports = export(pl, arm, near, far, os.path.join(out_root, "assets", "import", "models"))
    for img in (img0, img1):
        img.pack()
    bpy.context.preferences.filepaths.save_version = 0
    blend_path = os.path.join(model_dir, f"{pl.label}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)

    b0 = mesh_bbox(near)
    info = {
        "asset_id": pl.asset_id,
        "name": pl.name_fr,
        "size_tier": pl.tier,
        "builder": "assets/source/blender/build_plush_v2_small.py",
        "specs": "assets/source/blender/plush_v2_small_specs.py",
        "blend": os.path.relpath(blend_path, out_root),
        "exports": [os.path.relpath(p, out_root) for p in exports],
        "method": "SDF (union lisse de primitives) -> surface nets + projection de Newton -> décimation -> "
                  "découpe/plafonnement du rectangle utile -> UV smart project -> peinture procédurale par texel",
        "grid_step_studs": bud["voxel"],
        "highres_tris": hi_tris,
        "highres_bbox_blender": [[round(float(v), 4) for v in lo_hi], [round(float(v), 4) for v in hi_hi]],
        "lod0_tris": tri_count(near),
        "lod1_tris": tri_count(far),
        "lod0_bbox_blender": [[round(float(v), 4) for v in b0[0]], [round(float(v), 4) for v in b0[1]]],
        "top_clamped_vertices": moved,
        "lod_decimation_tries": lod_tries,
        "bones": pl.bone_names(),
        "weights": wstats,
        "materials_per_mesh": 1,
        "textures": {os.path.basename(p0): {"size": NEAR_TEX, "uv_coverage": round(cov0, 4),
                                            "studs_per_texel": round(tx0, 5)},
                     os.path.basename(p1): {"size": FAR_TEX, "uv_coverage": round(cov1, 4),
                                            "studs_per_texel": round(tx1, 5)}},
        "sha256": {os.path.relpath(p, out_root): sha256(p) for p in exports + [p0, p1]},
        "seed": specs.SEED,
        "blender_version": bpy.app.version_string,
    }
    with open(os.path.join(model_dir, "build_info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: info[k] for k in ("asset_id", "highres_tris", "lod0_tris", "lod1_tris", "lod0_bbox_blender",
                                           "top_clamped_vertices")}, ensure_ascii=False))
    return info


if __name__ == "__main__":
    args = sys.argv[1:]
    out_root = ROOT
    if "--out-root" in args:
        i = args.index("--out-root")
        out_root = os.path.abspath(args[i + 1])
        args = args[:i] + args[i + 2:]
    preview = "--preview" in args
    args = [a for a in args if a != "--preview"]
    which = args[0] if args else "all"
    keys = list(specs.PLUSHES) if which == "all" else which.split(",")
    for k in keys:
        build(k, out_root, preview)
