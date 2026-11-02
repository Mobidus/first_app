"""Atlas de texture partagé des canards gonflables (1 024 px, peint procéduralement).

Aucune image externe : tout est dessiné ici (PIL, suréchantillonnage x4, graine fixe).
Importé par duck_kit.py / build_ducks.py (UV) ; peut être lancé seul :
    .venv/bin/python -I assets/source/blender/duck_atlas.py <dossier_sortie>

Disposition (pixels, origine en haut à gauche) :
  ligne 0 (0-256)   : pont matelassé | filet trampoline | imprimé hawaïen | pont de l'île géante
  ligne 1 (256-512) : flanc vinyle, dessus du matelas | marinière, rayures maillot | visage | oeil, crâne,
                      ancre, appareil photo
  ligne 2 (512-768) : bonnet à fleurs, cape | paille, bec, SAUVETEUR, galon | aile | dessus de bouée
                      + collier de fleurs, pois, valve, bulle, verre de lunettes
  ligne 3 (768-1024): palette dégradée 32 cellules | imprimé hawaïen large (matelas) | réserve
Couleurs : canard #FFD23F, bec #FF9B47, pupilles #203055, palette piscine (#1FA8E0, #FF7FB8, #FF684B,
#39E68B). Le second fichier (rough) suit glTF metallicRoughness : G = rugosité, B = métal.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 1024
SS = 4
SEED = 20261102

HEX = {
    "yellow": "#FFD23F", "yellow_dark": "#E3A51A", "yellow_light": "#FFE88A", "orange": "#FF9B47",
    "orange_dark": "#E07122", "navy": "#203055", "navy_light": "#3A5288", "white": "#FBFBF6",
    "cream": "#FFF5DF", "pool": "#1FA8E0", "pool_dark": "#12719E", "pink": "#FF7FB8",
    "pink_dark": "#E0509A", "coral": "#FF684B", "coral_dark": "#D4442C", "mint": "#39E68B",
    "mint_dark": "#1FAE63", "red": "#E8343A", "red_dark": "#A81C27", "gold": "#F7BE2E",
    "gold_dark": "#C2840E", "black": "#1E2029", "steel": "#A9B6CC", "straw": "#EFCB7B",
    "straw_dark": "#C79A45", "lens": "#1B2647", "glass": "#BDEFFF", "violet": "#8855FF",
    "brown": "#8A5A3C", "leaf": "#2FAF6A", "khaki": "#D8C08E", "blush": "#FF9DB0",
}


def rgb(name_or_hex):
    h = HEX.get(name_or_hex, name_or_hex).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(c, f):
    return tuple(int(max(0, min(255, round(v * f)))) for v in c)


def mix(a, b, t):
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))


TILES = {
    # ligne 0
    "deck": (0, 0, 256, 256), "net": (256, 0, 512, 256), "hawaii": (512, 0, 768, 256),
    "island_top": (768, 0, 1024, 256),
    # ligne 1
    "s_vinyl": (0, 256, 256, 384), "lilo_top": (0, 384, 256, 512),
    "mariniere": (256, 256, 512, 384), "swim_stripes": (256, 384, 512, 512),
    "face": (512, 256, 768, 512),
    "eye": (768, 256, 896, 384), "skull": (896, 256, 1024, 384),
    "anchor": (768, 384, 896, 512), "camera": (896, 384, 1024, 512),
    # ligne 2
    "flower_cap": (0, 512, 256, 640), "cape": (0, 640, 256, 768),
    "straw": (256, 512, 384, 640), "bill": (384, 512, 512, 640),
    "sauveteur": (256, 640, 512, 704), "captain_band": (256, 704, 512, 768),
    "wing": (512, 512, 768, 640), "lei": (512, 640, 768, 704),
    "polka": (512, 704, 640, 768), "valve": (640, 704, 704, 768), "bubble": (704, 704, 768, 768),
    "ring_top": (768, 512, 1024, 768),
    # ligne 3
    "lilo_hawaii": (256, 768, 768, 1024), "lens": (768, 768, 896, 896),
}

PALETTE_ORDER = [
    "yellow", "yellow_dark", "yellow_light", "orange", "orange_dark", "navy", "navy_light", "white",
    "cream", "pool", "pool_dark", "pink", "pink_dark", "coral", "coral_dark", "mint",
    "mint_dark", "red", "red_dark", "gold", "gold_dark", "black", "steel", "straw",
    "straw_dark", "lens", "glass", "violet", "brown", "leaf", "khaki", "blush",
]
CELL_W, CELL_H = 32, 64
PAL_Y0 = 768

ROUGH = {
    "deck": 0.3, "net": 0.7, "hawaii": 0.32, "island_top": 0.3, "s_vinyl": 0.26, "lilo_top": 0.28,
    "mariniere": 0.34, "swim_stripes": 0.34, "face": 0.26, "eye": 0.18, "skull": 0.3, "anchor": 0.3,
    "camera": 0.35, "flower_cap": 0.4, "cape": 0.85, "straw": 0.9, "bill": 0.3, "sauveteur": 0.32,
    "captain_band": 0.6, "wing": 0.28, "lei": 0.75, "polka": 0.7, "valve": 0.3, "bubble": 0.05,
    "ring_top": 0.28, "lilo_hawaii": 0.32, "lens": 0.06,
}
PAL_ROUGH = {"yellow": 0.26, "yellow_dark": 0.28, "yellow_light": 0.26, "orange": 0.3, "orange_dark": 0.3,
             "navy": 0.45, "white": 0.35, "cream": 0.6, "black": 0.5, "gold": 0.28, "gold_dark": 0.3,
             "steel": 0.25, "straw": 0.9, "straw_dark": 0.9, "lens": 0.06, "glass": 0.05, "brown": 0.55,
             "khaki": 0.85, "red": 0.5, "red_dark": 0.7, "leaf": 0.6, "blush": 0.5}
PAL_METAL = {"gold": 0.9, "gold_dark": 0.85, "steel": 0.6}


def cell_rect(name):
    i = PALETTE_ORDER.index(name)
    col, row = i % 8, i // 8
    return (col * CELL_W, PAL_Y0 + row * CELL_H, col * CELL_W + CELL_W, PAL_Y0 + row * CELL_H + CELL_H)


def px_to_uv(rect, margin_px=1.5):
    x0, y0, x1, y1 = rect
    return ((x0 + margin_px) / SIZE, 1 - (y1 - margin_px) / SIZE, (x1 - margin_px) / SIZE, 1 - (y0 + margin_px) / SIZE)


def tile_uv(name, margin_px=1.5):
    return px_to_uv(TILES[name], margin_px)


def cell_uv(name):
    return px_to_uv(cell_rect(name), 3.0)


# --- outils de dessin ----------------------------------------------------------
class Canvas:
    """Dessin en pixels de tuile (x à droite, y vers le bas), suréchantillonné."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * SS, h * SS), bg)
        self.d = ImageDraw.Draw(self.img)

    def p(self, x, y):
        return (x * SS, y * SS)

    def circle(self, x, y, r, fill=None, outline=None, width=0.0):
        self.d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=fill, outline=outline,
                       width=max(1, int(width * SS)) if outline else 0)

    def ellipse(self, x, y, rx, ry, fill=None, outline=None, width=0.0):
        self.d.ellipse([(x - rx) * SS, (y - ry) * SS, (x + rx) * SS, (y + ry) * SS], fill=fill, outline=outline,
                       width=max(1, int(width * SS)) if outline else 0)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=0.0, radius=0.0):
        self.d.rounded_rectangle([min(x0, x1) * SS, min(y0, y1) * SS, max(x0, x1) * SS, max(y0, y1) * SS],
                                 radius=radius * SS, fill=fill, outline=outline,
                                 width=max(1, int(width * SS)) if outline else 0)

    def poly(self, pts, fill=None, outline=None, width=0.0):
        P = [self.p(*q) for q in pts]
        self.d.polygon(P, fill=fill)
        if outline:
            self.d.line(P + [P[0]], fill=outline, width=max(1, int(width * SS)), joint="curve")

    def line(self, pts, fill, width):
        P = [self.p(*q) for q in pts]
        self.d.line(P, fill=fill, width=max(1, int(width * SS)), joint="curve")
        r = width * SS / 2
        for q in (P[0], P[-1]):
            self.d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=fill)

    def text(self, x, y, s, size, fill, anchor="mm"):
        f = font(int(size * SS))
        self.d.text((x * SS, y * SS), s, fill=fill, font=f, anchor=anchor)

    def result(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def apply_mult(img, m):
    a = np.asarray(img, dtype=np.float32) * m[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def noise_layer(w, h, rng, scale, amp):
    gw, gh = max(2, int(w / scale)), max(2, int(h / scale))
    g = rng.normal(0, 1, (gh, gw)).astype(np.float32)
    im = Image.fromarray(((g - g.min()) / (np.ptp(g) + 1e-6) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    a = np.asarray(im, dtype=np.float32) / 255.0
    return 1.0 + (a - 0.5) * 2 * amp


def vgrad(img, bottom=0.8, top=1.0, top_frac=0.75):
    w, h = img.size
    t = np.clip(np.linspace(1, 0, h, dtype=np.float32) / top_frac, 0, 1)
    f = bottom + (top - bottom) * (t ** 0.8)
    return apply_mult(img, np.repeat(f[:, None], w, axis=1))


def radial_glow(img, cx, cy, r, amp):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    return apply_mult(img, 1 + amp * np.clip(1 - d, 0, 1) ** 2)


def edge_dark(img, band_px, amount):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy])
    return apply_mult(img, 1 - amount * np.clip(1 - d / band_px, 0, 1) ** 1.5)


# --- motifs réutilisables --------------------------------------------------------
def flower(c, x, y, r, petal, centre, n=5, rot=0.0, outline=None):
    for k in range(n):
        a = rot + 2 * math.pi * k / n
        c.circle(x + 0.55 * r * math.cos(a), y + 0.55 * r * math.sin(a), 0.48 * r, fill=petal)
    if outline:
        for k in range(n):
            a = rot + 2 * math.pi * k / n + math.pi / n
            c.line([(x + 0.25 * r * math.cos(a), y + 0.25 * r * math.sin(a)),
                    (x + 0.75 * r * math.cos(a), y + 0.75 * r * math.sin(a))], outline, max(0.6, 0.06 * r))
    c.circle(x, y, 0.3 * r, fill=centre)


def hibiscus(c, x, y, r, petal, rot):
    dark = shade(petal, 0.78)
    for k in range(5):
        a = rot + 2 * math.pi * k / 5
        px, py = x + 0.52 * r * math.cos(a), y + 0.52 * r * math.sin(a)
        c.circle(px, py, 0.5 * r, fill=petal)
    for k in range(5):
        a = rot + 2 * math.pi * k / 5
        c.line([(x, y), (x + 0.75 * r * math.cos(a), y + 0.75 * r * math.sin(a))], dark, max(0.8, 0.07 * r))
    c.circle(x, y, 0.2 * r, fill=rgb("red_dark"))
    a = rot + 0.6
    c.line([(x, y), (x + 0.95 * r * math.cos(a), y + 0.95 * r * math.sin(a))], rgb("yellow"), max(0.8, 0.07 * r))
    c.circle(x + 0.95 * r * math.cos(a), y + 0.95 * r * math.sin(a), 0.1 * r, fill=rgb("yellow"))


def leaf(c, x, y, L, ang, col):
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    for i in range(13):
        t = i / 12
        w = 0.28 * L * math.sin(math.pi * t)
        pts.append((t * L, w))
    pts += [(t * L, -0.28 * L * math.sin(math.pi * t)) for t in [i / 12 for i in range(12, -1, -1)]]
    P = [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]
    c.poly(P, fill=col)
    c.line([(x, y), (x + L * 0.95 * ca, y + L * 0.95 * sa)], shade(col, 0.7), max(0.7, 0.05 * L))


def hawaii_print(w, h, rng, density=1.0, base="pool"):
    """Imprimé chemise hawaïenne raccordable (dessin répété aux bords)."""
    c = Canvas(w, h, rgb(base))
    items = []
    n = int(w * h / 2600 * density)
    for _ in range(n):
        items.append((rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0, 2 * math.pi), rng.integers(0, 6),
                      rng.uniform(0.75, 1.2)))
    cols = [rgb("pink"), rgb("coral"), rgb("yellow"), rgb("white"), rgb("pink_dark"), rgb("coral")]
    for ox in (-w, 0, w):
        for oy in (-h, 0, h):
            for x, y, a, k, s in items:
                if k in (1, 4):
                    leaf(c, x + ox, y + oy, 30 * s, a, rgb("leaf") if k == 1 else rgb("mint_dark"))
    for ox in (-w, 0, w):
        for oy in (-h, 0, h):
            for x, y, a, k, s in items:
                if k in (0, 2, 5):
                    hibiscus(c, x + ox, y + oy, 14 * s, cols[k], a)
                elif k == 3:
                    flower(c, x + ox, y + oy, 8 * s, rgb("white"), rgb("yellow"), rot=a)
    return c.result()


# --- tuiles --------------------------------------------------------------------
def t_deck(rng):
    """Selle plate rembourrée : panneaux matelassés soudés, liseré, petit pictogramme valve."""
    w = h = 256
    base = rgb("yellow")
    c = Canvas(w, h, shade(base, 0.97))
    c.rect(10, 10, w - 10, h - 10, fill=base, radius=26)
    cols, rows = 3, 3
    pw, ph = (w - 40) / cols, (h - 40) / rows
    for i in range(cols):
        for j in range(rows):
            x0, y0 = 20 + i * pw, 20 + j * ph
            c.rect(x0 + 3, y0 + 3, x0 + pw - 3, y0 + ph - 3, fill=mix(base, rgb("yellow_light"), 0.55), radius=14)
            c.rect(x0 + 9, y0 + 9, x0 + pw - 9, y0 + ph - 9, fill=mix(base, rgb("yellow_light"), 0.3), radius=10)
    # soudures : double trait sombre + clair
    for i in range(1, cols):
        x = 20 + i * pw
        c.line([(x, 16), (x, h - 16)], mix(base, rgb("yellow_dark"), 0.7), 2.0)
        c.line([(x + 2.2, 16), (x + 2.2, h - 16)], rgb("yellow_light"), 1.0)
    for j in range(1, rows):
        y = 20 + j * ph
        c.line([(16, y), (w - 16, y)], mix(base, rgb("yellow_dark"), 0.7), 2.0)
        c.line([(16, y + 2.2), (w - 16, y + 2.2)], rgb("yellow_light"), 1.0)
    c.rect(10, 10, w - 10, h - 10, outline=rgb("yellow_dark"), width=3, radius=26)
    c.rect(16, 16, w - 16, h - 16, outline=shade(rgb("yellow_light"), 1.02), width=1.2, radius=22)
    img = c.result()
    for i in range(cols):
        for j in range(rows):
            img = radial_glow(img, 20 + (i + 0.4) * pw, 20 + (j + 0.35) * ph, pw * 0.45, 0.08)
    img = apply_mult(img, noise_layer(w, h, rng, 50, 0.02))
    return edge_dark(img, 8, 0.12)


def t_island_top(rng):
    """Pont de l'île géante : matelassage 4 x 4, barre de navire marine imprimée, bord en corde."""
    w = h = 256
    base = rgb("yellow")
    c = Canvas(w, h, base)
    n = 4
    pw = (w - 28) / n
    for i in range(n):
        for j in range(n):
            x0, y0 = 14 + i * pw, 14 + j * pw
            c.rect(x0 + 2, y0 + 2, x0 + pw - 2, y0 + pw - 2, fill=rgb("yellow_light"), radius=10)
            c.rect(x0 + 7, y0 + 7, x0 + pw - 7, y0 + pw - 7, fill=mix(base, rgb("yellow_light"), 0.5), radius=8)
    for i in range(1, n):
        p = 14 + i * pw
        c.line([(p, 12), (p, h - 12)], rgb("yellow_dark"), 2.0)
        c.line([(12, p), (w - 12, p)], rgb("yellow_dark"), 2.0)
    # corde (tirets crème + ombre) le long du bord
    for k in range(64):
        t0, t1 = k / 64, (k + 0.6) / 64
        for (ax, ay, bx, by) in ((8, 8, w - 8, 8), (w - 8, 8, w - 8, h - 8), (w - 8, h - 8, 8, h - 8), (8, h - 8, 8, 8)):
            c.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)],
                   rgb("cream"), 3.4)
    # barre de navire au centre (imprimée)
    cx, cy, R = w / 2, h / 2, 54
    navy = rgb("navy")
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        c.line([(cx, cy), (cx + (R + 16) * math.cos(a), cy + (R + 16) * math.sin(a))], navy, 6)
        c.circle(cx + (R + 18) * math.cos(a), cy + (R + 18) * math.sin(a), 6.5, fill=navy)
    c.circle(cx, cy, R, outline=navy, width=9)
    c.circle(cx, cy, R - 14, outline=navy, width=3)
    c.circle(cx, cy, 13, fill=navy)
    c.circle(cx, cy, 6, fill=rgb("gold"))
    img = c.result()
    img = apply_mult(img, noise_layer(w, h, rng, 50, 0.02))
    return edge_dark(img, 6, 0.1)


