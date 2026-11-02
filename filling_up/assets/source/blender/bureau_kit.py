"""Bibliothèque de modélisation paramétrique pour les props de la famille Bureau perdu.

Partagée par build_props_bureau.py (construction) et render_props_bureau.py (rendus).

Principes :
- 1 unité Blender = 1 stud (décision 0003) ; X largeur, Y profondeur, Z hauteur ;
  l'avant Roblox (-Z) correspond à +Y Blender. Pivot bottom_center = origine.
- chaque pièce est construite dans un bmesh temporaire (boîtes biseautées, cylindres,
  prismes à profil arrondi, lofts de rectangles arrondis, tubes balayés), puis
  peinte : chaque face reçoit des UV dans l'atlas partagé de la famille
  (pastille de couleur unie ou décalque projeté), et un seuil de lissage.
- le maillage final est assemblé par from_pydata (aucun booléen) : 1 matériau.
"""
from __future__ import annotations

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw, ImageFont

ATLAS_PX = 1024

# ---------------------------------------------------------------------------
# Palette : tokens docs/02 + palette config/rooms.json (bureau) + nuances dérivées
# (les nuances #D3C4F5, #1C9E9A, #5FDCD9, #FFD9B8 viennent de la planche Room_Office).
COLORS = {
    # docs/02_ASSETS_ET_CLAUDE_DESIGN.md
    "cream": "#FFF5DF", "navy": "#203055", "cyan": "#16D9FF", "yellow": "#FFE14D",
    "pink": "#FF4CB8", "mint": "#39E68B", "coral": "#FF684B", "violet": "#8855FF",
    # config/rooms.json families[bureau].palette
    "fond": "#EDF3F8", "lavender": "#B9A4EE", "turquoise": "#2ACBC7",
    # planche Room_Office.dc.html
    "lavender_light": "#D3C4F5", "teal_dark": "#1C9E9A", "teal_light": "#5FDCD9", "peach": "#FFD9B8",
    # nuances dérivées (ombrage peint, matières secondaires)
    "lavender_dark": "#9A84D8", "paper": "#FFFCF3", "paper_shade": "#EFE4CC", "yellow_dark": "#E9C53A",
    "pink_light": "#FF9CD6", "pink_dark": "#D63C9C", "navy_light": "#3B4E80", "metal": "#C8D2E2",
    "metal_dark": "#8793AB", "rubber": "#2B3352", "white": "#FFFFFF", "cyan_dark": "#0FA9CC",
    "mint_dark": "#22B56A", "coral_dark": "#D9503A", "cream_dark": "#F0DDB4", "grey_line": "#C9C2B0",
    "peach_dark": "#F2B98C", "turquoise_dark": "#22A9A6",
}


def rgb(name_or_hex):
    h = COLORS.get(name_or_hex, name_or_hex)
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def font(size):
    # police embarquée par Pillow (reproductible, pas de dépendance aux polices système)
    return ImageFont.load_default(size=size)


# ---------------------------------------------------------------------------
# Disposition du clavier (partagée par l'atlas et la géométrie)
KEY_U = 0.88          # pas d'une touche (studs)
KEY_GAP = 0.10        # joint entre touches
KB_ROWS = [
    # (y du centre de rangée en unités de rangée depuis l'arrière, [(label, largeur_u, fond, saut_u_avant)])
    [("Esc", 1, "coral", 0), ("F1", 1, "cream", .5), ("F2", 1, "cream", 0), ("F3", 1, "cream", 0), ("F4", 1, "cream", 0),
     ("F5", 1, "lavender_light", .5), ("F6", 1, "lavender_light", 0), ("F7", 1, "lavender_light", 0), ("F8", 1, "lavender_light", 0),
     ("F9", 1, "cream", .5), ("F10", 1, "cream", 0), ("F11", 1, "cream", 0), ("F12", 1, "cream", 0)],
    [("`", 1, "cream", 0)] + [(c, 1, "cream", 0) for c in "1234567890"] + [("-", 1, "cream", 0), ("=", 1, "cream", 0), ("Back", 2, "lavender_light", 0)],
    [("Tab", 1.5, "lavender_light", 0)] + [(c, 1, "cream", 0) for c in "QWERTYUIOP"] + [("[", 1, "cream", 0), ("]", 1, "cream", 0), ("\\", 1.5, "cream", 0)],
    [("Caps", 1.75, "lavender_light", 0)] + [(c, 1, "cream", 0) for c in "ASDFGHJKL"] + [(";", 1, "cream", 0), ("'", 1, "cream", 0), ("Enter", 2.25, "turquoise", 0)],
    [("Shift", 2.25, "lavender_light", 0)] + [(c, 1, "cream", 0) for c in "ZXCVBNM"] + [(",", 1, "cream", 0), (".", 1, "cream", 0), ("/", 1, "cream", 0), ("Shift", 2.75, "lavender_light", 0)],
    [("Ctrl", 1.5, "lavender_light", 0), ("Opt", 1, "lavender_light", 0), ("Alt", 1.5, "lavender_light", 0), ("", 7, "cream", 0),
     ("Alt", 1.5, "lavender_light", 0), ("Fn", 1, "yellow", 0), ("Ctrl", 1.5, "lavender_light", 0)],
]
KB_W, KB_D, KB_H = 14.0, 7.0, 2.0
KB_FRONT_BEZEL = 0.50
KB_ROW_PITCH = KEY_U


