"""Spécifications procédurales des GRANDES peluches v2 (lot plush_v2_big) : Balto, Ronron, Bobine.

Module pur (numpy uniquement), partagé par build_plush_v2_big.py, verify_plush_v2_big.py et
render_plush_v2_big.py. Indépendant de plush_specs.py (édité en parallèle par un autre agent) :
les conventions sont recopiées, pas importées.

Conventions (docs/decisions/0003, 0004, 0008) :
- 1 unité Blender = 1 stud. Axes Blender : X = largeur, Y = profondeur, Z = hauteur.
- Avant Roblox (-Z, LookVector) = +Y Blender. Gauche du personnage = -X Blender (suffixe _L).
- Pivot bottom_center : origine au centre de l'empreinte de l'enveloppe visuelle, au sol (z = 0).

Différences avec la chaîne v1 (build_plush.py) :
- la forme est un CHAMP DE DISTANCE SIGNÉE (SDF) : primitives (ellipsoïdes, cônes arrondis, tubes,
  dalles arrondies, tores) unies par union LISSE (smin), ce qui donne des raccords rembourrés au lieu
  des arêtes vives d'une union par remaillage ;
- deux contraintes de jeu sont imposées DANS le champ, donc garanties par construction :
  * dessous plat au sol (smax avec le demi-espace z >= 0),
  * rien au-dessus du dessus du collider à l'intérieur du rectangle praticable
    (smax avec min(z - top, distance hors rectangle)) ;
- la couleur n'est pas peinte sur les sommets d'un maillage haute définition mais évaluée PAR TEXEL
  (position 3D du texel reprojetée sur la surface SDF, normale = gradient du champ) : coutures,
  broderies et motifs restent nets quelle que soit la densité du maillage.

Tout est déterministe : aucune source d'aléa hors des tables de bruit initialisées avec SEED.
"""
from __future__ import annotations

import math

import numpy as np

SEED = 20261102

# ---------------------------------------------------------------------------
# Palette (sRGB hex)
# ---------------------------------------------------------------------------
HEX = {
    "navy": "#203055",          # broderies
    "cream": "#FFF1D2",
    "cream_warm": "#F6E7CC",
    "coral": "#FF684B",
    "mint": "#39E68B",
    "lilac": "#C3AEEB",
    "caramel": "#C98A4B",
    "sky": "#8CCBF0",
    "blush": "#F59A8C",
    # Balto (morse)
    "balto_body": "#8DB0C8",
    "balto_top": "#A3C3D8",
    "balto_dark": "#6A8EAA",
    "balto_muzzle": "#E9DFCB",
    "balto_whisker": "#F5EDDC",
    "balto_nose": "#B9787A",
    "balto_tusk": "#FFF3D9",
    # Ronron (chat)
    "cat_base": "#D99A5B",
    "cat_light": "#E6B074",
    "cat_stripe": "#A35F2B",
    "cat_cream": "#FFF0D8",
    "cat_pink": "#F3B2BE",
    "bell_gold": "#F2C94C",
    # Bobine (baleine)
    "whale_navy": "#2C4A7E",
    "whale_navy_dark": "#22396A",
    "whale_fin": "#5A86C8",
    "whale_cream": "#FFF0D6",
    "whale_groove": "#E3CBA4",
    "whale_spout": "#8CCBF0",
    "whale_spout_light": "#D8F0FF",
    "white": "#FFFDF6",
}


def srgb_to_linear(hex_color: str) -> np.ndarray:
    h = hex_color.lstrip("#")
    c = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def col(name: str) -> np.ndarray:
    return srgb_to_linear(HEX[name])


# ---------------------------------------------------------------------------
# Outils SDF (toutes les fonctions prennent P de forme (n, 3) et rendent (n,))
# ---------------------------------------------------------------------------
def rot_matrix(euler_deg):
    rx, ry, rz = [math.radians(a) for a in euler_deg]
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ my @ mx


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


def sd_ellipsoid(c, r, rot=(0, 0, 0)):
    c = np.asarray(c, float)
    r = np.asarray(r, float)
    R = rot_matrix(rot)

    def f(P):
        q = (P - c) @ R
        k0 = np.linalg.norm(q / r, axis=1)
        k1 = np.linalg.norm(q / (r * r), axis=1) + 1e-9
        return k0 * (k0 - 1.0) / k1
    return f


def sd_round_cone(a, b, r1, r2):
    """Cône arrondi exact (Inigo Quilez) entre a (rayon r1) et b (rayon r2)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2

    def f(P):
        pa = P - a
        y = pa @ ba
        z = y - l2
        v = pa * l2 - y[:, None] * ba
        x2 = np.einsum("ij,ij->i", v, v)
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        d_tip = np.sqrt(x2 + z2) * il2 - r2
        d_base = np.sqrt(x2 + y2) * il2 - r1
        d_side = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - r1
        return np.where(np.sign(z) * a2 * z2 > k, d_tip, np.where(np.sign(y) * a2 * y2 < k, d_base, d_side))
    return f


def sd_tube(points, radii):
    """Tube lisse le long d'une polyligne (union de cônes arrondis)."""
    segs = [sd_round_cone(points[i], points[i + 1], radii[i], radii[i + 1]) for i in range(len(points) - 1)]

    def f(P):
        d = segs[0](P)
        for s in segs[1:]:
            d = np.minimum(d, s(P))
        return d
    return f


def tube_param(P, points):
    """Abscisse curviligne (studs) du point de polyligne le plus proche, pour motifs le long d'un tube."""
    pts = [np.asarray(p, float) for p in points]
    best = np.full(len(P), 1e9)
    arc = np.zeros(len(P))
    acc = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        ab = b - a
        L = float(np.linalg.norm(ab))
        t = np.clip(((P - a) @ ab) / (L * L), 0, 1)
        d = np.linalg.norm(P - (a + t[:, None] * ab), axis=1)
        better = d < best
        best = np.where(better, d, best)
        arc = np.where(better, acc + t * L, arc)
        acc += L
    return arc, acc


def rrect2d(px, py, hx, hy, rc):
    """Distance signée à un rectangle arrondi 2D centré à l'origine."""
    rc = min(rc, hx, hy)
    dx = np.abs(px) - (hx - rc)
    dy = np.abs(py) - (hy - rc)
    return np.sqrt(np.maximum(dx, 0) ** 2 + np.maximum(dy, 0) ** 2) + np.minimum(np.maximum(dx, dy), 0) - rc


def sd_slab(cxy, half_xy, z0, z1, rc, re):
    """Dalle : rectangle arrondi en plan (rayon rc), extrudé entre z0 et z1, arêtes arrondies (re)."""
    cx, cy = cxy
    hx, hy = half_xy
    zc = 0.5 * (z0 + z1)
    hz = 0.5 * (z1 - z0)

    def f(P):
        d2 = rrect2d(P[:, 0] - cx, P[:, 1] - cy, hx, hy, rc)
        wx = d2 + re
        wz = np.abs(P[:, 2] - zc) - (hz - re)
        return np.sqrt(np.maximum(wx, 0) ** 2 + np.maximum(wz, 0) ** 2) + np.minimum(np.maximum(wx, wz), 0) - re
    return f


def round_rect_tb(u, v, hu, hv, rt, rb):
    """Rectangle arrondi 2D (u horizontal, v vertical) centré, rayon rt en haut et rb en bas."""
    r = np.where(v > 0, rt, rb)
    qu = np.abs(u) - hu + r
    qv = np.abs(v) - hv + r
    return np.minimum(np.maximum(qu, qv), 0) + np.sqrt(np.maximum(qu, 0) ** 2 + np.maximum(qv, 0) ** 2) - r


def round_rect_ell(u, v, hu, hv, rht, rvt, rhb, rvb):
    """Profil 2D (u horizontal, v vertical) à coins ELLIPTIQUES : coin haut (rht x rvt), coin bas (rhb x rvb).
    Astuce : l'axe u est dilaté pour rendre le coin circulaire (rayon rv), puis la distance est
    redivisée par le facteur (borne inférieure de la vraie distance, signe exact)."""
    s = np.where(v > 0, rvt / rht, rvb / rhb)
    r = np.where(v > 0, rvt, rvb)
    qu = np.abs(u) * s - hu * s + r
    qv = np.abs(v) - hv + r
    # intérieur : distance exacte à la face la plus proche (horizontale non dilatée, verticale telle quelle)
    d_in = np.where(qu > qv, (qu - r) / s, qv - r)
    # coin / extérieur : distance radiale dans l'espace dilaté, ramenée par la direction de la normale
    qup, qvp = np.maximum(qu, 0), np.maximum(qv, 0)
    L = np.sqrt(qup * qup + qvp * qvp) + 1e-12
    fac = np.sqrt((qup / (L * s)) ** 2 + (qvp / L) ** 2)
    d_out = (L - r) * fac
    return np.where((qu <= 0) & (qv <= 0), d_in, d_out)


def sd_cushion(x0, x1, y0, y1, z1, ex, ey, rc, k=0.3, z0=-0.4):
    """Corps « pouf » : intersection lisse de deux profils (XZ et YZ) à coins elliptiques et d'un rectangle
    arrondi en plan (rayon rc). ex / ey = (rh_haut, rv_haut, rh_bas, rv_bas). Avec rv_haut + rv_bas ~ z1
    le flanc est un bombé continu (pas de paroi verticale) ; le dessus reste plat jusqu'à rh_haut du bord,
    c'est-à-dire jusqu'à la ligne d'échantillonnage du dessus praticable.
    Le bas descend sous le sol (z0 < 0) : le plan du sol le recoupe net (dessous plat exactement à z = 0) ;
    le haut est relevé de k/4 pour compenser le décalage du smax entre les deux profils (dessus exact z1)."""
    cx, hx = 0.5 * (x0 + x1), 0.5 * (x1 - x0)
    cy, hy = 0.5 * (y0 + y1), 0.5 * (y1 - y0)
    zt = z1 + 0.25 * k
    zc = 0.5 * (z0 + zt)
    hz = 0.5 * (zt - z0)

    def f(P):
        v = P[:, 2] - zc
        dx = round_rect_ell(P[:, 0] - cx, v, hx, hz, *ex)
        dy = round_rect_ell(P[:, 1] - cy, v, hy, hz, *ey)
        dp = rrect2d(P[:, 0] - cx, P[:, 1] - cy, hx, hy, rc)
        return smax(smax(dx, dy, k), dp, k)
    return f


