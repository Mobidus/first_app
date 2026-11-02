"""Kit modulaire des canards gonflables FILLING UP (Blender bpy/bmesh, headless).

Deux bibliothèques construites en code :
  1. FORMES de corps (FORMS) : mini (canard de bain), medium (bouée à chevaucher), lilo (matelas),
     large_ring (bouée carrée à filet), giant (île). Chaque forme produit un corps gonflé dont le dessus
     praticable est plat à la hauteur du collider, des ailes, une queue, une valve, des soudures, et un
     contexte de tête (HeadCtx) dans la BANDE AVANT hors du rectangle praticable.
  2. ACCESSOIRES (ACCESSORIES) : une fonction par accessoire, accrochée à une PRISE :
     head_top (chapeaux), eyes (lunettes, masque, monocle, cache-oeil), beak_under (moustaches, pipe,
     trait de crème solaire), neck (noeuds, collier, sifflet, appareil photo), body (marinière, maillot,
     cape, bande SAUVETEUR, décalque).
Une variante = forme + accessoires ; build_ducks.py compose et fusionne en un seul maillage, un matériau.

Conventions (décision 0003) : 1 unité Blender = 1 stud ; X largeur, Y profondeur, Z haut ; avant Roblox
-Z = +Y Blender ; pivot bottom_center (origine au centre de l'empreinte, au sol).
Primitives (loft, lathe, tube, mappeurs UV) adaptées de prop_kit.py (copie, pas d'import).
"""
from __future__ import annotations

import math

import bpy  # bpy doit précéder bmesh
import bmesh
from mathutils import Matrix, Vector

import duck_atlas as atlas


# =====================================================================================
# niveau de détail
# =====================================================================================
class Q:
    """Densité de maillage ; k module la densité par forme (mini plus léger, géant plus dense)."""

    def __init__(self, lod, k=1.0):
        self.lod = lod
        self.hi = lod == 0
        self.k = k
        self.detail = lod == 0

    def n(self, hi, lo, mn=3):
        return max(mn, int(round(hi * self.k))) if self.hi else lo


# =====================================================================================
# primitives
# =====================================================================================
def clamp01(t):
    return 0.0 if t < 0 else (1.0 if t > 1 else t)