def t_net(rng):
    """Filet trampoline tendu : fond bleu piscine, mailles blanches en losange, noeuds, bordure."""
    w = h = 256
    c = Canvas(w, h, rgb("pool_dark"))
    c.rect(0, 0, w, h, fill=rgb("pool"))
    step = 21.3
    for k in range(-14, 15):
        x0 = k * step
        c.line([(x0, 0), (x0 + h, h)], shade(rgb("white"), 0.75), 4.0)
        c.line([(x0 + h, 0), (x0, h)], shade(rgb("white"), 0.75), 4.0)
    for k in range(-14, 15):
        x0 = k * step
        c.line([(x0, 0), (x0 + h, h)], rgb("white"), 2.4)
        c.line([(x0 + h, 0), (x0, h)], rgb("white"), 2.4)
    # noeuds aux croisements : croisements des diagonales x+y = k*step et x-y = m*step
    for a in range(-14, 30):
        for b in range(-14, 30):
            u, v = a * step, b * step  # x + y = u , x - y = v (pour x0 + y et x0 - y)
            x, y = (u + v) / 2, (u - v) / 2
            if -4 <= x <= w + 4 and -4 <= y <= h + 4:
                c.circle(x, y, 3.2, fill=rgb("white"))
    # bordure (lien du filet sur la bouée)
    c.rect(2, 2, w - 2, h - 2, outline=rgb("navy"), width=7, radius=40)
    c.rect(9, 9, w - 9, h - 9, outline=rgb("white"), width=2.5, radius=34)
    img = c.result()
    return apply_mult(img, noise_layer(w, h, rng, 60, 0.03))


