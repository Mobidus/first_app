"""Rendus de contrôle des peluches (Workbench, orthographique, fond neutre).

Usage : .venv/bin/python -I assets/source/blender/render_plush.py [mallow|loppy|octo|all]
Sorties : reports/T03/renders/<asset>_<vue>.png et <asset>_sheet.png
Ces images sont des contrôles de modélisation, pas des planches Claude Design.
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

import plush_specs as specs  # noqa: E402
from build_plush import MODEL_DIRS, ROOT, apply_pose  # noqa: E402

OUT = os.path.join(ROOT, "reports", "T03", "renders")
W, H = 640, 480


def setup_render(silhouette=False):
    """Cycles CPU (Workbench/EEVEE exigent un contexte GPU/EGL absent du conteneur)."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 4 if silhouette else 32
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    if sc.world is None:
        sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.93, 0.93, 0.93, 1)
    bg.inputs["Strength"].default_value = 1.0
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
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
        if "KEY" not in bpy.data.objects:
            ld = bpy.data.lights.new("KEY", "SUN")
            ld.energy = 2.2
            ld.angle = math.radians(25)
            lo = bpy.data.objects.new("KEY", ld)
            bpy.context.scene.collection.objects.link(lo)
            lo.rotation_euler = (math.radians(45), math.radians(10), math.radians(140))


def camera(direction, target, ortho_scale):
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho_scale
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    d = Vector(direction).normalized()
    cam.location = Vector(target) + d * 40.0
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def avatar_proxy(x, y):
    """Gabarit d'avatar ~5 studs (R15 normalisé, approximation boîtes) pour l'échelle."""
    parts = []
    for name, size, loc in (("legs", (1.6, 0.9, 2.0), (0, 0, 1.0)), ("torso", (2.0, 1.0, 2.0), (0, 0, 3.0)),
                            ("head", (1.1, 1.1, 1.1), (0, 0, 4.55))):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x + loc[0], y + loc[1], loc[2]))
        o = bpy.context.active_object
        o.scale = size
        o.name = f"avatar_{name}"
        mat = bpy.data.materials.new("avatar_mat")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.12, 0.28, 1)
        o.data.materials.append(mat)
        parts.append(o)
    return parts


def render(path):
    st = bpy.context.scene.render.image_settings
    st.file_format = "PNG"
    st.color_mode = "RGB"
    st.compression = 100
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def sheet(paths, cols, out):
    imgs = []
    for p in paths:
        im = bpy.data.images.load(p)
        a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)
        imgs.append(a)
    rows = math.ceil(len(imgs) / cols)
    canvas = np.ones((rows * H, cols * W, 4), dtype=np.float32)
    for k, a in enumerate(imgs):
        r, c = divmod(k, cols)
        r = rows - 1 - r  # origine bas-gauche dans Blender
        canvas[r * H:(r + 1) * H, c * W:(c + 1) * W] = a
    # planche à demi-résolution pour limiter le poids du dépôt
    canvas = canvas[::2, ::2]
    img = bpy.data.images.new("sheet", width=cols * W // 2, height=rows * H // 2, alpha=False)
    img.pixels = canvas.ravel()
    img.filepath_raw = out
    img.file_format = "PNG"
    img.save()


def run(key):
    cr = specs.CREATURES[key]()
    blend = os.path.join(ROOT, "assets", "source", "models", MODEL_DIRS[key], f"{cr.label}.blend")
    bpy.ops.wm.open_mainfile(filepath=blend)
    os.makedirs(OUT, exist_ok=True)
    arm = bpy.data.objects[f"{cr.label}_Rig"]
    far = bpy.data.objects[f"{cr.label}_LOD1"]
    far.hide_render = True
    w, d, h = cr.size_studs
    tgt = (0, 0, h / 2)
    span = max(w, d) * 1.25
    views = {
        "front": ((0, 1, 0), span),        # avant Roblox (-Z) = +Y Blender
        "side": ((1, 0, 0), span),
        "back": ((0, -1, 0), span),
        "top": ((0, 0, 1), span),
        "three_quarter": ((1.0, 1.1, 1.0), span * 1.05),
    }
    out = []
    setup_render()
    for vn, (dvec, sc) in views.items():
        cam = camera(dvec, tgt, sc)
        p = os.path.join(OUT, f"{cr.asset_id}_{vn}.png")
        render(p)
        out.append(p)
        bpy.data.objects.remove(cam)
    # silhouette noire (vue du jeu de trois-quarts et de dessus)
    setup_render(silhouette=True)
    for vn, dvec in (("silhouette_3q", (1.0, 1.1, 1.0)), ("silhouette_top", (0, 0, 1))):
        cam = camera(dvec, tgt, span * 1.05)
        p = os.path.join(OUT, f"{cr.asset_id}_{vn}.png")
        render(p)
        out.append(p)
        bpy.data.objects.remove(cam)
    # poses
    setup_render()
    for pname in ("rest", "fall", "impact", "rebound"):
        apply_pose(arm, cr.poses[pname])
        cam = camera((1.0, 1.1, 0.55), tgt, span * 1.05)
        p = os.path.join(OUT, f"{cr.asset_id}_pose_{pname}.png")
        render(p)
        out.append(p)
        bpy.data.objects.remove(cam)
    apply_pose(arm, {})
    # échelle avatar
    avatar_proxy(w / 2 + 2.0, d / 2 + 0.5)
    cam = camera((0.35, 1.0, 0.35), (1.5, 0, 2.5), span * 1.4)
    p = os.path.join(OUT, f"{cr.asset_id}_avatar_scale.png")
    render(p)
    out.append(p)
    sheet(out, 4, os.path.join(OUT, f"{cr.asset_id}_sheet.png"))
    print("rendered", len(out))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for k in (list(specs.CREATURES) if which == "all" else [which]):
        run(k)
