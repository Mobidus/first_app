"""Construit les 5 accessoires non-peluches de la famille Toy Overflow et la machine signature.

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/build_props_toy.py [all|toy_flat_duck|toy_train|...]

Assets : toy_flat_duck, toy_train, toy_drum, toy_domino, toy_shape_cube, machine_toy_spinner.

Conventions (docs/decisions/0003) : 1 unité Blender = 1 stud ; X = largeur, Y = profondeur, Z = hauteur ;
pivot bottom_center (origine au centre de l'enveloppe, au sol) ; avant Roblox (-Z) = +Y Blender. Les
dimensions, colliders et dessus jouables viennent de config/rooms.json (lu, jamais modifié).

Matières : un atlas partagé 1 024 px (toy_props_atlas_1024.png) découpé en cases de couleur 128 px ;
chaque face pointe sur le centre d'une case (UV « palette ») : couleurs nettes, aucune couture de texture,
un seul atlas pour toute la famille. Deux matériaux au plus par maillage : plastique brillant
(M_toy_gloss) et, pour la seule bulle de la machine, verre (M_toy_glass). Les détails (bords arrondis,
creux de domino, ouvertures du cube, roues, ressorts) sont modélisés.

LOD0 = géométrie détaillée (biseaux, segments) ; LOD1 = même dessin reconstruit avec moins de segments
(pas de décimation : les UV palette restent exactes).
Sorties : assets/source/models/toy/toy_props.blend (+ textures/, collision_toy_props.json, build_info),
assets/import/models/<id>.glb, <id>_lod1.glb, <id>.fbx.
Déterministe : aucune graine aléatoire.
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
from mathutils import Euler, Matrix, Vector  # noqa: E402

import plush_specs as specs  # noqa: E402  (superellipsoïdes partagées)

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MODEL_DIR = os.path.join(ROOT, "assets", "source", "models", "toy")
TEX_DIR = os.path.join(MODEL_DIR, "textures")
IMPORT_DIR = os.path.join(ROOT, "assets", "import", "models")
ATLAS_NAME = "toy_props_atlas_1024.png"
ATLAS_SIZE = 1024
CELLS = 8  # 8 x 8 cases de 128 px

# ---------------------------------------------------------------------------
# Palette (sRGB). Couleurs fonctionnelles (menthe #39E68B, corail #FF684B, cyan des balises)
# évitées sur les corps : elles restent aux balises de dessus (docs/04 §2).
# ---------------------------------------------------------------------------
PALETTE = [
    ("navy", "#203055"), ("cream", "#FFF5DF"), ("white", "#FBFAF6"), ("yellow", "#FFE14D"),
    ("duck_yellow", "#FFD23A"), ("duck_shade", "#F4B71F"), ("orange", "#FF8A3D"), ("orange_dark", "#E86A24"),
    ("blush", "#FF9AC8"), ("pink", "#FF4CB8"), ("pink_light", "#FF8FD2"), ("pink_dark", "#D6309A"),
    ("violet", "#8855FF"), ("violet_dark", "#6A3BD9"), ("lavender", "#B9A4EE"), ("lavender_light", "#D8CCF8"),
    ("lavender_dark", "#9C84E3"), ("teal", "#2ACBC7"), ("teal_dark", "#1FA9A6"), ("window", "#B9ECFA"),
    ("silver", "#CBD3E3"), ("glass", "#DFF7FF"), ("sky", "#5BC8F5"), ("navy_soft", "#34477A"),
]
PAL_INDEX = {n: i for i, (n, _h) in enumerate(PALETTE)}


def hex_to_srgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]


def cell_uv(name):
    i = PAL_INDEX[name]
    c, r = i % CELLS, i // CELLS
    return ((c + 0.5) / CELLS, 1.0 - (r + 0.5) / CELLS)


# ---------------------------------------------------------------------------
# Scène, atlas, matériaux
# ---------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    return sc


def make_atlas():
    os.makedirs(TEX_DIR, exist_ok=True)
    px = np.ones((ATLAS_SIZE, ATLAS_SIZE, 4), dtype=np.float32)
    step = ATLAS_SIZE // CELLS
    for name, hx in PALETTE:
        i = PAL_INDEX[name]
        c, r = i % CELLS, i // CELLS
        rgb = hex_to_srgb(hx)
        y0 = ATLAS_SIZE - (r + 1) * step  # pixels Blender : origine en bas
        px[y0:y0 + step, c * step:(c + 1) * step, :3] = rgb
    img = bpy.data.images.new("toy_props_atlas", ATLAS_SIZE, ATLAS_SIZE, alpha=False)
    img.colorspace_settings.name = "sRGB"
    # Les pixels d'une image « sRGB » sont stockés tels quels (valeurs sRGB) en 8 bits.
    img.pixels.foreach_set(px.ravel())
    path = os.path.join(TEX_DIR, ATLAS_NAME)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return img


def make_materials(img):
    mats = {}
    for key, rough, spec in (("gloss", 0.24, 0.55), ("glass", 0.05, 0.6)):
        m = bpy.data.materials.new(f"M_toy_{key}")
        m.use_nodes = True
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        if key == "glass":
            bsdf.inputs["Base Color"].default_value = (*[c ** 2.2 for c in hex_to_srgb("#DFF7FF")], 1.0)
            bsdf.inputs["Alpha"].default_value = 0.32
            if hasattr(m, "surface_render_method"):
                m.surface_render_method = "BLENDED"
            if hasattr(m, "blend_method"):
                m.blend_method = "BLEND"
        else:
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = img
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = rough if key == "glass" else 0.32
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = spec
        if "Coat Weight" in bsdf.inputs and key == "gloss":
            bsdf.inputs["Coat Weight"].default_value = 0.12
            bsdf.inputs["Coat Roughness"].default_value = 0.08
        mats[key] = m
    return mats


# ---------------------------------------------------------------------------
# Primitives bmesh (coordonnées locales, studs)
# ---------------------------------------------------------------------------
def bm_box(size, bevel=0.0, bseg=2, vbevel=None):
    """Boîte biseautée. vbevel : rayon distinct (petit) des 4 arêtes verticales, pour les plateaux dont
    l'empreinte jouable va jusqu'aux coins : arêtes du dessus arrondies (bevel), coins en plan presque vifs."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if vbevel is None:
        if bevel > 0 and bseg > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=bseg, profile=0.5,
                            affect="EDGES", clamp_overlap=True)
        return bm
    horiz = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6]
    if bevel > 0 and bseg > 0:
        bmesh.ops.bevel(bm, geom=horiz, offset=bevel, segments=bseg, profile=0.5, affect="EDGES", clamp_overlap=True)
    if vbevel > 0 and bseg > 0:
        vert = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(80)
                and abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-6]
        bmesh.ops.bevel(bm, geom=vert, offset=vbevel, segments=1, profile=0.5, affect="EDGES", clamp_overlap=True)
    return bm