def sd_round_box(c, half, r, rot=(0, 0, 0)):
    c = np.asarray(c, float)
    half = np.asarray(half, float)
    R = rot_matrix(rot)

    def f(P):
        q = np.abs((P - c) @ R) - (half - r)
        return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(axis=1), 0) - r
    return f


def sd_torus(c, R_major, r_minor, rot=(0, 0, 0)):
    """Tore dans le plan local XY (axe local Z)."""
    c = np.asarray(c, float)
    R = rot_matrix(rot)

    def f(P):
        q = (P - c) @ R
        a = np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2) - R_major
        return np.sqrt(a * a + q[:, 2] ** 2) - r_minor
    return f


def squash(fn, c, scale, rot=(0, 0, 0)):
    """Applique une échelle anisotrope locale (autour de c, repère tourné) à un champ : forme aplatie.

    Distance approchée (multipliée par la plus petite échelle : borne inférieure)."""
    c = np.asarray(c, float)
    s = np.asarray(scale, float)
    R = rot_matrix(rot)
    m = float(s.min())

    def f(P):
        q = ((P - c) @ R) / s
        return fn(q) * m
    return f


# ---------------------------------------------------------------------------
# Bruit de valeur 3D (tables fixes, graine SEED)
# ---------------------------------------------------------------------------
class Noise:
    def __init__(self, seed=SEED):
        rng = np.random.default_rng(seed)
        p = rng.permutation(256)
        self.perm = np.concatenate([p, p]).astype(np.int64)
        self.vals = rng.random(256)

    def __call__(self, P, freq):
        q = P * freq
        i = np.floor(q).astype(np.int64)
        f = q - i
        u = f * f * (3 - 2 * f)
        i &= 255
        pm = self.perm

        def h(dx, dy, dz):
            return self.vals[pm[pm[pm[(i[:, 0] + dx) & 255] + ((i[:, 1] + dy) & 255)] + ((i[:, 2] + dz) & 255)] & 255]
        x0 = h(0, 0, 0) * (1 - u[:, 0]) + h(1, 0, 0) * u[:, 0]
        x1 = h(0, 1, 0) * (1 - u[:, 0]) + h(1, 1, 0) * u[:, 0]
        x2 = h(0, 0, 1) * (1 - u[:, 0]) + h(1, 0, 1) * u[:, 0]
        x3 = h(0, 1, 1) * (1 - u[:, 0]) + h(1, 1, 1) * u[:, 0]
        y0 = x0 * (1 - u[:, 1]) + x1 * u[:, 1]
        y1 = x2 * (1 - u[:, 1]) + x3 * u[:, 1]
        return y0 * (1 - u[:, 2]) + y1 * u[:, 2]

    def fbm(self, P, freq, octaves=3):
        s, a, tot = 0.0, 1.0, 0.0
        for o in range(octaves):
            s = s + a * self(P + 17.31 * o, freq * (2 ** o))
            tot += a
            a *= 0.5
        return s / tot


NOISE = Noise()


# ---------------------------------------------------------------------------
# Aides de peinture (masques booléens sur les texels)
# ---------------------------------------------------------------------------
def paint(C, mask, color, alpha=1.0):
    if np.isscalar(alpha):
        C[mask] = C[mask] * (1 - alpha) + np.asarray(color) * alpha
    else:
        a = alpha[mask][:, None]
        C[mask] = C[mask] * (1 - a) + np.asarray(color) * a
    return C


def dashes(u, dash, duty=0.55):
    return np.mod(u / dash, 1.0) < duty


def running_stitch(dist, u, width=0.045, dash=0.34, duty=0.55):
    """Point avant : |dist| < width sur une fraction duty de chaque période dash de u."""
    return (np.abs(dist) < width) & dashes(u, dash, duty)


def satin(C, mask, color, P, axis=(1.0, 0.3, 0.6), freq=34.0, depth=0.16):
    """Broderie au passé plat : couleur + fines stries de fil."""
    ax = np.asarray(axis, float)
    ax /= np.linalg.norm(ax)
    s = 0.5 + 0.5 * np.sin((P @ ax) * freq)
    shade = 1.0 - depth * s
    C[mask] = np.asarray(color)[None, :] * shade[mask][:, None]
    return C


def ellipse2d(a, b, cx, cy, rx, ry):
    return ((a - cx) / rx) ** 2 + ((b - cy) / ry) ** 2


def arc_dist(a, b, cx, cy, r):
    """Distance au cercle (cx, cy, r) dans un plan 2D et angle."""
    da, db = a - cx, b - cy
    return np.sqrt(da * da + db * db) - r, np.arctan2(db, da)


def seg2d(a, b, p0, p1):
    p0 = np.asarray(p0, float)
    p1 = np.asarray(p1, float)
    d = p1 - p0
    L2 = float(d @ d)
    t = np.clip(((a - p0[0]) * d[0] + (b - p0[1]) * d[1]) / L2, 0, 1)
    ex = a - (p0[0] + t * d[0])
    ey = b - (p0[1] + t * d[1])
    return np.sqrt(ex * ex + ey * ey), t * math.sqrt(L2)


def polyline2d(a, b, pts):
    best = np.full(a.shape, 1e9)
    arc = np.zeros(a.shape)
    acc = 0.0
    for p0, p1 in zip(pts[:-1], pts[1:]):
        d, s = seg2d(a, b, p0, p1)
        better = d < best
        best = np.where(better, d, best)
        arc = np.where(better, acc + s, arc)
        acc += math.dist(p0, p1)
    return best, arc


def gingham(a, b, period, c1, c2, c3):
    """Vichy : deux bandes croisées -> trois tons."""
    ba = np.mod(a / period, 1.0) < 0.5
    bb = np.mod(b / period, 1.0) < 0.5
    n = (ba.astype(int) + bb.astype(int))[:, None]
    return np.where(n == 2, c3[None, :], np.where(n == 1, c2[None, :], c1[None, :]))


# ---------------------------------------------------------------------------
# Description d'une peluche
# ---------------------------------------------------------------------------
class Part:
    def __init__(self, name, fn, owner="body", k=0.3, op="union"):
        self.name = name
        self.fn = fn
        self.owner = owner      # groupe de skinning
        self.k = k              # rayon de raccord lisse avec ce qui précède
        self.op = op


class Plush:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        self.displace = kw.get("displace")
        self.poses = {}

    # ---- géométrie ---------------------------------------------------------
    def rect_out(self, P):
        cx, cy = self.rect_center
        w, d = self.collider_size[0], self.collider_size[1]
        return rrect2d(P[:, 0] - cx, P[:, 1] - cy, w / 2.0, d / 2.0, 0.0)

    def _bounds(self):
        """Boîte englobante de chaque primitive (échantillonnage 0,2 stud), pour ne l'évaluer que près
        d'elle : hors de la boîte élargie de k + 0,4 stud, smin(F, d, k) = F exactement."""
        if getattr(self, "_bb", None) is not None:
            return self._bb
        lo = np.array(self.grid_lo, float)
        hi = np.array(self.grid_hi, float)
        g = [np.arange(lo[a], hi[a] + 1e-9, 0.2) for a in range(3)]
        X, Y, Z = np.meshgrid(*g, indexing="ij")
        Pg = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
        bb = []
        for k, pt in enumerate(self.parts):
            if k < 2 or pt.op != "union":
                bb.append(None)
                continue
            d = pt.fn(Pg)
            m = d < 0.15
            if not m.any():
                bb.append(None)
                continue
            marg = pt.k + 0.45
            bb.append((Pg[m].min(axis=0) - marg, Pg[m].max(axis=0) + marg))
        self._bb = bb
        return bb

    def field(self, P, parts=False):
        F = None
        D = {}
        bb = self._bounds()
        for pt, b in zip(self.parts, bb):
            if b is None:
                d = pt.fn(P)
            else:
                m = np.all((P >= b[0]) & (P <= b[1]), axis=1)
                d = np.full(len(P), 1e3)
                if m.any():
                    d[m] = pt.fn(P[m])
            if parts:
                D[pt.name] = d
            if F is None:
                F = d
            elif pt.op == "union":
                F = smin(F, d, pt.k)
            else:
                F = smax(F, -d, pt.k)
        if self.displace is not None:
            F = F + self.displace(P)
        F = smax(F, -P[:, 2], self.floor_k)  # dessous plat au sol
        clip = np.minimum(P[:, 2] - self.top, -self.rect_out(P))
        # rien au-dessus du dessus dans le rectangle praticable ; congé large seulement là où la tête sort
        # du dessus (clip_k fonction de la position), étroit ailleurs pour que le dessus reste exactement à top
        k = self.clip_k(P) if callable(self.clip_k) else np.full(len(P), float(self.clip_k))
        h = np.maximum(k - np.abs(F - clip), 0.0) / k
        F = np.maximum(F, clip) + h * h * k * 0.25
        if parts:
            return F, D
        return F

    # ---- bones ---------------------------------------------------------------
    def belly_bone_names(self):
        return [f"Belly_{i}{j}" for j in range(3) for i in range(3)]  # i = colonne X, j = rangée Y Blender

    def belly_spacing(self):
        return (self.collider_size[0] / 3.0, self.collider_size[1] / 3.0)

    def belly_bone_heads(self):
        cx, cy = self.rect_center
        sx, sy = self.belly_spacing()
        z = self.top - 1.0
        return {f"Belly_{i}{j}": np.array([cx + (i - 1) * sx, cy + (j - 1) * sy, z])
                for j in range(3) for i in range(3)}

    def bone_names(self):
        return ["Root"] + self.belly_bone_names() + list(self.secondary.keys())

    # ---- poids ---------------------------------------------------------------
    def owner_memberships(self, D):
        groups = {}
        for pt in self.parts:
            if pt.op != "union":
                continue
            s = np.exp(-np.clip(D[pt.name], 0, None) / self.skin_falloff)
            groups[pt.owner] = np.maximum(groups.get(pt.owner, 0), s)
        return groups

    def skin_weights(self, P, max_influences=4):
        """Poids normalisés (décision 0004) :
        - corps : Root (bas, immobile) <-> grille 3x3 du ventre (haut), t = z / top, interpolation
          barycentrique sur la grille triangulée (3 bones) -> 4 influences au plus avec Root ;
        - autres groupes : leur bone secondaire ; ancrés à Root près du sol (z < 0,6)."""
        n = len(P)
        _, D = self.field(P, parts=True)
        groups = self.owner_memberships(D)
        total = sum(groups.values()) + 1e-12
        names = self.bone_names()
        W = {k: np.zeros(n) for k in names}
        body = groups.get("body", np.zeros(n)) / total
        t = np.clip(P[:, 2] / self.top, 0.0, 1.0)
        W["Root"] += body * (1.0 - t)
        cx, cy = self.rect_center
        sx, sy = self.belly_spacing()
        u = np.clip((P[:, 0] - cx) / sx + 1.0, 0.0, 2.0)
        v = np.clip((P[:, 1] - cy) / sy + 1.0, 0.0, 2.0)
        i0 = np.minimum(np.floor(u).astype(int), 1)
        j0 = np.minimum(np.floor(v).astype(int), 1)
        fu = u - i0
        fv = v - j0
        lower = (fu + fv) <= 1.0
        bw = body * t
        for ii in range(3):
            for jj in range(3):
                w = np.zeros(n)
                # triangle inférieur : (i0,j0) 1-fu-fv ; (i0+1,j0) fu ; (i0,j0+1) fv
                w += np.where(lower & (i0 == ii) & (j0 == jj), 1 - fu - fv, 0)
                w += np.where(lower & (i0 + 1 == ii) & (j0 == jj), fu, 0)
                w += np.where(lower & (i0 == ii) & (j0 + 1 == jj), fv, 0)
                # triangle supérieur : (i0+1,j0+1) fu+fv-1 ; (i0,j0+1) 1-fu ; (i0+1,j0) 1-fv
                w += np.where(~lower & (i0 + 1 == ii) & (j0 + 1 == jj), fu + fv - 1, 0)
                w += np.where(~lower & (i0 == ii) & (j0 + 1 == jj), 1 - fu, 0)
                w += np.where(~lower & (i0 + 1 == ii) & (j0 == jj), 1 - fv, 0)
                W[f"Belly_{ii}{jj}"] += bw * w
        floor = np.clip(1.0 - P[:, 2] / 1.0, 0.0, 1.0)
        for bname, (_h, owner) in self.secondary.items():
            g = groups.get(owner, np.zeros(n)) / total
            W[bname] += g * (1.0 - floor)
            W["Root"] += g * floor
        M = np.stack([W[k] for k in names], axis=1)
        M[M < 1e-4] = 0.0
        order = np.argsort(-M, axis=1, kind="stable")
        keep = np.zeros_like(M, dtype=bool)
        keep[np.arange(n)[:, None], order[:, :max_influences]] = True
        M = np.where(keep, M, 0.0)
        s = M.sum(axis=1, keepdims=True)
        orphan = s[:, 0] <= 1e-9
        M[orphan, 0] = 1.0
        M = M / M.sum(axis=1, keepdims=True)
        return names, M


