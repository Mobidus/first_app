"""Atlas de texture partagé de la famille Piscine Gonflable (1 024 px, peint procéduralement).

Aucune image externe : tout est dessiné ici (PIL, suréchantillonnage x4, graine fixe).
Importé par build_props_pool.py (UV) ; peut être lancé seul :
    .venv/bin/python -I assets/source/blender/pool_atlas.py <dossier_sortie>

Disposition (pixels, origine en haut à gauche, tuiles de 256) :
  ligne 0 : pont canard | pont flamant | dessus donut (+ filet) | pont licorne
  ligne 1 : dos crocodile | dessus matelas | couvercle glacière | dessus ballon (fuseaux)
  ligne 2 : matières latérales 256x128 (vinyle jaune, rose, blanc nacré, croco, glacière, matelas, fuseaux, donut)
  ligne 3 : palette dégradée (32 cellules) | visages, yeux, jauge, arc-en-ciel, autocollants
Couleurs : palette « Piscine » (eau #E3F7FF, bleu piscine #1FA8E0, soleil #FFD23F, flamant #FF7FB8,
corail #FF684B, menthe #39E68B, marine #203055).
Second fichier (rough) : convention glTF metallicRoughness, G = rugosité, B = métal.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
SS = 4
SEED = 20261102

HEX = {
    "navy": "#203055", "pool": "#1FA8E0", "yellow": "#FFD23F", "pink": "#FF7FB8", "coral": "#FF684B",
    "mint": "#39E68B", "water": "#E3F7FF", "white": "#FBFCFF",
    "yellow_dark": "#E8A91C", "orange": "#FF9A1F", "orange_dark": "#E0700F", "pink_dark": "#E0559A",
    "pink_light": "#FFC2DE", "green": "#3DBF55", "green_dark": "#24893A", "green_light": "#A6EC7E",
    "gold": "#FFC93C", "gold_dark": "#D9962A", "rubber": "#2A3145", "steel": "#B7C3D6",
    "pool_dark": "#1378A8", "dough": "#F2B96B", "dough_dark": "#C9853D", "red": "#F2434B",
    "lilac": "#B48CFF", "sky": "#8FD8FF", "pearl": "#F3F1FF", "tongue": "#FF5F7E",
    "mouth": "#7A1F3D", "glass": "#D8F4FF", "navy_light": "#4A5E92", "black": "#141A2B",
}


def rgb(n):
    h = HEX.get(n, n).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(c, f):
    return tuple(int(max(0, min(255, round(v * f)))) for v in c)


def mix(a, b, t):
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))


TILES = {
    "duck_top": (0, 0, 256, 256), "flamingo_top": (256, 0, 512, 256),
    "donut_top": (512, 0, 768, 256), "unicorn_top": (768, 0, 1024, 256),
    "croc_top": (0, 256, 256, 512), "mattress_top": (256, 256, 512, 512),
    "cooler_lid": (512, 256, 768, 512), "ball_top": (768, 256, 1024, 512),
    "s_duck": (0, 512, 256, 640), "s_pink": (0, 640, 256, 768),
    "s_pearl": (256, 512, 512, 640), "s_croc": (256, 640, 512, 768),
    "s_cooler": (512, 512, 768, 640), "s_mattress": (512, 640, 768, 768),
    "s_ball": (768, 512, 1024, 640), "s_donut": (768, 640, 1024, 768),
    # ligne 3 (décors)
    "duck_face": (256, 768, 384, 896), "unicorn_face": (384, 768, 512, 896),
    "croc_face": (512, 768, 768, 896), "cooler_face": (768, 768, 1024, 896),
    "pump_face": (256, 896, 384, 1024), "gauge": (384, 896, 512, 1024),
    "eye": (512, 896, 576, 960), "badge_sun": (576, 896, 640, 960),
    "donut_face": (512, 960, 640, 1024), "rainbow": (640, 896, 768, 960),
    "valve_label": (640, 960, 768, 1024), "pedal": (768, 896, 1024, 1024),
}

PALETTE_ORDER = [
    "navy", "pool", "yellow", "pink", "coral", "mint", "water", "white",
    "yellow_dark", "orange", "orange_dark", "pink_dark", "pink_light", "green", "green_dark", "green_light",
    "gold", "gold_dark", "rubber", "steel", "pool_dark", "dough", "dough_dark", "red",
    "lilac", "sky", "pearl", "tongue", "mouth", "glass", "navy_light", "black",
]
CELL_W, CELL_H = 32, 64

ROUGH_VINYL = 0.3
ROUGH = {k: ROUGH_VINYL for k in TILES}
ROUGH.update({"donut_top": 0.22, "s_donut": 0.3, "cooler_lid": 0.36, "s_cooler": 0.34, "gauge": 0.15,
              "pedal": 0.5, "eye": 0.2})
PAL_ROUGH = {"rubber": 0.82, "black": 0.6, "steel": 0.28, "gold": 0.26, "gold_dark": 0.3, "glass": 0.06,
             "dough": 0.55, "dough_dark": 0.6, "navy": 0.35}
PAL_METAL = {"steel": 0.7, "gold": 0.55, "gold_dark": 0.5}


def cell_rect(name):
    i = PALETTE_ORDER.index(name)
    col, row = i % 8, i // 8
    return (col * CELL_W, 768 + row * CELL_H, col * CELL_W + CELL_W, 768 + row * CELL_H + CELL_H)


def px_to_uv(rect, margin_px=1.5):
    x0, y0, x1, y1 = rect
    return ((x0 + margin_px) / SIZE, 1 - (y1 - margin_px) / SIZE, (x1 - margin_px) / SIZE, 1 - (y0 + margin_px) / SIZE)


def tile_uv(name, margin_px=1.5):
    return px_to_uv(TILES[name], margin_px)


def cell_uv(name):
    return px_to_uv(cell_rect(name), 3.0)


# --- outils de dessin -------------------------------------------------------------
class Canvas:
    """Surface en coordonnées monde (studs) projetées comme le mappeur `top` :
    image droite = monde -X, image haut = monde -Y (lecture à l'endroit depuis l'avant, +Y Blender).
    world=False : coordonnées en pixels de tuile."""

    def __init__(self, w_px, h_px, bg, x0=0.0, x1=1.0, y0=0.0, y1=1.0, world=True):
        self.W, self.H = w_px * SS, h_px * SS
        self.img = Image.new("RGB", (self.W, self.H), bg)
        self.d = ImageDraw.Draw(self.img)
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.world = world
        self.k = self.W / (x1 - x0) if world else SS

    def p(self, x, y):
        if not self.world:
            return (x * SS, y * SS)
        return ((self.x1 - x) / (self.x1 - self.x0) * self.W, (y - self.y0) / (self.y1 - self.y0) * self.H)

    def s(self, v):
        return v * self.k

    def circle(self, x, y, r, fill=None, outline=None, width=0.0):
        cx, cy = self.p(x, y)
        rr = self.s(r)
        self.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=fill, outline=outline,
                       width=max(1, int(self.s(width))) if outline else 0)

    def ellipse(self, x, y, rx, ry, fill=None, outline=None, width=0.0):
        cx, cy = self.p(x, y)
        a, b = abs(self.s(rx)), abs(self.s(ry)) * (1 if not self.world else self.H / self.W *
                                                    (self.x1 - self.x0) / (self.y1 - self.y0))
        self.d.ellipse([cx - a, cy - b, cx + a, cy + b], fill=fill, outline=outline,
                       width=max(1, int(self.s(width))) if outline else 0)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=0.0, radius=0.0):
        a, b = self.p(x0, y0), self.p(x1, y1)
        box = [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]
        self.d.rounded_rectangle(box, radius=self.s(radius), fill=fill, outline=outline,
                                 width=max(1, int(self.s(width))) if outline else 0)

    def poly(self, pts, fill=None, outline=None, width=0.0):
        P = [self.p(*q) for q in pts]
        self.d.polygon(P, fill=fill)
        if outline:
            self.line(pts + [pts[0]], outline, width)

    def line(self, pts, fill, width):
        P = [self.p(*q) for q in pts]
        self.d.line(P, fill=fill, width=max(1, int(self.s(width))), joint="curve")
        r = self.s(width) / 2
        for q in P:
            self.d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=fill)

    def arc(self, x, y, r, a0, a1, fill, width, n=24):
        pts = [(x + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                y + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        self.line(pts, fill, width)

    def wedge(self, x, y, r0, r1, a0, a1, fill, n=24):
        pts = [(x + r1 * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                y + r1 * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        pts += [(x + r0 * math.cos(math.radians(a1 - (a1 - a0) * i / n)),
                 y + r0 * math.sin(math.radians(a1 - (a1 - a0) * i / n))) for i in range(n + 1)]
        self.poly(pts, fill=fill)

    def result(self, w, h):
        return self.img.resize((w, h), Image.LANCZOS)


def star_pts(x, y, r0, r1, rot=0.0, n=5):
    return [(x + (r1 if i % 2 == 0 else r0) * math.cos(math.radians(rot + 90 + 180 / n * i)),
             y + (r1 if i % 2 == 0 else r0) * math.sin(math.radians(rot + 90 + 180 / n * i))) for i in range(2 * n)]


def noise_layer(w, h, rng, scale, amp, aniso=(1.0, 1.0)):
    gw, gh = max(2, int(w / scale * aniso[0])), max(2, int(h / scale * aniso[1]))
    g = rng.normal(0, 1, (gh, gw)).astype(np.float32)
    im = Image.fromarray(((g - g.min()) / (np.ptp(g) + 1e-6) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    a = np.asarray(im, dtype=np.float32) / 255.0
    return 1.0 + (a - 0.5) * 2 * amp


def apply_mult(img, m):
    a = np.asarray(img, dtype=np.float32) * m[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def apply_add(img, m):
    a = np.asarray(img, dtype=np.float32) + m[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def vgrad(img, bottom=0.8, top=1.0, top_frac=0.75):
    w, h = img.size
    t = np.linspace(1, 0, h, dtype=np.float32)
    t = np.clip(t / top_frac, 0, 1)
    f = bottom + (top - bottom) * (t ** 0.8)
    return apply_mult(img, np.repeat(f[:, None], w, axis=1))


def edge_dark(img, band_px, amount):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy])
    return apply_mult(img, 1 - amount * np.clip(1 - d / band_px, 0, 1) ** 1.5)


def puff_rows(w, h, n, axis, amp=0.1, hi=0.06):
    """Ombrage « boudins gonflés » : n tubes parallèles ; axis 0 = tubes horizontaux (le long de x)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = (yy / h if axis == 0 else xx / w) * n
    f = np.sin(np.pi * (t - np.floor(t)))
    return 1 - amp + amp * f + hi * np.clip(f - 0.8, 0, 1) * 5