def solid(bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def rrect(hw, hd, r, seg):
    """Rectangle arrondi CCW (vu de +Z), 4*(seg+1) points ; départ à +X."""
    r = max(0.01, min(r, hw - 1e-3, hd - 1e-3))
    pts = []
    for cx, cy, a0 in ((hw - r, hd - r, 0), (-hw + r, hd - r, 90), (-hw + r, -hd + r, 180), (hw - r, -hd + r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90.0 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def superellipse(a, b, e, n, phase=0.0, cx=0.0, cy=0.0):
    pts = []
    for i in range(n):
        t = phase + 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        pts.append((cx + a * math.copysign(abs(c) ** (2 / e), c), cy + b * math.copysign(abs(s) ** (2 / e), s)))
    return pts


def area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def ccw(pts):
    return pts if area2(pts) > 0 else list(reversed(pts))


def offset_poly(pts, d):
    """Décalage vers l'intérieur (d > 0) d'un contour CCW, par normales de sommet (coins limités)."""
    if abs(d) < 1e-9:
        return list(pts)
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        e1, e2 = (p1 - p0), (p2 - p1)
        e1 = e1.normalized() if e1.length > 1e-9 else e2.normalized()
        e2 = e2.normalized() if e2.length > 1e-9 else e1
        n1, n2 = Vector((-e1.y, e1.x)), Vector((-e2.y, e2.x))
        m = n1 + n2
        m = m.normalized() if m.length > 1e-6 else n1
        k = d / max(m.dot(n1), 0.45)
        q = p1 + m * k
        out.append((q.x, q.y))
    return out


def convex_hull(pts):
    """Enveloppe convexe CCW (chaîne monotone) : contours sûrs pour les décalages des coussins."""
    P = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))
    if len(P) < 3:
        return P

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def chaikin(pts, it=2, closed=True):
    for _ in range(it):
        out = []
        n = len(pts)
        rng_ = range(n) if closed else range(n - 1)
        if not closed:
            out.append(pts[0])
        for i in rng_:
            a, b = Vector(pts[i]), Vector(pts[(i + 1) % n])
            out.append(tuple(a * 0.75 + b * 0.25))
            out.append(tuple(a * 0.25 + b * 0.75))
        if not closed:
            out.append(pts[-1])
        pts = out
    return pts


def resample(pts, n, closed=True):
    """Rééchantillonne une polyligne en n points équidistants (longueur d'arc)."""
    P = [Vector(p) for p in pts] + ([Vector(pts[0])] if closed else [])
    L = [0.0]
    for a, b in zip(P[:-1], P[1:]):
        L.append(L[-1] + (b - a).length)
    tot = L[-1]
    out = []
    cnt = n if closed else n - 1
    j = 0
    for i in range(n):
        s = tot * i / cnt
        while j < len(L) - 2 and L[j + 1] < s:
            j += 1
        t = (s - L[j]) / max(L[j + 1] - L[j], 1e-9)
        q = P[j] + (P[j + 1] - P[j]) * t
        out.append(tuple(q))
    return out


def loft(rings, outline, cap0=True, cap1=True):
    """Empile des contours : rings = [(paramètre, z)], outline(paramètre, z) -> [(x, y)] (même nombre de points)."""
    bm = bmesh.new()
    loops = []
    for r in rings:
        pts = outline(r[0], r[1])
        loops.append([bm.verts.new((x, y, r[1])) for x, y in pts])
    n = len(loops[0])
    for a, b in zip(loops[:-1], loops[1:]):
        for i in range(n):
            bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    if cap0:
        bm.faces.new(list(reversed(loops[0])))
    if cap1:
        bm.faces.new(loops[-1])
    return solid(bm) if (cap0 and cap1) else bm


def loft_rr(rings, seg, cap0=True, cap1=True):
    """rings = [(hw, hd, R, z)] -> loft de rectangles arrondis."""
    return loft([((hw, hd, R), z) for hw, hd, R, z in rings], lambda p, z: rrect(p[0], p[1], p[2], seg), cap0, cap1)


def lathe(profile, n, cap0=True, cap1=True, a0=0.0):
    """Révolution autour de Z d'un profil [(r, z)] ; r = 0 -> pôle."""
    bm = bmesh.new()
    loops = []
    for r, z in profile:
        if r < 1e-6:
            loops.append([bm.verts.new((0.0, 0.0, z))])
        else:
            loops.append([bm.verts.new((r * math.cos(a0 + 2 * math.pi * i / n), r * math.sin(a0 + 2 * math.pi * i / n), z))
                          for i in range(n)])
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
    if cap0 and len(loops[0]) > 1:
        bm.faces.new(list(reversed(loops[0])))
    if cap1 and len(loops[-1]) > 1:
        bm.faces.new(loops[-1])
    closed = (cap0 or len(loops[0]) == 1) and (cap1 or len(loops[-1]) == 1)
    return solid(bm) if closed else bm


def sphere(r, nu, nv):
    prof = [(r * math.sin(math.pi * i / nv), -r * math.cos(math.pi * i / nv)) for i in range(nv + 1)]
    prof[0] = (0.0, -r)
    prof[-1] = (0.0, r)
    return lathe(prof, nu)


def prism(outline, z0, z1):
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


def tube(path, radius, nv, closed=False, up=(0, 0, 1), caps=True):
    """Tube balayé le long d'une polyligne 3D ; radius constant ou fonction de t in [0, 1]."""
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
        rings.append([bm.verts.new(P[i] + r * (math.cos(2 * math.pi * k / nv) * N[i] + math.sin(2 * math.pi * k / nv) * B))
                      for k in range(nv)])
    segs = n if closed else n - 1
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(nv):
            bm.faces.new((a[k], a[(k + 1) % nv], b[(k + 1) % nv], b[k]))
    if not closed and caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return solid(bm)


def bezier(P0, P1, P2, P3, n):
    P0, P1, P2, P3 = (Vector(p) for p in (P0, P1, P2, P3))
    return [tuple((1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t * t * P2 + t ** 3 * P3)
            for t in [i / (n - 1) for i in range(n)]]


def transform(bm, M):
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts[:])
    return bm


def place(bm, M):
    """Applique M ; si M est un miroir (det < 0), retourne les faces pour garder les normales sortantes."""
    transform(bm, M)
    if M.to_3x3().determinant() < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return bm


def move(bm, d):
    bmesh.ops.translate(bm, vec=Vector(d), verts=bm.verts[:])
    return bm


def basis(U, V, N, O=(0, 0, 0)):
    U, V, N, O = Vector(U), Vector(V), Vector(N), Vector(O)
    return Matrix(((U.x, V.x, N.x, O.x), (U.y, V.y, N.y, O.y), (U.z, V.z, N.z, O.z), (0, 0, 0, 1)))


def edge_rings(t, steps, re=None):
    """Anneaux (inset, z) d'un coussin d'épaisseur t : bords arrondis de rayon re (défaut t/2)."""
    re = min(t / 2, re if re is not None else t / 2)
    z0, z1 = -t / 2, t / 2
    rings = []
    for i in range(steps + 1):
        a = (math.pi / 2) * i / steps
        rings.append((re * (1 - math.sin(a)), z0 + re * (1 - math.cos(a))))
    if t / 2 - re > 1e-4:
        rings.append((0.0, z1 - re))
    for i in range(1, steps + 1):
        a = (math.pi / 2) * i / steps
        rings.append((re * (1 - math.cos(a)), z1 - re + re * math.sin(a)))
    return rings


def puff(pts, t, steps, re=None):
    """Coussin gonflé : contour 2D (plan local xy) épaissi en z avec bords arrondis (soudure au milieu)."""
    pts = ccw(pts)
    return loft(edge_rings(t, max(1, steps), re), lambda i, z: offset_poly(pts, i))


# =====================================================================================
# mappeurs UV vers l'atlas
# =====================================================================================
def _lerp_uv(r, u, v):
    u0, v0, u1, v1 = r
    return (u0 + clamp01(u) * (u1 - u0), v0 + clamp01(v) * (v1 - v0))


def m_pal(cell, z0, z1):
    r = atlas.cell_uv(cell)
    uc = (r[0] + r[2]) / 2

    def f(co):
        t = clamp01((co.z - z0) / max(z1 - z0, 1e-6))
        return (uc, r[1] + t * (r[3] - r[1]))
    return f


def m_top(tile, x0, x1, y0, y1):
    r = atlas.tile_uv(tile)
    return lambda co: _lerp_uv(r, (x1 - co.x) / (x1 - x0), (y1 - co.y) / (y1 - y0))


def m_plane(tile, origin, uax, vax, su, sv):
    r = atlas.tile_uv(tile)
    o, ua, va = Vector(origin), Vector(uax), Vector(vax)
    return lambda co: _lerp_uv(r, 0.5 + (co - o).dot(ua) / su, 0.5 + (co - o).dot(va) / sv)


def r_const(m):
    return lambda c, n: m


def r_pal(cell, z0, z1):
    return r_const(m_pal(cell, z0, z1))


def r_if(pred, a, b):
    return lambda c, n: (a if pred(c, n) else b)(c, n)


def r_band(tile, z0, z1):
    """Bandes horizontales : v = hauteur, u selon l'angle autour de Z (raccord à l'arrière)."""
    r = atlas.tile_uv(tile)

    def rule(c, n):
        ac = math.atan2(c.x, c.y)

        def f(co):
            a = math.atan2(co.x, co.y)
            if a - ac > math.pi:
                a -= 2 * math.pi
            elif ac - a > math.pi:
                a += 2 * math.pi
            return _lerp_uv(r, 0.5 + a / (2 * math.pi), (co.z - z0) / (z1 - z0))
        return f
    return rule


def r_box(tile, bbox):
    """Projection boîte : côtés u = horizontal, v = hauteur."""
    x0, x1, y0, y1, z0, z1 = bbox
    r = atlas.tile_uv(tile)

    def rule(c, n):
        ax = max(range(3), key=lambda i: abs(n[i]))
        if ax == 2:
            return lambda co: _lerp_uv(r, (co.x - x0) / (x1 - x0), (co.z - z0) / (z1 - z0))
        if ax == 0:
            return lambda co: _lerp_uv(r, (co.y - y0) / (y1 - y0), (co.z - z0) / (z1 - z0))
        return lambda co: _lerp_uv(r, (co.x - x0) / (x1 - x0), (co.z - z0) / (z1 - z0))
    return rule


def r_tilebox(tile, bbox, scale_u=1.0):
    """Projection boîte pour un imprimé : chaque face prend la tuile sur sa projection dominante."""
    x0, x1, y0, y1, z0, z1 = bbox
    r = atlas.tile_uv(tile)

    def rule(c, n):
        ax = max(range(3), key=lambda i: abs(n[i]))
        if ax == 2:
            return lambda co: _lerp_uv(r, (co.x - x0) / (x1 - x0), (co.y - y0) / (y1 - y0))
        if ax == 0:
            return lambda co: _lerp_uv(r, ((co.y - y0) / (y1 - y0)) * scale_u % 1.0001, (co.z - z0) / (z1 - z0))
        return lambda co: _lerp_uv(r, ((co.x - x0) / (x1 - x0)) * scale_u % 1.0001, (co.z - z0) / (z1 - z0))
    return rule


# =====================================================================================
# assemblage
# =====================================================================================
class Asset:
    """Accumule des pièces (UV par face) dans un seul maillage, un matériau."""

    def __init__(self, aid, env, lod, k=1.0):
        self.id = aid
        self.W, self.D, self.H = env
        self.lod = lod
        self.q = Q(lod, k)
        self.bm = bmesh.new()
        self.bm.loops.layers.uv.new("UVMap")
        self.parts = 0
        self.fit_factors = None
        self.labels = []
        self.tally = {}
        self.extent = {}
        self._last = "misc"

    def pal(self, cell, z0=None, z1=None):
        return r_pal(cell, 0.0 if z0 is None else z0, self.H if z1 is None else z1)

    def add(self, part, rule, label=None):
        part.normal_update()
        if label:
            self._last = label
        self.tally[self._last] = self.tally.get(self._last, 0) + sum(len(f.verts) - 2 for f in part.faces)
        if part.verts:
            lo = [min(v.co[i] for v in part.verts) for i in range(3)]
            hi = [max(v.co[i] for v in part.verts) for i in range(3)]
            b = self.extent.get(self._last)
            self.extent[self._last] = (lo, hi) if b is None else ([min(a, c) for a, c in zip(b[0], lo)],
                                                                  [max(a, c) for a, c in zip(b[1], hi)])
        uvl = part.loops.layers.uv.get("UVMap") or part.loops.layers.uv.new("UVMap")
        if rule is not None:
            for f in part.faces:
                mp = rule(f.calc_center_median(), f.normal)
                for lp in f.loops:
                    lp[uvl].uv = mp(lp.vert.co)
        for f in part.faces:
            f.material_index = 0
            f.smooth = True
        me = bpy.data.meshes.new("part_tmp")
        part.to_mesh(me)
        part.free()
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        self.parts += 1
        if label:
            self.labels.append(label)

    def bounds(self):
        xs = [v.co for v in self.bm.verts]
        return (Vector((min(c.x for c in xs), min(c.y for c in xs), min(c.z for c in xs))),
                Vector((max(c.x for c in xs), max(c.y for c in xs), max(c.z for c in xs))))

    def fit(self, core):
        """Ajuste exactement l'enveloppe W x D x H par une déformation affine par morceaux HORS du cœur
        protégé (rectangle du collider en X/Y, dessus du collider en Z) : le dessus praticable n'est pas touché.
        Les facteurs (≈ 1) sont consignés dans build_info.json."""
        cx, cy, T = core
        mn, mx = self.bounds()
        fac = {}

        def warp(i, lo_t, hi_t, c_lo, c_hi, key):
            k_hi = (hi_t - c_hi) / (mx[i] - c_hi) if mx[i] > c_hi + 1e-6 else 1.0
            k_lo = (c_lo - lo_t) / (c_lo - mn[i]) if mn[i] < c_lo - 1e-6 else 1.0
            fac[key] = (round(k_lo, 4), round(k_hi, 4))
            for v in self.bm.verts:
                c = v.co[i]
                if c > c_hi:
                    v.co[i] = c_hi + (c - c_hi) * k_hi
                elif c < c_lo:
                    v.co[i] = c_lo - (c_lo - c) * k_lo
        warp(0, -self.W / 2, self.W / 2, -cx, cx, "x")
        warp(1, -self.D / 2, self.D / 2, -cy, cy, "y")
        k = (self.H - T) / (mx[2] - T)
        fac["z"] = (1.0, round(k, 4))
        for v in self.bm.verts:
            if v.co.z > T:
                v.co.z = T + (v.co.z - T) * k
        if abs(mn.z) > 1e-4:
            for v in self.bm.verts:
                v.co.z -= mn.z
        self.fit_factors = fac
        return fac

    def to_object(self, name, materials, sharp_deg=72.0):
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


class Measure:
    """Même interface que Asset.add, mais ne mesure que la boîte englobante (passe de placement de la tête)."""

    def __init__(self, asset):
        self.H = asset.H
        self.q = asset.q
        self.lod = asset.lod
        self.mn = Vector((1e9, 1e9, 1e9))
        self.mx = Vector((-1e9, -1e9, -1e9))

    def pal(self, cell, z0=None, z1=None):
        return r_pal(cell, 0.0, 1.0)

    def add(self, part, rule, label=None):
        for v in part.verts:
            for i in range(3):
                self.mn[i] = min(self.mn[i], v.co[i])
                self.mx[i] = max(self.mx[i], v.co[i])
        part.free()


# =====================================================================================
# contexte de tête (prises)
# =====================================================================================
class HeadCtx:
    """Tête-coussin (deux panneaux soudés) : repère local x = droite, y = avant (regard), z = haut.

    Dimensions : demi-largeur hx, demi-hauteur hz, demi-épaisseur hy ; le bec dépasse de p devant le visage.
    Bande avant disponible en local : y in [-hy, hy + p] (le dos de la tête est au bord du rectangle praticable).
    Prises : head_top (0, 0, top_z), eyes (±ex, hy, ez), beak_under (0, hy + p/2, beak_under_z), neck (0, 0, neck_z).
    """

    def __init__(self, hx, hz, hy, p, center_xy, fwd="y", seam=True, k=1.0):
        self.hx, self.hz, self.hy, self.p = hx, hz, hy, p
        self.k = k  # échelle des petites épaisseurs (tubes, montures)
        self.R = Matrix.Identity(3) if fwd == "y" else Matrix.Rotation(-math.pi / 2, 3, "Z")
        self.fwd_axis = fwd
        self.cxy = center_xy
        self.z = 0.0
        self.seam = seam
        self.ex = 2 * atlas.EYE_U * hx
        self.ez = (2 * atlas.EYE_V - 1) * hz
        self.re = 2 * atlas.EYE_RU * hx
        self.bz = -0.3 * hz
        self.bt = 0.2 * hz
        self.bw = 0.6 * hx
        self._neck_z = -hz - 0.1 * k
        self.neck_abs = None  # hauteur monde imposée de la prise « neck » (matelas : sur l'oreiller)
        self.top_z = hz
        self.neck_hw = 0.62 * hx

    @property
    def neck_z(self):
        return self._neck_z if self.neck_abs is None else self.neck_abs - self.z

    # repère
    @property
    def o(self):
        return Vector((self.cxy[0], self.cxy[1], self.z))

    @property
    def right(self):
        return self.R @ Vector((1, 0, 0))

    @property
    def fwd(self):
        return self.R @ Vector((0, 1, 0))

    @property
    def up(self):
        return Vector((0, 0, 1))

    def P(self, x, y, z):
        return self.o + self.R @ Vector((x, y, z))

    def D(self, v):
        return self.R @ Vector(v)

    def M(self, U=(1, 0, 0), V=(0, 1, 0), N=(0, 0, 1), at=(0, 0, 0)):
        """Matrice monde d'une pièce construite en (u, v, w) et posée en local (U, V, N à partir de `at`)."""
        return basis(self.D(U), self.D(V), self.D(N), self.P(*at))

    def half_width(self, z):
        """Demi-largeur du contour de la tête à la hauteur locale z (superellipse e = 2.5)."""
        t = clamp01(abs(z) / self.hz)
        w = (1 - t ** 2.5) ** (1 / 2.5) if t < 1 else 0.0
        return self.hx * w * (1 - 0.07 * z / self.hz)

    def front(self, thr=0.4):
        f = self.fwd
        return lambda c, n: n.dot(f) > thr

    def plane(self, tile, at, su, sv, mirror=False):
        ua = self.right if mirror else -self.right
        return m_plane(tile, self.P(*at), ua, self.up, su, sv)

    def pal(self, A, cell):
        return r_pal(cell, self.z - self.hz, self.z + self.hz)

    def cyl(self, tile, at, z0, z1):
        """Projection cylindrique autour de l'axe local haut passant par `at` ; raccord à l'arrière."""
        r = atlas.tile_uv(tile)
        o = self.P(*at)
        R, F = self.right, self.fwd

        def rule(c, n):
            d = c - o
            ac = math.atan2(d.dot(R), d.dot(F))

            def f(co):
                d2 = co - o
                a = math.atan2(d2.dot(R), d2.dot(F))
                if a - ac > math.pi:
                    a -= 2 * math.pi
                elif ac - a > math.pi:
                    a += 2 * math.pi
                return _lerp_uv(r, 0.5 + a / (2 * math.pi), (d2.z - z0) / (z1 - z0))
            return f
        return rule

    def box(self, tile, size):
        """Projection boîte dans le repère de la tête (imprimés : paille, etc.)."""
        r = atlas.tile_uv(tile)
        o, R, F = self.o, self.right, self.fwd

        def rule(c, n):
            if abs(n.z) > 0.6:
                return lambda co: _lerp_uv(r, 0.5 + (co - o).dot(R) / size, 0.5 + (co - o).dot(F) / size)
            if abs(n.dot(R)) > abs(n.dot(F)):
                return lambda co: _lerp_uv(r, 0.5 + (co - o).dot(F) / size, 0.5 + (co.z - o.z) / size)
            return lambda co: _lerp_uv(r, 0.5 + (co - o).dot(R) / size, 0.5 + (co.z - o.z) / size)
        return rule


def head_outline(hc, n):
    pts = superellipse(hc.hx, hc.hz, 2.5, n, phase=math.pi / 2)
    return [(x * (1 - 0.07 * z / hc.hz), z) for x, z in pts]


def build_head(A, hc, eyes=True):
    """Tête-coussin + yeux (dômes) + bec en deux parties + soudure périphérique."""
    q = A.q
    n = q.n(26, 8, 8)
    pts = head_outline(hc, n)
    head = puff(pts, 2 * hc.hy, q.n(2, 1, 1))
    place(head, hc.M((1, 0, 0), (0, 0, 1), (0, -1, 0)))  # u = droite, v = haut, épaisseur selon l'avant
    face = hc.plane("face", (0, hc.hy, 0), 2 * hc.hx, 2 * hc.hz)
    A.add(head, r_if(hc.front(0.35), r_const(face), hc.pal(A, "yellow")), "head")
    if q.detail and hc.seam:
        sp = resample(head_outline(hc, 60), q.n(22, 8, 8))
        path = [tuple(hc.P(x, 0.0, z)) for x, z in sp]
        A.add(tube(path, 0.05 * hc.k, 3, closed=True, up=tuple(hc.fwd)), hc.pal(A, "yellow_dark"))
    if eyes and q.detail:
        for sx in (-1, 1):
            r, d = hc.re, 0.11 * hc.k
            prof = [(r, 0.0), (r * 0.96, d * 0.45), (r * 0.78, d * 0.85), (r * 0.42, d * 1.0), (0.0, d * 1.04)]
            e = lathe(prof[:2] + prof[3:], q.n(12, 6, 6))
            at = (sx * hc.ex, hc.hy - 0.02, hc.ez)
            place(e, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=at))
            m = hc.plane("eye", at, 2 * r, 2 * r, mirror=sx > 0)
            A.add(e, r_if(hc.front(0.15), r_const(m), hc.pal(A, "navy")), "eye")
    build_bill(A, hc)


def bill_outline(hc, bw, y_back, y_tip, n):
    bl = (y_tip - y_back) / 2
    pts = superellipse(bw, bl, 2.6, n, cy=y_back + bl)
    out = []
    for x, y in pts:  # bec de canard : bout légèrement élargi, base plus étroite
        t = (y - y_back) / (2 * bl)
        out.append((x * (0.86 + 0.18 * t), y))
    return out


