"""Rendus de contrôle des props Bureau perdu (Cycles CPU ; Workbench/EEVEE exigent un GPU absent).

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/render_props_bureau.py [--extra] [asset_id ...]

Sorties (reports/T03/renders/) :
    <id>_3q.png            vue de trois-quarts avant (512 px, 32 échantillons, sol + ombres)
    <id>_silhouette.png    silhouette noire même vue (lisibilité sans couleur)
    props_bureau_sheet.png / props_bureau_silhouettes_sheet.png   planches de famille
    --extra : vues face / dessus / LOD1 / échelle avatar dans le dossier scratch indiqué par
              la variable BUREAU_EXTRA_DIR (contrôle d'itération, non livrées).
Ces images sont des contrôles de modélisation, pas des planches Claude Design.
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import bureau_kit as K  # noqa: E402
from build_props_bureau import ASSET_ORDER, BLEND_FILE, ROOT  # noqa: E402

OUT = os.path.join(ROOT, "reports", "T03", "renders")
PX = 512
VIEW_3Q = Vector((-0.82, 1.2, 0.92))      # avant (+Y Blender = -Z Roblox), côté -X, en plongée
VIEW_LOW = Vector((-0.82, 1.2, 0.3))      # même azimut, presque à hauteur d'oeil


def lin(hexname):
    def c(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = K.rgb(hexname)
    return (c(r), c(g), c(b), 1.0)


def setup(silhouette=False, samples=32):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 6 if silhouette else samples
    sc.cycles.use_denoising = not silhouette
    sc.cycles.max_bounces = 4
    sc.render.resolution_x = sc.render.resolution_y = PX
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (1, 1, 1, 1) if silhouette else lin("#EAF0F6")
    bg.inputs["Strength"].default_value = 1.0 if silhouette else 0.62
    vl = bpy.context.view_layer
    if silhouette:
        m = bpy.data.materials.get("SIL") or bpy.data.materials.new("SIL")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = (0, 0, 0, 1)
        nt.links.new(e.outputs[0], o.inputs[0])
        vl.material_override = m
    else:
        vl.material_override = None
    floor = bpy.data.objects.get("FLOOR")
    if floor:
        floor.hide_render = silhouette
    for n in ("KEY", "FILL"):
        if n in bpy.data.objects:
            bpy.data.objects[n].hide_render = silhouette


def lights_and_floor():
    if "KEY" not in bpy.data.objects:
        ld = bpy.data.lights.new("KEY", "SUN")
        ld.energy = 2.1
        ld.angle = math.radians(10)
        lo = bpy.data.objects.new("KEY", ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.rotation_euler = (math.radians(50), 0, math.radians(-128))
        lf = bpy.data.lights.new("FILL", "SUN")
        lf.energy = 0.5
        lf.angle = math.radians(40)
        fo = bpy.data.objects.new("FILL", lf)
        bpy.context.scene.collection.objects.link(fo)
        fo.rotation_euler = (math.radians(62), 0, math.radians(-215))
    if "FLOOR" not in bpy.data.objects:
        bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
        f = bpy.context.active_object
        f.name = "FLOOR"
        m = bpy.data.materials.new("floor")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = lin("#DCE4EE")
        b.inputs["Roughness"].default_value = 0.9
        f.data.materials.append(m)


def camera(direction, target, radius, lens=50.0, ortho=None):
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cd.clip_end = 2000
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    cam = bpy.data.objects.new("cam", cd)
    bpy.context.scene.collection.objects.link(cam)
    d = Vector(direction).normalized()
    fov = 2 * math.atan(18.0 / lens)
    dist = radius / math.sin(fov / 2) * 1.04
    cam.location = Vector(target) + d * (dist if not ortho else 200)
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def render(path):
    st = bpy.context.scene.render.image_settings
    st.file_format = "PNG"
    st.color_mode = "RGB"
    st.compression = 90
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def show_only(names):
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob.name != "FLOOR" and not ob.name.startswith("avatar"):
            ob.hide_render = ob.name not in names


def bbox(ob):
    cs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
    mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
    return mn, mx


def avatar_proxy(x, y):
    """Gabarit d'avatar ~5 studs (boîtes R15 approximatives) pour juger l'échelle."""
    for name, size, loc in (("legs", (1.6, 0.9, 2.0), (0, 0, 1.0)), ("torso", (2.0, 1.0, 2.0), (0, 0, 3.0)),
                            ("head", (1.1, 1.1, 1.1), (0, 0, 4.55))):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x + loc[0], y + loc[1], loc[2]))
        o = bpy.context.active_object
        o.scale = size
        o.name = f"avatar_{name}"
        mat = bpy.data.materials.new("avatar_mat")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = lin("#3B4E80")
        o.data.materials.append(mat)


def label_sheet(paths, labels, cols, out, cell=PX, scale=1.0):
    rows = math.ceil(len(paths) / cols)
    W, H = cols * cell, rows * (cell + 34)
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for k, (p, lab) in enumerate(zip(paths, labels)):
        r, c = divmod(k, cols)
        im = Image.open(p).convert("RGB").resize((cell, cell))
        sheet.paste(im, (c * cell, r * (cell + 34) + 34))
        d.text((c * cell + 10, r * (cell + 34) + 8), lab, font=K.font(17), fill=K.rgb("navy"))
    if scale != 1.0:
        sheet = sheet.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    sheet.save(out, optimize=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    extra = "--extra" in sys.argv
    extra_dir = os.environ.get("BUREAU_EXTRA_DIR", os.path.join(OUT, "_extra"))
    ids = args or ASSET_ORDER
    bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)
    os.makedirs(OUT, exist_ok=True)
    lights_and_floor()
    beauty, sil, sil_low, labels = [], [], [], []
    for aid in ids:
        ob = bpy.data.objects[aid]
        mn, mx = bbox(ob)
        size = mx - mn
        tgt = Vector((0, 0, size.z * 0.42))
        rad = 0.5 * size.length
        show_only({aid})
        setup()
        cam = camera(VIEW_3Q, tgt, rad)
        p = os.path.join(OUT, f"{aid}_3q.png")
        render(p)
        beauty.append(p)
        setup(silhouette=True)
        ps = os.path.join(OUT, f"{aid}_silhouette.png")
        render(ps)
        sil.append(ps)
        bpy.data.objects.remove(cam)
        cam = camera(VIEW_LOW, tgt, rad)          # hauteur d'oeil d'avatar : profils, pieds, vides
        pl = os.path.join(OUT, f"{aid}_silhouette_low.png")
        render(pl)
        sil_low.append(pl)
        bpy.data.objects.remove(cam)
        tris = sum(len(pl.vertices) - 2 for pl in ob.data.polygons)
        labels.append(f"{aid}  {size.x:.1f}x{size.y:.1f}x{size.z:.1f}  {tris} tris")
        if extra:
            os.makedirs(extra_dir, exist_ok=True)
            setup(samples=16)
            for vn, dv, o in (("front", (0, 1, 0.12), None), ("top", (0, -0.001, 1), max(size.x, size.y) * 1.1),
                              ("back3q", (0.9, -1.1, 0.8), None)):
                cam = camera(dv, tgt, rad, ortho=o)
                render(os.path.join(extra_dir, f"{aid}_{vn}.png"))
                bpy.data.objects.remove(cam)
            show_only({f"{aid}_LOD1"})
            cam = camera(VIEW_3Q, tgt, rad)
            render(os.path.join(extra_dir, f"{aid}_lod1_3q.png"))
            bpy.data.objects.remove(cam)
    if not args:
        label_sheet(beauty, labels, 3, os.path.join(OUT, "props_bureau_sheet.png"))
        both, blabels = [], []
        for p1, p2, lab in zip(sil, sil_low, labels):
            both += [p1, p2]
            short = lab.split("  ")[0]
            blabels += [short + " (3/4 haut)", short + " (oeil)"]
        label_sheet(both, blabels, 6, os.path.join(OUT, "props_bureau_silhouettes_sheet.png"), scale=0.5)
        # échelle avatar : la famille alignée avec un gabarit de 5 studs (lecture gauche -> droite vue de face)
        show_only(set(ASSET_ORDER))
        xs = 0.0
        avatar_proxy(xs - 1.0, 2.0)
        xs -= 3.0
        for aid in ASSET_ORDER:
            ob = bpy.data.objects[aid]
            mn, mx = bbox(ob)
            ob.location.x = xs - mx.x
            ob.location.y = -4.0 if aid.startswith("machine") else 0.0
            xs -= (mx.x - mn.x) + 1.6
        setup()
        bpy.context.scene.render.resolution_x = 2000
        bpy.context.scene.render.resolution_y = 520
        span = -xs + 2.0
        cam = camera((0.0, 1.0, 0.38), (xs / 2 + 0.5, 0, 5.0), 10, ortho=span * 1.02)
        render(os.path.join(OUT, "props_bureau_lineup.png"))


if __name__ == "__main__":
    main()
