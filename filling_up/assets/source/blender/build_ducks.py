"""Construit la gamme de canards gonflables (5 formes x accessoires = 15 variantes) pour FILLING UP.

Usage (depuis filling_up/) :
    .venv/bin/python -I assets/source/blender/build_ducks.py [--out-root DIR] [id ...]

Sorties (racine du projet, ou DIR pour la reconstruction de contrôle du déterminisme) :
  assets/source/models/ducks/ducks.blend                 (LOD0 + LOD1 de chaque variante, atlas empaqueté)
  assets/source/models/ducks/textures/duck_atlas_1024.png (+ duck_atlas_rough_1024.png : G rugosité, B métal)
  assets/source/models/ducks/build_info.json, collision_ducks.json
  assets/import/models/<id>.glb, <id>_lod1.glb, <id>.fbx

Approche modulaire : duck_kit.FORMS (corps) + duck_kit.ACCESSORIES (prises head_top / eyes / beak_under /
neck / body). Chaque variante = forme + accessoires, fusionnée en UN maillage, UN matériau (atlas partagé).
Unités/axes : décision 0003 (1 BU = 1 stud ; X largeur, Y profondeur, Z haut ; avant Roblox -Z = +Y Blender ;
pivot au sol, centré). Construction déterministe (graines fixes) ; aucun asset tiers.
"""
from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import duck_atlas as atlas  # noqa: E402
import duck_kit as K  # noqa: E402

SEED = 20261102
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # filling_up/

# budgets de triangles (LOD0 min, LOD0 max, LOD1 max) par forme
BUDGETS = {"mini": (600, 1500, 350), "medium": (1500, 3200, 700), "lilo": (1200, 2600, 600),
           "large_ring": (2500, 4500, 900), "giant": (4000, 7000, 1200)}