def bm_cyl(r1, h, seg, r2=None, bevel=0.0, bseg=1):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r1,
                          radius2=r1 if r2 is None else r2, depth=h)
    if bevel > 0 and bseg > 0:
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(40)]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=bseg, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return bm


def bm_sphere(radii, u, v):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    bmesh.ops.scale(bm, vec=Vector(radii), verts=bm.verts)
    return bm


def bm_from_pydata(verts, faces):
    bm = bmesh.new()
    vs = [bm.verts.new(tuple(map(float, v))) for v in verts]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bm.normal_update()
    return bm


def bm_super(radii, eh, ev, u, v):
    pr = specs.Prim("s", (0, 0, 0), radii, eh=eh, ev=ev)
    verts, faces = pr.surface_points(seg=u, rings=v)
    return bm_from_pydata(verts, faces)


def bm_lathe(profile, seg, closed=False):
    """Révolution d'un profil (r, z) autour de Z. r == 0 -> pôle. closed : profil fermé (anneau)."""
    verts, faces, rings = [], [], []
    for (r, z) in profile:
        if r <= 1e-6:
            rings.append([len(verts)])
            verts.append((0.0, 0.0, z))
        else:
            ring = []
            for s in range(seg):
                a = 2 * math.pi * s / seg
                ring.append(len(verts))
                verts.append((r * math.cos(a), r * math.sin(a), z))
            rings.append(ring)
    pairs = list(zip(rings[:-1], rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for ra, rb in pairs:
        if len(ra) == 1 and len(rb) == 1:
            continue
        if len(ra) == 1:
            for s in range(seg):
                faces.append((ra[0], rb[s], rb[(s + 1) % seg]))
        elif len(rb) == 1:
            for s in range(seg):
                faces.append((ra[s], rb[0], ra[(s + 1) % seg]))
        else:
            for s in range(seg):
                faces.append((ra[s], ra[(s + 1) % seg], rb[(s + 1) % seg], rb[s]))
    bm = bm_from_pydata(verts, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def bm_torus(R, r, useg, vseg):
    prof = [(R + r * math.cos(2 * math.pi * k / vseg), r * math.sin(2 * math.pi * k / vseg)) for k in range(vseg)]
    return bm_lathe(prof, useg, closed=True)


def catmull(points, n):
    """Échantillonne une Catmull-Rom (n points) passant par les points donnés."""
    P = [np.array(p, float) for p in points]
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    segs = len(P) - 3
    out = []
    for k in range(n):
        u = k / (n - 1) * segs
        i = min(int(u), segs - 1)
        t = u - i
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return np.array(out)


def bm_tube(path, radii, sides, caps=True):
    """Tube balayé le long d'un chemin (repères à transport parallèle)."""
    path = np.asarray(path, float)
    n = len(path)
    radii = np.broadcast_to(np.asarray(radii, float), (n,))
    T = np.gradient(path, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    ref = np.array([0, 0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0, 0])
    Nn = np.cross(T[0], ref)
    Nn /= np.linalg.norm(Nn)
    verts, faces = [], []
    for i in range(n):
        if i > 0:
            Nn = Nn - T[i] * np.dot(Nn, T[i])
            Nn /= np.linalg.norm(Nn)
        B = np.cross(T[i], Nn)
        for s in range(sides):
            a = 2 * math.pi * s / sides
            verts.append(path[i] + radii[i] * (math.cos(a) * Nn + math.sin(a) * B))
    for i in range(n - 1):
        for s in range(sides):
            a, b = i * sides + s, i * sides + (s + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    if caps:
        faces.append(tuple(reversed(range(sides))))
        faces.append(tuple((n - 1) * sides + s for s in range(sides)))
    bm = bm_from_pydata(verts, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def bm_prism(poly, z0, z1):
    """Polygone 2D (x, y) extrudé entre z0 et z1."""
    n = len(poly)
    verts = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    bm = bm_from_pydata(verts, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def bm_rounded_slab(hx, hy, rc, h, cseg, bevel=0.0, bseg=0):
    """Rectangle à coins arrondis (plan), extrudé sur h (z de 0 à h), arêtes haut/bas biseautées."""
    poly = []
    for (cx, cy, a0) in ((hx - rc, hy - rc, 0), (-hx + rc, hy - rc, 90), (-hx + rc, -hy + rc, 180), (hx - rc, -hy + rc, 270)):
        for k in range(cseg + 1):
            a = math.radians(a0 + 90.0 * k / cseg)
            poly.append((cx + rc * math.cos(a), cy + rc * math.sin(a)))
    bm = bm_prism(poly, 0.0, h)
    if bevel > 0 and bseg > 0:
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(60)]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=bseg, profile=0.5, affect="EDGES", clamp_overlap=True)
    return bm


def helix(radius, z0, z1, turns, per_turn):
    n = int(turns * per_turn) + 1
    return [(radius * math.cos(2 * math.pi * turns * k / (n - 1)), radius * math.sin(2 * math.pi * turns * k / (n - 1)),
             z0 + (z1 - z0) * k / (n - 1)) for k in range(n)]


# ---------------------------------------------------------------------------
# Constructeur d'asset
# ---------------------------------------------------------------------------
class Builder:
    def __init__(self, lod, mats, prefix):
        self.lod = lod
        self.mats = mats
        self.prefix = prefix
        self.parts = []

    def s(self, a, b):
        return a if self.lod == 0 else b

    def add(self, name, bm, color, mat="gloss", loc=(0, 0, 0), rot=(0, 0, 0), face_color=None, keep=True):
        uv = bm.loops.layers.uv.verify()
        for f in bm.faces:
            c = face_color(f) if face_color else color
            u, v = cell_uv(c)
            for lp in f.loops:
                lp[uv].uv = (u, v)
            f.material_index = 0
        me = bpy.data.meshes.new(f"{self.prefix}_{name}")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(f"{self.prefix}_{name}", me)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = Euler([math.radians(a) for a in rot], "XYZ")
        me.materials.append(self.mats[mat])
        if keep:
            self.parts.append(ob)
        return ob


def activate(obj, others=()):
    bpy.ops.object.select_all(action="DESELECT")
    for o in others:
        o.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def boolean(target, cutter, op="DIFFERENCE"):
    activate(target)
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation = op
    m.object = cutter
    m.solver = "EXACT"
    if hasattr(m, "material_mode"):
        m.material_mode = "TRANSFER"
    bpy.ops.object.modifier_apply(modifier=m.name)
    me = cutter.data
    bpy.data.objects.remove(cutter)
    bpy.data.meshes.remove(me)


def join(parts, name, smooth_angle=46.0):
    activate(parts[0], parts[1:])
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # sol : aucun sommet sous z = 0 (pivot bottom_center)
    me = ob.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    co[:, 2] = np.maximum(co[:, 2], 0.0)
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(me)
    bm.free()
    activate(ob)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(smooth_angle), keep_sharp_edges=True)
    # matériaux dédoublonnés (un slot par matériau réel)
    used = []
    for slot in ob.material_slots:
        if slot.material and slot.material not in used:
            used.append(slot.material)
    remap = [used.index(s.material) for s in ob.material_slots]
    idx = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("material_index", idx)
    idx = np.array([remap[i] for i in idx], dtype=np.int32)
    me.materials.clear()
    for m in used:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", idx)
    me.update()
    return ob


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


# ---------------------------------------------------------------------------
# 1. Canard à dos plat (14 x 10 x 8, collider 8 x 8 x 6 centré x = -1)
# ---------------------------------------------------------------------------
DUCK_COLLIDER_CENTER = (-1.0, 0.0)


def build_duck(B):
    s = B.s
    # coque : superellipsoïde (ventre de canard de bain), tronquée au sol
    B.add("body", bm_super((5.5, 4.3, 3.1), 2.3, 2.2, s(24, 10), s(12, 6)), "duck_yellow", loc=(-1.35, 0, 2.6))
    # queue relevée vers l'arrière (hors empreinte : x < -5,1)
    B.add("tail", bm_sphere((0.9, 1.4, 1.75), s(14, 8), s(8, 4)), "duck_yellow", loc=(-5.78, 0, 5.05), rot=(0, -40, 0))
    # ailes + plume de bout d'aile (débordent sur les flancs : enveloppe 10 de profondeur)
    for sy in (1, -1):
        B.add(f"wing_{sy}", bm_sphere((2.55, 0.55, 1.45), s(12, 8), s(7, 4)), "duck_shade",
              loc=(-1.6, sy * 4.42, 3.45), rot=(sy * 10, 15, 0))
        if B.lod == 0:
            B.add(f"feather_{sy}", bm_sphere((1.05, 0.48, 0.62), 8, 5), "duck_shade",
                  loc=(-3.7, sy * 4.4, 4.05), rot=(sy * 10, 32, 0))
    # selle de jouet porteur : coussin orange à rebord, plateau crème plat à z = 6
    # selle-coussin à coins arrondis (plan) : couvre l'empreinte 8 x 8 + 0,4 de marge
    B.add("saddle", bm_rounded_slab(4.42, 4.42, 1.0, 0.8, s(5, 2), 0.26, s(2, 1)), "pink",
          loc=(*DUCK_COLLIDER_CENTER, 5.2))
    B.add("saddle_top", bm_rounded_slab(3.95, 3.95, 0.7, 0.1, s(4, 2), 0.03, s(1, 0)), "pink_light",
          loc=(*DUCK_COLLIDER_CENTER, 5.93))
    # cou et tête (tout ce qui dépasse z = 6,25 reste à x > 3, hors empreinte)
    B.add("neck", bm_sphere((1.45, 1.75, 1.65), s(12, 8), s(7, 4)), "duck_yellow", loc=(3.85, 0, 4.45))
    hc = Vector((4.85, 0, 6.1))
    B.add("head", bm_sphere((1.8, 1.8, 1.8), s(20, 9), s(11, 5)), "duck_yellow", loc=hc)
    B.add("beak_top", bm_sphere((0.64, 0.95, 0.34), s(12, 8), s(7, 4)), "orange", loc=(6.47, 0, 5.8))
    B.add("beak_low", bm_sphere((0.5, 0.76, 0.2), s(12, 6), s(6, 3)), "orange_dark", loc=(6.36, 0, 5.47))
    if B.lod == 0:  # mèche sur le crâne (reste < 8)
        B.add("tuft", bm_sphere((0.5, 0.18, 0.26), 8, 4), "duck_shade", loc=(4.55, 0, 7.72), rot=(0, -25, 0))
    for sy in (1, -1):
        d = Vector((0.58, sy * 0.66, 0.46)).normalized()
        B.add(f"eye_{sy}", bm_sphere((0.3, 0.3, 0.3), s(10, 5), s(6, 3)), "navy", loc=hc + d * 1.68)
        if B.lod == 0:
            B.add(f"eye_hi_{sy}", bm_sphere((0.1, 0.1, 0.1), 6, 4), "white", loc=hc + d * 1.94 + Vector((0.04, 0, 0.1)))
            d2 = Vector((0.5, sy * 0.85, -0.05)).normalized()
            B.add(f"blush_{sy}", bm_sphere((0.34, 0.1, 0.22), 8, 4), "blush", loc=hc + d2 * 1.76,
                  rot=(0, 0, sy * 30))
        B.add(f"foot_{sy}", bm_sphere((1.0, 0.72, 0.17), s(8, 6), s(5, 3)), "orange", loc=(2.35, sy * 1.55, 0.15),
              rot=(0, 0, sy * 12))


# ---------------------------------------------------------------------------
# 2. Petit train (16 x 8 x 5, collider = enveloppe, toit plat à z = 5)
# ---------------------------------------------------------------------------
def build_train(B):
    s = B.s
    B.add("roof", bm_box((16.0, 8.0, 0.45), 0.15, s(2, 1), vbevel=0.0), "teal_dark", loc=(0, 0, 4.775))
    if B.lod == 0:
        for sy in (1, -1):
            B.add(f"roof_stripe_{sy}", bm_box((15.0, 0.34, 0.04), 0.0, 0), "cream", loc=(0, sy * 3.42, 5.0))
    # cheminée raccourcie : coupée au ras du toit (dessus jouable plat), dôme jaune affleurant
    B.add("chimney_ring", bm_cyl(0.95, 0.1, s(18, 8)), "yellow", loc=(5.6, 0, 4.97))
    B.add("chimney_mouth", bm_cyl(0.62, 0.1, s(16, 6)), "navy", loc=(5.6, 0, 4.98))
    if B.lod == 0:
        B.add("dome", bm_cyl(0.7, 0.1, 16), "yellow", loc=(3.0, 0, 4.97))
    # caisse
    B.add("body", bm_box((15.2, 7.1, 3.25), 0.3, s(2, 1)), "teal", loc=(-0.1, 0, 2.95))
    for x in (0.6, 3.0, 5.4):  # cerclages de chaudière
        B.add(f"band_{x}", bm_box((0.28, 7.3, 3.36), 0.0, 0), "yellow", loc=(x, 0, 2.97))
    # cabine : fenêtres latérales et arrière
    for sy in (1, -1):
        for x in (-6.15, -4.05):
            if B.lod == 0:
                B.add(f"wframe_{sy}_{x}", bm_box((1.75, 0.12, 1.5), 0.0, 0), "navy", loc=(x, sy * 3.56, 3.35))
            B.add(f"wglass_{sy}_{x}", bm_box((1.45, 0.12, 1.2), 0.0, 0), "window", loc=(x, sy * 3.6, 3.35))
        if B.lod == 0:
            B.add(f"rframe_{sy}", bm_box((0.12, 1.6, 1.4), 0.0, 0), "navy", loc=(-7.71, sy * 1.7, 3.35))
        B.add(f"rglass_{sy}", bm_box((0.12, 1.3, 1.1), 0.0, 0), "window", loc=(-7.75, sy * 1.7, 3.35))
    # face avant : porte de boîte à fumée, cerclage, phare
    B.add("smokebox", bm_cyl(1.7, 0.2, s(20, 10), bevel=0.05, bseg=s(1, 0)), "navy", loc=(7.55, 0, 2.85), rot=(0, 90, 0))
    if B.lod == 0:
        B.add("smokebox_ring", bm_torus(1.72, 0.13, 20, 4), "yellow", loc=(7.62, 0, 2.85), rot=(0, 90, 0))
        B.add("door_handle", bm_sphere((0.24, 0.24, 0.24), 8, 5), "yellow", loc=(7.72, 0.0, 2.85))
    B.add("lamp", bm_cyl(0.45, 0.32, s(14, 6)), "yellow", loc=(7.66, 0, 4.0), rot=(0, 90, 0))
    if B.lod == 0:
        B.add("lamp_lens", bm_sphere((0.18, 0.34, 0.34), 10, 6), "cream", loc=(7.82, 0, 4.0))
    # châssis, chasse-pierres, tampons
    B.add("frame", bm_box((15.4, 6.2, 0.6), 0.08, s(1, 0)), "navy", loc=(-0.2, 0, 1.05))
    wedge = bm_prism([(6.95, 0.18), (7.98, 0.18), (7.98, 0.45), (7.1, 1.45), (6.95, 1.45)], -2.6, 2.6)
    B.add("cowcatcher", wedge, "pink_dark", rot=(90, 0, 0))
    for sy in (1, -1):
        B.add(f"buffer_{sy}", bm_cyl(0.3, 0.42, s(10, 5)), "navy", loc=(-7.85, sy * 2.3, 1.75), rot=(0, 90, 0))
        if B.lod == 0:
            B.add(f"buffer_cap_{sy}", bm_cyl(0.42, 0.1, 12, bevel=0.03, bseg=1), "yellow",
                  loc=(-8.0, sy * 2.3, 1.75), rot=(0, 90, 0))
    # roues (repère de mouvement) : 4 par côté, moyeux, bielle d'accouplement
    for sy in (1, -1):
        for x in (-5.6, -2.0, 1.6, 5.2):
            B.add(f"wheel_{sy}_{x}", bm_cyl(1.18, 0.42, s(16, 8), bevel=0.07, bseg=s(1, 0)), "pink",
                  loc=(x, sy * 3.62, 1.18), rot=(90, 0, 0))
            if B.lod == 0:
                B.add(f"hub_{sy}_{x}", bm_cyl(0.5, 0.12, 8), "navy", loc=(x, sy * 3.86, 1.18), rot=(90, 0, 0))
                B.add(f"cap_{sy}_{x}", bm_cyl(0.22, 0.08, 8), "yellow", loc=(x, sy * 3.94, 1.18), rot=(90, 0, 0))
        B.add(f"rod_{sy}", bm_box((11.2, 0.1, 0.22), 0.03, s(1, 0)), "silver", loc=(-0.2, sy * 3.95, 1.55))


# ---------------------------------------------------------------------------
# 3. Tambour (10 x 10 x 5, collider 8 x 8 x 5) : carré ressort de 8 studs
# ---------------------------------------------------------------------------
def build_drum(B):
    s = B.s
    seg = s(32, 12)
    B.add("shell", bm_lathe([(4.5, 0.4), (4.62, 1.8), (4.5, 3.2)], seg), "pink")
    rim = lambda z0, z1: [(4.38, z0), (4.85, z0), (4.95, z0 + 0.12), (4.95, z1 - 0.12), (4.85, z1), (4.38, z1)]
    rim1 = lambda z0, z1: [(4.38, z0), (4.95, z0), (4.95, z1), (4.38, z1)]
    B.add("rim_low", bm_lathe(s(rim(0.0, 0.62), rim1(0.0, 0.62)), seg, closed=True), "violet")
    B.add("rim_top", bm_lathe(s(rim(2.95, 3.6), rim1(2.95, 3.6)), seg, closed=True), "violet")
    B.add("skin", bm_cyl(4.45, 0.12, seg), "yellow", loc=(0, 0, 3.48))
    if B.lod == 0:
        n = 10
        for k in range(n):
            a0 = 2 * math.pi * k / n
            a1 = a0 + math.pi / n
            a2 = a0 + 2 * math.pi / n
            pb0 = (4.8 * math.cos(a0), 4.8 * math.sin(a0), 0.62)
            pt = (4.8 * math.cos(a1), 4.8 * math.sin(a1), 2.95)
            pb1 = (4.8 * math.cos(a2), 4.8 * math.sin(a2), 0.62)
            B.add(f"cord_a{k}", bm_tube([pb0, pt], 0.085, 6), "cream")
            B.add(f"cord_b{k}", bm_tube([pt, pb1], 0.085, 6), "cream")
            for (p, zz) in ((pb0, 0.45), (pt, 3.12)):
                ang = math.degrees(math.atan2(p[1], p[0]))
                B.add(f"lug_{k}_{zz}", bm_box((0.22, 0.42, 0.34), 0.0, 0), "yellow",
                      loc=(5.0 * p[0] / 4.8 * 0.985, 5.0 * p[1] / 4.8 * 0.985, zz), rot=(0, 0, ang))
    # ressorts (repère de rebond) entre la peau et le carré
    for sx in (1, -1):
        for sy in (1, -1):
            c = (sx * 2.75, sy * 2.75)
            if B.lod == 0:
                path = [(c[0] + x, c[1] + y, z) for (x, y, z) in helix(0.5, 3.62, 4.62, 2.75, 8)]
                B.add(f"spring_{sx}_{sy}", bm_tube(path, 0.1, 5, caps=True), "silver")
                B.add(f"spring_base_{sx}_{sy}", bm_cyl(0.62, 0.08, 12), "silver", loc=(c[0], c[1], 3.57))
            else:
                B.add(f"spring_{sx}_{sy}", bm_cyl(0.45, 1.1, 6), "silver", loc=(c[0], c[1], 4.1))
    # carré ressort 8 x 8 : cadre bleu nuit + tapis jaune, dessus à z = 5
    B.add("pad", bm_box((8.24, 8.24, 0.36), 0.12, s(2, 0)), "navy", loc=(0, 0, 4.82))
    B.add("pad_mat", bm_box((7.5, 7.5, 0.06), 0.02, s(1, 0)), "yellow", loc=(0, 0, 4.99))
    if B.lod == 0:  # liseré crème du tapis (couture de trampoline)
        for sx in (1, -1):
            B.add(f"mat_line_x{sx}", bm_box((0.08, 6.8, 0.02), 0.0, 0), "cream", loc=(sx * 3.4, 0, 5.025))
            B.add(f"mat_line_y{sx}", bm_box((6.8, 0.08, 0.02), 0.0, 0), "cream", loc=(0, sx * 3.4, 5.025))


# ---------------------------------------------------------------------------
# 4. Domino couché (12 x 6 x 3)
# ---------------------------------------------------------------------------
DOMINO_PIPS = [(-4.6, 1.6), (-4.6, -1.6), (-1.4, 1.6), (-1.4, -1.6), (-3.0, 0.0),  # cinq
               (1.4, -1.6), (3.0, 0.0), (4.6, 1.6)]                                # trois


def build_domino(B):
    s = B.s
    body = B.add("body", bm_box((12.0, 6.0, 3.0), 0.18, s(3, 1), vbevel=0.0), "lavender", loc=(0, 0, 1.5))
    if B.lod == 0:
        # creux de points : une sphère par point, retranchée (bord blanc net, fond blanc)
        cutters = [B.add(f"pip_cut_{i}", bm_sphere((0.52, 0.52, 0.52), 18, 9), "white", loc=(x, y, 3.36), keep=False)
                   for i, (x, y) in enumerate(DOMINO_PIPS)]
        activate(cutters[0], cutters[1:])
        bpy.ops.object.join()
        boolean(body, bpy.context.view_layer.objects.active)
    else:
        for i, (x, y) in enumerate(DOMINO_PIPS):
            B.add(f"pip_{i}", bm_cyl(0.46, 0.04, 8), "white", loc=(x, y, 3.0))
    B.add("divider", bm_box((0.24, 5.3, 0.04), 0.0, 0), "navy", loc=(0, 0, 3.0))
    B.add("pin", bm_cyl(0.3, 0.06, s(16, 8), bevel=0.02, bseg=s(1, 0)), "silver", loc=(0, 0, 3.0))
    if B.lod == 0:  # filet gravé sur le pourtour (lisibilité de la tranche)
        for sy in (1, -1):
            B.add(f"edge_line_{sy}", bm_box((11.2, 0.04, 0.08), 0.0, 0), "lavender_dark", loc=(0, sy * 3.0, 1.5))
        for sx in (1, -1):
            B.add(f"edge_line_x{sx}", bm_box((0.04, 5.2, 0.08), 0.0, 0), "lavender_dark", loc=(sx * 6.0, 0, 1.5))


# ---------------------------------------------------------------------------
# 5. Cube à formes (10 x 10 x 7) : ouvertures sur les côtés, dessus fermé
# ---------------------------------------------------------------------------
def shape_poly(kind, n_circle=24):
    if kind == "circle":
        return [(1.1 * math.cos(2 * math.pi * k / n_circle), 1.1 * math.sin(2 * math.pi * k / n_circle)) for k in range(n_circle)]
    if kind == "square":
        return [(-0.95, -0.95), (0.95, -0.95), (0.95, 0.95), (-0.95, 0.95)]
    if kind == "triangle":
        return [(1.3 * math.cos(math.radians(90 + 120 * k)), 1.3 * math.sin(math.radians(90 + 120 * k)) - 0.15) for k in range(3)]
    if kind == "star":
        return [((1.35 if k % 2 == 0 else 0.6) * math.cos(math.radians(90 + 36 * k)),
                 (1.35 if k % 2 == 0 else 0.6) * math.sin(math.radians(90 + 36 * k)) - 0.05) for k in range(10)]
    if kind == "hexagon":
        return [(1.15 * math.cos(math.radians(60 * k)), 1.15 * math.sin(math.radians(60 * k))) for k in range(6)]
    if kind == "heart":
        pts = []
        for k in range(28):
            t = 2 * math.pi * k / 28
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((x * 0.072, y * 0.072 + 0.12))
        return pts[::-1] if _area(pts) < 0 else pts
    if kind == "cross":
        a, b = 0.38, 1.12
        return [(-a, -b), (a, -b), (a, -a), (b, -a), (b, a), (a, a), (a, b), (-a, b), (-a, a), (-b, a), (-b, -a), (-a, -a)]
    if kind == "arch":
        nn = max(n_circle // 2, 5)
        pts = [(1.15 * math.cos(math.pi * k / nn), 1.15 * math.sin(math.pi * k / nn) - 0.45) for k in range(nn + 1)]
        return pts + [(-1.15, -0.85), (1.15, -0.85)]
    raise KeyError(kind)


def _area(pts):
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))


CUBE_FACES = [  # (rotation Z en degrés, [(forme, couleur des parois)])
    (0, [("circle", "yellow"), ("triangle", "pink")]),      # avant +Y
    (-90, [("square", "orange"), ("star", "yellow")]),     # droite +X
    (180, [("hexagon", "pink"), ("heart", "orange")]),     # arrière -Y
    (90, [("cross", "yellow"), ("arch", "pink")]),         # gauche -X
]


def build_shape_cube(B):
    s = B.s
    B.add("plinth", bm_box((10.0, 10.0, 0.55), 0.12, s(2, 1)), "violet", loc=(0, 0, 0.275))
    body = B.add("body", bm_box((9.3, 9.3, 6.0), 0.1, s(1, 0)), "lavender", loc=(0, 0, 3.5))
    for sx in (1, -1):
        for sy in (1, -1):
            B.add(f"post_{sx}_{sy}", bm_cyl(0.62, 6.0, s(18, 8)), "violet", loc=(sx * 4.4, sy * 4.4, 3.5))
    B.add("lid", bm_box((10.0, 10.0, 0.55), 0.15, s(3, 1), vbevel=0.0), "violet", loc=(0, 0, 6.725))
    B.add("lid_plate", bm_box((8.5, 8.5, 0.05), 0.02, s(1, 0)), "lavender_light", loc=(0, 0, 7.0))
    face_d = 4.65
    for rotz, shapes in CUBE_FACES:
        R = Matrix.Rotation(math.radians(rotz), 3, "Z")
        n = R @ Vector((0, 1, 0))
        t = R @ Vector((1, 0, 0))
        for k, (kind, wall) in enumerate(shapes):
            u = (-2.1, 2.1)[k]
            poly = shape_poly(kind, s(24, 10))
            loc = n * face_d + t * u + Vector((0, 0, 3.55))
            if B.lod == 0:
                cut = bm_prism(poly, -0.35, 0.45)
                deep = lambda f, w=wall: "navy" if f.normal.z > 0.5 else (w if f.normal.z > -0.5 else w)
                c = B.add(f"cut_{kind}", cut, wall, loc=loc, rot=(90, 0, rotz), face_color=deep, keep=False)
                boolean(body, c)
            else:
                B.add(f"hole_{kind}", bm_prism(poly, -0.02, 0.0), "navy", loc=loc, rot=(90, 0, rotz))


# ---------------------------------------------------------------------------
# 6. Machine signature : Toupie Trieuse (24 x 24 x 18), suspendue
# ---------------------------------------------------------------------------
SPIN_PROFILE = [(0.0, 0.0), (0.27, 0.2), (0.68, 0.75), (1.44, 1.6), (3.24, 3.3), (5.58, 5.0), (7.74, 6.2), (9.09, 7.0),
                (9.54, 7.8), (9.63, 8.7), (9.54, 9.7), (9.09, 10.6), (8.1, 11.4), (6.48, 12.1), (4.5, 12.6),
                (2.34, 12.9), (0.0, 13.0)]


def profile_r(z):
    zs = [p[1] for p in SPIN_PROFILE]
    rs = [p[0] for p in SPIN_PROFILE]
    return float(np.interp(z, zs, rs))


def build_machine(B):
    """Retourne trois groupes de pièces : support fixe, toupie tournante (axe Z), trompes."""
    s = B.s
    groups = {"Mount": [], "Spinner": [], "Trunks": []}

    def add(group, *a, **k):
        ob = B.add(*a, **k)
        groups[group].append(ob)
        B.parts.remove(ob)
        return ob

    # support de plafond fixe
    add("Mount", "plate", bm_cyl(2.6, 0.45, s(28, 8), bevel=0.1, bseg=s(2, 0)), "violet_dark", loc=(0, 0, 17.775))
    add("Mount", "rod", bm_cyl(0.38, 2.1, s(12, 5)), "navy", loc=(0, 0, 16.55))
    if B.lod == 0:
        add("Mount", "collar", bm_cyl(0.62, 0.35, 14, bevel=0.06, bseg=1), "yellow", loc=(0, 0, 17.4))

    # corps de toupie : rayures torsadées rose / rose clair, pointe bleu nuit
    seg = s(48, 9)
    prof = SPIN_PROFILE if B.lod == 0 else [SPIN_PROFILE[i] for i in (0, 2, 4, 6, 8, 9, 10, 12, 14, 16)]

    def stripe(f):
        c = f.calc_center_median()
        if c.z < 0.9:
            return "navy"
        if c.z > 12.75:
            return "pink_light"
        a = math.atan2(c.y, c.x) + math.pi / 12
        return "pink" if int(math.floor(a / (2 * math.pi / 12))) % 2 == 0 else "pink_light"
    add("Spinner", "body", bm_lathe(prof, seg), "pink", face_color=stripe if B.lod == 0 else None)
    # anneaux jaunes
    for z in (5.6, 11.4):
        add("Spinner", f"ring_{z}", bm_torus(profile_r(z) + 0.12, 0.42, s(44, 10), s(6, 3)), "yellow", loc=(0, 0, z))
    # ampoules sur l'anneau haut
    if B.lod == 0:
        for k in range(12):
            a = 2 * math.pi * (k + 0.5) / 12
            r = profile_r(11.4) + 0.12
            add("Spinner", f"bulb_{k}", bm_sphere((0.3, 0.3, 0.3), 8, 4), "cream",
                loc=(r * math.cos(a), r * math.sin(a), 11.4 + 0.5))
    # manche et bouton (liaison au support)
    add("Spinner", "stem", bm_cyl(1.0, 1.7, s(18, 6), bevel=0.08, bseg=s(1, 0)), "pink_dark", loc=(0, 0, 13.6))
    add("Spinner", "knob", bm_sphere((1.15, 1.15, 0.95), s(18, 6), s(9, 4)), "yellow", loc=(0, 0, 14.75))
    # grande fenêtre centrale (avant +Y) : bulle de verre, cadre jaune, jouets colorés à l'intérieur
    zc, yc = 8.5, 9.3
    if B.lod == 0:
        add("Spinner", "window_frame", bm_torus(2.62, 0.34, 28, 6), "yellow", loc=(0, yc + 0.32, zc), rot=(90, 0, 0))
    add("Spinner", "window_back", bm_cyl(2.55, 0.1, s(28, 10)), "violet_dark", loc=(0, yc + 0.15, zc), rot=(90, 0, 0))
    add("Spinner", "bubble", bm_sphere((2.55, 2.45, 2.55), s(24, 10), s(12, 5)), "glass", mat="glass", loc=(0, yc, zc))
    if B.lod == 0:
        balls = [(-1.05, 10.6, 7.45, 0.66, "yellow"), (0.4, 10.9, 7.3, 0.6, "sky"), (1.4, 10.55, 7.95, 0.62, "violet"),
                 (-0.35, 10.75, 8.7, 0.56, "orange"), (0.95, 10.8, 9.2, 0.5, "white"), (-1.35, 10.5, 9.2, 0.48, "pink_dark"),
                 (0.2, 10.4, 10.0, 0.45, "duck_yellow")]
        for i, (x, y, z, r, c) in enumerate(balls):
            add("Spinner", f"ball_{i}", bm_sphere((r, r, r), 10, 6), c, loc=(x, y, z))

    # trois trompes violettes pendantes (avant-gauche, avant-droite, arrière), manchettes et pavillons jaunes
    for k, adeg in enumerate((0, 180, 270)):
        a = math.radians(adeg)
        rz = [(8.7, 10.6), (9.9, 11.55), (11.05, 10.9), (11.3, 9.3), (11.15, 7.7), (10.95, 6.55)]
        pts = [(r * math.cos(a), r * math.sin(a), z) for r, z in rz]
        path = catmull(pts, s(22, 6))
        radii = np.interp(np.linspace(0, 1, len(path)), [0, 0.3, 1], [0.95, 0.82, 0.72])
        add("Trunks", f"trunk_{k}", bm_tube(path, radii, s(10, 5), caps=False), "violet")
        if B.lod == 0:
            for t in (0.35, 0.66):
                i = int(round(t * (len(path) - 1)))
                cuff = path[max(i - 1, 0):i + 2]
                add("Trunks", f"cuff_{k}_{t}", bm_tube(cuff, float(np.interp(t, [0, 0.3, 1], [0.95, 0.82, 0.72])) + 0.1, 10),
                    "yellow")
        # pavillon évasé au bout, orienté selon la tangente
        tan = Vector(path[-1] - path[-2]).normalized()
        q = tan.to_track_quat("Z", "Y")
        add("Trunks", f"mouth_{k}", bm_cyl(0.74, 0.75, s(16, 6), r2=1.15), "yellow", loc=Vector(path[-1]) + tan * 0.3,
            rot=tuple(math.degrees(v) for v in q.to_euler()))
    return groups


# ---------------------------------------------------------------------------
# Données d'assets (config/rooms.json lu en lecture seule)
# ---------------------------------------------------------------------------
BUILDERS = {
    "toy_flat_duck": (build_duck, DUCK_COLLIDER_CENTER),
    "toy_train": (build_train, (0.0, 0.0)),
    "toy_drum": (build_drum, (0.0, 0.0)),
    "toy_domino": (build_domino, (0.0, 0.0)),
    "toy_shape_cube": (build_shape_cube, (0.0, 0.0)),
}
MACHINE_ID = "machine_toy_spinner"


def load_family():
    with open(os.path.join(ROOT, "config", "rooms.json"), encoding="utf-8") as f:
        fam = [x for x in json.load(f)["families"] if x["id"] == "toy"][0]
    return fam


def to_roblox(v):
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(float(-v[1]), 4)]


def collision_entry(prop, center):
    w, d, h = prop["collider"]["size_studs"]
    cx, cy = center
    e = {
        "asset_id": prop["id"],
        "authority": "server_collider_separate_from_visual_mesh",
        "pivot": "bottom_center",
        "forward_axis": "-Z",
        "dimensions_order_config": "width_depth_height",
        "visual_envelope_studs_config": prop["size_studs"],
        "collider": {
            "shape": "box",
            "size_studs_config": [w, d, h],
            "size_vector3_roblox": [w, h, d],
            "offset_from_pivot_roblox": to_roblox((cx, cy, h / 2.0)),
            "tags": ["FillCollider"],
            "can_collide": True,
        },
        "walkable_top": {
            "size_studs": prop["collider"]["walkable_top"],
            "height_studs": h,
            "center_roblox": to_roblox((cx, cy, h)),
            "flat_tolerance_studs": 0.25,
        },
        "support_sockets_roblox": [to_roblox((cx + sx * w / 4, cy + sy * d / 4, h)) for sx in (-1, 1) for sy in (-1, 1)]
        + [to_roblox((cx, cy, h))],
        "visual_mesh": {"can_collide": False, "can_query": False, "can_touch": False},
        "behavior": prop["behavior"],
        "behavior_params": prop.get("behavior_params"),
    }
    return e


# ---------------------------------------------------------------------------
def export_asset(asset_id, lod0_objs, lod1_objs):
    os.makedirs(IMPORT_DIR, exist_ok=True)
    base = os.path.join(IMPORT_DIR, asset_id)

    def sel(objs):
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]

    common = dict(export_format="GLB", use_selection=True, export_yup=True, export_apply=True,
                  export_texcoords=True, export_normals=True, export_materials="EXPORT",
                  export_animations=False, export_image_format="AUTO")
    sel(lod0_objs)
    bpy.ops.export_scene.gltf(filepath=base + ".glb", **common)
    sel(lod1_objs)
    bpy.ops.export_scene.gltf(filepath=base + "_lod1.glb", **common)
    sel(lod0_objs)
    bpy.ops.export_scene.fbx(filepath=base + ".fbx", use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0, bake_anim=False,
                             path_mode="COPY", embed_textures=True, mesh_smooth_type="FACE")
    return [base + ".glb", base + "_lod1.glb", base + ".fbx"]


def collect(name, objs):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    for o in objs:
        for c in o.users_collection:
            c.objects.unlink(o)
        col.objects.link(o)
    return col


def bbox(objs):
    co = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in objs])
    return co.min(0), co.max(0)


