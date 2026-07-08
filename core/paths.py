"""Resource path resolution that works in dev and inside a PyInstaller one-folder bundle (§8.2)."""

from __future__ import annotations

import os
import sys

# In a frozen bundle, resources live under sys._MEIPASS; in dev, under the project root.
_BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource(*parts: str) -> str:
    """Absolute path to a bundled resource, resolving under _MEIPASS when frozen and the repo in dev."""
    return os.path.join(_BASE, *parts)


def ifcconvert() -> str:
    """Path to the bundled IfcConvert.exe (IFC -> GLB/STP conversion)."""
    return resource("bin", "IfcConvert.exe")


def gltfpack() -> str:
    """Path to the bundled gltfpack.exe (mesh decimation + meshopt compression)."""
    return resource("bin", "gltfpack.exe")


def node() -> str:
    """Bundled portable Node runtime (only needed for Draco compression)."""
    return resource("bin", "node.exe")


def gltf_pipeline() -> str:
    """Bundled gltf-pipeline CLI entry (Draco/KHR_draco_mesh_compression); run via node()."""
    return resource("bin", "gltfpipe", "node_modules", "gltf-pipeline", "bin", "gltf-pipeline.js")


def public_key() -> str:
    """Path to the bundled RSA public key PEM used to verify licenses (§6.2)."""
    return resource("licensing", "public_key.pem")
