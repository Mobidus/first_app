"""Rendus de contrôle de la famille Piscine Gonflable (Cycles CPU), depuis les GLB RÉIMPORTÉS.

Usage : .venv/bin/python -I assets/source/blender/render_props_pool.py [id ...]
  POOL_PREVIEW=1 : rendu rapide (8 échantillons) dans le scratch indiqué par POOL_RENDER_OUT.
Sorties (reports/T03/renders/) :
  <id>_3q.png          vue trois-quarts avant-droite (512 px, 48 échantillons, débruitage OIDN)
  <id>_silhouette.png  silhouette noire, vue basse 3/4 avant (hauteur d'yeux, ~15°)
  props_pool_sheet.png (3 x 4, étiquettes id / dimensions / triangles), props_pool_silhouettes_sheet.png
  props_pool_lineup.png (famille alignée + gabarit d'avatar 2 x 5 x 1,5 studs, échelle commune)
Copie autonome de render_props_reception.py (aucun import croisé). Contrôles de modélisation, pas des
captures Roblox.
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from build_props_pool import BUILDERS, IMPORT_DIR, ROOT  # noqa: E402

OUT = os.environ.get("POOL_RENDER_OUT") or os.path.join(ROOT, "reports", "T03", "renders")
PREVIEW = bool(os.environ.get("POOL_PREVIEW"))
RES = 512
BG = (227, 247, 255)  # eau #E3F7FF
VIEW_DIR = Vector((1.0, 1.3, 0.95))  # avant = +Y Blender (-Z Roblox), côté droit +X visible
# silhouette à hauteur d'yeux d'avatar (~15°) : c'est l'angle sous lequel un joueur voit les bouées dans la salle
SIL_DIR = Vector((0.75, 1.6, 0.48))


def empty():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path, offset=(0, 0, 0)):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    for o in objs:
        o.location = Vector(o.location) + Vector(offset)
    return objs


def setup(samples=48, transparent=True):
    sc = bpy.context.scene
    samples = 8 if PREVIEW else samples
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    try:
        sc.cycles.use_denoising = samples > 8
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:  # noqa: BLE001
        sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 6
    sc.render.resolution_x = sc.render.resolution_y = RES
    sc.render.film_transparent = transparent
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    if sc.world is None:
        sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.82, 0.9, 1.0, 1)
    bg.inputs["Strength"].default_value = 0.55
    if "KEY" not in bpy.data.objects:
        ld = bpy.data.lights.new("KEY", "SUN")
        ld.energy = 2.6
        ld.angle = math.radians(12)
        lo = bpy.data.objects.new("KEY", ld)
        sc.collection.objects.link(lo)
        d = Vector((-0.35, 0.8, 1.25)).normalized()
        lo.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        fd = bpy.data.lights.new("FILL", "SUN")
        fd.energy = 0.6
        fd.angle = math.radians(40)
        fo = bpy.data.objects.new("FILL", fd)
        sc.collection.objects.link(fo)
        fo.rotation_euler = Vector((1.0, -0.4, 0.5)).normalized().to_track_quat("Z", "Y").to_euler()
    if "GROUND" not in bpy.data.objects:
        bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
        g = bpy.context.active_object
        g.name = "GROUND"
        g.is_shadow_catcher = True


def frame_camera(objs, direction=VIEW_DIR, margin=1.12):
    pts = []
    for o in objs:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    d = direction.normalized()
    q = (-d).to_track_quat("-Z", "Y")
    R = q.to_matrix()
    right, up = R @ Vector((1, 0, 0)), R @ Vector((0, 1, 0))
    xs = [p.dot(right) for p in pts]
    ys = [p.dot(up) for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    ctr = sum(pts, Vector()) / len(pts)
    ctr = ctr - right * (ctr.dot(right) - cx) - up * (ctr.dot(up) - cy)
    span = max(max(xs) - min(xs), max(ys) - min(ys)) * margin
    cam_data = bpy.data.cameras.get("cam") or bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = span
    cam_data.clip_end = 1000
    cam = bpy.data.objects.get("cam") or bpy.data.objects.new("cam", cam_data)
    if cam.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(cam)
    cam.location = ctr + d * 100.0
    cam.rotation_euler = q.to_euler()
    bpy.context.scene.camera = cam
    return cam


def render_to(path, bg=BG):
    sc = bpy.context.scene
    st = sc.render.image_settings
    st.file_format = "PNG"
    st.color_mode = "RGBA" if sc.render.film_transparent else "RGB"
    tmp = path + ".tmp.png"
    sc.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    im = Image.open(tmp).convert("RGBA")
    base = Image.new("RGBA", im.size, bg + (255,))
    base.alpha_composite(im)
    base.convert("RGB").save(path, optimize=True)
    os.remove(tmp)


def silhouette_mode(on):
    vl = bpy.context.view_layer
    g = bpy.data.objects.get("GROUND")
    if on:
        m = bpy.data.materials.get("SIL") or bpy.data.materials.new("SIL")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = (0, 0, 0, 1)
        nt.links.new(e.outputs[0], o.inputs[0])
        vl.material_override = m
        if g:
            g.hide_render = True
        bpy.context.scene.cycles.samples = 4
        bpy.context.scene.cycles.use_denoising = False
    else:
        vl.material_override = None
        if g:
            g.hide_render = False


def label_font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def sheet(paths, labels, out, cols=3, cell=512, scale=0.75, insets=None):
    """Planche : une case par asset, étiquette id + dimensions + triangles ; `insets` {index: chemin} en coin."""
    c = int(cell * scale)
    rows = math.ceil(len(paths) / cols)
    pad = 46
    img = Image.new("RGB", (cols * c, rows * (c + pad)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f1, f2 = label_font(15), label_font(12)
    for k, (p, lab) in enumerate(zip(paths, labels)):
        r, cc = divmod(k, cols)
        im = Image.open(p).resize((c, c), Image.LANCZOS)
        img.paste(im, (cc * c, r * (c + pad)))
        if insets and k in insets:
            s_ = c // 3
            ins = Image.open(insets[k][0]).resize((s_, s_), Image.LANCZOS)
            img.paste(ins, (cc * c + c - s_ - 6, r * (c + pad) + 6))
            d.rectangle([cc * c + c - s_ - 6, r * (c + pad) + 6, cc * c + c - 6, r * (c + pad) + 6 + s_],
                        outline=(32, 48, 85), width=2)
            d.text((cc * c + c - s_ - 2, r * (c + pad) + s_ - 10), insets[k][1], fill=(32, 48, 85), font=f2)
        d.text((cc * c + 8, r * (c + pad) + c + 4), lab[0], fill=(32, 48, 85), font=f1)
        d.text((cc * c + 8, r * (c + pad) + c + 24), lab[1], fill=(74, 94, 146), font=f2)
    img.save(out, optimize=True)


def labels_for(ids):
    import json
    try:
        with open(os.path.join(ROOT, "assets", "source", "models", "pool", "build_info.json"), encoding="utf-8") as f:
            info = json.load(f)["assets"]
    except (OSError, KeyError, ValueError):
        info = {}
    out = []
    for p in ids:
        a = info.get(p, {})
        dm = a.get("lod0_dims_wdh")
        txt = (f"{dm[0]:.2f} x {dm[1]:.2f} x {dm[2]:.2f} studs  |  tris {a.get('lod0_tris')} / LOD1 {a.get('lod1_tris')}"
               if dm else "")
        out.append((p, txt))
    return out


def render_asset(pid):
    empty()
    setup()
    objs = import_glb(os.path.join(IMPORT_DIR, pid + ".glb"))
    frame_camera(objs)
    p3 = os.path.join(OUT, f"{pid}_3q.png")
    render_to(p3)
    silhouette_mode(True)
    frame_camera(objs, SIL_DIR)
    ps = os.path.join(OUT, f"{pid}_silhouette.png")
    render_to(ps, bg=(255, 255, 255))
    silhouette_mode(False)
    return p3, ps


def lineup(ids):
    empty()
    setup(samples=32)
    x = 0.0
    allo = []
    gap = 2.5
    for pid in ids:
        objs = import_glb(os.path.join(IMPORT_DIR, pid + ".glb"))
        mn = min((o.matrix_world @ Vector(c)).x for o in objs for c in o.bound_box)
        mx = max((o.matrix_world @ Vector(c)).x for o in objs for c in o.bound_box)
        for o in objs:
            o.location.x += x - mn
        x += (mx - mn) + gap
        allo += objs
    # gabarit d'avatar : boîte marine 2 (largeur) x 1,5 (profondeur) x 5 (hauteur) studs
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x + 1.0, 0, 2.5))
    o = bpy.context.active_object
    o.scale = (2.0, 1.5, 5.0)
    m = bpy.data.materials.new("avatar")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.03, 0.05, 0.12, 1)
    o.data.materials.append(m)
    allo.append(o)
    bpy.context.scene.render.resolution_x = 2048
    bpy.context.scene.render.resolution_y = 640
    frame_camera(allo, Vector((0.25, 1.0, 0.55)), margin=1.04)
    cam = bpy.context.scene.camera
    cam.data.ortho_scale *= 1.0
    out = os.path.join(OUT, "props_pool_lineup.png")
    render_to(out)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    ids = sys.argv[1:] or list(BUILDERS)
    res = {}
    for pid in ids:
        res[pid] = render_asset(pid)
        print("rendered", pid, flush=True)
    if len(ids) == len(BUILDERS):
        main9 = [p for p in ids if p != "pool_air_mattress_deflated"]
        labs = labels_for(main9)
        k = main9.index("pool_air_mattress")
        sheet([res[p][0] for p in main9], labs, os.path.join(OUT, "props_pool_sheet.png"),
              insets={k: (res["pool_air_mattress_deflated"][0], "dégonflé")})
        sheet([res[p][1] for p in main9], labs, os.path.join(OUT, "props_pool_silhouettes_sheet.png"),
              insets={k: (res["pool_air_mattress_deflated"][1], "dégonflé")})
        lineup(ids)


if __name__ == "__main__":
    main()
