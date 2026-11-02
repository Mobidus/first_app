"""Review renders of generated rooms (Blender, Cycles CPU). Input: reports/room_previews/rooms.json
(tools/dump_rooms.luau). Output: reports/room_previews/<idx>_<template>_d<depth>.png + contact sheet.

Legend: set dressing (decision 0018) uses the family palette (furniture, rugs, ceiling lights);
navy = structural pedestal / suspended shelf; family colour = stable prop; mint plate = landing
marker / exit ledge; translucent mint box = protected exit clearance 8x8x10; coral plates = wave
mouths; blue box = spawn sas; orange box = avatar 2x5x1.5 for scale; yellow dots = required route
(node top centres, hop order); violet balls = optional tokens. These are geometry review images,
not in-game screenshots (no Roblox renderer here).

Usage: .venv/bin/python -I tools/render_rooms.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.environ.get("FU_ROOMS_JSON", os.path.join(ROOT, "reports", "room_previews", "rooms.json"))
OUT = os.path.join(ROOT, "reports", "room_previews", os.environ.get("FU_PREVIEW_SUBDIR", ""))
W, H = 960, 720

FAMILY = {"reception": "#16D9FF", "toy": "#FF4CB8", "bureau": "#2ACBC7", "kitchen": "#24BFC4", "garage": "#FF9B47", "bin": "#16D9FF"}
NAVY, MINT, CORAL, CREAM, VIOLET, BLUE, ORANGE, YELLOW = "#203055", "#39E68B", "#FF684B", "#FFF5DF", "#8855FF", "#4A7BFF", "#FF9B47", "#FFE14D"


PALETTES = {f["id"]: f["palette"] for f in json.load(open(os.path.join(ROOT, "config", "rooms.json"), encoding="utf-8"))["families"]}
ROLE_FIXED = {"soft": "#FFF5DF", "dark": "#203055", "plant": "#3FBF6A", "glass": "#BFE9FF", "glow": "#FFF3C4"}


def rgb(hexs: str, a: float = 1.0):
    h = hexs.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[x ** 2.2 for x in c], a)


_mats: dict = {}


def mat(hexs: str, alpha: float = 1.0, emit: float = 0.0):
    key = (hexs, alpha, emit)
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(f"m{len(_mats)}")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgb(hexs)
    b.inputs["Roughness"].default_value = 0.6
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        m.blend_method = "BLEND" if hasattr(m, "blend_method") else None
    if emit > 0:
        b.inputs["Emission Color"].default_value = rgb(hexs)
        b.inputs["Emission Strength"].default_value = emit
    _mats[key] = m
    return m


def box(b: dict, hexs: str, alpha: float = 1.0, emit: float = 0.0):
    """Room-local box {cx,cy,cz,sx,sy,sz} (y up) -> Blender (X=x, Y=-z, Z=y)."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(b["cx"], -b["cz"], b["cy"]))
    o = bpy.context.active_object
    o.scale = (max(b["sx"], 0.02), max(b["sz"], 0.02), max(b["sy"], 0.02))
    o.data.materials.append(mat(hexs, alpha, emit))
    return o


def sphere(x, y, z, r, hexs, emit=0.0):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(x, -z, y), segments=12, ring_count=6)
    bpy.context.active_object.data.materials.append(mat(hexs, 1.0, emit))


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _mats.clear()
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.view_settings.view_transform = "Standard"
    sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.92, 0.94, 0.97, 1)
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 3.0
    so = bpy.data.objects.new("sun", sun)
    so.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
    sc.collection.objects.link(so)