VARIANTS = {
    "pool_duck_mini_classic": dict(
        form="mini", acc=[], skin="yellow", name="Mini canard de bain",
        brief="Petit canard de bain classique en vinyle jaune brillant, dos plat praticable à 3 studs, tête ronde "
              "à l'avant, bec orange, grands yeux marine, queue relevée, soudures et valve."),
    "pool_duck_mini_sunglasses": dict(
        form="mini", acc=["glasses_star"], skin="yellow", name="Mini canard lunettes étoiles",
        brief="Mini canard de bain avec d'énormes lunettes de soleil en forme d'étoiles roses."),
    "pool_duck_mini_swimcap": dict(
        form="mini", acc=["swim_cap"], skin="yellow", name="Mini canard bonnet de bain",
        brief="Mini canard de bain coiffé d'un bonnet de bain bleu piscine couvert de grosses fleurs en relief."),
    "pool_duck_mini_bowtie": dict(
        form="mini", acc=["bowtie_red", "moustache_curl"], skin="yellow", name="Mini canard noeud papillon",
        brief="Mini canard de bain chic : noeud papillon rouge à pois blancs et petite moustache bouclée."),
    "pool_duck_summer": dict(
        form="medium", acc=["glasses_round", "straw_hat"], skin="yellow", name="Canard bouée été",
        brief="Canard gonflable à chevaucher, selle plate matelassée, avec lunettes rondes corail et grand "
              "chapeau de paille à ruban corail."),
    "pool_duck_gentleman": dict(
        form="medium", acc=["moustache_handlebar", "top_hat", "bowtie_black", "monocle"], skin="yellow",
        name="Canard gentleman",
        brief="Canard gonflable à chevaucher très distingué : moustache en guidon, haut-de-forme noir à ruban "
              "rouge, noeud papillon noir et monocle doré à chaînette."),
    "pool_duck_sailor": dict(
        form="medium", acc=["sailor_bob", "sailor_scarf"], skin="mariniere", name="Canard marin",
        brief="Canard gonflable à chevaucher en marinière rayée marine et blanche, bob de marin blanc à badge "
              "ancre et foulard marine."),
    "pool_duck_snorkel": dict(
        form="medium", acc=["diving_mask", "snorkel", "swimsuit_band"], skin="yellow", name="Canard plongeur",
        brief="Canard gonflable à chevaucher équipé d'un masque de plongée bleu, d'un tuba corail et d'un "
              "maillot rétro rayé rouge et blanc autour du corps."),
    "pool_duck_royal": dict(
        form="medium", acc=["crown", "cape"], skin="yellow", wing_tile="cape", name="Canard royal",
        brief="Canard gonflable à chevaucher couronné d'or, cape de velours rouge bordée d'hermine qui retombe "
              "sur l'arrière et les côtés sans dépasser le dessus utile."),
    "pool_duck_lilo_classic": dict(
        form="lilo", acc=[], skin="yellow", name="Matelas canard",
        brief="Long matelas pneumatique jaune à cinq boudins, oreiller et tête de canard à un bout, queue à "
              "l'autre bout ; creux entre boudins de moins de 0,25 stud."),
    "pool_duck_lilo_hawaii": dict(
        form="lilo", acc=["glasses_heart", "lei"], skin="hawaii", name="Matelas canard hawaïen",
        brief="Matelas canard aux boudins imprimés chemise hawaïenne (hibiscus sur bleu piscine), lunettes "
              "coeur menthe et collier de fleurs."),
    "pool_duck_ring_pirate": dict(
        form="large_ring", acc=["tricorn", "eye_patch", "moustache_pirate", "skull_decal"], skin="yellow",
        name="Bouée canard pirate",
        brief="Grande bouée canard carrée à filet trampoline : tricorne noir galonné d'or, cache-oeil, moustache "
              "bouclée et décalque tête de mort sur le flanc."),
    "pool_duck_ring_lifeguard": dict(
        form="large_ring", acc=["lifeguard_cap", "whistle", "sunscreen", "sauveteur_band"], skin="yellow",
        name="Bouée canard sauveteur",
        brief="Grande bouée canard sauveteur : casquette rouge, sifflet sur cordon, trait de crème solaire "
              "blanche sur le bec et bande rouge SAUVETEUR autour de la bouée."),
    "pool_duck_ring_tourist": dict(
        form="large_ring", acc=["bucket_hat", "camera", "glasses_wide", "hawaii_print"], skin="hawaii",
        name="Bouée canard touriste",
        brief="Grande bouée canard touriste : flancs en chemise hawaïenne, bob beige à fleur, lunettes noires "
              "et appareil photo en bandoulière."),
    "pool_duck_captain": dict(
        form="giant", acc=["captain_cap", "moustache_walrus", "bubble_pipe", "mariniere"], skin="mariniere",
        name="Capitaine Coin-Coin",
        brief="Île canard géante « Capitaine Coin-Coin » : casquette de capitaine à ancre dorée, grosse "
              "moustache blanche, marinière rayée marine, pipe à bulles de savon (jouet) et bulles irisées ; pont "
              "matelassé imprimé d'une barre de navire."),
}


def form_of(vid):
    return VARIANTS[vid]["form"]


def build_head_group(A, hc, v):
    K.build_head(A, hc, eyes=True)
    for acc in v["acc"]:
        sock, fn, _label = K.ACCESSORIES[acc]
        if sock != "body" and fn is not None:
            fn(A, hc)


