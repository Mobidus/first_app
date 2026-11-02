"""Specifications procédurales des peluches FILLING UP (Mallow, Loppy, Octo).

Module pur (numpy uniquement), partagé par build_plush.py et verify_exports.py.

Conventions (voir docs/decisions/0003 et 0004) :
- 1 unité Blender = 1 stud. Axes Blender : X = largeur, Y = profondeur, Z = hauteur.
- Pivot bottom_center : origine au centre de l'empreinte au sol (z = 0).
- Avant Roblox (-Z, LookVector) = +Y Blender (le glTF convertit (x, y, z) -> (x, z, -y)).
- Toutes les dimensions sont issues de config/rooms.json (size_studs et collider).

Chaque créature est décrite par des primitives implicites (superellipsoïdes) unies
par remaillage voxel, par une fonction de couleurs de régions (peinture
procédurale des tissus, coutures, broderies) et par un rig :
  Root (ancrage statique, jamais posé) + 9 bones de ventre en grille 3x3
  + au plus 6 secondaires.
"""
from __future__ import annotations

import math
import numpy as np

# ---------------------------------------------------------------------------
# Palette (sRGB hex). Les couleurs fonctionnelles (menthe #39E68B, corail
# danger #FF684B, cyan mobile...) ne sont PAS utilisées sur les corps : elles
# sont réservées aux balises de dessus (docs/04 §2).
# ---------------------------------------------------------------------------
HEX = {
    "mallow_fabric": "#EBCB98",
    "mallow_belly": "#FFF1D2",
    "caramel": "#C98A4B",
    "caramel_light": "#DDA769",
    "star_patch": "#F6CF4F",
    "stitch_navy": "#203055",
    "stitch_caramel": "#9C6331",
    "nose_brown": "#4A2E1C",
    "loppy_fabric": "#BBA3E6",
    "loppy_cream": "#FFF1DA",
    "loppy_ear_inner": "#F7C9D6",
    "loppy_nose": "#F07C6A",
    "octo_fabric": "#8FDDBE",
    "octo_under": "#F38D72",
    "octo_sucker": "#FFD3C2",
    "octo_eye_white": "#FFF5DF",
}


def srgb_to_linear(hex_color: str) -> np.ndarray:
    h = hex_color.lstrip("#")
    c = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def col(name: str) -> np.ndarray:
    return srgb_to_linear(HEX[name])


# ---------------------------------------------------------------------------
# Primitives implicites
# ---------------------------------------------------------------------------
def rot_matrix(euler_deg):
    rx, ry, rz = [math.radians(a) for a in euler_deg]
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ my @ mx


class Prim:
    """Superellipsoïde : ((|x|^eh + |y|^eh)^(ev/eh) + |z|^ev)^(1/ev) = 1."""

    def __init__(self, name, center, radii, eh=2.0, ev=2.0, rot=(0, 0, 0), owner="body"):
        self.name = name
        self.center = np.asarray(center, dtype=float)
        self.radii = np.asarray(radii, dtype=float)
        self.eh = float(eh)
        self.ev = float(ev)
        self.R = rot_matrix(rot)
        self.owner = owner  # groupe de skinning : body, head, arm_l, ...

    def local(self, p):
        p = np.atleast_2d(p) - self.center
        return (p @ self.R) / self.radii  # R orthonormale : inverse = transposée

    def value(self, p):
        q = np.abs(self.local(p)) + 1e-12
        xy = (q[:, 0] ** self.eh + q[:, 1] ** self.eh) ** (self.ev / self.eh)
        return (xy + q[:, 2] ** self.ev) ** (1.0 / self.ev)

    def surface_points(self, seg=48, rings=24):
        """Points de surface (et faces quad/tri) d'une sphère UV projetée."""
        verts, faces = [], []
        for r in range(1, rings):
            th = math.pi * r / rings
            for s in range(seg):
                ph = 2 * math.pi * s / seg
                verts.append((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)))
        top = len(verts)
        verts.append((0, 0, 1))
        bot = len(verts)
        verts.append((0, 0, -1))
        d = np.array(verts)
        # rayon tel que f(r*d) = 1 dans l'espace normalisé
        q = np.abs(d) + 1e-12
        f = ((q[:, 0] ** self.eh + q[:, 1] ** self.eh) ** (self.ev / self.eh) + q[:, 2] ** self.ev) ** (1.0 / self.ev)
        loc = d / f[:, None]
        world = (loc * self.radii) @ self.R.T + self.center
        for r in range(rings - 2):
            for s in range(seg):
                a = r * seg + s
                b = r * seg + (s + 1) % seg
                faces.append((a, b, b + seg, a + seg))
        for s in range(seg):
            faces.append((top, (s + 1) % seg, s))
            base = (rings - 2) * seg
            faces.append((bot, base + s, base + (s + 1) % seg))
        return world, faces