def main(which):
    reset_scene()
    os.makedirs(MODEL_DIR, exist_ok=True)
    img = make_atlas()
    mats = make_materials(img)
    fam = load_family()
    props = {p["id"]: p for p in fam["props"]}
    info = {"blender_version": bpy.app.version_string, "atlas": os.path.relpath(os.path.join(TEX_DIR, ATLAS_NAME), ROOT),
            "palette": dict(PALETTE), "assets": {}}
    collisions = {}
    ids = list(BUILDERS) + [MACHINE_ID] if which == "all" else [which]
    for asset_id in ids:
        lods = []
        if asset_id == MACHINE_ID:
            for lod in (0, 1):
                B = Builder(lod, mats, f"{asset_id}_L{lod}")
                groups = build_machine(B)
                objs = [join(parts, f"{asset_id}_{g}" + ("" if lod == 0 else "_LOD1")) for g, parts in groups.items()]
                lods.append(objs)
            size = fam["machine"]["size_studs"]
        else:
            fn, center = BUILDERS[asset_id]
            for lod in (0, 1):
                B = Builder(lod, mats, f"{asset_id}_L{lod}")
                fn(B)
                lods.append([join(B.parts, asset_id + ("" if lod == 0 else "_LOD1"))])
            size = props[asset_id]["size_studs"]
            collisions[asset_id] = collision_entry(props[asset_id], center)
        mn, mx = bbox(lods[0])
        exports = export_asset(asset_id, lods[0], lods[1])
        collect(asset_id, lods[0] + lods[1])
        info["assets"][asset_id] = {
            "lod0_tris": sum(tri_count(o) for o in lods[0]),
            "lod1_tris": sum(tri_count(o) for o in lods[1]),
            "meshes_lod0": [o.name for o in lods[0]],
            "materials_per_mesh": {o.name: [m.name for m in o.data.materials] for o in lods[0]},
            "bbox_min": [round(float(v), 3) for v in mn],
            "bbox_max": [round(float(v), 3) for v in mx],
            "size_measured_wdh": [round(float(v), 3) for v in (mx - mn)],
            "size_config_wdh": size,
            "exports": [os.path.relpath(p, ROOT) for p in exports],
        }
        print(asset_id, json.dumps(info["assets"][asset_id]))
    if which == "all":
        img.pack()
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(MODEL_DIR, "toy_props.blend"), compress=True)
        with open(os.path.join(MODEL_DIR, "collision_toy_props.json"), "w", encoding="utf-8") as f:
            json.dump({"family": "toy", "units": "studs", "axes": "roblox_model_space (X largeur, Y haut, Z profondeur ; avant = -Z)",
                       "props": collisions,
                       "machine": {"asset_id": MACHINE_ID, "collision": "separate_architecture_proxy",
                                   "parts": {"Mount": "fixe", "Spinner": "rotation autour de l'axe vertical passant par le pivot",
                                             "Trunks": "fixes ou solidaires de la toupie (au choix du runtime)"}}},
                      f, ensure_ascii=False, indent=2)
        with open(os.path.join(MODEL_DIR, "build_info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    return info


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