def build_bill(A, hc):
    q = A.q
    n = q.n(14, 6, 6)
    y_back = hc.hy - 0.55 * hc.k
    up = puff(bill_outline(hc, hc.bw, y_back, hc.hy + hc.p, n), hc.bt, q.n(2, 1, 1))
    place(up, hc.M(at=(0, 0, hc.bz)))
    zt = hc.z + hc.bz
    m_bill = m_plane("bill", hc.P(0, hc.hy + hc.p * 0.4, hc.bz), -hc.right, hc.fwd, 2 * hc.bw, 2 * (hc.p + 0.55 * hc.k))
    A.add(up, r_if(lambda c, n: n.z > 0.55, r_const(m_bill), r_pal("orange", zt - hc.bt, zt + hc.bt)), "bill")
    if q.detail and getattr(hc, "lower_bill", True):
        lo = puff(bill_outline(hc, hc.bw * 0.8, y_back, hc.hy + hc.p * 0.72, n), hc.bt * 0.6, 1)
        place(lo, hc.M(at=(0, 0, hc.bz - hc.bt * 0.62)))
        A.add(lo, r_pal("orange_dark", zt - hc.bt * 1.2, zt))
    hc.beak_under_z = hc.bz - hc.bt * (0.95 if q.detail else 0.55)


# =====================================================================================
# formes de corps
# =====================================================================================
def deck_profile(T, s, b_in, zm, rt, nb, top_angles):
    """Profil (inset, z) d'un corps gonflé : fond arrondi -> bombé latéral s à zm -> gros arrondi -> dessus
    plat à T à partir d'un inset rt. inset < 0 = vers l'extérieur."""
    rings = []
    for i in range(nb + 1):
        a = (math.pi / 2) * i / nb
        rings.append((-s + (b_in + s) * (1 - math.sin(a)), zm * (1 - math.cos(a))))
    for deg in top_angles:
        a = math.radians(deg)
        rings.append((-s + (s + rt) * (1 - math.cos(a)), zm + (T - zm) * math.sin(a)))
    return rings


def top_angles(q):
    return [16, 36, 55, 70, 82, 90] if q.hi else [40, 72, 90]


class Body:
    """Contexte de corps : collider, enveloppe, contour à une hauteur donnée, règles de peau."""

    def __init__(self, form, P, q):
        self.form = form
        self.P = P
        self.q = q
        self.cw, self.cd, self.T = P["collider"]
        self.W, self.D, self.H = P["envelope"]

    def outline_at(self, z):
        """(demi-largeur, demi-profondeur, rayon de coin) du corps à la hauteur z."""
        rings = self.rings
        inset = rings[-1][0]
        for a, b in zip(rings[:-1], rings[1:]):
            if a[1] <= z <= b[1] and b[1] > a[1]:
                t = (z - a[1]) / (b[1] - a[1])
                inset = a[0] + (b[0] - a[0]) * t
                break
        if z < rings[0][1]:
            inset = rings[0][0]
        return (self.hw0 - inset, self.hd0 - inset, max(self.R0 - inset, 0.05))


def side_rule(A, bc, skin):
    T = bc.T
    bbox = (-bc.W / 2, bc.W / 2, -bc.D / 2, bc.D / 2, 0.0, T)
    vin = r_box("s_vinyl", bbox)
    if skin == "mariniere":
        zc = T - (0.55 if bc.form != "giant" else 1.0)
        mar = r_box("mariniere", (bbox[0], bbox[1], bbox[2], bbox[3], 0.0, zc))
        return r_if(lambda c, n: c.z < zc, mar, vin)
    if skin == "hawaii":
        return r_tilebox("hawaii", (-bc.W / 2, bc.W / 2, -bc.D / 2, bc.D / 2, 0.0, T), 2.0)
    return vin


def build_deck_body(A, bc, skin):
    """Corps à dessus plat (mini, medium, giant)."""
    q, P = A.q, bc.P
    bc.hw0 = bc.cw / 2 + P["margin"]
    bc.hd0 = bc.cd / 2 + P["margin"]
    bc.R0 = P["R0"]
    seg = q.n(P.get("seg", 6), 2, 2)
    bc.rings = deck_profile(bc.T, P["s"], P["b_in"], P["zm"], P["rt"], P.get("nb", 3) if q.hi else 1, top_angles(q))
    body = loft_rr([(bc.hw0 - i, bc.hd0 - i, max(bc.R0 - i, 0.05), z) for i, z in bc.rings], seg)
    top = m_top(P.get("top_tile", "deck"), -bc.hw0, bc.hw0, -bc.hd0, bc.hd0)
    A.add(body, r_if(lambda c, n: n.z > 0.92 and c.z > bc.T - 0.03, r_const(top), side_rule(A, bc, skin)), "body")
    if q.detail and P.get("seam", True):  # soudure de l'équateur
        hw, hd, R = bc.outline_at(P["zm"])
        path = [(x, y, P["zm"]) for x, y in rrect(hw + 0.01, hd + 0.01, R, seg)]
        A.add(tube(path, P.get("seam_r", 0.06), 4, closed=True), A.pal("yellow_dark"))


def build_wings(A, bc, W2, yc, zc, L, Hh, t, steps=2, tile="wing"):
    q = A.q
    n = q.n(16, 6, 6)
    if bc.form == "mini":
        steps = 1
    for sx in (-1, 1):
        pts = []
        for x, z in superellipse(L / 2, Hh / 2, 2.2, n):
            u = x / (L / 2)  # -1 = arrière
            back = max(0.0, -u)
            z2 = z * (1 - 0.45 * back) + 0.42 * Hh * back ** 2
            pts.append((x, z2))
        w = puff(pts, t, q.n(steps, 1, 1))
        xc = sx * (W2 - t / 2)
        place(w, basis((0, 1, 0), (0, 0, 1), (1, 0, 0), (xc, yc, zc)))
        m = m_plane(tile, (xc, yc, zc), (0, sx, 0), (0, 0, 1), L, Hh * 1.25)
        other = A.pal("yellow") if tile == "wing" else A.pal("red_dark")
        A.add(w, r_if(lambda c, n, sx=sx: n.x * sx > 0.45, r_const(m), other), "wing")


def build_tail(A, bc, y_front, y_back, z0, th, t, axis="y"):
    """Queue relevée : y_front (bord avant au-dessus du dessus utile) -> y_back (bout de l'enveloppe).

    axis='y' : queue à l'arrière (-Y) ; axis='x' : queue au bout -X (matelas)."""
    q = A.q
    T = bc.T
    L = y_front - y_back
    # contour convexe à bord avant VERTICAL (y = y_front) : rien ne déborde au-dessus du rectangle praticable
    raw = [(y_front, z0 - 0.55), (y_back + 0.35 * L, z0 - 0.55), (y_back + 0.04 * L, T - 0.25),
           (y_back, T + 0.35 * th), (y_back + 0.12 * L, T + th), (y_back + 0.4 * L, T + 0.92 * th),
           (y_front, T + 0.25 * th)]
    raw = convex_hull(raw)
    pts = chaikin(ccw(raw), 1) if q.hi else ccw(raw)
    # rayon d'arrondi limité par la petite dimension du contour (sinon le décalage se retourne)
    if q.hi:
        w = puff(pts, t, 2 if bc.form != "mini" else 1, re=min(t / 2, 0.32 * L))
    else:
        w = prism(pts, -t / 2, t / 2)
    if axis == "y":
        place(w, basis((0, 1, 0), (0, 0, 1), (1, 0, 0)))
    else:
        place(w, basis((1, 0, 0), (0, 0, 1), (0, -1, 0)))
    A.add(w, A.pal("yellow"), "tail")


def build_valve(A, at, out_dir, r=0.2):
    """Valve gonflable : embase + bouchon (pictogramme de valve sur le dessus du bouchon)."""
    q = A.q
    if not q.hi:
        return
    n = q.n(10, 6, 6)
    prof = [(r * 1.5, 0.0), (r * 0.7, 0.1), (r * 0.7, 0.28), (r, 0.32), (r, 0.42), (0.0, 0.46)]
    v = lathe(prof, n)
    d = Vector(out_dir).normalized()
    u = d.cross(Vector((0, 0, 1)))
    if u.length < 1e-3:
        u = Vector((1, 0, 0))
    u.normalize()
    vv = d.cross(u)
    place(v, basis(u, vv, d, at))
    cap = m_plane("valve", Vector(at) + d * 0.46, u, vv, 2 * r, 2 * r)
    A.add(v, r_if(lambda c, n: n.dot(d) > 0.7 and (c - Vector(at)).dot(d) > 0.4, r_const(cap), A.pal("white")), "valve")


def neck_for(A, bc, hc, z_world_lo):
    """Cou : coussin vertical de la base (dans le corps) jusqu'au centre de la tête."""
    q = A.q
    zl = z_world_lo - hc.z
    if hc.z - hc.hz < bc.T - 0.6:  # tête déjà enfoncée devant le corps : pas de cou visible
        return
    w = hc.neck_hw
    if q.hi:
        pts = rrect(w, (0 - zl) / 2, w * 0.95, 2)
        pts = [(x, y + zl / 2) for x, y in pts]
        nk = puff(pts, 2 * hc.hy * 0.96, 1)
    else:
        nk = prism([(-w, zl), (w, zl), (w * 0.8, 0.0), (-w * 0.8, 0.0)], -hc.hy * 0.9, hc.hy * 0.9)
    place(nk, hc.M((1, 0, 0), (0, 0, 1), (0, -1, 0)))
    A.add(nk, r_pal("yellow", z_world_lo, hc.z), "neck")


# --- forme : paramètres -----------------------------------------------------------
# valve : (x, z, côté) ; côté "back" -> pointe vers -Y, "side" -> pointe vers +X (sous l'aile, vers l'arrière)
FORMS = {
    "mini": dict(collider=(4, 4, 3), envelope=(5, 6, 6), walkable=(4, 4), k=0.75, margin=0.15, R0=0.8, rt=0.32,
                 s=0.25, b_in=0.55, zm=1.25, seg=5, seam=False, nb=2,
                 head=dict(hx=1.85, hz=1.5, hy=0.36, p=0.4, seam=False, lower_bill=False), neck_lo=2.7,
                 wings=dict(yc=-0.3, zc=1.45, L=2.5, Hh=1.2, t=0.5, lod1=False),
                 tail=dict(th=1.15, t=1.25), valve=(1.0, 1.3, "back")),
    "medium": dict(collider=(9, 8, 4), envelope=(12, 10, 9), walkable=(9, 8), k=1.0, margin=0.15, R0=1.2, rt=0.35,
                   s=0.6, b_in=0.9, zm=1.9, seg=4,
                   head=dict(hx=2.9, hz=2.35, hy=0.36, p=0.4, seam=True), neck_lo=3.3,
                   wings=dict(yc=-0.6, zc=2.0, L=5.2, Hh=2.3, t=1.0),
                   tail=dict(th=1.7, t=2.0), valve=(-2.4, 1.3, "side")),
    "large_ring": dict(collider=(12, 12, 5), envelope=(15, 14, 11), walkable=(12, 12), k=1.0, margin=0.15, R0=1.2,
                       rt=0.35, s=0.6, b_in=1.1, zm=2.35, seg=4, hole=2.9,
                       head=dict(hx=3.0, hz=2.45, hy=0.36, p=0.4, seam=True), neck_lo=4.3,
                       wings=dict(yc=-0.8, zc=2.5, L=6.0, Hh=2.6, t=1.1),
                       tail=dict(th=1.9, t=2.2), valve=(-3.6, 1.6, "side")),
    "giant": dict(collider=(18, 16, 8), envelope=(24, 20, 14), walkable=(18, 16), k=1.2, margin=0.15, R0=1.5,
                  rt=0.35, s=1.2, b_in=1.6, zm=3.8, seg=5, seam_r=0.09, top_tile="island_top",
                  head=dict(hx=4.8, hz=3.7, hy=0.81, p=0.5, seam=True), neck_lo=7.2,
                  wings=dict(yc=-1.2, zc=3.9, L=10.0, Hh=4.4, t=2.0),
                  tail=dict(th=2.8, t=3.2), valve=(5.0, 2.6, "back")),
    "lilo": dict(collider=(14, 7, 2), envelope=(16, 8, 5), walkable=(14, 7), k=1.0, margin=0.15,
                 head=dict(hx=2.4, hz=1.72, hy=0.36, p=0.4, seam=False, lower_bill=False),
                 tail=dict(th=1.2, t=1.0)),
}


def place_valve(A, bc, P, r):
    vx, vz, side = P["valve"]
    hw, hd, _R = bc.outline_at(vz)
    if side == "back":
        build_valve(A, (vx, -hd + 0.02, vz), (0, -1, 0.3), r=r)
    else:
        build_valve(A, (hw - 0.02, vx, vz), (1, 0, 0.3), r=r)