def compose(vid, lod):
    v = VARIANTS[vid]
    form = v["form"]
    P = K.FORMS[form]
    A = K.Asset(vid, P["envelope"], lod, P["k"])
    bc = K.form_body(A, form, v.get("skin", "yellow"), v.get("wing_tile", "wing"))
    for acc in v["acc"]:
        sock, fn, _label = K.ACCESSORIES[acc]
        if sock == "body" and fn is not None:
            fn(A, bc)
    hc = K.head_ctx(form, A)
    meas = K.Measure(A)
    hc.z = 0.0
    neck_abs, hc.neck_abs = hc.neck_abs, None  # passe de mesure : prises toutes relatives à la tête
    build_head_group(meas, hc, v)
    hc.neck_abs = neck_abs
    hc.z = bc.H - meas.mx.z  # la tête + accessoires atteignent exactement le haut de l'enveloppe
    if "neck_lo" in P:
        K.neck_for(A, bc, hc, P["neck_lo"])
    build_head_group(A, hc, v)
    cw, cd, T = P["collider"]
    fac = A.fit((cw / 2, cd / 2, T))
    info = {"head_center": [round(c, 4) for c in hc.o],
            "head_size": {"half_width": hc.hx, "thickness_along_facing": round(2 * hc.hy, 4), "half_height": hc.hz,
                          "bill_protrusion": hc.p},
            "head_axis": "+X" if form == "lilo" else "+Y (Roblox -Z)", "fit_factors": fac}
    return A, info


# =====================================================================================
# matériaux, export, sauvegarde
# =====================================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    return sc


def make_material(col_png, rough_png):
    img = bpy.data.images.load(col_png)
    img.colorspace_settings.name = "sRGB"
    rimg = bpy.data.images.load(rough_png)
    rimg.colorspace_settings.name = "Non-Color"
    m = bpy.data.materials.new("M_duck_atlas")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    tr = nt.nodes.new("ShaderNodeTexImage")
    tr.image = rimg
    sp = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tr.outputs["Color"], sp.inputs["Color"])
    nt.links.new(sp.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sp.outputs["Blue"], bsdf.inputs["Metallic"])
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.5
    return m, (img, rimg)


def select_only(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def export(ob, path, fbx=None):
    select_only(ob)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_texcoords=True, export_normals=True,
                              export_materials="EXPORT", export_animations=False, export_skins=False)
    if fbx:
        bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"}, axis_forward="-Z",
                                 axis_up="Y", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                                 global_scale=1.0, bake_anim=False, path_mode="COPY", embed_textures=True,
                                 mesh_smooth_type="FACE", use_mesh_modifiers=True)


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def collision_entry(vid):
    P = K.FORMS[form_of(vid)]
    w, d, h = P["collider"]
    W, D, H = P["envelope"]
    return {
        "asset_id": vid,
        "duck_form": form_of(vid),
        "behavior": "stable",
        "pivot": "bottom_center",
        "forward_axis": "-Z",
        "head_end": "+X" if form_of(vid) == "lilo" else "-Z",
        "visual_envelope_studs_wdh": [W, D, H],
        "collider": {"shape": "box", "size_studs_config": [w, d, h], "size_vector3_roblox": [w, h, d],
                     "offset_from_pivot_roblox": [0, h / 2, 0], "tags": ["FillCollider"], "can_collide": True},
        "walkable_top": {"size_studs": list(P["walkable"]), "height_studs": h, "center_roblox": [0, h, 0]},
        "visual_mesh": {"can_collide": False, "can_query": False, "can_touch": False},
    }