# ---------------------------------------------------------------------------
# Poses : {bone: {"t": (dx, dy, dz), "r": (axis_xyz, angle_deg)}} en espace modèle Blender
# ---------------------------------------------------------------------------
def belly_pose(pl, dz, radial):
    out = {}
    cx, cy = pl.rect_center
    for name, h in pl.belly_bone_heads().items():
        ox = np.sign(round(h[0] - cx, 3))
        oy = np.sign(round(h[1] - cy, 3))
        out[name] = {"t": (float(ox * radial[0]), float(oy * radial[1]), float(dz)), "r": None}
    return out


def standard_poses(pl, secondary_poses):
    """Poses de démonstration calibrées sur la hauteur du dessus (ratios de config/runtime.json)."""
    top = pl.top
    w, d = pl.collider_size[0], pl.collider_size[1]
    rad = (0.07 * w, 0.07 * d)
    poses = {
        "rest": {},
        "fall": belly_pose(pl, 0.114 * top, (-0.25 * rad[0], -0.25 * rad[1])),
        "impact": belly_pose(pl, -0.272 * top, rad),
        "rebound": belly_pose(pl, 0.05 * top, (-0.1 * rad[0], -0.1 * rad[1])),
        "player_landing": belly_pose(pl, -0.08, (0.0, 0.0)),
    }
    poses["player_landing"]["Belly_11"] = {"t": (0.0, 0.0, -0.15), "r": None}
    for pname, sec in secondary_poses.items():
        poses[pname].update(sec)
    return poses


# ---------------------------------------------------------------------------
# Peinture commune : passepoil du plateau, couture du bas, étiquette cousue
# ---------------------------------------------------------------------------
def piping(pl, P, N, C, color, margin=0.32, width=0.11):
    """Cordon passepoilé autour du plateau praticable (torsadé)."""
    cx, cy = pl.rect_center
    w, d = pl.collider_size[0], pl.collider_size[1]
    dd = rrect2d(P[:, 0] - cx, P[:, 1] - cy, w / 2 + margin, d / 2 + margin, 0.6)
    m = (np.abs(dd) < width) & (P[:, 2] > pl.top - 0.9) & (N[:, 2] > 0.15)
    ang = np.arctan2(P[:, 1] - cy, P[:, 0] - cx) * (w + d) / 3.2
    tw = 0.5 + 0.5 * np.sin(ang * 22.0 + dd * 30.0)
    cc = np.asarray(color)[None, :] * (0.86 + 0.14 * tw[:, None])
    C[m] = cc[m]
    # ombre portée juste à l'intérieur
    sh = (dd < -width) & (dd > -width - 0.08) & (P[:, 2] > pl.top - 0.9)
    C[sh] *= 0.82
    return C


def bottom_seam(P, N, C, z=0.42, color=None, period_u=None):
    m = (np.abs(P[:, 2] - z) < 0.05) & (np.abs(N[:, 2]) < 0.8)
    u = np.arctan2(P[:, 1], P[:, 0]) * 8.0
    m &= dashes(u, 0.36)
    if color is not None:
        C[m] = color
    return C


def tag_paint(P, N, C, center, half_xz, base, label, text_col, stitch_col):
    """Étiquette textile cousue : bord piqué, bande de couleur, lignes de « texte » brodées."""
    a = P[:, 0] - center[0]
    b = P[:, 2] - center[2]
    on = (np.abs(a) < half_xz[0] + 0.05) & (np.abs(b) < half_xz[1] + 0.05) & (np.abs(P[:, 1] - center[1]) < 0.35)
    C[on] = base
    band = on & (b > half_xz[1] * 0.35)
    C[band] = label
    # texte : trois courtes lignes brodées + petit cœur
    for k, (ln, off) in enumerate(((0.75, -0.05), (0.55, -0.32), (0.65, -0.58))):
        m = on & (np.abs(b - off * half_xz[1]) < 0.045) & (np.abs(a) < ln * half_xz[0]) & dashes(a + 3, 0.12, 0.7)
        C[m] = text_col
    heart = on & (ellipse2d(a, b, 0.0, half_xz[1] * 0.68, 0.16, 0.12) < 1.0)
    C[heart] = text_col
    edge = on & ((np.abs(np.abs(a) - (half_xz[0] - 0.08)) < 0.025) | (np.abs(np.abs(b) - (half_xz[1] - 0.08)) < 0.025))
    edge &= (np.abs(a) < half_xz[0] - 0.05) & (np.abs(b) < half_xz[1] - 0.05)
    edge &= dashes(a + b + 5, 0.1, 0.6)
    C[edge] = stitch_col
    return C