def form_body(A, form, skin, wing_tile="wing"):
    P = FORMS[form]
    bc = Body(form, P, A.q)
    q = A.q
    if form in ("mini", "medium", "giant", "large_ring"):
        if form == "large_ring":
            build_ring_body(A, bc, skin)
        else:
            build_deck_body(A, bc, skin)
        wg = P["wings"]
        if q.hi or wg.get("lod1", True):
            build_wings(A, bc, bc.W / 2, wg["yc"], wg["zc"], wg["L"], wg["Hh"], wg["t"], tile=wing_tile)
        tl = P["tail"]
        build_tail(A, bc, -(bc.cd / 2 - 0.1), -bc.D / 2, bc.T - 0.4, tl["th"], tl["t"])
        place_valve(A, bc, P, r=0.2 * (bc.T / 4) ** 0.5)
    elif form == "lilo":
        build_lilo_body(A, bc, skin)
    return bc


def head_ctx(form, A):
    P = FORMS[form]
    h = P["head"]
    cw, cd, T = P["collider"]
    W, D, H = P["envelope"]
    k = min((h["hx"] / 1.85) ** 0.6, 1.25)
    if form == "lilo":
        back = cw / 2 - 0.12
        hc = HeadCtx(h["hx"], h["hz"], h["hy"], h["p"], (back + h["hy"], 0.0), fwd="x", seam=h["seam"], k=k)
        hc.neck_abs = 2.55  # collier posé sur l'oreiller, à la base de la tête
    else:
        back = cd / 2 - 0.12
        hc = HeadCtx(h["hx"], h["hz"], h["hy"], h["p"], (0.0, back + h["hy"]), fwd="y", seam=h["seam"], k=k)
    hc.lower_bill = h.get("lower_bill", True)
    hc.form = form
    hc.T = T
    hc.H = H
    return hc


# --- bouée carrée à filet ----------------------------------------------------------------
def build_ring_body(A, bc, skin):
    q, P = A.q, bc.P
    bc.hw0 = bc.cw / 2 + P["margin"]
    bc.hd0 = bc.cd / 2 + P["margin"]
    bc.R0 = P["R0"]
    seg = q.n(P["seg"], 2, 2)
    T = bc.T
    bc.rings = deck_profile(T, P["s"], P["b_in"], P["zm"], P["rt"], q.n(4, 1, 1), top_angles(q))
    hi = P["hole"]
    Ri = 1.6
    rr = [(bc.hw0 - i, bc.hd0 - i, max(bc.R0 - i, 0.05), z) for i, z in bc.rings]
    z_net = T - 0.16
    inner = [(hi + 0.16, hi + 0.16, Ri + 0.16, T), (hi + 0.045, hi + 0.045, Ri + 0.045, T - 0.05), (hi, hi, Ri, z_net)]
    if not q.hi:
        inner = [(hi + 0.1, hi + 0.1, Ri + 0.1, T), (hi, hi, Ri, z_net)]
    body = loft_rr(rr + inner, seg)
    bc.hole = hi
    top = m_top("ring_top", -bc.hw0, bc.hw0, -bc.hd0, bc.hd0)
    net = m_top("net", -hi, hi, -hi, hi)
    sr = side_rule(A, bc, skin)

    def rule(c, n):
        if n.z > 0.9 and c.z > T - 0.03:
            return top
        if n.z > 0.9 and c.z < T - 0.1 and c.z > T - 0.3:
            return net
        if max(abs(c.x), abs(c.y)) < hi + 0.3 and c.z > T - 0.3:
            return m_pal("yellow_dark", T - 0.3, T)
        return sr(c, n)
    A.add(body, rule, "ring")
    if q.detail:
        hw, hd, R = bc.outline_at(P["zm"])
        path = [(x, y, P["zm"]) for x, y in rrect(hw + 0.01, hd + 0.01, R, seg)]
        A.add(tube(path, 0.065, 4, closed=True), A.pal("yellow_dark"))


# --- matelas ------------------------------------------------------------------------------
def lilo_section(a_in, a_out, b, n, outer_sign):
    """Section superellipse (e = 3) d'un boudin ; a_out côté extérieur (bord du matelas)."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        a = a_out if (c * outer_sign) > 0 else a_in
        pts.append((a * math.copysign(abs(c) ** (2 / 3), c), b + b * math.copysign(abs(s) ** (2 / 3), s)))
    return pts


def build_lilo_body(A, bc, skin):
    q, P = A.q, bc.P
    T = bc.T
    bc.hw0 = 7.15
    bc.hd0 = atlas.LILO_HALF_D
    bc.R0 = 0.6
    top_tile = "lilo_hawaii" if skin == "hawaii" else "lilo_top"
    top = m_top(top_tile, -bc.hw0, bc.hw0, -bc.hd0, bc.hd0)
    if skin == "hawaii":
        side = r_tilebox("hawaii", (-8, 8, -4, 4, 0, T), 4.0)
    else:
        side = r_box("s_vinyl", (-8, 8, -4, 4, 0, T))
    b = (T - 0.02) / 2
    if not q.hi:
        # LOD1 : un seul coussin, boudins peints
        bc.rings = [(0.55, 0.0), (-0.0, 0.55), (0.0, T - 0.32), (0.3, T)]
        body = loft_rr([(bc.hw0 - i, bc.hd0 - i, max(bc.R0 - i, 0.05), z) for i, z in bc.rings], 2)
        A.add(body, r_if(lambda c, n: n.z > 0.9, r_const(top), side), "lilo")
    else:
        bc.rings = [(0.0, 0.0), (0.0, T)]
        ys = atlas.LILO_TUBE_Y
        nsec = q.n(12, 8, 8)
        xs_end = [6.85, 7.04, 7.15]
        for kk, yc in enumerate(ys):
            outer = 1 if kk == len(ys) - 1 else (-1 if kk == 0 else 0)
            a_in, a_out = 0.95, (1.1 if outer else 0.95)
            sec = lilo_section(a_in, a_out, b, nsec, outer if outer else 1)
            bm = bmesh.new()
            loops = []
            stations = [-x for x in reversed(xs_end)] + [0.0] + xs_end
            for x in stations:
                ax = abs(x)
                f = 1.0 if ax <= 6.85 else math.sqrt(max(0.0, 1 - ((ax - 6.85) / 0.3) ** 2))
                f = max(f, 0.18)
                loops.append([bm.verts.new((x, yc + sy * f, b + (sz - b) * f)) for sy, sz in sec])
            n = len(sec)
            for la, lb in zip(loops[:-1], loops[1:]):
                for i in range(n):
                    bm.faces.new((la[i], la[(i + 1) % n], lb[(i + 1) % n], lb[i]))
            bm.faces.new(list(reversed(loops[0])))
            bm.faces.new(loops[-1])
            solid(bm)
            A.add(bm, r_if(lambda c, n: n.z > 0.5, r_const(top), side), "tube")
        # soudures aux bouts
    # oreiller transversal sous la tête (hors du rectangle praticable, x >= 6.9)
    pil = rrect(0.55, 1.3, 0.5, 2 if q.hi else 1)
    pil = [(x + 7.45, z + 1.3) for x, z in pil]
    pw = puff(pil, 6.2, q.n(2, 1, 1), re=1.0)
    place(pw, basis((1, 0, 0), (0, 0, 1), (0, -1, 0)))
    A.add(pw, r_tilebox("hawaii", (6.9, 8.0, -3.1, 3.1, 0, 2.6)) if skin == "hawaii" else A.pal("yellow"), "pillow")
    # valve au bout -X du premier boudin (côté queue)
    build_valve(A, (-7.12, -2.9, 1.0), (-1, 0, 0.3), r=0.17)
    tl = P["tail"]
    build_tail(A, bc, -(bc.cw / 2 - 0.1), -bc.W / 2, T - 0.3, tl["th"], tl["t"], axis="x")


# =====================================================================================
# accessoires : prises de la tête
# =====================================================================================
def star_pts(r_out, r_in, n=5, rot=90.0):
    return [((r_out if i % 2 == 0 else r_in) * math.cos(math.radians(rot + 180.0 * i / n)),
             (r_out if i % 2 == 0 else r_in) * math.sin(math.radians(rot + 180.0 * i / n))) for i in range(2 * n)]


def heart_pts(s, n):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x * s / 17, (y + 2) * s / 17))
    return ccw(pts)


def lens_shape(shape, hc, n):
    hx = hc.hx
    if shape == "star":
        return star_pts(0.5 * hx, 0.27 * hx), 0.07 * hx
    if shape == "round":
        return superellipse(0.37 * hx, 0.37 * hx, 2.0, n), 0.07 * hx
    if shape == "heart":
        return heart_pts(0.44 * hx, n), 0.065 * hx
    if shape == "wide":
        pts = superellipse(0.42 * hx, 0.27 * hx, 3.2, n)
        return [(x * (1 + 0.12 * y / (0.27 * hx)), y) for x, y in pts], 0.075 * hx
    raise ValueError(shape)


def acc_glasses(A, hc, shape, frame_cell, lens_tile="lens"):
    """Prise eyes : lunettes (monture épaisse + verres + branches jusqu'au dos de la tête)."""
    q = A.q
    n = (q.n(14, 8, 8) if shape != "heart" else q.n(12, 8, 8)) if shape != "star" else 10
    pts, fw = lens_shape(shape, hc, n)
    pts = ccw(pts)
    inner = offset_poly(pts, fw)
    yg = hc.hy + 0.16 * hc.k
    th = 0.12 * hc.k
    ex = hc.ex if shape != "star" else hc.ex * 1.12
    zz = hc.ez + (0.03 * hc.hx if shape != "heart" else -0.02 * hc.hx)
    for sx in (-1, 1):
        at = (sx * ex, yg, zz)
        fr = ring_prism(pts, inner, -th / 2, th / 2) if q.hi else prism(pts, -th / 2, th / 2)
        place(fr, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=at))
        if q.hi:
            A.add(fr, A.pal(frame_cell), "glasses_frame")
            ln = bmesh.new()
            ln.faces.new([ln.verts.new((x, z, th / 2 - 0.035 * hc.k)) for x, z in inner])
            place(ln, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=at))
            rl = 0.8 * hc.hx
            A.add(ln, r_if(hc.front(0.5), r_const(hc.plane(lens_tile, at, rl, rl, mirror=sx > 0)), A.pal("lens")))
        else:
            rl = 0.8 * hc.hx
            A.add(fr, r_if(hc.front(0.5), r_const(hc.plane(lens_tile, at, rl, rl)), A.pal(frame_cell)))
    if q.hi:
        xin = min(abs(x) for x, z in pts if abs(z) < 0.15 * hc.hx) if shape != "star" else 0.25 * hc.hx
        br = tube([tuple(hc.P(-ex + xin * 0.9, yg, zz + 0.12 * hc.hx)), tuple(hc.P(0, yg + 0.03, zz + 0.16 * hc.hx)),
                   tuple(hc.P(ex - xin * 0.9, yg, zz + 0.12 * hc.hx))], 0.055 * hc.k, 4, up=tuple(hc.fwd))
        A.add(br, A.pal(frame_cell))
        xo = max(x for x, z in pts)
        if getattr(hc, "form", "") == "mini":
            return
        for sx in (-1, 1):
            zt = zz + 0.12 * hc.hx
            w = hc.half_width(zt)
            path = [hc.P(sx * (ex + xo * 0.92), yg - 0.02, zt), hc.P(sx * (w + 0.03), hc.hy * 0.5, zt),
                    hc.P(sx * (w + 0.03), -hc.hy + 0.03, zt - 0.05)]
            A.add(tube([tuple(p) for p in path], 0.05 * hc.k, 4, up=(0, 0, 1)), A.pal(frame_cell))


def flower_pts(r, n, petals=5):
    return [((r * (0.72 + 0.28 * math.cos(petals * 2 * math.pi * i / n))) * math.cos(2 * math.pi * i / n),
             (r * (0.72 + 0.28 * math.cos(petals * 2 * math.pi * i / n))) * math.sin(2 * math.pi * i / n)) for i in range(n)]


def add_flower(A, M, r, petal, centre, q, t=None, n=None):
    n = n or (15 if q.hi else 10)
    t = t or 0.16 * r
    f = puff(flower_pts(r, n), t, 1)
    place(f, M)
    A.add(f, A.pal(petal))
    if q.hi:
        c = lathe([(0.3 * r, 0.0), (0.2 * r, 0.12 * r), (0.0, 0.17 * r)], 6)
        place(c, M @ Matrix.Translation((0, 0, t / 2 - 0.02)))
        A.add(c, A.pal(centre))


