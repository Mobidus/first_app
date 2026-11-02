"""Construit les 8 props + la machine signature de la famille Bureau perdu (Blender headless).

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/build_props_bureau.py

Sorties :
    assets/source/models/bureau/bureau_props.blend          (toutes les sources, atlas empaqueté)
    assets/source/models/bureau/textures/bureau_atlas_1024.png
    assets/source/models/bureau/build_info.json            (mesures, colliders, sockets)
    assets/import/models/<id>.glb, <id>_lod1.glb, <id>.fbx

Conventions (identiques à build_plush.py / décision 0003) : 1 unité Blender = 1 stud,
X largeur, Y profondeur, Z hauteur ; avant Roblox (-Z) = +Y Blender ; pivot bottom_center
(origine au centre de l'empreinte, au sol). Un seul matériau par maillage (atlas partagé
1 024 px de la famille). Les dimensions et colliders sont lus dans config/rooms.json.

Contrat gameplay respecté par construction : enveloppe = size_studs, dessus plat à la hauteur
du collider sur toute l'empreinte walkable_top (biseaux de bord <= 0,2 stud, joints <= 0,2 stud).
Le LOD1 est un second dessin simplifié (mêmes enveloppe et dessus), pas une décimation.
Graine fixe : SEED (aléas de pile, de feuilles, d'angles).
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
from mathutils import Vector  # noqa: E402

import bureau_kit as K  # noqa: E402
from bureau_kit import (T, Rx, Ry, Rz, box, catmull, coil_along, cyl, frame, grid_slab, loft,  # noqa: E402
                        prism, round_poly, top_edges, tube, xf)

SEED = 4207
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # filling_up/
MODEL_DIR = os.path.join(ROOT, "assets", "source", "models", "bureau")
TEX_DIR = os.path.join(MODEL_DIR, "textures")
IMPORT_DIR = os.path.join(ROOT, "assets", "import", "models")
ATLAS_FILE = os.path.join(TEX_DIR, "bureau_atlas_1024.png")
BLEND_FILE = os.path.join(MODEL_DIR, "bureau_props.blend")

ASSET_ORDER = ["bureau_paper_ream", "bureau_binder_stack", "bureau_desk", "bureau_locker", "bureau_keyboard",
               "bureau_rail_chair", "bureau_spring_phone", "bureau_loose_files", "machine_bureau_copier"]


def load_family():
    with open(os.path.join(ROOT, "config", "rooms.json"), encoding="utf-8") as f:
        fam = next(x for x in json.load(f)["families"] if x["id"] == "bureau")
    specs = {p["id"]: p for p in fam["props"]}
    specs[fam["machine"]["id"]] = dict(fam["machine"], collider=None, behavior="machine")
    return fam, specs


def rng_for(asset_id):
    # graine stable (pas de hash() Python, randomisé par processus)
    return random.Random(SEED * 1000 + ASSET_ORDER.index(asset_id))


def rot_dir(ang, d):
    v = Rz(ang).to_3x3() @ Vector(d)
    return tuple(v)


# ===========================================================================
# 1. Ramette géante 10 x 8 x 3
def build_paper_ream(mb, lod, rng):
    L0 = lod == 0
    n = 6 if L0 else 1
    t = 2.92 / n
    side_dec = [dict(dir=(-1, 0, 0), name="sheet_edges"), dict(dir=(0, 1, 0), name="sheet_edges"),
                dict(dir=(0, -1, 0), name="sheet_edges"), dict(dir=(1, 0, 0), name="sheet_edges")]
    for i in range(n):
        jx = rng.uniform(0.02, 0.16) if (L0 and i != n - 1) else 0.0
        jy = rng.uniform(-0.015, 0.015) if L0 else 0.0
        b = box((-5.0 + jx, -3.965 + jy, i * t), (4.9, 3.965 + jy, (i + 1) * t - (0.012 if L0 else 0)),
                r=0.05 if L0 else 0, seg=2)
        mb.add(b, "cream", side_dec)
    if L0:  # deux feuilles qui dépassent de la tranche ouverte
        for (zz, ang, dx) in ((t * 2, 3.5, -0.05), (t * 4, -2.5, -0.04)):
            s = box((-4.7, -3.5, zz - 0.02), (2.0, 3.5, zz + 0.015))
            xf(s, T(dx, 0, 0) @ Rz(ang, (-1.5, 0, zz)))
            mb.add(s, "paper", [dict(dir=(0, 0, 1), name="sheet_text", cos=0.9)])
    # emballage (papier blanc, liserés cyan, étiquette)
    wr = box((-3.0, -4.0, 0.0), (5.0, 4.0, 3.0), r=0.08 if L0 else 0, seg=3,
             sel=lambda e, z0, z1: abs(e.verts[0].co.x - e.verts[1].co.x) > 1e-4)
    mb.add(wr, "paper", [dict(dir=(0, 0, 1), name="ream_label", cos=0.9),
                         dict(dir=(0, 1, 0), name="ream_side", cos=0.9),
                         dict(dir=(0, -1, 0), name="ream_side", cos=0.9)])
    if L0:
        # bord déchiré de l'emballage (dents en zigzag) sur le dessus, l'avant et l'arrière
        top = [(-2.95, -4.0)]
        for k in range(15):
            y = -4.0 + 8.0 * (k + 0.5) / 15
            top.append((-3.0 - (0.42 if k % 2 else 0.18) - rng.uniform(0, 0.12), y))
        top.append((-2.95, 4.0))
        mb.add(prism(top, "Z", 2.935, 2.995), "paper")
        for (y0, y1) in ((3.935, 3.995), (-3.995, -3.935)):
            fr = [(-2.95, 0.0)]
            for k in range(6):
                z = 3.0 * (k + 0.5) / 6
                fr.append((-3.0 - (0.4 if k % 2 else 0.16) - rng.uniform(0, 0.1), z))
            fr.append((-2.95, 3.0))
            mb.add(prism(fr, "Y", y0, y1), "paper", [dict(dir=(0, 1, 0), name="ream_side", cos=0.9, range=(-6, 6, 0, 3)),
                                                      dict(dir=(0, -1, 0), name="ream_side", cos=0.9, range=(-6, 6, 0, 3))])
        # pliage « paquet cadeau » de l'extrémité droite
        mb.add(prism([(4.0, 0.0), (4.0, 3.0), (2.5, 1.5)], "X", 5.0, 5.02), "paper_shade")
        mb.add(prism([(-4.0, 0.0), (-2.5, 1.5), (-4.0, 3.0)], "X", 5.0, 5.02), "paper_shade")
        mb.add(prism([(-4.0, 0.02), (4.0, 0.02), (2.2, 1.6), (-2.2, 1.6)], "X", 5.02, 5.042), "paper")
        mb.add(prism([(-4.0, 2.98), (-2.4, 1.3), (2.4, 1.3), (4.0, 2.98)], "X", 5.042, 5.064), "paper",
               [dict(dir=(1, 0, 0), name="ream_side", cos=0.9, range=(-4, 4, 1.0, 3.0))])
        mb.add(cyl((5.06, 0, 1.45), 0.42, 0.02, sides=16, axis="X"), "turquoise")
    else:
        mb.add(prism([(-4.0, 0.0), (4.0, 0.0), (4.0, 3.0), (-4.0, 3.0)], "X", 5.0, 5.05), "paper_shade")


# ===========================================================================
# 2. Classeurs empilés 8 x 8 x 5
def binder(mb, lod, W, D, z0, color, k, ang, dx, dy, top=False):
    L0 = lod == 0
    Th, ct = 1.25, 0.13
    M = T(dx, dy, z0) @ Rz(ang)
    fwd = rot_dir(ang, (0, 1, 0))

    def put(bm, paint, dec=()):
        mb.add(xf(bm, M), paint, dec)

    put(box((-W / 2, -D / 2, 0), (W / 2, D / 2 - 0.4, ct), r=0.04 if L0 else 0, seg=1), color)
    put(box((-W / 2, -D / 2, Th - ct), (W / 2, D / 2 - 0.4, Th), r=0.04 if L0 else 0, seg=1), color,
        [dict(dir=(0, 0, 1), name="binder_cover", cos=0.9)] if top else ())
    sp = [(D / 2 - 0.62, 0.006), (D / 2, 0.006), (D / 2, Th - 0.006), (D / 2 - 0.62, Th - 0.006)]
    put(prism(round_poly(sp, [0, 0.34, 0.34, 0], seg=3 if L0 else 1), "X", -W / 2, W / 2), color,
        [dict(dir=fwd, name=f"binder_spine_{k}", cos=0.85, up=(0, 0, 1))])
    put(box((-W / 2 + 0.25, -D / 2 + 0.18, ct), (W / 2 - 0.25, D / 2 - 0.45, Th - ct)), "cream",
        [dict(dir=rot_dir(ang, (-1, 0, 0)), name="sheet_edges"), dict(dir=rot_dir(ang, (1, 0, 0)), name="sheet_edges"),
         dict(dir=rot_dir(ang, (0, -1, 0)), name="sheet_edges")])
    if L0:
        # trou de préhension (anneau métal + fond sombre) sur le dos
        hx = -(W / 2 - 1.55)            # côté droit vu de face = -X
        put(cyl((hx, D / 2 - 0.06, Th / 2), 0.3, 0.08, sides=12, axis="Y"), "navy")
        ring = [Vector((hx + 0.36 * math.cos(a), D / 2 - 0.07, Th / 2 + 0.36 * math.sin(a)))
                for a in [2 * math.pi * i / 14 for i in range(14)]]
        put(tube(ring, 0.055, sides=4, closed=True), "metal", ())
        # intercalaires colorés qui dépassent des feuilles (côté -X)
        for j, (yy, col) in enumerate(((-2.2, "mint"), (-0.4, "yellow"), (1.4, "coral"))):
            zt = ct + 0.18 + 0.27 * ((j + k) % 3)
            put(box((-W / 2 + 0.03, yy - 0.42, zt), (-W / 2 + 0.3, yy + 0.42, zt + 0.06)), col)


def build_binder_stack(mb, lod, rng):
    cfg = [(7.5, 7.4, "pink", -2.4), (7.55, 7.45, "lavender", 1.9), (7.6, 7.5, "pink", -1.3)]
    for i, (W, D, col, ang) in enumerate(cfg):
        dx = rng.uniform(-0.04, 0.04)
        dy = rng.uniform(-0.05, 0.03)
        binder(mb, lod, W, D, i * 1.25, col, i, ang, dx, dy)
    binder(mb, lod, 8.0, 8.0, 3.75, "lavender", 3, 0.0, 0.0, 0.0, top=True)


# ===========================================================================
# 3. Bureau 16 x 10 x 7
def build_desk(mb, lod, rng):
    L0 = lod == 0
    r = 0.15 if L0 else 0
    mb.add(box((-8, -5, 6.35), (8, 5, 6.96), r=r, seg=3), "turquoise")
    if L0:   # passe-câble affleurant + liseré de chant clair
        mb.add(cyl((-6.6, -3.9, 6.94), 0.45, 0.035, sides=14), "teal_dark")
        mb.add(cyl((-6.6, -3.9, 6.95), 0.3, 0.03, sides=14), "navy")
    mb.add(box((-5.5, -3.8, 6.9), (5.5, 3.4, 7.0), r=0.04 if L0 else 0, seg=1), "lavender_light")
    for sx in (-1, 1):
        x0, x1 = sorted((sx * 3.0, sx * 7.75))
        mb.add(box((x0, -4.75, 0.7), (x1, 4.6, 6.35), r=0.1 if L0 else 0, seg=2), "turquoise")
        # pieds fuselés (silhouette de meuble de bureau, caisson plein au-dessus)
        for fx in (x0 + 0.55, x1 - 0.55):
            for fy in (-4.2, 4.05):
                mb.add(cyl((fx, fy, 0.0), 0.3, 0.72, sides=12 if L0 else 5, r_top=0.42), "navy")
                if L0:
                    mb.add(cyl((fx, fy, 0.0), 0.33, 0.08, sides=12), "metal")
    mb.add(box((-3.0, -4.6, 0.7), (3.0, 3.4 if L0 else 3.6, 5.55)), "teal_dark")      # retrait du plan de jambes
    mb.add(box((-2.9, 3.2, 5.62), (2.9, 4.72, 6.33), r=0.06 if L0 else 0, seg=1), "teal_dark")  # tiroir à crayons
    drawers = [(-1, 0.9, 2.65, "drawer_a4"), (-1, 2.8, 4.45, None), (-1, 4.6, 6.2, None),
               (1, 0.9, 4.0, "drawer_a3"), (1, 4.15, 6.2, None)]
    for (sx, z0, z1, lab) in drawers:
        x0, x1 = sorted((sx * 3.25, sx * 7.5))
        xc = (x0 + x1) / 2
        mb.add(box((x0, 4.55, z0), (x1, 4.75, z1), r=0.08 if L0 else 0, seg=2, skip=[(0, -1, 0)]), "teal_dark")
        zh = z1 - 0.45
        mb.add(cyl((xc - 0.9, 4.88, zh), 0.09, 1.8, sides=10 if L0 else 4, axis="X"), "cream")
        if L0:
            for ox in (-0.75, 0.75):
                mb.add(cyl((xc + ox, 4.74, zh), 0.065, 0.14, sides=6, axis="Y"), "cream")
            if lab:
                mb.add(box((xc - 0.4, 4.75, z1 - 1.15), (xc + 0.4, 4.78, z1 - 0.75)), "white",
                       [dict(dir=(0, 1, 0), name=lab, cos=0.9)])
    mb.add(cyl((-0.6, 4.86, 5.97), 0.07, 1.2, sides=8 if L0 else 4, axis="X"), "cream")
    if L0:
        note = box((-7.78, -1.0, 3.3), (-7.75, 0.2, 4.5))
        xf(note, Rx(5, (-7.76, -0.4, 3.9)))
        mb.add(note, "yellow", [dict(dir=(-1, 0, 0), name="desk_note", cos=0.9)])


# ===========================================================================
# 4. Casier couché 12 x 8 x 6 (portes vers l'avant, socle d'origine en -X)
def build_locker(mb, lod, rng):
    L0 = lod == 0
    mb.add(box((-5.55, -4.0, 0.28), (6.0, 3.78, 6.0), r=0.12 if L0 else 0, seg=3), "lavender",
           [dict(dir=(0, 0, 1), name="locker_top", cos=0.95)])
    mb.add(box((-6.0, -4.0, 0.55), (-5.55, 4.0, 6.0), r=0.06 if L0 else 0, seg=2), "navy")   # socle (fond d'origine)
    for fx in (-4.9, 5.3):          # patins caoutchouc : le casier couché ne repose pas à plat
        for fy in (-3.3, 3.1):
            mb.add(cyl((fx, fy, 0.0), 0.36, 0.3, sides=12 if L0 else 6, r_top=0.3), "rubber")
    fr = 0.05 if L0 else 0
    for (a, b) in (((-5.2, 3.78, 5.62), (5.62, 4.0, 6.0)), ((-5.2, 3.78, 0.28), (5.62, 4.0, 0.6)),
                   ((-5.2, 3.78, 2.95), (5.62, 4.0, 3.15)), ((5.62, 3.78, 0.28), (6.0, 4.0, 6.0)),
                   ((-5.55, 3.78, 0.28), (-5.2, 4.0, 6.0))):
        mb.add(box(a, b, r=fr, seg=1), "lavender")
    for (z0, z1, card, hinge_z) in ((3.15, 5.62, "locker_card_7", 5.62), (0.6, 2.95, "locker_card_8", 0.6)):
        zc = (z0 + z1) / 2
        if L0:
            mb.add(box((-5.2, 3.76, z0), (5.62, 3.92, z1), r=0.05, seg=2, skip=[(0, -1, 0)]), "lavender_light")
            mb.add(box((-4.95, 3.9, zc - 0.85), (-2.95, 3.935, zc + 0.85)), "navy")
            for k in range(6):
                sl = box((-0.14, -0.022, -0.8), (0.14, 0.022, 0.8))
                xf(sl, T(-4.72 + k * 0.33, 3.9, zc) @ Rz(38))
                mb.add(sl, "lavender_light")
            mb.add(box((3.4, 3.9, zc - 0.45), (4.6, 3.935, zc + 0.45), r=0.03, seg=1), "navy")
            mb.add(box((3.55, 3.92, zc - 0.12), (4.45, 3.99, zc + 0.12), r=0.035, seg=1), "metal")
            mb.add(box((0.9, 3.9, zc + 0.3), (2.5, 3.945, zc + 1.0)), "white", [dict(dir=(0, 1, 0), name=card, cos=0.9)])
            for hx in (-1.6, 2.9):
                mb.add(cyl((hx, 3.88, hinge_z), 0.1, 0.7, sides=8, axis="X"), "metal")
        else:
            mb.add(box((-5.2, 3.76, z0), (5.62, 3.92, z1)), "lavender_light",
                   [dict(dir=(0, 1, 0), name="locker_door_lod", cos=0.9)])


# ===========================================================================
# 5. Clavier géant 14 x 7 x 2
def build_keyboard(mb, lod, rng, atlas):
    L0 = lod == 0
    prof = [(3.5, 1.88), (3.5, 1.5), (3.0, 0.3), (-3.15, 0.3), (-3.5, 0.75), (-3.5, 1.88)]
    if L0:
        prof = round_poly(prof, [0.1, 0.18, 0.12, 0.12, 0.18, 0.1], seg=2)
    mb.add(prism(prof, "X", -7.0, 7.0, bevel=0.1 if L0 else 0, seg=2), "yellow")
    if L0:
        for i, k in enumerate(K.keyboard_layout()):
            kb = box((k["x0"], k["y0"], 1.72), (k["x1"], k["y1"], 2.0), r=0.07, seg=1, sel=top_edges,
                     skip=[(0, 0, -1)])
            mb.add(kb, k["color"], [dict(dir=(0, 0, 1), rect=atlas.key_cells[i], cos=0.9)])
        for j, (x, c) in enumerate(((-5.55, "mint"), (-5.2, "cyan"), (-4.85, "mint"))):
            mb.add(cyl((x, -3.0, 1.84), 0.1, 0.06, sides=8), c)
        mb.add(box((4.0, -3.3, 1.86), (6.2, -2.72, 1.9)), "navy", [dict(dir=(0, 0, 1), name="brand_plate", cos=0.9)])
    else:
        mb.add(box((-6.98, -3.48, 1.85), (6.98, 3.48, 2.0)), "yellow",
               [dict(dir=(0, 0, 1), name="keyboard_top", cos=0.9, range=(-7, 7, -3.5, 3.5))])
    for sx in (-1, 1):
        x0, x1 = sorted((sx * 5.3, sx * 6.4))
        mb.add(box((x0, -3.3, 0.0), (x1, -2.65, 0.32), r=0.05 if L0 else 0, seg=1), "navy")
        mb.add(cyl((sx * 5.85, 2.55, 0.0), 0.3, 0.32, sides=10 if L0 else 6), "rubber")


# ===========================================================================
# 6. Chaise sur rail 9 x 9 x 6
def build_rail_chair(mb, lod, rng):
    L0 = lod == 0
    rail = [(-0.36, 0), (0.36, 0), (0.36, 0.1), (0.12, 0.1), (0.12, 0.38), (0.28, 0.38), (0.28, 0.55),
            (-0.28, 0.55), (-0.28, 0.38), (-0.12, 0.38), (-0.12, 0.1), (-0.36, 0.1)]
    for sy in (-2.4, 2.4):
        pr = rail if L0 else [(-0.3, 0), (0.3, 0), (0.3, 0.55), (-0.3, 0.55)]
        mb.add(prism([(y + sy, z) for (y, z) in pr], "X", -4.5, 4.5), "metal_dark")
        # butées de fin de rail
        for sx in (-1, 1):
            x0, x1 = sorted((sx * 4.5, sx * 4.15))
            mb.add(box((x0, sy - 0.42, 0.0), (x1, sy + 0.42, 0.75), r=0.06 if L0 else 0, seg=1), "coral")
    for x in ((-3.2, 0.0, 3.2) if L0 else (0.0,)):
        mb.add(box((x - 0.35, -3.3, 0.0), (x + 0.35, 3.3, 0.16)), "navy")
    if L0:
        for sx in (-2.6, 2.6):
            for sy in (-2.4, 2.4):
                mb.add(cyl((sx, sy - 0.2, 0.86), 0.31, 0.4, sides=12, axis="Y"), "navy")
                mb.add(cyl((sx, sy - 0.24, 0.86), 0.13, 0.48, sides=6, axis="Y"), "metal")
    chev = [dict(dir=(0, 1, 0), name="chevrons", cos=0.9), dict(dir=(0, -1, 0), name="chevrons", cos=0.9),
            dict(dir=(1, 0, 0), name="chevrons", cos=0.9), dict(dir=(-1, 0, 0), name="chevrons", cos=0.9)]
    mb.add(box((-3.9, -3.9, 0.9), (3.9, 3.9, 1.5), r=0.15 if L0 else 0, seg=2), "cyan", chev)
    # piètement étoile chromé + roulettes + vérin (repère « chaise de bureau »)
    mb.add(cyl((0, 0, 1.75), 0.78, 0.55, sides=16 if L0 else 6, bevel=0.08 if L0 else 0), "metal_dark")
    for k in range(5):
        a = 18 + 72 * k
        arm = prism([(0.5, 1.92), (3.5, 1.86), (3.5, 2.14), (0.5, 2.3)], "Y", -0.26, 0.26,
                    bevel=0.06 if L0 else 0, seg=1)
        mb.add(xf(arm, Rz(a)), "metal")
        c = Rz(a).to_3x3() @ Vector((3.25, 0, 0))
        if L0:
            mb.add(xf(box((-0.16, -0.16, 1.78), (0.16, 0.16, 1.92)), T(c.x, c.y, 0)), "navy")
            w = cyl((0, -0.16, 1.7), 0.2, 0.32, sides=10, axis="Y")
            mb.add(xf(w, T(c.x, c.y, 0) @ Rz(a + 90)), "rubber")
        else:
            mb.add(xf(box((-0.2, -0.2, 1.5), (0.2, 0.2, 1.9)), T(c.x, c.y, 0)), "rubber")
    mb.add(cyl((0, 0, 2.28), 0.55, 0.42, sides=14 if L0 else 6, r_top=0.44), "navy")
    mb.add(cyl((0, 0, 2.5), 0.36, 0.55, sides=14 if L0 else 6), "metal")
    mb.add(box((-1.3, -1.3, 2.92), (1.3, 1.3, 3.08)), "navy")
    if L0:
        mb.add(cyl((1.3, 0.6, 3.0), 0.06, 1.9, sides=6, axis="X"), "navy")
        mb.add(cyl((3.15, 0.6, 3.0), 0.17, 0.32, sides=8, axis="X"), "coral")
    # fauteuil-cube : socle, accoudoirs roulés, dossier rabattu, coussin
    mb.add(box((-4.3, -4.3, 3.05), (4.3, 4.3, 3.45), r=0.12 if L0 else 0, seg=2), "navy_light")
    def shell(f):   # dessus des accoudoirs/dossier clairs, flancs lavande soutenue
        return "lavender" if f.normal.z > 0.55 else "lavender_dark"

    arm_p = [(3.25, 3.4), (4.2, 3.4), (4.2, 4.6), (4.5, 5.0), (4.5, 6.0), (3.25, 6.0)]
    radii = [0, 0.08, 0.25, 0.3, 0.18, 0.12]
    seg = 3 if L0 else 0
    for sx in (-1, 1):
        p = round_poly([(sx * x, z) for (x, z) in arm_p], radii, seg=seg) if L0 else [(sx * x, z) for (x, z) in arm_p]
        mb.add(prism(p, "Y", -4.5, 4.5, bevel=0.12 if L0 else 0, seg=2), shell, smooth=50)
    back_p = [(-2.9, 3.4), (-4.2, 3.4), (-4.2, 4.6), (-4.5, 5.0), (-4.5, 6.0), (-2.9, 6.0)]
    p = round_poly(back_p, radii, seg=seg) if L0 else back_p
    mb.add(prism(p, "X", -3.25, 3.25, bevel=0.1 if L0 else 0, seg=2), shell, smooth=50)
    if L0:
        # le coussin pénètre légèrement accoudoirs et dossier : joints en V peu profonds, jamais de fente
        cush = loft([(4.5, 3.12, 3.55, 0.3), (4.62, 3.25, 3.68, 0.38), (4.78, 3.29, 3.73, 0.4), (5.66, 3.29, 3.73, 0.4),
                     (5.84, 3.25, 3.69, 0.32), (5.95, 3.1, 3.54, 0.2)], cx=0.0, cy=0.77, n=3)
        # jupe d'assise en retrait sous le coussin
        mb.add(box((-3.26, -2.92, 3.4), (3.26, 4.25, 5.8), r=0.1, seg=2), "lavender_dark")
        for sx in (-1, 1):   # cales d'angle : aucune fente verticale entre coussin et accoudoir
            x0, x1 = sorted((sx * 2.85, sx * 3.27))
            mb.add(box((x0, 4.0, 4.7), (x1, 4.47, 5.8)), "lavender_dark")
        # passepoil cyan (accent) le long du coussin et des accoudoirs
        mb.add(tube([(-3.05, 4.42, 5.82), (3.05, 4.42, 5.82)], 0.07, sides=6), "cyan", smooth=80)
        for sx in (-1, 1):
            mb.add(tube([(sx * 3.32, -4.45, 5.9), (sx * 3.32, 4.45, 5.9)], 0.065, sides=6), "cyan", smooth=80)
        mb.add(tube([(-3.3, -2.95, 5.9), (3.3, -2.95, 5.9)], 0.065, sides=6), "cyan", smooth=80)
    else:
        cush = box((-3.27, -2.93, 3.4), (3.27, 4.5, 5.95))
    mb.add(cush, "lavender_light", smooth=50)
    if L0:
        for bx in (-1.6, 0.0, 1.6):
            for by in (-0.6, 2.2):
                mb.add(cyl((bx, by, 5.9), 0.14, 0.065, sides=8), "navy")


# ===========================================================================
# 7. Téléphone à ressort 10 x 8 x 4
def build_spring_phone(mb, lod, rng, atlas):
    L0 = lod == 0
    cx = 0.45          # le corps passe sous le combiné : aucune fente entre combiné et boîtier
    n = 3 if L0 else 1
    mb.add(loft([(0.0, 4.9, 3.9, 0.7), (0.3, 4.9, 3.9, 0.7), (0.42, 4.78, 3.78, 0.6)], cx=0, n=n), "pink_dark")
    # ressort principal (jaune = code rebond)
    turns, ppt = (2.5, 12) if L0 else (2.5, 7)
    R, wr, z0, z1 = 2.7, 0.22, 0.42, 2.0
    pts = []
    m = int(turns * ppt)
    for i in range(m + 1):
        a = 2 * math.pi * turns * i / m
        f = turns * i / m
        if f < 0.5:
            z = z0 + wr
        elif f > turns - 0.5:
            z = z1 - wr
        else:
            z = z0 + wr + (z1 - z0 - 2 * wr) * (f - 0.5) / (turns - 1.0)
        pts.append((cx + R * math.cos(a), R * math.sin(a), z))
    mb.add(tube(pts, wr, sides=8 if L0 else 4), "yellow", smooth=70)
    lv = [(1.95, 3.85, 3.35, 1.0), (2.15, 4.25, 3.75, 0.8), (2.6, 4.5, 3.95, 0.45), (3.2, 4.55, 4.0, 0.25),
          (3.82, 4.55, 4.0, 0.2), (3.92, 4.43, 3.88, 0.15)]
    if not L0:
        lv = [(1.95, 4.0, 3.5, 0.6), (2.6, 4.5, 3.95, 0.3), (3.92, 4.55, 4.0, 0.06)]
    mb.add(loft(lv, cx=cx, n=n), "pink",
           smooth=50)
    if L0:   # étiquette BOB-7 et voyant de sonnerie sur la face avant
        mb.add(box((-1.2, 3.96, 2.85), (1.6, 4.012, 3.55), r=0.04, seg=1), "white",
               [dict(dir=(0, 1, 0), name="phone_label", cos=0.9)])
        mb.add(cyl((-2.2, 3.95, 3.2), 0.28, 0.07, sides=12, axis="Y", bevel=0.03), "coral")
    # pavé jaune plat + touches affleurantes
    mb.add(box((1.15, -0.35, 3.86), (4.65, 3.65, 3.96), r=0.08 if L0 else 0, seg=2), "yellow",
           () if L0 else [dict(dir=(0, 0, 1), name="phone_top", cos=0.9)])
    if L0:
        digits = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"]
        for i, dg in enumerate(digits):
            c, rr = i % 3, i // 3
            xa = 4.35 - c * 1.12           # colonne 0 à gauche vue de face (= +X)
            ya = -0.05 + rr * 0.95
            kb = box((xa - 0.82, ya, 3.84), (xa, ya + 0.72, 4.0), r=0.06, seg=1, sel=top_edges, skip=[(0, 0, -1)])
            mb.add(kb, "cream", [dict(dir=(0, 0, 1), rect=atlas.phone_cells[dg], cos=0.9)])
    mb.add(box((-3.4, 1.55, 3.88), (0.8, 3.45, 3.97), r=0.05 if L0 else 0, seg=1), "navy",
           [dict(dir=(0, 0, 1), name="phone_screen", cos=0.9)])
    if L0:
        for k in range(5):
            y = -3.4 + k * 0.45
            mb.add(box((-3.3, y, 3.86), (0.6, y + 0.2, 3.95), r=0.04, seg=1), "pink_dark")
        mb.add(cyl((-2.4, 0.55, 3.86), 0.36, 0.12, sides=12, bevel=0.04), "mint")
        mb.add(cyl((-1.3, 0.55, 3.86), 0.36, 0.12, sides=12, bevel=0.04), "coral")
    # combiné latéral : profil en arche (écouteur et micro en bout), dessus plat = dessus du collider
    hp = [(-3.98, 4.0), (3.98, 4.0), (3.98, 2.55), (2.55, 2.45), (2.15, 3.3), (-2.15, 3.3), (-2.55, 2.45), (-3.98, 2.55)]
    if L0:
        hp = round_poly(hp, [0.15, 0.15, 0.4, 0.3, 0.4, 0.4, 0.3, 0.4], seg=3)
    mb.add(prism(hp, "X", -5.0, -3.92, bevel=0.12 if L0 else 0, seg=2), "pink_light", smooth=50)
    for sy in (-1, 1):
        mb.add(box((-4.85, sy * 3.25 - 0.45, 0.4), (-4.07, sy * 3.25 + 0.45, 2.52), r=0.12 if L0 else 0, seg=2),
               "pink_dark")
        if L0:   # grilles d'écouteur / micro sous les extrémités
            mb.add(cyl((-4.46, sy * 3.25, 2.4), 0.36, 0.08, sides=12), "navy")
    # cordon spiralé (repère de ressort) suspendu sous la poignée
    ctrl = [(-4.46, 2.7, 2.42), (-4.46, 2.15, 1.45), (-4.46, 1.1, 0.95), (-4.46, -0.4, 0.95), (-4.46, -1.6, 1.5),
            (-4.2, -2.1, 2.3), (-3.86, -2.1, 2.8)]
    path = catmull(ctrl, per_seg=10)
    if L0:
        mb.add(tube(coil_along(path, 0.2, 13, 6), 0.065, sides=4, caps=True), "pink_dark", smooth=80)
    else:
        mb.add(tube(path[::6] + [path[-1]], 0.16, sides=4), "pink_dark", smooth=80)


# ===========================================================================
# 8. Dossiers libres 10 x 8 x 5 (temporaire : pile instable)
def build_loose_files(mb, lod, rng):
    L0 = lod == 0
    nl = 7 if L0 else 3
    Hs = 4.34
    th = Hs / nl
    covers = ["peach", "cream_dark", "lavender_light", "peach", "teal_light", "cream_dark", "peach"]
    for i in range(nl):
        z0 = i * th
        W, D = (8.3, 6.3)
        for _ in range(60):
            ang = rng.uniform(-9.0, 9.0) if L0 else (-5, 4, -3)[i]
            dx, dy = rng.uniform(-0.35, 0.35), rng.uniform(-0.3, 0.3)
            c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            ex = abs(c) * W / 2 + abs(s) * (D / 2 + 0.14)
            ey = abs(s) * W / 2 + abs(c) * (D / 2 + 0.14)
            if abs(dx) + ex <= 4.9 and abs(dy) + ey <= 3.9:
                break
        M = T(dx, dy, z0) @ Rz(ang)
        spine = 1 if i % 3 != 1 else -1
        col = covers[i % len(covers)]
        mb.add(xf(box((-W / 2, -D / 2, 0.0), (W / 2, D / 2, 0.06)), M), col)
        mb.add(xf(box((-W / 2 + 0.12, -D / 2 + 0.15, 0.06), (W / 2 - 0.2, D / 2 - 0.12, th - 0.06)), M), "paper",
               [dict(dir=rot_dir(ang, d), name="sheet_edges") for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))])
        mb.add(xf(box((-W / 2 + 0.05, -D / 2, th - 0.06), (W / 2 - 0.05, D / 2, th)), M), col)
        sp = [(spine * (D / 2 - 0.1), 0.006), (spine * (D / 2 + 0.12), 0.006), (spine * (D / 2 + 0.12), th - 0.006),
              (spine * (D / 2 - 0.1), th - 0.006)]
        rr = [0, min(0.25, th / 2 - 0.01), min(0.25, th / 2 - 0.01), 0]
        prof = round_poly(sp, rr, seg=2) if L0 else sp
        mb.add(xf(prism(prof, "X", -W / 2, W / 2), M), "pink",
               [dict(dir=rot_dir(ang, (0, spine, 0)), name="folder_edge", cos=0.8, up=(0, 0, 1))])
    # feuilles éventail qui s'échappent de la pile
    nsheet = 11 if L0 else 3
    made = 0
    tries = 0
    while made < nsheet and tries < 200:
        tries += 1
        k = rng.randint(1, nl - 1)
        zb = k * th + 0.005
        theta = rng.choice([90, 180, 90, 180, 135, 0, -90, 105, 200, 160, 70]) + rng.uniform(-14, 14)
        width = rng.uniform(2.0, 2.9)
        dirv = Vector((math.cos(math.radians(theta)), math.sin(math.radians(theta)), 0))
        edge = 4.3 if abs(dirv.x) > abs(dirv.y) else 3.3
        out = rng.uniform(0.9, 1.6)
        droop = rng.uniform(0.3, 0.8) if L0 else 0.3
        ok = False
        while out > 0.25:
            segs = 6 if L0 else 2
            top = [(edge - 2.0, zb + 0.03)]
            for j in range(segs + 1):
                s = edge + out * j / segs
                f = j / segs
                top.append((s, zb + 0.03 - droop * f * f))
            bot = [(s, z - 0.03) for (s, z) in reversed(top)]
            prof = top + bot
            sh = prism(prof, "Y", -width / 2, width / 2)
            sideoff = rng.uniform(-1.2, 1.2)
            xf(sh, Rz(theta) @ T(0, sideoff, 0))
            cs = [v.co for v in sh.verts]
            if max(abs(c.x) for c in cs) <= 4.95 and max(abs(c.y) for c in cs) <= 3.95 and min(c.z for c in cs) > 0.02:
                ok = True
                break
            sh.free()
            out -= 0.15
        if ok:
            mb.add(sh, "paper", [dict(dir=(0, 0, 1), name="sheet_text", cos=0.5, up=rot_dir(theta, (1, 0, 0)))])
            made += 1
    # dossier supérieur : couverture souple pleine empreinte (dessus du collider)
    mb.add(box((-4.9, -3.9, Hs), (4.9, 3.9, Hs + 0.06)), "peach")
    mb.add(box((-4.75, -3.75, Hs + 0.06), (4.85, 3.82, 4.8)), "paper",
           [dict(dir=d, name="sheet_edges") for d in ((1, 0, 0), (0, 1, 0), (0, -1, 0))])

    def ztop(x, y):
        return 5.0 - 0.10 * max(abs(x) / 5.0, abs(y) / 4.0) ** 6

    nx, ny = (10, 8) if L0 else (1, 1)
    mb.add(grid_slab(-5.0, 5.0, -4.0, 4.0, nx, ny, ztop if L0 else (lambda x, y: 5.0), 0.07), "peach",
           [dict(dir=(0, 0, 1), name="folder_cover", cos=0.8, range=(-5, 5, -4, 4))], smooth=30)
    spf = [(-4.85, Hs), (-5.0, Hs), (-5.0, 4.93), (-4.85, 4.93)]
    mb.add(prism(round_poly(spf, [0, 0.07, 0.07, 0], seg=2) if L0 else spf, "Y", -3.95, 3.95), "pink")
    if L0:
        mb.add(box((1.0, 3.7, 4.55), (2.5, 4.0, 4.82), r=0.04, seg=1), "pink",
               [dict(dir=(0, 1, 0), name="folder_tab", cos=0.9)])
        # trombone posé sur le bord avant
        x0 = -3.7
        shape = [(x0, 3.9), (x0, 2.7)]
        shape += [(x0 + 0.28 - 0.28 * math.cos(a), 2.7 - 0.28 * math.sin(a)) for a in
                  [math.pi * j / 6 for j in range(1, 6)]]
        shape += [(x0 + 0.56, 2.7), (x0 + 0.56, 3.65)]
        shape += [(x0 + 0.36 + 0.2 * math.cos(a), 3.65 + 0.2 * math.sin(a)) for a in
                  [math.pi * j / 5 for j in range(1, 5)]]
        shape += [(x0 + 0.16, 3.65), (x0 + 0.16, 2.95)]
        shape += [(x0 + 0.28 - 0.12 * math.cos(a), 2.95 - 0.12 * math.sin(a)) for a in
                  [math.pi * j / 4 for j in range(1, 4)]]
        shape += [(x0 + 0.4, 2.95), (x0 + 0.4, 3.5)]
        pts3 = [(x, y, ztop(x, y) - 0.045) for (x, y) in shape]
        mb.add(tube(pts3, 0.045, sides=5), "metal", smooth=70)


# ===========================================================================
# 9. Machine signature : Copieur Panique 22 x 14 x 18
def build_copier(mb, lod, rng):
    L0 = lod == 0
    r3 = 0.3 if L0 else 0
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * 7.9, sy * 5.0 - 0.3
            mb.add(box((x - 0.35, y - 0.45, 0.45), (x + 0.35, y + 0.45, 1.12), r=0.06 if L0 else 0, seg=1), "navy")
            if L0:
                mb.add(cyl((x - 0.2, y, 0.42), 0.42, 0.4, sides=12, axis="X"), "rubber")
            else:
                mb.add(box((x - 0.2, y - 0.42, 0.0), (x + 0.2, y + 0.42, 0.84)), "rubber")
    mb.add(box((-8.7, -6.5, 0.8), (8.7, 5.9, 1.2)), "navy")
    mb.add(box((-9.0, -6.8, 1.1), (9.0, 6.2, 9.0), r=r3, seg=3), "yellow",
           [] if L0 else [dict(dir=(0, 1, 0), name="copier_front_lod", cos=0.9, range=(-8.5, 8.5, 1.4, 8.7))])
    mb.add(box((-9.0, -6.8, 9.0), (9.0, 6.2, 13.6), r=r3, seg=3), "yellow")
    if L0:
        for (z0, z1, lab) in ((1.4, 3.7, "drawer_a4"), (3.9, 6.2, "drawer_a3"), (6.4, 8.7, "drawer_a4")):
            mb.add(box((-8.5, 6.0, z0), (8.5, 6.55, z1), r=0.15, seg=2, skip=[(0, -1, 0)]), "cream")
            mb.add(box((-1.8, 6.5, z1 - 0.65), (1.8, 6.6, z1 - 0.35), r=0.05, seg=1), "navy")
            mb.add(box((5.4, 6.55, z1 - 0.95), (6.6, 6.58, z1 - 0.35)), "white", [dict(dir=(0, 1, 0), name=lab, cos=0.9)])
            mb.add(box((-6.8, 6.55, z1 - 0.95), (-5.6, 6.58, z1 - 0.35)), "navy",
                   [dict(dir=(0, 1, 0), name="paper_level", cos=0.9)])
        mb.add(box((2.2, 6.55, 4.6), (3.4, 6.58, 5.2)), "coral", [dict(dir=(0, 1, 0), name="label_a3_note", cos=0.9)])
        # feuille coincée (bourrage) entre deux tiroirs
        jam = [(5.95, 6.25), (6.6, 6.3), (6.85, 6.05), (6.97, 5.6), (6.93, 5.6), (6.81, 6.02), (6.58, 6.26), (5.95, 6.21)]
        mb.add(prism(jam, "X", 2.0, 4.6), "paper", [dict(dir=(0, 1, 0), name="sheet_text", cos=0.5)])
        # porte avant + plaque de marque
        mb.add(box((-8.6, 6.2, 9.4), (8.6, 6.32, 12.3), r=0.08, seg=2, skip=[(0, -1, 0)]), "yellow_dark")
        mb.add(box((6.4, 6.3, 11.7), (8.0, 6.36, 12.0), r=0.03, seg=1), "navy")
        mb.add(box((-7.6, 6.3, 10.2), (-2.6, 6.36, 11.4), r=0.05, seg=1), "navy", [dict(dir=(0, 1, 0), name="brand_plate", cos=0.9)])
        # grand écran facial : la panique de BOB, lisible de loin
        mb.add(box((0.0, 6.25, 9.55), (5.6, 6.55, 13.1), r=0.15, seg=2, skip=[(0, -1, 0)]), "navy")
        mb.add(box((0.25, 6.5, 9.8), (5.35, 6.6, 12.85), r=0.05, seg=1), "cyan",
               [dict(dir=(0, 1, 0), name="copier_screen", cos=0.9)])
        # ouïes d'aération côté -X
        for k in range(6):
            z = 2.2 + k * 0.6
            mb.add(box((-9.06, -6.0, z), (-8.95, -1.2, z + 0.28), r=0.04, seg=1), "navy")
        mb.add(box((-9.06, -0.6, 2.2), (-8.97, 0.4, 3.2)), "yellow", [dict(dir=(-1, 0, 0), name="warning", cos=0.9)])
        mb.add(box((-8.0, -6.86, 3.0), (8.0, -6.8, 8.0)), "yellow_dark")  # panneau arrière
    else:
        mb.add(box((-8.6, 6.2, 9.4), (8.6, 6.32, 12.3)), "yellow_dark")
        mb.add(box((-7.6, 6.3, 10.2), (-2.6, 6.36, 11.4)), "navy", [dict(dir=(0, 1, 0), name="brand_plate", cos=0.9)])
        mb.add(box((0.25, 6.3, 9.8), (5.35, 6.6, 12.85)), "cyan", [dict(dir=(0, 1, 0), name="copier_screen", cos=0.9)])
    # bac de sortie turquoise (côté -X) et blocs de papier solides
    tray = [(-8.9, 8.2), (-11.0, 8.9), (-11.0, 9.45), (-10.75, 9.45), (-10.65, 9.15), (-8.9, 8.55)]
    mb.add(prism(tray, "Y", -4.2, 4.2, bevel=0.06 if L0 else 0, seg=1), "turquoise")
    mb.add(box((-9.08, -4.3, 8.65), (-8.95, 4.3, 9.4)), "navy")
    ang = math.degrees(math.atan2(0.6, 1.75))
    d = Vector((-math.cos(math.radians(ang)), 0, math.sin(math.radians(ang))))
    nrm = Vector((math.sin(math.radians(ang)), 0, math.cos(math.radians(ang))))
    base = Vector((-8.9, 0, 8.55))
    nb = 3 if L0 else 1
    for k in range(nb):
        c = base + d * 0.95 + nrm * (0.26 + 0.5 * k) + Vector((0, rng.uniform(-0.15, 0.15), 0))
        bl = box((-0.8, -2.7, -0.24), (0.8, 2.7, 0.24) if L0 else (0.8, 2.7, 0.24 + 0.5 * (nb - 1)),
                 r=0.05 if L0 else 0, seg=1)
        xf(bl, T(c.x, c.y, c.z) @ Ry(ang) @ Rz(rng.uniform(-4, 4) if L0 else 0))
        mb.add(bl, "cream", [dict(dir=(0, 0, 1), name="sheet_text", cos=0.8),
                             dict(dir=(0, 1, 0), name="sheet_edges", cos=0.7),
                             dict(dir=(0, -1, 0), name="sheet_edges", cos=0.7),
                             dict(dir=(-1, 0, 0), name="sheet_edges", cos=0.7)])
    if L0:
        sheet = [(-8.95, 9.05), (-9.4, 9.32), (-9.9, 9.5), (-10.35, 9.48), (-10.35, 9.44), (-9.9, 9.46), (-9.4, 9.28),
                 (-8.95, 9.01)]
        mb.add(prism(sheet, "Y", -2.5, 2.5), "paper", [dict(dir=(0, 0, 1), name="sheet_text", cos=0.5)])
    # bac by-pass (côté +X)
    mb.add(prism([(8.95, 6.8), (11.0, 7.6), (11.0, 7.95), (8.95, 7.25)], "Y", -3.5, 3.5), "turquoise")
    if L0:
        bp = box((-0.75, -2.6, 0.0), (0.75, 2.6, 0.06))
        xf(bp, T(10.0, 0.0, 7.62) @ Ry(-math.degrees(math.atan2(0.8, 2.05))))
        mb.add(bp, "paper", [dict(dir=(0, 0, 1), name="sheet_text", cos=0.8)])
    # module scanner, volet, chargeur de documents
    mb.add(box((-9.0, -6.8, 13.6), (9.0, 6.2, 15.3), r=0.2 if L0 else 0, seg=2), "cream")
    mb.add(box((-8.9, -6.7, 15.3), (8.9, 6.1, 15.75), r=0.15 if L0 else 0, seg=2), "cream_dark")
    if L0:
        mb.add(loft([(15.75, 2.25, 6.3, 0.45), (17.2, 2.25, 6.3, 0.45), (17.75, 2.0, 6.05, 0.4), (18.0, 1.6, 5.7, 0.3)],
                    cx=6.55, cy=-0.3, n=3), "cream", smooth=40)
        mb.add(box((4.24, -5.0, 15.85), (4.34, 5.0, 16.3)), "navy")
    else:
        mb.add(box((4.3, -6.6, 15.75), (8.8, 6.0, 18.0)), "cream")
    mb.add(prism([(4.3, 16.3), (4.3, 16.75), (-5.5, 17.3), (-5.5, 16.95)], "Y", -5.0, 4.4), "turquoise")
    st = box((-3.6, -4.2, 0.0), (3.6, 3.6, 0.35), r=0.04 if L0 else 0, seg=1)
    xf(st, T(-0.4, 0, 16.92) @ Ry(math.degrees(math.atan2(0.55, 9.8))))
    mb.add(st, "paper", [dict(dir=(0, 0, 1), name="sheet_text", cos=0.9)])
    # gyrophare « panique »
    mb.add(cyl((-7.5, -4.5, 15.75), 0.75, 0.35, sides=16 if L0 else 8), "navy")
    if L0:
        mb.add(loft([(16.1, 0.62, 0.62, 0.62), (16.9, 0.62, 0.62, 0.62), (17.3, 0.5, 0.5, 0.5), (17.55, 0.28, 0.28, 0.28)],
                    cx=-7.5, cy=-4.5, n=4), "coral", smooth=60)
    else:
        mb.add(cyl((-7.5, -4.5, 16.1), 0.62, 1.45, sides=8, r_top=0.3), "coral")
    # pupitre incliné : écran de BOB paniqué, gros bouton rose, touches
    pan = [(5.4, 12.0), (7.0, 12.35), (7.0, 12.85), (5.8, 15.45), (5.4, 15.45)]
    nrm_p = Vector((0, 2.6, 1.2)).normalized()
    slope_up = Vector((0, -1.2, 2.6)).normalized()
    mb.add(prism(round_poly(pan, [0, 0.1, 0.15, 0.15, 0], seg=2) if L0 else pan, "X", -8.8, -0.4), "cream",
           [] if L0 else [dict(dir=tuple(nrm_p), name="copier_panel", cos=0.95, up=tuple(slope_up))])
    F = frame(Vector((-4.6, 6.4, 14.15)), (-1, 0, 0), tuple(slope_up))
    if L0:
        scr = box((-3.95, -1.15, -0.03), (-0.35, 1.15, 0.07), r=0.05, seg=1)
        mb.add(xf(scr, F), "navy", [dict(dir=tuple(nrm_p), name="copier_err", cos=0.95, up=tuple(slope_up))])
        mb.add(xf(cyl((2.95, 0.15, 0.0), 0.62, 0.22, sides=18, bevel=0.07, seg=2), F), "pink")
        mb.add(xf(cyl((1.75, 0.55, 0.0), 0.3, 0.15, sides=12, bevel=0.04), F), "mint")
        mb.add(xf(cyl((1.75, -0.4, 0.0), 0.3, 0.15, sides=12, bevel=0.04), F), "coral")
        for i in range(3):
            for j in range(3):
                kb = box((-0.15, -0.17, -0.02), (0.15, 0.17, 0.1), r=0.03, seg=1)
                mb.add(xf(kb, F @ T(0.15 + i * 0.4, -0.65 + j * 0.48, 0)), "navy_light")
        for i, c in enumerate(("mint", "yellow", "coral")):
            mb.add(xf(cyl((3.85, -0.7 + i * 0.45, 0.0), 0.1, 0.08, sides=6), F), c)
    # pare-chocs arrière (enveloppe -7)
    mb.add(box((-8.5, -7.0, 8.8), (8.5, -6.8, 9.4), r=0.05 if L0 else 0, seg=1), "navy")


BUILDERS = {
    "bureau_paper_ream": build_paper_ream,
    "bureau_binder_stack": build_binder_stack,
    "bureau_desk": build_desk,
    "bureau_locker": build_locker,
    "bureau_keyboard": build_keyboard,
    "bureau_rail_chair": build_rail_chair,
    "bureau_spring_phone": build_spring_phone,
    "bureau_loose_files": build_loose_files,
    "machine_bureau_copier": build_copier,
}
NEEDS_ATLAS = {"bureau_keyboard", "bureau_spring_phone"}


# ===========================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0  # 1 BU = 1 stud (décision 0003)
    return sc


def mesh_bounds(ob):
    cs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
    mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
    return mn, mx


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def collider_info(spec):
    if not spec.get("collider"):
        return {"shape": "separate_architecture_proxy",
                "note": "Machine décorative : collision du parcours séparée (manifest), aucun dessus praticable."}
    w, d, h = spec["collider"]["size_studs"]
    tw, td = spec["collider"]["walkable_top"]
    return {
        "authority": "server_collider_separate_from_visual_mesh",
        "pivot": "bottom_center", "forward_axis": "-Z", "dimensions_order_config": "width_depth_height",
        "shape": "box", "size_studs_config": [w, d, h], "size_vector3_roblox": [w, h, d],
        "offset_from_pivot_roblox": [0.0, h / 2.0, 0.0],
        "walkable_top": {"size_studs": [tw, td], "height_studs": h, "center_roblox": [0.0, h, 0.0]},
        "support_sockets_roblox": [[sx * tw / 4, h, sz * td / 4] for sx in (-1, 1) for sz in (-1, 1)] + [[0.0, h, 0.0]],
        "visual_mesh": {"can_collide": False, "can_query": False, "can_touch": False},
        "behavior": spec.get("behavior"), "behavior_params": spec.get("behavior_params"),
    }


def export_asset(aid, lod0, lod1):
    os.makedirs(IMPORT_DIR, exist_ok=True)
    base = os.path.join(IMPORT_DIR, aid)

    def sel(ob):
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob

    common = dict(export_format="GLB", use_selection=True, export_yup=True, export_apply=True,
                  export_texcoords=True, export_normals=True, export_tangents=False, export_materials="EXPORT",
                  export_vertex_color="NONE", export_image_format="AUTO", export_cameras=False,
                  export_lights=False, export_animations=False, export_skins=False, export_extras=False)
    sel(lod0)
    bpy.ops.export_scene.gltf(filepath=base + ".glb", **common)
    sel(lod1)
    bpy.ops.export_scene.gltf(filepath=base + "_lod1.glb", **common)
    sel(lod0)
    bpy.ops.export_scene.fbx(filepath=base + ".fbx", use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0, bake_anim=False,
                             path_mode="COPY", embed_textures=True, mesh_smooth_type="FACE",
                             use_mesh_modifiers=True, add_leaf_bones=False)
    return [base + ".glb", base + "_lod1.glb", base + ".fbx"]


def main():
    only = sys.argv[1:] or ASSET_ORDER
    fam, specs = load_family()
    reset_scene()
    os.makedirs(TEX_DIR, exist_ok=True)
    atlas = K.Atlas()
    K.save_atlas(atlas, ATLAS_FILE)
    img = bpy.data.images.load(ATLAS_FILE)
    img.name = "bureau_atlas_1024"
    mat = K.make_material(img)
    info = {"family": "bureau", "blender_version": bpy.app.version_string, "seed": SEED,
            "atlas": os.path.relpath(ATLAS_FILE, ROOT), "atlas_px": K.ATLAS_PX, "materials_per_mesh": 1,
            "units": "1 BU = 1 stud ; X largeur, Y profondeur (avant Roblox -Z = +Y Blender), Z hauteur",
            "palette_sources": ["config/rooms.json families[bureau].palette", "docs/02 tokens",
                                "assets/source/design/canvas/project/Room_Office.dc.html"],
            "assets": {}}
    for aid in ASSET_ORDER:
        if aid not in only:
            continue
        spec = specs[aid]
        coll = bpy.data.collections.new(aid)
        bpy.context.scene.collection.children.link(coll)
        objs = []
        for lod in (0, 1):
            name = aid if lod == 0 else f"{aid}_LOD1"
            mb = K.MeshBuilder(name, atlas)
            fn = BUILDERS[aid]
            rng = rng_for(aid)
            if aid in NEEDS_ATLAS:
                fn(mb, lod, rng, atlas)
            else:
                fn(mb, lod, rng)
            ob = mb.build(mat, coll)
            objs.append(ob)
        lod0, lod1 = objs
        exports = export_asset(aid, lod0, lod1)
        mn, mx = mesh_bounds(lod0)
        mn1, mx1 = mesh_bounds(lod1)
        size = [round(mx.x - mn.x, 3), round(mx.y - mn.y, 3), round(mx.z - mn.z, 3)]
        entry = {
            "name": spec.get("name"), "size_studs_config": spec["size_studs"],
            "bbox_studs_width_depth_height": size,
            "bbox_lod1": [round(mx1.x - mn1.x, 3), round(mx1.y - mn1.y, 3), round(mx1.z - mn1.z, 3)],
            "bbox_min": [round(mn.x, 3), round(mn.y, 3), round(mn.z, 3)],
            "lod0_tris": tri_count(lod0), "lod1_tris": tri_count(lod1),
            "visual_brief": spec.get("visual"), "collision": collider_info(spec),
            "exports": [os.path.relpath(p, ROOT) for p in exports],
        }
        info["assets"][aid] = entry
        print(f"[build] {aid}: bbox={size} tris LOD0={entry['lod0_tris']} LOD1={entry['lod1_tris']}")
    img.pack()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_FILE, compress=True)
    info_path = os.path.join(MODEL_DIR, "build_info.json")
    if set(only) != set(ASSET_ORDER) and os.path.exists(info_path):
        with open(info_path, encoding="utf-8") as f:
            old = json.load(f)
        old["assets"].update(info["assets"])
        info["assets"] = old["assets"]
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