# ============================== BALTO (morse) ==============================
def balto():
    top = 6.0
    rect_center = (0.0, -0.6)  # rectangle praticable 12 x 12 : x [-6, 6], y [-6.6, 5.4]
    # arrondis du dessus commençant juste au-delà de la ligne d'échantillonnage (0,25 stud dans le rectangle)
    body = sd_cushion(-7.15, 7.15, -7.45, 6.3, 6.12, ex=(1.38, 2.7, 1.5, 3.7), ey=(1.08, 2.4, 1.2, 3.8), rc=2.6)
    belly = sd_slab((0.0, -0.4), (6.6, 6.4), 0.0, 3.2, rc=3.4, re=1.5)
    head = sd_ellipsoid((0.0, 5.95, 5.0), (4.0, 1.68, 3.05), rot=(-14, 0, 0))
    pad_l = sd_ellipsoid((-1.28, 6.6, 4.2), (1.58, 0.86, 1.12))
    pad_r = sd_ellipsoid((1.28, 6.6, 4.2), (1.58, 0.86, 1.12))
    nose = sd_ellipsoid((0.0, 6.62, 5.42), (0.78, 0.5, 0.42))
    brow_l = sd_ellipsoid((-1.6, 6.5, 6.6), (0.85, 0.5, 0.4), rot=(0, -12, 0))
    brow_r = sd_ellipsoid((1.6, 6.5, 6.6), (0.85, 0.5, 0.4), rot=(0, 12, 0))
    tusk_l = sd_tube([(-0.98, 6.62, 3.45), (-1.08, 7.02, 2.0), (-0.95, 6.98, 0.78)], [0.44, 0.34, 0.25])
    tusk_r = sd_tube([(0.98, 6.62, 3.45), (1.08, 7.02, 2.0), (0.95, 6.98, 0.78)], [0.44, 0.34, 0.25])
    # moustache touffue : bourrelets festonnés le long du bas des coussinets
    bristles = []
    for side in (-1, 1):
        for k in range(7):
            a = k / 6.0
            x = side * (0.22 + 2.4 * a)
            y = 7.02 - 0.75 * a * a
            z = 3.32 + 0.42 * a
            bristles.append(sd_ellipsoid((x, y, z), (0.42, 0.34, 0.4)))

    def bristle_fn(P):
        d = bristles[0](P)
        for bb in bristles[1:]:
            d = np.minimum(d, bb(P))
        return d

    # nageoires avant aux coins avant (pointées vers l'extérieur et l'avant), nageoires arrière aux coins
    # arrière (pointées vers l'extérieur et l'arrière) = « queue » du morse
    fl_l = sd_ellipsoid((-6.3, 5.4, 0.46), (2.05, 1.05, 0.44), rot=(0, 8, -40))
    fl_r = sd_ellipsoid((6.3, 5.4, 0.46), (2.05, 1.05, 0.44), rot=(0, -8, 40))
    tail_root = sd_ellipsoid((0.0, -6.6, 0.8), (2.4, 0.85, 0.75))
    fluke_l = sd_ellipsoid((-6.1, -5.95, 0.42), (2.05, 1.0, 0.4), rot=(0, 6, 35))
    fluke_r = sd_ellipsoid((6.1, -5.95, 0.42), (2.05, 1.0, 0.4), rot=(0, -6, -35))
    tag = sd_round_box((-3.6, -7.22, 1.0), (0.42, 0.05, 0.6), 0.04)

    parts = [
        Part("body", body, "body"),
        Part("belly", belly, "body", k=0.9),
        Part("head", head, "head", k=0.8),
        Part("pad_l", pad_l, "head", k=0.3),
        Part("pad_r", pad_r, "head", k=0.3),
        Part("nose", nose, "head", k=0.25),
        Part("brow_l", brow_l, "head", k=0.3),
        Part("brow_r", brow_r, "head", k=0.3),
        Part("bristles", bristle_fn, "head", k=0.12),
        Part("tusk_l", tusk_l, "head", k=0.12),
        Part("tusk_r", tusk_r, "head", k=0.12),
        Part("flipper_l", fl_l, "flipper_l", k=0.45),
        Part("flipper_r", fl_r, "flipper_r", k=0.45),
        Part("tail_root", tail_root, "tail", k=0.5),
        Part("fluke_l", fluke_l, "tail", k=0.35),
        Part("fluke_r", fluke_r, "tail", k=0.35),
        Part("tag", tag, "body", k=0.03),
    ]

    pl = Plush(
        asset_id="toy_plush_balto", label="Balto", name_fr="Morse Balto", size_tier="large",
        envelope=[16.0, 15.0, 8.0], collider_size=[12.0, 12.0, 6.0], walkable=[12.0, 12.0],
        rect_center=rect_center, top=top, parts=parts, floor_k=0.35,
        clip_k=lambda P: 0.1 + 0.35 * np.clip((P[:, 1] - 4.2) / 0.6, 0, 1) * np.clip((5.4 - np.abs(P[:, 0])) / 0.8, 0, 1),
        voxel=0.07, grid_lo=(-8.6, -8.1, -0.3), grid_hi=(8.6, 8.1, 8.4),
        lod0_target=4600, lod0_range=(3500, 5000), lod1_target=860, lod1_max=900,
        tex0=1024, tex1=256, skin_falloff=0.35, behavior="stable",
        secondary={
            "Head": (np.array([0.0, 5.2, 4.6]), "head"),
            "Flipper_L": (np.array([-5.4, 4.8, 0.8]), "flipper_l"),
            "Flipper_R": (np.array([5.4, 4.8, 0.8]), "flipper_r"),
            "Tail": (np.array([0.0, -6.2, 0.8]), "tail"),
        },
    )

    def color_fn(P, N, D):
        n = len(P)
        names = list(D.keys())
        stack = np.stack([D[k] for k in names], axis=1)
        reg = np.array(names)[np.argmin(stack, axis=1)]
        C = np.tile(col("balto_body"), (n, 1))
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        # dégradé ventral plus soutenu près du sol
        low = np.clip(1.0 - z / 1.6, 0, 1)
        C *= (1.0 - 0.12 * low)[:, None]
        # plateau supérieur plus clair (panneau cousu)
        topm = (N[:, 2] > 0.75) & (z > top - 0.4)
        C[topm] = col("balto_top")
        # taches de peau (morse) discrètes
        sp = NOISE(P, 0.9)
        C[(sp > 0.8) & np.isin(reg, ["body", "belly", "head"])] *= 0.93
        # plis du cou sur les flancs, juste derrière la tête (creux ombré + bourrelet éclairé)
        side = (np.abs(N[:, 0]) > 0.45) & np.isin(reg, ["body", "belly"])
        for y0 in (2.1, 3.0, 3.85):
            yy = y0 + 0.45 * np.sin(z * 0.75) - 0.08 * (6.0 - z)
            dy = y - yy
            band = side & (z > 0.9) & (z < 4.9 - 0.4 * (y0 - 2.1))
            C[band & (np.abs(dy) < 0.06)] *= 0.74
            lit = band & (dy > 0.06) & (dy < 0.36)
            C[lit] *= (1.0 + 0.10 * (1 - (dy[lit] - 0.06) / 0.3))[:, None]
        # nageoires et queue plus foncées + « doigts » piqués
        for rg in ("flipper_l", "flipper_r", "fluke_l", "fluke_r", "tail_root"):
            C[reg == rg] = col("balto_dark")
        for rg, cx_, cy_, th, sgn in (("flipper_l", -6.3, 5.4, -40, -1), ("flipper_r", 6.3, 5.4, 40, 1),
                                      ("fluke_l", -6.1, -5.95, 35, -1), ("fluke_r", 6.1, -5.95, -35, 1)):
            m = (reg == rg) & (N[:, 2] > 0.15)
            t = math.radians(th)
            lu = (x - cx_) * math.cos(t) + (y - cy_) * math.sin(t)
            lv = -(x - cx_) * math.sin(t) + (y - cy_) * math.cos(t)
            for off in (-0.4, 0.0, 0.4):
                st = m & (np.abs(lv - off) < 0.045) & (sgn * lu > 0.2) & dashes(lu + 5, 0.26)
                C[st] = col("navy")
            rim = m & (sgn * lu > 1.55)
            C[rim] *= 0.88
        # tête : un peu plus claire, coussinets crème, nez rosé
        C[reg == "head"] = col("balto_body") * 1.04
        for rg in ("brow_l", "brow_r"):
            C[reg == rg] = col("balto_body") * 1.04
        pads = np.isin(reg, ["pad_l", "pad_r"])
        C[pads] = col("balto_muzzle")
        C[reg == "nose"] = col("balto_nose")
        # moustache touffue : fils brodés (stries verticales)
        br = reg == "bristles"
        C[br] = col("balto_whisker")
        stri = 0.5 + 0.5 * np.sin(x * 26.0 + 2.0 * np.sin(z * 9.0))
        C[br] *= (0.86 + 0.14 * stri[br])[:, None]
        # brins de moustache brodés sur les coussinets (traits courts descendants)
        pf = pads & (N[:, 1] > 0.2)
        stri2 = np.mod((x + 0.15 * z) / 0.22, 1.0) < 0.35
        C[pf & stri2 & (z < 3.95)] *= 0.88
        # points de moustache (trous) brodés navy
        for sgn in (-1, 1):
            for (dx_, dz_) in ((0.6, 4.6), (1.15, 4.8), (1.75, 4.65), (0.9, 4.25), (1.5, 4.22), (2.1, 4.35)):
                m = pf & (ellipse2d(x, z, sgn * dx_, dz_, 0.085, 0.085) < 1.0)
                C[m] = col("navy")
        # défenses ivoire, couture arrière
        tk = np.isin(reg, ["tusk_l", "tusk_r"])
        C[tk] = col("balto_tusk")
        tseam = tk & (np.abs(np.abs(x) - 0.98) < 0.035) & (N[:, 1] < 0.0) & dashes(z, 0.2)
        C[tseam] = col("caramel")
        tip = tk & (z < 1.25)
        C[tip] *= 0.96
        # yeux brodés (sur la tête, face avant)
        front = N[:, 1] > 0.15
        for sgn in (-1, 1):
            e = ellipse2d(x, z, sgn * 1.6, 6.05, 0.38, 0.48)
            m = front & (e < 1.0) & (y > 6.0)
            satin(C, m, col("navy"), P, axis=(0.2, 0, 1), freq=40)
            hl = m & (ellipse2d(x, z, sgn * 1.6 - 0.12, 6.24, 0.12, 0.12) < 1.0)
            C[hl] = col("cream")
            # sourcils (arcs piqués)
            dd, ang = arc_dist(x, z, sgn * 1.6, 6.0, 0.8)
            m2 = front & (np.abs(dd) < 0.05) & (ang > 1.0) & (ang < 2.15) & (y > 5.8)
            C[m2] = col("navy")
            # joues roses
            bl = front & (ellipse2d(x, z, sgn * 2.75, 5.1, 0.55, 0.42) < 1.0) & ~pads & (reg == "head")
            paint(C, bl, col("blush"), 0.55)
        # couture centrale de tête
        hs = (reg == "head") & (np.abs(x) < 0.04) & (z > 7.55) & (N[:, 1] < 0.75) & dashes(y + z, 0.3)
        C[hs] = col("navy")
        # passepoil crème autour du plateau (hors tête) + coutures de soufflets et d'échine piquées
        Cp = piping(pl, P, N, C.copy(), col("cream_warm"))
        bodyreg = np.isin(reg, ["body", "belly"])
        C[bodyreg] = Cp[bodyreg]
        spine = topm & (np.abs(x) < 0.045) & dashes(y, 0.36) & (y < 4.9) & (y > -6.3)
        C[spine] = col("navy")
        for x0 in (-3.7, 3.7):
            gx = x0 + 0.35 * np.sin(y * 0.45)
            g = topm & (np.abs(x - gx) < 0.07) & (y < 5.0) & (y > -6.4)
            C[g] *= 0.8
            gs = topm & (np.abs(x - gx - 0.16) < 0.04) & dashes(y, 0.3) & (y < 5.0) & (y > -6.4)
            C[gs] = col("cream_warm")
        # appliqué poisson cousu sur le dos (arrière droit) : corps corail, queue crème, feston navy
        fa, fb = (x - 3.0), (y + 3.6)
        body_f = ellipse2d(fa, fb, 0.0, 0.0, 1.05, 0.62) < 1.0
        tail_f = (fa < -0.85) & (fa > -1.75) & (np.abs(fb) < (-0.85 - fa) * 0.75 + 0.05)
        fishm = topm & (body_f | tail_f)
        C[fishm] = col("coral")
        C[topm & tail_f] = col("cream_warm")
        for k in range(3):
            sc_ = topm & body_f & (np.abs(np.sqrt(ellipse2d(fa, fb, 0.55 - 0.42 * k, 0.0, 0.3, 0.42)) - 1.0) < 0.12) & (fa < 0.55 - 0.42 * k)
            C[sc_] = col("coral") * 0.82
        eye_f = topm & (ellipse2d(fa, fb, 0.55, 0.12, 0.1, 0.1) < 1.0)
        C[eye_f] = col("navy")
        rim = topm & (((np.abs(np.sqrt(ellipse2d(fa, fb, 0.0, 0.0, 1.05, 0.62)) - 1.0) < 0.07) & (fa > -0.85)) |
                      ((np.abs(np.abs(fb) - ((-0.85 - fa) * 0.75 + 0.05)) < 0.05) & (fa < -0.85) & (fa > -1.75)))
        C[rim & dashes(fa + fb * 2 + 9, 0.16, 0.6)] = col("navy")
        # couture du bas
        bottom_seam(P, N, C, z=0.45, color=col("navy"))
        # patch vichy corail cousu sur le flanc droit (+X)
        sidex = (N[:, 0] > 0.45) & (x > 5.0)
        a, b = y + 1.6, z - 3.0
        pm = sidex & (np.abs(a) < 1.55) & (np.abs(b) < 1.15)
        rr = rrect2d(a, b, 1.55, 1.15, 0.3)
        pm &= rr < 0
        gc = gingham(a + 5, b + 5, 0.42, col("coral"), col("coral") * 0.8 + col("cream") * 0.2, col("cream") * 0.85 + col("coral") * 0.15)
        C[pm] = gc[pm]
        st = sidex & (np.abs(rr + 0.16) < 0.045) & dashes(a + b * 1.3 + 9, 0.26)
        C[st] = col("navy")
        for (cx_, cz_) in ((-1.15, -0.78), (1.15, -0.78), (-1.15, 0.78), (1.15, 0.78)):
            xs = sidex & ((np.abs((a - cx_) - (b - cz_)) < 0.05) | (np.abs((a - cx_) + (b - cz_)) < 0.05)) \
                & (np.abs(a - cx_) < 0.17) & (np.abs(b - cz_) < 0.17)
            C[xs] = col("cream")
        C[(rr > 0) & (rr < 0.07) & sidex] *= 0.78  # ombre du bord du patch
        # pansement (patch croisé) sur la nageoire gauche
        t = math.radians(-40)
        lu = (x + 6.3) * math.cos(t) + (y - 5.4) * math.sin(t)
        lv = -(x + 6.3) * math.sin(t) + (y - 5.4) * math.cos(t)
        m = (reg == "flipper_l") & (N[:, 2] > 0.3) & (np.abs(lu + 0.55) < 0.28) & (np.abs(lv) < 0.75)
        C[m] = col("cream_warm")
        C[m & (np.abs(lv) < 0.2)] = col("blush")
        C[m & (np.abs(lv) > 0.32) & (np.mod((lu + 3) / 0.14, 1) < 0.35) & (np.mod((lv + 3) / 0.14, 1) < 0.35)] = col("caramel")
        # étiquette cousue
        tg = reg == "tag"
        C[tg] = col("cream")
        tag_paint(P, N, C, (-3.6, -7.22, 1.0), (0.42, 0.6), col("cream"), col("coral"), col("navy"), col("caramel"))
        return C

    pl.color_fn = color_fn
    pl.poses = standard_poses(pl, {
        "fall": {
            "Head": {"t": (0.0, 0.0, 0.25), "r": ((1, 0, 0), 6.0)},
            "Flipper_L": {"t": (0.0, 0.0, 0.25), "r": ((0, 1, 0), 12.0)},
            "Flipper_R": {"t": (0.0, 0.0, 0.25), "r": ((0, 1, 0), -12.0)},
            "Tail": {"t": (0.0, 0.0, 0.2), "r": ((1, 0, 0), -10.0)},
        },
        "impact": {
            "Head": {"t": (0.0, 0.3, -0.45), "r": ((1, 0, 0), -5.0)},
            "Flipper_L": {"t": (-0.45, 0.2, 0.05), "r": ((0, 1, 0), 8.0)},
            "Flipper_R": {"t": (0.45, 0.2, 0.05), "r": ((0, 1, 0), -8.0)},
            "Tail": {"t": (0.0, -0.35, 0.05), "r": ((1, 0, 0), -6.0)},
        },
        "rebound": {
            "Head": {"t": (0.0, 0.0, 0.12), "r": ((1, 0, 0), 3.0)},
            "Flipper_L": {"t": (0.0, 0.0, 0.1), "r": ((0, 1, 0), 5.0)},
            "Flipper_R": {"t": (0.0, 0.0, 0.1), "r": ((0, 1, 0), -5.0)},
            "Tail": {"t": (0.0, 0.0, 0.08), "r": ((1, 0, 0), -4.0)},
        },
    })
    pl.visual_brief = ("Grand morse couché à plat, velours bleu ciel grisé, plateau plus clair cerné d'un passepoil "
                       "crème : tête relevée à l'avant avec moustache touffue brodée, gros coussinets crème piqués de "
                       "points, défenses en tissu ivoire pointant vers le bas, yeux et sourcils brodés navy, joues "
                       "rosées. Nageoires avant aux coins avant, nageoire caudale en deux lobes à l'arrière, plis de "
                       "lard piqués sur les flancs, patch vichy corail cousu sur le flanc droit, pansement sur la "
                       "nageoire gauche, étiquette cousue à l'arrière. Dos plat praticable à 6 studs.")
    return pl