def gloss_streak(w, h, pos=0.3, width=0.06, amount=26.0, slope=0.6):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = (xx / w * slope + yy / h) - pos * (1 + slope)
    return amount * np.exp(-(d / width) ** 2)


def seam_line(c, pts, base, width=0.07):
    """Soudure HF : sillon sombre + liseré clair."""
    c.line(pts, shade(base, 0.72), width)
    c.line([(x + width * 0.45, y + width * 0.45) for x, y in pts], shade(base, 1.12), width * 0.35)


def sprinkles(c, rng, region_fn, n, cols, length=0.32, width=0.09):
    k = 0
    tries = 0
    while k < n and tries < n * 30:
        tries += 1
        x, y = rng.uniform(c.x1, c.x0) if c.x1 < c.x0 else rng.uniform(c.x0, c.x1), rng.uniform(c.y0, c.y1)
        if not region_fn(x, y):
            continue
        a = rng.uniform(0, math.pi)
        dx, dy = math.cos(a) * length / 2, math.sin(a) * length / 2
        col = cols[k % len(cols)]
        c.line([(x - dx, y - dy), (x + dx, y + dy)], shade(col, 0.75), width * 1.25)
        c.line([(x - dx, y - dy), (x + dx, y + dy)], col, width)
        k += 1