def acc_swim_cap(A, hc):
    """Prise head_top : bonnet de bain bleu piscine à fleurs (dôme couvrant le haut de la tête)."""
    q = A.q
    n = q.n(18, 7, 7)
    z0 = 0.05 * hc.hz
    prof = []
    steps = q.n(4, 2, 2)
    for i in range(steps + 1):
        z = z0 + (hc.hz - z0) * i / steps
        prof.append((hc.half_width(z) + 0.09, z))
    prof[-1] = (hc.half_width(hc.hz * 0.985) * 0.7 + 0.05, hc.hz + 0.06)
    prof.append((0.0, hc.hz + 0.13))
    cap = lathe(prof, n, cap0=False)
    sy = (hc.hy + 0.13) / (hc.hx + 0.09)
    place(cap, hc.M((1, 0, 0), (0, sy, 0), (0, 0, 1), at=(0, 0.02, 0)))
    A.add(cap, hc.cyl("flower_cap", (0, 0, 0), z0, hc.hz + 0.15), "swim_cap")
    if q.hi and hc.form != "mini":  # bourrelet du bord
        path = []
        for i in range(n):
            a = 2 * math.pi * i / n
            w = hc.half_width(z0) + 0.09
            path.append(tuple(hc.P(w * math.cos(a), 0.02 + (hc.hy + 0.13) * math.sin(a), z0)))
        A.add(tube(path, 0.07, 5, closed=True), A.pal("pool_dark"))
    # grosses fleurs en relief
    spots = [(-0.5, 0.62, 0.36, "pink", "yellow"), (0.42, 0.8, 0.3, "white", "coral"),
             (0.8, 0.32, 0.26, "mint", "white"), (-0.08, 0.98, 0.24, "coral", "yellow")]
    for fx, fz, fr, pc, cc in (spots[:3] if hc.form != "mini" else spots[:2]) if q.hi else spots[:1]:
        x, z = fx * hc.hx, fz * hc.hz
        y = hc.hy + 0.2
        M = hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(x, y, z))
        add_flower(A, M, fr * hc.hx, pc, cc, q, t=0.14)


def bow_lobe(s, n):
    raw = [(0.08, 0.16), (0.55, 0.5), (0.92, 0.48), (1.0, 0.0), (0.92, -0.48), (0.55, -0.5), (0.08, -0.16)]
    pts = [(x * s, y * s) for x, y in raw]
    return chaikin(pts, 1) if n > 8 else pts


def acc_bowtie(A, hc, tile_or_cell, size, z=None, y=None):
    """Prise neck : noeud papillon (deux coques gonflées + noeud)."""
    q = A.q
    z = hc.neck_z if z is None else z
    y = (hc.hy + 0.05 * hc.k) if y is None else y
    t = min(0.26 * size, 0.3)
    for sx in (-1, 1):
        pts = [(sx * x, yy) for x, yy in bow_lobe(size, 10 if (q.hi and size > 1.2) else 6)]
        lb = puff(pts, t, 1) if q.hi else prism(ccw(pts), -t / 2, t / 2)
        place(lb, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(0, y, z)))
        if tile_or_cell in atlas.TILES:
            m = hc.plane(tile_or_cell, (0, y, z), 1.2 * size, 0.6 * size)
            A.add(lb, r_if(hc.front(0.3), r_const(m), A.pal("red")), "bowtie")
        else:
            A.add(lb, A.pal(tile_or_cell), "bowtie")
    kn = puff(superellipse(0.2 * size, 0.24 * size, 3, 8), t * 1.3, 1) if q.hi else \
        prism(superellipse(0.2 * size, 0.24 * size, 3, 4), -t * 0.65, t * 0.65)
    place(kn, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(0, y + 0.02, z)))
    A.add(kn, A.pal("red_dark" if tile_or_cell in ("polka", "red") else "black"))


def stache_path(hc, reach, curl, down=False, n=14):
    """Demi-moustache (côté +x) : part du centre sous le bec, s'élargit, finit en boucle."""
    pts = []
    for i in range(n):
        t = i / (n - 1)
        if t < 0.62:
            u = t / 0.62
            x = 0.05 * hc.hx + u * (reach - 0.05 * hc.hx)
            z = -0.12 * curl * math.sin(math.pi * u) * (1 if not down else 1.6)
            pts.append((x, z))
        else:
            u = (t - 0.62) / 0.38
            a = -math.pi / 2 + u * 1.75 * math.pi * (1 if not down else -1)
            cx, cz = reach, (curl if not down else -curl) * 0.55 + (-0.0)
            pts.append((cx + curl * 0.55 * math.cos(a) * (1 if not down else 1),
                        cz + curl * 0.55 * math.sin(a) * (1 if not down else -1)))
    return pts


def acc_moustache(A, hc, style):
    """Prise beak_under : moustaches (petite bouclée, guidon, pirate, morse blanche)."""
    q = A.q
    yb = hc.hy + hc.p * 0.5
    zb = getattr(hc, "beak_under_z", hc.bz - hc.bt) - 0.02
    if style == "walrus":
        raw = []
        nn = q.n(24, 10, 10)
        for i in range(nn):
            t = 2 * math.pi * i / nn
            x = 1.25 * hc.hx * math.cos(t)
            z = (0.32 * hc.hx if math.sin(t) > 0 else 0.42 * hc.hx) * math.sin(t)
            if math.sin(t) < 0:  # bord inférieur festonné
                z *= 1 + 0.18 * math.cos(6 * t)
                z -= 0.12 * hc.hx * (abs(math.cos(t)) ** 2)
            raw.append((x, z))
        st = puff(raw, min(0.42 * hc.k, hc.p * 0.95), q.n(2, 1, 1))
        place(st, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(0, hc.hy + hc.p * 0.45, zb - 0.22 * hc.hx)))
        A.add(st, A.pal("white"), "moustache")
        return
    cfg = {"curl": (0.52, 0.3, 0.085, 0.035, "brown", False), "handlebar": (1.0, 0.36, 0.13, 0.04, "brown", False),
           "pirate": (0.88, 0.34, 0.11, 0.035, "black", True)}[style]
    reach, curl, r0, r1, col, down = cfg
    reach *= hc.hx
    curl *= hc.hx
    rmax = hc.p * 0.48  # la moustache tient dans la profondeur du bec
    for sx in (-1, 1):
        pts = stache_path(hc, reach, curl, down, q.n(13, 4, 4))
        path = [tuple(hc.P(sx * x, yb, zb + z)) for x, z in pts]
        rad = lambda t, r0=r0, r1=r1: min(rmax, (r1 + (r0 - r1) * (1 - t) ** 0.8) * hc.hx)
        A.add(tube(path, rad, q.n(6, 3, 3), up=tuple(hc.fwd)), A.pal(col), "moustache")


def ellip_lathe(A, hc, prof, n, ry_scale, at=(0, 0, 0), cap0=True, cap1=True, tilt=0.0):
    """Lathe autour de l'axe haut local, écrasé en profondeur (y) : chapeaux à la mesure de la tête plate."""
    m = lathe(prof, n, cap0, cap1)
    M = hc.M((1, 0, 0), (0, ry_scale, 0), (0, 0, 1), at=at)
    if tilt:
        M = M @ Matrix.Rotation(math.radians(tilt), 4, "Y")
    place(m, M)
    return m


def hat_depth(hc, front_extra=0.0):
    """Demi-profondeur et centre (y local) disponibles pour un chapeau : dos de la tête -> devant."""
    y0, y1 = -hc.hy, hc.hy + front_extra
    return (y1 - y0) / 2, (y0 + y1) / 2


def acc_top_hat(A, hc, tilt=-9.0):
    q = A.q
    n = q.n(18, 8, 8)
    base = hc.hz * 0.82
    ry, yc = hat_depth(hc, 0.16)
    rb = 0.92 * hc.hx
    sy = ry / rb
    brim = [(rb, 0.0), (rb * 1.0, 0.09), (rb * 0.6, 0.11)]
    m = ellip_lathe(A, hc, [(0.0, -0.02)] + brim + [(0.0, 0.11)], n, sy, at=(0, yc, base), tilt=tilt)
    A.add(m, A.pal("black"), "top_hat")
    rc = 0.6 * hc.hx
    hh = 0.95 * hc.hx
    crown = [(rc * 0.98, 0.05), (rc * 1.08, hh * 0.96), (rc * 0.8, hh + 0.02), (0.0, hh + 0.03)]
    m = ellip_lathe(A, hc, [(0.0, 0.05)] + crown, n, (ry - 0.04) / rc, at=(0, yc, base), tilt=tilt)
    A.add(m, A.pal("black"))
    band = [(rc * 1.045, 0.08), (rc * 1.075, 0.36 * hh)]
    m = ellip_lathe(A, hc, band, n, (ry - 0.02) / rc, at=(0, yc, base), cap0=False, cap1=False, tilt=tilt)
    A.add(m, A.pal("red"))


def acc_monocle(A, hc):
    q = A.q
    r = 0.42 * hc.hx
    at = (-hc.ex, hc.hy + 0.2 * hc.k, hc.ez)
    n = q.n(16, 6, 6)
    ring = [tuple(hc.P(at[0] + r * math.cos(2 * math.pi * i / n), at[1], at[2] + r * math.sin(2 * math.pi * i / n))) for i in range(n)]
    A.add(tube(ring, 0.07 * hc.k, q.n(5, 3, 3), closed=True), A.pal("gold"), "monocle")
    if q.hi:
        gl = bmesh.new()
        gl.faces.new([gl.verts.new((x, z, 0.0)) for x, z in superellipse(r, r, 2, n)])
        place(gl, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=at))
        A.add(gl, A.pal("glass"))
        p0 = hc.P(at[0] - r * 0.7, at[1], at[2] - r * 0.7)
        p3 = hc.P(-hc.hx * 0.75, hc.hy + 0.05, hc.neck_z + 0.1)
        pts = bezier(p0, p0 + Vector((0, 0, -0.6)) + hc.D((-0.3, 0.1, 0)), p3 + hc.D((-0.3, 0.05, 0.3)), p3, 9)
        A.add(tube(pts, 0.035 * hc.k, 4), A.pal("gold"))


def acc_straw_hat(A, hc):
    q = A.q
    n = q.n(24, 10, 10)
    base = hc.hz * 0.8
    ry, yc = hat_depth(hc, 0.3)
    rb = 1.6 * hc.hx
    sy = ry / rb
    prof = [(0.0, 0.05), (rb * 0.5, 0.04), (rb, 0.02), (rb * 1.01, 0.11), (rb * 0.5, 0.15), (0.0, 0.16)]
    if not q.hi:
        prof = [(0.0, 0.05), (rb, 0.02), (rb, 0.12), (0.0, 0.16)]
    m = lathe(prof, n)
    M = hc.M((1, 0, 0), (0, sy, 0), (0, 0, 1), at=(0, yc, base))
    place(m, M)
    for v in m.verts:  # bord qui retombe sur les côtés, relevé devant
        d = v.co - hc.P(0, yc, base)
        xr = d.dot(hc.right) / rb
        yr = d.dot(hc.fwd) / max(ry, 1e-3)
        v.co.z += -0.18 * hc.hx * xr ** 2 + 0.06 * hc.hx * yr
    A.add(m, hc.box("straw", 1.2 * hc.hx), "straw_hat")
    rc = 0.66 * hc.hx
    hh = 0.78 * hc.hx
    crown = [(0.0, 0.05), (rc, 0.05), (rc * 0.94, 0.62 * hh), (rc * 0.6, hh), (0.0, hh + 0.02)]
    m = ellip_lathe(A, hc, crown, q.n(20, 8, 8), (ry - 0.02) / rc, at=(0, yc, base))
    A.add(m, hc.box("straw", 1.2 * hc.hx))
    band = [(rc * 1.025, 0.07), (rc * 0.99, 0.34 * hh)]
    m = ellip_lathe(A, hc, band, q.n(20, 8, 8), (ry) / rc, at=(0, yc, base), cap0=False, cap1=False)
    A.add(m, A.pal("coral"))
    if q.hi:  # noeud du ruban sur le côté droit
        for k, ang in ((0, 25), (1, -25)):
            lb = puff(superellipse(0.26 * hc.hx, 0.13 * hc.hx, 2.2, 8, cx=0.22 * hc.hx), 0.1, 1)
            place(lb, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(rc * 0.55, yc + ry * 0.75, base + 0.2 * hh)) @
                  Matrix.Rotation(math.radians(ang + (180 if k else 0)), 4, "Z"))
            A.add(lb, A.pal("coral"))
        for sx in (0.25, 0.7):
            path = [tuple(hc.P(rc * 0.6, yc + ry * 0.8, base + 0.2 * hh)),
                    tuple(hc.P(rc * (0.6 + 0.3 * sx), yc + ry * 0.85, base - 0.35 * hc.hx)),
                    tuple(hc.P(rc * (0.7 + 0.5 * sx), yc + ry * 0.85, base - 0.7 * hc.hx))]
            A.add(tube(path, lambda t: 0.08 * (1 - 0.4 * t) * hc.k, 3), A.pal("coral"))