# ============================== RONRON (chat) ==============================
RONRON_TAIL = [(-4.2, -5.65, 1.15), (-6.4, -5.5, 0.85), (-7.3, -3.6, 0.68), (-7.42, -0.5, 0.62),
               (-7.25, 2.4, 0.6), (-6.3, 4.6, 0.58), (-4.6, 5.75, 0.55), (-3.3, 5.95, 0.5)]
RONRON_COLLAR = [(-3.0, 4.5, 4.7), (-2.4, 5.35, 3.55), (-1.3, 5.8, 3.0), (0.0, 5.95, 2.85),
                 (1.3, 5.8, 3.0), (2.4, 5.35, 3.55), (3.0, 4.5, 4.7)]
RONRON_TAIL_R = [0.85, 0.78, 0.72, 0.7, 0.68, 0.64, 0.58, 0.52]


def ronron():
    top = 6.0
    rect_center = (0.0, -0.9)  # 12 x 10 : x [-6, 6], y [-5.9, 4.1]
    body = sd_cushion(-7.1, 7.1, -6.45, 4.9, 6.12, ex=(1.33, 2.7, 1.5, 3.7), ey=(0.78, 2.2, 1.1, 4.0), rc=2.4)
    belly = sd_slab((0.0, -0.8), (6.5, 5.2), 0.0, 3.0, rc=3.0, re=1.4)
    haunch_l = sd_ellipsoid((-6.2, -3.3, 2.05), (1.75, 2.75, 2.0))
    haunch_r = sd_ellipsoid((6.2, -3.3, 2.05), (1.75, 2.75, 2.0))
    chest = sd_ellipsoid((0.0, 4.35, 2.45), (4.2, 1.55, 2.4))
    head = sd_ellipsoid((0.0, 4.95, 5.0), (3.95, 1.52, 2.15))
    cheek_l = sd_ellipsoid((-2.45, 5.1, 4.2), (1.7, 1.2, 1.15))
    cheek_r = sd_ellipsoid((2.45, 5.1, 4.2), (1.7, 1.2, 1.15))
    muzzle = sd_ellipsoid((0.0, 6.0, 4.25), (1.15, 0.5, 0.72))
    ear_shape = sd_round_cone((0, 0, 0), (0, 0, 1.25), 1.1, 0.2)
    ear_l = squash(ear_shape, (-2.45, 4.95, 6.5), (1.0, 0.42, 1.0), rot=(0, -16, 0))
    ear_r = squash(ear_shape, (2.45, 4.95, 6.5), (1.0, 0.42, 1.0), rot=(0, 16, 0))
    paw_l = sd_ellipsoid((-1.9, 5.6, 0.58), (1.08, 0.88, 0.58))
    paw_r = sd_ellipsoid((1.9, 5.6, 0.58), (1.08, 0.88, 0.58))
    tail = sd_tube(RONRON_TAIL, RONRON_TAIL_R)
    collar = sd_tube(RONRON_COLLAR, [0.3] * len(RONRON_COLLAR))
    bell = sd_ellipsoid((0.0, 6.0, 2.35), (0.47, 0.45, 0.47))
    tag = sd_round_box((4.4, -6.38, 1.0), (0.42, 0.05, 0.6), 0.04)

    parts = [
        Part("body", body, "body"),
        Part("belly", belly, "body", k=0.9),
        Part("haunch_l", haunch_l, "body", k=0.9),
        Part("haunch_r", haunch_r, "body", k=0.9),
        Part("chest", chest, "body", k=0.8),
        Part("head", head, "head", k=0.7),
        Part("cheek_l", cheek_l, "head", k=0.5),
        Part("cheek_r", cheek_r, "head", k=0.5),
        Part("muzzle", muzzle, "head", k=0.3),
        Part("ear_l", ear_l, "ear_l", k=0.3),
        Part("ear_r", ear_r, "ear_r", k=0.3),
        Part("paw_l", paw_l, "body", k=0.25),
        Part("paw_r", paw_r, "body", k=0.25),
        Part("tail", tail, "tail", k=0.3),
        Part("collar", collar, "body", k=0.08),
        Part("bell", bell, "head", k=0.1),
        Part("tag", tag, "body", k=0.03),
    ]
    pl = Plush(
        asset_id="toy_plush_ronron", label="Ronron", name_fr="Chat Ronron", size_tier="large",
        envelope=[16.0, 13.0, 8.0], collider_size=[12.0, 10.0, 6.0], walkable=[12.0, 10.0],
        rect_center=rect_center, top=top, parts=parts, floor_k=0.35,
        clip_k=lambda P: 0.1 + 0.3 * np.clip((P[:, 1] - 2.9) / 0.6, 0, 1) * np.clip((5.0 - np.abs(P[:, 0])) / 0.8, 0, 1),
        voxel=0.07, grid_lo=(-8.7, -7.2, -0.3), grid_hi=(8.7, 7.2, 8.5),
        lod0_target=4600, lod0_range=(3500, 5000), lod1_target=860, lod1_max=900,
        tex0=1024, tex1=256, skin_falloff=0.35, behavior="stable",
        secondary={
            "Head": (np.array([0.0, 4.4, 4.4]), "head"),
            "Ear_L": (np.array([-2.45, 4.95, 6.5]), "ear_l"),
            "Ear_R": (np.array([2.45, 4.95, 6.5]), "ear_r"),
            "Tail": (np.array([-4.6, -5.6, 1.1]), "tail"),
        },
    )

    def color_fn(P, N, D):
        n = len(P)
        names = list(D.keys())
        stack = np.stack([D[k] for k in names], axis=1)
        reg = np.array(names)[np.argmin(stack, axis=1)]
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        C = np.tile(col("cat_base"), (n, 1))
        # dos un peu plus clair au centre (lumière du velours)
        topm = (N[:, 2] > 0.75) & (z > top - 0.4)
        C[topm] = col("cat_light")
        furry = np.isin(reg, ["body", "belly", "haunch_l", "haunch_r"])
        # rayures tigrées : bandes transversales qui descendent sur les flancs
        wob = 0.3 * np.sin(x * 0.5 + 0.8) + 0.42 * np.abs(x) + 0.3 * (NOISE(P, 0.5) - 0.5)
        ph = (y + wob) / 2.15
        band = np.abs(np.mod(ph, 1.0) - 0.5) * 2.0  # 0 au centre de bande
        width = 0.2 + 0.06 * np.sin(x * 0.7 + y * 0.3)
        fade = np.clip((z - 1.2) / 1.8, 0, 1)
        broken = NOISE(P * np.array([1.0, 3.0, 1.0]), 0.9) > 0.3  # rayures interrompues
        stripe = furry & (band < width * fade) & (y < 3.5) & (y > -6.3) & broken
        C[stripe] = col("cat_stripe")
        # ligne d'échine foncée (tabby) au centre du dos
        # rayures des cuisses (arcs concentriques)
        for sgn in (-1, 1):
            hm = (reg == ("haunch_l" if sgn < 0 else "haunch_r")) | (furry & (np.abs(x) > 5.6) & (y < -0.8))
            r = np.hypot(y + 3.3, z - 2.05)
            ring = np.abs(np.mod(r / 1.05, 1.0) - 0.5) < 0.11
            C[hm & ring & (r > 1.5) & (r < 2.2) & (N[:, 0] * sgn > 0.4) & (sgn < 0)] = col("cat_stripe")
        # poitrail crème (bavoir ondulé)
        chest = (reg == "chest") | (furry & (N[:, 1] > 0.5) & (y > 3.4))
        bib = chest & (np.abs(x) < 3.0 + 0.25 * np.sin(z * 4.0)) & (z < 4.5)
        C[bib] = col("cat_cream")
        C[np.isin(reg, ["paw_l", "paw_r"])] = col("cat_cream")
        # orteils piqués
        for sgn in (-1, 1):
            pm = (reg == ("paw_l" if sgn < 0 else "paw_r")) & (N[:, 1] > 0.2)
            for dx_ in (-0.32, 0.32):
                m = pm & (np.abs(x - sgn * 1.9 - dx_) < 0.04) & (z > 0.35) & (z < 0.95)
                C[m] = col("cat_stripe")
        # tête
        hd = np.isin(reg, ["head", "cheek_l", "cheek_r"])
        C[hd] = col("cat_base")
        C[hd & (z < 4.05) & (np.abs(x) < 2.8)] = col("cat_cream")
        C[reg == "muzzle"] = col("cat_cream")
        front = N[:, 1] > 0.2
        # « M » du front et rayures des joues
        for xx, ln in ((-0.55, 0.85), (0.0, 1.05), (0.55, 0.85)):
            m = hd & front & (np.abs(x - xx - 0.12 * (z - 6.4) * np.sign(xx)) < 0.13) & (z > 7.05 - ln) & (z < 7.1)
            C[m] = col("cat_stripe")
        for sgn in (-1, 1):
            for zz in (4.55, 4.95):
                m = hd & (np.abs(z - zz - 0.18 * (np.abs(x) - 3.3)) < 0.1) & (np.abs(x) > 3.15) & (x * sgn > 0)
                C[m] = col("cat_stripe")
        # yeux fermés : arcs endormis brodés + cils
        for sgn in (-1, 1):
            ex = sgn * 1.35
            dd, ang = arc_dist(x, z, ex, 5.52, 0.55)
            m = front & hd & (np.abs(dd) < 0.075) & (ang < -0.35) & (ang > -2.8)
            satin(C, m, col("navy"), P, axis=(1, 0, 0.2), freq=50)
            for la in (-0.55, -2.6):
                lx = ex + 0.55 * math.cos(la)
                lz = 5.52 + 0.55 * math.sin(la)
                ox, oz = math.cos(la), math.sin(la)
                d1, s1 = seg2d(x, z, (lx, lz), (lx + 0.22 * ox + 0.1 * sgn * (1 if la > -1 else -1), lz + 0.22 * oz))
                C[front & hd & (d1 < 0.04)] = col("navy")
            bl = front & (ellipse2d(x, z, sgn * 2.5, 4.45, 0.55, 0.36) < 1.0) & hd
            paint(C, bl, col("blush"), 0.6)
            # moustaches (vibrisses) piquées
            for k, dz_ in enumerate((-0.15, 0.1, 0.35)):
                d1, s1 = seg2d(x, z, (sgn * 1.2, 4.15 + dz_ * 0.6), (sgn * 2.7, 4.0 + dz_))
                C[front & (d1 < 0.032) & dashes(s1, 0.18, 0.7) & (np.abs(x) > 1.05)] = col("navy")
        # nez rose triangulaire + bouche « w »
        nose = front & (z < 4.68) & (z > 4.32) & (np.abs(x) < (z - 4.32) * 0.95) & (y > 5.9)
        satin(C, nose, col("cat_pink") * 0.9, P, axis=(1, 0, 0), freq=60)
        for sgn in (-1, 1):
            dd, ang = arc_dist(x, z, sgn * 0.24, 4.25, 0.24)
            m = front & (np.abs(dd) < 0.04) & (ang < -0.2) & (ang > -2.9) & (y > 5.7)
            C[m] = col("navy")
        # oreilles : intérieur rose + touffe crème
        for rg, sgn in (("ear_l", -1), ("ear_r", 1)):
            em = reg == rg
            C[em] = col("cat_base")
            inner = em & (N[:, 1] > 0.35)
            lx = (x - sgn * 2.45) - 0.29 * (z - 6.5) * sgn
            m = inner & (np.abs(lx) < 0.72 * (1.0 - (z - 6.5) / 1.4)) & (z > 6.65)
            C[m] = col("cat_pink")
            fl = m & (np.mod((lx * 3 + z * 2) / 0.35, 1.0) < 0.25) & (z < 7.0)
            C[fl] = col("cat_cream")
            tipm = em & (z > 7.6)
            C[tipm] = col("cat_stripe")
        # queue annelée, bout crème
        tm = reg == "tail"
        arc, L = tube_param(P, RONRON_TAIL)
        rings = np.abs(np.mod(arc / 1.25, 1.0) - 0.5) < 0.2
        C[tm & rings] = col("cat_stripe")
        C[tm & (arc > L - 1.0)] = col("cat_cream")
        # collier corail piqué + grelot en tissu
        cm = reg == "collar"
        C[cm] = col("coral")
        ce = cm & (np.abs(np.abs(N[:, 2]) - 0.55) < 0.12) & dashes(x + 10, 0.2)
        C[ce] = col("cream")
        bm = reg == "bell"
        C[bm] = col("bell_gold")
        sl = bm & (np.abs(x) < 0.05) & (z < 2.28)
        C[sl] = col("navy")
        sl2 = bm & (np.abs(z - 2.33) < 0.045)
        C[sl2] = col("caramel")
        C[bm & (ellipse2d(x, z, 0.0, 1.98, 0.09, 0.09) < 1.0)] = col("navy")
        # passepoil crème (hors tête) + couture d'échine
        Cp = piping(pl, P, N, C.copy(), col("cat_cream"))
        bodyreg = np.isin(reg, ["body", "belly", "haunch_l", "haunch_r"])
        C[bodyreg] = Cp[bodyreg]
        spine = topm & (np.abs(x) < 0.045) & dashes(y, 0.36) & (y < 3.8) & (y > -5.6)
        C[spine] = col("cat_stripe") * 0.8
        bottom_seam(P, N, C, z=0.42, color=col("cat_stripe") * 0.8)
        # patch lune lilas cousu sur la cuisse droite (+X)
        sm = (N[:, 0] > 0.45) & (x > 5.2)
        a, b = y + 3.2, z - 2.35
        moon = sm & (ellipse2d(a, b, 0, 0, 1.05, 1.05) < 1.0) & (ellipse2d(a, b, 0.48, 0.32, 0.85, 0.85) > 1.0)
        C[moon] = col("lilac")
        dd = np.sqrt(a * a + b * b) - 1.05
        st = sm & (np.abs(dd + 0.1) < 0.04) & dashes(np.arctan2(b, a) * 1.05, 0.2) & \
            (ellipse2d(a, b, 0.48, 0.32, 0.85, 0.85) > 1.15)
        C[st] = col("navy")
        for (sa, sb) in ((0.9, 0.95), (1.35, 0.3), (0.55, 1.45)):
            xs = sm & (((np.abs(a - sa) < 0.035) & (np.abs(b - sb) < 0.16)) | ((np.abs(b - sb) < 0.035) & (np.abs(a - sa) < 0.16)))
            C[xs] = col("cream")
        # « z z » brodés (sommeil) sur le flanc gauche, près de la tête
        lm = (N[:, 0] < -0.45) & (x < -5.2)
        for (za, zb, s) in ((2.2, 3.6, 0.5), (2.95, 4.35, 0.36)):
            pts = [(za - s, zb + s), (za + s, zb + s), (za - s, zb - s), (za + s, zb - s)]
            d1, s1 = polyline2d(y, z, pts)
            C[lm & (d1 < 0.06)] = col("cream")
        # étiquette cousue
        C[reg == "tag"] = col("cream")
        tag_paint(P, N, C, (4.4, -6.38, 1.0), (0.42, 0.6), col("cream"), col("lilac"), col("navy"), col("caramel"))
        return C

    pl.color_fn = color_fn
    pl.poses = standard_poses(pl, {
        "fall": {
            "Head": {"t": (0.0, 0.0, 0.25), "r": ((1, 0, 0), 6.0)},
            "Ear_L": {"t": (0.0, 0.0, 0.1), "r": ((0, 1, 0), 14.0)},
            "Ear_R": {"t": (0.0, 0.0, 0.1), "r": ((0, 1, 0), -14.0)},
            "Tail": {"t": (0.0, 0.0, 0.3), "r": ((0, 0, 1), -6.0)},
        },
        "impact": {
            "Head": {"t": (0.0, 0.25, -0.9), "r": ((1, 0, 0), -8.0)},
            "Ear_L": {"t": (0.0, 0.0, -0.75), "r": ((0, 1, 0), -16.0)},
            "Ear_R": {"t": (0.0, 0.0, -0.75), "r": ((0, 1, 0), 16.0)},
            "Tail": {"t": (-0.3, 0.0, -0.1), "r": ((0, 0, 1), 4.0)},
        },
        "rebound": {
            "Head": {"t": (0.0, 0.0, 0.12), "r": ((1, 0, 0), 3.0)},
            "Ear_L": {"t": (0.0, 0.0, 0.05), "r": ((0, 1, 0), 6.0)},
            "Ear_R": {"t": (0.0, 0.0, 0.05), "r": ((0, 1, 0), -6.0)},
            "Tail": {"t": (0.0, 0.0, 0.1), "r": ((0, 0, 1), -3.0)},
        },
    })
    pl.visual_brief = ("Grand chat tigré caramel endormi en position « pain », dos plat praticable à 6 studs cerné "
                       "d'un passepoil crème : rayures par texture, tête à l'avant avec yeux fermés brodés en arcs, "
                       "nez rose, bouche en w et vibrisses piquées, joues rosées, oreilles dressées à intérieur rose, "
                       "poitrail et pattes crème aux orteils piqués, collier corail en tissu avec grelot doré cousu, "
                       "longue queue annelée enroulée le long du flanc gauche, patch lune lilas sur la cuisse droite, "
                       "« z z » brodés, étiquette cousue à l'arrière.")
    return pl