# --- tuiles de dessus ---------------------------------------------------------------
def t_duck_top(rng):
    Y = rgb("yellow")
    c = Canvas(256, 228, Y, -4.6, 4.6, -4.1, 4.1)
    # selle matelassée centrale (orange) + 3 boudins avant-arrière
    c.rect(-3.0, -2.9, 3.0, 2.9, fill=mix(Y, rgb("orange"), 0.35), radius=1.1)
    for x in (-1.0, 1.0):
        seam_line(c, [(x, -2.7), (x, 2.7)], mix(Y, rgb("orange"), 0.35))
    c.rect(-3.0, -2.9, 3.0, 2.9, outline=shade(Y, 0.75), width=0.1, radius=1.1)
    for x in (-3.8, 3.8):
        seam_line(c, [(x, -3.6), (x, 3.6)], Y)
    # étoiles imprimées
    for (x, y, r, col, rot) in ((-4.1, -3.4, 0.38, "white", 10), (4.1, 3.3, 0.36, "coral", -8),
                                (-4.15, 2.6, 0.3, "coral", 20), (4.15, -2.5, 0.32, "white", -15),
                                (0, -3.55, 0.3, "white", 0), (2.0, 3.45, 0.26, "pool", 12),
                                (-2.0, 3.45, 0.26, "pool", -12), (-2.0, -3.5, 0.22, "coral", 5),
                                (2.0, -3.5, 0.22, "coral", -5)):
        c.poly(star_pts(x, y, r * 0.45, r, rot), fill=rgb(col), outline=shade(rgb(col), 0.8), width=0.04)
    # empreinte « assise » sur la selle : petit coeur menthe (appui sûr)
    c.circle(0, 0, 0.75, fill=shade(mix(Y, rgb("orange"), 0.35), 1.06))
    img = c.result(256, 256)
    img = apply_mult(img, puff_rows(256, 256, 3, 1, 0.07, 0.04))
    img = apply_add(img, gloss_streak(256, 256, 0.32, 0.05, 30))
    img = apply_mult(img, noise_layer(256, 256, rng, 50, 0.015))
    return edge_dark(img, 10, 0.2)


def t_flamingo_top(rng):
    P = rgb("pink")
    c = Canvas(256, 228, P, -4.6, 4.6, -4.1, 4.1)
    # plumes festonnées en bordure (rose clair)
    for side in range(4):
        for k in range(-5, 6):
            t = k * 0.85
            if side < 2:
                y = -3.75 if side == 0 else 3.75
                if abs(t) > 4.2:
                    continue
                c.circle(t, y, 0.62, fill=rgb("pink_light"), outline=shade(P, 0.9), width=0.05)
            else:
                x = -4.25 if side == 2 else 4.25
                if abs(t) > 3.5:
                    continue
                c.circle(x, t, 0.62, fill=rgb("pink_light"), outline=shade(P, 0.9), width=0.05)
    c.rect(-3.5, -3.0, 3.5, 3.0, fill=P, radius=1.2)
    seam_line(c, [(-3.5 + 1.2, -3.0), (3.5 - 1.2, -3.0)], P)
    c.rect(-3.5, -3.0, 3.5, 3.0, outline=shade(P, 0.75), width=0.09, radius=1.2)
    # vagues blanches + soleil
    for j, y in enumerate((-1.6, 0.0, 1.6)):
        pts = [(-3.1 + 0.1 * i, y + 0.22 * math.sin(i * 0.1 * 2 * math.pi / 1.3 + j)) for i in range(63)]
        c.line(pts, rgb("white"), 0.16)
    c.circle(2.3, -2.1, 0.55, fill=rgb("yellow"))
    for i in range(8):
        a = math.radians(i * 45)
        c.line([(2.3 + 0.7 * math.cos(a), -2.1 + 0.7 * math.sin(a)), (2.3 + 0.9 * math.cos(a), -2.1 + 0.9 * math.sin(a))],
               rgb("yellow"), 0.1)
    for (x, y) in ((-2.4, 2.2), (2.5, 2.2), (-2.6, -2.2)):
        c.circle(x - 0.13, y, 0.17, fill=rgb("white"))
        c.circle(x + 0.13, y, 0.17, fill=rgb("white"))
        c.poly([(x - 0.29, y + 0.05), (x + 0.29, y + 0.05), (x, y + 0.38)], fill=rgb("white"))
    img = c.result(256, 256)
    img = apply_add(img, gloss_streak(256, 256, 0.3, 0.05, 28))
    img = apply_mult(img, noise_layer(256, 256, rng, 50, 0.015))
    return edge_dark(img, 10, 0.2)


DONUT_HOLE_R = 1.75


def t_donut_top(rng):
    G = rgb("pink")
    c = Canvas(256, 256, rgb("dough"), -4.25, 4.25, -4.25, 4.25)
    # glaçage à bord coulant (le bord libre est sur les flancs) : tout le pont est glacé
    pts = []
    for i in range(96):
        a = 2 * math.pi * i / 96
        r = 4.6 + 0.18 * math.sin(7 * a) + 0.1 * math.sin(13 * a + 1)
        pts.append((r * math.cos(a), r * math.sin(a)))
    c.rect(-4.25, -4.25, 4.25, 4.25, fill=G)
    c.poly(pts, fill=G)
    # trou : anneau de pâte + filet trampoline blanc tendu
    c.circle(0, 0, DONUT_HOLE_R + 0.32, fill=mix(G, rgb("dough"), 0.25))
    c.circle(0, 0, DONUT_HOLE_R + 0.08, fill=rgb("pool"))
    c.circle(0, 0, DONUT_HOLE_R - 0.12, fill=rgb("white"))
    R = DONUT_HOLE_R - 0.12
    for k in range(-8, 9):
        t = k * 0.22
        if abs(t) < R:
            h = math.sqrt(R * R - t * t)
            c.line([(t - h * 0.0, -h), (t, h)], rgb("sky"), 0.035)
            c.line([(-h, t), (h, t)], rgb("sky"), 0.035)
    for i in range(16):
        a = 2 * math.pi * (i + 0.5) / 16
        c.circle((DONUT_HOLE_R - 0.02) * math.cos(a), (DONUT_HOLE_R - 0.02) * math.sin(a), 0.07, fill=rgb("white"))
    c.circle(0, 0, 0.42, fill=rgb("mint"), outline=rgb("white"), width=0.05)

    def glaze(x, y):
        r = math.hypot(x, y)
        return r > DONUT_HOLE_R + 0.5 and abs(x) < 4.0 and abs(y) < 4.0
    cols = [rgb(n) for n in ("white", "yellow", "mint", "pool", "coral", "lilac")]
    sprinkles(c, rng, glaze, 120, cols)
    img = c.result(256, 256)
    yy, xx = np.mgrid[0:256, 0:256].astype(np.float32)
    rr = np.hypot(xx - 128, yy - 128) / 128 * 4.25
    ring = np.exp(-((rr - 3.0) / 0.9) ** 2)
    img = apply_mult(img, 0.94 + 0.08 * ring)
    img = apply_add(img, gloss_streak(256, 256, 0.33, 0.04, 34))
    shadow = np.clip(1 - np.exp(-((rr - (DONUT_HOLE_R - 0.12)) / 0.18) ** 2) * 0.25, 0, 1)
    img = apply_mult(img, np.where(rr < DONUT_HOLE_R, shadow, 1.0).astype(np.float32))
    return edge_dark(img, 8, 0.15)


