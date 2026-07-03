"""
F6 (AR, iOS-native) — GLB -> USDZ, dependency-free.

USDZ is Apple's ARKit / Quick Look format (iPad/iPhone AR opens it with no conversion step). This turns
the plain, coloured, Y-up GLB that IfcConvert already produces (F4) into a USDZ, so the same crop + our
four AR group colours reach ARKit directly.

Self-contained on purpose — no pxr/USD, no new bundled binary, nothing to fetch — to match the project's
air-gapped bundle contract (§1). It:
  1. reads the *uncompressed* GLB (numpy, already a runtime dep) into world-space triangle meshes, and
  2. writes an ASCII USD layer (.usda) packaged as a spec-compliant .usdz (stored zip, 64-byte-aligned
     file data, per Apple's USDZ layout).

Read the GLB BEFORE the F5 Draco/meshopt post-step (which encodes the buffers); this reader handles plain
glTF accessors only, which is exactly what `convert.to_glb` emits.
"""

from __future__ import annotations

import json
import os
import struct
import zlib

import numpy as np

# glTF accessor component types -> numpy dtype
_COMPONENT = {
    5120: np.int8,
    5121: np.uint8,
    5122: np.int16,
    5123: np.uint16,
    5125: np.uint32,
    5126: np.float32,
}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
_DEFAULT_COLOR = (0.8, 0.8, 0.8)  # matches the Structural fallback grey
_ALIGN = 64  # Apple USDZ requires file data aligned to 64 bytes


# --------------------------------------------------------------------------- GLB reading


