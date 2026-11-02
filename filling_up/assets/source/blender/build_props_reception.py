"""Construit les 8 props de la famille Réception + la machine signature (Le Tamponneur).

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/build_props_reception.py

Sorties :
  assets/source/models/reception/reception_props.blend      (LOD0 + LOD1 de chaque asset, atlas empaqueté)
  assets/source/models/reception/textures/reception_atlas_1024.png (+ _rough_1024 : G rugosité, B métal)
  assets/source/models/reception/build_info.json, collision_reception.json
  assets/import/models/<id>.glb, <id>_lod1.glb, <id>.fbx

Données canoniques : config/rooms.json (families[id=reception]) ; direction artistique :
docs/04_UNIVERS_ET_SALLES.md §2/§6, docs/02_ASSETS_ET_CLAUDE_DESIGN.md (tokens) et la planche
assets/source/design/canvas/project/Room_Reception.dc.html. Unités/axes : décision 0003
(1 BU = 1 stud ; X largeur, Y profondeur, Z hauteur ; avant Roblox -Z = +Y Blender ; pivot au sol, centré).
Construction déterministe (graines fixes) ; aucun asset tiers.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402  (bpy doit précéder bmesh)
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import prop_kit as K  # noqa: E402
import reception_atlas as atlas  # noqa: E402

SEED = 20261102
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # filling_up/
MODEL_DIR = os.path.join(ROOT, "assets", "source", "models", "reception")
TEX_DIR = os.path.join(MODEL_DIR, "textures")
IMPORT_DIR = os.path.join(ROOT, "assets", "import", "models")
MACHINE_ID = "machine_reception_stamp"


def family():
    with open(os.path.join(ROOT, "config", "rooms.json"), encoding="utf-8") as f:
        d = json.load(f)
    return next(x for x in d["families"] if x["id"] == "reception")


def spec(pid):
    fam = family()
    if pid == MACHINE_ID:
        return fam["machine"]
    return next(p for p in fam["props"] if p["id"] == pid)


def new_asset(pid, lod):
    return K.Asset(pid, tuple(float(v) for v in spec(pid)["size_studs"]), lod)


def split(pred, a, b):
    return K.r_if(pred, a, b)


def seg(q, hi, lo=1):
    return hi if q.lod == 0 else lo


# =====================================================================================
# 1. Carton standard 10 x 8 x 4 — kraft, ruban cyan, étiquette, poignées découpées
# =====================================================================================
def carton(lod):
    A = new_asset("reception_carton", lod)
    q = A.q
    tt = 0.035  # épaisseur du ruban
    hw, hd, top = 5.0 - tt, 4.0, 4.0 - tt
    rings = K.bev_rings(0.0, top, 0.16, 0.2, seg(q, 4), seg(q, 4), mids=seg(q, 3, 0))
    rings = K.add_bulge(rings, 0.05, 0.0, top)
    body = K.loft(hw, hd, 0.5, rings, seg(q, 6), min_corner=2)
    if q.detail:  # poignées découpées sur les deux bouts
        cutters = []
        for sx in (-1, 1):
            c = K.slab(0.85, 0.28, -0.5, 0.5, 0.27, 0, 0, q)
            K.orient(c, "x")
            K.move(c, (sx * 5.0, 0, 1.75))
            cutters.append(c)
        body = K.boolean_diff(body, cutters)
    side = K.r_box("s_cardboard", A.bbox)
    rule = split(K.r_top_faces(top - 0.02, 0.9), K.r_const(K.m_top("carton_top", -5, 5, -4, 4)), side)
    A.add(body, rule, cut_rule=A.pal("rubber"))
    # ruban adhésif : dessus + retombées sur les deux bouts
    path = K.section_path(rings, hw, 2.55)
    tape = K.wrap_strip(path, "xz", -0.8, 0.8, tt, (0.0, 2.0))
    A.add(tape, A.pal("cyan"))
    if q.detail:
        # second ruban, plus court, en travers (fermeture renforcée) côté avant/arrière
        path2 = K.section_path(rings, hd, 3.25)
        tape2 = K.wrap_strip(path2, "yz", 3.55, 4.25, tt * 0.5, (0.0, 2.0))
        A.add(tape2, A.pal("cyan"))
    # étiquette d'expédition sur la face avant (+Y), épouse le bombé
    zs = [0.9 + 1.6 * k / 4 for k in range(5)]
    lp = [(hd - K.interp_inset(rings, z), z) for z in zs]
    label = K.wrap_strip(lp, "yz", 0.6, 3.8, 0.012, (0.0, 2.0))
    A.add(label, split(lambda c, n: n.y > 0.5,
                       K.r_const(K.m_plane("label_carton", (2.2, 4.0, 1.7), (-1, 0, 0), (0, 0, 1), 3.2, 1.6)),
                       A.pal("white")))
    return A


# =====================================================================================
# 2. Caisse mousse 8 x 8 x 4 — mousse orange dense, rebord épais, poignées creuses, nervures
# =====================================================================================
def foam_crate(lod):
    A = new_asset("reception_foam_crate", lod)
    q = A.q
    rim_r = K.bev_rings(2.85, 4.0, 0.14, 0.22, seg(q, 3), seg(q, 4))
    rim = K.loft(4.0, 4.0, 0.6, rim_r, seg(q, 6), min_corner=2)
    if q.detail:  # poignées creuses (décoratives) sur les deux bouts
        cutters = []
        for sx in (-1, 1):
            c = K.slab(1.25, 0.3, -0.45, 0.45, 0.29, 0, 0, q)
            K.orient(c, "x")
            K.move(c, (sx * 4.0, 0, 3.42))
            cutters.append(c)
        rim = K.boolean_diff(rim, cutters)
    side = K.r_box("s_foam", A.bbox)
    A.add(rim, split(K.r_top_faces(3.9, 0.7), K.r_const(K.m_top("foam_top", -4, 4, -4, 4)), side))
    if not q.detail:
        for sx in (-1, 1):  # poignée lointaine : simple plaque sombre
            p = K.slab(0.03, 1.2, 3.15, 3.7, 0.02, 0, 0, q, cx=sx * 3.96)
            A.add(p, A.pal("navy"))
    # corps conique (la caisse s'emboîte : plus étroite en bas)
    br = K.bev_rings(0.0, 2.95, 0.35, 0.0, seg(q, 3), 0, mids=seg(q, 2, 0))
    br = [(r[0] + 0.2 + 0.32 * (1 - r[1] / 2.95), r[1]) for r in br]
    body = K.loft(4.0, 4.0, 0.7, br, seg(q, 6), cap1=True)
    A.add(body, side)
    # nervures verticales de renfort (2 par face)
    if q.detail:
        zs = [0.3 + 2.55 * k / 4 for k in range(5)]
        for p in (-1.9, 1.9):
            for sgn in (-1, 1):
                path = [(sgn * (4.0 - K.interp_inset(br, z)), z) for z in zs]
                rib = K.wrap_strip(path, "xz", p - 0.28, p + 0.28, 0.16, (0.0, 1.5))
                A.add(rib, A.pal("foam_dark"))
                path = [(sgn * (4.0 - K.interp_inset(br, z)), z) for z in zs]
                rib = K.wrap_strip(path, "yz", p - 0.28, p + 0.28, 0.16, (0.0, 1.5))
                A.add(rib, A.pal("foam_dark"))
    return A


# =====================================================================================
# 3. Valise orange couchée 10 x 6 x 4 — coques nervurées, fermeture, poignée et roues encastrées
# =====================================================================================
def suitcase(lod):
    A = new_asset("reception_suitcase", lod)
    q = A.q
    hw, hd, R = 5.0, 2.95, 0.62
    low_r = K.bev_rings(0.0, 1.9, 0.6, 0.06, seg(q, 3), 1)
    up_r = K.bev_rings(2.1, 3.95, 0.06, 0.24, 1, seg(q, 3))
    lower = K.loft(hw, hd, R, low_r, seg(q, 5))
    upper = K.loft(hw, hd, R, up_r, seg(q, 5), min_corner=2)
    if q.detail:
        cl, cu = [], []
        for sy in (-1, 1):
            for (z0, z1, lst) in ((0.12, 1.62, cl), (2.38, 3.82, cu)):
                c = K.slab(0.75, 1.0, z0, z1, 0.3, 0, 0, q, cx=4.6, cy=sy * 2.25)
                lst.append(c)
        h = K.slab(0.575, 1.5, 2.5, 3.4, 0.45, 0, 0, q)  # poignée de portage (face avant)
        K.orient(h, "y")
        K.move(h, (0, 0, 3.0))
        cu.append(h)
        t = K.slab(1.5, 0.55, -5.4, -4.55, 0.4, 0, 0, q)  # canne télescopique (bout -X)
        K.orient(t, "x")
        K.move(t, (0, 0, 3.0))
        cu.append(t)
        lower = K.boolean_diff(lower, cl)
        upper = K.boolean_diff(upper, cu)
    side = K.r_box("s_shell", A.bbox)
    A.add(lower, side)
    A.add(upper, split(K.r_top_faces(3.85, 0.7), K.r_const(K.m_top("suitcase_top", -5, 5, -3, 3)), side))
    zip_r = [(0.1, 1.86), (0.1, 2.14)]
    A.add(K.loft(hw, hd, R, zip_r, seg(q, 5)), A.pal("navy"))
    # nervures peu profondes (coque haute par-dessus, coque basse par-dessous)
    ribs_x = (-3.4, -2.75, 2.75, 3.4) if q.detail else (-3.1, 3.1)
    up_path = K.section_path(up_r, hd, 2.3)
    lo_side = [(hd - K.interp_inset(low_r, 1.7), 1.7)] + [(hd - r[0], r[1]) for r in reversed(low_r)
                                                         if 0.25 < r[1] < 1.7]
    for x in ribs_x:
        A.add(K.wrap_strip(up_path, "yz", x - 0.16, x + 0.16, 0.05, (0.0, 2.6)), A.pal("shell_rib"))
        if q.detail:
            for sg in (1, -1):
                A.add(K.wrap_strip([(sg * s_, z) for s_, z in lo_side], "yz", x - 0.16, x + 0.16, 0.05, (0.0, 1.1)),
                      A.pal("shell_rib"))
    if q.detail:
        # roues pivotantes jumelées dans les poches d'angle (bout +X)
        for sy in (-1, 1):
            for zc in (0.87, 3.1):
                for dy in (-0.2, 0.2):
                    w = K.lathe([(0.2, -0.09), (0.5, -0.07), (0.5, 0.07), (0.2, 0.09)], 12, closed_profile=True)
                    K.transform(w, Matrix.Rotation(math.radians(90), 4, "X"))
                    K.move(w, (4.47, sy * 2.25 + dy, zc))
                    A.add(w, A.pal("rubber"))
                ax = K.lathe([(0.2, -0.3), (0.2, 0.3)], 6)
                K.transform(ax, Matrix.Rotation(math.radians(90), 4, "X"))
                K.move(ax, (4.47, sy * 2.25, zc))
                A.add(ax, A.pal("steel"))
                hs = K.slab(0.3, 0.42, zc - 0.22, zc + 0.22, 0.12, 0, 0, K.Q(1), cx=4.0, cy=sy * 2.25)
                A.add(hs, A.pal("navy"))
        # poignée de portage
        hp = [(-1.25, 2.55, 3.0), (-1.18, 2.76, 3.0), (-0.95, 2.83, 3.0), (0.95, 2.83, 3.0), (1.18, 2.76, 3.0),
              (1.25, 2.55, 3.0)]
        A.add(K.tube(hp, 0.15, 8, up=(0, 0, 1)), A.pal("navy"))
        # poignée télescopique repliée
        tp = [(-4.6, -1.25, 3.0), (-4.78, -1.18, 3.0), (-4.84, -0.95, 3.0), (-4.84, 0.95, 3.0), (-4.78, 1.18, 3.0),
              (-4.6, 1.25, 3.0)]
        A.add(K.tube(tp, 0.15, 8, up=(0, 0, 1)), A.pal("navy"))
        # tirette de fermeture + porte-étiquette
        tab = K.slab(0.16, 0.05, 1.45, 2.05, 0.04, 0.03, 0.03, q, cx=2.0, cy=2.9)
        A.add(tab, A.pal("steel"))
        zs = [0.7 + 0.8 * k / 3 for k in range(4)]
        lp = [(hd - K.interp_inset(low_r, z), z) for z in zs]
        idl = K.wrap_strip(lp, "yz", -2.1, -0.4, 0.03, (0.0, 1.0))
        A.add(idl, split(lambda c, n: n.y > 0.5,
                         K.r_const(K.m_plane("label_small", (-1.25, 3.0, 1.1), (-1, 0, 0), (0, 0, 1), 1.7, 0.8)),
                         A.pal("steel")))
    else:
        for sy in (-1, 1):
            for zc in (0.87, 3.1):
                w = K.lathe([(0.48, -0.25), (0.48, 0.25)], 8)
                K.transform(w, Matrix.Rotation(math.radians(90), 4, "X"))
                K.move(w, (4.5, sy * 2.25, zc))
                A.add(w, A.pal("rubber"))
    return A


# =====================================================================================
# 4. Palette turquoise 12 x 10 x 2 — plateau fermé, 9 plots, 3 semelles, nervures de dessous
# =====================================================================================
def pallet(lod):
    A = new_asset("reception_pallet", lod)
    q = A.q
    deck = K.slab(6.0, 5.0, 1.35, 2.0, 0.5, 0.1, 0.2, q, min_corner=2)
    A.add(deck, split(K.r_top_faces(1.95, 0.7), K.r_const(K.m_top("pallet_top", -6, 6, -5, 5)),
                      split(lambda c, n: n.z < -0.7, A.pal("turq_dark"), K.r_box("s_pallet", A.bbox))))
    for x in (-4.9, 0.0, 4.9):
        for y in (-3.95, 0.0, 3.95):
            rings = K.bev_rings(0.22, 1.4, 0.1, 0.0, 1, 0)
            rings = [(r[0] + 0.08 * (1 - (r[1] - 0.22) / 1.18), r[1]) for r in rings]
            foot = K.loft(1.1, 1.0, 0.35, rings, seg(q, 2), cx=x, cy=y)
            A.add(foot, K.r_box("s_pallet", A.bbox))
            if q.detail:  # creux de moulage sur la face visible de chaque plot extérieur
                for (nx, ny) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if (nx and abs(x) < 1) or (ny and abs(y) < 1) or (nx and nx * x < 0) or (ny and ny * y < 0):
                        continue
                    pad = K.slab(0.55 if ny else 0.03, 0.03 if ny else 0.5, 0.45, 1.15, 0.02, 0, 0, K.Q(1),
                                 cx=x + nx * (1.1 - 0.08 * 0.5), cy=y + ny * (1.0 - 0.08 * 0.5))
                    A.add(pad, A.pal("turq_dark"))
    for y in (-3.95, 0.0, 3.95):
        run = K.slab(6.0, 1.0, 0.0, 0.28, 0.35, 0.0, 0.08, K.Q(1) if q.lod else K.Q(0), cy=y)
        A.add(run, A.pal("turq_dark"))
    if q.detail:  # nervures sous plateau visibles dans les passages de fourche
        for y in (-1.95, 1.95):
            A.add(K.slab(5.8, 0.12, 1.15, 1.4, 0.05, 0, 0, K.Q(1), cy=y), A.pal("turq_dark"))
        for x in (-2.45, 2.45):
            A.add(K.slab(0.12, 4.8, 1.15, 1.4, 0.05, 0, 0, K.Q(1), cx=x), A.pal("turq_dark"))
    return A


# =====================================================================================
# 5. Bobine de ruban 9 x 9 x 3 (plateau 7 x 7) — flasques roses, ruban citron, plateau carré
# =====================================================================================
def tape_reel(lod):
    A = new_asset("reception_tape_reel", lod)
    q = A.q
    n = seg(q, 56, 16)
    fl = [(4.28, 0.0), (4.44, 0.05), (4.5, 0.18), (4.44, 0.31), (4.28, 0.36)]
    if q.lod:
        fl = [(4.35, 0.0), (4.5, 0.18), (4.35, 0.36)]
    A.add(K.lathe(fl, n), A.pal("pink"))
    A.add(K.lathe([(z[0], z[1] + 2.26) for z in fl], n), A.pal("pink"))
    rib = [(3.96, 0.34), (4.03, 0.42), (4.03, 2.2), (3.96, 2.28)]
    A.add(K.lathe(rib, n), split(lambda c, n_: abs(n_.z) > 0.9, A.pal("cream"),
                                  K.r_const(K.m_band("s_ribbon", 0.36, 2.26))))
    plate = K.slab(3.5, 3.5, 2.58, 3.0, 0.45, 0.05, 0.15, q, min_corner=2)
    A.add(plate, split(K.r_top_faces(2.96, 0.8), K.r_const(K.m_top("reel_top", -3.5, 3.5, -3.5, 3.5)),
                       A.pal("pink_dark")))
    if q.detail:
        # extrémité libre du ruban qui se décolle (lit sur le côté visible)
        bm = bmesh.new()
        secs = []
        N = 14
        for i in range(N + 1):
            t = i / N
            th = math.radians(5 + 70 * t)
            peel = 0.0 if t < 0.55 else ((t - 0.55) / 0.45) ** 1.5
            r = 4.04 + 0.4 * peel
            zc = 1.31 - 0.5 * (0.0 if t < 0.55 else ((t - 0.55) / 0.45) ** 2)
            out = Vector((math.cos(th), math.sin(th), 0))
            c = Vector((r * math.cos(th), r * math.sin(th), zc))
            up = Vector((0, 0, 1))
            hwb, th2 = 0.42, 0.025
            secs.append([bm.verts.new(c + up * hwb + out * th2), bm.verts.new(c - up * hwb + out * th2),
                         bm.verts.new(c - up * hwb - out * th2), bm.verts.new(c + up * hwb - out * th2)])
        for a, b in zip(secs[:-1], secs[1:]):
            for k in range(4):
                bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
        bm.faces.new(secs[0])
        bm.faces.new(list(reversed(secs[-1])))
        K.solid(bm)
        A.add(bm, A.pal("cream"))
    return A


# =====================================================================================
# 6. Colis oreiller 8 x 8 x 3 (rebond) — coussin capitonné, passepoil jaune, bandeau kraft, ressort
# =====================================================================================
def pillow_parcel(lod):
    A = new_asset("reception_pillow_parcel", lod)
    q = A.q
    half, R = 4.0, 0.45
    pr, pin = 0.17, 0.3  # passepoil : rayon, retrait de l'axe depuis l'enveloppe
    ztop_p, zbot_p = 2.75, 0.17
    # (inset, z, dr) : flanc bombé jusqu'à l'enveloppe, coins pincés ("oreilles") à mi-hauteur
    body_r = [(0.42, 0.0, 0.0), (0.3, 0.08, 0.0), (0.22, 0.2, -0.05), (0.08, 0.6, -0.25), (0.0, 1.45, -0.4),
              (0.08, 2.3, -0.25), (0.22, 2.66, -0.05), (0.3, 2.8, 0.0), (0.45, 2.87, 0.0), (0.75, 2.915, 0.2),
              (1.2, 2.945, 0.25), (1.9, 2.958, 0.25), (2.7, 2.965, 0.25)]
    if q.lod:
        body_r = [(0.42, 0.0, 0.0), (0.2, 0.2, 0.0), (0.0, 1.45, -0.4), (0.2, 2.7, 0.0), (0.45, 2.87, 0.0),
                  (1.4, 2.95, 0.25), (2.7, 2.965, 0.25)]
    body = K.loft(half, half, R, body_r, seg(q, 5), min_corner=2)
    A.add(body, split(lambda c, n: n.z > 0.45 and c.z > 2.78,
                      K.r_const(K.m_top("pillow_top", -4, 4, -4, 4)), K.r_box("s_fabric", A.bbox)))
    for zc in (ztop_p, zbot_p):
        path = [(x, y, zc) for x, y in K.rrect(half - pin, half - pin, R - pin + 0.02, seg(q, 5, 2))]
        A.add(K.tube(path, pr, seg(q, 8, 4), closed=True), A.pal("yellow"))

    # bandeau kraft d'emballage (passe par-dessus les passepoils, ne descend pas sous le sol)
    def env_inset(z):
        ins = K.interp_inset(body_r, z)
        for zc in (ztop_p, zbot_p):
            if abs(z - zc) < pr:
                ins = min(ins, pin - math.sqrt(pr * pr - (z - zc) ** 2))
        return ins
    bt = 0.035
    zs = [0.04, 0.08, 0.17, 0.3, 0.6, 1.0, 1.45, 1.9, 2.3, 2.6, 2.66, 2.75, 2.84]
    side = [(half - max(env_inset(z), bt), z) for z in zs]  # le bandeau serre le coussin : reste dans l'enveloppe
    side += [(half - pin, ztop_p + pr), (half - 0.45, 2.89)]
    side += [(half - r[0], r[1]) for r in body_r if r[0] > 0.6]
    path = side + [(-s, z) for s, z in reversed(side)]
    band = K.wrap_strip(path, "yz", -1.1, 1.1, bt, (0.0, 1.5), closed=True)
    A.add(band, split(lambda c, n: n.z > 0.45 and c.z > 2.8,
                      K.r_const(K.m_top("pillow_top", -4, 4, -4, 4)), A.pal("kraft")))
    if q.detail:  # boutons de capiton
        for x in (-2.6, 2.6):
            for y in (-2.6, 2.6):
                b = K.lathe([(0.24, -0.04), (0.24, 0.0), (0.18, 0.03), (0.0, 0.035)], 12, center=(x, y, 2.9487))
                A.add(b, A.pal("yellow_dark"))
    return A


# =====================================================================================
# 7. Chariot postal 10 x 8 x 3 (mobile) — plateau cyan balisé, pare-chocs, châssis, 4 roulettes
# =====================================================================================
def mail_cart(lod):
    A = new_asset("reception_mail_cart", lod)
    q = A.q
    lo = q.lod > 0
    deck = K.slab(4.92, 3.92, 2.42, 3.0, 0.45, 0.06, 0.12, q, min_corner=2)
    A.add(deck, split(K.r_top_faces(2.95, 0.8), K.r_const(K.m_top("cart_deck", -5, 5, -4, 4)), A.pal("cyan_dark")))
    bump = K.loft(5.0, 3.96, 0.5, [(0.05, 2.47), (0.0, 2.53), (0.0, 2.85), (0.05, 2.91)] if not lo else
                  [(0.0, 2.5), (0.0, 2.88)], seg(q, 4))

    def bump_rule(c, n):
        if abs(n.x) > 0.6:
            s = 1 if n.x > 0 else -1
            return K.m_plane("hazard", (s * 5.0, 0, 2.69), (0, s, 0), (0, 0, 1), 8.0, 0.44)
        return K.m_pal("navy", 0, 3)
    A.add(bump, bump_rule)
    simple = K.Q(1)  # pièces cachées sous le plateau : biseaux minimaux
    if not lo:
        for sy in (-1, 1):  # catadioptres fléchés sur les flancs (sens de translation)
            for x in (-2.6, 2.6):
                r = K.slab(0.9, 0.025, 2.58, 2.8, 0.02, 0, 0, simple, cx=x, cy=sy * 3.975)
                A.add(r, split(lambda c, n, sy=sy: n.y * sy > 0.5,
                               K.r_const(K.m_plane("arrow_strip", (x, sy * 4.0, 2.69), (-sy, 0, 0), (0, 0, 1), 1.8, 0.22)),
                               A.pal("cyan")))
        for x in (-3.75, 0.0, 3.75):
            A.add(K.slab(0.28, 2.6, 1.95, 2.43, 0.12, 0.04, 0.0, simple, cx=x), A.pal("navy"))
        for sx in (-1, 1):  # plaques d'extrémité + balises lumineuses
            A.add(K.slab(0.12, 3.2, 1.55, 2.45, 0.2, 0.04, 0.0, simple, cx=sx * 4.6), A.pal("navy"))
            for y in (-2.3, 2.3):
                b = K.lathe([(0.24, 0.0), (0.24, 0.05), (0.19, 0.15), (0.1, 0.2), (0.0, 0.215)], 10)
                K.transform(b, Matrix.Rotation(math.radians(90 * sx), 4, "Y"))
                K.move(b, (sx * 4.72, y, 2.0))
                A.add(b, A.pal("cyan"))
    for sy in (-1, 1):  # longerons
        A.add(K.slab(4.55, 0.3, 1.85, 2.45, 0.2, 0.05, 0.0, simple, cy=sy * 2.7), A.pal("navy"))
    # roulettes (roulent selon X = axe "width" du déplacement)
    nw = 16 if not lo else 8
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * 3.75, sy * 2.7
            if not lo:
                A.add(K.lathe([(0.5, 1.72), (0.5, 1.86)], 12, center=(cx, cy, 0)), A.pal("steel"))
                for dy in (-0.36, 0.36):
                    f = K.slab(0.42, 0.05, 0.62, 1.8, 0.04, 0, 0, simple, cx=cx, cy=cy + dy)
                    A.add(f, A.pal("cyan_dark"))
                tire = K.lathe([(0.48, -0.25), (0.72, -0.25), (0.82, -0.15), (0.82, 0.15), (0.72, 0.25), (0.48, 0.25)],
                               nw, closed_profile=True)
                K.transform(tire, Matrix.Rotation(math.radians(90), 4, "X"))
                K.move(tire, (cx, cy, 0.82))
                A.add(tire, A.pal("rubber"))
                hub = K.lathe([(0.49, -0.21), (0.49, 0.21)], nw)
                K.transform(hub, Matrix.Rotation(math.radians(90), 4, "X"))
                K.move(hub, (cx, cy, 0.82))
                A.add(hub, A.pal("cream"))
                cap = K.lathe([(0.2, -0.31), (0.2, 0.31)], 8)
                K.transform(cap, Matrix.Rotation(math.radians(90), 4, "X"))
                K.move(cap, (cx, cy, 0.82))
                A.add(cap, A.pal("cyan"))
            else:
                A.add(K.slab(0.3, 0.42, 0.82, 1.9, 0.02, 0, 0, simple, cx=cx, cy=cy), A.pal("cyan_dark"))
                w = K.lathe([(0.0, -0.25), (0.82, -0.2), (0.82, 0.2), (0.0, 0.25)], nw)
                K.transform(w, Matrix.Rotation(math.radians(90), 4, "X"))
                K.move(w, (cx, cy, 0.82))
                A.add(w, A.pal("rubber"))
    return A


# =====================================================================================
# 8. Colis accordéon 8 x 8 x 4 (temporaire) — soufflet rose plissé, couvercle à jauge circulaire
# =====================================================================================
def accordion_parcel(lod):
    A = new_asset("reception_accordion_parcel", lod)
    q = A.q
    rng = random.Random(SEED + 8)
    A.add(K.slab(4.0, 4.0, 0.0, 0.5, 0.55, 0.15, 0.08, q), A.pal("pink"))
    N = 7 if q.detail else 4
    z0, z1 = 0.5, 3.52
    h = (z1 - z0) / N
    rings, offs = [], []
    for k in range(2 * N + 1):
        z = z0 + k * h / 2
        if k % 2:
            ins = 0.1 + rng.uniform(0.0, 0.07)
        else:
            ins = 0.58 + rng.uniform(-0.05, 0.05) if 0 < k < 2 * N else 0.6
        rings.append((ins, z, 0.25))
        wob = 0.0 if k in (0, 2 * N) else 1.0
        offs.append((wob * rng.uniform(-0.06, 0.06), wob * rng.uniform(-0.06, 0.06)))
    bel = K.loft(4.0, 4.0, 0.55, rings, seg(q, 5))
    zmap = {round(r[1], 5): o for r, o in zip(rings, offs)}
    for v in bel.verts:
        o = zmap.get(round(v.co.z, 5))
        if o:  # léger flottement des plis : l'objet paraît fragile
            v.co.x += o[0]
            v.co.y += o[1]
    A.add(bel, K.r_box("s_pleat", A.bbox))
    lid = K.slab(4.0, 3.97, 3.48, 3.96, 0.55, 0.1, 0.22, q, min_corner=2)
    A.add(lid, split(K.r_top_faces(3.9, 0.8), K.r_const(K.m_top("accordion_top", -4, 4, -4, 4)), A.pal("pink")))
    bz = [(2.36, 3.92), (2.64, 3.92), (2.64, 3.98), (2.6, 4.0), (2.4, 4.0), (2.36, 3.98)]
    A.add(K.lathe(bz, seg(q, 48, 16), closed_profile=True), A.pal("navy"))
    if q.detail:
        lab = K.slab(0.55, 0.015, 3.59, 3.73, 0.02, 0, 0, q, cx=-2.0, cy=3.982)
        A.add(lab, split(lambda c, n: n.y > 0.5,
                         K.r_const(K.m_plane("label_small", (-2.0, 4.0, 3.66), (-1, 0, 0), (0, 0, 1), 1.1, 0.14)),
                         A.pal("white")))
    return A


# =====================================================================================
# 9. Machine signature : Le Tamponneur 18 x 12 x 20
# =====================================================================================
def stamp_machine(lod):
    A = new_asset(MACHINE_ID, lod)
    q = A.q
    lo = q.lod > 0
    coral = K.r_box("s_coral", A.bbox)
    sy0 = 2.2  # axe de presse (devant la colonne)
    A.add(K.slab(9.0, 6.0, 0.0, 0.7, 1.4, 0.05 if not lo else 0, 0.12, q), A.pal("navy"))  # socle
    A.add(K.slab(8.2, 5.4, 0.7, 2.8, 2.6, 0.1 if not lo else 0, 0.6, q), coral)  # pied arrondi
    # coussin tamponné (passepoil jaune) — le même colis oreiller que dans la salle
    cush_r = [(0.25, 2.75), (0.08, 2.9), (0.0, 3.3), (0.12, 3.62), (0.35, 3.76), (0.9, 3.82), (1.6, 3.84)]
    if lo:
        cush_r = [(0.0, 2.75), (0.0, 3.5), (0.5, 3.84)]
    A.add(K.loft(3.3, 2.5, 0.7, cush_r, seg(q, 4), 0.0, sy0),
          split(lambda c, n: n.z > 0.5, K.r_const(K.m_top("pillow_top", -3.3, 3.3, sy0 - 2.5, sy0 + 2.5)),
                K.r_box("s_fabric", A.bbox)))
    if not lo:
        A.add(K.tube([(x, y + sy0, 3.6) for x, y in K.rrect(3.2, 2.42, 0.6, 3)], 0.11, 6, closed=True),
              A.pal("yellow"))
    # colonne arrière ajourée : chaîne cyan visible derrière deux vitres latérales
    ccy = -3.2
    col = K.slab(4.6, 2.2, 2.6, 13.4, 1.0, 0.0, 0.4, q, cy=ccy)
    if not lo:
        c = K.slab(1.4, 4.0, -5.0, 5.0, 0.9, 0, 0, q)
        K.orient(c, "x")
        K.move(c, (0, ccy, 8.0))
        col = K.boolean_diff(col, [c])
    A.add(col, coral)
    for sx in (-1, 1):
        if not lo:
            fr = K.ring_prism(K.rrect(1.75, 4.35, 1.25, 4), K.rrect(1.4, 4.0, 0.9, 4), 4.55, 4.78)
            K.orient(fr, "x")
            if sx < 0:
                K.transform(fr, Matrix.Rotation(math.pi, 4, "Z"))
            K.move(fr, (0, ccy, 8.0))
            A.add(fr, A.pal("navy"))
            g = K.slab(0.02, 1.45, 4.0, 12.0, 0.01, 0, 0, q, cx=sx * 4.4, cy=ccy)
            A.add(g, A.pal("glass_tint"), mat=1)
        else:
            p = K.slab(0.03, 1.4, 4.0, 12.0, 0.02, 0, 0, q, cx=sx * 4.6, cy=ccy)
            A.add(p, split(lambda c, n: abs(c.y - ccy) < 1.1 and abs(n.x) > 0.5,
                           K.r_const(K.m_plane("arrow_strip", (sx * 4.63, ccy, 8.0), (0, 0, 1), (0, -sx, 0), 7.6, 2.0)),
                           A.pal("navy")))
    if not lo:
        # pignons (axe X) + chaîne à plaques alternées dans le plan YZ
        for zc in (5.3, 10.7):
            pts = []
            for i in range(20):
                a = 2 * math.pi * i / 20
                r = 0.92 if i % 2 == 0 else 0.76
                pts.append((r * math.cos(a), r * math.sin(a)))
            for gx in (-3.6, 3.6):  # un pignon derrière chaque vitre
                g = K.prism(pts, -0.15, 0.15)
                K.orient(g, "x")
                K.move(g, (gx, ccy, zc))
                A.add(g, A.pal("cyan_dark"))
            hb = K.lathe([(0.32, -3.9), (0.32, 3.9)], 10)
            K.transform(hb, Matrix.Rotation(math.radians(90), 4, "Y"))
            K.move(hb, (0, ccy, zc))
            A.add(hb, A.pal("steel"))
        rr = 1.02
        path = [(rr, 5.3 + 5.4 * i / 11) for i in range(11)]
        path += [(rr * math.cos(math.pi * i / 8), 10.7 + rr * math.sin(math.pi * i / 8)) for i in range(8)]
        path += [(-rr, 10.7 - 5.4 * i / 11) for i in range(11)]
        path += [(rr * math.cos(math.pi + math.pi * i / 8), 5.3 + rr * math.sin(math.pi + math.pi * i / 8))
                 for i in range(8)]
        L = len(path)
        st = [(0.19 + 0.12 * math.cos(math.radians(a)), 0.12 * math.sin(math.radians(a))) for a in (-90, 0, 90)]
        st += [(-0.19 + 0.12 * math.cos(math.radians(a)), 0.12 * math.sin(math.radians(a))) for a in (90, 180, 270)]
        for i in range(L):
            (y0, z0), (y1, z1) = path[i], path[(i + 1) % L]
            a = math.atan2(z1 - z0, y1 - y0)
            ca, sa = math.cos(a), math.sin(a)
            M = Matrix(((0, 0, 1, 3.95 if i % 2 else 3.82), (ca, -sa, 0, ccy + (y0 + y1) / 2),
                        (sa, ca, 0, (z0 + z1) / 2), (0, 0, 0, 1)))
            for side in (1, -1):
                pl = K.prism(st, -0.04, 0.04)
                K.transform(pl, Matrix.Scale(-1, 4, (1, 0, 0)) @ M if side < 0 else M)
                K.solid(pl)
                A.add(pl, A.pal("cyan"))
    # tête : gros bloc corail très arrondi, deux yeux mécaniques
    A.add(K.slab(7.2, 5.1, 12.6, 19.0, 2.2, 0.6, 1.1, q, cy=-0.5), coral)
    for sx in (-1, 1):
        ex, ez = sx * 3.0, 15.9
        if not lo:
            bez = K.lathe([(1.35, 0.0), (1.75, 0.0), (1.8, 0.15), (1.72, 0.35), (1.5, 0.42), (1.35, 0.35)], 20,
                          closed_profile=True)
            K.transform(bez, Matrix.Rotation(math.radians(-90), 4, "X"))
            K.move(bez, (ex, 4.55, ez))
            A.add(bez, A.pal("navy"))
            ball = K.lathe([(1.4, 0.0), (1.36, 0.22), (1.18, 0.44), (0.82, 0.6), (0.0, 0.68)], 20)
        else:
            ball = K.lathe([(1.78, 0.0), (1.78, 0.32), (1.3, 0.48), (0.0, 0.68)], 8)
        K.transform(ball, Matrix.Rotation(math.radians(-90), 4, "X"))
        K.move(ball, (ex, 4.5, ez))
        eye = K.m_plane("eye", (ex - sx * 0.22, 5.0, ez - 0.3), (-1, 0, 0), (0, 0, 1), 2.8, 2.8)
        A.add(ball, split(lambda c, n, ex=ex, ez=ez: math.hypot(c.x - ex, c.z - ez) > 1.42,
                          A.pal("navy"), K.r_const(eye)))
        step = 14 if not lo else 35
        lid_pts = [(1.58 * math.sin(math.radians(a)), 1.58 * math.cos(math.radians(a))) for a in range(-70, 71, step)]
        lid = K.prism([(v, u) for u, v in lid_pts], 4.75, 5.3)  # local x -> monde Z, local y -> monde X
        K.orient(lid, "y")
        K.transform(lid, Matrix.Rotation(math.radians(-12 * sx), 4, "Y"))
        K.move(lid, (ex, 0, ez + 0.05))
        A.add(lid, A.pal("machine_dark"))
    mouth = K.slab(1.0, 0.04, 13.4, 14.3, 0.25, 0, 0, q, cy=4.58)
    A.add(mouth, split(lambda c, n: n.y > 0.5,
                       K.r_const(K.m_plane("vents", (0, 4.62, 13.85), (-1, 0, 0), (0, 0, 1), 2.0, 0.9)),
                       A.pal("machine_dark")))
    # gyrophare cyan sur le dessus
    if not lo:
        A.add(K.lathe([(0.8, 18.95), (0.8, 19.3), (0.7, 19.32)], 20, center=(0, -0.5, 0)), A.pal("navy"))
        A.add(K.lathe([(0.62, 19.28), (0.6, 19.58), (0.46, 19.86), (0.22, 19.98), (0.0, 20.0)], 20,
                      center=(0, -0.5, 0)), A.pal("cyan"))
    else:
        A.add(K.lathe([(0.7, 18.95), (0.62, 19.5), (0.0, 20.0)], 8, center=(0, -0.5, 0)), A.pal("cyan"))
    if not lo:
        for sx in (-1, 1):
            v = K.slab(0.04, 1.9, 14.6, 16.8, 0.3, 0, 0, q, cx=sx * 7.2, cy=-0.6)
            A.add(v, split(lambda c, n, sx=sx: n.x * sx > 0.5,
                           K.r_const(K.m_plane("vents", (sx * 7.25, -0.6, 15.7), (0, sx, 0), (0, 0, 1), 3.8, 2.2)),
                           A.pal("machine_dark")))
            # flexibles tête -> colonne
            P0, P1, P2, P3 = (Vector((sx * 5.6, -3.4, 13.2)), Vector((sx * 6.5, -3.6, 11.6)),
                              Vector((sx * 5.6, -3.4, 10.0)), Vector((sx * 4.55, -3.3, 9.6)))
            pts = []
            for i in range(11):
                t = i / 10
                p = (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t * t * P2 + t ** 3 * P3
                pts.append(tuple(p))
            A.add(K.tube(pts, 0.28, 8, up=(0, 1, 0)), A.pal("navy"))
        badge = K.lathe([(0.6, 0.0), (0.6, 0.1), (0.53, 0.15), (0.0, 0.15)], 20)
        K.transform(badge, Matrix.Rotation(math.radians(-90), 4, "X"))
        K.move(badge, (0, 4.55, 17.2))
        A.add(badge, K.r_const(K.m_plane("machine_badge", (0, 4.7, 17.2), (-1, 0, 0), (0, 0, 1), 1.2, 1.2)))
    # vérin : collerette, soufflet, tige
    if not lo:
        A.add(K.lathe([(0.95, 12.45), (1.0, 12.55), (1.0, 12.95), (0.9, 13.05)], 20, center=(0, sy0, 0)),
              A.pal("cyan"))
        prof = [(0.95 if k % 2 else 0.72, 10.4 + 2.05 * k / 10) for k in range(11)]
        A.add(K.lathe(prof, 20, center=(0, sy0, 0)), A.pal("navy"))
        A.add(K.lathe([(0.5, 7.9), (0.5, 12.5)], 16, center=(0, sy0, 0)), A.pal("steel"))
        A.add(K.lathe([(0.9, 7.55), (0.9, 7.95), (0.6, 8.05)], 20, center=(0, sy0, 0)), A.pal("yellow_dark"))
    else:
        A.add(K.lathe([(0.8, 7.55), (0.55, 8.0), (0.9, 13.0)], 6, center=(0, sy0, 0)), A.pal("navy"))
    # gros tampon jaune + semelle encreuse
    A.add(K.slab(3.6, 2.6, 5.6, 7.6, 0.9, 0.25 if not lo else 0, 0.5, q, cy=sy0), A.pal("yellow"))
    if not lo:
        A.add(K.slab(3.35, 2.35, 5.1, 5.66, 0.8, 0.06, 0.04, q, cy=sy0),
              split(lambda c, n: n.z < -0.8, K.r_const(K.m_top("stamp_face", -3.35, 3.35, sy0 - 2.35, sy0 + 2.35)),
                    A.pal("navy")))
    else:
        A.add(K.slab(3.35, 2.35, 5.1, 5.66, 0.02, 0, 0, K.Q(1), cy=sy0), A.pal("navy"))
    # plaque de commande sur le pied
    pp = K.slab(0.55, 2.2, 5.36, 5.44, 0.2, 0, 0, K.Q(1) if lo else q)
    K.orient(pp, "y")
    K.move(pp, (0, 0, 1.6))
    A.add(pp, split(lambda c, n: n.y > 0.5,
                    K.r_const(K.m_plane("machine_panel", (0, 5.44, 1.6), (-1, 0, 0), (0, 0, 1), 4.4, 1.1)),
                    A.pal("machine_dark")))
    # goulotte d'éjection (+X) avec un carton intact qui glisse
    ang = math.atan2(2.0, 2.6)
    L = math.hypot(2.6, 2.0)
    ch = K.slab(L / 2, 1.5, -0.07, 0.07, 0.3, 0, 0, K.Q(1) if lo else q)
    M = Matrix.Translation((6.25 + 1.3, 0, 2.75 - 1.0)) @ Matrix.Rotation(ang, 4, "Y")
    K.transform(ch, M)
    A.add(ch, A.pal("cyan"))
    if not lo:
        for sy in (-1, 1):
            a = M @ Vector((-L / 2, sy * 1.5, 0.12))
            b = M @ Vector((L / 2 - 0.1, sy * 1.5, 0.12))
            A.add(K.tube([tuple(a), tuple(b)], 0.09, 6, up=(0, 1, 0)), A.pal("navy"))
        box = K.slab(0.62, 0.55, 0.0, 0.85, 0.12, 0.04, 0.06, K.Q(1))
        K.transform(box, M @ Matrix.Translation((0.35, 0.0, 0.07)))
        A.add(box, A.pal("kraft"))
        tp = K.slab(0.63, 0.14, 0.4, 0.86, 0.02, 0, 0, K.Q(1))
        K.transform(tp, M @ Matrix.Translation((0.35, 0.0, 0.07)))
        A.add(tp, A.pal("cyan"))
    return A


BUILDERS = {
    "reception_carton": carton,
    "reception_foam_crate": foam_crate,
    "reception_suitcase": suitcase,
    "reception_pallet": pallet,
    "reception_tape_reel": tape_reel,
    "reception_pillow_parcel": pillow_parcel,
    "reception_mail_cart": mail_cart,
    "reception_accordion_parcel": accordion_parcel,
    MACHINE_ID: stamp_machine,
}


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
    m = bpy.data.materials.new("M_reception_atlas")
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
        bsdf.inputs["Specular IOR Level"].default_value = 0.45
    g = bpy.data.materials.new("M_reception_glass")
    g.use_nodes = True
    gb = g.node_tree.nodes.get("Principled BSDF")
    gb.inputs["Base Color"].default_value = (0.85, 0.97, 1.0, 1.0)
    gb.inputs["Roughness"].default_value = 0.05
    gb.inputs["Alpha"].default_value = 0.12
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


def collision_entry(pid):
    s = spec(pid)
    c = s["collider"]
    w, d, h = c["size_studs"]
    return {
        "asset_id": pid,
        "behavior": s["behavior"],
        "behavior_params": s.get("behavior_params", {}),
        "pivot": "bottom_center",
        "forward_axis": "-Z",
        "visual_envelope_studs_wdh": s["size_studs"],
        "collider": {"shape": c["shape"], "size_studs_config": [w, d, h], "size_vector3_roblox": [w, h, d],
                     "offset_from_pivot_roblox": [0, h / 2, 0], "tags": ["FillCollider"], "can_collide": True},
        "walkable_top": {"size_studs": c["walkable_top"], "height_studs": h, "center_roblox": [0, h, 0]},
        "visual_mesh": {"can_collide": False, "can_query": False, "can_touch": False},
    }


def main():
    random.seed(SEED)
    os.makedirs(TEX_DIR, exist_ok=True)
    os.makedirs(IMPORT_DIR, exist_ok=True)
    col_png, rough_png = atlas.save_atlas(TEX_DIR)
    reset_scene()
    mat, glass, imgs = make_materials(col_png, rough_png)
    info = {"family": "reception", "seed": SEED, "blender_version": bpy.app.version_string,
            "units": "1 BU = 1 stud (décision 0003)", "atlas": os.path.relpath(col_png, ROOT),
            "atlas_roughness_metal": os.path.relpath(rough_png, ROOT), "assets": {}}
    only = sys.argv[1:] or list(BUILDERS)
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
        base = os.path.join(IMPORT_DIR, pid)
        export(objs[0], base + ".glb", base + ".fbx")
        export(objs[1], base + "_lod1.glb")
        objs[1].hide_set(True)
        objs[1].hide_render = True
        dims = [round(v, 4) for v in objs[0].dimensions]
        info["assets"][pid] = {
            "lod0_object": objs[0].name, "lod1_object": objs[1].name,
            "lod0_tris": tris(objs[0]), "lod1_tris": tris(objs[1]),
            "lod0_dims_wdh": dims, "lod1_dims_wdh": [round(v, 4) for v in objs[1].dimensions],
            "materials": [m.name for m in objs[0].data.materials],
            "exports": [os.path.relpath(base + e, ROOT) for e in (".glb", "_lod1.glb", ".fbx")],
        }
        print(pid, info["assets"][pid]["lod0_tris"], info["assets"][pid]["lod1_tris"], dims, flush=True)
    for im in imgs:
        im.pack()
    bpy.context.preferences.filepaths.save_version = 0
    blend = os.path.join(MODEL_DIR, "reception_props.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    info["blend"] = os.path.relpath(blend, ROOT)
    if len(only) == len(BUILDERS):
        with open(os.path.join(MODEL_DIR, "build_info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        coll = {"family": "reception", "units": "studs", "axes": "roblox_model_space (X largeur, Y haut, Z profondeur ; avant = -Z)",
                "authority": "server_collider_separate_from_visual_mesh",
                "props": [collision_entry(p) for p in BUILDERS if p != MACHINE_ID],
                "machine": {"asset_id": MACHINE_ID, "envelope_studs_wdh": spec(MACHINE_ID)["size_studs"],
                            "note": "Derrière une vitre, hors volume jouable : collision du parcours séparée."}}
        with open(os.path.join(MODEL_DIR, "collision_reception.json"), "w", encoding="utf-8") as f:
            json.dump(coll, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