def t_unicorn_top(rng):
    W = rgb("pearl")
    c = Canvas(256, 171, W, -6.1, 6.1, -4.1, 4.1)
    bands = ["red", "orange", "yellow", "mint", "pool", "lilac"]
    for i, b in enumerate(bands):  # arc-en-ciel en diagonale douce sur la croupe
        y0 = -2.4 + i * 0.42
        pts = [(-6.1 + 0.2 * k, y0 + 0.35 * math.sin(k * 0.2 * 0.5)) for k in range(62)]
        c.line(pts, mix(rgb(b), W, 0.25), 0.42)
    c.rect(-5.2, -3.4, 5.2, 3.4, outline=shade(W, 0.82), width=0.09, radius=1.3)
    for x in (-1.8, 1.8):
        seam_line(c, [(x, -3.3), (x, -2.75)], W)
        seam_line(c, [(x, 0.15), (x, 3.3)], W)
    for (x, y, r, col) in ((-4.4, 2.2, 0.4, "gold"), (4.3, 2.4, 0.35, "pink"), (3.6, -3.0, 0.3, "gold"),
                           (-3.4, -3.1, 0.28, "sky"), (0.0, 2.3, 0.45, "gold"), (-4.9, -0.8, 0.25, "pink"),
                           (5.0, -0.5, 0.25, "sky")):
        c.poly(star_pts(x, y, r * 0.42, r), fill=rgb(col), outline=shade(rgb(col), 0.82), width=0.04)
    for (x, y) in ((-2.6, 2.6), (2.6, 1.2)):
        c.circle(x - 0.15, y, 0.19, fill=rgb("pink"))
        c.circle(x + 0.15, y, 0.19, fill=rgb("pink"))
        c.poly([(x - 0.33, y + 0.06), (x + 0.33, y + 0.06), (x, y + 0.42)], fill=rgb("pink"))
    img = c.result(256, 256)
    yy, xx = np.mgrid[0:256, 0:256].astype(np.float32)
    irid = np.stack([np.sin(xx / 40) * 4, np.sin(yy / 35 + 1) * 4, np.cos((xx + yy) / 50) * 6], -1)
    img = Image.fromarray(np.clip(np.asarray(img, dtype=np.float32) + irid, 0, 255).astype(np.uint8))
    img = apply_add(img, gloss_streak(256, 256, 0.3, 0.05, 18))
    return edge_dark(img, 10, 0.16)


def t_croc_top(rng):
    G = rgb("green")
    c = Canvas(256, 130, G, -7.1, 7.1, -3.6, 3.6)
    # plaques dorsales en relief doux (ombre portée vers l'avant + reflet arrière, puis flou)
    plates = []
    for j, (y, ry) in enumerate(((-2.35, 0.5), (-1.0, 0.62), (1.0, 0.62), (2.35, 0.5))):
        for i in range(-6, 7):
            x = i * 1.05 + (0.52 if j % 2 else 0)
            if abs(x) <= 6.2:
                plates.append((x, y, 0.4 if abs(y) > 2 else 0.46, ry))
    for x, y, rx, ry in plates:
        c.ellipse(x, y + 0.12, rx, ry, fill=shade(G, 0.8))
    for x, y, rx, ry in plates:
        c.ellipse(x, y, rx * 0.92, ry * 0.9, fill=shade(G, 1.0))
        c.ellipse(x - 0.05, y - ry * 0.3, rx * 0.55, ry * 0.4, fill=shade(G, 1.1))
    for i in range(-12, 13):  # crête d'échine
        x = i * 0.52
        c.ellipse(x, 0.05, 0.22, 0.2, fill=shade(rgb("green_dark"), 0.95))
        c.ellipse(x - 0.03, -0.04, 0.12, 0.1, fill=rgb("green"))
    img = c.result(256, 256).filter(ImageFilter.GaussianBlur(1.6))
    c2 = Canvas(256, 130, (0, 0, 0), -7.1, 7.1, -3.6, 3.6)
    c2.img = img.resize((c2.W, c2.H))
    c2.d = ImageDraw.Draw(c2.img)
    r = np.random.default_rng(7)
    for _ in range(18):
        x, y = r.uniform(-6.6, 6.6), r.choice([-1, 1]) * r.uniform(2.95, 3.25)
        c2.circle(x, y, r.uniform(0.08, 0.16), fill=mix(G, rgb("green_light"), 0.6))
    c2.rect(-6.9, -3.4, 6.9, 3.4, outline=shade(G, 0.72), width=0.09, radius=0.9)
    for i in range(8):  # pâquerette autocollante
        a = math.radians(i * 45)
        c2.circle(-5.85 + 0.3 * math.cos(a), 3.0 + 0.3 * math.sin(a), 0.19, fill=rgb("white"))
    c2.circle(-5.85, 3.0, 0.17, fill=rgb("yellow"))
    img = c2.result(256, 256)
    img = apply_add(img, gloss_streak(256, 256, 0.35, 0.04, 26))
    img = apply_mult(img, noise_layer(256, 256, rng, 30, 0.02))
    return edge_dark(img, 8, 0.2)


MATTRESS_TUBES = 7


