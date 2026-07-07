# -*- mode: python ; coding: utf-8 -*-
# PyInstaller one-folder spec (F8). Build:  pyinstaller main.spec
# Corrected per D2/D4: NO --key (removed in PyInstaller 6.0; use PyArmor on licensing/ separately),
# everything driven from this spec (not CLI flags), strip + noupx.
import os

from PyInstaller.utils.hooks import collect_all

# ifcopenshell ships native .pyd + OpenCASCADE DLLs that are not auto-detected — collect everything.
_ifc_datas, _ifc_bins, _ifc_hidden = collect_all("ifcopenshell")

# Licensing dependencies, declared explicitly. Production builds Cython-compile licensing/ to native
# .pyd (scripts/obfuscate_licensing.py, spec §6.3) — that HIDES these imports from PyInstaller's static
# analysis, so machineid/cryptography/ntplib must be pulled in by name or the obfuscated exe crashes with
# ModuleNotFoundError. Harmless for the un-obfuscated build (already collected via source).
_crypto_datas, _crypto_bins, _crypto_hidden = collect_all("cryptography")

hiddenimports = _ifc_hidden + _crypto_hidden + [
    "ifcopenshell.express.express_parser",   # MANDATORY (spec §8.3) or runtime crash
    "ifcopenshell.util.unit",
    "cli",  # enables `IFC_Converter.exe --cli ...` headless batch conversion
    # NOTE: spec §8.3 also lists "ifcopenshell.geom.serializers" — it does NOT exist in 0.8.5 and is
    # unneeded (serialization is done by the bundled IfcConvert.exe, not Python). Dropped (build defect).
    "machineid",  # licensing/core.py — machine hash (§6.1)
    "ntplib",     # licensing/clockguard.py — optional NTP clock check (§6.2)
    "cryptography.hazmat.primitives.hashes",
    "cryptography.hazmat.primitives.serialization",
    "cryptography.hazmat.primitives.asymmetric.padding",
    "cryptography.exceptions",
    # qt-material renders SVG at runtime (theme icons). It's imported dynamically, so PyInstaller doesn't
    # see it — it was only bundled because matplotlib's Qt backend happened to pull QtSvg. Now that
    # matplotlib is excluded, declare it explicitly or the light theme loses its SVG assets.
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
]

# Bundled binaries + the hard-coded public key (resolved at runtime via core.paths/_MEIPASS).
datas = _ifc_datas + _crypto_datas + [
    ("bin/IfcConvert.exe", "bin"),
    ("bin/gltfpack.exe", "bin"),
    ("licensing/public_key.pem", "licensing"),
]

# Optional Draco backend (fetched via fetch_binaries.py --with-draco). Bundled only when present, so
# the default build is unaffected. node.exe + the gltf-pipeline npm tree power KHR_draco_mesh_compression.
if os.path.isfile("bin/node.exe"):
    datas.append(("bin/node.exe", "bin"))
if os.path.isdir("bin/gltfpipe"):
    for _root, _dirs, _files in os.walk("bin/gltfpipe"):
        for _f in _files:
            _src = os.path.join(_root, _f)
            datas.append((_src, os.path.relpath(_root, ".")))

binaries = _ifc_bins + _crypto_bins

# Dev-only / transitively-pulled packages the runtime never imports — excluded to trim the bundle.
# matplotlib (+ its Tk backend) is the big one (~tens of MB, drags in Tcl/Tk); trimesh/Cython/pytest are
# build/test tooling. None appear in the main.py import graph (core/ui/cli/licensing); verified by a
# post-exclude --selftest 9/9. Add here, never to hiddenimports.
excludes = [
    "matplotlib",
    "tkinter",
    "_tkinter",
    "trimesh",
    "Cython",
    "pytest",
    "IPython",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["hooks"],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="IFC_Converter",
    debug=False,
    strip=True,         # --strip
    upx=False,          # --noupx (UPX trips AV false-positives)
    console=False,      # windowed GUI app
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=True, upx=False, name="IFC_Converter",
)