def acc_bucket_hat(A, hc, crown_cell, band_cell, badge=None, flower=False):
    """Bob : calotte tronconique + bord incliné ; badge ancre (marin) ou fleur (touriste)."""
    q = A.q
    n = q.n(20, 8, 8)
    base = hc.hz * 0.72
    ry, yc = hat_depth(hc, 0.22)
    rc = 0.78 * hc.hx
    hh = 0.7 * hc.hx
    crown = [(rc, 0.0), (rc * 0.92, 0.75 * hh), (rc * 0.6, hh), (0.0, hh + 0.03)]
    m = ellip_lathe(A, hc, [(0.0, 0.0)] + crown, n, (ry - 0.05) / rc, at=(0, yc, base))
    A.add(m, A.pal(crown_cell), "bucket_hat")
    rb = 1.12 * hc.hx
    brim = [(rc * 0.9, 0.12), (rb, -0.28 * hc.hx), (rb * 0.99, -0.36 * hc.hx), (rc * 0.88, 0.04)]
    m = ellip_lathe(A, hc, brim, n, ry / rb, at=(0, yc, base), cap0=False, cap1=False)
    bm_close = m
    A.add(bm_close, A.pal(crown_cell))
    band = [(rc * 1.02, 0.1), (rc * 0.975, 0.36 * hh)]
    m = ellip_lathe(A, hc, band, n, (ry - 0.03) / rc, at=(0, yc, base), cap0=False, cap1=False)
    A.add(m, A.pal(band_cell))
    yf = yc + ry - 0.02
    if badge:
        r = 0.3 * hc.hx
        d = lathe([(r, 0.0), (r, 0.08), (0.0, 0.1)], q.n(14, 6, 6))
        at = (0, yf, base + 0.55 * hh)
        place(d, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=at))
        A.add(d, r_if(hc.front(0.5), r_const(hc.plane(badge, at, 2 * r, 2 * r)), A.pal("gold")))
    if flower:
        M = hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(0.45 * hc.hx, yf, base + 0.25 * hh))
        add_flower(A, M, 0.28 * hc.hx, "pink", "yellow", q, t=0.12)


def acc_sailor_scarf(A, hc):
    """Prise neck : foulard de marin (triangle marine, noeud rouge)."""
    q = A.q
    z = hc.neck_z + 0.05
    pts = [(-0.8 * hc.hx, 0.05), (0.8 * hc.hx, 0.05), (0.0, -0.75 * hc.hx)]
    pts = chaikin(pts, 1)
    s = puff(pts, 0.14, 1)
    place(s, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(0, hc.hy + 0.04, z)))
    A.add(s, A.pal("navy"), "scarf")
    kn = puff(superellipse(0.2 * hc.hx, 0.17 * hc.hx, 2.5, q.n(10, 6, 6)), 0.24, 1)
    place(kn, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(0, hc.hy + 0.1, z - 0.18 * hc.hx)))
    A.add(kn, A.pal("red"))


def acc_diving_mask(A, hc):
    """Prise eyes : masque de plongée (cadre bleu, ouverture : on voit les gros yeux), sangle."""
    q = A.q
    n = q.n(24, 10, 10)
    hw, hh = 0.98 * hc.hx, 0.44 * hc.hx
    pts = superellipse(hw, hh, 3.6, n)
    pts = [(x, z - 0.18 * hh * max(0.0, 1 - abs(x) / (0.3 * hw)) * (1 if z < 0 else 0)) for x, z in pts]
    inner = offset_poly(ccw(pts), 0.15 * hc.hx)
    at = (0, hc.hy + 0.12 * hc.k, hc.ez)
    fr = ring_prism(ccw(pts), inner, -0.13 * hc.k, 0.13 * hc.k)
    place(fr, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=at))
    A.add(fr, A.pal("pool"), "mask")
    if q.hi:
        for sx in (-1, 1):  # reflets sur la vitre
            bar = prism([(-0.04, -0.28), (0.04, -0.28), (0.04, 0.28), (-0.04, 0.28)], -0.01, 0.01)
            M = hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(sx * 0.5 * hw + 0.18 * hw, at[1] + 0.05, hc.ez + 0.05)) @ \
                Matrix.Rotation(math.radians(-32), 4, "Z") @ Matrix.Scale(hc.hx / 1.85, 4)
            place(bar, M)
            A.add(bar, A.pal("white"))
    w = hc.half_width(hc.ez) + 0.07
    nn = q.n(20, 8, 8)
    # sangle : l'arrière passe DANS la tête (le dos de la tête borde le rectangle praticable)
    path = [tuple(hc.P(w * math.cos(2 * math.pi * i / nn), 0.04 + (hc.hy - 0.02) * math.sin(2 * math.pi * i / nn), hc.ez))
            for i in range(nn)]
    A.add(tube(path, 0.09 * hc.k, 4, closed=True), A.pal("navy"))


def acc_snorkel(A, hc):
    q = A.q
    x0 = hc.half_width(hc.ez) + 0.2 * hc.k
    r = 0.14 * hc.k
    pts = bezier(hc.P(0.55 * hc.hx, hc.hy + hc.p * 0.55, hc.bz), hc.P(0.95 * hc.hx, hc.hy + 0.35, hc.bz - 0.1),
                 hc.P(x0 + 0.1, 0.1, hc.bz - 0.2), hc.P(x0, 0.0, hc.ez), q.n(7, 3, 3))
    pts += [tuple(hc.P(x0, 0.0, hc.ez + (hc.hz * 1.55 - hc.ez) * t)) for t in (0.5, 1.0)]
    A.add(tube(pts, r, q.n(8, 5, 5)), A.pal("coral"), "snorkel")
    top = hc.P(x0, 0.0, hc.hz * 1.55)
    cap = lathe([(r * 1.5, 0.0), (r * 1.6, 0.15), (r * 1.4, 0.32), (0.0, 0.36)], q.n(10, 5, 5))
    place(cap, basis((1, 0, 0), (0, 1, 0), (0, 0, 1), top))
    A.add(cap, A.pal("mint"))
    mp = lathe([(0.2 * hc.hx, 0.0), (0.22 * hc.hx, 0.08), (0.0, 0.1)], q.n(10, 5, 5))
    place(mp, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(0.48 * hc.hx, hc.hy + hc.p * 0.5, hc.bz)))
    A.add(mp, A.pal("mint"))
    if q.hi:  # clip sur la sangle
        cl = puff(superellipse(0.16, 0.24, 3, 8), 0.12, 1)
        place(cl, hc.M((0, 1, 0), (0, 0, 1), (1, 0, 0), at=(x0 - 0.12, 0.0, hc.ez)))
        A.add(cl, A.pal("mint"))


def crown_shell(n, rx, ry, h_lo, h_hi, pts_n, t):
    bm = bmesh.new()
    rows = []
    for k, (rad, off) in enumerate(((1.0, 0.0), (1.0 - t / rx, 0.0))):
        lo, hi = [], []
        for i in range(n):
            a = 2 * math.pi * i / n + math.pi / 2
            ph = (i * pts_n / n) % 1.0
            tri = 1 - abs(ph - 0.5) * 2
            z = h_lo + (h_hi - h_lo) * tri ** 1.4
            x, y = rx * rad * math.cos(a), ry * rad * math.sin(a)
            lo.append(bm.verts.new((x, y, 0.0)))
            hi.append(bm.verts.new((x, y, z)))
        rows.append((lo, hi))
    (olo, ohi), (ilo, ihi) = rows
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((olo[i], olo[j], ohi[j], ohi[i]))
        bm.faces.new((ilo[j], ilo[i], ihi[i], ihi[j]))
        bm.faces.new((ohi[i], ohi[j], ihi[j], ihi[i]))
        bm.faces.new((olo[j], olo[i], ilo[i], ilo[j]))
    return solid(bm)


def acc_crown(A, hc, tilt=8.0):
    q = A.q
    base = hc.hz * 0.78
    ry, yc = hat_depth(hc, 0.12)
    rx = 0.82 * hc.hx
    n = q.n(40, 20, 20)
    h_lo, h_hi = 0.45 * hc.hx, 1.05 * hc.hx
    sh = crown_shell(n, rx, ry, h_lo, h_hi, 5, 0.08 * hc.k)
    M = hc.M((1, 0, 0), (0, 1, 0), (0, 0, 1), at=(0, yc, base)) @ Matrix.Rotation(math.radians(tilt), 4, "Y")
    place(sh, M)
    A.add(sh, r_pal("gold", hc.z + base, hc.z + base + h_hi), "crown")
    cush = ellip_lathe(A, hc, [(rx * 0.95, 0.0), (rx * 0.85, 0.42 * hc.hx), (0.0, 0.68 * hc.hx)],
                       q.n(14, 6, 6), ry / rx * 0.95, at=(0, yc, base))
    transform(cush, Matrix.Translation(hc.P(0, yc, base)) @ Matrix.Rotation(math.radians(tilt), 4, hc.fwd) @
              Matrix.Translation(-hc.P(0, yc, base)))
    A.add(cush, A.pal("red"))
    band = ellip_lathe(A, hc, [(rx * 1.06, 0.0), (rx * 1.07, 0.27 * hc.hx)],
                       n // 2, (ry + 0.04) / (rx * 1.07), at=(0, yc, base), cap0=False, cap1=False)
    transform(band, Matrix.Translation(hc.P(0, yc, base)) @ Matrix.Rotation(math.radians(tilt), 4, hc.fwd) @
              Matrix.Translation(-hc.P(0, yc, base)))
    A.add(band, A.pal("gold_dark"))
    for i in range(5):  # perles aux pointes (gardées dans la bande de la tête)
        a = 2 * math.pi * (i + 0.5) / 5 + math.pi / 2
        rp = 0.1 * hc.hx
        yl = max(ry * math.sin(a), -ry + rp + 0.02)
        p = M @ Vector((rx * math.cos(a), yl, h_hi + 0.06 * hc.hx))
        s = sphere(rp, q.n(6, 4, 4), q.n(4, 3, 3))
        move(s, p)
        A.add(s, A.pal("white" if q.hi else "gold"))
    if q.hi:
        for x, col in ((-0.42, "pink"), (0.0, "pool"), (0.42, "mint")):
            j = puff(superellipse(0.13 * hc.hx, 0.16 * hc.hx, 2.2, 8), 0.1, 1)
            at = (x * rx, yc + ry + 0.03, base + 0.15 * hc.hx)
            place(j, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=at))
            transform(j, Matrix.Translation(hc.P(0, yc, base)) @ Matrix.Rotation(math.radians(tilt), 4, hc.fwd) @
                      Matrix.Translation(-hc.P(0, yc, base)))
            A.add(j, A.pal(col))


def acc_lei(A, hc):
    """Prise neck : collier de fleurs hawaïen (tube fleuri + grosses fleurs devant)."""
    q = A.q
    z = hc.neck_z + 0.18 * hc.hz
    rx = hc.neck_hw + 0.3 * hc.k
    ry = hc.hy - 0.15
    yc = 0.1
    n = q.n(14, 8, 8)
    path = []
    for i in range(n):
        a = 2 * math.pi * i / n
        front = max(0.0, math.sin(a))
        path.append(tuple(hc.P(rx * math.cos(a), yc + ry * math.sin(a), z - 0.35 * hc.hz * front ** 2)))
    ring = tube(path, 0.15 * hc.k, q.n(4, 3, 3), closed=True)
    A.add(ring, hc.cyl("lei", (0, 0, z), z - 0.6 * hc.hz, z + 0.2), "lei")
    cols = ["pink", "coral", "white", "yellow", "pink_dark", "coral", "white"]
    m = 4 if q.hi else 2
    for i in range(m):
        a = math.pi * (0.12 + 0.76 * i / (m - 1))
        front = math.sin(a)
        x, y = rx * math.cos(a), yc + ry * math.sin(a) + 0.12
        zz = z - 0.35 * hc.hz * front ** 2
        M = hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(x, y, zz)) @ Matrix.Rotation(math.radians(-35), 4, "X")
        add_flower(A, M, 0.22 * hc.hx * hc.k ** 0.2, cols[i % len(cols)], "yellow", q, t=0.12, n=12)