def t_mattress_top(rng):
    c = Canvas(256, 150, rgb("yellow"), -6.0, 6.0, -3.5, 3.5)
    w = 7.0 / MATTRESS_TUBES
    for k in range(MATTRESS_TUBES):
        y0 = -3.5 + k * w
        col = rgb("yellow") if k % 2 == 0 else rgb("pool")
        c.rect(-6.0, y0, 6.0, y0 + w, fill=col)
    # oreiller (bout -X) : bandeau eau + vagues
    c.rect(-6.0, -3.5, -4.15, 3.5, fill=rgb("water"))
    for j in range(5):
        y = -2.8 + j * 1.4
        pts = [(-5.9 + 0.08 * i, y + 0.18 * math.sin(i * 0.5)) for i in range(22)]
        c.line(pts, rgb("pool"), 0.1)
    seam_line(c, [(-4.15, -3.4), (-4.15, 3.4)], rgb("water"), 0.09)
    for k in range(1, MATTRESS_TUBES):
        seam_line(c, [(-4.1, -3.5 + k * w), (5.9, -3.5 + k * w)], rgb("white"), 0.06)
    for (x, y) in ((3.8, -2.5), (1.0, 1.5), (-1.9, -0.5), (4.6, 2.5)):
        c.poly(star_pts(x, y, 0.12, 0.28), fill=rgb("white"))
    img = c.result(256, 256)
    img = apply_mult(img, puff_rows(256, 256, MATTRESS_TUBES, 0, 0.1, 0.05))
    img = apply_add(img, gloss_streak(256, 256, 0.35, 0.05, 22, slope=2.0))
    return edge_dark(img, 6, 0.15)


def t_cooler_lid(rng):
    Wt = rgb("white")
    c = Canvas(256, 179, Wt, -5.0, 5.0, -3.5, 3.5)
    c.rect(-5.0, -3.5, 5.0, 3.5, outline=rgb("pool"), width=0.32, radius=0.5)
    c.rect(-4.3, -2.8, 4.3, 2.8, outline=shade(Wt, 0.85), width=0.08, radius=0.6)
    for k in range(-3, 4):  # nervures antidérapantes
        c.rect(k * 1.0 - 0.32, -0.25, k * 1.0 + 0.32, 0.25, fill=shade(Wt, 0.9), radius=0.2)

    def cube(x, y, s, rot):
        pts = [(x + s * math.cos(math.radians(rot + 45 + 90 * i)), y + s * math.sin(math.radians(rot + 45 + 90 * i)))
               for i in range(4)]
        c.poly(pts, fill=rgb("sky"), outline=rgb("pool"), width=0.06)
        c.line([(x - s * 0.3, y - s * 0.2), (x - s * 0.05, y - s * 0.45)], rgb("white"), 0.08)
    cube(-3.0, -1.6, 0.75, 12)
    cube(3.1, 1.5, 0.65, -20)
    cube(2.0, -1.8, 0.45, 30)
    for i in range(6):  # flocon
        a = math.radians(i * 60)
        c.line([(-2.6, 1.6), (-2.6 + 0.7 * math.cos(a), 1.6 + 0.7 * math.sin(a))], rgb("pool"), 0.09)
    img = c.result(256, 256)
    img = apply_add(img, gloss_streak(256, 256, 0.3, 0.05, 12))
    return edge_dark(img, 6, 0.12)


BALL_GORES = ["white", "red", "yellow", "pool", "mint", "orange"]
BALL_CAP_R = 0.95


def t_ball_top(rng):
    c = Canvas(256, 256, rgb("white"), -3.5, 3.5, -3.5, 3.5)
    for i, g in enumerate(BALL_GORES):
        a0, a1 = 60 * i, 60 * (i + 1)
        c.wedge(0, 0, 0, 6.0, a0, a1, rgb(g), n=8)
    for i in range(6):
        a = math.radians(60 * i)
        c.line([(0, 0), (6.0 * math.cos(a), 6.0 * math.sin(a))], shade(rgb("white"), 0.86), 0.05)
    c.circle(0, 0, BALL_CAP_R, fill=rgb("white"), outline=shade(rgb("white"), 0.8), width=0.06)
    c.circle(0, 0, 0.35, fill=shade(rgb("white"), 0.93), outline=shade(rgb("white"), 0.78), width=0.04)
    img = c.result(256, 256)
    yy, xx = np.mgrid[0:256, 0:256].astype(np.float32)
    rr = np.hypot(xx - 128, yy - 128) / 128
    img = apply_mult(img, 1.02 - 0.05 * rr)
    img = apply_add(img, 40 * np.exp(-(((xx - 95) / 40) ** 2 + ((yy - 85) / 22) ** 2)))
    return img


# --- tuiles latérales (v = hauteur, haut de l'image = haut de l'objet) -------------
def side_vinyl(rng, base, seam_rows=(0.62,), extra=None):
    w, h = 256, 128
    img = Image.new("RGB", (w, h), rgb(base))
    d = ImageDraw.Draw(img)
    if extra:
        extra(d, w, h)
    for s in seam_rows:
        y = int(h * (1 - s))
        d.line([(0, y), (w, y)], fill=shade(rgb(base), 0.7), width=2)
        d.line([(0, y + 2), (w, y + 2)], fill=shade(rgb(base), 1.15), width=1)
    yy = np.arange(h, dtype=np.float32)[:, None]
    img = apply_add(img, np.repeat(22 * np.exp(-((yy - h * 0.3) / 9) ** 2), w, axis=1))
    img = apply_mult(img, noise_layer(w, h, rng, 60, 0.012))
    return vgrad(img, 0.78, 1.0)


def side_croc(rng):
    w, h = 256, 128
    img = Image.new("RGB", (w, h), rgb("green"))
    d = ImageDraw.Draw(img)
    pts = [(x, int(h * 0.62 + 4 * math.sin(x / 9.0))) for x in range(0, w + 1, 4)]
    d.polygon(pts + [(w, h), (0, h)], fill=rgb("green_light"))
    for x in range(0, w, 16):  # rainures transversales du ventre
        d.line([(x, int(h * 0.72)), (x, h)], fill=shade(rgb("green_light"), 0.86), width=2)
    for x in range(6, w, 22):
        d.ellipse([x, 18, x + 10, 30], fill=rgb("green_dark"))
    img = apply_add(img, np.repeat(18 * np.exp(-((np.arange(h, dtype=np.float32)[:, None] - h * 0.25) / 8) ** 2),
                                   w, axis=1))
    return vgrad(img, 0.82, 1.0)


def side_cooler(rng):
    w, h = 256, 128
    c = Canvas(w, h, rgb("pool"), world=False)
    for y in (20, 108):
        c.rect(0, y - 2, w, y + 2, fill=rgb("pool_dark"))

    def cube(x, y, s, rot):
        pts = [(x + s * math.cos(math.radians(rot + 45 + 90 * i)), y + s * math.sin(math.radians(rot + 45 + 90 * i)))
               for i in range(4)]
        c.poly(pts, fill=rgb("water"), outline=rgb("white"), width=1.5)
        c.line([(x - s * 0.35, y - s * 0.15), (x - s * 0.1, y - s * 0.45)], rgb("white"), 2.5)
    for (x, y, s, r) in ((30, 50, 14, 10), (70, 80, 10, -15), (128, 46, 16, 25), (190, 78, 12, 5), (232, 44, 9, -30)):
        cube(x, y, s, r)
    img = c.result(w, h)
    return vgrad(img, 0.8, 1.0)


