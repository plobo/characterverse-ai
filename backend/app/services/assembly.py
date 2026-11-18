"""Deterministic character assembly: recipe -> resolved primitive parts -> GLB preview + PNG thumbnail.

The part-resolution algorithm is shared with the iOS and Android preview viewers and pinned by
shared/fixtures/assembly_golden.json. See docs/ARCHITECTURE.md#procedural-assembly.
"""

from __future__ import annotations

import io
import json
import math
import struct
from typing import Any

from app.services.catalog import Catalog

Vec3 = list[float]


def resolve_color(key: str, palette: dict[str, str], skin: str) -> str:
    if key in ("primary", "secondary", "accent"):
        return palette[key].upper()
    if key == "skin":
        return skin.upper()
    return key.upper()


def assemble_parts(recipe: dict[str, Any], catalog: Catalog) -> list[dict[str, Any]]:
    base_def = catalog.parts["baseModels"][recipe["baseModelId"]]
    raw: list[tuple[str, str, str, Vec3, Vec3, str]] = []  # id, shape, group, pos, size, color
    for p in base_def["parts"]:
        raw.append((p["id"], p["shape"], p["group"], list(p["position"]), list(p["size"]), p["color"]))

    for module_id in recipe["modules"]:
        module_def = catalog.parts["modules"][module_id]
        slot = catalog.get(module_id, "module").data["slot"]
        anchor = base_def["anchors"][slot]
        for p in module_def["parts"]:
            pos = [anchor[i] + p["position"][i] for i in range(3)]
            pid = f"{module_id}.{p['id']}"
            if module_def["mirrorX"]:
                raw.append(
                    (
                        pid + ".l",
                        p["shape"],
                        module_def["group"],
                        [-pos[0], pos[1], pos[2]],
                        list(p["size"]),
                        p["color"],
                    )
                )
                raw.append((pid + ".r", p["shape"], module_def["group"], pos, list(p["size"]), p["color"]))
            else:
                raw.append((pid, p["shape"], module_def["group"], pos, list(p["size"]), p["color"]))

    prop = recipe["proportions"]
    h, w, k = prop["height"], prop["shoulderWidth"], prop["headScale"]
    c = base_def["headCenter"]
    resolved = []
    for pid, shape, group, pos, size, color in raw:
        if group == "head":
            new_pos = [c[0] * w + (pos[0] - c[0]) * k, c[1] * h + (pos[1] - c[1]) * k, c[2] + (pos[2] - c[2]) * k]
            new_size = [size[0] * k, size[1] * k, size[2] * k]
        else:
            new_pos = [pos[0] * w, pos[1] * h, pos[2]]
            new_size = [size[0] * w, size[1] * h, size[2]]
        resolved.append(
            {
                "id": pid,
                "shape": shape,
                "position": new_pos,
                "size": new_size,
                "color": resolve_color(color, recipe["palette"], base_def["skin"]),
            }
        )
    return resolved


# ----------------------------------------------------------------------------- GLB


def _hex_to_rgb(color: str) -> tuple[float, float, float]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _unit_mesh(shape: str, seg: int = 16, rings: int = 10):
    """Unit primitive centred on origin spanning [-0.5, 0.5]. Returns (positions, normals, indices)."""
    pos: list[Vec3] = []
    nrm: list[Vec3] = []
    idx: list[int] = []
    if shape in ("sphere", "capsule"):
        for r in range(rings + 1):
            phi = math.pi * r / rings
            for s in range(seg + 1):
                theta = 2 * math.pi * s / seg
                n = [math.sin(phi) * math.cos(theta), math.cos(phi), math.sin(phi) * math.sin(theta)]
                nrm.append(n)
                pos.append([0.5 * v for v in n])
        for r in range(rings):
            for s in range(seg):
                a = r * (seg + 1) + s
                b = a + seg + 1
                idx += [a, a + 1, b, b, a + 1, b + 1]
    elif shape == "box":
        faces = [
            ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
            ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
            ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
            ((0, -1, 0), (0, 0, -1), (1, 0, 0)),
            ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
            ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
        ]
        for n, u, v in faces:
            start = len(pos)
            for du, dv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                pos.append([0.5 * (n[i] + du * u[i] + dv * v[i]) for i in range(3)])
                nrm.append(list(n))
            idx += [start, start + 1, start + 2, start, start + 2, start + 3]
    else:  # cylinder / cone
        top_r = 0.5 if shape == "cylinder" else 0.0
        for s in range(seg + 1):
            t = 2 * math.pi * s / seg
            ct, st = math.cos(t), math.sin(t)
            pos.append([0.5 * ct, -0.5, 0.5 * st])
            nrm.append([ct, 0.0, st])
            pos.append([top_r * ct, 0.5, top_r * st])
            nrm.append([ct, 0.0, st])
        for s in range(seg):
            a = 2 * s
            idx += [a, a + 1, a + 2, a + 2, a + 1, a + 3]
        centre = len(pos)
        pos.append([0.0, -0.5, 0.0])
        nrm.append([0.0, -1.0, 0.0])
        for s in range(seg):
            idx += [centre, 2 * s, 2 * (s + 1)]
    return pos, nrm, idx


