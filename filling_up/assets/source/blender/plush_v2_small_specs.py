"""Spécifications procédurales du lot « plush_v2_small » (Pipou, Mochi, Bulle, Grumf, Nuage).

Module pur (numpy uniquement), utilisé par build_plush_v2_small.py, verify_plush_v2_small.py et
render_plush_v2_small.py. Il ne dépend PAS de plush_specs.py (édité en parallèle par un autre lot).

Conventions (décisions 0003 / 0004 / 0008) :
- 1 unité Blender = 1 stud. Blender : X = largeur, Y = profondeur, Z = hauteur.
- Pivot bottom_center : origine au centre de l'enveloppe visuelle, au sol (z = 0).
- Avant Roblox (-Z, LookVector) = +Y Blender : tous les visages regardent +Y.
- Gauche du personnage = -X (il regarde +Y, sa droite est +X) : *_L côté -X, *_R côté +X.
- Modélisation par champs de distance signée (SDF) : primitives (ellipsoïdes, cônes arrondis,
  dalles arrondies, tores...) unies par union lisse, puis « couvercle » plat : rien ne dépasse le
  dessus du collider au-dessus du rectangle utile (décision 0008), et dessous plat au sol.
- Peinture procédurale (tissu velours, coutures, broderies) évaluée en 3D sur la surface ; graines fixes.
"""
from __future__ import annotations

import math
import numpy as np

SEED = 20261102

# ---------------------------------------------------------------------------
# Palette (sRGB). Famille : crèmes, pastels, corail #FF684B, menthe #39E68B, lilas, caramel,
# broderie marine #203055.
# ---------------------------------------------------------------------------
HEX = {
    "navy": "#203055",
    "navy_face": "#2D3C6B",
    "cream": "#FFF4DE",
    "cream_white": "#FFFBF1",
    "coral": "#FF684B",
    "coral_dark": "#D9482F",
    "coral_soft": "#FF8C70",
    "blush": "#FF9C8A",
    "mint": "#39E68B",
    "mint_pastel": "#A3EDC8",
    "mint_mid": "#6FDDA6",
    "mint_dark": "#2FB872",
    "lilac": "#C3A7EE",
    "lilac_dark": "#9C7FD6",
    "lilac_light": "#DCCBF7",
    "caramel": "#D9965A",
    "caramel_dark": "#A9692F",
    "caramel_light": "#E9B884",
    "yellow": "#FFD45C",
    "yellow_light": "#FFF0B0",
    "yellow_deep": "#F6B93B",
    "thread_orange": "#E3912C",
    "pink": "#F7AFC0",
    "pink_dark": "#E58AA0",
}