def t_s_vinyl(rng):
    """Flanc vinyle jaune : v = hauteur ; reflet doux près du haut, soudure de l'équateur."""
    w, h = 256, 128
    c = Canvas(w, h, rgb("yellow"))
    img = c.result()
    img = vgrad(img, 0.8, 1.04, top_frac=0.8)
    a = np.asarray(img, dtype=np.float32)
    yy = np.arange(h, dtype=np.float32)[:, None]
    hl = np.exp(-((yy - h * 0.2) / (h * 0.06)) ** 2) * 0.22
    a = a + (255 - a) * hl[..., None]
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return apply_mult(img, noise_layer(w, h, rng, 40, 0.015))


# boudins du matelas (centres en studs, demi-profondeur de projection) : partagés avec duck_kit
LILO_TUBE_Y = (-2.9, -1.45, 0.0, 1.45, 2.9)
LILO_HALF_D = 4.0


def t_lilo_top(rng):
    """Dessus du matelas : 5 boudins longitudinaux, creux soudés, reflets ; u = longueur, v = largeur.

    Projection m_top : rangée d'image 0 = monde -Y (arrière), bas de l'image = avant (+Y). Les creux tombent entre les centres LILO_TUBE_Y."""
    w, h = 256, 128
    img = Image.new("RGB", (w, h), rgb("yellow"))
    a = np.asarray(img, dtype=np.float32)
    ys = -LILO_HALF_D + (np.arange(h, dtype=np.float32) + 0.5) / h * 2 * LILO_HALF_D  # monde y par rangée
    cs = np.array(LILO_TUBE_Y, dtype=np.float32)
    k = np.argmin(np.abs(ys[:, None] - cs[None, :]), axis=1)
    dy = ys - cs[k]
    half = np.where(dy > 0, np.where(k == len(cs) - 1, 1.1, 0.725), np.where(k == 0, 1.1, 0.725))
    t = np.clip(np.abs(dy) / half, 0, 1)
    shade_f = 1.04 - 0.24 * t ** 2.5
    hl = np.exp(-((dy + 0.25) / 0.16) ** 2) * 0.3
    a = a * shade_f[:, None, None]
    a = a + (255 - a) * hl[:, None, None]
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for y0, y1 in zip(LILO_TUBE_Y[:-1], LILO_TUBE_Y[1:]):
        r = (LILO_HALF_D + (y0 + y1) / 2) / (2 * LILO_HALF_D) * h
        d.line([(0, r), (w, r)], fill=rgb("yellow_dark"), width=2)
    # bouts soudés (gauche/droite)
    d.rectangle([0, 0, 5, h], fill=rgb("yellow_dark"))
    d.rectangle([w - 6, 0, w, h], fill=rgb("yellow_dark"))
    return apply_mult(img, noise_layer(w, h, rng, 40, 0.02))


