"""Rendus de contrôle des canards gonflables (Cycles CPU), depuis les GLB RÉIMPORTÉS.

Usage : .venv/bin/python -I assets/source/blender/render_ducks.py [--root DIR] [--only-sheets] [id ...]
Sorties (reports/T03/renders/) :
  <id>_3q.png          vue trois-quarts avant-droite (512 px, 32 échantillons, débruitage OIDN si dispo)
  <id>_silhouette.png  silhouette noire, même cadrage
  ducks_sheet.png               planche 5 x 3 étiquetée (id, dimensions, triangles LOD0/LOD1)
  ducks_silhouettes_sheet.png   planche des silhouettes
  ducks_lineup.png              une variante par forme + gabarit d'avatar 2 x 5 x 1,5, triés par taille
  ducks_accessories_sheet.png   bibliothèque d'accessoires seule (construite par duck_kit, tête de taille medium)
Ce sont des contrôles de modélisation, pas des captures Roblox.
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import duck_kit as K  # noqa: E402
from build_ducks import ROOT, VARIANTS, make_material, form_of  # noqa: E402

RES = 512
BG = (223, 247, 255)
VIEW_DIR = Vector((1.0, 1.3, 0.95))  # avant = +Y Blender (-Z Roblox), côté droit +X visible
LINEUP = ["pool_duck_mini_classic", "pool_duck_lilo_classic", "pool_duck_summer", "pool_duck_ring_pirate",
          "pool_duck_captain"]


def empty():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path, offset=(0, 0, 0)):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    for o in objs:
        o.location = Vector(o.location) + Vector(offset)
    return objs


def setup(samples=32):
    sc = bpy.context.scene
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
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.82, 0.9, 1.0, 1)
    bg.inputs["Strength"].default_value = 0.6
    if "KEY" not in bpy.data.objects:
        ld = bpy.data.lights.new("KEY", "SUN")
        ld.energy = 2.6
        ld.angle = math.radians(12)
        lo = bpy.data.objects.new("KEY", ld)
        sc.collection.objects.link(lo)
        lo.rotation_euler = Vector((-0.35, 0.8, 1.25)).normalized().to_track_quat("Z", "Y").to_euler()
        fd = bpy.data.lights.new("FILL", "SUN")
        fd.energy = 0.7
        fd.angle = math.radians(40)
        fo = bpy.data.objects.new("FILL", fd)
        sc.collection.objects.link(fo)
        fo.rotation_euler = Vector((1.0, -0.4, 0.5)).normalized().to_track_quat("Z", "Y").to_euler()
    if "GROUND" not in bpy.data.objects:
        bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, 0))
        g = bpy.context.active_object
        g.name = "GROUND"
        g.is_shadow_catcher = True


def frame_camera(objs, direction=VIEW_DIR, margin=1.1):
    bpy.context.view_layer.update()  # matrix_world à jour après déplacement des objets
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
    sc = bpy.context.scene
    aspect = sc.render.resolution_x / sc.render.resolution_y
    span = max((max(xs) - min(xs)) / aspect, max(ys) - min(ys)) * margin
    cam_data = bpy.data.cameras.get("cam") or bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = span * max(aspect, 1.0)
    cam_data.clip_end = 2000
    cam = bpy.data.objects.get("cam") or bpy.data.objects.new("cam", cam_data)
    if cam.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(cam)
    cam.location = ctr + d * 300.0
    cam.rotation_euler = q.to_euler()
    sc.camera = cam
    return cam


def render_to(path, bg=BG):
    sc = bpy.context.scene
    st = sc.render.image_settings
    st.file_format = "PNG"
    st.color_mode = "RGBA"
    tmp = path + ".tmp.png"
    sc.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    im = Image.open(tmp).convert("RGBA")
    base = Image.new("RGBA", im.size, bg + (255,))
    base.alpha_composite(im)
    base.convert("RGB").save(path, optimize=True)
    os.remove(tmp)


def silhouette_mode(on, samples=32):
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
        bpy.context.scene.cycles.samples = samples
        bpy.context.scene.cycles.use_denoising = True


def font(size, bold=True):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in ("/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/dejavu/"):
        if os.path.exists(d + name):
            return ImageFont.truetype(d + name, size)
    return ImageFont.load_default()


def stats(objs):
    pts = np.array([list(o.matrix_world @ v.co) for o in objs for v in o.data.vertices])
    dims = pts.max(axis=0) - pts.min(axis=0)
    t = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    return dims, t


def label2(dims, t0, t1):
    return f"{dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} st (WxDxH) | tris {t0}/{t1}"


def sheet(paths, labels, out, cols=5, cell=512, scale=0.62, title=None):
    c = int(cell * scale)
    rows = math.ceil(len(paths) / cols)
    pad = 46
    top = 44 if title else 0
    img = Image.new("RGB", (cols * c, top + rows * (c + pad)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    if title:
        d.text((12, 10), title, fill=(32, 48, 85), font=font(20))
    f1, f2 = font(13), font(12, bold=False)
    for k, (p, lab) in enumerate(zip(paths, labels)):
        r, cc = divmod(k, cols)
        im = Image.open(p).resize((c, c), Image.LANCZOS)
        y0 = top + r * (c + pad)
        img.paste(im, (cc * c, y0))
        l1, l2 = lab if isinstance(lab, tuple) else (lab, "")
        d.text((cc * c + 8, y0 + c + 4), l1, fill=(32, 48, 85), font=f1)
        d.text((cc * c + 8, y0 + c + 23), l2, fill=(58, 82, 136), font=f2)
    img.save(out, optimize=True)


def render_asset(pid, imp, out):
    empty()
    setup()
    objs = import_glb(os.path.join(imp, pid + ".glb"))
    dims, t0 = stats(objs)
    o1 = import_glb(os.path.join(imp, pid + "_lod1.glb"), offset=(1000, 0, 0))
    _d, t1 = stats(o1)
    for o in o1:
        bpy.data.objects.remove(o)
    frame_camera(objs)
    p3 = os.path.join(out, f"{pid}_3q.png")
    render_to(p3)
    silhouette_mode(True)
    ps = os.path.join(out, f"{pid}_silhouette.png")
    render_to(ps, bg=(255, 255, 255))
    silhouette_mode(False)
    lab = (pid, label2(dims, t0, t1))
    return p3, ps, lab


def lineup(imp, out):
    empty()
    setup(samples=32)
    sc = bpy.context.scene
    ids = sorted(LINEUP, key=lambda v: np.prod(K.FORMS[form_of(v)]["envelope"]))
    # vue de face (+Y) : l'écran va de +X (gauche) à -X (droite) -> on aligne vers -X : avatar, puis du plus
    # petit au plus grand, lisible de gauche à droite
    allo = []
    gap = 2.5
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-1.0, 0, 2.5))
    o = bpy.context.active_object
    o.scale = (2.0, 1.5, 5.0)  # gabarit d'avatar : 2 (largeur) x 5 (hauteur) x 1,5 (profondeur) studs
    m = bpy.data.materials.new("avatar")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.03, 0.05, 0.12, 1)
    o.data.materials.append(m)
    allo.append(o)
    x = -2.0 - gap
    for pid in ids:
        objs = import_glb(os.path.join(imp, pid + ".glb"))
        mn = min((o.matrix_world @ Vector(c)).x for o in objs for c in o.bound_box)
        mx = max((o.matrix_world @ Vector(c)).x for o in objs for c in o.bound_box)
        for o in objs:
            o.location.x += x - mx
        x -= (mx - mn) + gap
        allo += objs
    sc.render.resolution_x = 2400
    sc.render.resolution_y = 760
    frame_camera(allo, Vector((0.22, 1.0, 0.42)), margin=1.04)
    p = os.path.join(out, "ducks_lineup.png")
    render_to(p)
    im = Image.open(p)
    d = ImageDraw.Draw(im)
    d.text((16, 12), "Canards gonflables : une variante par forme, triées par taille + avatar 2 x 5 x 1,5 studs (marine)",
           fill=(32, 48, 85), font=font(22))
    d.text((16, 42), "avatar  ->  " + "  ->  ".join(f"{form_of(v)} ({v})" for v in ids), fill=(58, 82, 136), font=font(16, bold=False))
    im.save(p, optimize=True)
    return p


def accessories_sheet(out, tex_dir):
    """Chaque accessoire construit SEUL (sans tête ni corps) par duck_kit, à l'échelle d'une tête medium."""
    tiles, labels = [], []
    tmp_dir = os.path.join(out, "_acc_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    for name, (sock, fn, lab) in K.ACCESSORIES.items():
        empty()
        setup(samples=24)
        sc = bpy.context.scene
        sc.render.resolution_x = sc.render.resolution_y = 256
        mat, _imgs = make_material(os.path.join(tex_dir, "duck_atlas_1024.png"),
                                   os.path.join(tex_dir, "duck_atlas_rough_1024.png"))
        A = K.Asset(name, (12, 10, 9), 0, 1.0)
        if sock == "body":
            if fn is None:  # peau du corps : échantillon de matière
                tile = "mariniere" if name == "mariniere" else "hawaii"
                pc = K.puff(K.rrect(1.6, 1.6, 0.5, 4), 0.5, 2)
                K.place(pc, K.basis((1, 0, 0), (0, 0, 1), (0, -1, 0), (0, 0, 1.7)))
                A.add(pc, K.r_if(lambda c, n: n.y > 0.5, K.r_const(K.m_plane(tile, (0, 0.25, 1.7), (-1, 0, 0), (0, 0, 1), 3.2, 3.2)),
                                 K.r_pal("yellow", 0, 3)))
            else:
                form = "large_ring" if name in ("sauveteur_band", "skull_decal") else "medium"
                meas = K.Measure(A)
                bc = K.form_body(meas, form, "yellow")
                fn(A, bc)
        else:
            hc = K.head_ctx("medium", A)
            hc.cxy = (0.0, 0.0)
            hc.z = 3.0
            hc.beak_under_z = hc.bz - hc.bt * 0.95
            fn(A, hc)
        if not A.bm.verts:
            continue
        ob = A.to_object(name, [mat])
        frame_camera([ob], Vector((0.75, 1.3, 0.6)), margin=1.15)
        p = os.path.join(tmp_dir, f"{name}.png")
        render_to(p)
        tiles.append(p)
        labels.append((name, f"[{sock}] {lab}"))
    pth = os.path.join(out, "ducks_accessories_sheet.png")
    sheet(tiles, labels, pth, cols=7, cell=256, scale=1.0,
          title="Bibliothèque d'accessoires des canards (duck_kit.ACCESSORIES) : prise [socket] et libellé")
    for p in tiles:
        os.remove(p)
    os.rmdir(tmp_dir)
    return pth


def main():
    args = sys.argv[1:]
    root = ROOT
    if "--root" in args:
        i = args.index("--root")
        root = os.path.abspath(args[i + 1])
        args = args[:i] + args[i + 2:]
    only_sheets = "--only-sheets" in args
    args = [a for a in args if a != "--only-sheets"]
    imp = os.path.join(root, "assets", "import", "models")
    out = os.path.join(root, "reports", "T03", "renders")
    tex = os.path.join(root, "assets", "source", "models", "ducks", "textures")
    os.makedirs(out, exist_ok=True)
    ids = args or list(VARIANTS)
    res = {}
    if not only_sheets:
        for pid in ids:
            res[pid] = render_asset(pid, imp, out)
            print("rendered", pid, flush=True)
    if len(ids) == len(VARIANTS):
        if only_sheets:
            for pid in ids:
                empty()
                o0 = import_glb(os.path.join(imp, pid + ".glb"))
                dims, t0 = stats(o0)
                o1 = import_glb(os.path.join(imp, pid + "_lod1.glb"))
                _d, t1 = stats(o1)
                res[pid] = (os.path.join(out, f"{pid}_3q.png"), os.path.join(out, f"{pid}_silhouette.png"),
                            (pid, label2(dims, t0, t1)))
        sheet([res[p][0] for p in ids], [res[p][2] for p in ids], os.path.join(out, "ducks_sheet.png"),
              title="Canards gonflables FILLING UP — 15 variantes (vue 3/4 avant-droite ; avant = -Z Roblox ; tris LOD0/LOD1)")
        sheet([res[p][1] for p in ids], [res[p][2] for p in ids], os.path.join(out, "ducks_silhouettes_sheet.png"),
              title="Silhouettes noires (même cadrage)")
        lineup(imp, out)
        print("sheets done", flush=True)
        accessories_sheet(out, tex)
        print("accessories done", flush=True)


if __name__ == "__main__":
    main()
