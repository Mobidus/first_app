"""Construit les peluches FILLING UP dans Blender (headless), de façon reproductible.

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/build_plush.py [mallow|loppy|octo|all]

Pipeline par créature :
 1. primitives implicites (plush_specs) -> maillages -> union par remaillage voxel
    = "haute définition" (sert à peindre les tissus, coutures et broderies) ;
 2. couleurs de régions calculées par sommet (attribut "Col") ;
 3. LOD proche (~3 000 triangles) et LOD lointain (~500) par décimation ;
 4. UV dépliées (smart project) puis cuisson de la couleur haute définition dans
    un atlas unique (1 024 px proche, 256 px lointain) : 1 matériau par maillage ;
 5. rig : Root (ancrage statique, jamais posé) + Belly_00..Belly_22 + secondaires ;
    poids calculés, normalisés, <= 4 influences ;
 6. poses de démonstration (repos, chute, impact, rebond, appui joueur) par
    translations/rotations de bones uniquement ; pose de référence = repos ;
 7. sauvegarde .blend, exports GLB/FBX, collision.json, pose_library.json.

Aucune graine aléatoire n'est nécessaire (tout est déterministe) ; SEED est fixé
pour toute extension future.
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import plush_specs as specs  # noqa: E402

SEED = 7
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # filling_up/
VOXEL = 0.05
NEAR_TRIS = 3400
FAR_TRIS = 690
NEAR_TEX = 1024
FAR_TEX = 256

MODEL_DIRS = {"mallow": "Mallow", "loppy": "Loppy", "octo": "Octo"}


# ---------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0  # 1 BU = 1 stud (cf. décision 0003)
    return sc


def activate(obj, others=()):
    bpy.ops.object.select_all(action="DESELECT")
    for o in others:
        o.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def mesh_from_prim(pr):
    verts, faces = pr.surface_points()
    me = bpy.data.meshes.new(pr.name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    ob = bpy.data.objects.new(pr.name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def build_highres(cr):
    objs = [mesh_from_prim(p) for p in cr.prims]
    activate(objs[0], objs[1:])
    bpy.ops.object.join()
    hi = bpy.context.view_layer.objects.active
    hi.name = f"{cr.label}_HI"
    m = hi.modifiers.new("remesh", "REMESH")
    m.mode = "VOXEL"
    m.voxel_size = VOXEL
    m.adaptivity = 0.0
    bpy.ops.object.modifier_apply(modifier=m.name)
    sm = hi.modifiers.new("smooth", "SMOOTH")
    sm.factor = 0.5
    sm.iterations = 2
    bpy.ops.object.modifier_apply(modifier=sm.name)
    # ne jamais passer sous le sol (z < 0)
    me = hi.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    co[:, 2] = np.maximum(co[:, 2], 0.0)
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    return hi


def paint_vertex_colors(obj, cr):
    me = obj.data
    n = len(me.vertices)
    P = np.empty(n * 3)
    me.vertices.foreach_get("co", P)
    P = P.reshape(-1, 3)
    N = np.empty(n * 3)
    me.vertices.foreach_get("normal", N)
    N = N.reshape(-1, 3)
    C = cr.color_fn(P, N)
    attr = me.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT")
    rgba = np.concatenate([C, np.ones((n, 1))], axis=1).astype(np.float32)
    attr.data.foreach_set("color", rgba.ravel())
    me.update()


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def make_lod(hi, name, target_tris):
    me = hi.data.copy()
    me.name = name
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    activate(ob)
    cur = tri_count(ob)
    d = ob.modifiers.new("decimate", "DECIMATE")
    d.decimate_type = "COLLAPSE"
    d.ratio = min(1.0, target_tris / max(cur, 1))
    d.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=d.name)
    t = ob.modifiers.new("tri", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=t.name)
    # supprimer l'attribut couleur hérité (la couleur passe par l'atlas cuit)
    for a in list(ob.data.color_attributes):
        ob.data.color_attributes.remove(a)
    bpy.ops.object.shade_smooth()
    return ob


def unwrap(ob):
    activate(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")


def hi_bake_material(hi):
    mat = bpy.data.materials.new("HI_bake_src")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "Col"
    nt.links.new(at.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    hi.data.materials.clear()
    hi.data.materials.append(mat)


def lod_material(ob, label, size):
    img = bpy.data.images.new(f"{ob.name}_albedo", width=size, height=size, alpha=False)
    img.colorspace_settings.name = "sRGB"
    mat = bpy.data.materials.new(f"M_{label}_fabric")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
    nt.nodes.active = tex
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return img


def bake(hi, lo, img, out_png):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 1
    sc.render.bake.use_selected_to_active = True
    sc.render.bake.cage_extrusion = 0.06
    sc.render.bake.max_ray_distance = 0.25
    sc.render.bake.margin = 6
    activate(lo, [hi])
    bpy.ops.object.bake(type="EMIT")
    img.filepath_raw = out_png
    img.file_format = "PNG"
    img.save()


# ---------------------------------------------------------------------------
def build_rig(cr, lods):
    arm_data = bpy.data.armatures.new(f"{cr.label}_Rig")
    arm = bpy.data.objects.new(f"{cr.label}_Rig", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    activate(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    root = eb.new("Root")
    root.head = (0, 0, 0)
    root.tail = (0, 0, 1.0)
    root.use_deform = True  # ancrage des sommets du dessous ; jamais posé (décision 0004)
    heads = cr.belly_bone_heads()
    for name, h in heads.items():
        b = eb.new(name)
        b.head = tuple(h)
        b.tail = tuple(h + np.array([0, 0, 0.8]))
        b.parent = root
        b.use_deform = True
    for name, (h, _owner) in cr.secondary_bones.items():
        b = eb.new(name)
        b.head = tuple(h)
        b.tail = tuple(h + np.array([0, 0, 0.8]))
        b.parent = root
        b.use_deform = True
    bpy.ops.object.mode_set(mode="OBJECT")

    stats = {}
    for lo in lods:
        me = lo.data
        n = len(me.vertices)
        P = np.empty(n * 3)
        me.vertices.foreach_get("co", P)
        P = P.reshape(-1, 3)
        names, W = cr.skin_weights(P)
        for j, bn in enumerate(names):
            vg = lo.vertex_groups.new(name=bn)
            idx = np.nonzero(W[:, j] > 0)[0]
            for i in idx:
                vg.add([int(i)], float(W[i, j]), "REPLACE")
        mod = lo.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        lo.parent = arm
        stats[lo.name] = {
            "vertices": n,
            "max_influences": int((W > 0).sum(axis=1).max()),
            "weight_sum_max_error": float(np.abs(W.sum(axis=1) - 1).max()),
            "unweighted_vertices": int(((W > 0).sum(axis=1) == 0).sum()),
        }
    return arm, stats


def pose_matrix(arm, bone_name, spec):
    """Matrice armature-space du bone pour une pose (translation + rotation autour de sa tête)."""
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


def apply_pose(arm, pose, scale=1.0):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)  # toujours depuis la pose de référence
    bpy.context.view_layer.update()
    for bname, sp in pose.items():
        sp2 = {"t": tuple(scale * x for x in sp["t"]) if sp.get("t") else None,
               "r": (sp["r"][0], scale * sp["r"][1]) if sp.get("r") else None}
        arm.pose.bones[bname].matrix = pose_matrix(arm, bname, sp2)
    bpy.context.view_layer.update()


def store_pose_actions(arm, cr):
    """Une action par pose (image 1) dans le .blend, pour relecture dans Blender."""
    arm.animation_data_create()
    for pname, pose in cr.poses.items():
        apply_pose(arm, pose)
        act = bpy.data.actions.new(f"{cr.label}_pose_{pname}")
        act.use_fake_user = True
        arm.animation_data.action = act
        for pb in arm.pose.bones:
            pb.keyframe_insert("location", frame=1)
            pb.keyframe_insert("rotation_quaternion", frame=1)
    arm.animation_data.action = None
    apply_pose(arm, {})


def to_roblox(v):
    """Blender (x, y, z) -> Roblox (x, y=z, z=-y)."""
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(float(-v[1]), 4)]


def pose_library(cr):
    heads = dict(cr.belly_bone_heads())
    for k, (h, _o) in cr.secondary_bones.items():
        heads[k] = h
    lib = {
        "asset_id": cr.asset_id,
        "axes": "roblox_model_space (X largeur, Y haut, Z profondeur ; avant = -Z)",
        "units": "studs",
        "usage": "Pose = translation et rotation (axe, angle en degrés, autour de la tête du bone au repos) "
                 "exprimées en espace modèle Roblox, à convertir dans l'espace parent de chaque Bone. "
                 "Toujours recalculer depuis la pose de référence (Transform = identité) ; ne jamais cumuler. "
                 "Aucune échelle : Bone.Transform est un CFrame.",
        "reference_pose": "rest (toutes transformations identité)",
        "static_bones": ["Root"],
        "bone_rest_heads": {"Root": [0, 0, 0], **{k: to_roblox(v) for k, v in heads.items()}},
        "poses": {},
    }
    for pname, pose in cr.poses.items():
        out = {}
        for b, sp in pose.items():
            e = {}
            if sp.get("t"):
                e["translation"] = to_roblox(sp["t"])
            if sp.get("r"):
                e["rotation_axis"] = to_roblox(sp["r"][0])
                e["rotation_degrees"] = sp["r"][1]
            out[b] = e
        lib["poses"][pname] = out
    return lib


def collision_json(cr):
    w, d, h = cr.collider["size_studs"]
    cx, cy = cr.collider_center_xy
    off = to_roblox((cx, cy, h / 2.0))
    top = h
    return {
        "asset_id": cr.asset_id,
        "authority": "server_collider_separate_from_visual_mesh",
        "pivot": "bottom_center",
        "forward_axis": "-Z",
        "dimensions_order_config": "width_depth_height",
        "collider": {
            "shape": "box",
            "size_studs_config": [w, d, h],
            "size_vector3_roblox": [w, h, d],
            "offset_from_pivot_roblox": off,
            "tags": ["FillCollider"],
            "can_collide": True,
            "anchor_after_settle": True,
        },
        "walkable_top": {
            "size_studs": cr.collider["walkable_top"],
            "height_studs": top,
            "center_roblox": to_roblox((cx, cy, top)),
            "marker": "safe_mint_footprint (affiché après stabilisation)",
        },
        "support_sockets_roblox": [to_roblox((cx + sx * w / 4, cy + sy * d / 4, top))
                                   for sx in (-1, 1) for sy in (-1, 1)] + [to_roblox((cx, cy, top))],
        "visual_mesh": {"can_collide": False, "can_query": False, "can_touch": False,
                        "follows_root_client_side": True, "anchored_weld_to_falling_root": False},
        "behavior": cr.behavior,
        "deformation_profile": "plush_soft",
        "notes": "Les grandes compressions précèdent l'activation de l'appui garanti ; le visuel déformé n'altère jamais ce collider.",
    }


def export(cr, arm, near, far, out_import):
    os.makedirs(out_import, exist_ok=True)
    base = os.path.join(out_import, cr.asset_id)
    apply_pose(arm, {})

    def sel(objs):
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]

    common = dict(export_format="GLB", use_selection=True, export_skins=True, export_animations=False,
                  export_yup=True, export_apply=False, export_influence_nb=4, export_all_influences=False,
                  export_def_bones=False, export_texcoords=True, export_normals=True, export_materials="EXPORT")
    sel([arm, near])
    bpy.ops.export_scene.gltf(filepath=base + ".glb", **common)
    sel([arm, far])
    bpy.ops.export_scene.gltf(filepath=base + "_lod1.glb", **common)
    sel([arm, near])
    bpy.ops.export_scene.fbx(filepath=base + ".fbx", use_selection=True, object_types={"ARMATURE", "MESH"},
                             add_leaf_bones=False, axis_forward="-Z", axis_up="Y", apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0, bake_anim=False,
                             path_mode="COPY", embed_textures=True, mesh_smooth_type="FACE",
                             use_armature_deform_only=False, primary_bone_axis="Y", secondary_bone_axis="X")
    return [base + ".glb", base + "_lod1.glb", base + ".fbx"]


def build(key):
    np.random.seed(SEED)
    cr = specs.CREATURES[key]()
    reset_scene()
    model_dir = os.path.join(ROOT, "assets", "source", "models", MODEL_DIRS[key])
    os.makedirs(model_dir, exist_ok=True)
    tex_dir = os.path.join(model_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    hi = build_highres(cr)
    paint_vertex_colors(hi, cr)
    hi_tris = tri_count(hi)
    near = make_lod(hi, f"{cr.label}_LOD0", NEAR_TRIS)
    far = make_lod(hi, f"{cr.label}_LOD1", FAR_TRIS)
    for ob in (near, far):
        unwrap(ob)
    hi_bake_material(hi)
    img0 = lod_material(near, cr.label, NEAR_TEX)
    img1 = lod_material(far, cr.label + "_far", FAR_TEX)
    bake(hi, near, img0, os.path.join(tex_dir, f"{cr.asset_id}_albedo_1024.png"))
    bake(hi, far, img1, os.path.join(tex_dir, f"{cr.asset_id}_albedo_256.png"))
    # la haute définition (~290 k triangles) n'est pas conservée dans le .blend : elle est régénérée
    # à l'identique par ce script (sortie vérifiée byte à byte), ce qui garde la source légère.
    hi_mesh = hi.data
    bpy.data.objects.remove(hi)
    bpy.data.meshes.remove(hi_mesh)

    arm, wstats = build_rig(cr, [near, far])
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    store_pose_actions(arm, cr)

    blend_path = os.path.join(model_dir, f"{cr.label}.blend")
    with open(os.path.join(model_dir, "collision.json"), "w", encoding="utf-8") as f:
        json.dump(collision_json(cr), f, ensure_ascii=False, indent=2)
    with open(os.path.join(model_dir, "pose_library.json"), "w", encoding="utf-8") as f:
        json.dump(pose_library(cr), f, ensure_ascii=False, indent=2)

    exports = export(cr, arm, near, far, os.path.join(ROOT, "assets", "import", "models"))
    # images empaquetées dans le .blend pour une source autonome
    for img in (img0, img1):
        img.pack()
    bpy.context.preferences.filepaths.save_version = 0  # pas de .blend1
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)

    info = {
        "asset_id": cr.asset_id,
        "blend": os.path.relpath(blend_path, ROOT),
        "exports": [os.path.relpath(p, ROOT) for p in exports],
        "highres_tris": hi_tris,
        "lod0_tris": tri_count(near),
        "lod1_tris": tri_count(far),
        "bones": ["Root"] + cr.belly_bone_names() + list(cr.secondary_bones.keys()),
        "weights": wstats,
        "materials_per_mesh": 1,
        "textures": [f"{cr.asset_id}_albedo_1024.png", f"{cr.asset_id}_albedo_256.png"],
        "voxel_size_studs": VOXEL,
        "seed": SEED,
        "blender_version": bpy.app.version_string,
    }
    with open(os.path.join(model_dir, "build_info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(json.dumps(info, ensure_ascii=False))
    return info


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    keys = list(specs.CREATURES) if which == "all" else [which]
    for k in keys:
        build(k)
