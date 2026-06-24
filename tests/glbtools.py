"""Parse a GLB and map each mesh node back to its IFC element class + glTF material name."""

from __future__ import annotations

import json
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