def keyboard_layout():
    """Liste de touches : dict(label, color, x0, x1, y0, y1) en studs (Blender).

    Lecture : un joueur placé devant (+Y) voit Esc à sa gauche, c'est-à-dire en +X
    (droite écran = -X vu depuis l'avant, cf. décision 0003)."""
    keys = []
    total_u = 15.0
    x_left = total_u * KEY_U / 2.0            # bord gauche (vu de face) = +X
    y_front = KB_D / 2 - KB_FRONT_BEZEL
    nrows = len(KB_ROWS)
    for r, row in enumerate(KB_ROWS):
        # rangée 0 = arrière (-Y), dernière = avant (+Y)
        yr1 = y_front - (nrows - 1 - r) * KB_ROW_PITCH
        yr0 = yr1 - KB_ROW_PITCH
        u = 0.0
        for (label, wu, col, skip) in row:
            u += skip
            xa = x_left - u * KEY_U
            xb = x_left - (u + wu) * KEY_U
            keys.append({"label": label, "color": col, "wu": wu,
                         "x0": xb + KEY_GAP / 2, "x1": xa - KEY_GAP / 2,
                         "y0": yr0 + KEY_GAP / 2, "y1": yr1 - KEY_GAP / 2, "row": r})
            u += wu
    return keys