def build_glb(parts: list[dict[str, Any]], name: str = "character") -> bytes:
    buffer = bytearray()
    buffer_views, accessors, meshes, nodes, materials = [], [], [], [], []
    material_index: dict[str, int] = {}

    def add_view(data: bytes, target: int) -> int:
        while len(buffer) % 4:
            buffer.append(0)
        buffer_views.append({"buffer": 0, "byteOffset": len(buffer), "byteLength": len(data), "target": target})
        buffer.extend(data)
        return len(buffer_views) - 1

    for part in parts:
        pos, nrm, idx = _unit_mesh(part["shape"])
        sx, sy, sz = part["size"]
        px, py, pz = part["position"]
        world = [[v[0] * sx + px, v[1] * sy + py, v[2] * sz + pz] for v in pos]
        normals = []
        for n in nrm:
            m = [n[0] / max(sx, 1e-6), n[1] / max(sy, 1e-6), n[2] / max(sz, 1e-6)]
            length = math.sqrt(sum(c * c for c in m)) or 1.0
            normals.append([c / length for c in m])
        pv = add_view(b"".join(struct.pack("<3f", *v) for v in world), 34962)
        nv = add_view(b"".join(struct.pack("<3f", *v) for v in normals), 34962)
        iv = add_view(b"".join(struct.pack("<H", i) for i in idx), 34963)
        mins = [min(v[i] for v in world) for i in range(3)]
        maxs = [max(v[i] for v in world) for i in range(3)]
        accessors.append(
            {"bufferView": pv, "componentType": 5126, "count": len(world), "type": "VEC3", "min": mins, "max": maxs}
        )
        accessors.append({"bufferView": nv, "componentType": 5126, "count": len(normals), "type": "VEC3"})
        accessors.append({"bufferView": iv, "componentType": 5123, "count": len(idx), "type": "SCALAR"})
        color = part["color"]
        if color not in material_index:
            r, g, b = _hex_to_rgb(color)
            materials.append(
                {
                    "name": color,
                    "pbrMetallicRoughness": {
                        "baseColorFactor": [r, g, b, 1.0],
                        "metallicFactor": 0.0,
                        "roughnessFactor": 0.6,
                    },
                }
            )
            material_index[color] = len(materials) - 1
        a0 = len(accessors) - 3
        meshes.append(
            {
                "name": part["id"],
                "primitives": [
                    {
                        "attributes": {"POSITION": a0, "NORMAL": a0 + 1},
                        "indices": a0 + 2,
                        "material": material_index[color],
                    }
                ],
            }
        )
        nodes.append({"name": part["id"], "mesh": len(meshes) - 1})

    while len(buffer) % 4:
        buffer.append(0)
    gltf = {
        "asset": {"version": "2.0", "generator": "CharacterVerse procedural assembler 1.0"},
        "scene": 0,
        "scenes": [{"name": name, "nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(buffer)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(buffer)
    out = io.BytesIO()
    out.write(struct.pack("<4sII", b"glTF", 2, total))
    out.write(struct.pack("<I4s", len(js), b"JSON"))
    out.write(js)
    out.write(struct.pack("<I4s", len(buffer), b"BIN\x00"))
    out.write(bytes(buffer))
    return out.getvalue()
