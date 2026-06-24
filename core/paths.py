"""Resource path resolution that works in dev and inside a PyInstaller one-folder bundle (§8.2)."""

from __future__ import annotations

import os
import sys

# In a frozen bundle, resources live under sys._MEIPASS; in dev, under the project root.
_BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource(*parts: str) -> str:
    return os.path.join(_BASE, *parts)


def ifcconvert() -> str:
    return resource("bin", "IfcConvert.exe")


def gltfpack() -> str:
    return resource("bin", "gltfpack.exe")


def public_key() -> str:
    return resource("licensing", "public_key.pem")
