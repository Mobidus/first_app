"""Rendus de contrôle (Cycles CPU) des assets Toy Overflow à partir des exports RÉIMPORTÉS.

Usage : .venv/bin/python -I assets/source/blender/render_props_toy.py [props|plush|all|<asset_id>...]
Sorties (reports/T03/renders/) :
  <id>_3q.png, <id>_sil.png (512 x 512, 32 échantillons), <id>_profile.png pour les assets allongés,
  props_toy_sheet.png (5 accessoires + machine), toy_family_lineup.png (les 8 objets + avatar).
Fond lavande de la famille (#EEE7FF), sol récepteur d'ombre, soleil + remplissage doux.
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

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
IMPORT_DIR = os.path.join(ROOT, "assets", "import", "models")
OUT = os.path.join(ROOT, "reports", "T03", "renders")
PX = 512
PROPS = ["toy_flat_duck", "toy_train", "toy_drum", "toy_domino", "toy_shape_cube", "machine_toy_spinner"]
PLUSH = ["toy_plush_mallow", "toy_plush_loppy", "toy_plush_octo"]


def srgb(h):
    h = h.lstrip("#")
    return [((int(h[i:i + 2], 16) / 255.0) ** 2.2) for i in (0, 2, 4)]


def scene(silhouette=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 8 if silhouette else 32
    sc.cycles.use_denoising = not silhouette
    sc.render.resolution_x = sc.render.resolution_y = PX
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    if silhouette:
        bg.inputs["Color"].default_value = (1, 1, 1, 1)
        bg.inputs["Strength"].default_value = 1.0
    else:
        bg.inputs["Color"].default_value = (*srgb("#EEE7FF"), 1)
        bg.inputs["Strength"].default_value = 0.55
        sun = bpy.data.lights.new("sun", "SUN")
        sun.energy = 2.3
        sun.angle = math.radians(18)
        so = bpy.data.objects.new("sun", sun)
        sc.collection.objects.link(so)
        so.rotation_euler = (math.radians(40), math.radians(8), math.radians(215))
        fill = bpy.data.lights.new("fill", "SUN")
        fill.energy = 0.55
        fo = bpy.data.objects.new("fill", fill)
        sc.collection.objects.link(fo)
        fo.rotation_euler = (math.radians(65), 0, math.radians(-40))
    return sc


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    return objs


def floor(z=0.0, size=400):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z - 0.001))
    p = bpy.context.active_object
    m = bpy.data.materials.new("floor")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    dif.inputs["Color"].default_value = (*srgb("#E4DBFA"), 1)
    nt.links.new(dif.outputs[0], out.inputs[0])
    p.data.materials.append(m)
    return p


def silhouette_override():
    m = bpy.data.materials.new("SIL")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (0, 0, 0, 1)
    nt.links.new(e.outputs[0], o.inputs[0])
    bpy.context.view_layer.material_override = m


def bounds(objs):
    co = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in objs])
    return co.min(0), co.max(0)


def camera(objs, direction, margin=1.12, persp=True):
    mn, mx = bounds(objs)
    ctr = Vector(((mn + mx) / 2).tolist())
    d = Vector(direction).normalized()
    cd = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cd)
    bpy.context.scene.collection.objects.link(cam)
    rot = (-d).to_track_quat("-Z", "Y")
    cam.rotation_euler = rot.to_euler()
    corners = [Vector((x, y, z)) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]
    Rinv = rot.to_matrix().inverted()
    loc_c = [Rinv @ (c - ctr) for c in corners]
    half = max(max(abs(p.x), abs(p.y)) for p in loc_c) * margin
    if persp:
        cd.type = "PERSP"
        cd.lens = 70.0
        fov = 2 * math.atan(cd.sensor_width / (2 * cd.lens))
        dist = half / math.tan(fov / 2) + max(p.z for p in loc_c)
        cam.location = ctr + d * dist
        cd.clip_end = dist * 4
    else:
        cd.type = "ORTHO"
        cd.ortho_scale = 2 * half
        cam.location = ctr + d * 200
        cd.clip_end = 1000
    bpy.context.scene.camera = cam
    return cam


def render(path):
    st = bpy.context.scene.render.image_settings
    st.file_format = "PNG"
    st.color_mode = "RGB"
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


VIEW_3Q = (1.0, 1.15, 0.85)  # avant (+X du canard / train, +Y Roblox -Z visible) et côté


def render_asset(asset_id):
    path = os.path.join(IMPORT_DIR, asset_id + ".glb")
    out = []
    for sil in (False, True):
        scene(sil)
        objs = import_glb(path)
        if sil:
            silhouette_override()
        else:
            floor()
        direction = (0.55, 1.0, 0.62) if asset_id.startswith("machine") else VIEW_3Q
        camera(objs, direction)
        p = os.path.join(OUT, f"{asset_id}_{'sil' if sil else '3q'}.png")
        render(p)
        out.append(p)
    if asset_id in ("toy_flat_duck", "toy_train", "toy_plush_loppy", "machine_toy_spinner"):
        scene(False)
        objs = import_glb(path)
        floor()
        camera(objs, (0.0, 1.0, 0.12) if asset_id != "machine_toy_spinner" else (0.0, 1.0, -0.05))
        p = os.path.join(OUT, f"{asset_id}_profile.png")
        render(p)
        out.append(p)
    return out


def load_px(p):
    im = bpy.data.images.load(p)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)
    return a


def sheet(paths, cols, out, tile=PX):
    rows = math.ceil(len(paths) / cols)
    canvas = np.ones((rows * tile, cols * tile, 4), dtype=np.float32)
    for k, p in enumerate(paths):
        a = load_px(p)
        if a.shape[0] != tile:
            step = a.shape[0] // tile
            a = a[::step, ::step]
        r, c = divmod(k, cols)
        r = rows - 1 - r
        canvas[r * tile:(r + 1) * tile, c * tile:(c + 1) * tile] = a[:tile, :tile]
    img = bpy.data.images.new("sheet", width=cols * tile, height=rows * tile, alpha=False)
    img.pixels.foreach_set(canvas.ravel())
    img.filepath_raw = out
    img.file_format = "PNG"
    img.save()


def lineup():
    """Les huit objets de la famille côte à côte + gabarit d'avatar (~5 studs)."""
    scene(False)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1600, 560
    order = ["toy_plush_mallow", "toy_plush_loppy", "toy_plush_octo", "toy_flat_duck", "toy_train", "toy_drum",
             "toy_domino", "toy_shape_cube"]
    x = 0.0
    allobjs = []
    for aid in order:
        objs = import_glb(os.path.join(IMPORT_DIR, aid + ".glb"))
        mn, mx = bounds(objs)
        dx = x - mn[0]
        roots = {o for o in bpy.data.objects if o.parent is None and (o in objs or any(c in objs for c in o.children_recursive))}
        for r in roots:
            r.location.x += dx
        bpy.context.view_layer.update()
        mn, mx = bounds(objs)
        x = mx[0] + 2.5
        allobjs += objs
    for name, size, loc in (("legs", (1.6, 0.9, 2.0), (0, 0, 1.0)), ("torso", (2.0, 1.0, 2.0), (0, 0, 3.0)),
                            ("head", (1.1, 1.1, 1.1), (0, 0, 4.55))):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x + 1.0 + loc[0], -2 + loc[1], loc[2]))
        o = bpy.context.active_object
        o.scale = size
        m = bpy.data.materials.new("av")
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*srgb("#203055"), 1)
        o.data.materials.append(m)
        bpy.context.view_layer.update()
        allobjs.append(o)
    floor()
    cam = camera(allobjs, (0.1, 1.0, 0.55), margin=1.07, persp=False)
    cam.data.ortho_scale *= 1.0
    p = os.path.join(OUT, "toy_family_lineup.png")
    render(p)
    return p


def main(args):
    os.makedirs(OUT, exist_ok=True)
    if not args or args == ["all"]:
        ids = PROPS + PLUSH
    elif args == ["props"]:
        ids = PROPS
    elif args == ["plush"]:
        ids = PLUSH
    else:
        ids = args
    done = {}
    for aid in ids:
        done[aid] = render_asset(aid)
        print("rendered", aid)
    if all(a in done for a in PROPS):
        tiles = []
        for aid in PROPS:
            tiles += done[aid][:2]
        sheet(tiles, 4, os.path.join(OUT, "props_toy_sheet.png"), tile=256)
    if not args or args == ["all"]:
        lineup()


if __name__ == "__main__":
    main(sys.argv[1:])