# ---------------------------------------------------------------------------
# Motifs procéduraux (coutures, broderies)
# ---------------------------------------------------------------------------
def seg_dist(p2, a, b):
    """Distance 2D point(s)-segment et paramètre t (0..1)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ab = b - a
    t = np.clip(((p2 - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
    proj = a + t[:, None] * ab
    return np.linalg.norm(p2 - proj, axis=1), t


def polyline_stitch(p2, pts, width=0.05, dash=0.32, duty=0.55, closed=False):
    """Point de couture en pointillés (running stitch) le long d'une polyligne."""
    pts = [np.asarray(x, float) for x in pts]
    if closed:
        pts = pts + [pts[0]]
    best = np.full(len(p2), 1e9)
    arc_at_best = np.zeros(len(p2))
    acc = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        d, t = seg_dist(p2, a, b)
        L = float(np.linalg.norm(b - a))
        better = d < best
        best = np.where(better, d, best)
        arc_at_best = np.where(better, acc + t * L, arc_at_best)
        acc += L
    on = (best < width) & (np.mod(arc_at_best / dash, 1.0) < duty)
    return on


def star_polygon(cx, cy, r_out, r_in, rot_deg=90.0, n=5):
    pts = []
    for k in range(2 * n):
        r = r_out if k % 2 == 0 else r_in
        a = math.radians(rot_deg) + math.pi * k / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def point_in_polygon(p2, poly):
    x, y = p2[:, 0], p2[:, 1]
    inside = np.zeros(len(p2), dtype=bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cond = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1)
        inside ^= cond
    return inside


def ellipse_blanket_stitch(p2, cx, cy, a, b, line_off=0.22, width=0.045, tick_every=0.42, tick_w=0.06):
    """Point de feston (blanket stitch) autour d'une ellipse : ligne extérieure + piquets."""
    dx = (p2[:, 0] - cx) / a
    dy = (p2[:, 1] - cy) / b
    rho = np.sqrt(dx * dx + dy * dy)
    dist = (rho - 1.0) * min(a, b)  # >0 à l'extérieur
    theta = np.arctan2(dy, dx)
    arc = theta * (a + b) * 0.5
    line = np.abs(dist - line_off) < width
    ticks = (dist > -0.02) & (dist < line_off) & (np.mod(arc / tick_every, 1.0) < tick_w / tick_every * 2.0)
    return line | ticks