def manifest_entry(vid):
    v = VARIANTS[vid]
    form = v["form"]
    P = K.FORMS[form]
    w, d, h = P["collider"]
    W, D, H = P["envelope"]
    acc_labels = [K.ACCESSORIES[a][2] for a in v["acc"]]
    head = ("La tête est au bout +X du matelas (bande de 1 stud) car la bande avant -Z ne fait que 0,5 stud ; "
            if form == "lilo" else "Tête et accessoires dans la bande avant (-Z Roblox) hors du dessus utile ; ")
    return {
        "id": vid,
        "name": v["name"],
        "category": "room_prop",
        "release_stage": "MVP",
        "status": "modeled",
        "roblox_asset_id": None,
        "source_path": "assets/source/models/ducks/ducks.blend",
        "export_path": f"assets/import/models/{vid}.glb",
        "additional_exports": [f"assets/import/models/{vid}_lod1.glb", f"assets/import/models/{vid}.fbx"],
        "dimensions_order": "width_depth_height",
        "size_studs": [W, D, H],
        "pivot": "bottom_center",
        "forward_axis": "-Z",
        "visual_brief": v["brief"] + " " + head + "vinyle jaune #FFD23F, bec #FF9B47, pupilles #203055.",
        "collision": {"shape": "box", "size_studs": [w, d, h], "walkable_top": list(P["walkable"]), "top_visible": True},
        "deformation_profile": None,
        "production_method": "blender_mesh_and_optional_rig",
        "requires_external_import": True,
        "max_triangles_near": BUDGETS[form][1],
        "max_materials": 1,
        "image_export_pixels": None,
        "provenance": "generated from code in Blender, no third-party assets",
        "validation_evidence": [
            f"reports/T03/ducks_verify.json#assets.{vid}",
            "reports/T03/ducks_verify_log.txt",
            "assets/source/models/ducks/build_info.json",
            "assets/source/models/ducks/collision_ducks.json",
            f"reports/T03/renders/{vid}_3q.png",
            f"reports/T03/renders/{vid}_silhouette.png",
            "reports/T03/renders/ducks_sheet.png",
            "reports/T03/renders/ducks_silhouettes_sheet.png",
            "reports/T03/renders/ducks_lineup.png",
            "reports/T03/renders/ducks_accessories_sheet.png",
        ],
        "design_reference_paths": [],
        "duck_form": form,
        "accessories": v["acc"],
        "accessories_labels_fr": acc_labels,
        "head_end": "+X" if form == "lilo" else "-Z",
        "max_triangles_far": BUDGETS[form][2],
    }