def srgb_to_linear(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, dtype=float), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def lin(name_or_hex):
    h = HEX.get(name_or_hex, name_or_hex).lstrip("#")
    return srgb_to_linear([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


# ---------------------------------------------------------------------------
# Primitives SDF (P : (n, 3) -> distances (n,))
# ---------------------------------------------------------------------------
def rotm(euler_deg):
    rx, ry, rz = [math.radians(a) for a in euler_deg]
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ my @ mx


def _norm(a):
    return np.sqrt(np.einsum("ij,ij->i", a, a))


def ellipsoid(c, r, rot=(0, 0, 0)):
    c = np.asarray(c, float)
    r = np.asarray(r, float)
    R = rotm(rot)

    def f(P):
        q = (P - c) @ R
        k0 = _norm(q / r)
        k1 = _norm(q / (r * r))
        return np.where(k1 > 1e-9, k0 * (k0 - 1.0) / np.maximum(k1, 1e-9), -r.min())
    return f


def superellipsoid(c, r, eh=2.0, ev=2.0, rot=(0, 0, 0)):
    c = np.asarray(c, float)
    r = np.asarray(r, float)
    R = rotm(rot)

    def f(P):
        q = (P - c) @ R
        a = np.abs(q / r) + 1e-12
        v = ((a[:, 0] ** eh + a[:, 1] ** eh) ** (ev / eh) + a[:, 2] ** ev) ** (1.0 / ev)
        L = _norm(q)
        return np.where(v > 1e-3, (v - 1.0) * L / np.maximum(v, 1e-3), -r.min())
    return f


def round_box(c, half, rad, rot=(0, 0, 0)):
    c = np.asarray(c, float)
    half = np.asarray(half, float)
    R = rotm(rot)

    def f(P):
        q = np.abs((P - c) @ R) - (half - rad)
        return _norm(np.maximum(q, 0.0)) + np.minimum(q.max(axis=1), 0.0) - rad
    return f


def slab(cxy, half_xy, z0, z1, rc, re):
    """Dalle : rectangle arrondi en plan (rayon rc) extrudé de z0 à z1, arêtes arrondies (re)."""
    cx, cy = cxy
    hx, hy = half_xy
    zc, hz = 0.5 * (z0 + z1), 0.5 * (z1 - z0)

    def f(P):
        qx = np.abs(P[:, 0] - cx) - (hx - rc)
        qy = np.abs(P[:, 1] - cy) - (hy - rc)
        d2 = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - rc
        wx = d2 + re
        wz = np.abs(P[:, 2] - zc) - (hz - re)
        return np.sqrt(np.maximum(wx, 0) ** 2 + np.maximum(wz, 0) ** 2) + np.minimum(np.maximum(wx, wz), 0) - re
    return f


def round_cone(a, b, ra, rb):
    """Cône arrondi (iq) entre a (rayon ra) et b (rayon rb)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    l2 = float(ba @ ba)
    rr = ra - rb
    a2 = l2 - rr * rr
    il2 = 1.0 / l2

    def f(P):
        pa = P - a
        y = pa @ ba
        z = y - l2
        xv = pa * l2 - np.outer(y, ba)
        x2 = np.einsum("ij,ij->i", xv, xv)
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        d_end = np.sqrt(x2 + z2) * il2 - rb
        d_start = np.sqrt(x2 + y2) * il2 - ra
        d_mid = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - ra
        return np.where(np.sign(z) * a2 * z2 > k, d_end, np.where(np.sign(y) * a2 * y2 < k, d_start, d_mid))
    return f


def torus(c, R_major, r_minor, rot=(0, 0, 0)):
    """Tore d'axe local Y."""
    c = np.asarray(c, float)
    M = rotm(rot)

    def f(P):
        q = (P - c) @ M
        qx = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - R_major
        return np.sqrt(qx * qx + q[:, 1] ** 2) - r_minor
    return f


def chain(points, radii):
    """Suite de cônes arrondis (queue, plumes...)."""
    fs = [round_cone(points[i], points[i + 1], radii[i], radii[i + 1]) for i in range(len(points) - 1)]

    def f(P):
        d = fs[0](P)
        for g in fs[1:]:
            d = np.minimum(d, g(P))
        return d
    return f


def union(*fns):
    def f(P):
        d = fns[0](P)
        for g in fns[1:]:
            d = np.minimum(d, g(P))
        return d
    return f


def xform(fn, c=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    """Place une forme définie autour de l'origine : échelle (aplatissement) puis rotation puis translation.
    Distance approchée (borne inférieure) multipliée par la plus petite échelle."""
    c = np.asarray(c, float)
    R = rotm(rot)
    s = np.asarray(scale, float)
    smin_ = float(s.min())

    def f(P):
        q = ((P - c) @ R) / s
        return fn(q) * smin_
    return f


def mirror_x(fn):
    """Symétrique de la forme par rapport au plan x = 0."""
    M = np.array([-1.0, 1.0, 1.0])

    def f(P):
        return fn(P * M)
    return f


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def rect_sd(P, rect):
    """Distance signée 2D au rectangle (xmin, xmax, ymin, ymax) : > 0 à l'extérieur."""
    x0, x1, y0, y1 = rect
    dx = np.maximum(x0 - P[:, 0], P[:, 0] - x1)
    dy = np.maximum(y0 - P[:, 1], P[:, 1] - y1)
    return np.sqrt(np.maximum(dx, 0) ** 2 + np.maximum(dy, 0) ** 2) + np.minimum(np.maximum(dx, dy), 0)


# ---------------------------------------------------------------------------
# Bruit de valeur 3D déterministe (texture velours / feutre)
# ---------------------------------------------------------------------------
_RNG_TABLE = np.random.default_rng(SEED).random(4096)


def value_noise(P, freq, salt=0):
    q = P * freq + salt * 17.13
    i = np.floor(q).astype(np.int64)
    f = q - i
    f = f * f * (3 - 2 * f)

    def h(ix, iy, iz):
        return _RNG_TABLE[(ix * 73856093 ^ iy * 19349663 ^ iz * 83492791 ^ salt * 2654435761) % 4096]

    out = 0.0
    for dx in (0, 1):
        wx = f[:, 0] if dx else 1 - f[:, 0]
        for dy in (0, 1):
            wy = f[:, 1] if dy else 1 - f[:, 1]
            for dz in (0, 1):
                wz = f[:, 2] if dz else 1 - f[:, 2]
                out = out + wx * wy * wz * h(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz)
    return out  # [0, 1]


# ---------------------------------------------------------------------------
# Contexte de peinture (masques adoucis = broderies sans crénelage)
# ---------------------------------------------------------------------------
class Ctx:
    def __init__(self, P, N, D, w):
        self.P = P
        self.N = N
        self.D = D
        self.w = max(float(w), 1e-3)
        self.n = len(P)
        self.C = np.zeros((self.n, 3))

    def soft(self, d, w=None):
        w = self.w * 1.4 if w is None else w
        return np.clip(0.5 - d / w, 0.0, 1.0)

    def fill(self, col):
        self.C[:] = lin(col) if isinstance(col, str) else col

    def paint(self, alpha, col):
        rgb = lin(col) if isinstance(col, str) else np.asarray(col)
        a = np.clip(alpha, 0, 1)[:, None]
        self.C = self.C * (1 - a) + rgb * a

    def shade(self, alpha, factor):
        a = np.clip(alpha, 0, 1)[:, None]
        self.C = self.C * (1 - a + a * factor)

    def on(self, *names, tol=0.04):
        d = np.min(np.stack([self.D[n] for n in names]), axis=0)
        return self.soft(d - tol)

    def facing(self, n0, lo=0.1, hi=0.35):
        n0 = np.asarray(n0, float) / np.linalg.norm(n0)
        c = self.N @ n0
        return np.clip((c - lo) / (hi - lo), 0, 1)

    def plane_uv(self, c, n0, up=(0, 0, 1)):
        """Coordonnées 2D (s, t) dans le plan de normale n0 passant par c (s vers la droite du regard)."""
        n0 = np.asarray(n0, float) / np.linalg.norm(n0)
        up = np.asarray(up, float)
        u = np.cross(up, n0)
        if np.linalg.norm(u) < 1e-6:
            u = np.array([1.0, 0, 0])
        u /= np.linalg.norm(u)
        v = np.cross(n0, u)
        q = self.P - np.asarray(c, float)
        return q @ u, q @ v, q @ n0

    def ellipse(self, c, n0, a, b, rot_deg=0.0, depth=0.6, up=(0, 0, 1)):
        """Masque d'ellipse projetée suivant n0 sur les faces orientées vers n0."""
        s, t, h = self.plane_uv(c, n0, up)
        if rot_deg:
            ca, sa = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
            s, t = ca * s + sa * t, -sa * s + ca * t
        d = (np.sqrt((s / a) ** 2 + (t / b) ** 2) - 1.0) * min(a, b)
        return self.soft(d) * self.facing(n0, 0.05, 0.3) * (np.abs(h) < depth)

    def segment_mask(self, c, n0, pts2d, width, depth=0.6, up=(0, 0, 1)):
        """Trait brodé (polyligne 2D dans le plan de normale n0) : distance au trait < width."""
        s, t, h = self.plane_uv(c, n0, up)
        p2 = np.stack([s, t], axis=1)
        best = np.full(self.n, 1e9)
        for a, b in zip(pts2d[:-1], pts2d[1:]):
            a = np.asarray(a, float)
            b = np.asarray(b, float)
            ab = b - a
            tt = np.clip(((p2 - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
            best = np.minimum(best, np.linalg.norm(p2 - (a + tt[:, None] * ab), axis=1))
        return self.soft(best - width) * self.facing(n0, 0.0, 0.25) * (np.abs(h) < depth)

    def dash(self, param, period=0.2, duty=0.58):
        ph = np.mod(param / period, 1.0)
        dd = (np.abs(ph - 0.5) - duty * 0.5) * period
        return self.soft(dd)

    def stitch_line(self, d_line, param, col, width=0.032, period=0.19, duty=0.6, groove=0.86):
        """Couture : sillon légèrement sombre + point avant (pointillés) de fil contrasté."""
        ad = np.abs(d_line)
        self.shade(self.soft(ad - width * 2.6, self.w * 3.0), groove)
        a = self.soft(ad - width) * self.dash(param, period, duty)
        self.paint(a, col)
        # reflet du fil
        self.shade(self.soft(ad - width * 0.35) * self.dash(param, period, duty * 0.55), 1.12)

    def satin(self, mask, col, direction_param, period=0.045, amp=0.10):
        """Broderie au point lancé : couleur modulée par des stries régulières."""
        rgb = lin(col) if isinstance(col, str) else np.asarray(col)
        mod = 1.0 + amp * np.sin(2 * np.pi * direction_param / period)
        a = np.clip(mask, 0, 1)[:, None]
        self.C = self.C * (1 - a) + (rgb[None, :] * mod[:, None]) * a


def roundrect_param(P, cx, cy, hx, hy):
    """Paramètre d'abscisse approximatif le long d'un rectangle arrondi (pour les pointillés)."""
    x = P[:, 0] - cx
    y = P[:, 1] - cy
    return np.where(np.abs(x) / hx > np.abs(y) / hy, y, x)


# ---------------------------------------------------------------------------
# Rotations (poses)
# ---------------------------------------------------------------------------
def rodrigues(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * (K @ K)


def axis_angle(R):
    ang = math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2)))
    if ang < 1e-9:
        return (0.0, 0.0, 1.0), 0.0
    ax = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * math.sin(ang))
    ax = ax / np.linalg.norm(ax)
    return tuple(float(round(v, 5)) for v in ax), round(math.degrees(ang), 3)


def follow(parent_head, parent_pose, child_head, extra_r=None, extra_t=(0, 0, 0)):
    """Pose d'un bone enfant direct de Root qui suit rigidement un autre bone (tête -> oreilles)."""
    hp = np.asarray(parent_head, float)
    hc = np.asarray(child_head, float)
    Rp = rodrigues(*parent_pose["r"]) if parent_pose.get("r") else np.eye(3)
    Re = rodrigues(*extra_r) if extra_r else np.eye(3)
    tp = np.asarray(parent_pose.get("t") or (0, 0, 0), float)
    R = Rp @ Re
    t = Rp @ (hc - hp) + hp + tp - hc + np.asarray(extra_t, float)
    ax, ang = axis_angle(R)
    out = {"t": tuple(float(round(v, 4)) for v in t), "r": None}
    if ang > 1e-6:
        out["r"] = (ax, ang)
    return out


# ---------------------------------------------------------------------------
# Peluche
# ---------------------------------------------------------------------------
class Plush:
    CAP_MARGIN = 0.07   # les reliefs au-dessus du dessus restent à > 0,07 stud du rectangle utile
    CAP_SMOOTH = 0.16   # arrondi de l'arête du panneau de dessus (passepoil)
    FLOOR_SMOOTH = 0.05

    def __init__(self, **kw):
        self.__dict__.update(kw)
        w, d, _h = self.collider_size
        cx, cy = self.collider_center
        self.rect = (cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2)
        self.top = float(self.collider_size[2])

    # --- géométrie -----------------------------------------------------------
    def part_names(self):
        return [p[0] for p in self.parts]

    def eval_parts(self, P):
        return {name: fn(P) for name, _owner, fn in self.parts}

    def finalize(self, f, P):
        g = np.minimum(P[:, 2] - self.top, self.CAP_MARGIN - rect_sd(P, self.rect))
        f = smax(f, g, self.CAP_SMOOTH)
        return smax(f, -P[:, 2], self.FLOOR_SMOOTH)

    def sdf(self, P, D=None):
        D = self.eval_parts(P) if D is None else D
        return self.finalize(self.compose(D, P), P)

    def owners(self):
        out = []
        for _n, o, _f in self.parts:
            if o not in out:
                out.append(o)
        return out

    # --- rig -----------------------------------------------------------------
    def belly_bone_names(self):
        return [f"Belly_{i}{j}" for j in range(3) for i in range(3)]

    def belly_bone_heads(self):
        cx, cy = self.collider_center
        s = self.belly_spacing
        z = self.top - 1.0
        return {f"Belly_{i}{j}": np.array([cx + (i - 1) * s[0], cy + (j - 1) * s[1], z])
                for j in range(3) for i in range(3)}

    def bone_names(self):
        return ["Root"] + self.belly_bone_names() + list(self.secondary.keys())

    def skin_weights(self, P, D, max_influences=4):
        """Root (bas, statique) + grille 3x3 du ventre (barycentrique) ; secondaires par appartenance."""
        n = len(P)
        groups = {}
        for name, owner, _fn in self.parts:
            s = np.exp(-np.clip(D[name], 0, None) * 11.0)
            groups[owner] = np.maximum(groups.get(owner, 0), s)
        total = sum(groups.values()) + 1e-12
        names = self.bone_names()
        W = {k: np.zeros(n) for k in names}
        body = groups.get("body", np.zeros(n)) / total
        t = np.clip(P[:, 2] / self.top, 0.0, 1.0)
        W["Root"] += body * (1.0 - t)
        cx, cy = self.collider_center
        u = np.clip((P[:, 0] - cx) / self.belly_spacing[0] + 1.0, 0.0, 2.0)
        v = np.clip((P[:, 1] - cy) / self.belly_spacing[1] + 1.0, 0.0, 2.0)
        i0 = np.minimum(np.floor(u).astype(int), 1)
        j0 = np.minimum(np.floor(v).astype(int), 1)
        fu = u - i0
        fv = v - j0
        lower = (fu + fv) <= 1.0
        bw = body * t
        corners = [
            (np.where(lower, i0, i0 + 1), np.where(lower, j0, j0 + 1), np.where(lower, 1 - fu - fv, fu + fv - 1)),
            (np.where(lower, i0 + 1, i0), np.where(lower, j0, j0 + 1), np.where(lower, fu, 1 - fu)),
            (np.where(lower, i0, i0 + 1), np.where(lower, j0 + 1, j0), np.where(lower, fv, 1 - fv)),
        ]
        for ii, jj, ww in corners:
            for a in range(3):
                for b in range(3):
                    sel = (ii == a) & (jj == b)
                    W[f"Belly_{a}{b}"] += np.where(sel, bw * ww, 0.0)
        floor = np.clip(1.0 - P[:, 2] / 0.6, 0.0, 1.0)
        for bname, (_head, owner) in self.secondary.items():
            g = groups.get(owner, np.zeros(n)) / total
            W[bname] += g * (1.0 - floor)
            W["Root"] += g * floor
        M = np.stack([W[k] for k in names], axis=1)
        M[M < 1e-5] = 0.0
        order = np.argsort(-M, axis=1, kind="stable")
        keep = np.zeros_like(M, dtype=bool)
        keep[np.arange(n)[:, None], order[:, :max_influences]] = True
        M = np.where(keep, M, 0.0)
        s = M.sum(axis=1, keepdims=True)
        orphan = s[:, 0] <= 1e-9
        M[orphan, 0] = 1.0
        M = M / M.sum(axis=1, keepdims=True)
        return names, M

    def belly_pose(self, dz, radial):
        out = {}
        cx, cy = self.collider_center
        for name, h in self.belly_bone_heads().items():
            ox = np.sign(round(h[0] - cx, 3))
            oy = np.sign(round(h[1] - cy, 3))
            out[name] = {"t": (float(ox * radial[0]), float(oy * radial[1]), float(dz)), "r": None}
        return out

    def landing(self):
        p = self.belly_pose(-0.06 if self.tier == "mini" else -0.08, (0.0, 0.0))
        p["Belly_11"] = {"t": (0.0, 0.0, -0.15), "r": None}
        return p


def merge(*ds):
    out = {}
    for d in ds:
        out.update(d)
    return out


def U(*items):
    """Union lisse en chaîne : U(d0, (d1, k1), (d2, k2), ...)."""
    f = items[0]
    for d, k in items[1:]:
        f = smin(f, d, k)
    return f


def Umin(D, names, k):
    f = D[names[0]]
    for nme in names[1:]:
        f = smin(f, D[nme], k)
    return f


# ============================== PIPOU =======================================
# aile en goutte (repère local : x épaisseur, y de l'avant vers l'arrière, z haut) avec deux plumes de bout
WING = union(round_cone((0, 0.42, 0.06), (0, -0.50, -0.10), 0.52, 0.16),
             round_cone((0, -0.05, 0.22), (0, -0.70, 0.30), 0.24, 0.10),
             round_cone((0, -0.10, -0.18), (0, -0.66, -0.28), 0.22, 0.09))


def pipou():
    T = 3.0
    parts = [
        ("body", "body", slab((0.0, -0.36), (2.07, 2.11), 0.75, 3.3, 0.6, 0.45)),
        ("belly", "body", superellipsoid((0.0, -0.20, 1.42), (2.24, 2.20, 1.42), eh=3.0, ev=2.6)),
        ("cheek_l", "body", ellipsoid((-1.15, 1.25, 1.62), (0.78, 0.68, 0.72))),
        ("cheek_r", "body", ellipsoid((1.15, 1.25, 1.62), (0.78, 0.68, 0.72))),
        ("beak_up", "body", ellipsoid((0.0, 2.14, 1.86), (0.40, 0.36, 0.20), rot=(-12, 0, 0))),
        ("beak_lo", "body", ellipsoid((0.0, 2.04, 1.64), (0.27, 0.26, 0.13), rot=(8, 0, 0))),
        ("foot_l", "body", ellipsoid((-0.66, 1.30, 0.15), (0.42, 0.55, 0.17))),
        ("foot_r", "body", ellipsoid((0.66, 1.30, 0.15), (0.42, 0.55, 0.17))),
        ("toes_l", "body", chain([(-1.0, 1.72, 0.13), (-0.66, 1.98, 0.13), (-0.32, 1.72, 0.13)], [0.13, 0.14, 0.13])),
        ("toes_r", "body", chain([(0.32, 1.72, 0.13), (0.66, 1.98, 0.13), (1.0, 1.72, 0.13)], [0.13, 0.14, 0.13])),
        ("wing_l", "wing_l", xform(WING, c=(-2.27, -0.30, 1.72), rot=(-24, 0, -16), scale=(0.36, 1.0, 1.0))),
        ("wing_r", "wing_r", xform(WING, c=(2.27, -0.30, 1.72), rot=(-24, 0, 16), scale=(0.36, 1.0, 1.0))),
        ("tuft_c", "tuft", chain([(0.0, 1.78, 2.55), (0.0, 1.98, 3.25), (0.03, 2.22, 3.80), (0.0, 2.36, 3.94)],
                                 [0.21, 0.17, 0.10, 0.07])),
        ("tuft_l", "tuft", chain([(-0.22, 1.80, 2.55), (-0.42, 1.98, 3.10), (-0.68, 2.20, 3.52)], [0.17, 0.13, 0.07])),
        ("tuft_r", "tuft", chain([(0.22, 1.80, 2.55), (0.42, 1.98, 3.10), (0.68, 2.20, 3.52)], [0.17, 0.13, 0.07])),
        ("tail", "body", chain([(0.0, -2.05, 1.5), (0.0, -2.30, 1.78)], [0.24, 0.12])),
    ]

    def compose(D, P):
        f = smin(D["body"], D["belly"], 0.45)
        f = smin(f, smin(D["cheek_l"], D["cheek_r"], 0.0), 0.35)
        f = smin(f, smin(D["beak_up"], D["beak_lo"], 0.04), 0.06)
        for n in ("foot_l", "foot_r", "toes_l", "toes_r"):
            f = smin(f, D[n], 0.06)
        f = smin(f, D["wing_l"], 0.05)
        f = smin(f, D["wing_r"], 0.05)
        f = smin(f, Umin(D, ["tuft_c", "tuft_l", "tuft_r"], 0.06), 0.12)
        f = smin(f, D["tail"], 0.1)
        return f

    def paint(cx):
        P, N = cx.P, cx.N
        cx.fill("yellow")
        # ventre clair cousu (point de feston)
        bel = cx.ellipse((0, 2.0, 1.02), (0, 1, 0), 1.05, 0.78, depth=1.2)
        cx.paint(bel, "yellow_light")
        s, t, _h = cx.plane_uv((0, 2.0, 1.02), (0, 1, 0))
        rho = np.sqrt((s / 1.05) ** 2 + (t / 0.78) ** 2)
        ring_d = (rho - 1.0) * 0.78
        cx.stitch_line(ring_d * cx.facing((0, 1, 0), 0.05, 0.3) + (1 - cx.facing((0, 1, 0), 0.05, 0.3)) * 9,
                       np.arctan2(t, s) * 0.9, "thread_orange", period=0.16)
        # joues rosées (feutrine appliquée)
        for sx in (-1, 1):
            cx.paint(cx.ellipse((sx * 1.18, 2.0, 1.72), (sx * 0.35, 1, 0), 0.27, 0.2) * 0.85, "blush")
        # yeux brodés (point lancé vertical) + reflet
        for sx in (-1, 1):
            e = cx.ellipse((sx * 0.70, 2.0, 2.22), (sx * 0.2, 1, 0), 0.17, 0.24)
            cx.satin(e, "navy", P[:, 0] * 1.0 + P[:, 2] * 0.15, period=0.04)
            cx.paint(cx.ellipse((sx * 0.70 - 0.05, 2.0, 2.31), (sx * 0.2, 1, 0), 0.055, 0.065), "cream_white")
        # sourcils (petits traits)
        for sx in (-1, 1):
            cx.paint(cx.segment_mask((sx * 0.70, 2.0, 2.58), (sx * 0.2, 1, 0),
                                     [(-0.13 * sx, -0.02), (0.0, 0.03), (0.13 * sx, -0.02)], 0.022), "thread_orange")
        # bec et pattes corail, couture médiane du bec
        cx.paint(cx.on("beak_up", "beak_lo", tol=0.03), "coral")
        mid = np.abs(P[:, 2] - 1.74 - 0.15 * (P[:, 1] - 2.0)) - 0.0
        cx.shade(cx.soft(mid - 0.018) * cx.on("beak_up", "beak_lo", tol=0.02), 0.62)
        cx.paint(cx.on("foot_l", "foot_r", "toes_l", "toes_r", tol=0.03), "coral")
        feet = cx.on("foot_l", "foot_r", "toes_l", "toes_r", tol=0.03)
        for sx in (-1, 1):
            for k in (-1, 1):
                cx.paint(cx.segment_mask((sx * 0.62, 1.95, 0.3), (0, 0, 1), [(k * 0.08, 0.0), (k * 0.2, 0.36)], 0.018,
                                         depth=0.25, up=(0, 1, 0)) * feet, "coral_dark")
        # ailes : jaune soutenu, plumes brodées
        for wn, sx in (("wing_l", -1), ("wing_r", 1)):
            wm = cx.on(wn, tol=0.025)
            cx.paint(wm, "yellow_deep")
            q = (P - np.array([sx * 2.27, -0.30, 1.72])) @ rotm((-24, 0, 16 * sx))
            for zc in (-0.08, 0.16):
                arc = np.abs(q[:, 2] - zc - 0.35 * (q[:, 1] + 0.1) ** 2)
                cx.paint(cx.soft(arc - 0.02) * wm * (q[:, 1] < 0.25) * (q[:, 1] > -0.75) *
                         cx.facing((sx, 0, 0), 0.2, 0.4), "thread_orange")
        # houppette : 3 plumes, nervure brodée
        tm = cx.on("tuft_c", "tuft_l", "tuft_r", tol=0.025)
        cx.paint(tm, "yellow_deep")
        cx.paint(tm * cx.soft(np.abs(P[:, 0] - 0.0) - 0.015) * (P[:, 2] > 2.9), "thread_orange")
        cx.paint(cx.on("tail", tol=0.03), "yellow_deep")
        # panneau de dessus cousu
        topm = (P[:, 2] > T - 0.05).astype(float) * cx.facing((0, 0, 1), 0.7, 0.9)
        cx_, cy_ = 0.0, -0.4
        dd = np.maximum(np.abs(P[:, 0] - cx_) - 1.62, np.abs(P[:, 1] - cy_) - 1.62)
        cx.stitch_line(np.where(topm > 0.5, dd, 9.0), roundrect_param(P, cx_, cy_, 1.62, 1.62), "thread_orange")
        # couture verticale dos
        back = cx.facing((0, -1, 0), 0.3, 0.6) * (P[:, 2] < T - 0.2) * (P[:, 2] > 0.25)
        cx.stitch_line(np.where(back > 0.5, P[:, 0], 9.0), P[:, 2], "thread_orange")
        # étiquette tissée au dos (bas)
        tag = cx.ellipse((0.95, -2.4, 0.55), (0, -1, 0), 0.26, 0.16, depth=0.5)
        cx.paint(tag, "cream_white")
        cx.paint(tag * cx.soft(np.abs(P[:, 2] - 0.55) - 0.025), "coral")

    secondary = {
        "Wing_L": (np.array([-2.0, -0.3, 1.6]), "wing_l"),
        "Wing_R": (np.array([2.0, -0.3, 1.6]), "wing_r"),
        "Tuft": (np.array([0.0, 1.8, 2.6]), "tuft"),
    }
    pl = Plush(
        key="pipou", asset_id="toy_plush_pipou", label="Pipou", name_fr="Poussin Pipou", tier="mini",
        envelope=[5, 5, 4], collider_size=[4, 4, 3], collider_center=(0.0, -0.4),
        parts=parts, compose=compose, paint=paint, secondary=secondary, belly_spacing=(1.5, 1.5),
        behavior="stable", behavior_params=None, symmetric=True,
        face_probe={"xz": (0.70, 2.17), "expect": "navy", "what": "œil droit brodé (côté +X)"},
        visual_brief=("Poussin rond jaune en velours ras, petit bec et pattes corail, deux ailerons cousus, houppette "
                      "de trois plumes plantée sur la face avant (hors rectangle utile). Yeux brodés marine, joues "
                      "en feutrine rosée, ventre clair au point de feston, panneau de dessus plat cousu à hauteur 3. "
                      "Mini peluche de remplissage : trop petite pour un appui obligatoire."),
    )
    pl.poses = {
        "rest": {},
        "fall": merge(pl.belly_pose(0.34, (-0.10, -0.10)), {
            "Wing_L": {"t": (0.0, 0.0, 0.22), "r": ((0, 1, 0), 16.0)},
            "Wing_R": {"t": (0.0, 0.0, 0.22), "r": ((0, 1, 0), -16.0)},
            "Tuft": {"t": (0.0, -0.05, 0.28), "r": ((1, 0, 0), 8.0)},
        }),
        "impact": merge(pl.belly_pose(-0.82, (0.24, 0.15)), {
            "Wing_L": {"t": (-0.08, 0.0, -0.45), "r": ((0, 1, 0), -12.0)},
            "Wing_R": {"t": (0.08, 0.0, -0.45), "r": ((0, 1, 0), 12.0)},
            "Tuft": {"t": (0.0, 0.05, -0.70), "r": ((1, 0, 0), -14.0)},
        }),
        "rebound": merge(pl.belly_pose(0.15, (-0.05, -0.05)), {
            "Wing_L": {"t": (0.0, 0.0, 0.10), "r": ((0, 1, 0), 7.0)},
            "Wing_R": {"t": (0.0, 0.0, 0.10), "r": ((0, 1, 0), -7.0)},
            "Tuft": {"t": (0.0, 0.0, 0.14), "r": ((1, 0, 0), 5.0)},
        }),
    }
    pl.poses["player_landing"] = pl.landing()
    return pl


# ============================== MOCHI =======================================
def mochi():
    T = 3.0
    parts = [
        ("body", "body", slab((0.0, -0.40), (2.66, 2.03), 0.0, 3.3, 0.7, 0.5)),
        ("belly", "body", ellipsoid((0.0, -0.26, 1.32), (2.72, 2.06, 1.36))),
        ("face", "body", ellipsoid((0.0, 1.05, 1.62), (1.85, 1.2, 1.3))),
        ("snout", "body", ellipsoid((0.0, 2.06, 1.62), (0.66, 0.42, 0.46))),
        ("cheek_l", "body", ellipsoid((-2.30, 0.95, 1.22), (0.70, 0.86, 0.80))),
        ("cheek_r", "body", ellipsoid((2.30, 0.95, 1.22), (0.70, 0.86, 0.80))),
        ("ear_l", "ear_l", ellipsoid((-1.52, 1.95, 3.40), (0.57, 0.19, 0.60), rot=(-8, -16, 0))),
        ("ear_r", "ear_r", ellipsoid((1.52, 1.95, 3.40), (0.57, 0.19, 0.60), rot=(-8, 16, 0))),
        ("ear_cup_l", "ear_l", ellipsoid((-1.52, 2.13, 3.44), (0.38, 0.12, 0.40), rot=(-8, -16, 0))),
        ("ear_cup_r", "ear_r", ellipsoid((1.52, 2.13, 3.44), (0.38, 0.12, 0.40), rot=(-8, 16, 0))),
        ("paw_l", "paw_l", ellipsoid((-0.62, 2.12, 0.62), (0.34, 0.30, 0.28), rot=(0, 0, 10))),
        ("paw_r", "paw_r", ellipsoid((0.62, 2.12, 0.62), (0.34, 0.30, 0.28), rot=(0, 0, -10))),
        ("foot_l", "body", ellipsoid((-1.55, -2.14, 0.16), (0.48, 0.30, 0.18))),
        ("foot_r", "body", ellipsoid((1.55, -2.14, 0.16), (0.48, 0.30, 0.18))),
        ("tail", "body", ellipsoid((0.0, -2.33, 0.95), (0.2, 0.16, 0.18))),
    ]

    def compose(D, P):
        f = smin(D["body"], D["belly"], 0.45)
        f = smin(f, D["face"], 0.5)
        f = smin(f, D["snout"], 0.2)
        f = smin(f, D["cheek_l"], 0.42)
        f = smin(f, D["cheek_r"], 0.42)
        for s in ("l", "r"):
            ear = smax(D[f"ear_{s}"], -D[f"ear_cup_{s}"], 0.05)
            f = smin(f, ear, 0.1)
            f = smin(f, D[f"paw_{s}"], 0.08)
            f = smin(f, D[f"foot_{s}"], 0.06)
        f = smin(f, D["tail"], 0.06)
        return f

    def paint(cx):
        P, N = cx.P, cx.N
        cx.fill("caramel")
        # masque crème (ventre, museau, bas des joues) avec liseré ondulé cousu
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        front = np.clip((y - 0.2) / 1.8, 0, 1)
        bound = 0.75 + 0.95 * front + 0.12 * np.sin(x * 3.4) - 0.55 * np.clip(np.abs(x) - 1.3, 0, 2) * front
        # liste blanche sur le front (du museau vers le dessus)
        blaze = (np.abs(x) < 0.26 + 0.1 * (2.6 - z)) & (y > 1.2) & (z < 2.85)
        dcream = np.where(blaze, -1.0, z - bound)
        cream = cx.soft(dcream, cx.w * 2.0)
        cx.paint(cream, "cream")
        cx.paint(cx.on("snout", tol=0.03), "cream")
        edge = np.where(blaze, 9.0, z - bound)
        cx.stitch_line(np.where(z < 2.9, edge, 9.0), x + y * 0.3, "caramel_dark", period=0.17)
        # joues : rond plus clair
        for sx in (-1, 1):
            cx.paint(cx.ellipse((sx * 2.45, 1.3, 1.25), (sx * 0.8, 0.6, 0), 0.32, 0.26) * 0.8, "pink")
        # oreilles : intérieur rose
        for s, sx in (("l", -1), ("r", 1)):
            em = cx.on(f"ear_{s}", tol=0.03)
            cup = cx.soft(cx.D[f"ear_cup_{s}"] - 0.03) * em
            cx.paint(cup * cx.facing((0, 1, 0), -0.1, 0.2), "pink")
        # yeux brodés + reflet
        for sx in (-1, 1):
            e = cx.ellipse((sx * 0.80, 2.0, 2.18), (sx * 0.3, 1, 0), 0.19, 0.21)
            cx.satin(e, "navy", P[:, 0] + P[:, 2] * 0.2, period=0.04)
            cx.paint(cx.ellipse((sx * 0.80 - 0.06, 2.0, 2.27), (sx * 0.3, 1, 0), 0.06, 0.065), "cream_white")
        # nez rose et bouche « ω » brodée
        nose = cx.ellipse((0.0, 2.45, 1.86), (0, 1, 0.5), 0.14, 0.09)
        cx.paint(nose, "pink_dark")
        mouth = cx.segment_mask((0.0, 2.4, 1.58), (0, 1, 0.1),
                                [(-0.30, 0.06), (-0.22, -0.04), (-0.11, -0.07), (0.0, 0.03), (0.11, -0.07),
                                 (0.22, -0.04), (0.30, 0.06)], 0.02)
        mouth = np.maximum(mouth, cx.segment_mask((0.0, 2.4, 1.58), (0, 1, 0.1), [(0.0, 0.03), (0.0, 0.22)], 0.02))
        cx.paint(mouth, "navy")
        # moustaches brodées
        for sx in (-1, 1):
            n0 = (sx * 0.55, 1, 0)
            for dz, dzz in ((0.12, 0.22), (0.0, 0.0), (-0.12, -0.22)):
                cx.paint(cx.segment_mask((sx * 0.95, 2.1, 1.62), n0, [(0.0, dz), (0.62, dz + dzz)], 0.016, depth=0.4)
                         * cx.facing(n0, 0.45, 0.65) * (y > 1.0), "navy")
        # pattes roses + doigts brodés
        pm = cx.on("paw_l", "paw_r", "foot_l", "foot_r", tol=0.03)
        cx.paint(pm, "pink")
        for sx in (-1, 1):
            for k in (-1, 0, 1):
                cx.paint(cx.segment_mask((sx * 0.62 + k * 0.12, 2.4, 0.62), (0, 1, 0), [(0, 0.04), (0, 0.16)],
                                         0.016, depth=0.4) * pm, "pink_dark")
        cx.paint(cx.on("tail", tol=0.03), "caramel_light")
        # rayures du front (3 traits caramel foncé sur le dessus avant)
        topm = (z > T - 0.05).astype(float) * cx.facing((0, 0, 1), 0.7, 0.9)
        for k in (-1, 0, 1):
            cx.paint(topm * cx.soft(np.abs(x - k * 0.45) - 0.07) * (y > 0.4) * (y < 1.3), "caramel_dark")
        # panneau de dessus cousu
        dd = np.maximum(np.abs(x) - 2.12, np.abs(y + 0.4) - 1.62)
        cx.stitch_line(np.where(topm > 0.5, dd, 9.0), roundrect_param(P, 0.0, -0.4, 2.12, 1.62), "caramel_dark")
        back = cx.facing((0, -1, 0), 0.3, 0.6) * (z < T - 0.2) * (z > 0.3)
        cx.stitch_line(np.where(back > 0.5, x, 9.0), z, "caramel_dark")
        tag = cx.ellipse((1.3, -2.45, 0.6), (0, -1, 0), 0.26, 0.16, depth=0.5)
        cx.paint(tag, "cream_white")
        cx.paint(tag * cx.soft(np.abs(z - 0.6) - 0.025), "coral")

    secondary = {
        "Ear_L": (np.array([-1.45, 1.8, 2.95]), "ear_l"),
        "Ear_R": (np.array([1.45, 1.8, 2.95]), "ear_r"),
        "Paw_L": (np.array([-0.6, 1.95, 0.65]), "paw_l"),
        "Paw_R": (np.array([0.6, 1.95, 0.65]), "paw_r"),
    }
    pl = Plush(
        key="mochi", asset_id="toy_plush_mochi", label="Mochi", name_fr="Hamster Mochi", tier="mini",
        envelope=[6, 5, 4], collider_size=[5, 4, 3], collider_center=(0.0, -0.4),
        parts=parts, compose=compose, paint=paint, secondary=secondary, belly_spacing=(1.9, 1.5),
        behavior="stable", behavior_params=None, symmetric=True,
        face_probe={"xz": (0.80, 2.16), "expect": "navy", "what": "œil droit brodé (côté +X)"},
        visual_brief=("Hamster caramel et crème en petit pain dodu : grosses abajoues sur les côtés, oreilles rondes "
                      "à intérieur rose plantées sur l'avant (hors rectangle utile), pattes roses à l'avant, liste "
                      "crème sur le museau, moustaches et bouche brodées marine. Dessus plat cousu à hauteur 3. "
                      "Mini peluche de remplissage."),
    )
    pl.poses = {
        "rest": {},
        "fall": merge(pl.belly_pose(0.34, (-0.10, -0.10)), {
            "Ear_L": {"t": (0.0, 0.0, 0.30), "r": ((0, 1, 0), 10.0)},
            "Ear_R": {"t": (0.0, 0.0, 0.30), "r": ((0, 1, 0), -10.0)},
            "Paw_L": {"t": (0.0, 0.0, 0.12), "r": ((1, 0, 0), -10.0)},
            "Paw_R": {"t": (0.0, 0.0, 0.12), "r": ((1, 0, 0), -10.0)},
        }),
        "impact": merge(pl.belly_pose(-0.82, (0.30, 0.27)), {
            "Ear_L": {"t": (-0.18, 0.05, -0.80), "r": ((0, 1, 0), -14.0)},
            "Ear_R": {"t": (0.18, 0.05, -0.80), "r": ((0, 1, 0), 14.0)},
            "Paw_L": {"t": (-0.15, 0.12, -0.14), "r": ((1, 0, 0), 10.0)},
            "Paw_R": {"t": (0.15, 0.12, -0.14), "r": ((1, 0, 0), 10.0)},
        }),
        "rebound": merge(pl.belly_pose(0.15, (-0.05, -0.05)), {
            "Ear_L": {"t": (0.0, 0.0, 0.14), "r": ((0, 1, 0), 5.0)},
            "Ear_R": {"t": (0.0, 0.0, 0.14), "r": ((0, 1, 0), -5.0)},
        }),
    }
    pl.poses["player_landing"] = pl.landing()
    return pl


# ============================== BULLE =======================================
# nageoire en éventail (repère local : x vers l'extérieur, y, z épaisseur) : trois rayons palmés
FIN = union(round_cone((0, 0, 0), (0.62, 0.42, 0), 0.18, 0.13), round_cone((0, 0, 0), (0.70, -0.02, 0), 0.18, 0.14),
            round_cone((0, 0, 0), (0.55, -0.45, 0), 0.18, 0.12), ellipsoid((0.38, -0.01, 0), (0.36, 0.42, 0.12)))
# queue en éventail (plan local XZ, épaisseur y) : cinq rayons qui montent depuis la racine
TAIL_FAN = union(*[round_cone((0, 0, 0), (L * math.sin(math.radians(a)), 0, L * math.cos(math.radians(a))), 0.20, 0.15)
                   for a, L in ((-58, 1.30), (-29, 1.64), (0, 1.83), (29, 1.64), (58, 1.30))],
                 ellipsoid((0, 0, 0.95), (1.05, 0.14, 0.88)))


def bulle():
    T = 3.0
    parts = [
        ("body", "body", slab((0.0, 0.30), (2.50, 1.62), 0.0, 3.3, 0.8, 0.5)),
        ("belly", "body", superellipsoid((0.0, 0.31, 1.36), (2.52, 1.60, 1.38), eh=3.0, ev=2.4)),
        ("lips", "body", torus((0.0, 1.88, 1.22), 0.26, 0.135, rot=(0, 0, 0))),
        ("eye_l", "body", ellipsoid((-1.18, 1.76, 2.10), (0.42, 0.20, 0.42))),
        ("eye_r", "body", ellipsoid((1.18, 1.76, 2.10), (0.42, 0.20, 0.42))),
        ("fin_l", "fin_l", mirror_x(xform(FIN, c=(2.30, 0.25, 1.45), rot=(0, -34, -25), scale=(0.9, 1.0, 0.42)))),
        ("fin_r", "fin_r", xform(FIN, c=(2.30, 0.25, 1.45), rot=(0, -34, -25), scale=(0.9, 1.0, 0.42))),
        ("tail_root", "tail", ellipsoid((0.0, -1.38, 1.95), (0.50, 0.32, 0.50))),
        ("tail_fan", "tail", xform(TAIL_FAN, c=(0.0, -1.66, 2.02), rot=(6, 0, 0), scale=(1.0, 0.55, 1.0))),
    ]
    spikes = []
    for sx in (-1, 1):
        for (yy, zz) in ((-0.55, 0.95), (0.55, 0.85), (1.30, 1.25), (0.0, 1.85), (-0.75, 2.45), (0.75, 2.45)):
            base = np.array([sx * 2.30, yy, zz])
            tip = base + np.array([sx * 0.50, 0.08 * yy, 0.06 * (zz - 1.6)])
            spikes.append((f"spike_{'l' if sx < 0 else 'r'}_{len(spikes)}", "body", round_cone(base, tip, 0.21, 0.09)))
    for sx in (-1, 1):  # deux piquants sur les coins avant bas
        base = np.array([sx * 1.75, 1.45, 0.62])
        tip = base + np.array([sx * 0.30, 0.38, -0.04])
        spikes.append((f"spike_f{'l' if sx < 0 else 'r'}", "body", round_cone(base, tip, 0.19, 0.08)))
    parts += spikes
    spike_names = [p[0] for p in spikes]

    def compose(D, P):
        f = smin(D["body"], D["belly"], 0.4)
        f = smin(f, D["lips"], 0.06)
        f = smin(f, D["eye_l"], 0.08)
        f = smin(f, D["eye_r"], 0.08)
        f = smin(f, Umin(D, spike_names, 0.0), 0.10)
        f = smin(f, D["fin_l"], 0.16)
        f = smin(f, D["fin_r"], 0.16)
        tail = smin(D["tail_root"], D["tail_fan"], 0.15)
        return smin(f, tail, 0.12)

    def paint(cx):
        P, N = cx.P, cx.N
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        cx.fill("mint_pastel")
        # ventre crème (bas), liseré cousu
        bnd = 0.95 + 0.35 * np.clip((y - 0.5) / 1.2, 0, 1) + 0.08 * np.sin(x * 4.0)
        cx.paint(cx.soft(z - bnd, cx.w * 2), "cream")
        cx.stitch_line(np.where(z < 2.2, z - bnd, 9.0), x + y, "mint_dark", period=0.17)
        # taches menthe sur le dessus et les flancs (graine fixe)
        rng = np.random.default_rng(SEED + 5)
        for _ in range(26):
            c = np.array([rng.uniform(-2.3, 2.3), rng.uniform(-1.2, 1.6), 0.0])
            r = rng.uniform(0.13, 0.26)
            d = np.sqrt((x - c[0]) ** 2 + (y - c[1]) ** 2) - r
            cx.paint(cx.soft(d) * (z > 2.75), "mint_mid")
        for _ in range(16):
            sx = rng.choice([-1, 1])
            c = (rng.uniform(-1.1, 1.3), rng.uniform(1.4, 2.6))
            r = rng.uniform(0.1, 0.18)
            d = np.sqrt((y - c[0]) ** 2 + (z - c[1]) ** 2) - r
            cx.paint(cx.soft(d) * (np.sign(x) == sx) * cx.facing((sx, 0, 0), 0.3, 0.5), "mint_mid")
        # écailles brodées sur les flancs (arcs festonnés)
        for sx in (-1, 1):
            side = cx.facing((sx, 0, 0), 0.35, 0.6) * (z > 1.25) * (z < 2.75)
            yy = np.mod(y + 0.0, 0.42) - 0.21
            row = np.floor((z - 1.25) / 0.34)
            yy = np.mod(y + 0.21 * np.mod(row, 2), 0.42) - 0.21
            arc = np.abs(np.sqrt(yy ** 2 + (np.mod(z - 1.25, 0.34) - 0.34) ** 2) - 0.21)
            cx.paint(side * cx.soft(arc - 0.012), "mint_mid")
        # piquants de tissu : menthe soutenu, pointe plus claire
        sp = cx.on(*spike_names, tol=0.03)
        cx.paint(sp, "mint_mid")
        tipness = np.clip((np.abs(x) - 2.62) / 0.22, 0, 1)
        cx.paint(sp * tipness * 0.85, "mint_pastel")
        # lèvres corail, intérieur de bouche marine
        cx.paint(cx.on("lips", tol=0.03), "coral")
        mouth_in = cx.ellipse((0.0, 1.95, 1.22), (0, 1, 0), 0.12, 0.12, depth=0.5)
        cx.paint(mouth_in, "navy")
        # grands yeux : blanc, pupille marine, reflet, cerne brodé
        for sx in (-1, 1):
            n0 = (sx * 0.25, 1, 0.1)
            cx.paint(cx.ellipse((sx * 1.22, 1.9, 2.12), n0, 0.38, 0.38), "cream_white")
            p = cx.ellipse((sx * 1.15, 1.9, 2.05), n0, 0.22, 0.25)
            cx.satin(p, "navy", P[:, 0] + P[:, 2] * 0.2, period=0.04)
            cx.paint(cx.ellipse((sx * 1.15 - 0.07, 1.9, 2.15), n0, 0.07, 0.07), "cream_white")
            s, t, _h = cx.plane_uv((sx * 1.22, 1.9, 2.12), n0)
            ring = np.abs(np.sqrt(s ** 2 + t ** 2) - 0.40)
            cx.paint(cx.soft(ring - 0.022) * cx.facing(n0, 0.05, 0.3), "mint_dark")
        # joues
        for sx in (-1, 1):
            cx.paint(cx.ellipse((sx * 0.62, 1.9, 1.55), (sx * 0.1, 1, 0), 0.2, 0.13) * 0.7, "blush")
        # nageoires et queue corail, rayons brodés
        for fn, sx in (("fin_l", -1), ("fin_r", 1)):
            fm = cx.on(fn, tol=0.025)
            cx.paint(fm, "coral_soft")
            q = P - np.array([sx * 2.30, 0.25, 1.45])
            rr = np.linalg.norm(q, axis=1)
            ang = np.arctan2(q[:, 1], np.abs(q[:, 0]))
            ray = np.abs(np.mod(ang * 4.0 / np.pi + 0.5, 1.0) - 0.5) * rr
            cx.paint(fm * cx.soft(ray - 0.02) * (rr > 0.2), "coral_dark")
        tm = cx.on("tail_root", "tail_fan", tol=0.03)
        cx.paint(tm, "coral_soft")
        q = P - np.array([0.0, -1.66, 2.02])
        ang = np.degrees(np.arctan2(q[:, 0], q[:, 2]))
        rr = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2)
        # rayons brodés entre les nervures (tous les 29 degrés), bord festonné plus foncé
        ray = np.abs(np.mod(ang / 29.0 + 0.5, 1.0) - 0.5) * 29.0 * np.pi / 180.0 * rr
        cx.paint(tm * cx.soft(ray - 0.022) * (rr > 0.45) * (1 - cx.on("tail_root", tol=0.02)), "coral_dark")
        # panneau de dessus cousu
        topm = (z > T - 0.05).astype(float) * cx.facing((0, 0, 1), 0.7, 0.9)
        dd = np.maximum(np.abs(x) - 2.12, np.abs(y - 0.25) - 1.12)
        cx.stitch_line(np.where(topm > 0.5, dd, 9.0), roundrect_param(P, 0.0, 0.25, 2.12, 1.12), "mint_dark")

    secondary = {
        "Fin_L": (np.array([-2.4, 0.25, 1.45]), "fin_l"),
        "Fin_R": (np.array([2.4, 0.25, 1.45]), "fin_r"),
        "Tail": (np.array([0.0, -1.45, 1.95]), "tail"),
    }
    pl = Plush(
        key="bulle", asset_id="toy_plush_bulle", label="Bulle", name_fr="Poisson Bulle", tier="mini",
        envelope=[6, 4, 4], collider_size=[5, 3, 3], collider_center=(0.0, 0.25),
        parts=parts, compose=compose, paint=paint, secondary=secondary, belly_spacing=(1.9, 1.1),
        behavior="stable", behavior_params=None, symmetric=True,
        face_probe={"xz": (1.11, 2.03), "expect": "navy", "what": "pupille droite brodée (côté +X)"},
        visual_brief=("Poisson-globe menthe vu de face : grands yeux brodés, bouche en « o » corail, piquants de "
                      "tissu courts et doux uniquement sur les côtés, nageoires latérales et queue en éventail corail "
                      "relevée derrière (hors rectangle utile). Ventre crème cousu, taches menthe, écailles brodées. "
                      "Dessus plat cousu à hauteur 3. Mini peluche de remplissage."),
    )
    pl.poses = {
        "rest": {},
        "fall": merge(pl.belly_pose(0.34, (-0.10, -0.06)), {
            "Fin_L": {"t": (0.0, 0.0, 0.20), "r": ((0, 1, 0), 14.0)},
            "Fin_R": {"t": (0.0, 0.0, 0.20), "r": ((0, 1, 0), -14.0)},
            "Tail": {"t": (0.0, 0.10, 0.20), "r": ((1, 0, 0), -6.0)},
        }),
        "impact": merge(pl.belly_pose(-0.82, (0.18, 0.12)), {
            "Fin_L": {"t": (-0.03, 0.0, -0.40), "r": ((0, 1, 0), -12.0)},
            "Fin_R": {"t": (0.03, 0.0, -0.40), "r": ((0, 1, 0), 12.0)},
            "Tail": {"t": (0.0, 0.0, -0.55), "r": ((0, 1, 0), 8.0)},
        }),
        "rebound": merge(pl.belly_pose(0.15, (-0.05, -0.03)), {
            "Fin_L": {"t": (0.0, 0.0, 0.08), "r": ((0, 1, 0), 6.0)},
            "Fin_R": {"t": (0.0, 0.0, 0.08), "r": ((0, 1, 0), -6.0)},
            "Tail": {"t": (0.0, 0.0, 0.10), "r": ((0, 1, 0), -4.0)},
        }),
    }
    pl.poses["player_landing"] = pl.landing()
    return pl


# ============================== GRUMF =======================================
def grumf():
    T = 4.0
    tail_pts = [(3.2, -3.95, 1.55), (4.55, -3.92, 1.45), (5.25, -2.95, 1.30), (5.40, -1.45, 1.12),
                (5.20, -0.05, 0.98), (4.80, 0.80, 1.02)]
    tail_rad = [0.92, 0.82, 0.68, 0.55, 0.42, 0.30]
    parts = [
        ("body", "body", slab((0.0, -0.98), (4.28, 4.02), 0.0, 4.25, 0.85, 0.5)),
        ("belly", "body", superellipsoid((0.0, -0.95, 1.95), (4.52, 3.98, 2.02), eh=3.0, ev=2.4)),
        ("neck", "body", ellipsoid((0.0, 2.75, 2.25), (2.7, 1.3, 1.62))),
        ("head", "head", superellipsoid((0.0, 4.02, 4.05), (2.9, 0.95, 1.95), eh=2.0, ev=2.3, rot=(-8, 0, 0))),
        ("snout", "head", ellipsoid((0.0, 4.32, 3.18), (2.15, 0.60, 0.98))),
        ("cheek_l", "head", ellipsoid((-2.3, 3.95, 3.30), (0.85, 0.95, 0.85))),
        ("cheek_r", "head", ellipsoid((2.3, 3.95, 3.30), (0.85, 0.95, 0.85))),
        ("brow_l", "head", ellipsoid((-1.18, 4.42, 5.20), (0.62, 0.50, 0.42))),
        ("brow_r", "head", ellipsoid((1.18, 4.42, 5.20), (0.62, 0.50, 0.42))),
        ("leg_fl", "leg_fl", round_cone((-3.9, 1.6, 1.05), (-5.18, 2.45, 0.74), 0.92, 0.74)),
        ("leg_fr", "leg_fr", round_cone((3.9, 1.6, 1.05), (5.18, 2.45, 0.74), 0.92, 0.74)),
        ("leg_bl", "leg_bl", round_cone((-3.9, -3.2, 1.05), (-5.18, -3.95, 0.74), 0.92, 0.74)),
        ("leg_br", "leg_br", round_cone((3.75, -3.35, 0.9), (4.60, -4.30, 0.55), 0.70, 0.52)),
        ("tail", "tail", chain(tail_pts, tail_rad)),
    ]
    # plaques arrondies (uniquement sur la queue) : ellipsoïdes aplatis dans le plan de la queue
    plates = []
    for k, (i, size) in enumerate(((0.75, 0.80), (1.85, 0.68), (2.9, 0.54), (3.85, 0.40))):
        j = int(math.floor(i))
        t = i - j
        a = np.array(tail_pts[j])
        b = np.array(tail_pts[min(j + 1, len(tail_pts) - 1)])
        c = a + t * (b - a)
        r = tail_rad[j] + t * (tail_rad[min(j + 1, len(tail_rad) - 1)] - tail_rad[j])
        tang = b - a
        yaw = math.degrees(math.atan2(tang[1], tang[0]))
        ctr = c + np.array([0, 0, r * 0.78 + size * 0.42])
        plates.append((f"plate_{k}", "tail", ellipsoid(ctr, (size * 0.92, 0.25, size * 0.88), rot=(0, 0, yaw))))
    parts += plates
    plate_names = [p[0] for p in plates]
    claws = []
    for leg, (ex, ey, ez), dirx, diry in (("leg_fl", (-5.18, 2.45, 0.72), -1, 0.55), ("leg_fr", (5.18, 2.45, 0.72), 1, 0.55),
                                         ("leg_bl", (-5.18, -3.95, 0.72), -1, -0.45), ("leg_br", (4.6, -4.3, 0.55), 1, -1.0)):
        d = np.array([dirx, diry, 0.0])
        d /= np.linalg.norm(d)
        side = np.array([-d[1], d[0], 0.0])
        rr = 0.70 if leg != "leg_br" else 0.52
        for k in (-1, 0, 1):
            c = np.array([ex, ey, max(0.2, ez - 0.4)]) + d * (rr * 0.85) + side * (k * 0.32 * rr / 0.7)
            claws.append((f"claw_{leg}_{k + 1}", leg, ellipsoid(c, (0.17, 0.17, 0.15))))
    parts += claws
    claw_names = [p[0] for p in claws]

    def compose(D, P):
        f = smin(D["body"], D["belly"], 0.6)
        head = smin(D["head"], D["snout"], 0.35)
        head = smin(head, smin(D["cheek_l"], D["cheek_r"], 0.0), 0.3)
        head = smin(head, smin(D["brow_l"], D["brow_r"], 0.0), 0.25)
        head = smin(head, D["neck"], 0.5)
        f = smin(f, head, 0.45)
        for lg in ("leg_fl", "leg_fr", "leg_bl", "leg_br"):
            f = smin(f, D[lg], 0.3)
        f = smin(f, Umin(D, claw_names, 0.0), 0.06)
        tail = smin(D["tail"], Umin(D, plate_names, 0.0), 0.12)
        return smin(f, tail, 0.35)

    def paint(cx):
        P, N = cx.P, cx.N
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        cx.fill("lilac")
        # dessous / gorge menthe clair
        chin = cx.on("snout", "neck", tol=0.05) * cx.soft(z - (3.35 + 0.15 * np.cos(x * 1.4)), cx.w * 2)
        cx.paint(chin, "mint_pastel")
        cx.stitch_line(np.where(cx.on("snout", "neck", "head", tol=0.06) > 0.5, z - (3.35 + 0.15 * np.cos(x * 1.4)), 9.0),
                       x, "lilac_dark", period=0.2)
        # taches menthe appliquées sur le dos (feston)
        topm = (z > T - 0.05).astype(float) * cx.facing((0, 0, 1), 0.7, 0.9)
        for (sx_, sy_, r) in ((-1.8, -2.6, 0.85), (1.6, -0.6, 0.7), (-0.9, 0.9, 0.55), (2.3, -3.4, 0.5),
                              (-2.7, -0.4, 0.45), (0.4, -3.9, 0.4), (0.6, 1.9, 0.38)):
            d = np.sqrt((x - sx_) ** 2 + (y - sy_) ** 2) - r
            cx.paint(cx.soft(d) * topm, "mint_pastel")
            ring = np.abs(d + 0.07)
            ang = np.arctan2(y - sy_, x - sx_) * r
            cx.paint(cx.soft(ring - 0.022) * topm * cx.dash(ang, 0.18, 0.6), "mint_dark")
        # flancs : taches menthe plus petites
        rng = np.random.default_rng(SEED + 11)
        for _ in range(18):
            sx = rng.choice([-1, 1])
            c = (rng.uniform(-4.0, 1.8), rng.uniform(1.6, 3.4))
            r = rng.uniform(0.18, 0.32)
            d = np.sqrt((y - c[0]) ** 2 + (z - c[1]) ** 2) - r
            cx.paint(cx.soft(d) * (np.sign(x) == sx) * cx.facing((sx, 0, 0), 0.4, 0.6) * cx.on("body", "belly", tol=0.06),
                     "lilac_light")
        # plaques de queue menthe, couture centrale
        pm = cx.on(*plate_names, tol=0.03)
        cx.paint(pm, "mint_mid")
        cx.paint(pm * cx.soft(cx.D["tail"] - 0.06) * 0.0, "mint_mid")
        cx.paint(cx.on("tail", tol=0.03) * cx.soft(-(np.linalg.norm(P[:, :2] - np.array([4.8, 0.8]), axis=1) - 0.55)),
                 "mint_pastel")
        # griffes crème
        cx.paint(cx.on(*claw_names, tol=0.03), "cream")
        # visage : yeux brodés, reflets, sourcils, narines, sourire, joues
        n0 = (0, 1, 0.12)
        for sx in (-1, 1):
            ne = (sx * 0.25, 1, 0.15)
            e = cx.ellipse((sx * 1.15, 4.8, 4.72), ne, 0.36, 0.44)
            cx.satin(e, "navy", P[:, 0] + P[:, 2] * 0.2, period=0.05)
            cx.paint(cx.ellipse((sx * 1.15 - 0.11, 4.8, 4.9), ne, 0.12, 0.13), "cream_white")
            cx.paint(cx.ellipse((sx * 1.15 + 0.12, 4.8, 4.52), ne, 0.055, 0.06), "cream_white")
            cx.paint(cx.segment_mask((sx * 1.15, 4.8, 5.42), (sx * 0.3, 1, 0.6),
                                     [(-0.3 * sx, -0.04), (0.0, 0.06), (0.3 * sx, 0.0)], 0.035), "lilac_dark")
            cx.paint(cx.ellipse((sx * 2.2, 4.6, 3.75), (sx * 0.7, 1, 0), 0.38, 0.24) * 0.8, "blush")
            cx.paint(cx.ellipse((sx * 0.42, 5.0, 3.85), (sx * 0.1, 1, 0.5), 0.1, 0.065), "navy")
        smile = cx.segment_mask((0.0, 5.0, 3.42), n0,
                                [(-0.95, 0.16), (-0.55, -0.06), (0.0, -0.15), (0.55, -0.06), (0.95, 0.16)], 0.032)
        cx.paint(smile, "navy")
        # deux petites dents brodées crème
        for sx in (-1, 1):
            cx.paint(cx.segment_mask((sx * 0.3, 5.0, 3.22), n0, [(-0.07, 0.02), (0.0, -0.1), (0.07, 0.02)], 0.03)
                     * cx.facing((0, 1, 0), 0.3, 0.6), "cream_white")
        # couture médiane du crâne (du front jusqu'à la nuque) et taches menthe à l'arrière de la tête
        hm = cx.on("head", "brow_l", "brow_r", tol=0.06) * np.maximum(cx.facing((0, 0.2, 1), 0.2, 0.5),
                                                                      cx.facing((0, -1, 0.2), 0.2, 0.5))
        cx.stitch_line(np.where((hm > 0.5) & (z > 4.1), x, 9.0), y + z, "lilac_dark")
        hb = cx.on("head", tol=0.05) * cx.facing((0, -1, 0.1), 0.3, 0.6)
        for (bx, bz, br) in ((-1.5, 4.9, 0.36), (1.25, 5.25, 0.3), (1.9, 4.45, 0.24), (-0.7, 5.55, 0.22)):
            cx.paint(hb * cx.soft(np.sqrt((x - bx) ** 2 + (z - bz) ** 2) - br), "mint_pastel")
        # coutures des pattes (anneau à la jonction)
        for lg in ("leg_fl", "leg_fr", "leg_bl", "leg_br"):
            seam = cx.D[lg] - smin(cx.D["body"], cx.D["belly"], 0.6)
            cx.stitch_line(np.where(cx.on(lg, "body", "belly", tol=0.12) > 0.5, seam, 9.0), z * 2 + x + y,
                           "lilac_dark", width=0.035)
        # panneau de dessus cousu
        dd = np.maximum(np.abs(x) - 3.55, np.abs(y + 1.0) - 3.55)
        cx.stitch_line(np.where(topm > 0.5, dd, 9.0), roundrect_param(P, 0.0, -1.0, 3.55, 3.55), "lilac_dark",
                       width=0.04, period=0.24)

    secondary = {
        "Head": (np.array([0.0, 3.2, 3.6]), "head"),
        "Tail": (np.array([3.6, -3.8, 1.5]), "tail"),
        "Leg_FL": (np.array([-3.9, 1.6, 1.0]), "leg_fl"),
        "Leg_FR": (np.array([3.9, 1.6, 1.0]), "leg_fr"),
        "Leg_BL": (np.array([-3.9, -3.2, 1.0]), "leg_bl"),
        "Leg_BR": (np.array([3.75, -3.35, 0.9]), "leg_br"),
    }
    pl = Plush(
        key="grumf", asset_id="toy_plush_grumf", label="Grumf", name_fr="Dino Grumf", tier="medium",
        envelope=[12, 10, 6], collider_size=[8, 8, 4], collider_center=(0.0, -1.0),
        parts=parts, compose=compose, paint=paint, secondary=secondary, belly_spacing=(3.0, 3.0),
        behavior="stable", behavior_params=None, symmetric=False,
        face_probe={"xz": (1.15, 4.62), "expect": "navy", "what": "œil droit brodé (côté +X)"},
        visual_brief=("Bébé dinosaure lilas allongé à plat, grosse tête ronde relevée à l'avant (hors rectangle "
                      "utile), yeux et sourire brodés marine, gorge menthe cousue, joues rosées. Queue enroulée le "
                      "long du flanc droit portant cinq plaques arrondies menthe (plaques uniquement sur la queue), "
                      "quatre pattes courtes écartées à griffes crème. Dos plat à hauteur 4 avec taches menthe "
                      "appliquées au point de feston et panneau cousu."),
    )
    head = secondary["Head"][0]
    pl.poses = {
        "rest": {},
        "fall": merge(pl.belly_pose(0.46, (-0.20, -0.20)), {
            "Head": {"t": (0.0, 0.0, 0.30), "r": ((1, 0, 0), 8.0)},
            "Tail": {"t": (0.0, 0.0, 0.22), "r": ((0, 1, 0), -8.0)},
            "Leg_FL": {"t": (0.0, 0.0, 0.16), "r": ((0, 1, 0), 10.0)},
            "Leg_FR": {"t": (0.0, 0.0, 0.16), "r": ((0, 1, 0), -10.0)},
            "Leg_BL": {"t": (0.0, 0.0, 0.14), "r": ((0, 1, 0), 10.0)},
            "Leg_BR": {"t": (0.0, 0.0, 0.14), "r": ((0, 1, 0), -10.0)},
        }),
        "impact": merge(pl.belly_pose(-1.10, (0.60, 0.45)), {
            "Head": {"t": (0.0, 0.22, -0.85), "r": ((1, 0, 0), -9.0)},
            "Tail": {"t": (0.35, 0.0, -0.25), "r": ((0, 1, 0), 6.0)},
            "Leg_FL": {"t": (-0.32, 0.12, -0.30), "r": ((0, 1, 0), -8.0)},
            "Leg_FR": {"t": (0.32, 0.12, -0.30), "r": ((0, 1, 0), 8.0)},
            "Leg_BL": {"t": (-0.32, -0.10, -0.30), "r": ((0, 1, 0), -8.0)},
            "Leg_BR": {"t": (0.28, -0.12, -0.26), "r": ((0, 1, 0), 8.0)},
        }),
        "rebound": merge(pl.belly_pose(0.20, (-0.10, -0.10)), {
            "Head": {"t": (0.0, 0.0, 0.16), "r": ((1, 0, 0), 4.0)},
            "Tail": {"t": (0.0, 0.0, 0.10), "r": None},
        }),
    }
    pl.poses["player_landing"] = pl.landing()
    _ = head
    return pl


# ============================== NUAGE =======================================
def nuage():
    T = 4.0
    parts = [
        ("core", "body", slab((0.0, -0.98), (4.10, 3.51), 0.0, 3.97, 0.55, 0.38)),
    ]
    # pompons du dessus (aplatis par le couvercle à hauteur 4) : 3 x 3, creux de matelassage peu profonds
    top_puffs = []
    for i, xx in enumerate((-2.72, 0.0, 2.72)):
        for j, yy in enumerate((-3.15, -1.0, 1.15)):
            top_puffs.append((f"tp_{i}{j}", "body", ellipsoid((xx, yy, 2.95), (1.62, 1.36, 1.38))))
    # pompons latéraux (couronne basse) : silhouette de nuage festonnée
    side_puffs = []
    ring = [(-3.78, -3.30), (-3.86, -1.42), (-3.86, 0.52), (-3.45, 1.95), (3.78, -3.30), (3.86, -1.42), (3.86, 0.52),
            (3.45, 1.95), (-1.85, -3.42), (0.0, -3.42), (1.85, -3.42), (-1.95, 1.95), (1.95, 1.95)]
    for k, (xx, yy) in enumerate(ring):
        ry = 1.04 if yy < -3.0 else 1.22
        side_puffs.append((f"sp_{k}", "body", ellipsoid((xx, yy, 1.78), (1.16, ry, 1.30))))
    parts += top_puffs + side_puffs
    parts += [
        ("leg_fl", "body", round_cone((-3.0, 1.85, 1.0), (-3.45, 2.25, 0.32), 0.55, 0.5)),
        ("leg_fr", "body", round_cone((3.0, 1.85, 1.0), (3.45, 2.25, 0.32), 0.55, 0.5)),
        ("leg_bl", "body", round_cone((-3.0, -3.45, 1.0), (-3.45, -3.85, 0.32), 0.55, 0.5)),
        ("leg_br", "body", round_cone((3.0, -3.45, 1.0), (3.45, -3.85, 0.32), 0.55, 0.5)),
        ("head", "head", ellipsoid((0.0, 3.42, 4.12), (1.72, 1.0, 1.55), rot=(22, 0, 0))),
        ("muzzle", "head", ellipsoid((0.0, 3.90, 3.40), (1.12, 0.50, 0.70), rot=(18, 0, 0))),
        ("wool_a", "head", ellipsoid((-0.62, 3.22, 5.38), (0.58, 0.50, 0.48))),
        ("wool_b", "head", ellipsoid((0.62, 3.22, 5.38), (0.58, 0.50, 0.48))),
        ("wool_c", "head", ellipsoid((0.0, 3.36, 5.58), (0.52, 0.48, 0.44))),
        ("ear_l", "ear_l", ellipsoid((-2.05, 3.22, 4.55), (0.95, 0.30, 0.38), rot=(0, 26, -12))),
        ("ear_r", "ear_r", ellipsoid((2.05, 3.22, 4.55), (0.95, 0.30, 0.38), rot=(0, -26, 12))),
        ("bow_knot", "bow", ellipsoid((1.10, 3.45, 5.48), (0.19, 0.18, 0.19))),
        ("bow_a", "bow", ellipsoid((0.72, 3.45, 5.60), (0.36, 0.16, 0.26), rot=(0, 18, 0))),
        ("bow_b", "bow", ellipsoid((1.48, 3.45, 5.40), (0.36, 0.16, 0.26), rot=(0, 18, 0))),
    ]
    tp_names = [p[0] for p in top_puffs]
    sp_names = [p[0] for p in side_puffs]
    puff_names = tp_names + sp_names

    def compose(D, P):
        f = D["core"]
        f = smin(f, Umin(D, tp_names, 0.22), 0.25)
        f = smin(f, Umin(D, sp_names, 0.18), 0.25)
        for lg in ("leg_fl", "leg_fr", "leg_bl", "leg_br"):
            f = smin(f, D[lg], 0.15)
        head = smin(D["head"], D["muzzle"], 0.3)
        wool = Umin(D, ["wool_a", "wool_b", "wool_c"], 0.12)
        head = smin(head, wool, 0.14)
        f = smin(f, head, 0.3)
        f = smin(f, D["ear_l"], 0.1)
        f = smin(f, D["ear_r"], 0.1)
        bow = Umin(D, ["bow_knot", "bow_a", "bow_b"], 0.05)
        return smin(f, bow, 0.06)

    def paint(cx):
        P, N = cx.P, cx.N
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        cx.fill("cream")
        # matelassage : couture le long des creux entre deux pompons voisins
        Dp = np.stack([cx.D[n] for n in puff_names], axis=1)
        srt = np.sort(Dp, axis=1)
        crease = srt[:, 1] - srt[:, 0]
        wool_zone = cx.on("core", *puff_names, tol=0.12) * (1 - cx.on("head", "muzzle", tol=0.1))
        cx.stitch_line(np.where((wool_zone > 0.5) & (z < T - 0.06), crease - 0.0, 9.0), z * 1.3 + x * 0.7 + y * 0.7,
                       "caramel", width=0.03, period=0.2)
        topm = (z > T - 0.05).astype(float) * cx.facing((0, 0, 1), 0.7, 0.9)
        # lignes de matelassage du dessus (entre les pompons aplatis)
        for xl in (-1.36, 1.36):
            cx.stitch_line(np.where(topm > 0.5, x - xl, 9.0), y, "caramel", width=0.03)
        for yl in (-2.08, 0.08):
            cx.stitch_line(np.where(topm > 0.5, y - yl, 9.0), x, "caramel", width=0.03)
        # boucles de laine (petits motifs en spirale brodés ton sur ton)
        rng = np.random.default_rng(SEED + 21)
        for _ in range(60):
            c = np.array([rng.uniform(-4.6, 4.6), rng.uniform(-4.3, 2.3), rng.uniform(0.5, 4.0)])
            d = np.linalg.norm(P - c, axis=1)
            cx.shade(cx.soft(np.abs(d - 0.12) - 0.012) * wool_zone * (d < 0.2), 0.9)
        # pattes marine (sabots)
        cx.paint(cx.on("leg_fl", "leg_fr", "leg_bl", "leg_br", tol=0.05) * cx.soft(z - 1.05, 0.05), "navy")
        # tête marine, laine du crâne crème
        hm = cx.on("head", "muzzle", tol=0.035)
        cx.paint(hm, "navy_face")
        cx.paint(cx.on("wool_a", "wool_b", "wool_c", tol=0.03), "cream")
        # oreilles marine, intérieur rose
        for en, sx in (("ear_l", -1), ("ear_r", 1)):
            em = cx.on(en, tol=0.03)
            cx.paint(em, "navy_face")
            cx.paint(em * cx.facing((0, 1, 0.3), 0.2, 0.5) * cx.soft(np.abs(z - 4.55) - 0.13) *
                     (np.abs(x) > 1.85) * (np.abs(x) < 2.85), "pink")
        # yeux fermés brodés crème (arcs), cils
        for sx in (-1, 1):
            n0 = (sx * 0.35, 1, 0.3)
            arc = cx.segment_mask((sx * 0.70, 4.0, 4.42), n0,
                                  [(-0.30, 0.07), (-0.15, -0.07), (0.0, -0.10), (0.15, -0.07), (0.30, 0.07)], 0.04)
            cx.paint(arc * hm, "cream_white")
            for k in (-1, 0, 1):
                cx.paint(cx.segment_mask((sx * 0.70, 4.0, 4.42), n0, [(k * 0.16, -0.09), (k * 0.23, -0.22)], 0.02)
                         * hm, "cream_white")
            cx.paint(cx.ellipse((sx * 1.0, 4.0, 3.9), n0, 0.25, 0.15) * 0.8 * hm, "blush")
        # nez corail et bouche brodée crème
        cx.paint(cx.ellipse((0.0, 4.45, 3.58), (0, 1, 0.35), 0.19, 0.12) * hm, "coral")
        mouth = cx.segment_mask((0.0, 4.45, 3.28), (0, 1, 0.1),
                                [(-0.26, 0.05), (-0.13, -0.06), (0.0, 0.02), (0.13, -0.06), (0.26, 0.05)], 0.025)
        mouth = np.maximum(mouth, cx.segment_mask((0.0, 4.45, 3.28), (0, 1, 0.1), [(0.0, 0.02), (0.0, 0.22)], 0.025))
        cx.paint(mouth * hm, "cream_white")
        # nœud corail, couture et pli
        bm = cx.on("bow_knot", "bow_a", "bow_b", tol=0.03)
        cx.paint(bm, "coral")
        cx.paint(cx.on("bow_knot", tol=0.02), "coral_dark")
        for bn in ("bow_a", "bow_b"):
            cx.shade(cx.on(bn, tol=0.02) * cx.soft(np.abs(z - 5.5 + (x - 1.10) * 0.27) - 0.02), 0.75)
        # étiquette
        tag = cx.ellipse((2.0, -4.45, 0.9), (0, -1, 0), 0.32, 0.2, depth=1.2)
        cx.paint(tag, "cream_white")
        cx.paint(tag * cx.soft(np.abs(z - 0.9) - 0.03), "coral")

    secondary = {
        "Head": (np.array([0.0, 3.15, 3.9]), "head"),
        "Ear_L": (np.array([-1.5, 3.22, 4.55]), "ear_l"),
        "Ear_R": (np.array([1.5, 3.22, 4.55]), "ear_r"),
        "Bow": (np.array([1.10, 3.45, 5.4]), "bow"),
    }
    pl = Plush(
        key="nuage", asset_id="toy_plush_nuage", label="Nuage", name_fr="Mouton Nuage", tier="medium",
        envelope=[10, 9, 6], collider_size=[8, 7, 4], collider_center=(0.0, -1.0),
        parts=parts, compose=compose, paint=paint, secondary=secondary, belly_spacing=(3.0, 2.6),
        behavior="bounce", behavior_params={"vertical_impulse_multiplier": 1.12}, symmetric=False,
        face_probe={"xz": (0.0, 3.95), "expect": "navy_face", "what": "visage marine entre les yeux et le nez"},
        visual_brief=("Mouton crème en nuage de pompons matelassés : couronne de pompons festonnés sur les côtés, "
                      "pompons du dessus aplatis à hauteur 4 (matelassage cousu, dessus plat). Tête marine relevée "
                      "à l'avant (hors rectangle utile) avec houppette de laine, yeux fermés brodés crème, nez corail, "
                      "oreilles marine à intérieur rose, petit nœud corail ; quatre sabots marine. Rebond moelleux."),
    )
    hh = secondary["Head"][0]
    head_fall = {"t": (0.0, 0.0, 0.30), "r": ((1, 0, 0), 7.0)}
    head_imp = {"t": (0.0, 0.18, -0.95), "r": ((1, 0, 0), -8.0)}
    head_reb = {"t": (0.0, 0.0, 0.16), "r": ((1, 0, 0), 3.0)}
    pl.poses = {"rest": {}}
    for pname, hp, dz, rad, ear_extra, bow_extra in (
            ("fall", head_fall, 0.46, (-0.20, -0.18), 9.0, 6.0),
            ("impact", head_imp, -1.10, (0.60, 0.42), -9.0, -6.0),
            ("rebound", head_reb, 0.20, (-0.10, -0.08), 4.0, 3.0)):
        pose = merge(pl.belly_pose(dz, rad), {"Head": hp})
        pose["Ear_L"] = follow(hh, hp, secondary["Ear_L"][0], extra_r=((0, 1, 0), -ear_extra))
        pose["Ear_R"] = follow(hh, hp, secondary["Ear_R"][0], extra_r=((0, 1, 0), ear_extra))
        pose["Bow"] = follow(hh, hp, secondary["Bow"][0], extra_r=((0, 1, 0), bow_extra))
        pl.poses[pname] = pose
    pl.poses["player_landing"] = pl.landing()
    return pl


PLUSHES = {"pipou": pipou, "mochi": mochi, "bulle": bulle, "grumf": grumf, "nuage": nuage}
MODEL_DIRS = {"pipou": "Pipou", "mochi": "Mochi", "bulle": "Bulle", "grumf": "Grumf", "nuage": "Nuage"}

BUDGETS = {
    "mini": {"lod0_min": 800, "lod0_max": 1600, "lod1_max": 400, "lod0_target": 1520, "lod1_target": 380,
             "voxel": 0.032},
    "medium": {"lod0_min": 2000, "lod0_max": 3400, "lod1_max": 700, "lod0_target": 3250, "lod1_target": 670,
               "voxel": 0.05},
}

RUNTIME_LIMITS = {
    "fall_stretch_y_max": 1.12,
    "impact_scale_y_min": 0.72,
    "impact_scale_xz_max": 1.18,
    "plush_lattice_bones": 9,
    "secondary_bones_max": 6,
    "max_secondary_angle_degrees": 18,
    "walkable_top_alignment_tolerance_studs": 0.25,
}