def t_stripes(w, h, cols, n, piping=None):
    c = Canvas(w, h, cols[1])
    sh = h / n
    for k in range(n):
        if k % 2 == 0:
            c.rect(0, k * sh, w, (k + 1) * sh, fill=cols[0])
    if piping:
        c.rect(0, 0, w, 4, fill=piping)
        c.rect(0, h - 4, w, h, fill=piping)
    return c.result()


# position des yeux dans le visage (fractions de la largeur/hauteur de la tête), partagée avec duck_kit
EYE_U, EYE_V, EYE_RU, EYE_RV = 0.2, 0.59, 0.135, 0.15


def t_face(rng):
    """Visage (projection de face) : jaune, joues roses, reflet sur le front ; yeux peints pour le LOD1
    (au LOD0, des dômes d'oeil couvrent exactement ces yeux)."""
    w = h = 256
    c = Canvas(w, h, rgb("yellow"))
    for sx in (-1, 1):
        c.ellipse(128 + sx * 84, 172, 24, 15, fill=rgb("blush"))
    img = c.result().filter(ImageFilter.GaussianBlur(2.5))
    img = radial_glow(img, 96, 60, 70, 0.14)
    img = vgrad(img, 0.88, 1.04, top_frac=0.9)
    img = apply_mult(img, noise_layer(w, h, rng, 40, 0.012))
    # sourcils (comme le canard de la famille Piscine) : arcs marine au-dessus des yeux
    d = ImageDraw.Draw(img)
    for sx in (-1, 1):
        cx = w * (0.5 + sx * EYE_U)
        top = h * (1 - EYE_V - EYE_RV) - 9
        pts = [(cx + sx * (-20 + 40 * t / 8), top - 7 * math.sin(math.pi * t / 8) + sx * 0 + (3 if t < 4 else 0) * 0)
               for t in range(9)]
        d.line(pts, fill=rgb("navy"), width=6, joint="curve")
        for q in (pts[0], pts[-1]):
            d.ellipse([q[0] - 3, q[1] - 3, q[0] + 3, q[1] + 3], fill=rgb("navy"))
    eye = t_eye()
    ew, eh = int(2 * EYE_RU * w), int(2 * EYE_RV * h)
    em = Image.new("L", (128 * SS, 128 * SS), 0)
    ImageDraw.Draw(em).ellipse([0, 0, 128 * SS - 1, 128 * SS - 1], fill=255)
    em = em.resize((ew, eh), Image.LANCZOS)
    for sx in (-1, 1):
        cx, cy = w * (0.5 + sx * EYE_U), h * (1 - EYE_V)
        e = eye.resize((ew, eh), Image.LANCZOS)
        if sx > 0:
            e = e.transpose(Image.FLIP_LEFT_RIGHT)
        img.paste(e, (int(round(cx - ew / 2)), int(round(cy - eh / 2))), em)
    return img


