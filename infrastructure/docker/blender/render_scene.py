"""Fixed, reviewed Blender script. Reads a data-only scene document and renders PNG frames with EEVEE.

Usage: blender --background --factory-startup --python render_scene.py -- scene.json out_dir
This script never evaluates strings from the document; it only reads numbers, colours and enum values.
"""
import json
import math
import sys
from pathlib import Path

import bpy  # type: ignore  # provided by Blender

ALLOWED_SHAPES = {"sphere", "capsule", "box", "cylinder", "cone"}


def hex_rgba(value):
    v = value.lstrip("#")
    return (int(v[0:2], 16) / 255, int(v[2:4], 16) / 255, int(v[4:6], 16) / 255, 1.0)


def material(color, cache={}):  # noqa: B006 - intentional per-process cache
    if color not in cache:
        m = bpy.data.materials.new(color)
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = hex_rgba(color)
        cache[color] = m
    return cache[color]


def add_part(part, x_offset, scale):
    shape = part["shape"] if part["shape"] in ALLOWED_SHAPES else "box"
    px, py, pz = (float(v) for v in part["position"])
    sx, sy, sz = (float(v) for v in part["size"])
    loc = (x_offset + px * scale, pz * scale, py * scale)  # glTF y-up -> Blender z-up
    if shape in ("sphere", "capsule"):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=loc)
    elif shape == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1, location=loc)
    elif shape == "cone":
        bpy.ops.mesh.primitive_cone_add(radius1=0.5, depth=1, location=loc)
    else:
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.scale = (sx * scale, sz * scale, sy * scale)
    obj.data.materials.append(material(part["color"]))
    return obj


def main():
    doc_path, out_dir = sys.argv[sys.argv.index("--") + 1 :][:2]
    doc = json.loads(Path(doc_path).read_text())
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if hasattr(bpy.types, "EEVEE_NEXT") else "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = int(doc["width"]), int(doc["height"])
    scene.render.fps = int(doc["fps"])
    frame = 0
    for s in doc["scenes"]:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()
        bpy.ops.mesh.primitive_plane_add(size=40)
        bpy.context.active_object.data.materials.append(material(s["environment"]["ground"]))
        world = bpy.data.worlds.new("w")
        world.color = hex_rgba(s["environment"]["skyBottom"])[:3]
        scene.world = world
        bpy.ops.object.light_add(type="SUN", location=(4, -6, 8))
        bpy.context.active_object.data.color = hex_rgba(s["light"])[:3]
        for actor in s["actors"]:
            for part in actor["parts"]:
                add_part(part, float(actor["x"]), float(actor["scale"]))
        zoom = float(s["camera"]["zoom"])
        bpy.ops.object.camera_add(location=(0, -9 / zoom, 1.4), rotation=(math.radians(85), 0, 0))
        scene.camera = bpy.context.active_object
        for _ in range(int(s["durationFrames"])):
            scene.render.filepath = str(Path(out_dir) / f"frame_{frame:05d}.png")
            bpy.ops.render.render(write_still=True)
            frame += 1


main()