def write_manifest(root):
    doc = {"task": "T03", "batch": "ducks",
           "rule": "Statut au plus 'modeled' ; roblox_asset_id null tant qu'aucun import Roblox réel n'a eu lieu. "
                   "À fusionner dans assets/manifest.json par l'agent principal (ce lot ne modifie pas le manifeste).",
           "generator_script": "assets/source/blender/build_ducks.py",
           "supporting_files": ["assets/source/blender/duck_kit.py", "assets/source/blender/duck_atlas.py",
                                "assets/source/models/ducks/textures/duck_atlas_1024.png",
                                "assets/source/models/ducks/textures/duck_atlas_rough_1024.png"],
           "new_assets": [manifest_entry(v) for v in VARIANTS]}
    path = os.path.join(root, "reports", "T03", "manifest_new_ducks.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path


def main():
    args = sys.argv[1:]
    root = ROOT
    if "--out-root" in args:
        i = args.index("--out-root")
        root = os.path.abspath(args[i + 1])
        args = args[:i] + args[i + 2:]
    model_dir = os.path.join(root, "assets", "source", "models", "ducks")
    tex_dir = os.path.join(model_dir, "textures")
    import_dir = os.path.join(root, "assets", "import", "models")
    random.seed(SEED)
    os.makedirs(tex_dir, exist_ok=True)
    os.makedirs(import_dir, exist_ok=True)
    col_png, rough_png = atlas.save_atlas(tex_dir)
    reset_scene()
    mat, imgs = make_material(col_png, rough_png)
    info = {"family": "pool_ducks", "seed": SEED, "blender_version": bpy.app.version_string,
            "units": "1 BU = 1 stud (décision 0003)", "atlas": os.path.relpath(col_png, root),
            "atlas_roughness_metal": os.path.relpath(rough_png, root),
            "approach": "modulaire : duck_kit.FORMS (5 corps) + duck_kit.ACCESSORIES (prises head_top/eyes/"
                        "beak_under/neck/body) ; une variante = un maillage, un matériau",
            "fit_note": "Après composition, une déformation affine par morceaux HORS du rectangle du collider et "
                        "au-dessus du dessus utile ajuste l'enveloppe exactement ; facteurs ≈ 1 consignés par asset.",
            "contract_notes": [
                "Bande de tête : l'enveloppe ne laisse que (enveloppe - collider)/2 devant le rectangle praticable "
                "(1 stud ; 2 studs pour l'île géante). Les têtes sont donc des coussins soudés de 0,72 stud d'épaisseur "
                "(1,62 pour le géant) + bec de 0,4-0,5 ; dos de la tête 0,12 stud à l'intérieur du bord du rectangle "
                "(dans la marge non échantillonnée de 0,25).",
                "Matelas : la bande avant -Z ne fait que 0,5 stud ; la tête est au bout +X (bande de 1 stud), regard +X, "
                "queue au bout -X.",
                "Mini LOD1 : ailes supprimées (budget 350) ; la largeur 5 est atteinte par l'ajustement d'enveloppe hors "
                "collider (facteur x 1,25 sur le bombé latéral, au-delà de |x| = 2).",
                "Chapeaux à la profondeur de la tête : calottes elliptiques écrasées en profondeur, bords larges en X.",
            ],
            "assets": {}}
    only = args or list(VARIANTS)
    for vid in VARIANTS:
        if vid not in only:
            continue
        coll = bpy.data.collections.new(vid)
        bpy.context.scene.collection.children.link(coll)
        objs, cinfo = {}, {}
        for lod in (0, 1):
            A, ci = compose(vid, lod)
            cinfo[lod] = ci
            ob = A.to_object(f"{vid}_LOD{lod}", [mat])
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            coll.objects.link(ob)
            objs[lod] = ob
        base = os.path.join(import_dir, vid)
        export(objs[0], base + ".glb", base + ".fbx")
        export(objs[1], base + "_lod1.glb")
        objs[1].hide_set(True)
        objs[1].hide_render = True
        v = VARIANTS[vid]
        info["assets"][vid] = {
            "duck_form": v["form"], "accessories": v["acc"], "skin": v.get("skin", "yellow"),
            "lod0_object": objs[0].name, "lod1_object": objs[1].name,
            "lod0_tris": tris(objs[0]), "lod1_tris": tris(objs[1]),
            "lod0_dims_wdh": [round(x, 4) for x in objs[0].dimensions],
            "lod1_dims_wdh": [round(x, 4) for x in objs[1].dimensions],
            "materials": [m.name for m in objs[0].data.materials],
            "head": cinfo[0], "lod1_fit_factors": cinfo[1]["fit_factors"],
            "exports": [os.path.relpath(base + e, root) for e in (".glb", "_lod1.glb", ".fbx")],
        }
        a = info["assets"][vid]
        print(vid, a["lod0_tris"], a["lod1_tris"], a["lod0_dims_wdh"], a["lod1_dims_wdh"], cinfo[0]["fit_factors"],
              cinfo[1]["fit_factors"], flush=True)
    for im in imgs:
        im.pack()
    bpy.context.preferences.filepaths.save_version = 0
    blend = os.path.join(model_dir, "ducks.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    info["blend"] = os.path.relpath(blend, root)
    if len(only) == len(VARIANTS):
        with open(os.path.join(model_dir, "build_info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        cj = {"family": "pool_ducks", "units": "studs",
              "axes": "roblox_model_space (X largeur, Y haut, Z profondeur ; avant = -Z)",
              "authority": "server_collider_separate_from_visual_mesh",
              "rule": "tête, cou, chapeaux, queue et accessoires hors du rectangle praticable ou sous son dessus",
              "props": [collision_entry(v) for v in VARIANTS]}
        with open(os.path.join(model_dir, "collision_ducks.json"), "w", encoding="utf-8") as f:
            json.dump(cj, f, ensure_ascii=False, indent=2)
        write_manifest(root)


if __name__ == "__main__":
    main()