def t_eye():
    w = h = 128
    c = Canvas(w, h, rgb("navy"))
    c.circle(64, 64, 61, fill=rgb("white"))
    c.circle(64, 64, 61, outline=rgb("navy"), width=5)
    c.circle(66, 70, 37, fill=rgb("navy"))
    c.circle(66, 70, 30, fill=rgb("navy_light"))
    c.circle(66, 70, 25, fill=rgb("navy"))
    c.circle(52, 54, 13, fill=rgb("white"))
    c.circle(78, 84, 5.5, fill=rgb("white"))
    return c.result()


def t_skull():
    w = h = 128
    c = Canvas(w, h, rgb("black"))
    c.circle(64, 64, 62, fill=rgb("white"))
    c.circle(64, 64, 55, fill=rgb("black"))
    wh = rgb("white")
    for a in (45, 135):
        r = math.radians(a)
        dx, dy = 36 * math.cos(r), 36 * math.sin(r)
        c.line([(64 - dx, 74 - dy), (64 + dx, 74 + dy)], wh, 9)
        for s in (-1, 1):
            c.circle(64 + s * dx + s * 4 * math.cos(r + 1.2), 74 + s * dy + s * 4 * math.sin(r + 1.2), 7, fill=wh)
            c.circle(64 + s * dx + s * 4 * math.cos(r - 1.2), 74 + s * dy + s * 4 * math.sin(r - 1.2), 7, fill=wh)
    c.ellipse(64, 52, 25, 23, fill=wh)
    c.rect(50, 60, 78, 80, fill=wh, radius=6)
    c.circle(54, 52, 7.5, fill=rgb("black"))
    c.circle(74, 52, 7.5, fill=rgb("black"))
    c.poly([(64, 60), (60, 67), (68, 67)], fill=rgb("black"))
    for k in range(4):
        c.line([(55 + k * 6, 72), (55 + k * 6, 80)], rgb("black"), 2)
    return c.result()