def side_mattress(rng):
    w, h = 256, 128
    c = Canvas(w, h, rgb("yellow"), world=False)
    bw = w / MATTRESS_TUBES
    for k in range(MATTRESS_TUBES):
        c.rect(k * bw, 0, (k + 1) * bw, h, fill=rgb("yellow") if k % 2 == 0 else rgb("pool"))
    img = c.result(w, h)
    img = apply_mult(img, puff_rows(w, h, MATTRESS_TUBES, 1, 0.12, 0.04))
    return vgrad(img, 0.8, 1.0)


def side_ball(rng):
    w, h = 256, 128
    c = Canvas(w, h, rgb("white"), world=False)
    for i, g in enumerate(BALL_GORES):
        c.rect(i * w / 6, 0, (i + 1) * w / 6, h, fill=rgb(g))
    for i in range(7):
        c.rect(i * w / 6 - 0.8, 0, i * w / 6 + 0.8, h, fill=shade(rgb("white"), 0.85))
    # calotte inférieure blanche (bas de l'image)
    c.rect(0, h * 0.86, w, h, fill=rgb("white"))
    c.rect(0, h * 0.86 - 1, w, h * 0.86 + 1, fill=shade(rgb("white"), 0.8))
    img = c.result(w, h)
    return vgrad(img, 0.85, 1.0, 0.9)


def side_donut(rng):
    w, h = 256, 128
    c = Canvas(w, h, rgb("dough"), world=False)
    c.rect(0, h * 0.84, w, h, fill=shade(rgb("dough"), 1.08))  # dessous plus clair
    pts = [(0, 0)]
    r = np.random.default_rng(11)
    x = 0
    while x <= w:
        depth = r.uniform(0.3, 0.68)
        wid = r.uniform(14, 26)
        pts += [(x + wid * 0.1, h * 0.28), (x + wid * 0.3, h * depth), (x + wid * 0.5, h * (depth + 0.06)),
                (x + wid * 0.7, h * depth), (x + wid * 0.9, h * 0.3)]
        x += wid
    pts += [(w, 0)]
    c.poly(pts, fill=rgb("pink"))
    img = c.result(w, h)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    d = ImageDraw.Draw(img)
    rr = np.random.default_rng(12)
    cols = [rgb(n) for n in ("white", "yellow", "mint", "pool", "coral", "lilac")]
    for k in range(40):
        x0, y0 = rr.uniform(0, w), rr.uniform(4, h * 0.25)
        a = rr.uniform(0, math.pi)
        d.line([(x0, y0), (x0 + 6 * math.cos(a), y0 + 6 * math.sin(a))], fill=cols[k % 6], width=3)
    yy = np.arange(h, dtype=np.float32)[:, None]
    img = apply_add(img, np.repeat(26 * np.exp(-((yy - h * 0.15) / 7) ** 2), w, axis=1))
    return vgrad(img, 0.8, 1.0)


# --- décors frontaux ------------------------------------------------------------------
def big_eye(c, x, y, rx, ry, look=(0.2, 0.1), lid=False):
    navy = rgb("navy")
    c.d.ellipse([*c.p(x - rx - 4, y - ry - 4), *c.p(x + rx + 4, y + ry + 4)], fill=navy)
    c.d.ellipse([*c.p(x - rx, y - ry), *c.p(x + rx, y + ry)], fill=rgb("white"))
    px, py = x + look[0] * rx, y + look[1] * ry
    pr = min(rx, ry) * 0.55
    c.d.ellipse([*c.p(px - pr, py - pr * 1.15), *c.p(px + pr, py + pr * 1.15)], fill=navy)
    c.d.ellipse([*c.p(px - pr * 0.75, py - pr * 0.8), *c.p(px - pr * 0.15, py - pr * 0.2)], fill=rgb("white"))
    c.d.ellipse([*c.p(px + pr * 0.25, py + pr * 0.35), *c.p(px + pr * 0.55, py + pr * 0.65)], fill=rgb("white"))
    if lid:
        c.d.chord([*c.p(x - rx - 4, y - ry - 4), *c.p(x + rx + 4, y + ry + 4)], 180, 360, fill=lid)


def t_duck_face():
    w = h = 128
    c = Canvas(w, h, rgb("yellow"), world=False)
    big_eye(c, 40, 54, 17, 21, (0.25, 0.15))
    big_eye(c, 88, 54, 17, 21, (0.25, 0.15))
    c.line([(24, 26), (34, 21), (48, 24)], rgb("navy"), 4)
    c.line([(80, 24), (94, 21), (104, 26)], rgb("navy"), 4)
    c.ellipse(22, 84, 11, 7, fill=mix(rgb("yellow"), rgb("coral"), 0.45))
    c.ellipse(106, 84, 11, 7, fill=mix(rgb("yellow"), rgb("coral"), 0.45))
    img = c.result(w, h)
    yy = np.arange(h, dtype=np.float32)[:, None]
    return apply_add(img, np.repeat(14 * np.exp(-((yy - 14) / 10) ** 2), w, axis=1))


def t_unicorn_face():
    """Profil, museau vers la GAUCHE de l'image (= +X monde, convention u = -X)."""
    w = h = 128
    c = Canvas(w, h, rgb("pearl"), world=False)
    c.arc(58, 44, 12, 200, 340, rgb("navy"), 4.5)
    for a in (290, 315, 340):
        r = math.radians(a)
        c.line([(58 + 12 * math.cos(r), 44 + 12 * math.sin(r)), (58 + 20 * math.cos(r + 0.25), 44 + 20 * math.sin(r + 0.25))],
               rgb("navy"), 3)
    c.ellipse(44, 66, 10, 6.5, fill=rgb("pink_light"))
    c.ellipse(13, 68, 3.5, 5, fill=rgb("pink_dark"))
    c.arc(26, 78, 9, 40, 140, rgb("navy"), 3)
    for (x, y, r) in ((84, 30, 5), (94, 56, 3.5)):
        c.poly(star_pts(x, y, r * 0.45, r), fill=rgb("gold"))
    return c.result(w, h)


