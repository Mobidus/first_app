"""Kit de modélisation paramétrique pour les props de salle FILLING UP (Blender bpy/bmesh, headless).

Briques : dalles arrondies par anneaux (loft), tours (lathe), tubes balayés, bandes enveloppantes
(ruban, nervures), prismes, booléens EXACT, et mappeurs UV vers l'atlas de famille.
Conventions (décision 0003) : 1 unité Blender = 1 stud ; X = largeur, Y = profondeur (avant
Roblox -Z = +Y Blender), Z = hauteur ; pivot bottom_center = origine, au sol.
"""
from __future__ import annotations

import math

import bpy  # bpy doit précéder bmesh
import bmesh
from mathutils import Matrix, Vector

import reception_atlas as atlas


class Q:
    """Niveau de détail : nombre de segments et détails optionnels."""

    def __init__(self, lod):
        self.lod = lod
        self.corner = 4 if lod == 0 else 1
        self.bev = 3 if lod == 0 else 1
        self.round = 40 if lod == 0 else 12
        self.small = 16 if lod == 0 else 6
        self.tube = 8 if lod == 0 else 4
        self.detail = lod == 0


def clamp01(t):
    return 0.0 if t < 0 else (1.0 if t > 1 else t)


# --- contours 2D -----------------------------------------------------------------
def rrect(hw, hd, r, seg):
    """Rectangle arrondi (CCW vu de +Z), 4*(seg+1) points."""
    if seg <= 0:
        return [(hw, hd), (-hw, hd), (-hw, -hd), (hw, -hd)]
    r = max(0.005, min(r, hw - 1e-3, hd - 1e-3))
    pts = []
    for cx, cy, a0 in ((hw - r, hd - r, 0), (-hw + r, hd - r, 90), (-hw + r, -hd + r, 180), (hw - r, -hd + r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90.0 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def bev_rings(z0, z1, rb, rt, nb, nt, mids=0):
    """Anneaux (inset, z) d'une dalle à biseaux arrondis bas (rb) et haut (rt) ; `mids` anneaux
    intermédiaires (utiles pour un bombé latéral visible)."""
    rings = []
    if rb > 0 and nb > 0:
        for i in range(nb + 1):
            a = (math.pi / 2) * i / nb
            rings.append((rb * (1 - math.sin(a)), z0 + rb * (1 - math.cos(a))))
    else:
        rings.append((0.0, z0))
    za, zb = rings[-1][1], (z1 - rt if (rt > 0 and nt > 0) else z1)
    for k in range(1, mids + 1):
        rings.append((0.0, za + (zb - za) * k / (mids + 1)))
    if rt > 0 and nt > 0:
        for i in range(nt + 1):
            a = (math.pi / 2) * i / nt
            rings.append((rt * (1 - math.cos(a)), z1 - rt + rt * math.sin(a)))
    else:
        rings.append((0.0, z1))
    return rings


def add_bulge(rings, amount, z0, z1):
    """Bombé latéral : inset + amount * ((z - zm)/demi-hauteur)^2 (0 au milieu)."""
    zm, hh = (z0 + z1) / 2, (z1 - z0) / 2
    return [(r[0] + amount * ((r[1] - zm) / hh) ** 2, r[1]) + tuple(r[2:]) for r in rings]


def interp_inset(rings, z):
    for a, b in zip(rings[:-1], rings[1:]):
        if a[1] <= z <= b[1] and b[1] > a[1]:
            t = (z - a[1]) / (b[1] - a[1])
            return a[0] + (b[0] - a[0]) * t
    return rings[0][0] if z < rings[0][1] else rings[-1][0]


# --- primitives bmesh --------------------------------------------------------------
def solid(bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def loft(hw, hd, R, rings, seg, cx=0.0, cy=0.0, cap0=True, cap1=True, outline=None, min_corner=1):
    """Empile des contours rectangles arrondis ; rings = [(inset, z[, dr])].

    min_corner=2 pour les corps qui portent le dessus praticable : un chanfrein unique (LOD1)
    rognerait les coins du rectangle walkable_top."""
    seg = max(seg, min_corner) if seg > 0 else seg
    bm = bmesh.new()
    loops = []
    for r in rings:
        inset, z = r[0], r[1]
        dr = r[2] if len(r) > 2 else 0.0
        if outline is not None:
            pts = outline(inset, z)
        else:
            pts = rrect(hw - inset, hd - inset, max(R - inset + dr, 0.02), seg)
        loops.append([bm.verts.new((cx + x, cy + y, z)) for x, y in pts])
    n = len(loops[0])
    for a, b in zip(loops[:-1], loops[1:]):
        for i in range(n):
            bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    if cap0:
        bm.faces.new(list(reversed(loops[0])))
    if cap1:
        bm.faces.new(loops[-1])
    return solid(bm) if (cap0 and cap1) else bm


def slab(hw, hd, z0, z1, R, rb, rt, q, cx=0.0, cy=0.0, bulge=0.0, mids=0, min_corner=1):
    rings = bev_rings(z0, z1, rb, rt, q.bev if rb > 0 else 0, q.bev if rt > 0 else 0, mids)
    if bulge:
        rings = add_bulge(rings, bulge, z0, z1)
    return loft(hw, hd, R, rings, q.corner, cx, cy, min_corner=min_corner)


def lathe(profile, n, center=(0, 0, 0), cap0=True, cap1=True, a0=0.0, closed_profile=False):
    """Révolution autour de Z d'un profil [(r, z)] ; r = 0 -> pôle ; closed_profile -> tore."""
    bm = bmesh.new()
    cx, cy, cz = center
    loops = []
    for r, z in profile:
        if r < 1e-6:
            loops.append([bm.verts.new((cx, cy, cz + z))])
        else:
            loops.append([bm.verts.new((cx + r * math.cos(a0 + 2 * math.pi * i / n),
                                        cy + r * math.sin(a0 + 2 * math.pi * i / n), cz + z)) for i in range(n)])
    for a, b in zip(loops[:-1], loops[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for i in range(n):
                bm.faces.new((a[0], b[(i + 1) % n], b[i])[::-1])
        elif len(b) == 1:
            for i in range(n):
                bm.faces.new((a[i], a[(i + 1) % n], b[0]))
        else:
            for i in range(n):
                bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    if closed_profile:
        a, b = loops[-1], loops[0]
        for i in range(n):
            bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
        return solid(bm)
    if cap0 and len(loops[0]) > 1:
        bm.faces.new(list(reversed(loops[0])))
    if cap1 and len(loops[-1]) > 1:
        bm.faces.new(loops[-1])
    closed = (cap0 or len(loops[0]) == 1) and (cap1 or len(loops[-1]) == 1)
    return solid(bm) if closed else bm


def prism(outline, z0, z1):
    """Prisme droit d'un contour 2D CCW."""
    bm = bmesh.new()
    a = [bm.verts.new((x, y, z0)) for x, y in outline]
    b = [bm.verts.new((x, y, z1)) for x, y in outline]
    n = len(outline)
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    return solid(bm)


def ring_prism(outer, inner, z0, z1):
    """Cadre : anneau entre deux contours CCW de même nombre de points, extrudé en Z."""
    bm = bmesh.new()
    ob = [bm.verts.new((x, y, z0)) for x, y in outer]
    ot = [bm.verts.new((x, y, z1)) for x, y in outer]
    ib = [bm.verts.new((x, y, z0)) for x, y in inner]
    it = [bm.verts.new((x, y, z1)) for x, y in inner]
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((ob[i], ob[j], ot[j], ot[i]))
        bm.faces.new((ib[j], ib[i], it[i], it[j]))
        bm.faces.new((ot[i], ot[j], it[j], it[i]))
        bm.faces.new((ob[j], ob[i], ib[i], ib[j]))
    return solid(bm)


def orient(bm, axis):
    """Réoriente une pièce construite en XY extrudée en Z (permutations circulaires, sans miroir).

    'x' : extrusion le long de X ; local x -> monde Y, local y -> monde Z.
    'y' : extrusion le long de Y ; local x -> monde Z, local y -> monde X.
    """
    if axis == "x":
        M = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    elif axis == "y":
        M = Matrix(((0, 1, 0, 0), (0, 0, 1, 0), (1, 0, 0, 0), (0, 0, 0, 1)))
    else:
        return bm
    return transform(bm, M)


def tube(path, radius, nv, closed=False, up=(0, 0, 1), caps=True):
    """Tube balayé le long d'une polyligne 3D (repère par transport parallèle)."""
    P = [Vector(p) for p in path]
    n = len(P)
    T = []
    for i in range(n):
        if closed:
            a, b = P[(i - 1) % n], P[(i + 1) % n]
        else:
            a, b = P[max(i - 1, 0)], P[min(i + 1, n - 1)]
        T.append((b - a).normalized())
    upv = Vector(up)
    ref = upv if abs(T[0].dot(upv)) < 0.95 else Vector((1, 0, 0))
    N = [(ref - T[0] * ref.dot(T[0])).normalized()]
    for i in range(1, n):
        v = N[-1] - T[i] * N[-1].dot(T[i])
        N.append(v.normalized())
    bm = bmesh.new()
    rings = []
    rr = radius if callable(radius) else (lambda t, r=radius: r)
    for i in range(n):
        B = T[i].cross(N[i])
        r = rr(i / max(n - 1, 1))
        rings.append([bm.verts.new(P[i] + r * (math.cos(2 * math.pi * k / nv) * N[i] +
                                               math.sin(2 * math.pi * k / nv) * B)) for k in range(nv)])
    segs = n if closed else n - 1
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(nv):
            bm.faces.new((a[k], a[(k + 1) % nv], b[(k + 1) % nv], b[k]))
    if not closed and caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return solid(bm)


def wrap_strip(path2d, plane, a0, a1, t, center2d, closed=False, inner=0.012):
    """Bande épaisse posée sur une section (ruban adhésif, nervure, bandeau).

    path2d : [(s, z)] ; plane 'xz' -> s = X, extrusion Y de a0 à a1 ; 'yz' -> s = Y, extrusion X.
    t : épaisseur vers l'extérieur ; la face interne est enfoncée de `inner`.
    """
    P = [Vector((s, z)) for s, z in path2d]
    n = len(P)
    C = Vector(center2d)
    Nrm = []
    for i in range(n):
        if closed:
            a, b = P[(i - 1) % n], P[(i + 1) % n]
        else:
            a, b = P[max(i - 1, 0)], P[min(i + 1, n - 1)]
        d = (b - a).normalized()
        nn = Vector((d.y, -d.x))
        if nn.dot(P[i] - C) < 0:
            nn = -nn
        Nrm.append(nn)
    bm = bmesh.new()

    def v3(p2, a):
        return bm.verts.new((p2.x, a, p2.y) if plane == "xz" else (a, p2.x, p2.y))

    O = [[v3(P[i] + Nrm[i] * t, a) for i in range(n)] for a in (a0, a1)]
    I = [[v3(P[i] - Nrm[i] * inner, a) for i in range(n)] for a in (a0, a1)]
    segs = n if closed else n - 1
    for i in range(segs):
        j = (i + 1) % n
        bm.faces.new((O[0][i], O[0][j], O[1][j], O[1][i]))
        bm.faces.new((I[0][i], I[1][i], I[1][j], I[0][j]))
        bm.faces.new((O[0][i], I[0][i], I[0][j], O[0][j]))
        bm.faces.new((O[1][i], O[1][j], I[1][j], I[1][i]))
    if not closed:
        bm.faces.new((O[0][0], O[1][0], I[1][0], I[0][0]))
        bm.faces.new((O[0][-1], I[0][-1], I[1][-1], O[1][-1]))
    return solid(bm)


def section_path(rings, half, zmin):
    """Section d'une dalle (s, z) depuis zmin côté +s, par-dessus, jusqu'à zmin côté -s."""
    side = [(half - interp_inset(rings, zmin), zmin)]
    side += [(half - r[0], r[1]) for r in rings if r[1] > zmin + 1e-4]
    return side + [(-s, z) for s, z in reversed(side)]


def transform(bm, M):
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts[:])
    return bm


def rot(axis, deg, about=(0, 0, 0)):
    c = Vector(about)
    return Matrix.Translation(c) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-c)


def move(bm, d):
    bmesh.ops.translate(bm, vec=Vector(d), verts=bm.verts[:])
    return bm


CUT_TAG = 9


def boolean_diff(bm, cutters):
    """Différence booléenne EXACT (cibles et outils fermés)."""
    sc = bpy.context.scene
    for f in bm.faces:
        f.material_index = 0
    me = bpy.data.meshes.new("bool_tgt")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("bool_tgt", me)
    sc.collection.objects.link(ob)
    mb = bpy.data.materials.get("_bool_base") or bpy.data.materials.new("_bool_base")
    mc = bpy.data.materials.get("_bool_cut") or bpy.data.materials.new("_bool_cut")
    me.materials.append(mb)
    tmp = []
    for k, c in enumerate(cutters):
        for f in c.faces:
            f.material_index = 0
        cme = bpy.data.meshes.new(f"bool_cut{k}")
        c.to_mesh(cme)
        cme.materials.append(mc)  # les faces issues de l'outil restent repérables (poches)
        c.free()
        co = bpy.data.objects.new(f"bool_cut{k}", cme)
        sc.collection.objects.link(co)
        tmp.append(co)
        m = ob.modifiers.new(f"b{k}", "BOOLEAN")
        m.operation = "DIFFERENCE"
        m.solver = "EXACT"
        m.material_mode = "TRANSFER"
        m.object = co
    dg = bpy.context.evaluated_depsgraph_get()
    res = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    out = bmesh.new()
    out.from_mesh(res)
    cut_idx = [i for i, m in enumerate(res.materials) if m and m.name == mc.name]
    for f in out.faces:
        f.material_index = CUT_TAG if f.material_index in cut_idx else 0
    for o in tmp + [ob]:
        d = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(d)
    bpy.data.meshes.remove(res)
    return out


# --- mappeurs UV vers l'atlas ------------------------------------------------------
def _lerp_uv(r, u, v):
    u0, v0, u1, v1 = r
    return (u0 + clamp01(u) * (u1 - u0), v0 + clamp01(v) * (v1 - v0))


def m_pal(cell, z0, z1):
    """Cellule de palette ; v suit la hauteur (dégradé d'occlusion peint dans la cellule)."""
    r = atlas.cell_uv(cell)
    uc = (r[0] + r[2]) / 2

    def f(co):
        t = clamp01((co.z - z0) / max(z1 - z0, 1e-6))
        return (uc, r[1] + t * (r[3] - r[1]))
    return f


def m_top(tile, x0, x1, y0, y1):
    """Projection de dessus ; lecture droite pour un joueur à l'avant (+Y)."""
    r = atlas.tile_uv(tile)
    return lambda co: _lerp_uv(r, (x1 - co.x) / (x1 - x0), (y1 - co.y) / (y1 - y0))


def m_plane(tile, origin, uax, vax, su, sv):
    r = atlas.tile_uv(tile)
    o, ua, va = Vector(origin), Vector(uax), Vector(vax)
    return lambda co: _lerp_uv(r, 0.5 + (co - o).dot(ua) / su, 0.5 + (co - o).dot(va) / sv)


def m_band(tile, z0, z1, u=0.5):
    r = atlas.tile_uv(tile)
    return lambda co: _lerp_uv(r, u, (co.z - z0) / (z1 - z0))


def r_const(m):
    return lambda c, n: m


def r_pal(cell, z0, z1):
    return r_const(m_pal(cell, z0, z1))


def r_box(tile, bbox, top_rule=None, top_min_nz=0.7):
    """Projection boîte : côtés u = horizontal, v = hauteur ; dessus délégué ou bande haute."""
    x0, x1, y0, y1, z0, z1 = bbox
    r = atlas.tile_uv(tile)

    def rule(c, n):
        ax = max(range(3), key=lambda i: abs(n[i]))
        if ax == 2 or n.z > top_min_nz:
            if n.z > 0 and top_rule is not None:
                return top_rule(c, n)
            return lambda co: _lerp_uv(r, (co.x - x0) / (x1 - x0), 0.93 + 0.06 * (co.y - y0) / (y1 - y0))
        if ax == 0:
            if n.x > 0:
                return lambda co: _lerp_uv(r, (co.y - y0) / (y1 - y0), (co.z - z0) / (z1 - z0))
            return lambda co: _lerp_uv(r, (y1 - co.y) / (y1 - y0), (co.z - z0) / (z1 - z0))
        if n.y > 0:
            return lambda co: _lerp_uv(r, (x1 - co.x) / (x1 - x0), (co.z - z0) / (z1 - z0))
        return lambda co: _lerp_uv(r, (co.x - x0) / (x1 - x0), (co.z - z0) / (z1 - z0))
    return rule


def r_if(pred, a, b):
    return lambda c, n: (a if pred(c, n) else b)(c, n)


def r_top_faces(zmin, nz=0.5):
    return lambda c, n: n.z > nz and c.z >= zmin


def inside(box, pad=0.0):
    x0, x1, y0, y1, z0, z1 = box
    return lambda c, n: (x0 - pad <= c.x <= x1 + pad and y0 - pad <= c.y <= y1 + pad and z0 - pad <= c.z <= z1 + pad)


# --- assemblage ----------------------------------------------------------------------
class Asset:
    """Accumule des pièces (UV + matériau par face) dans un seul maillage."""

    def __init__(self, aid, size, lod):
        self.id = aid
        self.W, self.D, self.H = size
        self.lod = lod
        self.q = Q(lod)
        self.bm = bmesh.new()
        self.bm.loops.layers.uv.new("UVMap")
        self.parts = 0

    @property
    def bbox(self):
        return (-self.W / 2, self.W / 2, -self.D / 2, self.D / 2, 0.0, self.H)

    def pal(self, cell):
        return r_pal(cell, 0.0, self.H)

    def add(self, part, rule, mat=0, cut_rule=None):
        """Ajoute une pièce ; les faces de poche booléenne (CUT_TAG) prennent `cut_rule` (marine par défaut)."""
        part.normal_update()
        uvl = part.loops.layers.uv.get("UVMap") or part.loops.layers.uv.new("UVMap")
        cut_rule = cut_rule or self.pal("navy")
        for f in part.faces:
            r = cut_rule if f.material_index == CUT_TAG else rule
            mp = r(f.calc_center_median(), f.normal)
            for lp in f.loops:
                lp[uvl].uv = mp(lp.vert.co)
            f.material_index = mat
            f.smooth = True
        me = bpy.data.meshes.new("part_tmp")
        part.to_mesh(me)
        part.free()
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        self.parts += 1

    def to_object(self, name, materials, sharp_deg=42.0):
        bm = self.bm
        bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(sharp_deg))
        for m in materials:
            me.materials.append(m)
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        wn = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
        wn.mode = "FACE_AREA"
        wn.weight = 50
        wn.keep_sharp = True
        bpy.ops.object.modifier_apply(modifier=wn.name)
        return ob
