"""Atlas de texture partagé de la famille Réception (1 024 px, peint procéduralement).

Aucune image externe : tout est dessiné ici (PIL, suréchantillonnage x4, graine fixe).
Le module est importé par build_props_reception.py (UV) et peut être lancé seul :
    .venv/bin/python -I assets/source/blender/reception_atlas.py <dossier_sortie>

Disposition (pixels, origine en haut à gauche, tuiles de 256) :
  ligne 0 : dessus carton | dessus caisse mousse | dessus colis oreiller | dessus colis accordéon
  ligne 1 : plateau chariot | plateau palette | plateau bobine | coque valise
  ligne 2 : matières latérales 256x128 (carton, mousse, coque, palette, ruban, tissu, plis, corail)
  ligne 3 : palette dégradée (32 cellules) | étiquettes / balisage | détails machine | réserve

Couleurs : tokens de docs/02_ASSETS_ET_CLAUDE_DESIGN.md et teintes de la planche
assets/source/design/canvas/project/Room_Reception.dc.html.
Le second fichier (rough) suit la convention glTF metallicRoughness : G = rugosité, B = métal.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
TILE = 256
SS = 4  # suréchantillonnage du dessin vectoriel
SEED = 20261102

# --- couleurs (sRGB hex) -------------------------------------------------------
HEX = {
    # tokens projet
    "navy": "#203055", "cyan": "#16D9FF", "yellow": "#FFE14D", "pink": "#FF4CB8", "mint": "#39E68B",
    "coral": "#FF684B", "cream": "#FFF5DF", "violet": "#8855FF", "ice": "#DFF7FF",
    # teintes planche Réception
    "kraft": "#F3C969", "kraft_dark": "#C99A3E", "foam": "#FF9B47", "foam_dark": "#D9772E",
    "shell": "#FF8A3D", "shell_rib": "#C9631E", "turq": "#2ACBC7", "turq_dark": "#1C9E9A",
    "pillow": "#FFF1DC", "pink_light": "#FFB3DE", "machine": "#FF8C7A",
    # dérivées (ombres/accents)
    "machine_dark": "#D9655A", "pink_dark": "#D13A96", "cyan_dark": "#0FA3C2", "navy_light": "#3A5288",
    "rubber": "#262C3D", "steel": "#A9B6CC", "white": "#FBFBF6", "yellow_dark": "#E3B92B",
    "turq_light": "#5FE0DC", "cream_dark": "#E9D9B8", "mint_dark": "#22B56A", "glass_tint": "#BDEFFF",
}


def rgb(name_or_hex):
    h = HEX.get(name_or_hex, name_or_hex).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(c, f):
    return tuple(int(max(0, min(255, round(v * f)))) for v in c)


def mix(a, b, t):
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))


# --- disposition ---------------------------------------------------------------
TILES = {
    "carton_top": (0, 0, 256, 256), "foam_top": (256, 0, 512, 256),
    "pillow_top": (512, 0, 768, 256), "accordion_top": (768, 0, 1024, 256),
    "cart_deck": (0, 256, 256, 512), "pallet_top": (256, 256, 512, 512),
    "reel_top": (512, 256, 768, 512), "suitcase_top": (768, 256, 1024, 512),
    "s_cardboard": (0, 512, 256, 640), "s_foam": (0, 640, 256, 768),
    "s_shell": (256, 512, 512, 640), "s_pallet": (256, 640, 512, 768),
    "s_ribbon": (512, 512, 768, 640), "s_fabric": (512, 640, 768, 768),
    "s_pleat": (768, 512, 1024, 640), "s_coral": (768, 640, 1024, 768),
    # ligne 3
    "label_carton": (256, 768, 512, 896), "hazard": (256, 896, 512, 960), "label_small": (256, 960, 384, 1024),
    "arrow_strip": (384, 960, 512, 1024),
    "machine_panel": (512, 768, 768, 896), "stamp_face": (512, 896, 640, 1024), "eye": (640, 896, 768, 1024),
    "machine_badge": (768, 768, 896, 896), "chevrons": (896, 768, 1024, 896), "vents": (768, 896, 1024, 1024),
}

PALETTE_ORDER = [
    "navy", "cyan", "yellow", "pink", "mint", "coral", "cream", "ice",
    "kraft", "kraft_dark", "foam", "foam_dark", "shell", "shell_rib", "turq", "turq_dark",
    "pillow", "pink_light", "machine", "machine_dark", "pink_dark", "cyan_dark", "navy_light", "rubber",
    "steel", "white", "yellow_dark", "turq_light", "cream_dark", "mint_dark", "glass_tint", "violet",
]
CELL_W, CELL_H = 32, 64  # 8 x 4 cellules dans la tuile (0, 768)-(256, 1024)

# rugosité / métal par région (convention glTF : G = rugosité, B = métal)
ROUGH = {
    "carton_top": 0.86, "s_cardboard": 0.88, "foam_top": 0.95, "s_foam": 0.95, "pillow_top": 0.95,
    "s_fabric": 0.96, "accordion_top": 0.72, "s_pleat": 0.8, "cart_deck": 0.42, "pallet_top": 0.55,
    "s_pallet": 0.52, "reel_top": 0.4, "s_ribbon": 0.55, "suitcase_top": 0.32, "s_shell": 0.32,
    "s_coral": 0.42, "label_carton": 0.8, "hazard": 0.5, "label_small": 0.8, "arrow_strip": 0.5,
    "machine_panel": 0.45, "stamp_face": 0.85, "eye": 0.3, "machine_badge": 0.4, "chevrons": 0.45,
    "vents": 0.5,
}
PAL_ROUGH = {"navy": 0.4, "rubber": 0.85, "steel": 0.3, "cyan": 0.35, "cyan_dark": 0.35, "yellow": 0.4,
             "kraft": 0.88, "kraft_dark": 0.88, "foam": 0.95, "foam_dark": 0.95, "pillow": 0.95,
             "cream_dark": 0.9, "white": 0.7, "glass_tint": 0.1}
PAL_METAL = {"steel": 0.6}


def cell_rect(name):
    i = PALETTE_ORDER.index(name)
    col, row = i % 8, i // 8
    x0 = col * CELL_W
    y0 = 768 + row * CELL_H
    return (x0, y0, x0 + CELL_W, y0 + CELL_H)


def px_to_uv(rect, margin_px=1.5):
    x0, y0, x1, y1 = rect
    return ((x0 + margin_px) / SIZE, 1 - (y1 - margin_px) / SIZE, (x1 - margin_px) / SIZE, 1 - (y0 + margin_px) / SIZE)


def tile_uv(name, margin_px=1.5):
    return px_to_uv(TILES[name], margin_px)


def cell_uv(name):
    return px_to_uv(cell_rect(name), 3.0)


# --- outils de dessin ----------------------------------------------------------
class Canvas:
    """Surface de dessin en coordonnées "monde" (studs) d'un rectangle projeté.

    Projection identique au mappeur UV `top` : image droite = monde -X, image haut = monde -Y
    (le dessin se lit à l'endroit pour un joueur placé à l'avant, +Y Blender = -Z Roblox).
    Pour les tuiles latérales on passe `world=False` et on dessine en pixels de tuile.
    """

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

    def ellipse(self, x, y, rx, ry, outline, width):
        cx, cy = self.p(x, y)
        a, b = self.s(rx), self.s(ry)
        self.d.ellipse([cx - a, cy - b, cx + a, cy + b], outline=outline, width=max(1, int(self.s(width))))

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=0.0, radius=0.0):
        a, b = self.p(x0, y0), self.p(x1, y1)
        box = [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]
        self.d.rounded_rectangle(box, radius=self.s(radius), fill=fill, outline=outline,
                                 width=max(1, int(self.s(width))) if outline else 0)

    def poly(self, pts, fill=None, outline=None, width=0.0):
        P = [self.p(*q) for q in pts]
        self.d.polygon(P, fill=fill)
        if outline:
            self.d.line(P + [P[0]], fill=outline, width=max(1, int(self.s(width))), joint="curve")

    def line(self, pts, fill, width):
        P = [self.p(*q) for q in pts]
        self.d.line(P, fill=fill, width=max(1, int(self.s(width))), joint="curve")
        r = self.s(width) / 2
        for q in (P[0], P[-1]):
            self.d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=fill)

    def dashed(self, a, b, fill, width, dash, gap):
        L = math.dist(a, b)
        n = int(L / (dash + gap)) + 1
        for i in range(n):
            t0 = i * (dash + gap) / L
            t1 = min(1.0, (i * (dash + gap) + dash) / L)
            if t0 >= 1:
                break
            p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
            self.line([p0, p1], fill, width)

    def arc_seg(self, x, y, r0, r1, a0, a1, fill, n=16):
        pts = [(x + r1 * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                y + r1 * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        pts += [(x + r0 * math.cos(math.radians(a1 - (a1 - a0) * i / n)),
                 y + r0 * math.sin(math.radians(a1 - (a1 - a0) * i / n))) for i in range(n + 1)]
        self.poly(pts, fill=fill)

    def result(self, w, h):
        return self.img.resize((w, h), Image.LANCZOS)


def noise_layer(w, h, rng, scale, amp, aniso=(1.0, 1.0)):
    """Bruit basse fréquence multiplicatif (valeurs autour de 1)."""
    gw, gh = max(2, int(w / scale * aniso[0])), max(2, int(h / scale * aniso[1]))
    g = rng.normal(0, 1, (gh, gw)).astype(np.float32)
    im = Image.fromarray(((g - g.min()) / (np.ptp(g) + 1e-6) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    a = np.asarray(im, dtype=np.float32) / 255.0
    return 1.0 + (a - 0.5) * 2 * amp


def apply_mult(img, m):
    a = np.asarray(img, dtype=np.float32) * m[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def speckle(img, rng, density, amp, size=1):
    a = np.asarray(img, dtype=np.float32).copy()
    h, w = a.shape[:2]
    n = int(w * h * density)
    ys, xs = rng.integers(0, h - size, n), rng.integers(0, w - size, n)
    f = rng.uniform(1 - amp, 1 + amp * 0.5, n).astype(np.float32)
    for dy in range(size):
        for dx in range(size):
            a[ys + dy, xs + dx] *= f[:, None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def vgrad(img, bottom=0.8, top=1.0, top_frac=0.75):
    """Assombrissement vers le bas (v = hauteur) : occlusion douce peinte."""
    w, h = img.size
    t = np.linspace(1, 0, h, dtype=np.float32)  # rangée 0 = haut
    t = np.clip(t / top_frac, 0, 1)
    f = bottom + (top - bottom) * (t ** 0.8)
    return apply_mult(img, np.repeat(f[:, None], w, axis=1))


def edge_dark(img, band_px, amount):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy])
    f = 1 - amount * np.clip(1 - d / band_px, 0, 1) ** 1.5
    return apply_mult(img, f)


# --- pictogrammes génériques (ISO 780 génériques, sans marque) ------------------
def icon_up_arrows(c, x, y, s, col):
    for dx in (-0.28 * s, 0.28 * s):
        c.line([(x + dx, y + 0.45 * s), (x + dx, y - 0.35 * s)], col, 0.09 * s)
        c.poly([(x + dx - 0.2 * s, y - 0.2 * s), (x + dx + 0.2 * s, y - 0.2 * s), (x + dx, y - 0.5 * s)], fill=col)
    c.line([(x - 0.55 * s, y + 0.55 * s), (x + 0.55 * s, y + 0.55 * s)], col, 0.09 * s)


def icon_umbrella(c, x, y, s, col):
    pts = [(x + 0.5 * s * math.cos(math.radians(a)), y - 0.15 * s - 0.45 * s * math.sin(math.radians(a)))
           for a in range(0, 181, 15)]
    c.poly(pts, fill=col)
    c.line([(x, y - 0.15 * s), (x, y + 0.4 * s), (x - 0.15 * s, y + 0.5 * s)], col, 0.08 * s)
    for k in (-1, 0, 1):
        c.line([(x + k * 0.35 * s, y - 0.75 * s), (x + k * 0.35 * s - 0.05 * s, y - 0.62 * s)], col, 0.05 * s)


def icon_glass(c, x, y, s, col, cracked=True):
    c.poly([(x - 0.32 * s, y - 0.5 * s), (x + 0.32 * s, y - 0.5 * s), (x + 0.22 * s, y - 0.05 * s),
            (x - 0.22 * s, y - 0.05 * s)], fill=col)
    c.line([(x, y - 0.05 * s), (x, y + 0.4 * s)], col, 0.09 * s)
    c.line([(x - 0.25 * s, y + 0.45 * s), (x + 0.25 * s, y + 0.45 * s)], col, 0.09 * s)
    if cracked:
        c.line([(x - 0.05 * s, y - 0.5 * s), (x + 0.06 * s, y - 0.33 * s), (x - 0.04 * s, y - 0.22 * s)],
               rgb("white"), 0.05 * s)


def icon_spring(c, x, y, s, col):
    """Ressort hélicoïdal (boucles empilées entre deux plaques) + chevron de rebond ("haut" = -y)."""
    c.line([(x - 0.4 * s, y + 0.62 * s), (x + 0.4 * s, y + 0.62 * s)], col, 0.1 * s)
    c.line([(x - 0.3 * s, y - 0.18 * s), (x + 0.3 * s, y - 0.18 * s)], col, 0.1 * s)
    for i in range(4):
        yy = y + 0.5 * s - i * 0.19 * s
        c.ellipse(x, yy, 0.3 * s, 0.1 * s, col, 0.07 * s)
    c.line([(x - 0.26 * s, y - 0.42 * s), (x, y - 0.66 * s), (x + 0.26 * s, y - 0.42 * s)], col, 0.1 * s)


def icon_hourglass(c, x, y, s, col, sand):
    c.poly([(x - 0.38 * s, y - 0.55 * s), (x + 0.38 * s, y - 0.55 * s), (x + 0.06 * s, y),
            (x + 0.38 * s, y + 0.55 * s), (x - 0.38 * s, y + 0.55 * s), (x - 0.06 * s, y)], fill=col)
    c.poly([(x - 0.24 * s, y - 0.42 * s), (x + 0.24 * s, y - 0.42 * s), (x, y - 0.12 * s)], fill=sand)
    c.poly([(x - 0.25 * s, y + 0.45 * s), (x + 0.25 * s, y + 0.45 * s), (x, y + 0.22 * s)], fill=sand)
    c.line([(x - 0.48 * s, y - 0.6 * s), (x + 0.48 * s, y - 0.6 * s)], col, 0.1 * s)
    c.line([(x - 0.48 * s, y + 0.6 * s), (x + 0.48 * s, y + 0.6 * s)], col, 0.1 * s)


def icon_double_arrow(c, x0, x1, y, s, col):
    c.line([(x0 + 0.4 * s, y), (x1 - 0.4 * s, y)], col, 0.28 * s)
    for xa, sg in ((x0, 1), (x1, -1)):
        c.poly([(xa, y), (xa + sg * 0.7 * s, y - 0.5 * s), (xa + sg * 0.7 * s, y + 0.5 * s)], fill=col)


def barcode(c, x0, y0, w, h, rng, col):
    x = x0
    while x < x0 + w:
        bw = rng.choice([0.03, 0.05, 0.08]) * h
        c.rect(x, y0, x + bw, y0 + h, fill=col)
        x += bw + rng.choice([0.03, 0.05]) * h


# --- tuiles --------------------------------------------------------------------
def t_carton_top(rng):
    c = Canvas(256, 205, rgb("kraft"), -5, 5, -4, 4)
    # rabats : ligne de jonction centrale (sous le ruban) + bords de rabat
    c.rect(-5, -4, 5, -3.86, fill=shade(rgb("kraft"), 0.9))
    c.rect(-5, 3.86, 5, 4, fill=shade(rgb("kraft"), 0.9))
    c.line([(-5, 0), (5, 0)], shade(rgb("kraft"), 0.6), 0.06)
    c.rect(-5, -0.8, 5, 0.8, fill=rgb("cyan"))  # ruban (couvert par la géométrie)
    # pictogrammes imprimés sur le rabat arrière (lecture depuis l'avant)
    navy = rgb("navy")
    icon_up_arrows(c, 3.2, -2.35, 1.1, navy)
    icon_umbrella(c, 1.6, -2.35, 1.0, navy)
    icon_glass(c, 0.1, -2.35, 1.0, navy, cracked=False)
    # étiquette d'expédition sur le rabat avant
    c.rect(-4.3, 1.4, -1.2, 3.3, fill=rgb("white"), radius=0.12)
    c.rect(-4.3, 2.85, -1.2, 3.3, fill=rgb("coral"), radius=0.12)
    c.rect(-4.3, 2.85, -1.2, 3.0, fill=rgb("coral"))
    for k in range(3):
        c.rect(-4.0, 2.45 - k * 0.32, -2.0 - 0.4 * k, 2.6 - k * 0.32, fill=shade(rgb("navy"), 1.6))
    barcode(c, -4.0, 1.55, 2.4, 0.38, rng, navy)
    # gribouillis de marqueur (adresse manuscrite, illisible)
    pts = [(1.2 + 0.25 * i, 2.2 + 0.18 * math.sin(i * 1.7) + (0.12 if i % 3 == 0 else 0)) for i in range(13)]
    c.line(pts, rgb("navy_light"), 0.08)
    pts = [(1.2 + 0.25 * i, 1.6 + 0.16 * math.sin(i * 2.3 + 1)) for i in range(10)]
    c.line(pts, rgb("navy_light"), 0.08)
    img = c.result(256, 256)
    img = apply_mult(img, noise_layer(256, 256, rng, 24, 0.05, (1.0, 2.5)))
    img = speckle(img, rng, 0.02, 0.12)
    return edge_dark(img, 10, 0.18)


def t_foam_top(rng):
    c = Canvas(256, 256, rgb("foam"), -4, 4, -4, 4)
    # rebord + plateau en mousse alvéolée (boîte à oeufs douce)
    c.rect(-3.35, -3.35, 3.35, 3.35, fill=shade(rgb("foam"), 0.93), radius=0.5)
    for i in range(7):
        for j in range(7):
            x, y = -3.0 + i * 1.0, -3.0 + j * 1.0
            c.circle(x, y, 0.36, fill=shade(rgb("foam"), 1.06))
            c.circle(x + 0.5, y + 0.5, 0.2, fill=shade(rgb("foam"), 0.86)) if (i < 6 and j < 6) else None
    c.rect(-3.35, -3.35, 3.35, 3.35, outline=shade(rgb("foam"), 0.78), width=0.08, radius=0.5)
    img = c.result(256, 256)
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    img = speckle(img, rng, 0.08, 0.12)
    return edge_dark(img, 8, 0.15)


def t_pillow_top(rng):
    base = rgb("pillow")
    c = Canvas(256, 256, base, -4, 4, -4, 4)
    # matelassage en losanges, couture jaune pointillée
    yel = rgb("yellow_dark")
    for k in range(-3, 4):
        a = (-4.0, k * 2.6 - 4.0)
        b = (4.0, k * 2.6 + 4.0)
        c.dashed(a, b, yel, 0.07, 0.22, 0.14)
        c.dashed((4.0, k * 2.6 - 4.0), (-4.0, k * 2.6 + 4.0), yel, 0.07, 0.22, 0.14)
    for (x, y) in ((2.6, 2.6), (-2.6, 2.6), (2.6, -2.6), (-2.6, -2.6)):
        c.circle(x, y, 0.75, fill=shade(base, 0.9))
        c.circle(x, y, 0.5, fill=shade(base, 0.82))
    # bande kraft (dessus du bandeau modélisé) + badge ressort
    c.rect(-1.15, -4, 1.15, 4, fill=rgb("kraft"))
    c.rect(-1.15, -4, -1.0, 4, fill=rgb("kraft_dark"))
    c.rect(1.0, -4, 1.15, 4, fill=rgb("kraft_dark"))
    for yy in (-3.2, 3.2):
        icon_up_arrows(c, 0, yy, 0.6, rgb("navy"))
    c.circle(0, 0, 1.08, fill=rgb("navy"))
    c.circle(0, 0, 0.95, fill=rgb("yellow"))
    icon_spring(c, 0, 0, 1.15, rgb("navy"))
    img = c.result(256, 256)
    img = apply_mult(img, weave(256, 256, 3, 0.05))
    img = apply_mult(img, noise_layer(256, 256, rng, 40, 0.03))
    return edge_dark(img, 8, 0.1)


def weave(w, h, period, amp):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = np.sin(xx * 2 * math.pi / period) * np.sin(yy * 2 * math.pi / period)
    return 1 + amp * v


def t_accordion_top(rng):
    c = Canvas(256, 256, rgb("pink_light"), -4, 4, -4, 4)
    pink, navy = rgb("pink"), rgb("navy")
    c.rect(-4, -4, 4, 4, outline=pink, width=0.42)
    # pictogrammes fragiles aux coins
    icon_glass(c, -3.0, -3.0, 0.9, pink)
    icon_glass(c, 3.0, 3.0, 0.9, pink)
    # jauge circulaire 12 segments + sablier
    c.circle(0, 0, 2.55, fill=navy)
    c.circle(0, 0, 2.38, fill=rgb("cream"))
    for i in range(12):
        a0 = 90 - i * 30 - 13
        a1 = 90 - i * 30 + 13
        lit = i < 9
        c.arc_seg(0, 0, 1.55, 2.2, a0, a1, pink if lit else shade(rgb("pink_light"), 1.05))
    c.circle(0, 0, 1.42, fill=navy)
    c.circle(0, 0, 1.28, fill=rgb("cream"))
    icon_hourglass(c, 0, 0, 1.55, navy, pink)
    # plis de pression (fragilité)
    c.line([(2.0, -3.6), (2.6, -3.0), (2.3, -2.6), (2.9, -2.0)], shade(rgb("pink_light"), 0.85), 0.07)
    c.line([(-3.6, 2.2), (-3.0, 2.6), (-2.6, 2.3), (-2.0, 2.9)], shade(rgb("pink_light"), 0.85), 0.07)
    img = c.result(256, 256)
    img = apply_mult(img, noise_layer(256, 256, rng, 30, 0.035))
    return edge_dark(img, 8, 0.12)


def t_cart_deck(rng):
    c = Canvas(256, 205, rgb("cyan"), -5, 5, -4, 4)
    # tôle larmée stylisée
    for i in range(-12, 13):
        for j in range(-9, 10):
            x, y = i * 0.42, j * 0.42
            ang = 35 if (i + j) % 2 == 0 else -35
            dx, dy = 0.13 * math.cos(math.radians(ang)), 0.13 * math.sin(math.radians(ang))
            c.line([(x - dx, y - dy), (x + dx, y + dy)], shade(rgb("cyan"), 0.86), 0.06)
    # bandes de balisage aux extrémités (axe de déplacement = largeur)
    for xs in (-1, 1):
        x0, x1 = (4.25, 5.0) if xs > 0 else (-5.0, -4.25)
        c.rect(x0, -4, x1, 4, fill=rgb("yellow"))
        for k in range(-8, 9):
            y = k * 0.6
            c.poly([(x0, y), (x0, y + 0.3), (x1, y + 0.3 + 0.75 * xs * 0 + 0.75), (x1, y + 0.75)], fill=rgb("navy"))
        c.rect(x0, -4, x1, 4, outline=rgb("navy"), width=0.06)
    # flèches de translation
    icon_double_arrow(c, -3.6, 3.6, 1.8, 1.0, rgb("navy"))
    icon_double_arrow(c, -3.6, 3.6, -1.8, 1.0, rgb("navy"))
    c.rect(-2.2, -0.55, 2.2, 0.55, fill=shade(rgb("cyan"), 0.9), radius=0.3)
    for k in range(-3, 4):
        c.circle(k * 0.6, 0, 0.13, fill=rgb("white"))
    for (x, y) in ((3.9, 3.6), (-3.9, 3.6), (3.9, -3.6), (-3.9, -3.6)):
        c.circle(x, y, 0.16, fill=rgb("steel"))
    img = c.result(256, 256)
    img = apply_mult(img, noise_layer(256, 256, rng, 30, 0.025))
    return edge_dark(img, 6, 0.2)


def t_pallet_top(rng):
    t = rgb("turq")
    c = Canvas(256, 213, t, -6, 6, -5, 5)
    # plateau fermé, picots antidérapants et rainures (non traversantes)
    c.rect(-5.6, -4.6, 5.6, 4.6, outline=shade(t, 0.88), width=0.12, radius=0.4)
    for i in range(-10, 11):
        for j in range(-8, 9):
            if abs(j) % 3 == 0:
                continue
            c.rect(i * 0.5 - 0.12, j * 0.5 - 0.12, i * 0.5 + 0.12, j * 0.5 + 0.12,
                   fill=shade(t, 1.08), radius=0.05)
    for y in (-3.0, 0.0, 3.0):
        for k in range(-5, 5):
            c.rect(k * 1.1 + 0.15, y - 0.13, k * 1.1 + 0.9, y + 0.13, fill=rgb("turq_dark"), radius=0.1)
    for (x, y) in ((5.2, 4.2), (-5.2, 4.2), (5.2, -4.2), (-5.2, -4.2)):
        c.circle(x, y, 0.3, fill=rgb("turq_dark"))
        c.circle(x, y, 0.18, fill=rgb("navy"))
    img = c.result(256, 256)
    img = apply_mult(img, noise_layer(256, 256, rng, 30, 0.025))
    return edge_dark(img, 6, 0.15)


def t_reel_top(rng):
    pk = rgb("pink")
    c = Canvas(256, 256, pk, -3.5, 3.5, -3.5, 3.5)
    c.rect(-3.5, -3.5, 3.5, 3.5, outline=shade(pk, 0.85), width=0.14, radius=0.4)
    c.circle(0, 0, 3.05, outline=shade(pk, 0.82), width=0.1)
    for i in range(6):
        a = math.radians(30 + 60 * i)
        c.circle(2.05 * math.cos(a), 2.05 * math.sin(a), 0.55, fill=shade(pk, 0.78))
        c.circle(2.05 * math.cos(a), 2.05 * math.sin(a), 0.42, fill=shade(pk, 0.7))
    c.circle(0, 0, 1.05, fill=rgb("cream"))
    c.circle(0, 0, 1.05, outline=shade(pk, 0.7), width=0.1)
    for i in range(3):
        a = math.radians(90 + 120 * i)
        c.circle(0.55 * math.cos(a), 0.55 * math.sin(a), 0.14, fill=rgb("navy"))
    # amorce de ruban citron (accent jaune, cosmétique trace_ruban_citron)
    c.arc_seg(0, 0, 2.75, 2.92, 200, 320, rgb("yellow"))
    img = c.result(256, 256)
    img = apply_mult(img, noise_layer(256, 256, rng, 40, 0.02))
    return edge_dark(img, 6, 0.15)


def t_suitcase_top(rng):
    o = rgb("shell")
    c = Canvas(256, 154, o, -5, 5, -3, 3)
    # autocollants de voyage génériques (sans marque) entre les nervures
    c.rect(-1.75, 0.1, 0.05, 1.5, fill=rgb("cream"), radius=0.25)
    c.poly([(-1.5, 0.75), (-0.4, 1.0), (-0.1, 0.8), (-0.4, 0.62), (-1.0, 0.65), (-1.3, 0.3), (-1.45, 0.35),
            (-1.25, 0.7)], fill=rgb("cyan_dark"))
    c.circle(0.95, -0.8, 0.78, fill=rgb("navy"))
    c.circle(0.95, -0.8, 0.66, fill=rgb("yellow"))
    star = []
    for i in range(10):
        r = 0.48 if i % 2 == 0 else 0.2
        a = math.radians(90 + 36 * i)
        star.append((0.95 + r * math.cos(a), -0.8 + r * math.sin(a)))
    c.poly(star, fill=rgb("coral"))
    c.rect(-1.4, -1.6, -0.3, -0.5, fill=rgb("mint"), radius=0.5)
    c.rect(-1.15, -1.35, -0.55, -0.75, fill=rgb("cream"), radius=0.3)
    img = c.result(256, 256)
    # reflet satiné diagonal
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    band = np.exp(-(((xx * 0.6 + yy) - 0.55 * (w + h) * 0.8) / 40.0) ** 2)
    img = apply_mult(img, 1 + 0.08 * band)
    img = apply_mult(img, noise_layer(256, 256, rng, 50, 0.015))
    return edge_dark(img, 6, 0.12)


def side_tile(rng, base, kind):
    w, h = 256, 128
    img = Image.new("RGB", (w, h), rgb(base))
    if kind == "cardboard":
        a = np.asarray(img, dtype=np.float32)
        xx = np.arange(w, dtype=np.float32)
        a = a * (1 + 0.025 * np.sin(xx * 2 * math.pi / 6.0))[None, :, None]
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        img = apply_mult(img, noise_layer(w, h, rng, 18, 0.05, (2.5, 1.0)))
        img = speckle(img, rng, 0.02, 0.12)
        d = ImageDraw.Draw(img)
        d.line([(0, 6), (w, 6)], fill=shade(rgb(base), 0.78), width=2)  # pli des rabats (haut)
        d.line([(0, h - 6), (w, h - 6)], fill=shade(rgb(base), 0.8), width=2)
    elif kind == "foam":
        img = apply_mult(img, noise_layer(w, h, rng, 20, 0.04))
        img = speckle(img, rng, 0.12, 0.16)
        img = speckle(img, rng, 0.01, 0.25, size=2)
    elif kind == "shell":
        img = apply_mult(img, noise_layer(w, h, rng, 60, 0.02))
        yy = np.arange(h, dtype=np.float32)[:, None]
        img = apply_mult(img, np.repeat(1 + 0.07 * np.exp(-((yy - h * 0.3) / 10) ** 2), w, axis=1))
    elif kind == "pallet":
        img = apply_mult(img, noise_layer(w, h, rng, 30, 0.03))
        d = ImageDraw.Draw(img)
        for y in (int(h * 0.12), int(h * 0.88)):
            d.line([(0, y), (w, y)], fill=shade(rgb(base), 0.85), width=2)
    elif kind == "ribbon":
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, w, 7], fill=shade(rgb("cream_dark"), 0.95))
        d.rectangle([0, h - 8, w, h], fill=shade(rgb("cream_dark"), 0.9))
        for y0, y1 in ((38, 50), (78, 90)):
            d.rectangle([0, y0, w, y1], fill=rgb("yellow"))
        yy = np.arange(h, dtype=np.float32)[:, None]
        img = apply_mult(img, np.repeat(1 + 0.03 * np.sin(yy * 2 * math.pi / 4.0), w, axis=1))
    elif kind == "fabric":
        img = apply_mult(img, weave(w, h, 3, 0.05))
        img = apply_mult(img, noise_layer(w, h, rng, 30, 0.03))
    elif kind == "pleat":
        img = apply_mult(img, noise_layer(w, h, rng, 16, 0.05, (3.0, 1.0)))
        img = speckle(img, rng, 0.01, 0.1)
    elif kind == "coral":
        img = apply_mult(img, noise_layer(w, h, rng, 60, 0.015))
    return vgrad(img, 0.8, 1.0)


def t_label_carton(rng):
    w, h = 256, 128
    c = Canvas(w, h, rgb("white"), world=False)
    c.rect(0, 0, w, 22, fill=rgb("cyan"))
    c.rect(0, 22, w, 26, fill=rgb("navy"))
    for k in range(4):
        c.rect(14, 38 + k * 13, 14 + 130 - 22 * k, 45 + k * 13, fill=rgb("navy_light"))
    xx = 150
    r = np.random.default_rng(5)
    while xx < 240:
        bw = int(r.choice([2, 3, 5]))
        c.rect(xx, 40, xx + bw, 100, fill=rgb("navy"))
        xx += bw + int(r.choice([2, 3]))
    icon_c = Canvas(1, 1, (0, 0, 0), world=False)  # noqa: F841 (gabarit)
    c.rect(14, 96, 60, 116, fill=rgb("coral"), radius=4)
    c.rect(66, 96, 112, 116, fill=rgb("mint"), radius=4)
    img = c.result(w, h)
    return edge_dark(img, 4, 0.2)


def t_hazard():
    w, h = 256, 64
    c = Canvas(w, h, rgb("yellow"), world=False)
    for k in range(-4, 20):
        x = k * 22
        c.poly([(x, h), (x + 11, h), (x + 11 + h * 0.6, 0), (x + h * 0.6, 0)], fill=rgb("navy"))
    return c.result(w, h)


def t_label_small():
    w, h = 128, 64
    c = Canvas(w, h, rgb("white"), world=False)
    c.rect(0, 0, 24, h, fill=rgb("pink"))
    for k in range(3):
        c.rect(32, 12 + k * 14, 110 - 15 * k, 19 + k * 14, fill=rgb("navy_light"))
    return edge_dark(c.result(w, h), 3, 0.2)


def t_arrow_strip():
    w, h = 128, 64
    c = Canvas(w, h, rgb("cyan"), world=False)
    for k in range(4):
        x = 8 + k * 30
        c.poly([(x, 14), (x + 14, 32), (x, 50), (x + 8, 50), (x + 22, 32), (x + 8, 14)], fill=rgb("navy"))
    return c.result(w, h)


def t_machine_panel(rng):
    w, h = 256, 128
    c = Canvas(w, h, rgb("machine"), world=False)
    c.rect(6, 6, w - 6, h - 6, outline=rgb("machine_dark"), width=3, radius=14)
    for k in range(6):
        c.rect(24, 22 + k * 15, 140, 30 + k * 15, fill=rgb("machine_dark"), radius=4)
    c.circle(196, 64, 34, fill=rgb("navy"))
    c.circle(196, 64, 28, fill=rgb("cream"))
    for i in range(9):
        a = math.radians(210 - i * 30)
        c.line([(196 + 18 * math.cos(a), 64 - 18 * math.sin(a)), (196 + 25 * math.cos(a), 64 - 25 * math.sin(a))],
               rgb("navy"), 2.5)
    c.line([(196, 64), (196 + 20 * math.cos(math.radians(40)), 64 - 20 * math.sin(math.radians(40)))],
           rgb("coral"), 3.5)
    c.circle(196, 64, 4, fill=rgb("navy"))
    for (x, y) in ((16, 16), (w - 16, 16), (16, h - 16), (w - 16, h - 16)):
        c.circle(x, y, 4, fill=rgb("machine_dark"))
    img = c.result(w, h)
    return vgrad(img, 0.88, 1.0)


def t_stamp_face():
    w, h = 128, 128
    c = Canvas(w, h, rgb("navy"), world=False)
    c.circle(64, 64, 52, outline=rgb("navy_light"), width=6)
    c.line([(38, 66), (56, 86), (92, 42)], rgb("navy_light"), 11)
    return c.result(w, h)


def t_eye():
    w, h = 128, 128
    c = Canvas(w, h, rgb("cream"), world=False)
    c.circle(64, 64, 63, fill=rgb("cream"))
    c.circle(64, 64, 34, fill=rgb("cyan_dark"))
    c.circle(64, 64, 28, fill=rgb("cyan"))
    c.circle(64, 64, 17, fill=rgb("navy"))
    c.circle(52, 50, 8, fill=rgb("white"))
    c.circle(76, 78, 3.5, fill=rgb("white"))
    for i in range(16):
        a = math.radians(i * 22.5)
        c.line([(64 + 20 * math.cos(a), 64 + 20 * math.sin(a)), (64 + 30 * math.cos(a), 64 + 30 * math.sin(a))],
               shade(rgb("cyan"), 0.8), 1.5)
    return c.result(w, h)


def t_machine_badge():
    w, h = 128, 128
    c = Canvas(w, h, rgb("navy"), world=False)
    c.circle(64, 64, 58, fill=rgb("yellow"))
    c.circle(64, 64, 50, fill=rgb("navy"))
    # tampon stylisé (pictogramme, sans texte)
    c.rect(48, 30, 80, 62, fill=rgb("yellow"), radius=10)
    c.rect(58, 60, 70, 76, fill=rgb("yellow"))
    c.rect(34, 76, 94, 92, fill=rgb("yellow"), radius=5)
    c.line([(36, 102), (92, 102)], rgb("cyan"), 4)
    return c.result(w, h)


def t_chevrons():
    w, h = 128, 128
    c = Canvas(w, h, rgb("yellow"), world=False)
    for k in range(-3, 8):
        y = k * 24
        c.poly([(0, y), (64, y + 30), (128, y), (128, y + 12), (64, y + 42), (0, y + 12)], fill=rgb("navy"))
    return c.result(w, h)


def t_vents():
    w, h = 256, 128
    c = Canvas(w, h, rgb("machine"), world=False)
    for k in range(7):
        c.rect(16 + k * 34, 18, 34 + k * 34, 110, fill=rgb("machine_dark"), radius=8)
        c.rect(19 + k * 34, 22, 31 + k * 34, 106, fill=rgb("navy"), radius=6)
    return vgrad(c.result(w, h), 0.9, 1.0)


def palette_tile():
    img = Image.new("RGB", (256, 256), (255, 0, 255))
    for name in PALETTE_ORDER:
        x0, y0, x1, y1 = cell_rect(name)
        cell = Image.new("RGB", (CELL_W, CELL_H), rgb(name))
        cell = vgrad(cell, 0.8, 1.02, top_frac=0.85)
        img.paste(cell, (x0, y0 - 768))
    return img


def build_atlas():
    rng = np.random.default_rng(SEED)
    atlas = Image.new("RGB", (SIZE, SIZE), rgb("ice"))
    rough = Image.new("RGB", (SIZE, SIZE), (0, 128, 0))
    paint = {
        "carton_top": t_carton_top, "foam_top": t_foam_top, "pillow_top": t_pillow_top,
        "accordion_top": t_accordion_top, "cart_deck": t_cart_deck, "pallet_top": t_pallet_top,
        "reel_top": t_reel_top, "suitcase_top": t_suitcase_top,
    }
    for name, fn in paint.items():
        x0, y0, x1, y1 = TILES[name]
        atlas.paste(fn(rng).resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    sides = {"s_cardboard": ("kraft", "cardboard"), "s_foam": ("foam", "foam"), "s_shell": ("shell", "shell"),
             "s_pallet": ("turq", "pallet"), "s_ribbon": ("cream", "ribbon"), "s_fabric": ("pillow", "fabric"),
             "s_pleat": ("pink_light", "pleat"), "s_coral": ("machine", "coral")}
    for name, (base, kind) in sides.items():
        x0, y0, _x1, _y1 = TILES[name]
        atlas.paste(side_tile(rng, base, kind), (x0, y0))
    extra = {"label_carton": t_label_carton(rng), "hazard": t_hazard(), "label_small": t_label_small(),
             "arrow_strip": t_arrow_strip(), "machine_panel": t_machine_panel(rng), "stamp_face": t_stamp_face(),
             "eye": t_eye(), "machine_badge": t_machine_badge(), "chevrons": t_chevrons(), "vents": t_vents()}
    for name, im in extra.items():
        x0, y0, x1, y1 = TILES[name]
        atlas.paste(im.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    atlas.paste(palette_tile(), (0, 768))
    # carte rugosité / métal
    rd = ImageDraw.Draw(rough)
    for name, (x0, y0, x1, y1) in TILES.items():
        rd.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(0, int(255 * ROUGH.get(name, 0.5)), 0))
    for name in PALETTE_ORDER:
        x0, y0, x1, y1 = cell_rect(name)
        rd.rectangle([x0, y0, x1 - 1, y1 - 1],
                     fill=(0, int(255 * PAL_ROUGH.get(name, 0.45)), int(255 * PAL_METAL.get(name, 0.0))))
    return atlas, rough


def save_atlas(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    atlas, rough = build_atlas()
    p0 = os.path.join(out_dir, "reception_atlas_1024.png")
    p1 = os.path.join(out_dir, "reception_atlas_rough_1024.png")
    atlas.save(p0, optimize=True)
    rough.save(p1, optimize=True)
    return p0, p1


if __name__ == "__main__":
    print(save_atlas(sys.argv[1] if len(sys.argv) > 1 else "."))