def t_croc_face():
    """Profil, museau vers la GAUCHE de l'image (+X monde) : gueule en zigzag, dents au feutre."""
    w, h = 256, 128
    c = Canvas(w, h, rgb("green"), world=False)
    xs = [10 + 4 * i for i in range(58)]

    def up(x):
        t = (x - 10) / 228
        return 60 - 22 * t ** 3 + 2 * math.sin(t * 9)

    def gap(x):
        t = (x - 10) / 228
        return 4 + 20 * math.sin(math.pi * min(1.0, t * 1.08)) ** 0.8
    U = [(x, up(x)) for x in xs]
    D = [(x, up(x) + gap(x)) for x in xs]
    c.poly(U + D[::-1], fill=rgb("mouth"))
    c.poly([(x, y + g * 0.55) for (x, y), g in zip(U, [gap(x) for x in xs])][4:-6] + D[4:-6][::-1], fill=rgb("tongue"))
    for i in range(10):  # dents du haut
        x = 18 + i * 21
        y = up(x)
        c.poly([(x - 7, y - 1), (x + 7, y - 1), (x + 1, y + 11)], fill=rgb("white"), outline=rgb("navy"), width=1.6)
    for i in range(9):  # dents du bas
        x = 28 + i * 21
        y = up(x) + gap(x)
        c.poly([(x - 6, y + 1), (x + 6, y + 1), (x, y - 9)], fill=rgb("white"), outline=rgb("navy"), width=1.6)
    c.line(U, rgb("navy"), 3)
    c.line(D, rgb("navy"), 3)
    c.ellipse(26, 24, 6, 3.5, fill=rgb("green_dark"))
    c.ellipse(212, 86, 13, 8, fill=mix(rgb("green"), rgb("coral"), 0.45))
    for (x, y) in ((120, 100), (160, 104), (80, 98)):
        c.circle(x, y, 3, fill=rgb("green_light"))
    for (x, y) in ((90, 22), (140, 18), (180, 26)):
        c.circle(x, y, 4, fill=rgb("green_dark"))
    return c.result(w, h)


def t_cooler_face():
    w, h = 256, 128
    c = Canvas(w, h, rgb("pool"), world=False)
    # grand sourire + langue (les yeux sont modelés)
    c.d.chord([*c.p(70, 22), *c.p(186, 112)], 0, 180, fill=rgb("navy"))
    c.d.chord([*c.p(76, 28), *c.p(180, 106)], 0, 180, fill=rgb("mouth"))
    c.rect(84, 66, 172, 74, fill=rgb("white"), radius=3)
    c.ellipse(128, 98, 26, 12, fill=rgb("tongue"))
    c.ellipse(58, 60, 12, 7, fill=mix(rgb("pool"), rgb("pink"), 0.55))
    c.ellipse(198, 60, 12, 7, fill=mix(rgb("pool"), rgb("pink"), 0.55))
    for (x, y) in ((40, 24), (216, 26)):
        c.poly(star_pts(x, y, 4, 9), fill=rgb("white"))
    img = c.result(w, h)
    return vgrad(img, 0.9, 1.0)


def t_pump_face():
    w = h = 128
    c = Canvas(w, h, rgb("yellow"), world=False)
    big_eye(c, 40, 44, 15, 19, (0.0, -0.3))
    big_eye(c, 88, 44, 15, 19, (0.0, -0.3))
    c.line([(26, 18), (52, 22)], rgb("navy"), 4)
    c.line([(76, 22), (102, 18)], rgb("navy"), 4)
    c.d.chord([*c.p(34, 62), *c.p(94, 118)], 0, 180, fill=rgb("navy"))
    c.d.chord([*c.p(39, 66), *c.p(89, 113)], 0, 180, fill=rgb("mouth"))
    c.rect(42, 86, 86, 91, fill=rgb("white"), radius=2)
    c.ellipse(64, 104, 13, 6, fill=rgb("tongue"))
    c.poly([(112, 30), (118, 44), (112, 50), (106, 44)], fill=rgb("sky"), outline=rgb("pool"), width=1.5)
    return c.result(w, h)


def t_gauge():
    w = h = 128
    c = Canvas(w, h, rgb("white"), world=False)
    c.circle(64, 64, 62, fill=rgb("navy"))
    c.circle(64, 64, 56, fill=rgb("white"))
    for a0, a1, col in ((150, 230, "mint"), (230, 330, "yellow"), (330, 390, "coral")):
        c.wedge(64, 64, 40, 50, a0, a1, rgb(col), n=20)
    for i in range(11):
        a = math.radians(150 + 24 * i)
        c.line([(64 + 34 * math.cos(a), 64 + 34 * math.sin(a)), (64 + 40 * math.cos(a), 64 + 40 * math.sin(a))],
               rgb("navy"), 2.5)
    a = math.radians(352)
    c.line([(64 - 8 * math.cos(a), 64 - 8 * math.sin(a)), (64 + 44 * math.cos(a), 64 + 44 * math.sin(a))],
           rgb("red"), 5)
    c.circle(64, 64, 7, fill=rgb("navy"))
    c.poly(star_pts(64, 96, 4, 9), fill=rgb("yellow"), outline=rgb("navy"), width=1.5)
    return c.result(w, h)


def t_eye():
    w = h = 64
    c = Canvas(w, h, rgb("white"), world=False)
    c.circle(32, 32, 31, fill=rgb("white"))
    c.circle(38, 26, 15, fill=rgb("navy"))
    c.circle(33, 21, 5, fill=rgb("white"))
    c.circle(43, 31, 2.2, fill=rgb("white"))
    return c.result(w, h)


def t_badge_sun():
    w = h = 64
    c = Canvas(w, h, rgb("pool"), world=False)
    c.circle(32, 32, 31, fill=rgb("pool"))
    for i in range(12):
        a = math.radians(i * 30)
        c.poly([(32 + 16 * math.cos(a - 0.2), 32 + 16 * math.sin(a - 0.2)), (32 + 27 * math.cos(a), 32 + 27 * math.sin(a)),
                (32 + 16 * math.cos(a + 0.2), 32 + 16 * math.sin(a + 0.2))], fill=rgb("yellow"))
    c.circle(32, 32, 16, fill=rgb("yellow"))
    c.circle(26, 29, 2.2, fill=rgb("navy"))
    c.circle(38, 29, 2.2, fill=rgb("navy"))
    c.arc(32, 33, 7, 20, 160, rgb("navy"), 2)
    return c.result(w, h)


