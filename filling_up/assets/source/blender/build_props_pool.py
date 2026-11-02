"""Construit la famille « Piscine Gonflable » : 8 props jouables (+ variante dégonflée du matelas)
et la machine signature (La Pompe à Bouées).

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/build_props_pool.py [id ...]
Variable POOL_IMPORT_DIR : dossier d'export alternatif (contrôle de déterminisme : ni .blend ni json).

Sorties :
  assets/source/models/pool/pool_props.blend (LOD0 + LOD1, atlas empaqueté)
  assets/source/models/pool/textures/pool_atlas_1024.png (+ _rough_1024 : G rugosité, B métal)
  assets/source/models/pool/build_info.json, collision_pool.json
  assets/import/models/<id>.glb, <id>_lod1.glb, <id>.fbx

Contrat : spécifications SPECS ci-dessous (brief T03 « Piscine Gonflable » ; la famille n'existe pas
encore dans config/rooms.json). Unités/axes : décision 0003 (1 BU = 1 stud ; X largeur, Y profondeur,
Z hauteur ; avant Roblox -Z = +Y Blender). Pivot = origine = centre du bas du collider de jeu.
Construction déterministe (graines fixes) ; aucun asset tiers.

Principe artistique : vinyle gonflable brillant. Corps = coussins superelliptiques à flanc bombé,
soudure HF horizontale et sillon de soudure autour du pont plat ; têtes, ailes, queues = panneaux
gonflés soudés au bord (deux feuilles + collerette), comme les vraies bouées. Les têtes tiennent dans
la bande avant hors du rectangle praticable (enveloppe du brief conservée).
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import pool_atlas as atlas  # noqa: E402
import pool_kit as K  # noqa: E402

SEED = 20261102
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MODEL_DIR = os.path.join(ROOT, "assets", "source", "models", "pool")
TEX_DIR = os.path.join(MODEL_DIR, "textures")
IMPORT_DIR = os.environ.get("POOL_IMPORT_DIR") or os.path.join(ROOT, "assets", "import", "models")
MACHINE_ID = "machine_pool_pump"
DEFLATED_ID = "pool_air_mattress_deflated"

# -------------------------------------------------------------------------------------
# Spécifications (W x D x H studs ; H = haut). envelope = dimensions visées du maillage.
# brief_envelope = valeur du brief si elle diffère (contradiction documentée dans `envelope_note`).
# -------------------------------------------------------------------------------------
SPECS = {
    "pool_inflatable_duck": dict(
        name="Canard gonflable géant", category="room_prop", behavior="stable", behavior_params={},
        envelope=[12, 10, 8], collider=[9, 8, 4], walkable=[9, 8],
        visual="Canard jaune à chevaucher : pont-selle plat matelassé, tête et cou soudés à l'avant (-Z) hors du "
               "plateau, bec orange, grands yeux imprimés, ailes bombées sur les flancs, petite queue relevée.",
        note="Collider 9 x 8 x 4 (mise à jour orchestrateur : remplace le carton du tutoriel)."),
    "pool_flamingo_float": dict(
        name="Bouée flamant rose", category="room_prop", behavior="bounce", behavior_params={"profile": "springy"},
        envelope=[12, 10, 10], collider=[9, 8, 3], walkable=[9, 8],
        visual="Île flottante flamant rose : pont plat à vagues, long cou en S et tête à bec noir à l'avant, "
               "ailes repliées festonnées, plumes de queue."),
    "pool_beach_ball": dict(
        name="Ballon de plage écrasé", category="room_prop", behavior="bounce", behavior_params={},
        envelope=[7, 7, 4], brief_envelope=[7, 7, 5], collider=[7, 7, 4], walkable=[7, 7],
        visual="Ballon de plage écrasé en coussin : six fuseaux (blanc, rouge, jaune, bleu, vert, orange), "
               "calottes blanches, valve et autocollant soleil à l'avant ; dessus aplati.",
        envelope_note="Brief 7 x 7 x 5 incompatible : walkable 7 x 7 = toute l'emprise et rien ne doit dépasser "
                      "4,05 ; hauteur ramenée à 4."),
    "pool_donut_ring": dict(
        name="Bouée donut", category="room_prop", behavior="bounce", behavior_params={},
        envelope=[9, 9, 3], collider=[8, 8, 3], walkable=[8, 8],
        visual="Bouée donut glaçage rose à vermicelles et coulures, pâte dorée, frimousse sur la face avant ; "
               "trou couvert d'un filet trampoline blanc tendu au niveau du pont."),
    "pool_unicorn_float": dict(
        name="Licorne gonflable", category="room_prop", behavior="stable", behavior_params={},
        envelope=[14, 9, 10], collider=[12, 8, 4], walkable=[12, 8],
        visual="Licorne blanche nacrée : pont plat arc-en-ciel, tête de profil soudée à l'avant (-Z), crinière "
               "arc-en-ciel le long du cou, corne spirale dorée, queue arc-en-ciel, sabots dorés."),
    "pool_cooler": dict(
        name="Glacière rigolote", category="room_prop", behavior="stable", behavior_params={},
        envelope=[10, 7, 5], brief_envelope=[10, 7, 6], collider=[10, 7, 5], walkable=[10, 7],
        visual="Glacière bleue à couvercle blanc plat, grand sourire, langue tirée et yeux ronds à l'avant, "
               "poignées latérales sous le couvercle, glaçons imprimés.",
        envelope_note="Brief 10 x 7 x 6 incompatible : walkable 10 x 7 = toute l'emprise, collider 5 ; "
                      "hauteur ramenée à 5."),
    "pool_croc_float": dict(
        name="Crocodile gonflable", category="room_prop", behavior="moving",
        behavior_params={"path": "linear_back_and_forth"},
        envelope=[16, 8, 6], collider=[14, 7, 3], walkable=[14, 7],
        visual="Crocodile vert : dos plat à écailles imprimées, grosse tête de profil à l'avant (-Z) avec dents "
               "dessinées au feutre et deux yeux globuleux qui louchent, ventre vert clair, pattes, queue relevée."),
    "pool_air_mattress": dict(
        name="Matelas qui se dégonfle", category="room_prop", behavior="temporary",
        behavior_params={"effect": "deflate_after_contact", "collapse_visual": DEFLATED_ID},
        envelope=[12, 7, 2], collider=[12, 7, 2], walkable=[12, 7],
        visual="Matelas pneumatique à boudins alternés jaune/bleu, oreiller à vagues au bout -X, valve et "
               "étiquette à l'avant."),
    DEFLATED_ID: dict(
        name="Matelas dégonflé (visuel d'effondrement)", category="room_prop", behavior="temporary_collapsed",
        behavior_params={"variant_of": "pool_air_mattress"},
        envelope=[12, 7, 0.6], collider=None, walkable=None,
        visual="Même matelas affaissé et froissé, oreiller encore à moitié gonflé ; visuel seulement."),
    MACHINE_ID: dict(
        name="La Pompe à Bouées", category="signature_machine", behavior=None, behavior_params={},
        envelope=[22, 16, 18], collider=None, walkable=None,
        visual="Pompe à pied géante jaune : soufflet accordéon à visage, pédale à empreinte, manomètre à aiguille "
               "dans le rouge, deux tuyaux (l'un gonfle une bouée canard à moitié gonflée), pieds caoutchouc."),
}


def new_asset(pid, lod):
    return K.Asset(pid, tuple(float(v) for v in SPECS[pid]["envelope"]), lod)


def L(q, hi, lo):
    return hi if q.lod == 0 else lo


def split(pred, a, b):
    return K.r_if(pred, a, b)


def pal(cell, z0=0.0, z1=1.0):
    return K.r_pal(cell, z0, z1)


def PH(q):
    return K.PILLOW_HI if q.lod == 0 else K.PILLOW_L1


def PL(q):
    return K.PILLOW_LO if q.lod == 0 else K.PILLOW_L2


# =====================================================================================
# Corps de bouée commun
# =====================================================================================
def float_rings(hw, hd, H, mx, my, q, crest=(0.26, 0.26), puff=None, n_mid=5.0, n_bot=3.6, n_top=10.0,
                seam=True):
    """Anneaux (a, b, n, z) d'un coussin gonflé dont le pont plat (z = H) couvre hw x hd.

    mx, my : débord max du flanc au-delà du rectangle praticable ; crest : débord du bourrelet de
    soudure du pont. Ordre : fond -> flanc bombé -> soudure médiane -> arrondi -> bourrelet -> sillon -> pont."""
    P = puff if puff is not None else min(0.75, 0.28 * H)
    cx_, cy_ = crest
    dx_, dy_ = min(0.1, cx_ * 0.4), min(0.1, cy_ * 0.4)
    gx, gy = (cx_ + dx_) / 2, (cy_ + dy_) / 2
    rv = min(0.32 * H, 1.1)
    rings = []

    def ring(ix, iy, n, z):
        rings.append((hw + mx - ix, hd + my - iy, n, z))
    bottom = [(0.0, 1.0), (0.05, 0.62), (0.16, 0.24), (0.3, 0.05)] if q.lod == 0 else [(0.0, 1.0), (0.15, 0.25)]
    for fz, fi in bottom:
        ring(P * fi, P * fi, n_bot + (n_mid - n_bot) * fz / 0.3, fz * H)
    if seam and q.lod == 0:
        ring(0.0, 0.0, n_mid, 0.47 * H)
        ring(0.07, 0.07, n_mid, 0.5 * H)
        ring(0.0, 0.0, n_mid, 0.53 * H)
    else:
        ring(0.0, 0.0, n_mid, 0.5 * H)
    zr = H - rv
    if zr > 0.56 * H:
        ring(0.01, 0.01, n_mid, zr)
    m = 3 if q.lod == 0 else 1
    for k in range(1, m + 1):
        th = (math.pi / 2) * k / (m + 1)
        n = n_mid + (n_top - n_mid) * k / (m + 1)
        ring((mx - cx_) * (1 - math.cos(th)), (my - cy_) * (1 - math.cos(th)), n, zr + rv * math.sin(th))
    rings.append((hw + cx_, hd + cy_, n_top, H))
    if q.lod == 0:
        rings.append((hw + gx, hd + gy, n_top, H - 0.07))
    rings.append((hw + dx_, hd + dy_, n_top, H))
    return rings


def float_body(A, hw, hd, H, mx, my, top_tile, side_tile, N, **kw):
    q = A.q
    rings = float_rings(hw, hd, H, mx, my, q, **kw)
    body = K.blob(rings, N)
    a, b = rings[-1][0], rings[-1][1]
    side = K.r_box(side_tile, (-hw - mx, hw + mx, -hd - my, hd + my, 0.0, H))
    A.add(body, split(lambda c, n: n.z > 0.9 and c.z > H - 0.03,
                      K.r_const(K.m_top(top_tile, -a, a, -b, b)), side))
    return rings


def outline_smooth(points, per_seg, closed=True):
    """Contour 2D lissé (Catmull-Rom fermé)."""
    P = [Vector((p[0], p[1], 0)) for p in points]
    n = len(P)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = P[(i - 1) % n], P[i], P[(i + 1) % n], P[(i + 2) % n]
        for k in range(per_seg):
            t = k / per_seg
            v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                       (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
            out.append((v.x, v.y))
    return out


def ellipse2d(cx, cy, rx, ry, n, a0=0.0):
    return [(cx + rx * math.cos(a0 + 2 * math.pi * i / n), cy + ry * math.sin(a0 + 2 * math.pi * i / n))
            for i in range(n)]


def face_rule(tile, origin, su, sv, other, front=True, back_tile=None):
    """Panneau plan XZ : décor sur la face +Y (et miroir sur -Y si back_tile)."""
    o = Vector(origin)
    mf = K.m_plane(tile, o, (-1, 0, 0), (0, 0, 1), su, sv)
    mb = K.m_plane(back_tile, o, (-1, 0, 0), (0, 0, 1), su, sv) if back_tile else None

    def rule(c, n):
        if n.y > 0.3:
            return mf
        if mb is not None and n.y < -0.3:
            return mb
        return other(c, n)
    return rule


# =====================================================================================
# 1. Canard gonflable géant — enveloppe 12 x 10 x 8, collider 9 x 8 x 4
# =====================================================================================
def duck(lod):
    A = new_asset("pool_inflatable_duck", lod)
    q = A.q
    H, hw, hd = 4.0, 4.5, 4.0
    float_body(A, hw, hd, H, 0.75, 0.5, "duck_top", "s_duck", L(q, 40, 20))
    yel = pal("yellow", 0, 8)
    # tête + cou : panneau soudé face avant, plan XZ, y = 4.1 .. 4.98
    hc, hr = (0.0, 6.17), 1.8
    pts = []
    na = L(q, 18, 8)
    for i in range(na + 1):
        a = math.radians(-60 + (300 * i / na))
        pts.append((hc[0] + hr * 1.08 * math.cos(a), hc[1] + hr * math.sin(a)))
    pts += [(-0.92, 4.15), (-1.3, 3.5), (-1.75, 2.95), (0.0, 2.8), (1.75, 2.95), (1.3, 3.5), (0.92, 4.15)]
    head = K.pillow(pts, "xz", 4.54, 0.44, center=(0.0, 5.6), profile=PH(q))
    A.add(head, face_rule("duck_face", (0, 5.0, 6.2), 3.9, 3.9, yel))
    # bec : panneau plat (plan XY) qui dépasse du visage, mâchoire en sourire
    bill = [(1.25, 4.5), (1.38, 4.98), (1.1, 5.36), (0.55, 5.5), (0.0, 5.52), (-0.55, 5.5), (-1.1, 5.36),
            (-1.38, 4.98), (-1.25, 4.5), (0.0, 4.4)]
    if q.lod == 0:
        bill = outline_smooth(bill, 2)
    A.add(K.pillow(bill, "xy", 5.5, 0.22, center=(0.0, 4.95), profile=PL(q)), pal("orange", 5.1, 5.9))
    if q.lod == 0:
        jaw = outline_smooth([(0.95, 4.55), (0.88, 5.12), (0.0, 5.26), (-0.88, 5.12), (-0.95, 4.55)], 2)
        A.add(K.pillow(jaw, "xy", 5.17, 0.12, center=(0.0, 4.85), profile=K.PILLOW_LO), pal("orange_dark", 4.9, 5.4))
    # ailes bombées (plan YZ) sur les flancs, pointe relevée vers l'arrière
    wing = [(2.6, 2.3), (2.2, 3.15), (1.0, 3.55), (-0.8, 3.6), (-2.4, 3.5), (-3.7, 3.95), (-3.35, 2.95),
            (-2.6, 2.1), (-1.6, 1.55), (-0.5, 1.35), (0.6, 1.3), (1.8, 1.55)]
    wing = outline_smooth(wing, 2) if q.lod == 0 else wing[::2]
    for sx in (-1, 1):
        w = K.pillow([(y, z) for y, z in wing], "yz", sx * 5.55, 0.45, center=(-0.3, 2.5), profile=PL(q))
        A.add(w, pal("yellow_dark", 0, 8))
    # petite queue relevée (plan YZ) à l'arrière, hors plateau (y < -4)
    tail = [(-4.04, 3.4), (-4.06, 4.2), (-4.2, 4.75), (-4.42, 5.15), (-4.5, 4.6), (-4.5, 3.4)]
    tail = outline_smooth(tail, 2) if q.lod == 0 else tail
    A.add(K.pillow(tail, "yz", 0.0, 0.42, center=(-4.3, 4.0), profile=PL(q)), pal("yellow_dark", 0, 8))
    return A


# =====================================================================================
# 2. Bouée flamant rose — enveloppe 12 x 10 x 10, collider 9 x 8 x 3
# =====================================================================================
def flamingo(lod):
    A = new_asset("pool_flamingo_float", lod)
    q = A.q
    H, hw, hd = 3.0, 4.5, 4.0
    float_body(A, hw, hd, H, 0.75, 0.48, "flamingo_top", "s_pink", L(q, 40, 20))
    pk = pal("pink", 0, 10)
    # ailes repliées festonnées (plan YZ)
    wing = [(2.4, 1.9), (1.9, 2.75), (0.6, 3.15), (-1.2, 3.2), (-2.6, 3.3), (-3.7, 3.85), (-3.6, 3.0),
            (-3.0, 2.2), (-2.2, 1.75), (-1.2, 1.25), (0.0, 1.05), (1.3, 1.25)]
    wing = outline_smooth(wing, 2) if q.lod == 0 else wing[::2]
    for sx in (-1, 1):
        A.add(K.pillow(wing, "yz", sx * 5.55, 0.45, center=(-0.4, 2.2), profile=PL(q)), pal("pink_light", 0, 4))
    # cou en S (plan XZ, y = 4.62) : tube effilé
    ny = 4.62
    ctrl = [(0.0, ny, 1.4), (0.2, ny, 3.0), (-0.95, ny, 4.6), (-0.85, ny, 6.2), (0.3, ny, 7.3), (0.7, ny, 8.2),
            (0.3, ny, 8.95)]
    path = K.catmull(ctrl, L(q, 3, 2))
    A.add(K.tube(path, lambda t: 0.56 - 0.16 * t, L(q, 10, 6), up=(0, 1, 0)), pk)
    # tête
    A.add(K.ellipsoid((0.45, ny, 9.2), 0.98, 0.52, 0.76, L(q, 14, 8), L(q, 8, 4)), pk)
    # bec coudé vers +X et le bas : base blanche, pointe noire
    bp = K.catmull([(1.15, ny, 9.32), (1.85, ny, 9.18), (2.25, ny, 8.75), (2.35, ny, 8.3)], L(q, 3, 2))
    beak = K.tube(bp, lambda t: 0.38 * (1 - 0.7 * t), L(q, 8, 5), up=(0, 1, 0))
    A.add(beak, split(lambda c, n: c.z < 8.95, pal("black", 8, 10), pal("white", 8, 10)))
    # oeil (disque imprimé) côté avant +Y
    eye = K.lathe([(0.3, 0.0), (0.3, 0.04), (0.22, 0.08), (0.0, 0.1)], L(q, 12, 6))
    K.transform(eye, Matrix.Rotation(math.radians(-90), 4, "X"))
    K.move(eye, (0.62, ny + 0.43, 9.38))
    A.add(eye, K.r_const(K.m_plane("eye", (0.62, ny + 0.6, 9.38), (-1, 0, 0), (0, 0, 1), 0.62, 0.62)))
    # plumes de queue (plan YZ) à l'arrière, hors plateau
    tail = [(-4.05, 2.4), (-4.2, 3.2), (-4.5, 3.75), (-4.75, 3.9), (-4.85, 3.3), (-4.7, 2.6), (-4.45, 2.2)]
    tail = outline_smooth(tail, 2) if q.lod == 0 else tail
    for dx in ((-0.55, 0.0, 0.55) if q.lod == 0 else (0.0,)):
        A.add(K.pillow(tail, "yz", dx, 0.24, center=(-4.45, 3.0), profile=PL(q)), pal("pink_dark", 0, 4))
    return A


# =====================================================================================
# 3. Ballon de plage écrasé — 7 x 7 x 4 (dessus = collider)
# =====================================================================================
def beach_ball(lod):
    A = new_asset("pool_beach_ball", lod)
    q = A.q
    rings = [(1.75, 1.75, 2.3, 0.0), (2.6, 2.6, 2.5, 0.16), (3.1, 3.1, 2.8, 0.52), (3.38, 3.38, 3.2, 1.1),
             (3.5, 3.5, 3.9, 1.9), (3.5, 3.5, 5.0, 2.7), (3.48, 3.48, 7.5, 3.4), (3.45, 3.45, 12.0, 3.82),
             (3.43, 3.43, 16.0, 4.0)]
    if q.lod:
        rings = [rings[0], rings[2], rings[4], rings[5], rings[7], rings[8]]
    body = K.blob(rings, L(q, 48, 24))
    top = K.r_const(K.m_top("ball_top", -3.5, 3.5, -3.5, 3.5))
    A.add(body, split(lambda c, n: n.z > 0.55 and c.z > 3.7, top,
                      split(lambda c, n: n.z < -0.9, pal("white", 0, 4), K.r_angle("s_ball", 0, 0, 0.0, 4.0))))
    # valve (avant, bas du flanc) + autocollant soleil
    v = K.lathe([(0.26, 0.0), (0.26, 0.05), (0.13, 0.08), (0.13, 0.13), (0.0, 0.14)], L(q, 12, 6))
    K.transform(v, Matrix.Rotation(math.radians(-90 + 10), 4, "X"))
    K.move(v, (1.15, 3.36, 1.3))
    A.add(v, pal("white", 0, 4))
    if q.detail:
        b = K.lathe([(0.55, 0.0), (0.55, 0.02), (0.0, 0.025)], 16)
        K.transform(b, Matrix.Rotation(math.radians(-90), 4, "X"))
        K.move(b, (-1.0, 3.49, 2.35))
        A.add(b, K.r_const(K.m_plane("badge_sun", (-1.0, 3.5, 2.35), (-1, 0, 0), (0, 0, 1), 1.1, 1.1)))
    return A


# =====================================================================================
# 4. Bouée donut — 9 x 9 x 3, collider 8 x 8 x 3, filet trampoline au niveau du pont
# =====================================================================================
def donut(lod):
    A = new_asset("pool_donut_ring", lod)
    q = A.q
    hr = atlas.DONUT_HOLE_R
    rings = [(3.7, 3.7, 3.0, 0.0), (4.1, 4.1, 3.5, 0.18), (4.38, 4.38, 4.0, 0.6), (4.5, 4.5, 4.6, 1.35),
             (4.43, 4.43, 5.4, 2.1), (4.31, 4.31, 7.0, 2.6), (4.22, 4.22, 8.5, 2.86), (4.15, 4.15, 9.5, 2.98),
             (4.12, 4.12, 10.0, 3.0), (hr + 0.32, hr + 0.32, 2.0, 3.0), (hr + 0.12, hr + 0.12, 2.0, 2.96),
             (hr, hr, 2.0, 2.89), (hr - 0.06, hr - 0.06, 2.0, 2.86)]
    if q.lod:
        rings = [rings[0], rings[2], rings[3], rings[5], rings[7], rings[8], rings[9], rings[11], rings[12]]
    body = K.blob(rings, L(q, 48, 24))
    top = K.r_const(K.m_top("donut_top", -4.25, 4.25, -4.25, 4.25))
    A.add(body, split(lambda c, n: n.z > 0.5 and c.z > 2.75, top,
                      split(lambda c, n: n.z < -0.9, pal("dough", 0, 3), K.r_angle("s_donut", 0, 0, 0.0, 3.0))))
    # frimousse sur la face avant (bande qui épouse le flanc)
    if True:
        zs = [0.45 + 1.95 * k / L(q, 6, 2) for k in range(L(q, 6, 2) + 1)]

        def front_y(z):
            for (a0, _b0, _n0, z0), (a1, _b1, _n1, z1) in zip(rings[:-1], rings[1:]):
                if z0 <= z <= z1 and z1 > z0:
                    return a0 + (a1 - a0) * (z - z0) / (z1 - z0)
            return rings[0][0]
        prof = [(front_y(z), z) for z in zs]
        strip = K.wrap_strip(prof, "yz", -2.1, 2.1, 0.02, (0.0, 1.5))
        A.add(strip, split(lambda c, n: n.y > 0.4,
                           K.r_const(K.m_plane("donut_face", (0, 4.5, 1.45), (-1, 0, 0), (0, 0, 1), 4.2, 2.1)),
                           pal("dough", 0, 3)))
    # liseré du filet (cordon tendu)
    path = [(hr * math.cos(2 * math.pi * i / L(q, 32, 12)), hr * math.sin(2 * math.pi * i / L(q, 32, 12)), 2.9)
            for i in range(L(q, 32, 12))]
    A.add(K.tube(path, 0.065, L(q, 6, 4), closed=True), pal("pool", 2.5, 3.0))
    return A


# =====================================================================================
# 5. Licorne gonflable — enveloppe 14 x 9 x 10, collider 12 x 8 x 4
# =====================================================================================
def unicorn(lod):
    A = new_asset("pool_unicorn_float", lod)
    q = A.q
    H, hw, hd = 4.0, 6.0, 4.0
    float_body(A, hw, hd, H, 0.42, 0.18, "unicorn_top", "s_pearl", L(q, 36, 20), crest=(0.26, 0.13))
    wh = pal("pearl", 0, 10)
    hy, ht = 4.5, 0.42
    head = [(5.25, 2.9), (5.15, 4.6), (5.45, 5.95), (6.3, 6.35), (6.95, 6.85), (7.02, 7.5), (6.45, 7.95),
            (5.5, 8.6), (5.0, 9.15), (4.35, 9.35), (3.65, 8.8), (3.05, 7.0), (2.75, 5.0), (2.55, 2.9)]
    head = outline_smooth(head, L(q, 2, 1))
    A.add(K.pillow(head, "xz", hy, ht, center=(4.6, 6.6), profile=PH(q)),
          face_rule("unicorn_face", (5.0, hy, 7.5), 4.2, 4.2, wh, back_tile="unicorn_face"))
    # oreilles
    ear = [(4.45, 9.0), (4.75, 9.85), (5.05, 9.05)]
    A.add(K.pillow(ear, "xz", hy, 0.22, center=(4.75, 9.25), profile=PL(q)), pal("pink_light", 8, 10))
    # corne spirale dorée
    nring = L(q, 7, 3)
    prof = []
    for k in range(nring + 1):
        t = k / nring
        r = 0.36 * (1 - t) + 0.03
        prof.append((r * (1.0 if k % 2 == 0 else 0.84) if q.lod == 0 else r, 1.55 * t))
    prof.append((0.0, 1.62))
    horn = K.lathe(prof, L(q, 8, 5))
    if q.lod == 0:
        for v in horn.verts:  # torsade
            a = v.co.z * 2.6
            x, y = v.co.x, v.co.y
            v.co.x, v.co.y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
    K.transform(horn, Matrix.Rotation(math.radians(24), 4, "Y"))
    K.move(horn, (5.45, hy, 8.5))
    A.add(horn, pal("gold", 8, 10))
    # crinière arc-en-ciel (lobes soudés le long de la nuque)
    cols = ["red", "orange", "yellow", "mint", "pool", "lilac"]
    lobes = [(4.05, 9.3, 0.62), (3.4, 8.65, 0.66), (2.95, 7.75, 0.68), (2.65, 6.75, 0.66), (2.45, 5.7, 0.62),
             (2.35, 4.7, 0.58)]
    if q.lod:
        lobes = lobes[::2]
    for i, (x, z, r) in enumerate(lobes):
        lob = ellipse2d(x, z, r, r * 1.05, L(q, 8, 6), a0=0.3)
        A.add(K.pillow(lob, "xz", hy, ht + 0.04, center=(x, z), profile=PL(q)),
              pal(cols[i if q.lod == 0 else i * 2], 0, 10))
    # queue arc-en-ciel (bout -X, côté arrière)
    tl = [(-6.53, 3.35, 0.47), (-6.55, 4.05, 0.47), (-6.5, 4.72, 0.44), (-6.48, 5.32, 0.4)]  # x + r <= -6.05
    if q.lod:
        tl = tl[::2]
    for i, (x, z, r) in enumerate(tl):
        lob = ellipse2d(x, z, r, r * 1.1, L(q, 8, 6), a0=0.3)
        A.add(K.pillow(lob, "xz", -1.6, 0.38, center=(x, z), profile=PL(q)), pal(cols[(i + 1) % 6], 0, 10))
    # pattes courtes à sabots dorés (débordent en X)
    for sx in (-1, 1):
        for sy in (-2.3, 2.3):
            if sx < 0 and sy < 0:
                continue  # emplacement de la queue
            leg = K.ellipsoid((sx * 6.35, sy, 1.3), 0.5, 0.48, 0.62, L(q, 8, 6), L(q, 4, 3))
            A.add(leg, wh)
            if q.lod:
                continue
            hoof = K.lathe([(0.42, 0.0), (0.42, 0.18), (0.36, 0.22), (0.0, 0.22)], 8)
            K.transform(hoof, Matrix.Rotation(math.radians(90 * sx), 4, "Y"))
            K.move(hoof, (sx * 6.78, sy, 1.2))
            A.add(hoof, pal("gold", 0, 10))
    return A


# =====================================================================================
# 6. Glacière rigolote — 10 x 7 x 5
# =====================================================================================
def cooler(lod):
    A = new_asset("pool_cooler", lod)
    q = A.q
    lid = K.slab(5.0, 3.5, 4.2, 5.0, 0.6, 0.1, 0.14, q, min_corner=2)
    A.add(lid, split(K.r_top_faces(4.95, 0.8), K.r_const(K.m_top("cooler_lid", -5, 5, -3.5, 3.5)), pal("white", 0, 5)))
    br = K.bev_rings(0.22, 4.22, 0.35, 0.0, L(q, 3, 1), 0, mids=L(q, 2, 0))
    br = [(r[0] + 0.24 * (1 - (r[1] - 0.22) / 4.0) + 0.16, r[1]) for r in br]
    body = K.loft(4.95, 3.45, 0.75, br, L(q, 5, 1))
    face = K.m_plane("cooler_face", (0, 3.3, 2.1), (-1, 0, 0), (0, 0, 1), 5.6, 2.8)

    def body_rule(c, n):
        if n.y > 0.6 and abs(c.x) < 3.6:
            return face
        if n.z < -0.9:
            return K.m_pal("pool_dark", 0, 5)
        return K.r_box("s_cooler", (-5, 5, -3.5, 3.5, 0.22, 4.22))(c, n)
    A.add(body, body_rule)
    A.add(K.loft(4.62, 3.12, 0.6, [(0.0, 4.12), (0.0, 4.26)], L(q, 4, 1)), pal("navy", 0, 5))  # joint
    # pieds caoutchouc
    for sx in (-1, 1):
        for sy in (-1, 1):
            A.add(K.slab(0.55, 0.45, 0.0, 0.26, 0.2, 0.0, 0.05, K.Q(1), cx=sx * 3.7, cy=sy * 2.4), pal("rubber", 0, 5))
    # yeux ronds (dômes imprimés) + langue tirée
    for sx, look in ((-1, 0.0), (1, 0.12)):
        e = K.lathe([(0.62, 0.0), (0.62, 0.05), (0.52, 0.16), (0.3, 0.22), (0.0, 0.24)] if q.lod == 0 else
                    [(0.62, 0.0), (0.45, 0.18), (0.0, 0.24)], L(q, 16, 8))
        K.transform(e, Matrix.Rotation(math.radians(-90), 4, "X"))
        K.move(e, (sx * 1.3, 3.25, 3.2))
        A.add(e, K.r_const(K.m_plane("eye", (sx * 1.3 + look, 3.6, 3.2), (-sx, 0, 0), (0, 0, 1), 1.3, 1.3)))
    tongue = [(0.55, 1.45), (0.62, 0.95), (0.4, 0.55), (0.0, 0.45), (-0.4, 0.55), (-0.62, 0.95), (-0.55, 1.45)]
    tongue = outline_smooth(tongue, L(q, 2, 1))
    A.add(K.pillow(tongue, "xz", 3.36, 0.12, center=(0.0, 1.0), profile=PL(q)), pal("tongue", 0, 2))
    # poignées latérales (sous le couvercle, bouts ±X)
    for sx in (-1, 1):
        x = sx * 4.86
        p = [(x - sx * 0.12, -1.3, 3.55), (x, -1.2, 3.45), (x, -0.9, 3.3), (x, 0.9, 3.3), (x, 1.2, 3.45),
             (x - sx * 0.12, 1.3, 3.55)]
        A.add(K.tube(p, 0.12, L(q, 8, 4), up=(0, 0, 1)), pal("white", 0, 5))
        if q.detail:
            A.add(K.slab(0.08, 1.5, 3.35, 3.95, 0.12, 0, 0, K.Q(1), cx=sx * 4.66), pal("pool_dark", 0, 5))
    # loquet avant + charnière arrière
    A.add(K.slab(0.5, 0.1, 3.75, 4.5, 0.08, 0.02, 0.02, K.Q(1), cy=3.4), pal("white", 0, 5))
    A.add(K.slab(3.0, 0.08, 3.95, 4.25, 0.08, 0.0, 0.0, K.Q(1), cy=-3.38), pal("navy", 0, 5))
    return A


# =====================================================================================
# 7. Crocodile gonflable — enveloppe 16 x 8 x 6, collider 14 x 7 x 3
# =====================================================================================
def croc(lod):
    A = new_asset("pool_croc_float", lod)
    q = A.q
    H, hw, hd = 3.0, 7.0, 3.5
    float_body(A, hw, hd, H, 0.42, 0.17, "croc_top", "s_croc", L(q, 40, 20), crest=(0.24, 0.12))
    gr = pal("green", 0, 6)
    hy, ht = 3.95, 0.4
    # grosse tête de profil (museau vers +X), panneau soudé dans la bande avant
    head = [(2.6, 0.95), (4.6, 1.15), (6.5, 1.55), (7.7, 1.95), (8.0, 2.5), (7.9, 3.15), (7.4, 3.45), (6.2, 3.6),
            (5.4, 3.95), (4.95, 4.65), (4.0, 4.95), (3.1, 4.7), (2.6, 3.6)]
    head = outline_smooth(head, L(q, 2, 1))
    A.add(K.pillow(head, "xz", hy, ht, center=(4.4, 2.75), profile=PH(q)),
          face_rule("croc_face", (5.4, hy, 2.4), 5.6, 2.8, gr, back_tile="croc_face"))
    # bosses de narines
    if q.detail:
        A.add(K.ellipsoid((7.45, hy, 3.42), 0.32, 0.3, 0.2, 8, 4, z_from=0.0), gr)
    # yeux globuleux qui louchent (socle vert + globe imprimé)
    for (x, z, look) in ((3.7, 5.3, 0.22), (4.9, 5.36, -0.24)):
        if q.detail:
            A.add(K.ellipsoid((x, hy, z - 0.45), 0.52, 0.38, 0.42, 8, 4), gr)
        e = K.ellipsoid((x, hy, z), 0.64, 0.4, 0.64, L(q, 12, 8), L(q, 6, 4))
        A.add(e, split(lambda c, n: n.y > 0.2,
                       K.r_const(K.m_plane("eye", (x + look, hy + 0.4, z + 0.05), (-1, 0, 0), (0, 0, 1), 1.2, 1.2)),
                       pal("white", 0, 6)))
    # queue relevée (bout -X)
    tail = [(-6.5, 0.5), (-7.3, 0.9), (-7.85, 1.7), (-8.0, 2.8), (-7.85, 3.9), (-7.55, 4.7), (-7.3, 4.4),
            (-7.3, 3.6), (-7.15, 2.7), (-6.85, 2.1), (-6.4, 1.9)]
    tail = outline_smooth(tail, 2) if q.lod == 0 else tail
    A.add(K.pillow(tail, "xz", 0.0, 0.6, center=(-7.15, 1.8), profile=PL(q)), gr)
    if q.detail:  # crête dorsale de la queue
        for k, (x, z) in enumerate(((-7.95, 2.3), (-7.98, 3.0), (-7.85, 3.7), (-7.6, 4.35))):
            sp = [(x + 0.3, z - 0.3), (x - 0.02, z + 0.08), (x + 0.38, z + 0.32)]
            A.add(K.pillow([(u, v) for u, v in sp], "xz", 0.0, 0.18, center=(x - 0.1, z), profile=K.PILLOW_LO),
                  pal("green_dark", 0, 6))
    # pattes trapues (débordent en X)
    for sx in (-1, 1):
        for sy in (-2.3, 2.3):
            leg = K.ellipsoid((sx * 7.3, sy, 0.5), 0.7, 0.66, 0.5, L(q, 10, 6), L(q, 5, 2), z_from=-0.98)
            A.add(leg, split(lambda c, n: n.z < -0.2, pal("green_light", 0, 6), gr))
            if q.detail:
                for dy in (-0.36, 0.0, 0.36):
                    A.add(K.ellipsoid((sx * 7.84, sy + dy, 0.16), 0.15, 0.13, 0.12, 5, 2), pal("white", 0, 6))
    return A


# =====================================================================================
# 8. Matelas pneumatique — 12 x 7 x 2 (+ variante dégonflée)
# =====================================================================================
def mattress(lod):
    A = new_asset("pool_air_mattress", lod)
    q = A.q
    a, b = 6.0, 3.5
    rings = [(a - 0.42, b - 0.42, 3.5, 0.0), (a - 0.12, b - 0.12, 6.0, 0.22), (a, b, 10.0, 0.85),
             (a - 0.01, b - 0.01, 12.0, 1.45), (a - 0.02, b - 0.02, 14.0, 1.8)]
    if q.lod:
        rings = [rings[0], rings[2], rings[4]]
    body = K.blob(rings, L(q, 40, 20))
    top = K.r_const(K.m_top("mattress_top", -6, 6, -3.5, 3.5))

    def side(c, n):
        if n.z > 0.9:
            return top(c, n)
        if abs(n.x) > 0.7:
            return K.r_box("s_mattress", (-6, 6, -3.5, 3.5, 0, 2))(c, n)
        return K.m_pal("yellow", 0, 2)
    A.add(body, side)
    # boudins (couronnes) le long de X
    w = 7.0 / atlas.MATTRESS_TUBES
    crown = [(0.0, 1.76), (0.07, 1.88), (0.2, 1.95), (0.34, 1.975)] if q.lod == 0 else [(0.0, 1.76), (0.25, 1.96)]
    for k in range(atlas.MATTRESS_TUBES):
        yc = -3.5 + (k + 0.5) * w
        t = K.loft(4.92, w / 2, 0.42, crown, L(q, 3, 1), cx=0.88, cy=yc)
        A.add(t, top)
    pil = [(0.0, 1.76), (0.1, 1.92), (0.3, 2.0), (0.6, 2.03)] if q.lod == 0 else [(0.0, 1.76), (0.4, 2.02)]
    A.add(K.loft(0.92, 3.48, 0.6, pil, L(q, 4, 1), cx=-5.04), top)
    # valve plate + étiquette (avant)
    v = K.lathe([(0.3, 0.0), (0.3, 0.03), (0.16, 0.05), (0.0, 0.05)], L(q, 12, 6))
    K.transform(v, Matrix.Rotation(math.radians(-90), 4, "X"))
    K.move(v, (4.7, 3.49, 1.1))
    A.add(v, pal("white", 0, 2))
    if q.detail:
        lab = K.slab(0.7, 0.012, 0.75, 1.45, 0.05, 0, 0, K.Q(1), cx=3.4, cy=3.5)
        A.add(lab, split(lambda c, n: n.y > 0.5,
                         K.r_const(K.m_plane("valve_label", (3.4, 3.52, 1.1), (-1, 0, 0), (0, 0, 1), 1.4, 0.7)),
                         pal("white", 0, 2)))
    return A


def mattress_deflated(lod):
    """Matelas affaissé : champ de hauteur froissé (graine fixe), oreiller à moitié gonflé."""
    A = new_asset(DEFLATED_ID, lod)
    q = A.q
    rng = random.Random(SEED + 88)
    nx, ny = L(q, 40, 14), L(q, 18, 8)
    a, b = 6.0, 3.5
    waves = [(rng.uniform(0.6, 1.6), rng.uniform(0.4, 1.4), rng.uniform(0, 6.28), rng.uniform(0.015, 0.05))
             for _ in range(7)]
    w = 7.0 / atlas.MATTRESS_TUBES

    def hgt(x, y):
        ex = min(1.0, (a - abs(x)) / 0.45)
        ey = min(1.0, (b - abs(y)) / 0.45)
        edge = max(0.0, min(ex, ey))
        tube = 0.05 * math.sin(math.pi * ((y + b) / w % 1.0))
        wr = sum(amp * math.sin(fx * x + fy * y + ph) for fx, fy, ph, amp in waves)
        fold = 0.07 * math.exp(-((x - 1.4 + 0.3 * y) / 0.35) ** 2) + 0.05 * math.exp(-((x + 2.2 - 0.25 * y) / 0.3) ** 2)
        pw = math.exp(-((x + 5.0) / 1.0) ** 4)  # oreiller : plateau encore à moitié gonflé
        pillow = 0.41 * pw * (1 - 0.35 * (abs(y) / b) ** 2)
        h = 0.14 + tube + (wr + fold) * (1 - pw) + pillow
        return 0.035 + (h - 0.035) * (edge ** 0.6)
    bm = bmesh.new()
    xs = [-a + 2 * a * i / nx for i in range(nx + 1)]
    ys = [-b + 2 * b * j / ny for j in range(ny + 1)]
    grid = [[bm.verts.new((x, y, hgt(x, y) if 0 < i < nx and 0 < j < ny else 0.035))
             for j, y in enumerate(ys)] for i, x in enumerate(xs)]
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    # bord et dessous
    rim = [grid[i][0] for i in range(nx + 1)] + [grid[nx][j] for j in range(1, ny + 1)] + \
          [grid[i][ny] for i in range(nx - 1, -1, -1)] + [grid[0][j] for j in range(ny - 1, 0, -1)]
    low = [bm.verts.new((v.co.x, v.co.y, 0.0)) for v in rim]
    n = len(rim)
    for i in range(n):
        k = (i + 1) % n
        bm.faces.new((rim[k], rim[i], low[i], low[k]))
    bm.faces.new(low)
    K.solid(bm)
    top = K.r_const(K.m_top("mattress_top", -6, 6, -3.5, 3.5))
    A.add(bm, split(lambda c, n_: n_.z > 0.2, top, K.r_const(K.m_pal("yellow_dark", 0, 1))))
    # valve (avant), à plat
    v = K.lathe([(0.3, 0.0), (0.3, 0.03), (0.16, 0.05), (0.0, 0.05)], L(q, 12, 6))
    K.move(v, (4.7, 2.9, hgt(4.7, 2.9) - 0.01))
    A.add(v, pal("white", 0, 1))
    return A


# =====================================================================================
# 9. Machine signature : La Pompe à Bouées — 22 x 16 x 18
# =====================================================================================
def pump_machine(lod):
    A = new_asset(MACHINE_ID, lod)
    q = A.q
    lo = q.lod > 0
    # tapis caoutchouc + pieds
    mxc = -3.6
    A.add(K.slab(7.2, 7.9, 0.32, 0.9, 1.6, L(q, 0.1, 0), 0.25, q, cx=mxc), pal("navy", 0, 18))
    for sx in (-1, 1):
        for sy in (-1, 1):
            f = K.lathe([(0.75, 0.0), (0.85, 0.08), (0.85, 0.3), (0.7, 0.36)] if not lo else [(0.85, 0.0), (0.85, 0.36)],
                        L(q, 12, 5),
                        center=(mxc + sx * 6.0, sy * 6.6, 0))
            A.add(f, pal("rubber", 0, 18))
    # soufflet en coin : charnière arrière basse, pédale avant haute
    bx, by = mxc, -0.6
    ra, rb = 6.3, 5.6
    zb = 1.6

    def ztop(y):
        return 3.4 + (y - (by - rb)) / (2 * rb) * 8.6
    plate = K.blob([(ra + 0.3, rb + 0.3, 3.0, 0.9), (ra + 0.35, rb + 0.35, 3.0, 1.25), (ra + 0.2, rb + 0.2, 3.0, 1.6)],
                   L(q, 32, 16), cx=bx, cy=by)
    A.add(plate, pal("orange_dark", 0, 18))
    nf = L(q, 6, 3)
    rings = []
    for k in range(2 * nf + 1):
        s_ = 1.0 if k % 2 == 0 else 0.87
        rings.append((ra * s_, rb * s_, 3.0, k / (2 * nf)))

    def warp(x, y, t, k):
        return (x, y, zb + t * (ztop(y) - zb))
    bel = K.blob(rings, L(q, 36, 16), cx=bx, cy=by, cap0=False, cap1=False, warp=warp)
    face = K.m_plane("pump_face", (bx, 5.0, 6.4), (-1, 0, 0), (0, 0, 1), 7.6, 7.6)
    A.add(bel, split(lambda c, n: n.y > 0.25 and abs(c.x - bx) < 4.2, K.r_const(face), pal("yellow", 0, 12)))
    # pédale inclinée (grip caoutchouc + empreinte)
    ang = math.atan2(8.6, 2 * rb)
    hl = rb / math.cos(ang) + 0.35
    ped = K.slab(ra + 0.45, hl, -0.3, 0.3, 1.4, L(q, 0.12, 0), 0.15, q)
    M = Matrix.Translation((bx, by, ztop(by) + 0.25)) @ Matrix.Rotation(ang, 4, "X")
    K.transform(ped, M)
    nrm = (M.to_3x3() @ Vector((0, 0, 1))).normalized()
    ydir = (M.to_3x3() @ Vector((0, 1, 0))).normalized()
    pedal = K.m_plane("pedal", tuple(M @ Vector((0, 0, 0.3))), (-1, 0, 0), tuple(-ydir), 2 * ra, 2 * hl)
    A.add(ped, split(lambda c, n: n.dot(nrm) > 0.8, K.r_const(pedal), pal("orange", 0, 18)))
    # charnière arrière
    hinge = K.lathe([(0.5, -ra), (0.5, ra)], L(q, 12, 6))
    K.transform(hinge, Matrix.Rotation(math.radians(90), 4, "Y"))
    K.move(hinge, (bx, by - rb - 0.1, ztop(by - rb) - 0.05))
    A.add(hinge, pal("steel", 0, 18))
    # manomètre sur mât col-de-cygne (arrière droit)
    px_, py_ = 2.4, -6.2
    post = K.catmull([(px_, py_, 0.9), (px_, py_, 8.0), (px_ + 0.3, py_ + 0.5, 12.0), (px_ + 0.5, py_ + 1.4, 13.4)],
                     L(q, 4, 2))
    A.add(K.tube(post, 0.36, L(q, 10, 6), up=(0, 1, 0)), pal("steel", 0, 18))
    gx, gy, gz = px_ + 0.5, py_ + 1.9, 14.95
    gr_ = 2.55
    gauge = K.lathe([(gr_, -0.5), (gr_ + 0.18, -0.38), (gr_ + 0.18, 0.32), (gr_ - 0.05, 0.46), (gr_ - 0.22, 0.46),
                     (0.0, 0.46)], L(q, 28, 12))
    K.transform(gauge, Matrix.Rotation(math.radians(-90), 4, "X"))
    K.move(gauge, (gx, gy, gz))
    A.add(gauge, split(lambda c, n: n.y > 0.8 and math.hypot(c.x - gx, c.z - gz) < gr_ - 0.2,
                       K.r_const(K.m_plane("gauge", (gx, gy + 0.5, gz), (-1, 0, 0), (0, 0, 1), 2 * gr_ - 0.3, 2 * gr_ - 0.3)),
                       pal("red", 0, 18)))
    if not lo:
        glass = K.lathe([(gr_ - 0.2, 0.0), (gr_ - 0.6, 0.2), (1.2, 0.33), (0.0, 0.37)], 24)
        K.transform(glass, Matrix.Rotation(math.radians(-90), 4, "X"))
        K.move(glass, (gx, gy + 0.46, gz))
        A.add(glass, pal("glass", 0, 18), mat=1)
        for sx in (-1, 1):  # boulons du boîtier
            b = K.ellipsoid((gx + sx * 1.9, gy + 0.5, gz + 1.25), 0.14, 0.1, 0.14, 8, 4)
            A.add(b, pal("steel", 0, 18))
    cap = K.lathe([(0.5, 0.0), (0.5, 0.3), (0.32, 0.42), (0.0, 0.45)], L(q, 12, 6), center=(gx, gy, gz + gr_ + 0.12))
    A.add(cap, pal("yellow", 0, 18))
    # tuyau 1 : du soufflet vers la bouée canard à moitié gonflée (+X)
    rcx, rcy, R, r = 7.25, 2.4, 2.55, 1.0
    h1 = K.catmull([(bx + ra * 0.92, by + 1.2, 3.4), (4.2, 1.8, 3.8), (4.9, 2.6, 1.5), (5.0, 4.6, 0.55),
                    (rcx - 0.4, rcy + R + 0.45, 0.6)], L(q, 5, 2))
    A.add(K.tube(h1, 0.38, L(q, 10, 5), up=(0, 0, 1)), pal("pool", 0, 18))
    for t_ in (h1[0], h1[-1]):  # bagues de raccord
        A.add(K.ellipsoid(t_, 0.5, 0.5, 0.5, L(q, 10, 6), L(q, 4, 2)), pal("navy", 0, 18))
    # bouée canard molle : tore affaissé et ridé
    nu, nv = L(q, 36, 10), L(q, 10, 5)
    bm = bmesh.new()
    loops = []
    for i in range(nu):
        a = 2 * math.pi * i / nu
        sag = 0.6 + 0.4 * (0.5 + 0.5 * math.cos(a - math.radians(90)))  # côté valve (avant) encore gonflé
        rr = r * sag
        wr = 0.05 * math.sin(5 * a + 0.7) if not lo else 0.0
        ring = []
        for j in range(nv):
            b2 = 2 * math.pi * j / nv
            rad = R + (rr + wr) * math.cos(b2)
            zz = rr * 0.82 * (1 + math.sin(b2)) + (0.035 * math.sin(7 * a + 2 * j) if not lo else 0.0)
            ring.append(bm.verts.new((rcx + rad * math.cos(a), rcy + rad * math.sin(a), max(zz, 0.0))))
        loops.append(ring)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((loops[i][j], loops[(i + 1) % nu][j], loops[(i + 1) % nu][(j + 1) % nv],
                          loops[i][(j + 1) % nv]))
    K.solid(bm)
    A.add(bm, K.r_const(K.m_pal("yellow", 0, 2)))
    # tête de canard qui pend (panneau soudé incliné, côté arrière de la bouée, regarde l'avant)
    pts = [(1.45 * math.cos(math.radians(a)), 1.4 * math.sin(math.radians(a))) for a in range(-50, 231, L(q, 20, 56))]
    pts += [(-0.75, -1.45), (0.75, -1.45)]
    hb = K.pillow(pts, "xz", 0.0, 0.34, center=(0.0, 0.0), profile=PL(q))
    hm = Matrix.Translation((rcx + 0.6, rcy - R + 0.1, 2.75)) @ Matrix.Rotation(math.radians(-24), 4, "Y") @ \
        Matrix.Rotation(math.radians(14), 4, "X")
    K.transform(hb, hm)
    hn = (hm.to_3x3() @ Vector((0, 1, 0))).normalized()
    hface = K.m_plane("duck_face", tuple(hm @ Vector((0.0, 0.34, 0.12))), tuple(hm.to_3x3() @ Vector((-1, 0, 0))),
                      tuple(hm.to_3x3() @ Vector((0, 0, 1))), 3.0, 3.0)
    A.add(hb, split(lambda c, n: n.dot(hn) > 0.3, K.r_const(hface), pal("yellow", 0, 2)))
    bill = K.pillow([(0.7, 0.0), (0.6, 0.55), (0.0, 0.75), (-0.6, 0.55), (-0.7, 0.0)], "xy", 0.0, 0.16,
                    center=(0.0, 0.25), profile=PL(q))
    K.transform(bill, hm @ Matrix.Translation((0.0, 0.2, -0.5)))
    A.add(bill, pal("orange", 0, 2))
    # tuyau 2 : du soufflet vers une buse posée (côté -X, boucle sur le tapis)
    h2 = K.catmull([(bx - ra * 0.92, by + 1.4, 2.8), (-10.6, 0.8, 2.4), (-10.7, 4.0, 1.0), (-9.4, 6.6, 1.05),
                    (-7.0, 7.3, 1.05), (-5.0, 6.9, 1.05)], L(q, 5, 2))
    A.add(K.tube(h2, 0.36, L(q, 10, 5), up=(0, 0, 1)), pal("coral", 0, 18))
    A.add(K.ellipsoid(h2[0], 0.48, 0.48, 0.48, L(q, 10, 6), L(q, 4, 2)), pal("navy", 0, 18))
    nz = K.lathe([(0.45, 0.0), (0.45, 0.5), (0.28, 0.8), (0.2, 1.5), (0.0, 1.52)], L(q, 10, 6))
    K.transform(nz, Matrix.Rotation(math.radians(80), 4, "Y"))
    K.move(nz, (-5.05, 6.9, 1.05))
    A.add(nz, pal("navy", 0, 18))
    return A


BUILDERS = {
    "pool_inflatable_duck": duck,
    "pool_flamingo_float": flamingo,
    "pool_beach_ball": beach_ball,
    "pool_donut_ring": donut,
    "pool_unicorn_float": unicorn,
    "pool_cooler": cooler,
    "pool_croc_float": croc,
    "pool_air_mattress": mattress,
    DEFLATED_ID: mattress_deflated,
    MACHINE_ID: pump_machine,
}
WALKABLE_IDS = [p for p in BUILDERS if SPECS[p]["walkable"]]


# =====================================================================================
# matériaux, export, sauvegarde
# =====================================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    return sc


def make_materials(col_png, rough_png):
    img = bpy.data.images.load(col_png)
    img.colorspace_settings.name = "sRGB"
    rimg = bpy.data.images.load(rough_png)
    rimg.colorspace_settings.name = "Non-Color"
    m = bpy.data.materials.new("M_pool_vinyl")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    tr = nt.nodes.new("ShaderNodeTexImage")
    tr.image = rimg
    sp = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tr.outputs["Color"], sp.inputs["Color"])
    nt.links.new(sp.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sp.outputs["Blue"], bsdf.inputs["Metallic"])
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.55
    g = bpy.data.materials.new("M_pool_glass")
    g.use_nodes = True
    gb = g.node_tree.nodes.get("Principled BSDF")
    gb.inputs["Base Color"].default_value = (0.85, 0.97, 1.0, 1.0)
    gb.inputs["Roughness"].default_value = 0.05
    gb.inputs["Alpha"].default_value = 0.18
    g.surface_render_method = "BLENDED"
    return m, g, (img, rimg)


def select_only(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def export(ob, path, fbx=None):
    select_only(ob)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_texcoords=True, export_normals=True,
                              export_materials="EXPORT", export_animations=False, export_skins=False)
    if fbx:
        bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"}, axis_forward="-Z",
                                 axis_up="Y", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                                 global_scale=1.0, bake_anim=False, path_mode="COPY", embed_textures=True,
                                 mesh_smooth_type="FACE", use_mesh_modifiers=True)


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def bbox(ob):
    co = [ob.matrix_world @ v.co for v in ob.data.vertices]
    mn = [min(c[i] for c in co) for i in range(3)]
    mx = [max(c[i] for c in co) for i in range(3)]
    return mn, mx


def collision_entry(pid, mn, mx):
    s = SPECS[pid]
    cx, cy = (mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2
    e = {
        "asset_id": pid,
        "behavior": s["behavior"],
        "behavior_params": s["behavior_params"],
        "pivot": "bottom_center_of_gameplay_collider",
        "forward_axis": "-Z",
        "visual_envelope_studs_wdh": s["envelope"],
        "mesh_bbox_center_from_pivot_roblox": [round(cx, 3), round((mn[2] + mx[2]) / 2, 3), round(-cy, 3)],
        "visual_mesh": {"can_collide": False, "can_query": False, "can_touch": False},
    }
    if s.get("brief_envelope"):
        e["brief_envelope_studs_wdh"] = s["brief_envelope"]
        e["envelope_note"] = s["envelope_note"]
    if s["collider"]:
        w, d, h = s["collider"]
        e["collider"] = {"shape": "box", "size_studs_config": [w, d, h], "size_vector3_roblox": [w, h, d],
                         "offset_from_pivot_roblox": [0, h / 2, 0], "tags": ["FillCollider"], "can_collide": True}
        e["walkable_top"] = {"size_studs": s["walkable"], "height_studs": h, "center_roblox": [0, h, 0]}
    else:
        e["collider"] = None
        e["walkable_top"] = None
    return e


def main():
    random.seed(SEED)
    alt = bool(os.environ.get("POOL_IMPORT_DIR"))
    os.makedirs(TEX_DIR, exist_ok=True)
    os.makedirs(IMPORT_DIR, exist_ok=True)
    col_png, rough_png = atlas.save_atlas(TEX_DIR) if not alt else atlas.save_atlas(os.path.join(IMPORT_DIR, "tex"))
    reset_scene()
    mat, glass, imgs = make_materials(col_png, rough_png)
    info = {"family": "pool", "seed": SEED, "blender_version": bpy.app.version_string,
            "units": "1 BU = 1 stud (décision 0003)", "atlas": os.path.relpath(col_png, ROOT),
            "atlas_roughness_metal": os.path.relpath(rough_png, ROOT), "assets": {}}
    only = sys.argv[1:] or list(BUILDERS)
    boxes = {}
    for pid, fn in BUILDERS.items():
        if pid not in only:
            continue
        coll = bpy.data.collections.new(pid)
        bpy.context.scene.collection.children.link(coll)
        objs = {}
        for lod in (0, 1):
            A = fn(lod)
            mats = [mat, glass] if pid == MACHINE_ID else [mat]
            ob = A.to_object(f"{pid}_LOD{lod}", mats)
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            coll.objects.link(ob)
            objs[lod] = ob
        if not SPECS[pid]["collider"]:  # décor sans collider : pivot = centre du bas de la boîte englobante
            mn, mx = bbox(objs[0])
            off = Matrix.Translation((-(mn[0] + mx[0]) / 2, -(mn[1] + mx[1]) / 2, 0.0))
            for ob in objs.values():
                ob.data.transform(off)
        base = os.path.join(IMPORT_DIR, pid)
        export(objs[0], base + ".glb", base + ".fbx")
        export(objs[1], base + "_lod1.glb")
        objs[1].hide_set(True)
        objs[1].hide_render = True
        mn, mx = bbox(objs[0])
        boxes[pid] = (mn, mx)
        dims = [round(mx[i] - mn[i], 4) for i in range(3)]
        info["assets"][pid] = {
            "lod0_object": objs[0].name, "lod1_object": objs[1].name,
            "lod0_tris": tris(objs[0]), "lod1_tris": tris(objs[1]),
            "lod0_dims_wdh": dims, "lod1_dims_wdh": [round(v, 4) for v in objs[1].dimensions],
            "bbox_min": [round(v, 4) for v in mn], "bbox_max": [round(v, 4) for v in mx],
            "materials": [m.name for m in objs[0].data.materials],
            "exports": [os.path.relpath(base + e, ROOT) for e in (".glb", "_lod1.glb", ".fbx")],
        }
        print(pid, info["assets"][pid]["lod0_tris"], info["assets"][pid]["lod1_tris"], dims,
              [round(v, 3) for v in mn], [round(v, 3) for v in mx], flush=True)
    if alt:
        return
    for im in imgs:
        im.pack()
    bpy.context.preferences.filepaths.save_version = 0
    blend = os.path.join(MODEL_DIR, "pool_props.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    info["blend"] = os.path.relpath(blend, ROOT)
    if len(only) == len(BUILDERS):
        with open(os.path.join(MODEL_DIR, "build_info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        coll = {"family": "pool", "units": "studs",
                "axes": "roblox_model_space (X largeur, Y haut, Z profondeur ; avant = -Z)",
                "authority": "server_collider_separate_from_visual_mesh",
                "pivot_note": "Origine des fichiers = centre du bas du collider de jeu. Les têtes débordent à l'avant : "
                              "le centre de la boîte englobante du maillage est décalé de "
                              "mesh_bbox_center_from_pivot_roblox (à appliquer si l'import recentre le MeshPart).",
                "props": [collision_entry(p, *boxes[p]) for p in BUILDERS if p != MACHINE_ID],
                "machine": dict(collision_entry(MACHINE_ID, *boxes[MACHINE_ID]),
                                note="Décor seulement (alcôve) : aucune collision de parcours portée par le maillage.")}
        with open(os.path.join(MODEL_DIR, "collision_pool.json"), "w", encoding="utf-8") as f:
            json.dump(coll, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
