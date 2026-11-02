"""Rendus de contrôle du lot plush_v2_small (Cycles CPU, orthographique).

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/render_plush_v2_small.py [all|pipou,mochi,...] [--root DIR]
        [--out DIR] [--quick] [--no-lineup]
Sorties (par défaut reports/T03/renders/) :
    toy_plush_<id>_v2_3q.png, _v2_front.png, _v2_silhouette.png, _v2_pose_{rest,fall,impact,rebound}.png
    plush_v2_small_sheet.png (planche contact) et plush_v2_small_lineup.png (échelle : 5 peluches +
    Mallow GLB existant + boîte avatar 2 x 1,5 x 5 studs).
Les poses sont appliquées par le rig (bones), pas par une déformation du maillage.
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

import plush_v2_small_specs as specs  # noqa: E402
from build_plush_v2_small import ROOT, apply_pose  # noqa: E402

W, H = 640, 480


def setup_world(samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.seed = 1
    sc.cycles.use_denoising = samples > 8
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.93, 0.93, 0.94, 1)
    bg.inputs["Strength"].default_value = 0.85
    for name, energy, rot in (("KEY", 2.6, (52, 0, 150)), ("FILL", 0.7, (65, 0, 30)), ("RIM", 1.0, (70, 0, -60))):
        if name not in bpy.data.objects:
            ld = bpy.data.lights.new(name, "SUN")
            ld.energy = energy
            ld.angle = math.radians(20)
            lo = bpy.data.objects.new(name, ld)
            sc.collection.objects.link(lo)
            lo.rotation_euler = tuple(math.radians(a) for a in rot)


def silhouette_mode(on):
    vl = bpy.context.view_layer
    sc = bpy.context.scene
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
        sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
        sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    else:
        vl.material_override = None
        sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.93, 0.93, 0.94, 1)
        sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.85


def camera(direction, target, ortho_scale):
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho_scale
    cam_data.clip_end = 400
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    d = Vector(direction).normalized()
    cam.location = Vector(target) + d * 60.0
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


def floor_plane():
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    fl = bpy.context.active_object
    fl.name = "floor"
    m = bpy.data.materials.new("floor")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.86, 0.86, 0.88, 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
    fl.data.materials.append(m)
    fl.is_shadow_catcher = True
    return fl


VIEWS_3Q = (0.95, 1.25, 0.95)


def run(key, root, out, quick):
    pl = specs.PLUSHES[key]()
    blend = os.path.join(root, "assets", "source", "models", "plush_v2", specs.MODEL_DIRS[key], f"{pl.label}.blend")
    bpy.ops.wm.open_mainfile(filepath=blend)
    os.makedirs(out, exist_ok=True)
    arm = bpy.data.objects[f"{pl.label}_Rig"]
    bpy.data.objects[f"{pl.label}_LOD1"].hide_render = True
    floor_plane()
    w, d, h = pl.envelope
    tgt = (0, 0, h * 0.42)
    span = max(w, d, h * 1.3) * 1.55
    samples = 12 if quick else 40
    setup_world(samples)
    paths = []

    def shot(name, direction, scale, sil=False):
        silhouette_mode(sil)
        bpy.data.objects["floor"].hide_render = sil
        cam = camera(direction, tgt, scale)
        p = os.path.join(out, f"{pl.asset_id}_v2_{name}.png")
        render(p)
        bpy.data.objects.remove(cam)
        paths.append(p)

    shot("3q", VIEWS_3Q, span)
    shot("front", (0, 1, 0.08), span)
    if quick:
        shot("back3q", (-0.9, -1.1, 0.9), span)
        shot("top", (0, 0.0001, 1), span)
        return paths
    shot("silhouette", VIEWS_3Q, span, sil=True)
    for pname in ("rest", "fall", "impact", "rebound"):
        apply_pose(arm, pl.poses[pname])
        shot(f"pose_{pname}", (1.0, 1.25, 0.6), span * 1.08)
    apply_pose(arm, {})
    silhouette_mode(False)
    return paths


def contact_sheet(rows, out_path):
    from PIL import Image, ImageDraw
    cols = max(len(r[1]) for r in rows)
    tw, th = W // 2, H // 2
    lab = 26
    sheet = Image.new("RGB", (cols * tw, len(rows) * (th + lab)), (250, 250, 250))
    dr = ImageDraw.Draw(sheet)
    for r, (title, paths) in enumerate(rows):
        y0 = r * (th + lab)
        dr.text((6, y0 + 6), title, fill=(32, 48, 85))
        for c, p in enumerate(paths):
            im = Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS)
            sheet.paste(im, (c * tw, y0 + lab))
            dr.text((c * tw + 6, y0 + lab + 4), os.path.basename(p).split("_v2_")[-1][:-4], fill=(90, 90, 90))
    sheet.save(out_path)


def lineup(root, out_path, samples=48):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_world(samples)
    floor_plane()
    items = [("toy_plush_mallow", os.path.join(ROOT, "assets", "import", "models", "toy_plush_mallow.glb"), 12)]
    for k in specs.PLUSHES:
        pl = specs.PLUSHES[k]()
        items.append((pl.asset_id, os.path.join(root, "assets", "import", "models", f"{pl.asset_id}.glb"),
                       pl.envelope[0]))
    x = 0.0
    gap = 1.6
    # gabarit avatar : boîte 2 (largeur) x 1,5 (profondeur) x 5 (hauteur) studs
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x + 1.0, 0, 2.5))
    av = bpy.context.active_object
    av.scale = (2.0, 1.5, 5.0)
    m = bpy.data.materials.new("avatar")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.09, 0.13, 0.30, 1)
    av.data.materials.append(m)
    x += 2.0 + gap
    for aid, path, width in items:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            if o.parent is None:
                o.location.x += x + width / 2.0
        x += width + gap
    tgt = (x / 2.0, 0, 2.4)
    cam = camera((0.35, 1.0, 0.42), tgt, x * 1.02)
    bpy.context.scene.render.resolution_x = 1600
    bpy.context.scene.render.resolution_y = 520
    render(out_path)
    bpy.data.objects.remove(cam)


if __name__ == "__main__":
    args = sys.argv[1:]
    root = ROOT
    out = os.path.join(ROOT, "reports", "T03", "renders")
    quick = "--quick" in args
    no_lineup = "--no-lineup" in args
    args = [a for a in args if a not in ("--quick", "--no-lineup")]
    if "--root" in args:
        i = args.index("--root")
        root = os.path.abspath(args[i + 1])
        args = args[:i] + args[i + 2:]
    if "--out" in args:
        i = args.index("--out")
        out = os.path.abspath(args[i + 1])
        args = args[:i] + args[i + 2:]
    which = args[0] if args else "all"
    keys = list(specs.PLUSHES) if which == "all" else which.split(",")
    rows = []
    for k in keys:
        pl = specs.PLUSHES[k]()
        rows.append((f"{pl.name_fr} ({pl.asset_id}, {pl.tier})", run(k, root, out, quick)))
    sheet_name = "plush_v2_small_sheet.png" if not quick else "plush_v2_small_quick_sheet.png"
    contact_sheet(rows, os.path.join(out, sheet_name))
    if not quick and not no_lineup:
        lineup(root, os.path.join(out, "plush_v2_small_lineup.png"))
    print("rendered", sum(len(r[1]) for r in rows))