def anchor_icon(c, x, y, s, col, width):
    c.circle(x, y - 0.62 * s, 0.13 * s, outline=col, width=width * 0.8)
    c.line([(x, y - 0.5 * s), (x, y + 0.55 * s)], col, width)
    c.line([(x - 0.3 * s, y - 0.32 * s), (x + 0.3 * s, y - 0.32 * s)], col, width)
    pts = [(x + 0.5 * s * math.cos(math.radians(a)), y + 0.12 * s + 0.45 * s * math.sin(math.radians(a)))
           for a in range(10, 171, 10)]
    c.line(pts, col, width)
    for sx in (-1, 1):
        px, py = x + sx * 0.5 * s * math.cos(math.radians(10)), y + 0.12 * s + 0.45 * s * math.sin(math.radians(10))
        c.poly([(px - 0.12 * s, py - 0.02 * s), (px + 0.12 * s, py - 0.02 * s), (px, py - 0.22 * s)], fill=col)


def t_anchor():
    w = h = 128
    c = Canvas(w, h, rgb("gold"))
    c.circle(64, 64, 62, fill=rgb("gold"))
    c.circle(64, 64, 54, fill=rgb("navy"))
    anchor_icon(c, 64, 66, 70, rgb("gold"), 8)
    return c.result()


def t_camera():
    w = h = 128
    c = Canvas(w, h, rgb("black"))
    c.rect(0, 0, w, 30, fill=rgb("steel"))
    c.rect(0, 26, w, 32, fill=shade(rgb("steel"), 0.7))
    c.circle(64, 76, 42, fill=rgb("steel"))
    c.circle(64, 76, 36, fill=rgb("black"))
    c.circle(64, 76, 27, fill=rgb("pool_dark"))
    c.circle(64, 76, 18, fill=rgb("lens"))
    c.circle(55, 66, 7, fill=rgb("white"))
    c.rect(96, 8, 120, 22, fill=rgb("white"), radius=3)
    c.circle(16, 15, 6, fill=rgb("coral"))
    return c.result()


def t_flower_cap(rng):
    """Bonnet de bain bleu piscine à fleurs (u = tour, v = hauteur)."""
    w, h = 256, 128
    c = Canvas(w, h, rgb("pool"))
    pts = [(rng.uniform(0, w), rng.uniform(18, h - 10), rng.uniform(0, 6.28), int(rng.integers(0, 3)),
            rng.uniform(0.8, 1.2)) for _ in range(22)]
    cols = [(rgb("pink"), rgb("yellow")), (rgb("white"), rgb("coral")), (rgb("mint"), rgb("white"))]
    for ox in (-w, 0, w):
        for x, y, a, k, s in pts:
            flower(c, x + ox, y, 13 * s, cols[k][0], cols[k][1], rot=a)
    c.rect(0, h - 10, w, h, fill=rgb("pool_dark"))
    img = c.result()
    return vgrad(img, 0.85, 1.04)