def t_donut_face():
    w, h = 128, 64
    c = Canvas(w, h, rgb("dough"), world=False)
    c.arc(44, 30, 8, 200, 340, rgb("navy"), 3.5)
    c.arc(84, 30, 8, 200, 340, rgb("navy"), 3.5)
    c.d.chord([*c.p(52, 30), *c.p(76, 54)], 0, 180, fill=rgb("mouth"))
    c.ellipse(64, 48, 6, 3, fill=rgb("tongue"))
    c.ellipse(30, 42, 7, 4, fill=mix(rgb("dough"), rgb("coral"), 0.5))
    c.ellipse(98, 42, 7, 4, fill=mix(rgb("dough"), rgb("coral"), 0.5))
    img = c.result(w, h)
    return vgrad(img, 0.88, 1.0)


def t_rainbow():
    w, h = 128, 64
    c = Canvas(w, h, rgb("white"), world=False)
    bands = ["red", "orange", "yellow", "mint", "pool", "lilac"]
    for i, b in enumerate(bands):
        c.rect(0, i * h / 6, w, (i + 1) * h / 6, fill=rgb(b))
    img = c.result(w, h)
    return apply_mult(img, puff_rows(w, h, 6, 0, 0.12, 0.04))


def t_valve_label():
    w, h = 128, 64
    c = Canvas(w, h, rgb("white"), world=False)
    c.rect(2, 2, w - 2, h - 2, fill=rgb("white"), outline=rgb("pool"), width=3, radius=10)
    c.circle(30, 32, 18, fill=rgb("pool"))
    c.poly([(30, 18), (40, 34), (30, 46), (20, 34)], fill=rgb("white"))
    for k in range(3):
        c.rect(58, 18 + k * 11, 112 - 14 * k, 24 + k * 11, fill=rgb("navy_light"), radius=2)
    return c.result(w, h)


def t_pedal():
    w, h = 256, 128
    c = Canvas(w, h, rgb("orange"), world=False)
    c.rect(4, 4, w - 4, h - 4, outline=rgb("orange_dark"), width=4, radius=16)
    c.rect(56, 16, 200, 112, fill=rgb("rubber"), radius=18)
    for k in range(6):
        c.rect(66 + k * 22, 24, 74 + k * 22, 104, fill=shade(rgb("rubber"), 1.4), radius=4)
    c.ellipse(128, 70, 16, 26, fill=rgb("yellow"))
    for (dx, dy, r) in ((-14, -34, 6), (-3, -39, 5), (7, -38, 4.5), (15, -34, 4), (21, -27, 3.5)):
        c.circle(128 + dx, 70 + dy, r, fill=rgb("yellow"))
    for x in (28, 228):
        c.poly(star_pts(x, 64, 6, 13), fill=rgb("yellow"), outline=rgb("orange_dark"), width=2)
    return c.result(w, h)


def palette_tile():
    img = Image.new("RGB", (256, 256), (255, 0, 255))
    for name in PALETTE_ORDER:
        x0, y0, x1, y1 = cell_rect(name)
        cell = Image.new("RGB", (CELL_W, CELL_H), rgb(name))
        cell = vgrad(cell, 0.8, 1.03, top_frac=0.85)
        img.paste(cell, (x0, y0 - 768))
    return img


def build_atlas():
    rng = np.random.default_rng(SEED)
    atlas = Image.new("RGB", (SIZE, SIZE), rgb("water"))
    rough = Image.new("RGB", (SIZE, SIZE), (0, int(255 * ROUGH_VINYL), 0))
    tops = {"duck_top": t_duck_top, "flamingo_top": t_flamingo_top, "donut_top": t_donut_top,
            "unicorn_top": t_unicorn_top, "croc_top": t_croc_top, "mattress_top": t_mattress_top,
            "cooler_lid": t_cooler_lid, "ball_top": t_ball_top}
    for name, fn in tops.items():
        x0, y0, x1, y1 = TILES[name]
        atlas.paste(fn(rng).resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    sides = {
        "s_duck": side_vinyl(rng, "yellow"), "s_pink": side_vinyl(rng, "pink"),
        "s_pearl": side_vinyl(rng, "pearl", (0.62,)), "s_croc": side_croc(rng), "s_cooler": side_cooler(rng),
        "s_mattress": side_mattress(rng), "s_ball": side_ball(rng), "s_donut": side_donut(rng),
    }
    for name, im in sides.items():
        x0, y0, _x1, _y1 = TILES[name]
        atlas.paste(im, (x0, y0))
    extra = {"duck_face": t_duck_face(), "unicorn_face": t_unicorn_face(), "croc_face": t_croc_face(),
             "cooler_face": t_cooler_face(), "pump_face": t_pump_face(), "gauge": t_gauge(), "eye": t_eye(),
             "badge_sun": t_badge_sun(), "donut_face": t_donut_face(), "rainbow": t_rainbow(),
             "valve_label": t_valve_label(), "pedal": t_pedal()}
    for name, im in extra.items():
        x0, y0, x1, y1 = TILES[name]
        atlas.paste(im.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    atlas.paste(palette_tile(), (0, 768))
    rd = ImageDraw.Draw(rough)
    for name, (x0, y0, x1, y1) in TILES.items():
        rd.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(0, int(255 * ROUGH.get(name, ROUGH_VINYL)), 0))
    for name in PALETTE_ORDER:
        x0, y0, x1, y1 = cell_rect(name)
        rd.rectangle([x0, y0, x1 - 1, y1 - 1],
                     fill=(0, int(255 * PAL_ROUGH.get(name, ROUGH_VINYL)), int(255 * PAL_METAL.get(name, 0.0))))
    return atlas, rough


def save_atlas(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    atlas, rough = build_atlas()
    p0 = os.path.join(out_dir, "pool_atlas_1024.png")
    p1 = os.path.join(out_dir, "pool_atlas_rough_1024.png")
    atlas.save(p0, optimize=True)
    rough.save(p1, optimize=True)
    return p0, p1


if __name__ == "__main__":
    print(save_atlas(sys.argv[1] if len(sys.argv) > 1 else "."))
