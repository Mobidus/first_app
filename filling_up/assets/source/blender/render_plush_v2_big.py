"""Rendus de contrôle des grandes peluches v2 (Cycles CPU, orthographique, fond neutre).

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/render_plush_v2_big.py [balto|ronron|bobine|all|sheet|lineup]
        [--out-root DIR] [--renders DIR]

Par peluche (reports/T03/renders/) : <id>_3q.png, <id>_front.png, <id>_silhouette.png (3/4 noir),
<id>_silhouette_top.png, <id>_pose_{rest,fall,impact,rebound}.png.
« all » enchaîne les trois peluches puis la planche plush_v2_big_sheet.png et la mise à l'échelle
plush_v2_big_lineup.png (les 3 GLB + le GLB de Mallow pour référence + une boîte avatar 2 x 5 x 1,5 studs).
Les poses sont appliquées par le rig depuis la pose de référence (jamais cumulées).
Ce sont des contrôles de modélisation, pas des planches Claude Design.
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import plush_v2_big_specs as specs  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
W, H = 800, 600


def pose_matrix(arm, bone_name, spec):
    rest = arm.data.bones[bone_name].matrix_local.copy()
    h = Vector(rest.translation)
    M = rest
    if spec.get("r"):
        axis, ang = spec["r"]
        R = Matrix.Rotation(math.radians(ang), 4, Vector(axis).normalized())
        M = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ M
    if spec.get("t"):
        M = Matrix.Translation(Vector(spec["t"])) @ M
    return M


def apply_pose(arm, pose):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for bname, sp in pose.items():
        arm.pose.bones[bname].matrix = pose_matrix(arm, bname, sp)
    bpy.context.view_layer.update()


def setup_render(silhouette=False, samples=None):
    if samples is None:
        samples = 12 if QUICK else 40
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 4 if silhouette else samples
    try:
        sc.cycles.use_denoising = not silhouette
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:  # noqa: BLE001
        sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    if sc.world is None:
        sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.80, 0.84, 0.90, 1) if not silhouette else (1, 1, 1, 1)
    bg.inputs["Strength"].default_value = 0.9 if not silhouette else 1.0
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = 0.0
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
        for ob in bpy.data.objects:
            if ob.name.startswith(("KEY", "FILL", "FLOOR")):
                ob.hide_render = True
    else:
        vl.material_override = None
        for ob in bpy.data.objects:
            if ob.name.startswith(("KEY", "FILL", "FLOOR")):
                ob.hide_render = False
        if "KEY" not in bpy.data.objects:
            ld = bpy.data.lights.new("KEY", "SUN")
            ld.energy = 2.6
            ld.angle = math.radians(30)
            lo = bpy.data.objects.new("KEY", ld)
            sc.collection.objects.link(lo)
            lo.rotation_euler = (math.radians(50), math.radians(8), math.radians(150))
            lf = bpy.data.lights.new("FILL", "SUN")
            lf.energy = 0.7
            lf.angle = math.radians(60)
            fo = bpy.data.objects.new("FILL", lf)
            sc.collection.objects.link(fo)
            fo.rotation_euler = (math.radians(60), 0, math.radians(-40))
            # sol clair qui reçoit les ombres
            me = bpy.data.meshes.new("FLOOR")
            s = 200
            me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
            fl = bpy.data.objects.new("FLOOR", me)
            sc.collection.objects.link(fl)
            mat = bpy.data.materials.new("FLOORM")
            mat.use_nodes = True
            mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.78, 0.80, 0.84, 1)
            mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
            me.materials.append(mat)


def camera(direction, target, ortho_scale):
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho_scale
    cam_data.clip_end = 500
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    d = Vector(direction).normalized()
    cam.location = Vector(target) + d * 80.0
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


def label_image(path, text):
    im = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.width, 22], fill=(255, 255, 255))
    d.text((6, 5), text, fill=(20, 30, 60))
    return im


QUICK = False


def run(key, out_root, rdir):
    pl = specs.PLUSHES[key]()
    blend = os.path.join(out_root, "assets", "source", "models", "plush_v2", specs.MODEL_DIRS[key], f"{pl.label}.blend")
    bpy.ops.wm.open_mainfile(filepath=blend)
    os.makedirs(rdir, exist_ok=True)
    arm = bpy.data.objects[f"{pl.label}_Rig"]
    bpy.data.objects[f"{pl.label}_LOD1"].hide_render = True
    w, d, h = pl.envelope
    tgt = (0, 0, h * 0.42)
    span = max(w, d) * 1.18
    out = []
    setup_render()
    for vn, dvec, sc in (("3q", (0.95, 1.0, 0.78), span), ("front", (0, 1, 0.12), span * 0.95),
                         ("back3q", (-0.9, -1.0, 0.75), span), ("top", (0, -0.001, 1), span)):
        cam = camera(dvec, tgt, sc)
        p = os.path.join(rdir, f"{pl.asset_id}_{vn}.png")
        render(p)
        out.append(p)
        bpy.data.objects.remove(cam)
    out += silhouettes(pl, rdir)
    setup_render()
    if QUICK:
        print("rendered (quick)", key, len(out))
        return out
    for pname in ("rest", "fall", "impact", "rebound"):
        apply_pose(arm, pl.poses[pname])
        cam = camera((1.0, 1.05, 0.5), (0, 0, h * 0.5), span * 1.05)
        p = os.path.join(rdir, f"{pl.asset_id}_pose_{pname}.png")
        render(p)
        out.append(p)
        bpy.data.objects.remove(cam)
    apply_pose(arm, {})
    print("rendered", key, len(out))
    return out


def silhouettes(pl, rdir):
    """Silhouette noire de profil avant-trois-quarts, caméra quasi horizontale (lecture du personnage :
    tête, défenses, oreilles, queue, jet d'eau dépassent du contour) + silhouette vue de dessus."""
    w, d, h = pl.envelope
    out = []
    setup_render(silhouette=True)
    for vn, dvec, tz, sc in (("silhouette", (1.0, 0.45, 0.06), h * 0.5, max(w, d) * 1.15),
                             ("silhouette_top", (0, -0.001, 1), h * 0.42, max(w, d) * 1.18)):
        cam = camera(dvec, (0, 0, tz), sc)
        p = os.path.join(rdir, f"{pl.asset_id}_{vn}.png")
        render(p)
        out.append(p)
        bpy.data.objects.remove(cam)
    return out


def contact_sheet(rdir):
    rows = []
    cols = ["3q", "front", "back3q", "silhouette", "pose_rest", "pose_fall", "pose_impact", "pose_rebound"]
    tw, th = 400, 300
    for key in specs.PLUSHES:
        pl = specs.PLUSHES[key]()
        row = []
        for c in cols:
            p = os.path.join(rdir, f"{pl.asset_id}_{c}.png")
            im = label_image(p, f"{pl.name_fr} - {c}").resize((tw, th), Image.LANCZOS)
            row.append(im)
        rows.append(row)
    sheet = Image.new("RGB", (tw * len(cols), th * len(rows)), (255, 255, 255))
    for r, row in enumerate(rows):
        for c, im in enumerate(row):
            sheet.paste(im, (c * tw, r * th))
    out = os.path.join(rdir, "plush_v2_big_sheet.png")
    sheet.save(out, optimize=True)
    return out


def lineup(out_root, rdir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    items = [("toy_plush_mallow", os.path.join(ROOT, "assets", "import", "models", "toy_plush_mallow.glb"))]
    for key in specs.PLUSHES:
        pl = specs.PLUSHES[key]()
        items.append((pl.asset_id, os.path.join(out_root, "assets", "import", "models", pl.asset_id + ".glb")))
    x = 0.0
    gap = 3.0
    placed = []
    for aid, path in items:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        meshes = [o for o in new if o.type == "MESH" and not any(c.name == "glTF_not_exported" for c in o.users_collection)]
        mn = np.array([1e9] * 3)
        mx = -mn
        for o in meshes:
            for c in o.bound_box:
                v = o.matrix_world @ Vector(c)
                mn = np.minimum(mn, v)
                mx = np.maximum(mx, v)
        width = mx[0] - mn[0]
        dx = x - mn[0]
        for o in new:
            if o.parent is None:
                o.location.x += dx
        placed.append((aid, x, width))
        x += width + gap
    for o in bpy.data.objects:  # formes de bones créées par l'import glTF : jamais rendues
        if any(c.name == "glTF_not_exported" for c in o.users_collection):
            o.hide_render = True
    # boîte avatar 2 (largeur) x 5 (hauteur) x 1,5 (profondeur) studs
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x + 1.0, 0, 2.5))
    av = bpy.context.active_object
    av.scale = (2.0, 1.5, 5.0)
    av.name = "avatar_box_2x5x1.5"
    mat = bpy.data.materials.new("avatar")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.12, 0.28, 1)
    av.data.materials.append(mat)
    total = x + 2.0
    setup_render()
    global W, H
    W0, H0 = W, H
    W, H = 1600, 640
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = W, H
    cam = camera((0.18, 1.0, 0.32), (total / 2, 0, 4.0), total * 1.04)
    p = os.path.join(rdir, "plush_v2_big_lineup.png")
    render(p)
    W, H = W0, H0
    im = Image.open(p).convert("RGB")
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, im.width, 24], fill=(255, 255, 255))
    # la caméra regarde l'avant (+Y Blender) : +X est à gauche de l'image, l'ordre s'affiche donc inversé
    dr.text((8, 6), "Lineup, de gauche a droite (studs) : boite avatar 2x5x1.5 | Bobine 24x20x11 | Ronron 16x13x8 | "
                    "Balto 16x15x8 | Mallow 12x10x5 (reference, GLB existant)", fill=(20, 30, 60))
    im.save(p, optimize=True)
    return p


if __name__ == "__main__":
    args = sys.argv[1:]
    out_root = ROOT
    rdir = os.path.join(ROOT, "reports", "T03", "renders")
    if "--out-root" in args:
        i = args.index("--out-root")
        out_root = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    if "--renders" in args:
        i = args.index("--renders")
        rdir = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    if "--quick" in args:
        args.remove("--quick")
        QUICK = True
    which = args[0] if args else "all"
    if which in specs.PLUSHES:
        run(which, out_root, rdir)
    elif which == "silhouettes":
        for k in specs.PLUSHES:
            pl = specs.PLUSHES[k]()
            bpy.ops.wm.open_mainfile(filepath=os.path.join(out_root, "assets", "source", "models", "plush_v2",
                                                           specs.MODEL_DIRS[k], f"{pl.label}.blend"))
            bpy.data.objects[f"{pl.label}_LOD1"].hide_render = True
            silhouettes(pl, rdir)
    elif which == "sheet":
        print(contact_sheet(rdir))
    elif which == "lineup":
        print(lineup(out_root, rdir))
    else:
        for k in specs.PLUSHES:
            run(k, out_root, rdir)
        print(contact_sheet(rdir))
        print(lineup(out_root, rdir))