# ---------------------------------------------------------------------------
# Description de créature
# ---------------------------------------------------------------------------
class Creature:
    def __init__(self, asset_id, label, size_studs, collider, collider_center_xy, prims,
                 secondary_bones, belly_grid_center, belly_spacing, belly_top_z,
                 behavior, color_fn, poses):
        self.asset_id = asset_id
        self.label = label
        self.size_studs = size_studs          # [largeur, profondeur, hauteur]
        self.collider = collider              # dict box size_studs [w, d, h]
        self.collider_center_xy = collider_center_xy
        self.prims = prims
        self.secondary_bones = secondary_bones  # {name: (head_xyz, owner_group)}
        self.belly_grid_center = belly_grid_center
        self.belly_spacing = belly_spacing
        self.belly_top_z = belly_top_z
        self.behavior = behavior
        self.color_fn = color_fn
        self.poses = poses

    # ---- bones -------------------------------------------------------------
    def belly_bone_names(self):
        return [f"Belly_{i}{j}" for j in range(3) for i in range(3)]  # i = colonne X, j = rangée Y

    def belly_bone_heads(self):
        cx, cy = self.belly_grid_center
        s = self.belly_spacing
        z = self.belly_top_z - 1.0
        out = {}
        for j in range(3):
            for i in range(3):
                out[f"Belly_{i}{j}"] = np.array([cx + (i - 1) * s[0], cy + (j - 1) * s[1], z])
        return out

    # ---- régions -----------------------------------------------------------
    def owner_memberships(self, P):
        """Appartenance douce de chaque sommet à chaque groupe de skinning."""
        groups = {}
        for pr in self.prims:
            f = pr.value(P)
            s = np.exp(-np.clip(f - 1.0, 0, None) * 9.0)
            groups[pr.owner] = np.maximum(groups.get(pr.owner, 0), s)
        return groups

    def skin_weights(self, P, max_influences=4):
        """Poids normalisés par sommet : dict bone -> array(n).

        - body : réparti verticalement entre Root (bas, immobile) et la grille
          de ventre (haut), interpolation barycentrique (3 bones max) sur la grille
          -> au plus 4 influences avec Root.
        - autres groupes : leur bone secondaire.
        """
        n = len(P)
        groups = self.owner_memberships(P)
        total = sum(groups.values()) + 1e-12
        names = ["Root"] + self.belly_bone_names() + list(self.secondary_bones.keys())
        W = {k: np.zeros(n) for k in names}

        # body
        body = groups.get("body", np.zeros(n)) / total
        t = np.clip(P[:, 2] / self.belly_top_z, 0.0, 1.0)  # linéaire -> échelle verticale uniforme
        W["Root"] += body * (1.0 - t)
        cx, cy = self.belly_grid_center
        u = np.clip((P[:, 0] - cx) / self.belly_spacing[0] + 1.0, 0.0, 2.0)
        v = np.clip((P[:, 1] - cy) / self.belly_spacing[1] + 1.0, 0.0, 2.0)
        i0 = np.minimum(np.floor(u).astype(int), 1)
        j0 = np.minimum(np.floor(v).astype(int), 1)
        fu = u - i0
        fv = v - j0
        lower = (fu + fv) <= 1.0
        # triangle inférieur : (i0,j0), (i0+1,j0), (i0,j0+1)
        # triangle supérieur : (i0+1,j0+1), (i0,j0+1), (i0+1,j0)
        corners = []
        for k in range(n):
            if lower[k]:
                corners.append(((i0[k], j0[k], 1 - fu[k] - fv[k]), (i0[k] + 1, j0[k], fu[k]), (i0[k], j0[k] + 1, fv[k])))
            else:
                corners.append(((i0[k] + 1, j0[k] + 1, fu[k] + fv[k] - 1), (i0[k], j0[k] + 1, 1 - fu[k]), (i0[k] + 1, j0[k], 1 - fv[k])))
        for k, cs in enumerate(corners):
            for (ii, jj, w) in cs:
                W[f"Belly_{ii}{jj}"][k] += body[k] * t[k] * w

        # secondaires : les sommets en contact avec le sol (z < 0.6) restent ancrés à Root
        floor = np.clip(1.0 - P[:, 2] / 0.6, 0.0, 1.0)
        for bname, (_head, owner) in self.secondary_bones.items():
            g = groups.get(owner, np.zeros(n)) / total
            W[bname] += g * (1.0 - floor)
            W["Root"] += g * floor

        # élagage à max_influences puis normalisation
        M = np.stack([W[k] for k in names], axis=1)
        M[M < 1e-5] = 0.0
        order = np.argsort(-M, axis=1)
        keep = np.zeros_like(M, dtype=bool)
        rows = np.arange(n)[:, None]
        keep[rows, order[:, :max_influences]] = True
        M = np.where(keep, M, 0.0)
        s = M.sum(axis=1, keepdims=True)
        # sommet orphelin (ne devrait pas arriver) -> Root
        orphan = (s[:, 0] <= 1e-9)
        M[orphan, 0] = 1.0
        s = M.sum(axis=1, keepdims=True)
        M = M / s
        return names, M


# ---------------------------------------------------------------------------
# Poses (translations / rotations de bones en espace modèle Blender)
# Chaque pose : {bone: {"t": (dx, dy, dz), "r": (axis_xyz, angle_deg)}}
# Rotation appliquée autour de la tête du bone au repos.
# ---------------------------------------------------------------------------
def belly_pose(cr, dz, radial):
    """Translation verticale uniforme + écartement radial des bones de bord."""
    out = {}
    cx, cy = cr.belly_grid_center
    for name, h in cr.belly_bone_heads().items():
        ox = np.sign(round(h[0] - cx, 3))
        oy = np.sign(round(h[1] - cy, 3))
        out[name] = {"t": (float(ox * radial[0]), float(oy * radial[1]), float(dz)), "r": None}
    return out


def merge(*dicts):
    out = {}
    for d in dicts:
        out.update(d)
    return out