def acc_tricorn(A, hc):
    """Prise head_top : tricorne de pirate (vu de face : trois pointes), galon or, crâne au centre."""
    q = A.q
    base = hc.hz * 0.62
    ry, yc = hat_depth(hc, 0.18)
    w = 1.3 * hc.hx
    raw = [(-w, 0.35 * hc.hx), (-0.62 * hc.hx, 0.62 * hc.hx), (-0.25 * hc.hx, 0.92 * hc.hx), (0.0, 1.18 * hc.hx),
           (0.25 * hc.hx, 0.92 * hc.hx), (0.62 * hc.hx, 0.62 * hc.hx), (w, 0.35 * hc.hx), (0.7 * hc.hx, 0.02),
           (0.0, -0.12 * hc.hx), (-0.7 * hc.hx, 0.02)]
    pts = chaikin(raw, 1) if q.hi else list(raw)
    # pointes conservées
    keep = {0: raw[0], 3: raw[3], 6: raw[6]}
    if q.hi:
        pts = [p for p in pts]
        for idx, p in keep.items():
            j = min(range(len(pts)), key=lambda k: (pts[k][0] - p[0]) ** 2 + (pts[k][1] - p[1]) ** 2)
            pts[j] = p
    hat = puff(pts, 2 * ry, q.n(2, 1, 1), re=min(0.3, ry))
    place(hat, hc.M((1, 0, 0), (0, 0, 1), (0, -1, 0), at=(0, yc, base)))
    A.add(hat, A.pal("black"), "tricorn")
    if q.hi:
        top = [p for p in chaikin(raw[:7], 1, closed=False)]
        path = [tuple(hc.P(x * 0.97, yc + ry - 0.02, base + z - 0.03)) for x, z in top]
        A.add(tube(path, 0.07 * hc.k, 4, up=tuple(hc.fwd)), A.pal("gold"))
    r = 0.36 * hc.hx
    d = lathe([(r, 0.0), (r, 0.07), (0.0, 0.09)], q.n(14, 6, 6))
    at = (0, yc + ry - 0.04, base + 0.5 * hc.hx)
    place(d, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=at))
    A.add(d, r_if(hc.front(0.5), r_const(hc.plane("skull", at, 2 * r, 2 * r)), A.pal("white")))


def acc_eye_patch(A, hc):
    q = A.q
    r = hc.re * 1.2
    at = (-hc.ex, hc.hy + 0.14 * hc.k, hc.ez)
    p = puff(superellipse(r, r * 0.92, 2.2, q.n(14, 6, 6)), 0.12 * hc.k, 1)
    place(p, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=at))
    A.add(p, A.pal("black"), "eye_patch")
    if q.hi:
        pts = [hc.P(-hc.ex + 0.7 * r, at[1] - 0.02, hc.ez + 0.7 * r), hc.P(0.1 * hc.hx, hc.hy + 0.06, 0.62 * hc.hz),
               hc.P(0.62 * hc.hx, hc.hy + 0.02, 0.86 * hc.hz), hc.P(0.85 * hc.hx, 0.0, hc.half_width(0) * 0 + 0.85 * hc.hz)]
        A.add(tube([tuple(v) for v in pts], 0.05 * hc.k, 4, up=tuple(hc.fwd)), A.pal("black"))


def acc_lifeguard_cap(A, hc):
    q = A.q
    n = q.n(22, 8, 8)
    base = hc.hz * 0.55
    ry, yc = hat_depth(hc, 0.0)
    rc = hc.half_width(base) + 0.08
    hh = 0.7 * hc.hz
    prof = [(rc, 0.0), (rc * 0.98, 0.35 * hh), (rc * 0.85, 0.75 * hh), (rc * 0.5, 0.97 * hh), (0.0, hh)]
    m = ellip_lathe(A, hc, [(0.0, 0.0)] + prof, n, (ry + 0.04) / rc, at=(0, yc, base))
    A.add(m, A.pal("red"), "cap")
    vis = superellipse(0.72 * hc.hx, hc.p + 0.02, 2.4, q.n(16, 8, 8), phase=0.0)
    vis = [(x, y) for x, y in vis if y >= -0.01] + [(-0.72 * hc.hx, -0.3), (0.72 * hc.hx, -0.3)]
    vis = ccw(vis)
    vp = puff(vis, 0.1 * hc.k, 1)
    place(vp, hc.M(at=(0, hc.hy - 0.03, base + 0.05)) @ Matrix.Rotation(math.radians(-8), 4, "X"))
    A.add(vp, A.pal("red_dark"))
    b = sphere(0.1 * hc.hx, q.n(8, 4, 4), q.n(4, 3, 3))
    move(b, hc.P(0, yc, base + hh))
    A.add(b, A.pal("white"))
    if q.hi:  # pictogramme bouée blanc sur le devant
        rr = 0.24 * hc.hx
        nn = 16
        path = [tuple(hc.P(rr * math.cos(2 * math.pi * i / nn), yc + ry + 0.06, base + 0.42 * hh + rr * math.sin(2 * math.pi * i / nn)))
                for i in range(nn)]
        A.add(tube(path, 0.06 * hc.k, 4, closed=True), A.pal("white"))


def acc_whistle(A, hc):
    """Prise neck : cordon + sifflet (bleu piscine)."""
    q = A.q
    z = hc.neck_z + 0.1
    rx, ry = hc.neck_hw + 0.08, hc.hy - 0.04
    n = q.n(18, 6, 6)
    path = []
    for i in range(n):
        a = 2 * math.pi * i / n
        front = max(0.0, math.sin(a))
        path.append(tuple(hc.P(rx * math.cos(a), ry * math.sin(a), z - 0.55 * hc.hz * front ** 3)))
    A.add(tube(path, 0.045 * hc.k, 4, closed=True), A.pal("white"), "whistle_cord")
    wz = z - 0.55 * hc.hz - 0.25 * hc.k
    body = lathe([(0.0, -0.4), (0.18, -0.38), (0.24, -0.2), (0.24, 0.15), (0.2, 0.3), (0.0, 0.32)], q.n(12, 6, 6))
    M = hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(0, hc.hy + 0.0, wz)) @ Matrix.Rotation(math.radians(90), 4, "Y") @ \
        Matrix.Scale(hc.k * 1.15, 4)
    place(body, M)
    A.add(body, A.pal("pool"), "whistle")
    mp = prism(rrect(0.1, 0.08, 0.04, 1), 0, 0.35)
    place(mp, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(0.3 * hc.k, hc.hy + 0.0, wz)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
    A.add(mp, A.pal("pool_dark"))


def acc_sunscreen(A, hc):
    """Prise beak : trait de crème solaire blanche sur le bec."""
    hl = (hc.p + 0.25) / 2
    pts = rrect(0.16 * hc.hx, hl, 0.1, 2)
    s = puff(pts, 0.05, 1)
    place(s, hc.M(at=(0, hc.hy + hc.p - hl - 0.06, hc.bz + hc.bt / 2 - 0.005)))
    A.add(s, A.pal("white"), "sunscreen")
    if A.q.hi:
        for sx in (-1, 1):  # deux traits sur les joues
            c = puff(rrect(0.2 * hc.hx, 0.05, 0.04, 1), 0.04, 1)
            place(c, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=(sx * 0.7 * hc.hx, hc.hy + 0.005, -0.15 * hc.hz)))
            A.add(c, A.pal("white"))


def acc_camera(A, hc):
    """Prise neck : appareil photo sur sangle (boîtier + objectif vers l'avant)."""
    q = A.q
    z = hc.neck_z + 0.1
    rx, ry = hc.neck_hw + 0.1, hc.hy - 0.04
    n = q.n(18, 6, 6)
    path = []
    for i in range(n):
        a = 2 * math.pi * i / n
        front = max(0.0, math.sin(a))
        path.append(tuple(hc.P(rx * math.cos(a), ry * math.sin(a), z - 0.5 * hc.hz * front ** 3)))
    A.add(tube(path, 0.06 * hc.k, 4, closed=True), A.pal("navy"), "camera_strap")
    cz = z - 0.5 * hc.hz - 0.32 * hc.hx
    w, h, d = 0.62 * hc.hx, 0.36 * hc.hx, 0.17
    body = loft_rr([(w - 0.06, d - 0.03, 0.06, -h), (w, d, 0.09, -h + 0.06), (w, d, 0.09, h - 0.06), (w - 0.06, d - 0.03, 0.06, h)],
                   q.n(3, 1, 1))
    at = (0, hc.hy - 0.02, cz)
    place(body, hc.M((1, 0, 0), (0, 1, 0), (0, 0, 1), at=at))
    m = hc.plane("camera", (0, hc.hy - 0.02 + d, cz), 2 * w, 2 * h)
    A.add(body, r_if(hc.front(0.6), r_const(m), A.pal("black")), "camera")
    rl = 0.24 * hc.hx
    lens = lathe([(rl, 0.0), (rl, 0.22), (rl * 0.85, 0.26), (rl * 0.6, 0.25), (0.0, 0.24)], q.n(14, 6, 6))
    at2 = (0, hc.hy - 0.02 + d - 0.02, cz - 0.1 * h)
    place(lens, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=at2))
    A.add(lens, r_if(hc.front(0.6), r_const(hc.plane("camera", (0, at2[1], at2[2] + 0.4 * rl), 2.1 * rl * 1.6, 2.1 * rl * 1.6)),
                     A.pal("steel")))


def acc_captain_cap(A, hc):
    q = A.q
    n = q.n(24, 8, 8)
    base = hc.hz * 0.62
    ry, yc = hat_depth(hc, 0.05)
    rb = hc.half_width(base) + 0.1
    hb = 0.32 * hc.hx
    band = [(rb, 0.0), (rb, hb)]
    m = ellip_lathe(A, hc, [(0.0, 0.0)] + band + [(0.0, hb)], n, (ry + 0.02) / rb, at=(0, yc, base))
    A.add(m, hc.cyl("captain_band", (0, yc, 0), base, base + hb), "captain_cap")
    rt = rb * 1.22
    top = [(rb * 0.98, hb), (rt, hb + 0.38 * hc.hx), (rt * 1.02, hb + 0.46 * hc.hx), (rt * 0.9, hb + 0.52 * hc.hx), (0.0, hb + 0.56 * hc.hx)]
    m = ellip_lathe(A, hc, [(0.0, hb)] + top, n, (ry + 0.02) / rt, at=(0, yc, base))
    A.add(m, A.pal("white"))
    vis = superellipse(0.75 * hc.hx, hc.p + 0.02, 2.4, q.n(16, 8, 8))
    vis = ccw([(x, y) for x, y in vis if y >= -0.01] + [(-0.75 * hc.hx, -0.4), (0.75 * hc.hx, -0.4)])
    vp = puff(vis, 0.12 * hc.k, 1)
    place(vp, hc.M(at=(0, hc.hy - 0.04, base + 0.04)) @ Matrix.Rotation(math.radians(-10), 4, "X"))
    A.add(vp, A.pal("black"))
    r = 0.36 * hc.hx
    d = lathe([(r, 0.0), (r, 0.07), (r * 0.9, 0.12), (0.0, 0.13)], q.n(16, 6, 6))
    at = (0, yc + ry + 0.02, base + hb * 0.55 + 0.25 * hc.hx)
    place(d, hc.M((1, 0, 0), (0, 0, 1), (0, 1, 0), at=at))
    A.add(d, r_if(hc.front(0.5), r_const(hc.plane("anchor", at, 2 * r, 2 * r)), A.pal("gold")), "anchor")
    if q.hi:  # cordon doré au-dessus de la visière
        path = [tuple(hc.P(x, yc + ry + 0.05, base + 0.1 * hb + 0.03 * abs(x))) for x in
                [(-0.8 + 1.6 * i / 10) * rb for i in range(11)]]
        A.add(tube(path, 0.07 * hc.k, 5), A.pal("gold"))