# ---------------------------------------------------------------------------
class Atlas:
    """Atlas 1 024 px partagé par la famille : pastilles unies + décalques imprimés."""

    def __init__(self):
        self.img = Image.new("RGB", (ATLAS_PX, ATLAS_PX), rgb("fond"))
        self.d = ImageDraw.Draw(self.img)
        self.swatch = {}
        self.decal = {}
        for i, name in enumerate(COLORS):
            c, r = i % 16, i // 16
            rect = (c * 64, r * 64, c * 64 + 64, r * 64 + 64)
            self.d.rectangle([rect[0], rect[1], rect[2] - 1, rect[3] - 1], fill=rgb(name))
            self.swatch[name] = rect
        self.paint_decals()

    # -- UV -----------------------------------------------------------------
    def swatch_uv(self, name, s, t):
        x0, y0, x1, y1 = self.swatch[name]
        m = 18
        px = x0 + m + s * (x1 - x0 - 2 * m)
        py = y1 - m - t * (y1 - y0 - 2 * m)
        return (px / ATLAS_PX, 1.0 - py / ATLAS_PX)

    def rect_uv(self, rect, s, t, inset=1.5):
        x0, y0, x1, y1 = rect
        px = x0 + inset + s * (x1 - x0 - 2 * inset)
        py = y1 - inset - t * (y1 - y0 - 2 * inset)
        return (px / ATLAS_PX, 1.0 - py / ATLAS_PX)

    def reg(self, name, rect):
        self.decal[name] = rect
        return rect

    # -- dessin ---------------------------------------------------------------
    def text(self, rect, s, size, fill="navy", bold=True, dy=0, anchor="mm", xy=None):
        f = font(size)
        if xy is None:
            xy = ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2 + dy)
        self.d.text(xy, s, font=f, fill=rgb(fill), anchor=anchor,
                    stroke_width=1 if bold else 0, stroke_fill=rgb(fill))

    def rrect(self, box, r, fill, outline=None, width=0):
        self.d.rounded_rectangle(box, radius=r, fill=rgb(fill) if fill else None,
                                 outline=rgb(outline) if outline else None, width=width)

    def hourglass(self, cx, cy, s, fill="navy", sand="yellow"):
        d = self.d
        d.polygon([(cx - s, cy - s * 1.25), (cx + s, cy - s * 1.25), (cx, cy)], fill=rgb(fill))
        d.polygon([(cx - s, cy + s * 1.25), (cx + s, cy + s * 1.25), (cx, cy)], fill=rgb(fill))
        d.polygon([(cx - s * .45, cy + s * 1.05), (cx + s * .45, cy + s * 1.05), (cx, cy + s * .35)], fill=rgb(sand))
        d.rectangle([cx - s * 1.2, cy - s * 1.45, cx + s * 1.2, cy - s * 1.25], fill=rgb(fill))
        d.rectangle([cx - s * 1.2, cy + s * 1.25, cx + s * 1.2, cy + s * 1.45], fill=rgb(fill))

    def paint_decals(self):
        d = self.d
        # ---------------- ramette ----------------
        r = self.reg("ream_label", (0, 256, 256, 512))
        d.rectangle(r, fill=rgb("paper"))
        for yy in (264, 276, 492, 504):
            d.rectangle([0, yy - 4, 256, yy + 4], fill=rgb("cyan"))
        self.rrect((34, 300, 222, 468), 18, "turquoise", "navy", 5)
        self.rrect((54, 318, 128, 396), 8, "paper", "navy", 3)            # icône feuille
        for k in range(4):
            d.rectangle([64, 334 + k * 14, 116 - (k % 2) * 14, 339 + k * 14], fill=rgb("grey_line"))
        self.text(r, "A4", 58, "white", xy=(174, 356))
        self.text(r, "500 FEUILLES", 20, "navy", xy=(128, 420))
        self.text(r, "80 g · OVERFLOW", 14, "navy", bold=False, xy=(128, 446))

        r = self.reg("ream_side", (256, 256, 512, 384))
        d.rectangle(r, fill=rgb("paper"))
        for yy in (276, 364):
            d.rectangle([256, yy - 7, 512, yy + 7], fill=rgb("cyan"))
        d.rectangle([256, 296, 512, 300], fill=rgb("cyan_dark"))
        d.rectangle([256, 340, 512, 344], fill=rgb("cyan_dark"))
        self.text(r, "OVERFLOW  ·  A4  ·  500", 20, "navy", xy=(384, 320))

        r = self.reg("sheet_edges", (256, 384, 512, 512))
        for k, yy in enumerate(range(384, 512, 3)):
            col = "cream" if k % 3 else "paper_shade"
            d.rectangle([256, yy, 512, yy + 2], fill=rgb(col))
            if k % 7 == 3:
                d.rectangle([256, yy + 2, 512, yy + 2], fill=rgb("grey_line"))

        # ---------------- classeurs (4 dos de 256 x 32) ----------------
        labels = [("A - F", "pink"), ("G - M", "lavender"), ("N - S", "pink"), ("T - Z", "lavender")]
        for k, (lab, col) in enumerate(labels):
            r = self.reg(f"binder_spine_{k}", (512, 256 + 32 * k, 768, 288 + 32 * k))
            d.rectangle(r, fill=rgb(col))
            d.rectangle([r[0], r[1] + 2, r[2], r[1] + 4], fill=rgb("white"))
            d.rectangle([r[0], r[3] - 5, r[2], r[3] - 3], fill=rgb("white"))
            self.rrect((r[0] + 70, r[1] + 7, r[0] + 150, r[3] - 7), 3, "white", "navy", 2)
            self.text(r, lab, 13, "navy", xy=(r[0] + 110, r[1] + 16))
            d.rectangle([r[0] + 24, r[1] + 9, r[0] + 50, r[3] - 9], fill=rgb("navy_light"))
        r = self.reg("binder_cover", (512, 384, 640, 512))
        d.rectangle(r, fill=rgb("lavender"))
        self.rrect((r[0] + 8, r[1] + 8, r[2] - 8, r[3] - 8), 10, None, "lavender_dark", 3)
        self.rrect((r[0] + 22, r[1] + 76, r[0] + 84, r[1] + 108), 4, "white", "navy", 2)
        for k in range(3):
            d.rectangle([r[0] + 30, r[1] + 83 + k * 7, r[0] + 74 - k * 10, r[1] + 85 + k * 7], fill=rgb("navy_light"))

        # ---------------- divers ----------------
        r = self.reg("hourglass", (640, 384, 704, 448))
        self.rrect(r, 12, "pink", "navy", 3)
        self.hourglass(672, 416, 13)
        r = self.reg("warning", (704, 384, 768, 448))
        d.rectangle(r, fill=rgb("yellow"))
        d.polygon([(736, 392), (762, 440), (710, 440)], fill=rgb("coral"), outline=rgb("navy"))
        self.text(r, "!", 30, "navy", xy=(736, 424))
        r = self.reg("desk_note", (640, 448, 704, 512))
        d.rectangle(r, fill=rgb("yellow"))
        d.rectangle([640, 448, 704, 456], fill=rgb("yellow_dark"))
        for k in range(4):
            d.line([(648, 466 + k * 10), (696 - (k % 2) * 14, 464 + k * 10)], fill=rgb("navy"), width=3)
        r = self.reg("grommet", (704, 448, 768, 512))
        d.rectangle(r, fill=rgb("turquoise"))
        d.ellipse([712, 456, 760, 504], fill=rgb("navy"), outline=rgb("teal_dark"), width=5)

        r = self.reg("chevrons", (768, 256, 1024, 320))
        d.rectangle(r, fill=rgb("navy"))
        for k in range(3):
            x = 790 + k * 26
            d.polygon([(x + 18, 266), (x, 288), (x + 18, 310), (x + 26, 310), (x + 8, 288), (x + 26, 266)], fill=rgb("cyan"))
            x = 1002 - k * 26
            d.polygon([(x - 18, 266), (x, 288), (x - 18, 310), (x - 26, 310), (x - 8, 288), (x - 26, 266)], fill=rgb("cyan"))
        d.ellipse([882, 270, 910, 306], fill=rgb("cyan"))
        r = self.reg("brand_plate", (768, 320, 1024, 384))
        self.rrect(r, 14, "navy")
        self.text(r, "OVERFLOW", 34, "cream", dy=-6)
        self.text(r, "INDUSTRIES · BUREAU", 12, "cyan", bold=False, xy=(896, 370))
        r = self.reg("locker_card_7", (768, 384, 896, 448))
        self.rrect(r, 6, "white", "navy", 4)
        self.text(r, "B-07", 34, "navy")
        r = self.reg("locker_card_8", (896, 384, 1024, 448))
        self.rrect(r, 6, "white", "navy", 4)
        self.text(r, "B-08", 34, "navy")
        r = self.reg("locker_top", (768, 448, 1024, 512))
        d.rectangle(r, fill=rgb("lavender"))
        d.rectangle([776, 454, 1016, 506], outline=rgb("lavender_dark"), width=3)
        for x in (784, 1008):
            for y in (462, 498):
                d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=rgb("lavender_dark"))

        # ---------------- touches du clavier (cellules par touche) ----------------
        self.key_cells = {}
        x, y = 0, 512
        for i, k in enumerate(keyboard_layout()):
            w = int(round(32 * (k["x1"] - k["x0"] - 0.12) / (k["y1"] - k["y0"] - 0.12)))
            if x + w > 512:
                x, y = 0, y + 32
            rect = (x, y, x + w, y + 32)
            col = k["color"]
            d.rectangle([rect[0], rect[1], rect[2] - 1, rect[3] - 1], fill=rgb(col))
            d.rectangle([rect[0] + 2, rect[1] + 2, rect[2] - 3, rect[3] - 3],
                        fill=rgb("white") if col == "cream" else None)
            d.rectangle([rect[0] + 3, rect[1] + 3, rect[2] - 4, rect[3] - 4], fill=rgb(col))
            lab = k["label"]
            if lab:
                size = 17 if len(lab) <= 1 else (13 if len(lab) <= 3 else 11)
                fg = "white" if col in ("turquoise", "coral") else "navy"
                self.d.text(((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2), lab, font=font(size),
                            fill=rgb(fg), anchor="mm", stroke_width=0)
            self.key_cells[i] = rect
            x += w
        # vue de dessus du clavier (LOD1)
        r = self.reg("keyboard_top", (0, 768, 512, 1024))
        d.rectangle(r, fill=rgb("yellow"))
        sx = 512 / KB_W
        sy = 256 / KB_D
        for i, k in enumerate(keyboard_layout()):
            # vue du dessus, joueur devant : droite image = -X, haut image = -Y
            px0 = (KB_W / 2 - k["x1"]) * sx
            px1 = (KB_W / 2 - k["x0"]) * sx
            py0 = 768 + (k["y0"] + KB_D / 2) * sy
            py1 = 768 + (k["y1"] + KB_D / 2) * sy
            cell = self.img.crop(self.key_cells[i]).resize((max(2, int(px1 - px0)), max(2, int(py1 - py0))))
            self.img.paste(cell, (int(px0), int(py0)))
        d.rectangle([20, 774, 120, 792], fill=rgb("navy"))
        for k, c in enumerate(("mint", "cyan", "mint")):
            d.ellipse([440 + k * 16, 778, 450 + k * 16, 788], fill=rgb(c))

        # ---------------- téléphone ----------------
        digits = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"]
        self.phone_cells = {}
        for i, dg in enumerate(digits):
            c, rr = i % 3, i // 3
            rect = (512 + c * 32, 512 + rr * 32, 544 + c * 32, 544 + rr * 32)
            d.rectangle([rect[0], rect[1], rect[2] - 1, rect[3] - 1], fill=rgb("yellow"))
            d.rectangle([rect[0] + 3, rect[1] + 3, rect[2] - 4, rect[3] - 4], fill=rgb("cream"))
            self.text(rect, dg, 19, "navy")
            self.phone_cells[dg] = rect
        r = self.reg("phone_screen", (608, 512, 768, 576))
        self.rrect(r, 8, "navy")
        self.rrect((r[0] + 6, r[1] + 6, r[2] - 6, r[3] - 6), 6, "cyan")
        self.text(r, "DRING !", 22, "navy")
        r = self.reg("phone_label", (608, 576, 768, 616))
        self.rrect(r, 10, "white", "navy", 3)
        self.text(r, "BOB-7", 24, "navy")
        r = self.reg("copier_err", (640, 640, 768, 728))
        self.rrect(r, 10, "navy")
        self.rrect((r[0] + 6, r[1] + 6, r[2] - 6, r[3] - 6), 8, "cyan")
        self.text(r, "ERREUR !", 20, "coral", dy=-14)
        d.rectangle([r[0] + 16, r[1] + 52, r[2] - 16, r[1] + 66], outline=rgb("navy"), width=2)
        d.rectangle([r[0] + 18, r[1] + 54, r[0] + 90, r[1] + 64], fill=rgb("coral"))
        r = self.reg("phone_top", (512, 640, 640, 768))            # pavé (LOD1) : 3 x 4 touches
        d.rectangle(r, fill=rgb("yellow"))
        for i in range(12):
            c, rr = i % 3, i // 3
            bx, by = r[0] + 8 + c * 40, r[1] + 6 + rr * 31
            self.rrect((bx, by, bx + 32, by + 25), 4, "cream", "yellow_dark", 2)
            self.d.text((bx + 16, by + 12), digits[i], font=font(15), fill=rgb("navy"), anchor="mm")

        # ---------------- copieur ----------------
        r = self.reg("copier_screen", (768, 512, 1024, 688))
        self.rrect(r, 16, "navy")
        self.rrect((r[0] + 10, r[1] + 10, r[2] - 10, r[3] - 10), 12, "cyan")
        cx, cy = 896, 596
        for sgn in (-1, 1):                                  # yeux affolés
            ex = cx + sgn * 44
            d.ellipse([ex - 26, cy - 34, ex + 26, cy + 18], fill=rgb("white"), outline=rgb("navy"), width=5)
            d.ellipse([ex - 10 + sgn * 6, cy - 22, ex + 8 + sgn * 6, cy - 2], fill=rgb("navy"))
            d.line([(ex - 26, cy - 52 - sgn * 8), (ex + 22, cy - 52 + sgn * 8)], fill=rgb("navy"), width=7)
        pts = [(cx - 50 + k * 10, cy + 46 + (6 if k % 2 else -6)) for k in range(11)]
        d.line(pts, fill=rgb("navy"), width=6, joint="curve")
        d.polygon([(cx + 92, cy - 40), (cx + 82, cy - 18), (cx + 92, cy - 10), (cx + 102, cy - 18)], fill=rgb("white"),
                  outline=rgb("navy"))
        self.text(r, "!!", 28, "coral", xy=(cx - 96, cy - 50))
        r = self.reg("drawer_a4", (768, 688, 832, 720))
        self.rrect(r, 4, "white", "navy", 2)
        self.text(r, "A4", 18, "navy")
        r = self.reg("drawer_a3", (832, 688, 896, 720))
        self.rrect(r, 4, "white", "navy", 2)
        self.text(r, "A3", 18, "navy")
        r = self.reg("paper_level", (896, 688, 960, 720))
        d.rectangle(r, fill=rgb("navy"))
        for k in range(4):
            d.rectangle([900 + k * 14, 694, 910 + k * 14, 714], fill=rgb("mint" if k < 3 else "navy_light"))
        r = self.reg("label_a3_note", (960, 688, 1024, 720))
        self.rrect(r, 4, "coral", "navy", 2)
        self.text(r, "JAM!", 14, "white")
        r = self.reg("copier_vent", (768, 720, 896, 784))
        d.rectangle(r, fill=rgb("yellow"))
        for k in range(6):
            self.rrect((776, 726 + k * 9, 888, 731 + k * 9), 2, "navy")
        r = self.reg("copier_panel", (896, 720, 1024, 784))
        d.rectangle(r, fill=rgb("cream"))
        self.rrect((r[0] + 6, r[1] + 6, r[0] + 72, r[1] + 54), 6, "cyan", "navy", 3)
        d.ellipse([r[0] + 84, r[1] + 10, r[0] + 116, r[1] + 42], fill=rgb("pink"), outline=rgb("navy"), width=2)
        d.ellipse([r[0] + 92, r[1] + 46, r[0] + 108, r[1] + 60], fill=rgb("mint"))
        r = self.reg("copier_front_lod", (768, 784, 1024, 896))      # tiroirs papier (LOD1)
        d.rectangle(r, fill=rgb("yellow"))
        for k in range(3):
            y0 = r[1] + 6 + k * 34
            self.rrect((r[0] + 8, y0, r[2] - 8, y0 + 30), 5, "cream", "yellow_dark", 2)
            d.rectangle([r[0] + 100, y0 + 6, r[0] + 156, y0 + 11], fill=rgb("navy"))
            self.rrect((r[0] + 18, y0 + 14, r[0] + 46, y0 + 26), 2, "white", "navy", 1)

        # ---------------- dossiers ----------------
        r = self.reg("sheet_text", (512, 768, 640, 896))
        d.rectangle(r, fill=rgb("paper"))
        d.rectangle([r[0] + 12, r[1] + 12, r[0] + 70, r[1] + 20], fill=rgb("navy_light"))
        for k in range(8):
            d.rectangle([r[0] + 12, r[1] + 32 + k * 11, r[2] - 14 - (k * 23) % 40, r[1] + 35 + k * 11],
                        fill=rgb("grey_line"))
        r = self.reg("folder_cover", (640, 896, 896, 1024))
        d.rectangle(r, fill=rgb("peach"))
        d.rectangle([r[0], r[1], r[0] + 10, r[3]], fill=rgb("pink"))
        self.rrect((r[0] + 120, r[1] + 70, r[0] + 232, r[1] + 112), 6, "white", "navy", 3)
        for k in range(2):
            d.rectangle([r[0] + 130, r[1] + 80 + k * 12, r[0] + 200 - k * 20, r[1] + 84 + k * 12], fill=rgb("navy_light"))
        d.ellipse([r[0] + 200, r[1] + 74, r[0] + 230, r[1] + 108], fill=rgb("pink"))
        self.hourglass(r[0] + 215, r[1] + 91, 6.5)
        d.rectangle([r[0] + 24, r[1] + 14, r[0] + 96, r[1] + 26], fill=rgb("peach_dark"))
        r = self.reg("folder_edge", (896, 896, 1024, 960))
        d.rectangle(r, fill=rgb("pink"))
        d.rectangle([r[0], r[1] + 26, r[2], r[1] + 38], fill=rgb("pink_light"))
        r = self.reg("folder_tab", (896, 960, 1024, 1024))
        self.rrect(r, 6, "pink", "navy", 2)
        self.hourglass(960, 992, 10, fill="navy", sand="cream")
        r = self.reg("locker_door_lod", (512, 896, 640, 960))
        d.rectangle(r, fill=rgb("lavender_light"))
        for k in range(6):
            d.rectangle([r[2] - 40 + k * 6, r[1] + 10, r[2] - 37 + k * 6, r[3] - 10], fill=rgb("navy"))
        self.rrect((r[0] + 12, r[1] + 24, r[0] + 34, r[1] + 40), 3, "navy")
        r = self.reg("bypass_label", (512, 960, 640, 1024))
        d.rectangle(r, fill=rgb("turquoise"))
        self.text(r, "A4 >", 22, "white")


# ---------------------------------------------------------------------------
# Primitives (bmesh temporaires)
def _fit(bm, mn, mx):
    for v in bm.verts:
        v.co = Vector(((v.co.x + 0.5) * (mx[0] - mn[0]) + mn[0],
                       (v.co.y + 0.5) * (mx[1] - mn[1]) + mn[1],
                       (v.co.z + 0.5) * (mx[2] - mn[2]) + mn[2]))


def bevel_edges(bm, edges, r, seg):
    edges = [e for e in edges if e.is_valid]
    if r <= 0 or not edges:
        return
    verts = list({v for e in edges for v in e.verts})
    bmesh.ops.bevel(bm, geom=verts + edges, offset=r, offset_type="OFFSET", segments=seg,
                    profile=0.5, affect="EDGES", clamp_overlap=True)


def drop_faces(bm, normal, tol=0.999):
    n = Vector(normal)
    bm.normal_update()
    fs = [f for f in bm.faces if f.normal.dot(n) > tol]
    if fs:
        bmesh.ops.delete(bm, geom=fs, context="FACES_ONLY")


def box(mn, mx, r=0.0, seg=2, sel=None, skip=()):
    """Boîte alignée biseautée. sel(edge, zmin, zmax) filtre les arêtes biseautées."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    _fit(bm, mn, mx)
    if r > 0:
        z0, z1 = mn[2], mx[2]
        edges = [e for e in bm.edges if sel is None or sel(e, z0, z1)]
        bevel_edges(bm, edges, r, seg)
    for n in skip:
        drop_faces(bm, n)
    return bm


def top_edges(e, z0, z1):
    return all(abs(v.co.z - z1) < 1e-5 for v in e.verts)


def not_bottom(e, z0, z1):
    return not all(abs(v.co.z - z0) < 1e-5 for v in e.verts)


def vertical_edges(e, z0, z1):
    a, b = e.verts
    return abs(a.co.x - b.co.x) < 1e-6 and abs(a.co.y - b.co.y) < 1e-6


def cyl(center, r, h, sides=16, axis="Z", r_top=None, bevel=0.0, seg=1, skip_bottom=False):
    """Cylindre (tronc de cône) : base au point center, longueur h le long de +axis."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=sides, radius1=r,
                          radius2=r if r_top is None else r_top, depth=h)
    bmesh.ops.translate(bm, vec=Vector((0, 0, h / 2)), verts=bm.verts)
    bm.normal_update()
    if bevel > 0:
        caps = [f for f in bm.faces if abs(f.normal.z) > 0.99]
        edges = [e for f in caps for e in f.edges]
        bevel_edges(bm, edges, bevel, seg)
    if skip_bottom:
        drop_faces(bm, (0, 0, -1))
    rot = {"Z": Matrix.Identity(4), "X": Matrix.Rotation(math.radians(90), 4, "Y"),
           "-X": Matrix.Rotation(math.radians(-90), 4, "Y"), "Y": Matrix.Rotation(math.radians(-90), 4, "X"),
           "-Y": Matrix.Rotation(math.radians(90), 4, "X"), "-Z": Matrix.Rotation(math.radians(180), 4, "X")}[axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ rot, verts=bm.verts)
    return bm