def render_room(entry: dict, path: str):
    reset_scene()
    r = entry["room"]
    w, d, h = r["size"]["w"], r["size"]["d"], r["size"]["h"]
    fam = FAMILY.get(r["familyId"], "#16D9FF")
    box({"cx": 0, "cy": -0.5, "cz": 0, "sx": w, "sy": 1, "sz": d}, CREAM)
    # two back walls only (camera looks from the front-left corner)
    box({"cx": w / 2 + 0.5, "cy": h / 2, "cz": 0, "sx": 1, "sy": h, "sz": d}, "#DFE7F2")
    box({"cx": 0, "cy": h / 2, "cz": d / 2 + 0.5, "sx": w, "sy": h, "sz": 1}, "#E7ECF5")
    for s in r["solids"]:
        kind = s.get("kind")
        if kind in ("pedestal", "shelf", "architecture"):
            box(s["box"], MINT if s.get("nodeId") in ("exit_ledge", "lever") else NAVY)
        elif kind == "optional":
            box(s["box"], YELLOW, 0.85)
        else:
            box(s["box"], fam)
    pal = PALETTES.get(r["familyId"], {})
    for item in r.get("decor", []) or []:
        for part in item["parts"]:
            role = part["role"]
            hexs = ROLE_FIXED.get(role) or {"structure": pal.get("structure"), "accent": pal.get("accent"),
                                            "background": pal.get("fond")}.get(role) or "#999999"
            box(part["box"], hexs, 0.6 if role == "glass" else 1.0, 2.0 if role == "glow" else 0.0)
    for n in r["routeGraph"]["nodes"]:
        if n["kind"] in ("column", "shelf") and not n.get("optional"):
            wl = n["walkable"]
            box({"cx": n["box"]["cx"], "cy": n["topY"] + 0.06, "cz": n["box"]["cz"], "sx": max(1, wl["w"] - 2), "sy": 0.12, "sz": max(1, wl["d"] - 2)},
                MINT, 1.0, 0.6)
    c = r["exitClearance"]
    box(c, MINT, 0.25)
    box(r["exitOpening"], MINT, 1.0, 1.5)
    for m in r["waveMouths"]:
        box({"cx": m["cx"], "cy": h - 0.2, "cz": m["cz"], "sx": m["sx"], "sy": 0.4, "sz": m["sz"]}, CORAL, 1.0, 0.8)
    for sz in r["spawnZones"]:
        box(sz, BLUE, 0.35)
        box({"cx": sz["cx"], "cy": 2.5, "cz": sz["cz"], "sx": 2, "sy": 5, "sz": 1.5}, ORANGE)
    nodes = {n["id"]: n for n in r["routeGraph"]["nodes"]}
    for e in r["routeGraph"]["edges"]:
        a, b = nodes.get(e["from"]), nodes.get(e["to"])
        if not a or not b or a["kind"] == "floor":
            continue
        p0 = Vector((a["box"]["cx"], a["topY"] + 0.6, a["box"]["cz"]))
        p1 = Vector((b["box"]["cx"], b["topY"] + 0.6, b["box"]["cz"]))
        for i in range(1, 8):
            t = i / 8
            p = p0.lerp(p1, t)
            sphere(p.x, p.y + math.sin(t * math.pi) * 2.5, p.z, 0.3, YELLOW, 1.0)
    for tk in r.get("tokens", []):
        sphere(tk["x"], tk["y"], tk["z"], 0.6, VIOLET, 0.5)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.type = "ORTHO"
    cam_d.ortho_scale = max(w, d, h) * 1.75
    cam = bpy.data.objects.new("cam", cam_d)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (-w * 1.4, d * 1.4, h * 1.25)
    target = Vector((0, 0, h * 0.35))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main() -> int:
    data = json.load(open(SRC, encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    written = []
    for i, entry in enumerate(data["rooms"]):
        r = entry["room"]
        name = f"{i:02d}_{r['templateId']}_d{entry['depth']}.png"
        render_room(entry, os.path.join(OUT, name))
        written.append({"file": name, "depth": entry["depth"], "template": r["templateId"], "fallback": bool(r.get("fallback")),
                        "nodes": len(r["routeGraph"]["nodes"]), "size": r["size"],
                        "decor": sum(1 for it in (r.get("decor") or []) if it["kind"] in ("furniture", "wall"))})
        print("rendered", name, flush=True)
    json.dump({"runSeed": data["runSeed"], "renders": written,
               "note": "Geometry review renders from validated RoomDefinitions; not Roblox screenshots."},
              open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