# ============================== MALLOW ======================================
def mallow():
    # Ours couché sur le dos, ventre vers le haut (plateau utile), tête vers +X,
    # pattes arrière vers -X. Empreinte collider 8x8 centrée en x = -1.0.
    body_c = (-1.0, 0.0, 2.03)
    prims = [
        # ventre ovale dodu, dessus aplati à z ~ 4.03 (léger surplus : le pied s'y enfonce)
        Prim("body", body_c, (4.6, 4.35, 2.0), eh=3.6, ev=5.0, owner="body"),
        Prim("head", (4.15, 0.0, 2.55), (1.85, 2.30, 2.15), owner="head"),
        Prim("muzzle", (3.55, 0.0, 4.25), (0.85, 1.10, 0.55), owner="head"),
        Prim("nose", (3.80, 0.0, 4.78), (0.28, 0.38, 0.15), owner="head"),
        Prim("eye_l", (4.62, 0.88, 4.40), (0.30, 0.26, 0.14), owner="head"),
        Prim("eye_r", (4.62, -0.88, 4.40), (0.30, 0.26, 0.14), owner="head"),
        Prim("ear_l", (5.05, 1.95, 3.55), (0.68, 0.92, 0.88), rot=(0, -10, 30), owner="head"),
        Prim("ear_r", (5.05, -1.95, 3.55), (0.68, 0.92, 0.88), rot=(0, -10, -30), owner="head"),
        # pattes avant levées aux coins avant de l'empreinte (coussinets vers le haut)
        Prim("arm_l", (1.75, 3.55, 2.55), (1.55, 1.25, 1.38), rot=(0, 0, 35), owner="arm_l"),
        Prim("arm_r", (1.75, -3.55, 2.55), (1.55, 1.25, 1.38), rot=(0, 0, -35), owner="arm_r"),
        # pattes arrière courtes aux coins arrière
        Prim("leg_l", (-4.35, 3.05, 2.30), (1.55, 1.30, 1.55), rot=(0, 0, -30), owner="leg_l"),
        Prim("leg_r", (-4.35, -3.05, 2.30), (1.55, 1.30, 1.55), rot=(0, 0, 30), owner="leg_r"),
    ]
    pm = {p.name: p for p in prims}
    star = star_polygon(-2.0, 0.0, 1.25, 0.55, rot_deg=0.0)

    def color_fn(P, N):
        n = len(P)
        C = np.tile(col("mallow_fabric"), (n, 1))
        p2 = P[:, :2]
        top = (N[:, 2] > 0.55) & (P[:, 2] > 3.0)
        on_body = pm["body"].value(P) <= 1.03
        # ventre ovale plus clair + feston caramel
        belly_e = ((P[:, 0] + 1.0) / 3.1) ** 2 + (P[:, 1] / 2.6) ** 2 <= 1.0
        C[top & on_body & belly_e] = col("mallow_belly")
        blanket = ellipse_blanket_stitch(p2, -1.0, 0.0, 3.1, 2.6)
        C[top & on_body & blanket] = col("stitch_caramel")
        # patch étoile cousu
        in_star = point_in_polygon(p2, star)
        C[top & in_star] = col("star_patch")
        st = polyline_stitch(p2, [np.array(s) * 1.0 for s in star], width=0.05, dash=0.26, closed=True)
        C[top & st] = col("stitch_navy")
        # couture latérale du corps (mi-hauteur)
        side = on_body & (np.abs(N[:, 2]) < 0.6) & (np.abs(P[:, 2] - 2.0) < 0.06)
        ang = np.arctan2(P[:, 1], P[:, 0] + 1.0)
        side &= np.mod(ang * 4.7 / 0.33, 1.0) < 0.55
        C[side] = col("stitch_caramel")
        # museau caramel, nez et bouche brodés
        mz = pm["muzzle"].value(P) <= 1.04
        C[mz] = col("caramel_light")
        nose_tri = point_in_polygon(p2, [(4.05, 0.0), (3.66, 0.36), (3.66, -0.36)])
        C[mz & (P[:, 2] > 4.55) & nose_tri] = col("nose_brown")
        C[pm["nose"].value(P) <= 1.05] = col("nose_brown")
        mouth = polyline_stitch(p2, [(3.66, 0.0), (3.22, 0.0)], width=0.05, dash=10, duty=1.0)
        mouth |= polyline_stitch(p2, [(3.22, 0.0), (3.12, 0.26), (3.20, 0.48)], width=0.05, dash=10, duty=1.0)
        mouth |= polyline_stitch(p2, [(3.22, 0.0), (3.12, -0.26), (3.20, -0.48)], width=0.05, dash=10, duty=1.0)
        C[mz & mouth & (N[:, 2] > 0.3)] = col("nose_brown")
        # yeux brodés
        C[(pm["eye_l"].value(P) <= 1.08) | (pm["eye_r"].value(P) <= 1.08)] = col("stitch_navy")
        # oreilles : intérieur caramel côté visage (+Z)
        for e in ("ear_l", "ear_r"):
            inner = (pm[e].value(P) <= 1.03) & (N[:, 2] > 0.35) & (pm["head"].value(P) > 1.02)
            C[inner] = col("caramel")
        # couture centrale de tête (du front vers le crâne)
        hs = (pm["head"].value(P) <= 1.03) & (N[:, 2] > 0.2)
        cseam = polyline_stitch(p2, [(4.95, 0.0), (5.95, 0.0)], width=0.05, dash=0.28)
        C[hs & cseam & ~mz] = col("stitch_caramel")
        # coussinets des pattes arrière (semelles vers -X) et pattes avant
        # coussinets caramel sur le dessus des quatre pattes levées
        for lb in ("leg_l", "leg_r", "arm_l", "arm_r"):
            pr = pm[lb]
            on = pr.value(P) <= 1.03
            d2 = (P[:, 0] - pr.center[0]) ** 2 + (P[:, 1] - pr.center[1]) ** 2
            C[on & (N[:, 2] > 0.5) & (d2 < 0.85 ** 2)] = col("caramel")
            # trois petits orteils brodés vers l'extérieur
            outward = np.array([pr.center[0] - body_c[0], pr.center[1]])
            outward /= np.linalg.norm(outward)
            for k in (-1, 0, 1):
                ang = math.atan2(outward[1], outward[0]) + k * 0.55
                tx = pr.center[0] + 1.05 * math.cos(ang)
                ty = pr.center[1] + 1.05 * math.sin(ang)
                toe = (P[:, 0] - tx) ** 2 + (P[:, 1] - ty) ** 2 < 0.24 ** 2
                C[on & (N[:, 2] > 0.3) & toe] = col("caramel")
        return C

    secondary = {
        "Head": (np.array([3.0, 0.0, 2.6]), "head"),
        "Arm_L": (np.array([1.2, 3.1, 2.4]), "arm_l"),
        "Arm_R": (np.array([1.2, -3.1, 2.4]), "arm_r"),
        "Leg_L": (np.array([-3.8, 2.6, 2.2]), "leg_l"),
        "Leg_R": (np.array([-3.8, -2.6, 2.2]), "leg_r"),
    }

    cr = Creature(
        asset_id="toy_plush_mallow", label="Mallow",
        size_studs=[12, 10, 5], collider={"shape": "box", "size_studs": [8, 8, 4], "walkable_top": [8, 8]},
        collider_center_xy=(-1.0, 0.0), prims=prims, secondary_bones=secondary,
        belly_grid_center=(-1.0, 0.0), belly_spacing=(3.0, 3.0), belly_top_z=4.0,
        behavior="stable", color_fn=color_fn, poses={},
    )
    # top = 4 : étirement 1.12 -> +0.48 ; compression 0.72 -> -1.12
    cr.poses = {
        "rest": {},
        "fall": merge(belly_pose(cr, 0.46, (-0.22, -0.22)), {
            "Head": {"t": (0.0, 0.0, 0.30), "r": ((0, 1, 0), -7.0)},
            "Arm_L": {"t": (0.0, 0.0, 0.18), "r": ((1, 0, 0), -12.0)},
            "Arm_R": {"t": (0.0, 0.0, 0.18), "r": ((1, 0, 0), 12.0)},
            "Leg_L": {"t": (0.0, 0.0, 0.10), "r": ((0, 1, 0), 10.0)},
            "Leg_R": {"t": (0.0, 0.0, 0.10), "r": ((0, 1, 0), 10.0)},
        }),
        "impact": merge(belly_pose(cr, -1.10, (0.62, 0.62)), {
            "Head": {"t": (0.30, 0.0, -0.35), "r": ((0, 1, 0), 9.0)},
            "Arm_L": {"t": (0.0, 0.38, -0.62), "r": ((1, 0, 0), 9.0)},
            "Arm_R": {"t": (0.0, -0.38, -0.62), "r": ((1, 0, 0), -9.0)},
            "Leg_L": {"t": (-0.28, 0.12, -0.45), "r": ((0, 1, 0), -8.0)},
            "Leg_R": {"t": (-0.28, -0.12, -0.45), "r": ((0, 1, 0), -8.0)},
        }),
        "rebound": merge(belly_pose(cr, 0.20, (-0.10, -0.10)), {
            "Head": {"t": (0.0, 0.0, 0.16), "r": ((0, 1, 0), -3.0)},
            "Arm_L": {"t": (0.0, 0.0, 0.10), "r": ((1, 0, 0), -5.0)},
            "Arm_R": {"t": (0.0, 0.0, 0.10), "r": ((1, 0, 0), 5.0)},
        }),
        # appui du joueur : dépression <= 0.25 stud (docs/02)
        "player_landing": merge(belly_pose(cr, -0.08, (0.0, 0.0)), {
            "Belly_11": {"t": (0.0, 0.0, -0.15), "r": None},
        }),
    }
    return cr