def round_poly(pts, radii, seg=4):
    """Polygone 2D aux coins arrondis (Bézier quadratique sur chaque coin)."""
    out = []
    n = len(pts)
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * n
    for i in range(n):
        p = Vector(pts[i])
        r = radii[i]
        if r <= 0:
            out.append(tuple(p))
            continue
        a = Vector(pts[i - 1])
        b = Vector(pts[(i + 1) % n])
        da = (a - p)
        db = (b - p)
        la, lb = da.length, db.length
        t = min(r, la * 0.49, lb * 0.49)
        pa = p + da.normalized() * t
        pb = p + db.normalized() * t
        for k in range(seg + 1):
            s = k / seg
            q = (1 - s) ** 2 * pa + 2 * (1 - s) * s * p + s ** 2 * pb
            out.append((q.x, q.y))
    return out


def _signed_area(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def prism(poly, axis, a0, a1, bevel=0.0, seg=2):
    """Extrusion d'un profil 2D. axis='X' : profil (y, z) ; 'Y' : (x, z) ; 'Z' : (x, y)."""
    if _signed_area(poly) < 0:
        poly = list(reversed(poly))

    def P(u, v, a):
        if axis == "X":
            return Vector((a, u, v))
        if axis == "Y":
            return Vector((u, a, v))
        return Vector((u, v, a))

    bm = bmesh.new()
    r0 = [bm.verts.new(P(u, v, a0)) for (u, v) in poly]
    r1 = [bm.verts.new(P(u, v, a1)) for (u, v) in poly]
    n = len(poly)
    bm.faces.new(r0[::-1])
    bm.faces.new(r1)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        cap_edges = [e for e in bm.edges if all(abs(_axis_val(v.co, axis) - a0) < 1e-6 for v in e.verts)
                     or all(abs(_axis_val(v.co, axis) - a1) < 1e-6 for v in e.verts)]
        bevel_edges(bm, cap_edges, bevel, seg)
    return bm


def _axis_val(co, axis):
    return {"X": co.x, "Y": co.y, "Z": co.z}[axis]


def rrect_ring(cx, cy, hw, hd, r, n=3):
    r = max(0.0, min(r, hw - 1e-4, hd - 1e-4))
    pts = []
    for (sx, sy, a0) in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        ccx, ccy = cx + sx * (hw - r), cy + sy * (hd - r)
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((ccx + r * math.cos(a), ccy + r * math.sin(a)))
    return pts


def loft(levels, cx=0.0, cy=0.0, n=3, cap_bottom=True, cap_top=True):
    """Loft de rectangles arrondis : levels = [(z, demi_largeur, demi_profondeur, rayon)]."""
    bm = bmesh.new()
    rings = []
    for (z, hw, hd, r) in levels:
        rings.append([bm.verts.new((x, y, z)) for (x, y) in rrect_ring(cx, cy, hw, hd, r, n)])
    m = len(rings[0])
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_bottom:
        bm.faces.new(rings[0][::-1])
    if cap_top:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def tube(points, radius, sides=6, caps=True, closed=False):
    """Tube balayé le long d'une polyligne 3D (repères à transport parallèle)."""
    P = [Vector(p) for p in points]
    n = len(P)
    T = []
    for i in range(n):
        if closed:
            t = P[(i + 1) % n] - P[i - 1]
        else:
            t = P[min(i + 1, n - 1)] - P[max(i - 1, 0)]
        T.append(t.normalized())
    ref = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
    N = (ref - ref.dot(T[0]) * T[0]).normalized()
    bm = bmesh.new()
    rings = []
    rad = radius if callable(radius) else (lambda i: radius)
    for i in range(n):
        N = (N - N.dot(T[i]) * T[i]).normalized()
        B = T[i].cross(N)
        rr = rad(i)
        rings.append([bm.verts.new(P[i] + rr * (math.cos(2 * math.pi * k / sides) * N +
                                                 math.sin(2 * math.pi * k / sides) * B)) for k in range(sides)])
    segs = n if closed else n - 1
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(sides):
            l = (k + 1) % sides
            bm.faces.new((a[k], a[l], b[l], b[k]))
    if caps and not closed:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def catmull(ctrl, per_seg=8):
    C = [Vector(c) for c in ctrl]
    C = [C[0]] + C + [C[-1]]
    out = []
    for i in range(1, len(C) - 2):
        p0, p1, p2, p3 = C[i - 1], C[i], C[i + 1], C[i + 2]
        for k in range(per_seg):
            t = k / per_seg
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(C[-2])
    return out


def coil_along(path, coil_r, turns, pts_per_turn):
    """Points d'une hélice enroulée autour d'un chemin (cordon spiralé)."""
    # ré-échantillonnage par longueur
    L = [0.0]
    for a, b in zip(path[:-1], path[1:]):
        L.append(L[-1] + (b - a).length)
    total = L[-1]
    m = int(turns * pts_per_turn)
    out = []
    Tp = (path[1] - path[0]).normalized()
    ref = Vector((0, 0, 1)) if abs(Tp.z) < 0.9 else Vector((1, 0, 0))
    N = (ref - ref.dot(Tp) * Tp).normalized()
    j = 0
    for i in range(m + 1):
        s = total * i / m
        while j < len(L) - 2 and L[j + 1] < s:
            j += 1
        f = (s - L[j]) / max(L[j + 1] - L[j], 1e-9)
        p = path[j].lerp(path[j + 1], f)
        T = (path[j + 1] - path[j]).normalized()
        N = (N - N.dot(T) * T).normalized()
        B = T.cross(N)
        a = 2 * math.pi * turns * i / m
        out.append(p + coil_r * (math.cos(a) * N + math.sin(a) * B))
    return out


def grid_slab(x0, x1, y0, y1, nx, ny, ztop, thick):
    """Plaque fine dont le dessus suit ztop(x, y) (couverture de dossier souple)."""
    bm = bmesh.new()
    top, bot = {}, {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            x = x0 + (x1 - x0) * i / nx
            y = y0 + (y1 - y0) * j / ny
            z = ztop(x, y)
            top[i, j] = bm.verts.new((x, y, z))
            bot[i, j] = bm.verts.new((x, y, z - thick))
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((top[i, j], top[i + 1, j], top[i + 1, j + 1], top[i, j + 1]))
            bm.faces.new((bot[i, j], bot[i, j + 1], bot[i + 1, j + 1], bot[i + 1, j]))
    border = [(i, 0) for i in range(nx)] + [(nx, j) for j in range(ny)] + \
             [(i, ny) for i in range(nx, 0, -1)] + [(0, j) for j in range(ny, 0, -1)]
    for k in range(len(border)):
        a, b = border[k], border[(k + 1) % len(border)]
        bm.faces.new((bot[a], bot[b], top[b], top[a]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def xf(bm, M):
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm


def T(x, y, z):
    return Matrix.Translation(Vector((x, y, z)))


def Rz(deg, pivot=(0, 0, 0)):
    p = Vector(pivot)
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, "Z") @ Matrix.Translation(-p)


def Rx(deg, pivot=(0, 0, 0)):
    p = Vector(pivot)
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, "X") @ Matrix.Translation(-p)


def Ry(deg, pivot=(0, 0, 0)):
    p = Vector(pivot)
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, "Y") @ Matrix.Translation(-p)


def frame(origin, xaxis, yaxis):
    """Matrice d'un repère local (x, y, normale) : place une pièce sur un plan incliné."""
    X = Vector(xaxis).normalized()
    Y = Vector(yaxis).normalized()
    Z = X.cross(Y).normalized()
    M = Matrix((X, Y, Z)).transposed().to_4x4()
    M.translation = Vector(origin)
    return M


# ---------------------------------------------------------------------------
def default_up(n):
    if abs(n.z) > 0.9:
        return Vector((0, -1, 0)) if n.z > 0 else Vector((0, 1, 0))
    return Vector((0, 0, 1))


class MeshBuilder:
    """Accumule les pièces peintes et produit un maillage à 1 matériau."""

    def __init__(self, name, atlas):
        self.name = name
        self.atlas = atlas
        self.V, self.F, self.UV, self.thr = [], [], [], []
        self.parts = 0

    def add(self, bm, paint, decals=(), smooth=35.0):
        """paint : nom de pastille, ou fonction(face) -> nom.
        decals : dicts {dir, rect|cell, up?, cos?, range?} ; projection planaire."""
        bm.normal_update()
        bm.verts.index_update()
        base = len(self.V)
        self.V.extend(tuple(v.co) for v in bm.verts)
        faces = list(bm.faces)
        cos = [v.co for v in bm.verts]
        mn = Vector((min(c.x for c in cos), min(c.y for c in cos), min(c.z for c in cos)))
        mx = Vector((max(c.x for c in cos), max(c.y for c in cos), max(c.z for c in cos)))
        size = mx - mn
        assign = {}
        for dec in decals:
            n = Vector(dec["dir"]).normalized()
            sel = [f for f in faces if f not in assign and f.normal.dot(n) > dec.get("cos", 0.7)]
            if not sel:
                continue
            up = Vector(dec["up"]) if "up" in dec else default_up(n)
            up = (up - up.dot(n) * n).normalized()
            right = (-n).cross(up)
            if "range" in dec:
                u0, u1, v0, v1 = dec["range"]
            else:
                pts = [l.vert.co for f in sel for l in f.loops]
                us = [p.dot(right) for p in pts]
                vs = [p.dot(up) for p in pts]
                u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
            rect = dec["rect"] if "rect" in dec else self.atlas.decal[dec["name"]]
            for f in sel:
                assign[f] = (rect, right, up, (u0, u1, v0, v1), dec.get("flip_u", False))
        for f in faces:
            self.F.append([base + l.vert.index for l in f.loops])
            self.thr.append(smooth)
            a = assign.get(f)
            if a:
                rect, right, up, (u0, u1, v0, v1), flip = a
                for l in f.loops:
                    p = l.vert.co
                    s = min(1, max(0, (p.dot(right) - u0) / max(u1 - u0, 1e-6)))
                    t = min(1, max(0, (p.dot(up) - v0) / max(v1 - v0, 1e-6)))
                    if flip:
                        s = 1 - s
                    self.UV.append(self.atlas.rect_uv(rect, s, t))
            else:
                name = paint(f) if callable(paint) else paint
                n = f.normal
                ax = max(range(3), key=lambda k: abs(n[k]))
                i1, i2 = [k for k in range(3) if k != ax]
                for l in f.loops:
                    p = l.vert.co
                    s = (p[i1] - mn[i1]) / max(size[i1], 1e-6)
                    t = (p[i2] - mn[i2]) / max(size[i2], 1e-6)
                    self.UV.append(self.atlas.swatch_uv(name, s, t))
        bm.free()
        self.parts += 1

    def tris(self):
        return sum(len(f) - 2 for f in self.F)

    def build(self, material, collection):
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(self.V, [], self.F)
        uv = me.uv_layers.new(name="UVMap")
        flat = [c for p in self.UV for c in p]
        uv.data.foreach_set("uv", flat)
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:
            lf = e.link_faces
            if len(lf) != 2:
                e.smooth = False
                continue
            t = min(self.thr[lf[0].index], self.thr[lf[1].index])
            e.smooth = e.calc_face_angle(math.pi) < math.radians(t)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(material)
        ob = bpy.data.objects.new(self.name, me)
        collection.objects.link(ob)
        return ob


def make_material(img):
    mat = bpy.data.materials.new("M_bureau_atlas")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.48
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.35
    return mat


def save_atlas(atlas, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atlas.img.save(path, optimize=True)
