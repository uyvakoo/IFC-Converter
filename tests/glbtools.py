"""Parse a GLB and map each mesh node back to its IFC element class + glTF material name."""

from __future__ import annotations

import json
import math
import re
import struct

import ifcopenshell
import ifcopenshell.guid

_UUID = re.compile(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")


def _hex(s: str) -> str:
    return re.sub(r"[^0-9a-f]", "", s.lower())


def glb_json(path: str) -> dict:
    data = open(path, "rb").read()
    assert data[:4] == b"glTF", "not a glb"
    clen = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20 : 20 + clen])


def material_names(glb_path: str) -> set:
    return {m.get("name") for m in glb_json(glb_path).get("materials", [])}


def triangle_count(glb_path: str) -> int:
    """Sum of triangles from index accessors (works even after meshopt compression — counts are JSON)."""
    g = glb_json(glb_path)
    accessors = g.get("accessors", [])
    total = 0
    for mesh in g.get("meshes", []):
        for prim in mesh.get("primitives", []):
            idx = prim.get("indices")
            if idx is not None:
                total += accessors[idx]["count"] // 3
    return total


def make_dense_glb(path: str, n: int = 40, curve: float = 0.15, material: str = "Structural") -> int:
    """Write a valid GLB of a smooth (n+1)x(n+1) curved grid surface (2*n*n triangles), one material.

    Used to prove the low-poly/-si decimation stage: a smooth surface is genuinely decimatable (unlike
    the hard-edged box geometry in the IFC fixtures, which gltfpack's border-aware simplifier keeps).
    Returns the triangle count written.
    """
    verts, idx = [], []
    for i in range(n + 1):
        for j in range(n + 1):
            x, y = i / n, j / n
            z = curve * math.sin(x * math.pi) * math.sin(y * math.pi)
            verts.append((x, y, z))
    for i in range(n):
        for j in range(n):
            a = i * (n + 1) + j
            b, c, d = a + 1, a + (n + 1), a + (n + 2)
            idx += [a, c, b, b, c, d]
    pos = b"".join(struct.pack("<3f", *v) for v in verts)
    ind = b"".join(struct.pack("<I", v) for v in idx)
    buf = pos + ind
    mins = [min(v[k] for v in verts) for k in range(3)]
    maxs = [max(v[k] for v in verts) for k in range(3)]
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}],
        "materials": [{"name": material, "pbrMetallicRoughness": {"baseColorFactor": [0.8, 0.8, 0.8, 1]}}],
        "buffers": [{"byteLength": len(buf)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos), "byteLength": len(ind), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(verts),
             "type": "VEC3", "min": mins, "max": maxs},
            {"bufferView": 1, "componentType": 5125, "count": len(idx), "type": "SCALAR"},
        ],
    }  # fmt: skip
    jb = json.dumps(gltf).encode()
    jb += b" " * (-len(jb) % 4)
    buf += b"\x00" * (-len(buf) % 4)
    glb = b"glTF" + struct.pack("<II", 2, 12 + 8 + len(jb) + 8 + len(buf))
    glb += struct.pack("<I", len(jb)) + b"JSON" + jb
    glb += struct.pack("<I", len(buf)) + b"BIN\x00" + buf
    open(path, "wb").write(glb)
    return len(idx) // 3


def node_class_material(glb_path: str, ifc_path: str):
    """Return list of (ifc_class, material_name) for every mesh node mapped to an IFC element."""
    g = glb_json(glb_path)
    mats = [m.get("name") for m in g.get("materials", [])]
    meshes = g.get("meshes", [])
    model = ifcopenshell.open(ifc_path)
    guid_to_class = {
        _hex(ifcopenshell.guid.expand(e.GlobalId)): e.is_a() for e in model.by_type("IfcElement")
    }
    out = []
    for node in g.get("nodes", []):
        m = _UUID.search(node.get("name", ""))
        if not m or node.get("mesh") is None:
            continue
        cls = guid_to_class.get(_hex(m.group(1)))
        if cls is None:
            continue
        idx = meshes[node["mesh"]]["primitives"][0].get("material")
        out.append((cls, mats[idx] if idx is not None else None))
    return out
