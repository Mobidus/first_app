"""Construit les GRANDES peluches v2 (Balto, Ronron, Bobine) dans Blender (headless), de façon reproductible.

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/build_plush_v2_big.py [balto|ronron|bobine|all] [--out-root DIR]

--out-root redirige TOUTES les sorties (modèles, exports) vers DIR/<même arborescence> : sert au contrôle
de déterminisme (verify_plush_v2_big.py reconstruit dans un dossier temporaire et compare les empreintes).

Pipeline par peluche (spécifications : plush_v2_big_specs.py) :
 1. champ de distance signée (SDF) échantillonné sur une grille de pas `voxel` puis maillé par
    « surface nets » (numpy) ; sommets reprojetés sur la surface (un pas de Newton) ;
    pas de grille : 0,07 stud (grandes, ~5,6 M points) et 0,10 stud (géante, ~6,5 M points) :
    au-delà, mémoire et temps explosent sans gain visible après décimation (5 000 triangles) ;
 2. recentrage : origine = centre de l'empreinte de la boîte englobante, au sol (pivot bottom_center) ;
 3. LOD0 / LOD1 par décimation (collapse) avec recherche du ratio pour tomber dans le budget ;
    sécurité : aucun sommet au-dessus du dessus du collider dans le rectangle praticable ;
 4. UV (smart project), îlots du dessous réduits (jamais vus), ré-emballage ;
 5. albédo évalué PAR TEXEL : position 3D (rastérisation des triangles UV), reprojection sur la
    surface SDF, normale = gradient, couleur procédurale (tissu, coutures, broderies), occlusion douce
    issue du SDF, bruit de velours ; marges dilatées ; PNG (1 024 / 2 048 px LOD0, 256 px LOD1) ;
 6. rig : Root (ancrage, jamais posé) + Belly_00..Belly_22 + secondaires ; poids normalisés, <= 4 ;
 7. poses (actions dans le .blend), collision.json, pose_library.json, GLB / GLB LOD1 / FBX, .blend,
    build_info.json (avec empreintes SHA-256 des fichiers produits).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from PIL import Image  # noqa: E402

import plush_v2_big_specs as specs  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # filling_up/
SEED = specs.SEED
UNWRAP_METHOD = "MINIMUM_STRETCH"  # ABF / conforme échouent sur certains îlots annulaires (îlots dégénérés)


def log(*a):
    print("[v2big]", *a, flush=True)


# ---------------------------------------------------------------------------
# Scène
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


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


# ---------------------------------------------------------------------------
# SDF -> maillage (surface nets)
# ---------------------------------------------------------------------------
def eval_grid(pl, stride=4):
    """Grille fine évaluée seulement près de la surface : une grille grossière (pas stride * voxel)
    repère les blocs dont un coin est à moins de (diagonale du bloc + 2 voxels) de la surface ; ailleurs
    la valeur fine est remplacée par +-bande avec le signe du coin grossier (signe exact, valeur jamais
    utilisée par les surface nets puisqu'aucun changement de signe n'y a lieu)."""
    lo = np.array(pl.grid_lo, float)
    hi = np.array(pl.grid_hi, float)
    h = pl.voxel
    n = np.floor((hi - lo) / h).astype(int) + 1
    nc = (n - 1) // stride + 2  # coins grossiers (couvrent toute la grille fine)

    def eval_pts(ix, iy, iz):
        P = np.stack([lo[0] + h * ix, lo[1] + h * iy, lo[2] + h * iz], axis=1)
        return chunked(pl.field, P, 200000)

    I, J, K = np.meshgrid(np.arange(nc[0]) * stride, np.arange(nc[1]) * stride, np.arange(nc[2]) * stride, indexing="ij")
    Fc = eval_pts(I.ravel().astype(float), J.ravel().astype(float), K.ravel().astype(float)).reshape(tuple(nc))
    band = stride * h * math.sqrt(3.0) + 2.0 * h
    A = np.abs(Fc)
    S = np.sign(Fc)
    cmin = np.minimum.reduce([A[a:a + nc[0] - 1, b:b + nc[1] - 1, c:c + nc[2] - 1]
                              for a in (0, 1) for b in (0, 1) for c in (0, 1)])
    smin_ = np.minimum.reduce([S[a:a + nc[0] - 1, b:b + nc[1] - 1, c:c + nc[2] - 1]
                               for a in (0, 1) for b in (0, 1) for c in (0, 1)])
    smax_ = np.maximum.reduce([S[a:a + nc[0] - 1, b:b + nc[1] - 1, c:c + nc[2] - 1]
                               for a in (0, 1) for b in (0, 1) for c in (0, 1)])
    need_c = (cmin < band) | (smin_ != smax_)
    ci = [np.minimum(np.arange(n[a]) // stride, nc[a] - 2) for a in range(3)]
    need = need_c[np.ix_(ci[0], ci[1], ci[2])]
    near_c = [np.minimum((np.arange(n[a]) + stride // 2) // stride, nc[a] - 1) for a in range(3)]
    F = (np.sign(Fc[np.ix_(near_c[0], near_c[1], near_c[2])]) * band).astype(np.float64)
    idx = np.nonzero(need)
    F[idx] = eval_pts(idx[0].astype(float), idx[1].astype(float), idx[2].astype(float))
    return F, lo, h, n, float(need.mean())


def surface_nets(F, lo, h):
    nx, ny, nz = F.shape
    inside = F < 0
    ncx, ncy, ncz = nx - 1, ny - 1, nz - 1
    ncell = ncx * ncy * ncz
    sx = np.zeros(ncell)
    sy = np.zeros(ncell)
    sz = np.zeros(ncell)
    cnt = np.zeros(ncell)

    def cid(i, j, k):
        return (i * ncy + j) * ncz + k

    edges = []
    for axis in range(3):
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[axis] = slice(0, -1)
        sl1[axis] = slice(1, None)
        F0 = F[tuple(sl0)]
        F1 = F[tuple(sl1)]
        cross = inside[tuple(sl0)] != inside[tuple(sl1)]
        idx = np.nonzero(cross)
        f0 = F0[idx]
        f1 = F1[idx]
        t = f0 / (f0 - f1)
        pt = np.stack([idx[0], idx[1], idx[2]], axis=1).astype(float)
        pt[:, axis] += t
        pos = lo + pt * h
        i, j, k = idx
        # cellules adjacentes à l'arête
        others = [a for a in range(3) if a != axis]
        offs = [(0, 0), (-1, 0), (0, -1), (-1, -1)]
        for (da, db) in offs:
            c = [i.copy(), j.copy(), k.copy()]
            c[others[0]] = c[others[0]] + da
            c[others[1]] = c[others[1]] + db
            ok = (c[0] >= 0) & (c[0] < ncx) & (c[1] >= 0) & (c[1] < ncy) & (c[2] >= 0) & (c[2] < ncz)
            cc = cid(c[0][ok], c[1][ok], c[2][ok])
            sx += np.bincount(cc, weights=pos[ok, 0], minlength=ncell)
            sy += np.bincount(cc, weights=pos[ok, 1], minlength=ncell)
            sz += np.bincount(cc, weights=pos[ok, 2], minlength=ncell)
            cnt += np.bincount(cc, minlength=ncell)
        edges.append((axis, i, j, k, f0 < 0))
    active = np.nonzero(cnt > 0)[0]
    vmap = np.full(ncell, -1, dtype=np.int64)
    vmap[active] = np.arange(len(active))
    V = np.stack([sx[active], sy[active], sz[active]], axis=1) / cnt[active][:, None]
    faces = []
    for axis, i, j, k, inside0 in edges:
        others = [a for a in range(3) if a != axis]
        c = [i, j, k]
        a_, b_ = c[others[0]], c[others[1]]
        lim_a = (ncx, ncy, ncz)[others[0]]
        lim_b = (ncx, ncy, ncz)[others[1]]
        ok = (a_ >= 1) & (a_ < lim_a) & (b_ >= 1) & (b_ < lim_b)
        if axis == 0:
            ok &= i < ncx
        elif axis == 1:
            ok &= j < ncy
        else:
            ok &= k < ncz
        ii, jj, kk, ins = i[ok], j[ok], k[ok], inside0[ok]

        def cell(da, db):
            cc = [ii.copy(), jj.copy(), kk.copy()]
            cc[others[0]] = cc[others[0]] + da
            cc[others[1]] = cc[others[1]] + db
            return vmap[cid(cc[0], cc[1], cc[2])]
        # ordre (a-1,b-1) -> (a,b-1) -> (a,b) -> (a-1,b) : normale = e_a x e_b
        q = np.stack([cell(-1, -1), cell(0, -1), cell(0, 0), cell(-1, 0)], axis=1)
        # e_a x e_b = +axe pour (y,z)->x, (x,z)->-y, (x,y)->z
        sign = 1 if axis != 1 else -1
        flip = ins if sign > 0 else ~ins
        q = np.where(flip[:, None], q, q[:, ::-1])
        faces.append(q)
    Q = np.concatenate(faces, axis=0)
    Q = Q[(Q >= 0).all(axis=1)]
    return V, Q


def grad(pl, P, eps=0.015):
    k = np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], float)
    g = np.zeros_like(P)
    fs = 0.0
    for kk in k:
        f = pl.field(P + eps * kk)
        g += kk[None, :] * f[:, None]
        fs = fs + f
    return g / (4 * eps), fs / 4.0


def project(pl, P, iters=1):
    for _ in range(iters):
        g, f = grad(pl, P)
        g2 = np.einsum("ij,ij->i", g, g) + 1e-9
        step = np.clip(f / g2, -0.3, 0.3)
        P = P - step[:, None] * g
    return P


def chunked(fn, P, size=250000):
    outs = [fn(P[i:i + size]) for i in range(0, len(P), size)]
    if isinstance(outs[0], tuple):
        return tuple(np.concatenate([o[k] for o in outs]) for k in range(len(outs[0])))
    return np.concatenate(outs)


def build_highres(pl):
    t0 = time.time()
    F, lo, h, n, frac = eval_grid(pl)
    log(pl.label, "grid", tuple(int(v) for v in n), f"{n.prod() / 1e6:.1f} M pts", f"exact {frac:.1%}",
        f"{time.time() - t0:.1f}s")
    V, Q = surface_nets(F, lo, h)
    del F
    V = chunked(lambda p: project(pl, p, 2), V)
    V[:, 2] = np.maximum(V[:, 2], 0.0)
    log(pl.label, "surface nets", len(V), "verts", len(Q), "quads", f"{time.time() - t0:.1f}s")
    me = bpy.data.meshes.new(f"{pl.label}_HI")
    me.from_pydata(V.tolist(), [], Q.tolist())
    me.update()
    ob = bpy.data.objects.new(f"{pl.label}_HI", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def mesh_co(ob):
    me = ob.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def set_co(ob, co):
    ob.data.vertices.foreach_set("co", co.ravel())
    ob.data.update()


# ---------------------------------------------------------------------------
# LOD
# ---------------------------------------------------------------------------
def decimate_to(hi, name, target, lo_ok, hi_ok):
    src_tris = tri_count(hi)
    ratio = target / src_tris
    ob = None
    for attempt in range(6):
        if ob is not None:
            m = ob.data
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(m)
        me = hi.data.copy()
        me.name = name
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        activate(ob)
        d = ob.modifiers.new("decimate", "DECIMATE")
        d.decimate_type = "COLLAPSE"
        d.ratio = min(1.0, ratio)
        d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=d.name)
        t = ob.modifiers.new("tri", "TRIANGULATE")
        bpy.ops.object.modifier_apply(modifier=t.name)
        tc = tri_count(ob)
        if lo_ok <= tc <= hi_ok:
            break
        ratio *= target / max(tc, 1)
    bpy.ops.object.shade_smooth()
    return ob


def clamp_top(pl, ob, shift):
    """Sécurité de jeu : aucun sommet au-dessus du dessus dans le rectangle praticable, aucun sous le sol."""
    co = mesh_co(ob)
    P = co - shift
    inside = pl.rect_out(P) <= 0.0
    over = inside & (co[:, 2] > pl.top)
    n_over = int(over.sum())
    max_over = float((co[over, 2] - pl.top).max()) if n_over else 0.0
    co[over, 2] = pl.top
    co[:, 2] = np.maximum(co[:, 2], 0.0)
    set_co(ob, co)
    return {"vertices_clamped": n_over, "max_excess_before_clamp_studs": round(max_over, 4)}


# ---------------------------------------------------------------------------
# UV
# ---------------------------------------------------------------------------
def unwrap(ob, tex_size):
    activate(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(62), island_margin=0.0, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    # la projection plane de smart project superpose ce qui se cache derrière (défenses devant le visage...) :
    # on garde ses découpes comme coutures UV puis on déplie chaque îlot (ABF), sans recouvrement
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.seams_from_islands()
    bpy.ops.uv.unwrap(method=UNWRAP_METHOD, margin=0.0)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    # îlots tournés vers le sol : réduits (jamais vus en jeu) -> plus de texels pour le dessus et les flancs
    bm = bmesh.from_edit_mesh(ob.data)
    uvl = bm.loops.layers.uv.verify()
    bm.faces.ensure_lookup_table()
    seen = set()
    for f in bm.faces:
        if f.index in seen:
            continue
        # composante connexe en UV (arêtes partagées avec UV identiques)
        comp = [f]
        seen.add(f.index)
        stack = [f]
        while stack:
            g = stack.pop()
            for e in g.edges:
                for g2 in e.link_faces:
                    if g2.index in seen:
                        continue
                    la = [lp for lp in g.loops if lp.edge == e][0]
                    lb = [lp for lp in g2.loops if lp.edge == e][0]
                    # l'arête est cousue en UV si les deux extrémités coïncident
                    a0, a1 = la[uvl].uv, la.link_loop_next[uvl].uv
                    b0, b1 = lb[uvl].uv, lb.link_loop_next[uvl].uv
                    if ((a0 - b1).length < 1e-6 and (a1 - b0).length < 1e-6) or \
                            ((a0 - b0).length < 1e-6 and (a1 - b1).length < 1e-6):
                        seen.add(g2.index)
                        comp.append(g2)
                        stack.append(g2)
        nz = sum(g.normal.z * g.calc_area() for g in comp) / max(sum(g.calc_area() for g in comp), 1e-9)
        fac = 0.3 if nz < -0.6 else (1.45 if nz > 0.75 else 1.0)  # dessous réduit, dessus praticable agrandi
        if fac != 1.0:
            loops = [lp for g in comp for lp in g.loops]
            c = sum((lp[uvl].uv for lp in loops), Vector((0, 0))) / len(loops)
            for lp in loops:
                lp[uvl].uv = c + (lp[uvl].uv - c) * fac
    bmesh.update_edit_mesh(ob.data)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, rotate_method="ANY", shape_method="CONCAVE", margin=6.0 / tex_size)
    bpy.ops.object.mode_set(mode="OBJECT")


def texel_density(ob, tex_size, shift, pl):
    """px/stud moyen sur les faces du dessus praticable (normale z > 0,8, dans le rectangle)."""
    me = ob.data
    me.calc_loop_triangles()
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    co = mesh_co(ob)
    a3 = a2 = 0.0
    for lt in me.loop_triangles:
        v = [co[i] for i in lt.vertices]
        nrm = np.cross(v[1] - v[0], v[2] - v[0])
        area = 0.5 * np.linalg.norm(nrm)
        if area <= 0 or nrm[2] / (2 * area) < 0.8:
            continue
        c = (v[0] + v[1] + v[2]) / 3 - shift
        if pl.rect_out(c[None, :])[0] > 0:
            continue
        u = [uv[i] for i in lt.loops]
        auv = 0.5 * abs((u[1][0] - u[0][0]) * (u[2][1] - u[0][1]) - (u[2][0] - u[0][0]) * (u[1][1] - u[0][1]))
        a3 += area
        a2 += auv
    return float(math.sqrt(a2 / max(a3, 1e-9)) * tex_size)


# ---------------------------------------------------------------------------
# Albédo par texel
# ---------------------------------------------------------------------------
def rasterize(ob, size):
    me = ob.data
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    tv = np.empty(nt * 3, dtype=np.int64)
    tl = np.empty(nt * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tv)
    me.loop_triangles.foreach_get("loops", tl)
    tv = tv.reshape(-1, 3)
    tl = tl.reshape(-1, 3)
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2) * size - 0.5
    tri_id = np.full((size, size), -1, dtype=np.int64)
    bary = np.zeros((size, size, 3))
    interior = np.zeros((size, size), dtype=bool)
    overlap = 0
    for t in range(nt):
        p = uv[tl[t]]
        x0 = max(int(math.floor(p[:, 0].min())) - 1, 0)
        x1 = min(int(math.ceil(p[:, 0].max())) + 1, size - 1)
        y0 = max(int(math.floor(p[:, 1].min())) - 1, 0)
        y1 = min(int(math.ceil(p[:, 1].max())) + 1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(d) < 1e-12:
            continue
        l0 = ((p[1, 1] - p[2, 1]) * (X - p[2, 0]) + (p[2, 0] - p[1, 0]) * (Y - p[2, 1])) / d
        l1 = ((p[2, 1] - p[0, 1]) * (X - p[2, 0]) + (p[0, 0] - p[2, 0]) * (Y - p[2, 1])) / d
        l2 = 1 - l0 - l1
        ins = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not ins.any():
            continue
        ys, xs = Y[ins], X[ins]
        strict = (l0 > 0.05) & (l1 > 0.05) & (l2 > 0.05)
        sy, sx = Y[strict], X[strict]
        overlap += int(interior[sy, sx].sum())
        interior[sy, sx] = True
        tri_id[ys, xs] = t
        bary[ys, xs] = np.stack([l0[ins], l1[ins], l2[ins]], axis=1)
    rasterize.last_overlap = overlap / max(int((tri_id >= 0).sum()), 1)
    return tri_id, bary, tv


def sdf_ao(pl, P, N):
    ao = np.zeros(len(P))
    w = 1.0
    for i in range(1, 5):
        hgt = 0.22 * i
        d = pl.field(P + N * hgt)
        ao += w * np.clip(hgt - d, 0, None) / hgt
        w *= 0.5
    return np.clip(1.0 - 0.55 * ao, 0.0, 1.0)


def shade_texels(pl, Pd):
    """Couleur linéaire des texels (positions en coordonnées de conception)."""
    g, f = grad(pl, Pd)
    g2 = np.einsum("ij,ij->i", g, g) + 1e-9
    Pd = Pd - np.clip(f / g2, -0.3, 0.3)[:, None] * g
    N = g / np.sqrt(g2)[:, None]
    _F, D = pl.field(Pd, parts=True)
    C = pl.color_fn(Pd, N, D)
    ao = sdf_ao(pl, Pd, N)
    # velours / feutre : marbrure douce + grain fin, toujours à graine fixe
    m1 = specs.NOISE.fbm(Pd, 0.7, 3)
    m2 = specs.NOISE(Pd, 11.0)
    fab = (1.0 + 0.07 * (m1 - 0.5)) * (1.0 + 0.06 * (m2 - 0.5))
    C = C * fab[:, None] * (0.62 + 0.38 * ao)[:, None]
    return np.clip(C, 0.0, 1.0)


def bake_albedo(pl, ob, size, shift, out_png):
    t0 = time.time()
    tri_id, bary, tv = rasterize(ob, size)
    co = mesh_co(ob) - shift
    filled = tri_id >= 0
    ids = tri_id[filled]
    b = bary[filled]
    P = (co[tv[ids, 0]] * b[:, 0:1] + co[tv[ids, 1]] * b[:, 1:2] + co[tv[ids, 2]] * b[:, 2:3])
    C = chunked(lambda p: shade_texels(pl, p), P, 200000)
    img = np.zeros((size, size, 3))
    img[filled] = C
    # dilatation des marges (texels non couverts <- moyenne des voisins couverts)
    mask = filled.copy()
    for _ in range(12):
        acc = np.zeros_like(img)
        n = np.zeros((size, size))
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            sm = np.roll(np.roll(mask, dy, 0), dx, 1)
            si = np.roll(np.roll(img, dy, 0), dx, 1)
            acc += si * sm[..., None]
            n += sm
        new = (~mask) & (n > 0)
        img[new] = acc[new] / n[new][:, None]
        mask |= new
    img[~mask] = img[mask].mean(axis=0)
    srgb = np.where(img <= 0.0031308, img * 12.92, 1.055 * np.power(img, 1 / 2.4) - 0.055)
    arr = np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)[::-1]  # ligne 0 du PNG = haut (v = 1)
    Image.fromarray(arr).save(out_png, format="PNG", optimize=False, compress_level=9)
    cover = float(filled.mean())
    ov = rasterize.last_overlap
    log(pl.label, "albedo", size, f"cover={cover:.2f}", f"uv_overlap={ov:.4f}", f"{time.time() - t0:.1f}s")
    return cover, ov


def make_material(ob, label, png):
    img = bpy.data.images.load(png)
    img.colorspace_settings.name = "sRGB"
    mat = bpy.data.materials.new(f"M_{label}_fabric")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return img


# ---------------------------------------------------------------------------
# Rig
# ---------------------------------------------------------------------------
def build_rig(pl, lods, shift):
    arm_data = bpy.data.armatures.new(f"{pl.label}_Rig")
    arm = bpy.data.objects.new(f"{pl.label}_Rig", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    activate(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    root = eb.new("Root")
    root.head = (0, 0, 0)
    root.tail = (0, 0, 1.0)
    root.use_deform = True  # ancrage des sommets du dessous ; jamais posé (décision 0004)
    for name, h in pl.belly_bone_heads().items():
        hh = h + shift
        b = eb.new(name)
        b.head = tuple(hh)
        b.tail = tuple(hh + np.array([0, 0, 0.8]))
        b.parent = root
        b.use_deform = True
    for name, (h, _o) in pl.secondary.items():
        hh = h + shift
        b = eb.new(name)
        b.head = tuple(hh)
        b.tail = tuple(hh + np.array([0, 0, 0.8]))
        b.parent = root
        b.use_deform = True
    bpy.ops.object.mode_set(mode="OBJECT")
    stats = {}
    for lo in lods:
        P = mesh_co(lo) - shift
        names, W = pl.skin_weights(P)
        for j, bn in enumerate(names):
            vg = lo.vertex_groups.new(name=bn)
            for i in np.nonzero(W[:, j] > 0)[0]:
                vg.add([int(i)], float(W[i, j]), "REPLACE")
        mod = lo.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        lo.parent = arm
        stats[lo.name] = {
            "vertices": len(P),
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


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------
def to_roblox(v):
    """Blender (x, y, z) -> Roblox (x, y=z, z=-y)."""
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(float(-v[1]), 4)]


def pose_library(pl, shift):
    heads = {k: v + shift for k, v in pl.belly_bone_heads().items()}
    for k, (h, _o) in pl.secondary.items():
        heads[k] = h + shift
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
        "bone_rest_heads": {"Root": [0, 0, 0], **{k: to_roblox(v) for k, v in heads.items()}},
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


def collision_json(pl, shift):
    w, d, h = pl.collider_size
    cx, cy = pl.rect_center[0] + shift[0], pl.rect_center[1] + shift[1]
    top = h
    return {
        "asset_id": pl.asset_id,
        "authority": "server_collider_separate_from_visual_mesh",
        "pivot": "bottom_center",
        "forward_axis": "-Z",
        "dimensions_order_config": "width_depth_height",
        "size_tier": pl.size_tier,
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
            "size_studs": pl.walkable,
            "height_studs": top,
            "center_roblox": to_roblox((cx, cy, top)),
            "marker": "safe_mint_footprint (affiché après stabilisation)",
        },
        "support_sockets_roblox": [to_roblox((cx + sx * w / 4, cy + sy * d / 4, top))
                                   for sx in (-1, 1) for sy in (-1, 1)] + [to_roblox((cx, cy, top))],
        "visual_mesh": {"can_collide": False, "can_query": False, "can_touch": False,
                        "follows_root_client_side": True, "anchored_weld_to_falling_root": False},
        "visual_envelope_studs": pl.envelope,
        "behavior": pl.behavior,
        "deformation_profile": "plush_soft",
        "notes": "Les grandes compressions précèdent l'activation de l'appui garanti ; le visuel déformé n'altère "
                 "jamais ce collider. Tête, membres, queue et jet d'eau dépassent sur les côtés (enveloppe visuelle) "
                 "hors du rectangle praticable.",
    }


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
                  export_def_bones=False, export_texcoords=True, export_normals=True, export_materials="EXPORT",
                  export_image_format="AUTO")
    sel([arm, near])
    bpy.ops.export_scene.gltf(filepath=base + ".glb", **common)
    sel([arm, far])
    bpy.ops.export_scene.gltf(filepath=base + "_lod1.glb", **common)
    sel([arm, near])
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


# ---------------------------------------------------------------------------
def build(key, out_root=ROOT):
    t0 = time.time()
    np.random.seed(SEED)
    pl = specs.PLUSHES[key]()
    reset_scene()
    model_dir = os.path.join(out_root, "assets", "source", "models", "plush_v2", specs.MODEL_DIRS[key])
    tex_dir = os.path.join(model_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    hi = build_highres(pl)
    hi_tris = tri_count(hi) * 1  # quads
    co = mesh_co(hi)
    mn, mx = co.min(axis=0), co.max(axis=0)
    shift = np.array([-0.5 * (mn[0] + mx[0]), -0.5 * (mn[1] + mx[1]), 0.0])
    set_co(hi, co + shift)
    log(pl.label, "bbox design", np.round(mx - mn, 3).tolist(), "shift", np.round(shift, 4).tolist())

    near = decimate_to(hi, f"{pl.label}_LOD0", pl.lod0_target, pl.lod0_range[0] + 200, pl.lod0_range[1] - 100)
    far = decimate_to(hi, f"{pl.label}_LOD1", pl.lod1_target, int(pl.lod1_max * 0.8), pl.lod1_max)
    hi_mesh = hi.data
    bpy.data.objects.remove(hi)
    bpy.data.meshes.remove(hi_mesh)
    clamp0 = clamp_top(pl, near, shift)
    clamp1 = clamp_top(pl, far, shift)
    unwrap(near, pl.tex0)
    unwrap(far, pl.tex1)
    dens = texel_density(near, pl.tex0, shift, pl)
    log(pl.label, "LOD0", tri_count(near), "LOD1", tri_count(far), f"top texel density {dens:.1f} px/stud")

    png0 = os.path.join(tex_dir, f"{pl.asset_id}_albedo_{pl.tex0}.png")
    png1 = os.path.join(tex_dir, f"{pl.asset_id}_albedo_{pl.tex1}.png")
    cover0, ov0 = bake_albedo(pl, near, pl.tex0, shift, png0)
    cover1, ov1 = bake_albedo(pl, far, pl.tex1, shift, png1)
    img0 = make_material(near, pl.label, png0)
    img1 = make_material(far, pl.label + "_far", png1)

    arm, wstats = build_rig(pl, [near, far], shift)
    store_pose_actions(arm, pl)

    with open(os.path.join(model_dir, "collision.json"), "w", encoding="utf-8") as f:
        json.dump(collision_json(pl, shift), f, ensure_ascii=False, indent=2)
    with open(os.path.join(model_dir, "pose_library.json"), "w", encoding="utf-8") as f:
        json.dump(pose_library(pl, shift), f, ensure_ascii=False, indent=2)

    exports = export(pl, arm, near, far, os.path.join(out_root, "assets", "import", "models"))
    for img in (img0, img1):
        img.pack()
    bpy.context.preferences.filepaths.save_version = 0
    blend_path = os.path.join(model_dir, f"{pl.label}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)

    co0 = mesh_co(near)
    info = {
        "asset_id": pl.asset_id,
        "name": pl.name_fr,
        "size_tier": pl.size_tier,
        "blend": os.path.relpath(blend_path, out_root),
        "exports": [os.path.relpath(p, out_root) for p in exports],
        "method": "SDF (union lisse de primitives) -> surface nets (numpy) -> décimation collapse -> UV smart "
                  "project -> albédo évalué par texel sur la surface SDF (Blender ne cuit rien) -> rig 1+9+n",
        "voxel_size_studs": pl.voxel,
        "voxel_choice": ("0,07 stud pour les grandes (grille ~5,6 M points, ~1 min) ; 0,10 pour la géante (~6,5 M "
                         "points). Les détails fins (coutures, broderies) ne dépendent pas du voxel : ils sont "
                         "évalués par texel. 0,05 doublerait la mémoire (x2,7) sans gain après décimation."),
        "highres_quads": hi_tris,
        "lod0_tris": tri_count(near),
        "lod1_tris": tri_count(far),
        "lod0_bbox_studs_wdh": [round(float(v), 3) for v in (co0.max(axis=0) - co0.min(axis=0))],
        "design_to_pivot_shift_studs": [round(float(v), 4) for v in shift],
        "top_clamp_lod0": clamp0,
        "top_clamp_lod1": clamp1,
        "bones": pl.bone_names(),
        "secondary_bones": list(pl.secondary.keys()),
        "weights": wstats,
        "materials_per_mesh": 1,
        "textures": [os.path.basename(png0), os.path.basename(png1)],
        "texture_cover_fraction": {"lod0": round(cover0, 3), "lod1": round(cover1, 3)},
        "uv_overlap_fraction": {"lod0": round(ov0, 5), "lod1": round(ov1, 5)},
        "top_texel_density_px_per_stud_lod0": round(dens, 1),
        "seed": SEED,
        "blender_version": bpy.app.version_string,
        "build_seconds": None,
        "sha256": {os.path.relpath(p, out_root): sha256(p) for p in exports + [png0, png1]},
    }
    info["build_seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(model_dir, "build_info.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in info.items() if k != "build_seconds"}, f, ensure_ascii=False, indent=2)
    log(json.dumps({k: info[k] for k in ("asset_id", "lod0_tris", "lod1_tris", "lod0_bbox_studs_wdh",
                                         "top_texel_density_px_per_stud_lod0", "build_seconds")}, ensure_ascii=False))
    return info


if __name__ == "__main__":
    args = sys.argv[1:]
    out_root = ROOT
    if "--out-root" in args:
        i = args.index("--out-root")
        out_root = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    which = args[0] if args else "all"
    keys = list(specs.PLUSHES) if which == "all" else [which]
    for k in keys:
        build(k, out_root)