def _read_glb(path: str) -> tuple[dict, bytes]:
    """Return (gltf_json, binary_chunk) from a binary glTF (.glb) container."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        raise ValueError(f"not a binary glTF (.glb): {os.path.basename(path)}")
    total = struct.unpack_from("<I", data, 8)[0]
    gltf = None
    bin_chunk = b""
    off = 12
    while off < total:
        clen, ctype = struct.unpack_from("<II", data, off)
        body = data[off + 8 : off + 8 + clen]
        if ctype == 0x4E4F534A:  # 'JSON'
            gltf = json.loads(body)
        elif ctype == 0x004E4942:  # 'BIN\0'
            bin_chunk = body
        off += 8 + clen
    if gltf is None:
        raise ValueError("GLB has no JSON chunk")
    return gltf, bin_chunk


def _accessor(gltf: dict, buf: bytes, idx: int) -> np.ndarray:
    """Read accessor `idx` as an (count, ncomp) array, honouring bufferView byteStride (interleaving)."""
    acc = gltf["accessors"][idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    dtype = np.dtype(_COMPONENT[acc["componentType"]])
    ncomp = _NCOMP[acc["type"]]
    count = acc["count"]
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or (ncomp * dtype.itemsize)
    if stride == ncomp * dtype.itemsize:  # tightly packed
        flat = np.frombuffer(buf, dtype=dtype, count=count * ncomp, offset=base)
        return flat.reshape(count, ncomp)
    out = np.empty((count, ncomp), dtype=dtype)  # interleaved
    for i in range(count):
        out[i] = np.frombuffer(buf, dtype=dtype, count=ncomp, offset=base + i * stride)
    return out


def _quat_matrix(x: float, y: float, z: float, w: float) -> np.ndarray:
    m = np.eye(4)
    m[:3, :3] = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]
    return m


def _node_local(node: dict) -> np.ndarray:
    if "matrix" in node:  # glTF stores column-major; transpose to row-major for point' = M @ p
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    m = np.eye(4)
    if "scale" in node:
        m = np.diag([*node["scale"], 1.0]) @ m
    if "rotation" in node:
        m = _quat_matrix(*node["rotation"]) @ m
    if "translation" in node:
        t = np.eye(4)
        t[:3, 3] = node["translation"]
        m = t @ m
    return m


def _material_color(gltf: dict, prim: dict) -> tuple[float, float, float]:
    mi = prim.get("material")
    if mi is None:
        return _DEFAULT_COLOR
    mat = gltf.get("materials", [])[mi]
    bcf = mat.get("pbrMetallicRoughness", {}).get("baseColorFactor")
    if not bcf:
        return _DEFAULT_COLOR
    return (round(float(bcf[0]), 4), round(float(bcf[1]), 4), round(float(bcf[2]), 4))


class _Mesh:
    __slots__ = ("name", "points", "indices", "color")

    def __init__(self, name, points, indices, color):
        self.name = name
        self.points = points  # (n,3) float32 world-space
        self.indices = indices  # (m,) int, triangle list
        self.color = color


def _meshes_from_glb(gltf: dict, buf: bytes) -> list[_Mesh]:
    """Flatten the glTF scene graph into world-space triangle meshes (one per drawn primitive)."""
    meshes: list[_Mesh] = []
    scene_idx = gltf.get("scene", 0)
    scenes = gltf.get("scenes", [{"nodes": list(range(len(gltf.get("nodes", []))))}])
    roots = scenes[scene_idx].get("nodes", [])
    nodes = gltf.get("nodes", [])

    stack = [(r, np.eye(4)) for r in roots]
    counter = 0
    while stack:
        ni, parent = stack.pop()
        node = nodes[ni]
        world = parent @ _node_local(node)
        if "mesh" in node:
            for prim in gltf["meshes"][node["mesh"]].get("primitives", []):
                if prim.get("mode", 4) != 4:  # only TRIANGLES
                    continue
                pos = _accessor(gltf, buf, prim["attributes"]["POSITION"]).astype(np.float64)
                homo = np.column_stack([pos, np.ones(len(pos))])
                world_pos = (homo @ world.T)[:, :3].astype(np.float32)
                if "indices" in prim:
                    idx = _accessor(gltf, buf, prim["indices"]).reshape(-1).astype(np.int64)
                else:
                    idx = np.arange(len(world_pos), dtype=np.int64)
                meshes.append(
                    _Mesh(f"mesh_{counter}", world_pos, idx, _material_color(gltf, prim))
                )
                counter += 1
        for c in node.get("children", []):
            stack.append((c, world))
    return meshes


# --------------------------------------------------------------------------- USD authoring


def _fmt_floats(rows: np.ndarray) -> str:
    return ", ".join("(" + ", ".join(f"{v:.6g}" for v in row) + ")" for row in rows)


def _usda(meshes: list[_Mesh]) -> str:
    lines = [
        "#usda 1.0",
        "(",
        '    defaultPrim = "Root"',
        "    metersPerUnit = 1",
        '    upAxis = "Y"',
        ")",
        "",
        'def Xform "Root"',
        "{",
    ]
    for m in meshes:
        tris = len(m.indices) // 3
        counts = ", ".join(["3"] * tris)
        idx = ", ".join(str(int(i)) for i in m.indices[: tris * 3])
        lines += [
            f'    def Mesh "{m.name}"',
            "    {",
            f"        int[] faceVertexCounts = [{counts}]",
            f"        int[] faceVertexIndices = [{idx}]",
            f"        point3f[] points = [{_fmt_floats(m.points)}]",
            f"        color3f[] primvars:displayColor = [({m.color[0]:.4g}, {m.color[1]:.4g}, "
            f"{m.color[2]:.4g})] (interpolation = \"constant\")",
            '        uniform token subdivisionScheme = "none"',
            "    }",
        ]
    lines += ["}", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- USDZ packaging


def _write_usdz(files: dict[str, bytes], out_path: str) -> None:
    """Write a spec-compliant .usdz: a *stored* (uncompressed) zip whose file data is 64-byte aligned.

    The first entry is the default USD layer. ARKit/Quick Look mmaps the archive, so Apple requires each
    file's data to start on a 64-byte boundary — we pad the local header's extra field to achieve that.
    """
    entries = []
    with open(out_path, "wb") as f:
        for name, data in files.items():
            name_b = name.encode("utf-8")
            crc = zlib.crc32(data) & 0xFFFFFFFF
            size = len(data)
            start = f.tell()
            # local header is 30 bytes + filename + extra; pad extra so data lands on a 64-byte boundary
            pad = (-(start + 30 + len(name_b))) % _ALIGN
            extra = b"\x00" * pad
            f.write(
                struct.pack(
                    "<IHHHHHIIIHH",
                    0x04034B50, 20, 0, 0, 0, 0, crc, size, size, len(name_b), len(extra),
                )
            )  # fmt: skip
            f.write(name_b)
            f.write(extra)
            assert f.tell() % _ALIGN == 0
            f.write(data)
            entries.append((name_b, crc, size, start))
        cd_start = f.tell()
        for name_b, crc, size, off in entries:
            f.write(
                struct.pack(
                    "<IHHHHHHIIIHHHHHII",
                    0x02014B50, 20, 20, 0, 0, 0, 0, crc, size, size, len(name_b), 0, 0, 0, 0, 0, off,
                )
            )  # fmt: skip
            f.write(name_b)
        cd_size = f.tell() - cd_start
        f.write(
            struct.pack(
                "<IHHHHIIH",
                0x06054B50, 0, 0, len(entries), len(entries), cd_size, cd_start, 0,
            )
        )  # fmt: skip


# --------------------------------------------------------------------------- public API


def glb_to_usdz(glb_path: str, out_usdz: str) -> dict:
    """Convert a plain (uncompressed) GLB to a USDZ. Returns {meshes, vertices, triangles, bytes}.

    Preserves the GLB's world-space geometry and per-material displayColor (our four AR group colours).
    Raises ValueError if the GLB has no triangle geometry.
    """
    gltf, buf = _read_glb(glb_path)
    meshes = _meshes_from_glb(gltf, buf)
    if not meshes:
        raise ValueError("GLB has no triangle geometry to export to USDZ")
    stem = os.path.splitext(os.path.basename(out_usdz))[0]
    usda_name = stem + ".usda"
    usda_bytes = _usda(meshes).encode("utf-8")
    _write_usdz({usda_name: usda_bytes}, out_usdz)
    return {
        "meshes": len(meshes),
        "vertices": int(sum(len(m.points) for m in meshes)),
        "triangles": int(sum(len(m.indices) // 3 for m in meshes)),
        "bytes": os.path.getsize(out_usdz),
    }