# ============================== LOPPY =======================================
def loppy():
    # Lapin couché sur le ventre, dos plat jouable à z ~ 4, grosse tête dressée vers +X,
    # une oreille droite (-Y) et une oreille pliée qui retombe (+Y), cuisses arrondies.
    prims = [
        Prim("body", (-0.95, 0.0, 2.03), (4.03, 3.80, 2.0), eh=4.5, ev=5.5, owner="body"),
        Prim("haunch_l", (-2.7, 3.22, 1.55), (1.95, 0.78, 1.45), owner="body"),
        Prim("haunch_r", (-2.7, -3.22, 1.55), (1.95, 0.78, 1.45), owner="body"),
        Prim("head", (3.78, 0.0, 4.12), (1.22, 1.80, 1.62), owner="head"),
        Prim("cheeks", (4.15, 0.0, 3.55), (0.85, 1.32, 0.78), owner="head"),
        Prim("nose", (4.90, 0.0, 3.85), (0.12, 0.24, 0.17), owner="head"),
        Prim("eye_l", (4.76, 0.85, 4.45), (0.14, 0.24, 0.27), owner="head"),
        Prim("eye_r", (4.76, -0.85, 4.45), (0.14, 0.24, 0.27), owner="head"),
        Prim("ear_up", (3.50, -0.75, 5.85), (0.42, 0.60, 1.18), rot=(-10, -10, 0), owner="ear_r"),
        # oreille pliée longue qui retombe le long de la joue (hors empreinte : x > 3.1)
        Prim("ear_fold_a", (3.55, 1.20, 5.70), (0.44, 0.66, 0.62), rot=(50, 0, 0), owner="ear_l"),
        Prim("ear_fold_b", (3.62, 2.12, 4.75), (0.42, 0.62, 1.05), rot=(18, 0, 0), owner="ear_l"),
        Prim("ear_fold_c", (3.70, 2.32, 3.55), (0.40, 0.58, 0.72), rot=(5, 0, 0), owner="ear_l"),
        Prim("foot_l", (-4.15, 2.45, 0.55), (0.85, 0.85, 0.55), owner="legs"),
        Prim("foot_r", (-4.15, -2.45, 0.55), (0.85, 0.85, 0.55), owner="legs"),
        Prim("paw_l", (3.25, 1.55, 0.55), (1.05, 0.70, 0.55), owner="legs"),
        Prim("paw_r", (3.25, -1.55, 0.55), (1.05, 0.70, 0.55), owner="legs"),
        Prim("tail", (-4.45, 0.0, 2.65), (0.48, 0.62, 0.62), owner="tail"),
    ]
    pm = {p.name: p for p in prims}

    def color_fn(P, N):
        n = len(P)
        C = np.tile(col("loppy_fabric"), (n, 1))
        p2 = P[:, :2]
        on_body = pm["body"].value(P) <= 1.03
        top = on_body & (N[:, 2] > 0.55) & (P[:, 2] > 3.0)
        # couture centrale du dos
        C[top & polyline_stitch(p2, [(-4.3, 0.0), (2.4, 0.0)], width=0.05, dash=0.3)] = col("stitch_navy")
        side = on_body & (np.abs(N[:, 2]) < 0.6) & (np.abs(P[:, 2] - 2.0) < 0.06)
        ang = np.arctan2(P[:, 1], P[:, 0] + 0.95)
        C[side & (np.mod(ang * 4.2 / 0.33, 1.0) < 0.55)] = col("stitch_navy")
        for f in ("foot_l", "foot_r", "paw_l", "paw_r"):
            C[pm[f].value(P) <= 1.04] = col("loppy_cream")
        C[pm["tail"].value(P) <= 1.04] = col("loppy_cream")
        C[pm["cheeks"].value(P) <= 1.03] = col("loppy_cream")
        # cuisses : contour cousu sur la face extérieure
        for hn in ("haunch_l", "haunch_r"):
            hp = pm[hn]
            q = hp.local(P)
            rr = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2)
            outer = (np.abs(N[:, 1]) > 0.55) & (hp.value(P) <= 1.04)
            ring = outer & (np.abs(rr - 0.78) < 0.045) & (np.mod(np.arctan2(q[:, 2], q[:, 0]) * 1.6 / 0.3, 1.0) < 0.55)
            C[ring] = col("stitch_navy")
        # moustaches brodées
        wh = (P[:, 0] > 4.6) & (N[:, 0] > 0.4) & (np.abs(P[:, 1]) > 0.35) & (np.abs(P[:, 1]) < 1.05)
        for zz, slope in ((3.72, 0.12), (3.56, -0.05)):
            C[wh & (np.abs(P[:, 2] - (zz + slope * (np.abs(P[:, 1]) - 0.35))) < 0.035)] = col("stitch_navy")
        C[pm["nose"].value(P) <= 1.15] = col("loppy_nose")
        C[(pm["eye_l"].value(P) <= 1.1) | (pm["eye_r"].value(P) <= 1.1)] = col("stitch_navy")
        # intérieur d'oreilles (face avant +X)
        for e in ("ear_up", "ear_fold_a", "ear_fold_b", "ear_fold_c"):
            inner = (pm[e].value(P) <= 1.03) & (N[:, 0] > 0.35) & (pm["head"].value(P) > 1.02)
            C[inner] = col("loppy_ear_inner")
        return C

    secondary = {
        "Head": (np.array([3.4, 0.0, 3.4]), "head"),
        "Ear_L": (np.array([3.55, 0.90, 5.3]), "ear_l"),
        "Ear_R": (np.array([3.55, -0.70, 5.0]), "ear_r"),
        "Feet": (np.array([0.0, 0.0, 0.5]), "legs"),
        "Tail": (np.array([-4.2, 0.0, 2.6]), "tail"),
    }
    cr = Creature(
        asset_id="toy_plush_loppy", label="Loppy",
        size_studs=[10, 8, 7], collider={"shape": "box", "size_studs": [8, 7, 4], "walkable_top": [8, 7]},
        collider_center_xy=(-1.0, 0.0), prims=prims, secondary_bones=secondary,
        belly_grid_center=(-0.95, 0.0), belly_spacing=(2.8, 2.6), belly_top_z=4.0,
        behavior="bounce", color_fn=color_fn, poses={},
    )
    cr.poses = {
        "rest": {},
        "fall": merge(belly_pose(cr, 0.46, (-0.18, -0.18)), {
            "Head": {"t": (0.0, 0.0, 0.32), "r": ((0, 1, 0), -5.0)},
            "Ear_L": {"t": (0.0, 0.0, 0.42), "r": ((1, 0, 0), -16.0)},
            "Ear_R": {"t": (0.0, 0.0, 0.42), "r": ((1, 0, 0), 14.0)},
            "Tail": {"t": (0.0, 0.0, 0.25), "r": None},
        }),
        "impact": merge(belly_pose(cr, -1.10, (0.55, 0.55)), {
            "Head": {"t": (0.22, 0.0, -0.95), "r": ((0, 1, 0), 5.0)},
            "Ear_L": {"t": (0.10, 0.10, -1.10), "r": ((1, 0, 0), 18.0)},
            "Ear_R": {"t": (0.10, -0.10, -1.05), "r": ((1, 0, 0), -15.0)},
            "Feet": {"t": (0.0, 0.0, 0.0), "r": None},
            "Tail": {"t": (-0.2, 0.0, -0.6), "r": None},
        }),
        "rebound": merge(belly_pose(cr, 0.22, (-0.08, -0.08)), {
            "Head": {"t": (0.0, 0.0, 0.18), "r": None},
            "Ear_L": {"t": (0.0, 0.0, 0.25), "r": ((1, 0, 0), -8.0)},
            "Ear_R": {"t": (0.0, 0.0, 0.25), "r": ((1, 0, 0), 6.0)},
        }),
        "player_landing": merge(belly_pose(cr, -0.08, (0.0, 0.0)), {
            "Belly_11": {"t": (0.0, 0.0, -0.15), "r": None},
        }),
    }
    return cr