def acc_bubble_pipe(A, hc):
    """Prise beak_under : pipe à bulles de savon (jouet, pas de tabac) + bulles irisées."""
    q = A.q
    s = hc.hx / 3.0
    p0 = hc.P(0.55 * hc.hx, hc.hy + hc.p * 0.55, hc.bz - 0.05)
    p3 = hc.P(1.35 * hc.hx, hc.hy + hc.p - 0.47 * s, hc.bz - 0.75 * s)
    pts = bezier(p0, p0 + hc.D((0.5 * s, 0.0, -0.1)), p3 + hc.D((-0.6 * s, 0.0, -0.4 * s)), p3, q.n(8, 4, 4))
    A.add(tube(pts, 0.13 * s * 1.3, q.n(8, 5, 5)), A.pal("pink"), "pipe")
    bowl = lathe([(0.0, -0.05), (0.32 * s, -0.04), (0.42 * s, 0.25 * s), (0.45 * s, 0.6 * s), (0.36 * s, 0.62 * s), (0.34 * s, 0.4 * s),
                  (0.0, 0.38 * s)], q.n(14, 6, 6))
    move(bowl, p3 + Vector((0, 0, -0.15 * s)))
    A.add(bowl, A.pal("pool"), "pipe_bowl")
    bub = [(1.55, 0.9, 0.3), (2.0, 1.75, 0.42), (1.45, 2.55, 0.22)] if q.hi else [(1.8, 1.3, 0.38)]
    for bx, bz, br in bub:
        r = min(br * hc.hx * 0.55, hc.hy + hc.p / 2 - 0.06)  # tient dans la bande avant
        sp = sphere(r, q.n(12, 6, 6), q.n(7, 4, 4))
        c = hc.P(bx * hc.hx * 0.55 + 0.5 * hc.hx, hc.p / 2, hc.bz + bz * s)
        move(sp, c)
        A.add(sp, r_const(m_plane("bubble", c, -hc.right, hc.up, 2 * r, 2 * r)), "bubble")


# =====================================================================================
# accessoires : prise corps (body)
# =====================================================================================
def body_shell(A, bc, z_top, z_bot_fn, t, ang_ok, rows, uv_fn, off=0.0):
    """Coque mince qui épouse le flanc du corps (bandes, cape) : points du contour dont l'angle passe
    `ang_ok`, de z_top à z_bot_fn(angle). UV directes via uv_fn(s, t) (s = abscisse, t = 0 haut -> 1 bas)."""
    seg = bc.q.n(bc.P.get("seg", 6), 2, 2)
    base = rrect(1, 1, 0.5, seg)  # pour les indices / angles uniquement
    idx = [i for i in range(len(base)) if ang_ok(math.atan2(*rrect(bc.hw0, bc.hd0, bc.R0, seg)[i][::-1]))]
    if not idx:
        return
    full = len(idx) == len(base)
    n = len(base)
    if not full:  # suite contiguë (gère le passage par l'indice 0)
        start = next(i for i in idx if (i - 1) % n not in idx)
        idx = [(start + k) % n for k in range(len(idx))]
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rows_o, rows_i = [], []
    s_vals = [k / (len(idx) - (0 if full else 1)) for k in range(len(idx))]
    for r in range(rows + 1):
        ro, ri = [], []
        for k, i in enumerate(idx):
            p0 = rrect(bc.hw0, bc.hd0, bc.R0, seg)[i]
            a = math.atan2(p0[1], p0[0])
            zb = z_bot_fn(a)
            z = z_top + (zb - z_top) * r / rows
            hw, hd, R = bc.outline_at(z)
            pts = rrect(hw + off, hd + off, R + off, seg)
            pts_o = rrect(hw + off + t, hd + off + t, R + off + t, seg)
            ro.append(bm.verts.new((pts_o[i][0], pts_o[i][1], z)))
            ri.append(bm.verts.new((pts[i][0], pts[i][1], z)))
        rows_o.append(ro)
        rows_i.append(ri)
    m = len(idx)
    segs = m if full else m - 1

    def face(vs, uvs):
        f = bm.faces.new(vs)
        for lp, uv in zip(f.loops, uvs):
            lp[uvl].uv = uv
    for r in range(rows):
        for k in range(segs):
            j = (k + 1) % m
            sk, sj = s_vals[k], (s_vals[j] if j > k else 1.0)
            t0, t1 = r / rows, (r + 1) / rows
            face((rows_o[r][k], rows_o[r + 1][k], rows_o[r + 1][j], rows_o[r][j]),
                 (uv_fn(sk, t0), uv_fn(sk, t1), uv_fn(sj, t1), uv_fn(sj, t0)))
            face((rows_i[r][j], rows_i[r + 1][j], rows_i[r + 1][k], rows_i[r][k]),
                 (uv_fn(sj, t0), uv_fn(sj, t1), uv_fn(sk, t1), uv_fn(sk, t0)))
    for k in range(segs):  # bords haut et bas
        j = (k + 1) % m
        sk, sj = s_vals[k], (s_vals[j] if j > k else 1.0)
        face((rows_o[0][k], rows_o[0][j], rows_i[0][j], rows_i[0][k]), (uv_fn(sk, 0), uv_fn(sj, 0), uv_fn(sj, 0), uv_fn(sk, 0)))
        face((rows_o[-1][j], rows_o[-1][k], rows_i[-1][k], rows_i[-1][j]), (uv_fn(sj, 1), uv_fn(sk, 1), uv_fn(sk, 1), uv_fn(sj, 1)))
    if not full:
        for k in (0, m - 1):
            for r in range(rows):
                vs = (rows_o[r][k], rows_i[r][k], rows_i[r + 1][k], rows_o[r + 1][k])
                if k == 0:
                    vs = vs[::-1]
                face(vs, [uv_fn(s_vals[k], r / rows)] * 4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def tile_uv_fn(tile, u_rep=1.0, flip_v=True):
    r = atlas.tile_uv(tile)
    return lambda s, t: _lerp_uv(r, (s * u_rep) % 1.0 if u_rep != 1.0 else s, (1 - t) if flip_v else t)


def acc_swimsuit_band(A, bc):
    """Prise body : bande de maillot rétro rayé rouge et blanc autour du corps."""
    z1, z0 = bc.T * 0.8, bc.T * 0.32
    sh = body_shell(A, bc, z1, lambda a: z0, 0.05, lambda a: True, A.q.n(4, 2, 2), tile_uv_fn("swim_stripes"), off=0.0)
    A.add(sh, None, "swimsuit_band")


def acc_cape(A, bc):
    """Prise body : cape royale rouge qui retombe sur l'arrière et les côtés (sous le dessus utile)."""
    z_top = bc.T - 0.07
    ok = lambda a: math.sin(a) < 0.5
    hem = lambda a: 0.45 + 0.25 * math.sin(7 * a) * (1 if A.q.hi else 0) + 0.6 * max(0.0, math.sin(a) + 0.3)
    sh = body_shell(A, bc, z_top, hem, 0.06, ok, A.q.n(4, 2, 2), tile_uv_fn("cape"), off=0.0)
    A.add(sh, None, "cape")
    if A.q.hi:  # agrafes dorées aux deux extrémités
        for sx in (-1, 1):
            hw, hd, R = bc.outline_at(bc.T - 0.5)
            p = Vector((sx * (hw + 0.12), 0.35 * hd, bc.T - 0.45))
            s = sphere(0.22, 10, 6)
            move(s, p)
            A.add(s, A.pal("gold"))


def acc_sauveteur_band(A, bc):
    """Prise body : bande rouge SAUVETEUR autour de la bouée (texte sur l'avant et l'arrière)."""
    z1, z0 = bc.T * 0.66, bc.T * 0.36
    rr = atlas.tile_uv("sauveteur")
    red = atlas.cell_uv("red")

    def uv(s, t):  # s = 0..1 autour ; deux inscriptions centrées avant (+Y) et arrière
        a = s * 2 * math.pi
        return _lerp_uv(rr, (s * 4.0 + 0.5) % 1.0, 1 - t)
    sh = body_shell(A, bc, z1, lambda a: z0, 0.05, lambda a: True, 2, uv)
    A.add(sh, None, "sauveteur_band")


def acc_skull_decal(A, bc):
    """Prise body : décalque tête de mort sur le flanc avant droit de la bouée."""
    z = bc.T * 0.5
    hw, hd, R = bc.outline_at(z)
    a = math.radians(30)
    x, y = (hw - 0.6) * math.sin(a) + 0.0, hd
    x = 3.6
    p = Vector((x, hd + 0.02, z))
    r = 1.05
    d = lathe([(r, 0.0), (r, 0.05), (r * 0.93, 0.09), (0.0, 0.1)], A.q.n(20, 8, 8))
    place(d, basis((1, 0, 0), (0, 0, 1), (0, 1, 0), p) @ Matrix.Rotation(0, 4, "Z"))
    A.add(d, r_if(lambda c, n: n.y > 0.5, r_const(m_plane("skull", p, (-1, 0, 0), (0, 0, 1), 2 * r, 2 * r)),
                  A.pal("black")), "skull_decal")


# --- registre --------------------------------------------------------------------------------
ACCESSORIES = {
    # nom: (prise, fonction, libellé)
    "glasses_star": ("eyes", lambda A, hc: acc_glasses(A, hc, "star", "pink"), "lunettes étoile roses"),
    "glasses_round": ("eyes", lambda A, hc: acc_glasses(A, hc, "round", "coral"), "lunettes rondes"),
    "glasses_heart": ("eyes", lambda A, hc: acc_glasses(A, hc, "heart", "mint"), "lunettes coeur"),
    "glasses_wide": ("eyes", lambda A, hc: acc_glasses(A, hc, "wide", "black"), "lunettes de touriste"),
    "swim_cap": ("head_top", acc_swim_cap, "bonnet de bain à fleurs"),
    "bowtie_red": ("neck", lambda A, hc: acc_bowtie(A, hc, "polka", 0.62 * hc.hx), "noeud papillon rouge à pois"),
    "bowtie_black": ("neck", lambda A, hc: acc_bowtie(A, hc, "black", 0.5 * hc.hx), "noeud papillon noir"),
    "moustache_curl": ("beak_under", lambda A, hc: acc_moustache(A, hc, "curl"), "petite moustache bouclée"),
    "moustache_handlebar": ("beak_under", lambda A, hc: acc_moustache(A, hc, "handlebar"), "moustache en guidon"),
    "moustache_pirate": ("beak_under", lambda A, hc: acc_moustache(A, hc, "pirate"), "moustache de pirate"),
    "moustache_walrus": ("beak_under", lambda A, hc: acc_moustache(A, hc, "walrus"), "grosse moustache blanche"),
    "top_hat": ("head_top", acc_top_hat, "haut-de-forme"),
    "monocle": ("eyes", acc_monocle, "monocle et chaînette"),
    "straw_hat": ("head_top", acc_straw_hat, "chapeau de paille à ruban"),
    "sailor_bob": ("head_top", lambda A, hc: acc_bucket_hat(A, hc, "white", "navy", badge="anchor"), "bob de marin, badge ancre"),
    "sailor_scarf": ("neck", acc_sailor_scarf, "foulard de marin"),
    "diving_mask": ("eyes", acc_diving_mask, "masque de plongée"),
    "snorkel": ("beak_under", acc_snorkel, "tuba"),
    "crown": ("head_top", acc_crown, "couronne dorée"),
    "lei": ("neck", acc_lei, "collier de fleurs"),
    "tricorn": ("head_top", acc_tricorn, "tricorne de pirate"),
    "eye_patch": ("eyes", acc_eye_patch, "cache-oeil"),
    "lifeguard_cap": ("head_top", acc_lifeguard_cap, "casquette rouge de sauveteur"),
    "whistle": ("neck", acc_whistle, "sifflet sur cordon"),
    "sunscreen": ("beak_under", acc_sunscreen, "trait de crème solaire"),
    "bucket_hat": ("head_top", lambda A, hc: acc_bucket_hat(A, hc, "khaki", "coral", flower=True), "bob de touriste"),
    "camera": ("neck", acc_camera, "appareil photo en bandoulière"),
    "captain_cap": ("head_top", acc_captain_cap, "casquette de capitaine, ancre dorée"),
    "bubble_pipe": ("beak_under", acc_bubble_pipe, "pipe à bulles de savon"),
    # prise corps
    "swimsuit_band": ("body", acc_swimsuit_band, "maillot rétro rayé"),
    "cape": ("body", acc_cape, "cape royale rouge"),
    "sauveteur_band": ("body", acc_sauveteur_band, "bande SAUVETEUR"),
    "skull_decal": ("body", acc_skull_decal, "décalque tête de mort"),
    "mariniere": ("body", None, "marinière (peau du corps)"),
    "hawaii_print": ("body", None, "imprimé chemise hawaïenne (peau du corps)"),
}