def t_cape(rng):
    """Cape de velours rouge : plis verticaux, galon or en bas, hermine en haut ; u = tour, v = hauteur."""
    w, h = 256, 128
    img = Image.new("RGB", (w, h), rgb("red"))
    a = np.asarray(img, dtype=np.float32)
    xx = np.arange(w, dtype=np.float32)[None, :]
    folds = 0.82 + 0.2 * (0.5 + 0.5 * np.sin(xx / w * 2 * math.pi * 7))
    a = a * folds[..., None]
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    c = Canvas(w, h, (0, 0, 0))
    c.img = img.resize((w * SS, h * SS))
    c.d = ImageDraw.Draw(c.img)
    c.rect(0, h - 16, w, h - 6, fill=rgb("gold"))
    c.rect(0, h - 6, w, h, fill=rgb("gold_dark"))
    for k in range(16):
        c.circle(8 + k * 16, h - 11, 2.2, fill=rgb("gold_dark"))
    c.rect(0, 0, w, 24, fill=rgb("white"))
    for k in range(12):
        x = 10 + k * 21 + (6 if k % 2 else 0)
        c.poly([(x, 7), (x - 3, 16), (x + 3, 16)], fill=rgb("black"))
    return c.result()


def t_straw(rng):
    w = h = 128
    c = Canvas(w, h, rgb("straw"))
    n = 10
    s = w / n
    for i in range(n):
        for j in range(n):
            x0, y0 = i * s, j * s
            if (i + j) % 2 == 0:
                for k in range(3):
                    c.line([(x0 + 1, y0 + 2 + k * 4), (x0 + s - 1, y0 + 2 + k * 4)], rgb("straw_dark"), 1.0)
            else:
                for k in range(3):
                    c.line([(x0 + 2 + k * 4, y0 + 1), (x0 + 2 + k * 4, y0 + s - 1)], shade(rgb("straw"), 0.85), 1.0)
    img = c.result()
    return apply_mult(img, noise_layer(w, h, rng, 12, 0.08))


def t_bill(rng):
    """Bec vu de dessus (projection) : orange, narines, reflet. Image haut = arrière du bec."""
    w = h = 128
    c = Canvas(w, h, rgb("orange"))
    for sx in (-1, 1):
        c.ellipse(64 + sx * 18, 52, 5, 7, fill=rgb("orange_dark"))
    img = c.result()
    img = radial_glow(img, 52, 70, 40, 0.18)
    return img


def t_sauveteur():
    w, h = 256, 64
    c = Canvas(w, h, rgb("red"))
    c.rect(0, 0, w, 5, fill=rgb("white"))
    c.rect(0, h - 5, w, h, fill=rgb("white"))
    c.text(w / 2, h / 2 + 1, "SAUVETEUR", 25, rgb("white"))
    for x in (17, w - 17):
        c.circle(x, h / 2, 9, outline=rgb("white"), width=4.5)
    return c.result()


def t_captain_band():
    w, h = 256, 64
    c = Canvas(w, h, rgb("navy"))
    for y in (10, 54):
        c.rect(0, y - 3, w, y + 3, fill=rgb("gold"))
    for k in range(20):
        x = k * 14
        c.line([(x, 20), (x + 7, 32), (x, 44)], rgb("gold_dark"), 2.5)
    return c.result()


def t_wing(rng):
    """Aile (projection latérale) : jaune, trois soudures de plumes en arc, reflet."""
    w, h = 256, 128
    c = Canvas(w, h, rgb("yellow"))
    for k in range(3):  # soudures de plumes : arcs réguliers, doux
        x = 120 - k * 34
        pts = [(x + 34 * math.sin(t / 12 * math.pi), 18 + t * 7.6) for t in range(13)]
        c.line(pts, mix(rgb("yellow"), rgb("yellow_dark"), 0.6), 4.0)
        c.line([(p[0] + 3.2, p[1]) for p in pts], rgb("yellow_light"), 1.6)
    img = c.result()
    img = radial_glow(img, 160, 44, 70, 0.14)
    return vgrad(img, 0.86, 1.02)


def t_ring_top(rng):
    """Dessus de bouée : 8 segments alternés jaune / jaune clair, soudures blanches radiales."""
    w = h = 256
    c = Canvas(w, h, rgb("yellow"))
    cx, cy = w / 2, h / 2
    for k in range(8):
        a0 = 2 * math.pi * k / 8 + math.pi / 8
        a1 = a0 + 2 * math.pi / 8
        col = rgb("yellow") if k % 2 == 0 else rgb("yellow_light")
        pts = [(cx, cy)] + [(cx + 400 * math.cos(a0 + (a1 - a0) * i / 8), cy + 400 * math.sin(a0 + (a1 - a0) * i / 8))
                            for i in range(9)]
        c.poly(pts, fill=col)
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        c.line([(cx + 60 * math.cos(a), cy + 60 * math.sin(a)), (cx + 190 * math.cos(a), cy + 190 * math.sin(a))],
               rgb("white"), 2.4)
    c.rect(4, 4, w - 4, h - 4, outline=rgb("yellow_dark"), width=4, radius=24)
    img = c.result()
    img = radial_glow(img, 90, 80, 120, 0.08)
    return apply_mult(img, noise_layer(w, h, rng, 50, 0.015))