# ============================== OCTO ========================================
def octo():
    # Pieuvre : tête large à sommet aplati (z ~ 4), bourrelet périphérique doux,
    # huit bras épais corail rayonnants (diagonales plus longues -> silhouette étoilée).
    prims = [Prim("head", (0.0, 0.0, 2.03), (4.55, 4.55, 2.0), eh=4.6, ev=4.5, owner="body"),
             Prim("rim", (0.0, 0.0, 1.05), (4.85, 4.85, 1.0), eh=3.0, ev=2.2, owner="body"),
             Prim("eye_l", (-1.35, 4.42, 2.45), (0.80, 0.30, 0.95), owner="body"),
             Prim("eye_r", (1.35, 4.42, 2.45), (0.80, 0.30, 0.95), owner="body")]
    arm_groups = {"Arms_N": [], "Arms_E": [], "Arms_S": [], "Arms_W": []}
    for k in range(8):
        a = math.radians(45 * k)
        diag = k % 2 == 1
        r_c = 5.2 if diag else 4.45
        rx = 2.0 if diag else 1.55
        cx, cy = r_c * math.cos(a), r_c * math.sin(a)
        deg = math.degrees(a)
        quad = ["Arms_E", "Arms_N", "Arms_N", "Arms_W", "Arms_W", "Arms_S", "Arms_S", "Arms_E"][k]
        owner = quad.lower()
        prims.append(Prim(f"arm_{k}", (cx, cy, 0.72), (rx, 1.05, 0.72), rot=(0, 0, deg), owner=owner))
        # bout de bras enroulé ; les quatre diagonales se relèvent (bras « qui saluent »)
        tr = r_c + rx - (0.35 if diag else 0.62)
        prims.append(Prim(f"tip_{k}", (tr * math.cos(a), tr * math.sin(a), 1.05), (0.55, 0.62, 0.55), owner=owner))
        if diag:
            for j, (rr, zz, rz) in enumerate(((6.05, 1.75, 0.95), (6.15, 3.10, 0.95), (5.85, 4.20, 0.60))):
                prims.append(Prim(f"curl_{k}_{j}", (rr * math.cos(a), rr * math.sin(a), zz), (0.58, 0.58, rz), owner=owner))
        arm_groups[quad].append(k)
    pm = {p.name: p for p in prims}

    def color_fn(P, N):
        n = len(P)
        C = np.tile(col("octo_fabric"), (n, 1))
        p2 = P[:, :2]
        under = (N[:, 2] < -0.3) | (P[:, 2] < 0.35)
        C[under] = col("octo_under")
        for k in range(8):
            pr = pm[f"arm_{k}"]
            on = pr.value(P) <= 1.04
            C[on] = col("octo_under")
            C[pm[f"tip_{k}"].value(P) <= 1.04] = col("octo_under")
            for j in range(3):
                if f"curl_{k}_{j}" in pm:
                    C[pm[f"curl_{k}_{j}"].value(P) <= 1.04] = col("octo_under")
            # ventouses brodées sur le dessus des bras
            loc = pr.local(P) * pr.radii
            suck = on & (N[:, 2] > 0.4)
            dots = np.zeros(n, dtype=bool)
            for xx in (-0.3, 0.45, 1.15):
                dots |= (loc[:, 0] - xx) ** 2 + loc[:, 1] ** 2 < 0.15 ** 2
            C[suck & dots] = col("octo_sucker")
        top = (N[:, 2] > 0.6) & (P[:, 2] > 3.2)
        # couture en croix douce sur le sommet (repère de quartiers)
        C[top & polyline_stitch(p2, [(-3.6, 0.0), (3.6, 0.0)], width=0.05, dash=0.3)] = col("stitch_navy")
        C[top & polyline_stitch(p2, [(0.0, -3.6), (0.0, 3.6)], width=0.05, dash=0.3)] = col("stitch_navy")
        # yeux en couture : blanc crème + pupille navy + paupière brodée
        for e, ex in (("eye_l", -1.25), ("eye_r", 1.25)):
            on = pm[e].value(P) <= 1.06
            C[on] = col("octo_eye_white")
            pup = on & ((P[:, 0] - ex) ** 2 + (P[:, 2] - 2.30) ** 2 < 0.42 ** 2)
            C[pup] = col("stitch_navy")
        # bouche brodée
        mouth = (P[:, 1] > 4.2) & (N[:, 1] > 0.5) & (np.abs(P[:, 2] - (1.35 + 0.35 * (P[:, 0] / 0.6) ** 2)) < 0.07) & (np.abs(P[:, 0]) < 0.6)
        C[mouth] = col("stitch_navy")
        return C

    secondary = {}
    heads = {"Arms_N": (0.0, 4.0, 0.72), "Arms_E": (4.0, 0.0, 0.72), "Arms_S": (0.0, -4.0, 0.72), "Arms_W": (-4.0, 0.0, 0.72)}
    for q, h in heads.items():
        secondary[q] = (np.array(h), q.lower())
    cr = Creature(
        asset_id="toy_plush_octo", label="Octo",
        size_studs=[12, 12, 5], collider={"shape": "box", "size_studs": [8, 8, 4], "walkable_top": [8, 8]},
        collider_center_xy=(0.0, 0.0), prims=prims, secondary_bones=secondary,
        belly_grid_center=(0.0, 0.0), belly_spacing=(3.0, 3.0), belly_top_z=4.0,
        behavior="stable", color_fn=color_fn, poses={},
    )
    spread = {"Arms_N": (0, 1), "Arms_E": (1, 0), "Arms_S": (0, -1), "Arms_W": (-1, 0)}

    def arms(d, dz, ang):
        out = {}
        for q, (ux, uy) in spread.items():
            axis = (-uy, ux, 0)  # rotation qui relève/abaisse le bout des bras
            out[q] = {"t": (ux * d, uy * d, dz), "r": (axis, ang)}
        return out

    cr.poses = {
        "rest": {},
        "fall": merge(belly_pose(cr, 0.46, (-0.2, -0.2)), arms(-0.15, 0.25, -14.0)),
        "impact": merge(belly_pose(cr, -1.10, (0.62, 0.62)), arms(0.65, -0.10, 6.0)),
        "rebound": merge(belly_pose(cr, 0.20, (-0.1, -0.1)), arms(-0.05, 0.08, -5.0)),
        "player_landing": merge(belly_pose(cr, -0.08, (0.0, 0.0)), {"Belly_11": {"t": (0.0, 0.0, -0.15), "r": None}}),
    }
    return cr


CREATURES = {"mallow": mallow, "loppy": loppy, "octo": octo}

# Limites de config/runtime.json (deformation) : contrôlées par verify_exports.py
RUNTIME_LIMITS = {
    "fall_stretch_y_max": 1.12,
    "impact_scale_y_min": 0.72,
    "impact_scale_xz_max": 1.18,
    "plush_lattice_bones": 9,
    "secondary_bones_max": 6,
    "walkable_top_alignment_tolerance_studs": 0.25,
}