# ============================== BOBINE (baleine) ===========================
BOBINE_TAIL = [(0.0, -7.2, 4.3), (0.0, -8.5, 5.9), (0.0, -9.05, 7.8), (0.0, -9.15, 8.8)]
BOBINE_TAIL_R = [2.3, 1.55, 1.0, 0.75]


def bobine():
    top = 8.0
    rect_center = (0.0, 1.1)  # 18 x 16 : x [-9, 9], y [-6.9, 9.1]
    body = sd_cushion(-10.4, 10.4, -7.85, 9.95, 8.12, ex=(1.6, 3.4, 2.6, 5.0), ey=(1.15, 3.0, 2.0, 5.4), rc=3.0)
    belly = sd_slab((0.0, 0.8), (9.6, 8.6), 0.0, 4.5, rc=6.0, re=2.6)
    head = sd_ellipsoid((0.0, 7.2, 4.4), (8.8, 2.35, 3.8))
    fin_l = sd_ellipsoid((-10.05, 2.6, 2.9), (2.3, 1.45, 0.46), rot=(0, 6, 28))
    fin_r = sd_ellipsoid((10.05, 2.6, 2.9), (2.3, 1.45, 0.46), rot=(0, -6, -28))
    tail = sd_tube(BOBINE_TAIL, BOBINE_TAIL_R)
    fluke_l = sd_ellipsoid((-2.55, -9.2, 9.45), (2.85, 0.5, 1.1), rot=(0, 24, 0))
    fluke_r = sd_ellipsoid((2.55, -9.2, 9.45), (2.85, 0.5, 1.1), rot=(0, -24, 0))
    sp_c = sd_tube([(0.0, 9.3, 7.3), (0.0, 9.4, 8.6), (0.0, 9.45, 9.5)], [0.5, 0.42, 0.5])
    sp_l = sd_tube([(-0.2, 9.3, 7.6), (-0.85, 9.35, 8.5), (-1.25, 9.4, 9.0)], [0.38, 0.33, 0.42])
    sp_r = sd_tube([(0.2, 9.3, 7.6), (0.85, 9.35, 8.5), (1.25, 9.4, 9.0)], [0.38, 0.33, 0.42])

    def spout(P):
        return smin(smin(sp_c(P), sp_l(P), 0.2), sp_r(P), 0.2)

    tag = sd_round_box((6.2, -8.62, 1.25), (0.5, 0.05, 0.72), 0.04)

    def quilt_g(P):
        u = (P[:, 0] + P[:, 1]) / math.sqrt(2.0)
        v = (P[:, 0] - P[:, 1]) / math.sqrt(2.0)
        per = 3.4
        du = np.abs(np.mod(u / per + 0.5, 1.0) - 0.5) * per
        dv = np.abs(np.mod(v / per + 0.5, 1.0) - 0.5) * per
        dmin = np.minimum(du, dv)
        return np.exp(-(dmin / 0.32) ** 2)

    def displace(P):
        # matelassage : le corps culmine à 8,12 et le dessus est écrêté à 8,0 ; une rainure abaisse la surface de
        # 0,20 -> fond de rainure à 7,92, soit 0,08 stud sous les panneaux (<= 0,2 ; avec l'enfoncement client
        # de 0,15 sous le joueur, l'écart reste <= 0,25)
        w = np.clip((P[:, 2] - 7.0) / 0.8, 0, 1)
        return 0.20 * quilt_g(P) * w

    parts = [
        Part("body", body, "body"),
        Part("belly", belly, "body", k=1.4),
        Part("head", head, "head", k=1.2),
        Part("fin_l", fin_l, "fin_l", k=0.6),
        Part("fin_r", fin_r, "fin_r", k=0.6),
        Part("tail", tail, "tail", k=0.9),
        Part("fluke_l", fluke_l, "tail", k=0.5),
        Part("fluke_r", fluke_r, "tail", k=0.5),
        Part("spout", spout, "spout", k=0.25),
        Part("tag", tag, "body", k=0.03),
    ]
    pl = Plush(
        asset_id="toy_plush_bobine", label="Bobine", name_fr="Baleine Bobine", size_tier="giant",
        envelope=[24.0, 20.0, 11.0], collider_size=[18.0, 16.0, 8.0], walkable=[18.0, 16.0],
        rect_center=rect_center, top=top, parts=parts, floor_k=0.45, clip_k=0.1, displace=displace,
        voxel=0.10, grid_lo=(-12.8, -10.8, -0.4), grid_hi=(12.8, 10.8, 11.6),
        lod0_target=6500, lod0_range=(5000, 7000), lod1_target=1140, lod1_max=1200,
        tex0=2048, tex1=256, skin_falloff=0.5, behavior="stable",
        secondary={
            "Head": (np.array([0.0, 7.0, 4.4]), "head"),
            "Fin_L": (np.array([-9.0, 2.4, 2.6]), "fin_l"),
            "Fin_R": (np.array([9.0, 2.4, 2.6]), "fin_r"),
            "Tail": (np.array([0.0, -7.6, 4.8]), "tail"),
            "Spout": (np.array([0.0, 9.3, 7.4]), "spout"),
        },
    )
    pl.quilt_g = quilt_g

    def boundary_z(P):
        ang = np.arctan2(P[:, 1] - 0.6, P[:, 0])
        return 3.9 + 0.32 * np.sin(ang * 7.0)

    def color_fn(P, N, D):
        n = len(P)
        names = list(D.keys())
        stack = np.stack([D[k] for k in names], axis=1)
        reg = np.array(names)[np.argmin(stack, axis=1)]
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        C = np.tile(col("whale_navy"), (n, 1))
        bodyish = np.isin(reg, ["body", "belly", "head"])
        # ventre crème visible sur les côtés (frontière ondulée) et sur la face avant
        bz = boundary_z(P)
        frontface = (N[:, 1] > 0.35) & (y > 7.0)
        bz = np.where(frontface, 3.45 + 0.12 * np.cos(x * 0.9), bz)
        cream = bodyish & (z < bz)
        C[cream] = col("whale_cream")
        # liseré piqué à la frontière
        bl = bodyish & (np.abs(z - bz - 0.12) < 0.045) & dashes(np.arctan2(y, x) * 10 + x * frontface, 0.32)
        C[bl] = col("whale_cream")
        # sillons de gorge (rorqual) : lignes piquées verticales sur la face avant crème
        gr = cream & (N[:, 1] > 0.25) & (np.abs(np.mod(x / 0.75, 1.0) - 0.5) * 0.75 < 0.035) & (z < bz - 0.35) & (z > 0.7) & (np.abs(x) < 6.5)
        C[gr] = col("whale_groove")
        # dessus matelassé : rainures plus foncées, piqûres crème, panneaux bombés plus clairs
        topm = (z > top - 0.75) & (N[:, 2] > 0.5) & bodyish
        g = pl.quilt_g(P)
        puff = 1.0 + 0.10 * (1.0 - g)
        C[topm] *= puff[topm][:, None]
        groove = topm & (g > 0.72)
        C[groove] = col("whale_navy_dark")
        u = (x + y) / math.sqrt(2.0)
        v = (x - y) / math.sqrt(2.0)
        qs = topm & (g > 0.93) & (dashes(u + v + 20, 0.4))
        C[qs] = col("whale_cream")
        # petites étoiles brodées au centre de quelques panneaux
        per = 3.4
        cu = (np.floor(u / per) + 0.5) * per
        cv = (np.floor(v / per) + 0.5) * per
        du, dv = u - cu, v - cv
        sel = (np.mod(np.floor(u / per) + 2 * np.floor(v / per), 3) == 0)
        star = topm & sel & (((np.abs(du) < 0.05) & (np.abs(dv) < 0.28)) | ((np.abs(dv) < 0.05) & (np.abs(du) < 0.28)) |
                             ((np.abs(du - dv) < 0.06) & (np.abs(du) < 0.17)) | ((np.abs(du + dv) < 0.06) & (np.abs(du) < 0.17)))
        C[star] = col("sky")
        # passepoil crème autour du plateau
        Cp = piping(pl, P, N, C.copy(), col("whale_cream"), margin=0.35, width=0.14)
        C[bodyish] = Cp[bodyish]
        # yeux brodés : blanc crème, pupille navy, reflet
        front = (N[:, 1] > 0.2) & (y > 6.0)
        for sgn in (-1, 1):
            ex, ez = sgn * 4.25, 5.0
            ew = front & (ellipse2d(x, z, ex, ez, 0.78, 0.92) < 1.0)
            satin(C, ew, col("white"), P, axis=(0, 0, 1), freq=36, depth=0.08)
            pup = ew & (ellipse2d(x, z, ex + sgn * 0.08, ez - 0.12, 0.5, 0.6) < 1.0)
            satin(C, pup, col("navy"), P, axis=(1, 0, 0.3), freq=44)
            hl = pup & (ellipse2d(x, z, ex - 0.12, ez + 0.18, 0.16, 0.16) < 1.0)
            C[hl] = col("white")
            ring = front & (np.abs(np.sqrt(ellipse2d(x, z, ex, ez, 0.78, 0.92)) - 1.0) < 0.07)
            C[ring] = col("navy")
            # cils
            for la in (0.55, 0.95, 1.35):
                lx = ex + sgn * 0.78 * math.cos(la)
                lz = ez + 0.92 * math.sin(la)
                d1, s1 = seg2d(x, z, (lx, lz), (lx + sgn * 0.26 * math.cos(la), lz + 0.26 * math.sin(la)))
                C[front & (d1 < 0.05)] = col("cream")
            # joues corail
            bl2 = front & (ellipse2d(x, z, sgn * 5.2, 3.0, 0.8, 0.5) < 1.0)
            paint(C, bl2, col("coral"), 0.45)
        # sourire brodé
        dd, ang = arc_dist(x, z, 0.0, 6.2, 3.85)
        smile = front & (np.abs(dd) < 0.085) & (np.abs(x) < 2.7) & (z < 3.4)
        satin(C, smile, col("navy"), P, axis=(1, 0, 0), freq=40)
        for sgn in (-1, 1):
            d1, s1 = seg2d(x, z, (sgn * 2.62, 3.4), (sgn * 2.95, 3.68))
            C[front & (d1 < 0.07)] = col("navy")
        # nageoires : navy, bord crème, couture de base, pansement sur la gauche
        for rg, sgn in (("fin_l", -1), ("fin_r", 1)):
            fm = reg == rg
            C[fm] = col("whale_fin")
            edge = fm & (np.abs(x) > 10.9)
            C[edge] = col("whale_cream")
            under = fm & (N[:, 2] < -0.2)
            C[under] = col("whale_cream")
            r = np.hypot(x - sgn * 10.05, y - 2.6)
            st = fm & (np.abs(r - 1.55) < 0.04) & (N[:, 2] > 0.1) & dashes(np.arctan2(y - 2.6, x) * 1.55, 0.25)
            C[st] = col("whale_cream")
        bm = (reg == "fin_l") & (N[:, 2] > 0.2)
        a = (x + 10.2) * 0.88 + (y - 2.4) * 0.47
        b = -(x + 10.2) * 0.47 + (y - 2.4) * 0.88
        band = bm & (np.abs(a) < 0.95) & (np.abs(b) < 0.36)
        C[band] = col("cream_warm")
        C[band & (np.abs(a) < 0.3)] = col("blush")
        dots = band & (np.abs(a) > 0.4) & (np.mod(a / 0.18, 1.0) < 0.3) & (np.mod(b / 0.18, 1.0) < 0.3)
        C[dots] = col("caramel")
        # queue : navy, dessous de la nageoire caudale crème, couture centrale
        tm = np.isin(reg, ["tail", "fluke_l", "fluke_r"])
        C[tm] = col("whale_navy")
        flu = np.isin(reg, ["fluke_l", "fluke_r"])
        C[flu & (N[:, 1] < -0.3)] = col("whale_cream")
        fe = flu & (z > 9.45 + 0.42 * np.abs(x) - 0.2) & (N[:, 1] > -0.3)
        C[fe] = col("whale_navy_dark")
        ts = tm & (np.abs(x) < 0.045) & (N[:, 1] > 0.0) & dashes(z, 0.32)
        C[ts] = col("whale_cream")
        notch = flu & (np.abs(x) < 0.05) & dashes(z, 0.2)
        C[notch] = col("whale_cream")
        # jet d'eau en tissu : bleu ciel, reflets blancs piqués
        spm = reg == "spout"
        C[spm] = col("whale_spout")
        hl = spm & (NOISE(P, 3.0) > 0.62)
        C[hl] = col("whale_spout_light")
        sst = spm & (np.abs(np.mod(z / 0.45, 1.0) - 0.5) < 0.06) & (N[:, 1] > 0)
        C[sst] = col("white")
        # poche cousue bleu ciel sur le flanc droit (+X) avec cœur corail
        sm = (N[:, 0] > 0.45) & (x > 8.5)
        a, b = y + 0.8, z - 5.4
        rr = rrect2d(a, b, 1.9, 1.45, 0.35)
        pk = sm & (rr < 0) & (b < 1.45)
        C[pk] = col("sky")
        C[pk & (b > 1.05)] = col("sky") * 0.85  # ourlet
        st = sm & (np.abs(rr + 0.17) < 0.045) & dashes(a + b * 1.3 + 9, 0.26) & (b < 1.2)
        C[st] = col("white")
        hem = sm & (np.abs(b - 1.0) < 0.04) & (np.abs(a) < 1.75) & dashes(a + 9, 0.26)
        C[hem] = col("white")
        ha, hb = a * 1.0, b + 0.2
        heart = sm & ((ellipse2d(ha, hb, -0.25, 0.12, 0.3, 0.27) < 1) | (ellipse2d(ha, hb, 0.25, 0.12, 0.3, 0.27) < 1) |
                      ((hb < 0.12) & (hb > -0.62 + np.abs(ha) * 1.1)))
        satin(C, heart, col("coral"), P, axis=(0, 1, 1), freq=40)
        C[(rr > 0) & (rr < 0.08) & sm & (b < 1.45)] *= 0.75
        bottom_seam(P, N, C, z=0.5, color=col("whale_groove"))
        C[reg == "tag"] = col("cream")
        tag_paint(P, N, C, (6.2, -8.62, 1.25), (0.5, 0.72), col("cream"), col("coral"), col("navy"), col("caramel"))
        return C

    pl.color_fn = color_fn
    pl.poses = standard_poses(pl, {
        "fall": {
            "Head": {"t": (0.0, 0.0, 0.3), "r": ((1, 0, 0), 4.0)},
            "Fin_L": {"t": (0.0, 0.0, 0.3), "r": ((0, 1, 0), 14.0)},
            "Fin_R": {"t": (0.0, 0.0, 0.3), "r": ((0, 1, 0), -14.0)},
            "Tail": {"t": (0.0, 0.0, 0.2), "r": ((1, 0, 0), -6.0)},
            "Spout": {"t": (0.0, 0.0, 0.2), "r": ((1, 0, 0), -8.0)},
        },
        "impact": {
            "Head": {"t": (0.0, 0.3, -1.1), "r": ((1, 0, 0), -5.0)},
            "Fin_L": {"t": (-0.5, 0.0, -0.3), "r": ((0, 1, 0), -8.0)},
            "Fin_R": {"t": (0.5, 0.0, -0.3), "r": ((0, 1, 0), 8.0)},
            "Tail": {"t": (0.0, -0.2, -1.6), "r": ((1, 0, 0), -10.0)},
            "Spout": {"t": (0.0, 0.3, -2.0), "r": ((1, 0, 0), 12.0)},
        },
        "rebound": {
            "Head": {"t": (0.0, 0.0, 0.15), "r": ((1, 0, 0), 2.0)},
            "Fin_L": {"t": (0.0, 0.0, 0.12), "r": ((0, 1, 0), 6.0)},
            "Fin_R": {"t": (0.0, 0.0, 0.12), "r": ((0, 1, 0), -6.0)},
            "Tail": {"t": (0.0, 0.0, 0.15), "r": ((1, 0, 0), -4.0)},
            "Spout": {"t": (0.0, 0.0, 0.15), "r": ((1, 0, 0), -5.0)},
        },
    })
    pl.visual_brief = ("Baleine géante navy et crème (pièces XL) : corps dodu au dos plat matelassé en losanges "
                       "(rainures douces <= 0,12 stud, piqûres crème, petites étoiles brodées) cerné d'un passepoil, "
                       "ventre crème visible sur les flancs avec liseré ondulé et sillons de gorge piqués, grands yeux "
                       "brodés blanc et navy à cils, sourire brodé, joues corail, nageoires latérales à bord crème "
                       "(pansement sur la gauche), grande nageoire caudale relevée à l'arrière hors zone utile, "
                       "jet d'eau en tissu bleu ciel au bord avant, poche cousue bleu ciel à cœur corail sur le flanc "
                       "droit, étiquette cousue à l'arrière.")
    return pl


PLUSHES = {"balto": balto, "ronron": ronron, "bobine": bobine}
MODEL_DIRS = {"balto": "Balto", "ronron": "Ronron", "bobine": "Bobine"}

RUNTIME_LIMITS = {
    "fall_stretch_y_max": 1.12,
    "impact_scale_y_min": 0.72,
    "impact_scale_xz_max": 1.18,
    "plush_lattice_bones": 9,
    "secondary_bones_max": 6,
    "walkable_top_alignment_tolerance_studs": 0.25,
}