def t_lei(rng):
    w, h = 256, 64
    c = Canvas(w, h, rgb("leaf"))
    cols = [rgb("pink"), rgb("coral"), rgb("yellow"), rgb("white"), rgb("pink_dark")]
    for k in range(18):
        x = k * 14.2 + 4
        for y in (16, 48):
            flower(c, x + (7 if y > 30 else 0), y, 15, cols[(k + (y > 30)) % 5], rgb("yellow"), rot=k * 0.7)
    return c.result()


def t_polka():
    w, h = 128, 64
    c = Canvas(w, h, rgb("red"))
    for i in range(9):
        for j in range(5):
            c.circle(i * 16 + (8 if j % 2 else 0), j * 16 + 4, 4.2, fill=rgb("white"))
    return c.result()


def t_valve():
    w = h = 64
    c = Canvas(w, h, rgb("white"))
    c.circle(32, 32, 30, fill=rgb("white"))
    c.circle(32, 32, 24, outline=rgb("steel"), width=3)
    c.circle(32, 32, 12, fill=rgb("pool"))
    c.circle(29, 29, 4, fill=rgb("white"))
    return c.result()


def t_bubble():
    w = h = 64
    img = Image.new("RGB", (w, h), rgb("glass"))
    a = np.asarray(img, dtype=np.float32).copy()
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ang = np.arctan2(yy - 32, xx - 32)
    hue = np.stack([0.5 + 0.5 * np.sin(ang * 2 + k * 2.1) for k in range(3)], -1)
    a = a * 0.75 + hue * 255 * 0.25
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.ellipse([12, 10, 26, 22], fill=rgb("white"))
    return img


def t_lens():
    w = h = 128
    img = Image.new("RGB", (w, h), rgb("lens"))
    img = vgrad(img, 0.7, 1.6, top_frac=1.0)
    c = Canvas(w, h, (0, 0, 0))
    c.img = img.resize((w * SS, h * SS))
    c.d = ImageDraw.Draw(c.img)
    c.poly([(20, 0), (44, 0), (4, 60), (0, 60), (0, 30)], fill=mix(rgb("lens"), rgb("white"), 0.55))
    c.poly([(54, 0), (64, 0), (14, 80), (6, 80)], fill=mix(rgb("lens"), rgb("white"), 0.4))
    return c.result()


def palette_tile():
    img = Image.new("RGB", (256, 256), (255, 0, 255))
    for name in PALETTE_ORDER:
        x0, y0, x1, y1 = cell_rect(name)
        cell = Image.new("RGB", (CELL_W, CELL_H), rgb(name))
        cell = vgrad(cell, 0.8, 1.03, top_frac=0.85)
        img.paste(cell, (x0, y0 - PAL_Y0))
    return img


def build_atlas():
    rng = np.random.default_rng(SEED)
    atlas = Image.new("RGB", (SIZE, SIZE), rgb("cream"))
    rough = Image.new("RGB", (SIZE, SIZE), (0, 128, 0))
    tiles = {
        "deck": t_deck(rng), "net": t_net(rng), "hawaii": hawaii_print(256, 256, rng, 2.2),
        "island_top": t_island_top(rng), "s_vinyl": t_s_vinyl(rng), "lilo_top": t_lilo_top(rng),
        "mariniere": t_stripes(256, 128, (rgb("navy"), rgb("white")), 9),
        "swim_stripes": t_stripes(256, 128, (rgb("red"), rgb("white")), 7, piping=rgb("navy")),
        "face": t_face(rng), "eye": t_eye(), "skull": t_skull(), "anchor": t_anchor(), "camera": t_camera(),
        "flower_cap": t_flower_cap(rng), "cape": t_cape(rng), "straw": t_straw(rng), "bill": t_bill(rng),
        "sauveteur": t_sauveteur(), "captain_band": t_captain_band(), "wing": t_wing(rng),
        "lei": t_lei(rng), "polka": t_polka(), "valve": t_valve(), "bubble": t_bubble(),
        "ring_top": t_ring_top(rng), "lilo_hawaii": hawaii_print(512, 256, rng, 1.6), "lens": t_lens(),
    }
    for name, im in tiles.items():
        x0, y0, x1, y1 = TILES[name]
        atlas.paste(im.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    atlas.paste(palette_tile(), (0, PAL_Y0))
    rd = ImageDraw.Draw(rough)
    for name, (x0, y0, x1, y1) in TILES.items():
        rd.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(0, int(255 * ROUGH.get(name, 0.4)), 0))
    for name in PALETTE_ORDER:
        x0, y0, x1, y1 = cell_rect(name)
        rd.rectangle([x0, y0, x1 - 1, y1 - 1],
                     fill=(0, int(255 * PAL_ROUGH.get(name, 0.35)), int(255 * PAL_METAL.get(name, 0.0))))
    return atlas, rough


def save_atlas(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    atlas, rough = build_atlas()
    p0 = os.path.join(out_dir, "duck_atlas_1024.png")
    p1 = os.path.join(out_dir, "duck_atlas_rough_1024.png")
    atlas.save(p0, optimize=True)
    rough.save(p1, optimize=True)
    return p0, p1


if __name__ == "__main__":
    print(save_atlas(sys.argv[1] if len(sys.argv) > 1 else "."))
