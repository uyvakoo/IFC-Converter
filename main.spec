# -*- mode: python ; coding: utf-8 -*-
# PyInstaller one-folder spec (F8). Build:  pyinstaller main.spec
# Corrected per D2/D4: NO --key (removed in PyInstaller 6.0; use PyArmor on licensing/ separately),
# everything driven from this spec (not CLI flags), strip + noupx.
from PyInstaller.utils.hooks import collect_all

# ifcopenshell ships native .pyd + OpenCASCADE DLLs that are not auto-detected — collect everything.
_ifc_datas, _ifc_bins, _ifc_hidden = collect_all("ifcopenshell")

hiddenimports = _ifc_hidden + [
    "ifcopenshell.express.express_parser",   # MANDATORY (spec §8.3) or runtime crash
    "ifcopenshell.util.unit",
    # NOTE: spec §8.3 also lists "ifcopenshell.geom.serializers" — it does NOT exist in 0.8.5 and is
    # unneeded (serialization is done by the bundled IfcConvert.exe, not Python). Dropped (build defect).
]

# Bundled binaries + the hard-coded public key (resolved at runtime via core.paths/_MEIPASS).
datas = _ifc_datas + [
    ("bin/IfcConvert.exe", "bin"),
    ("bin/gltfpack.exe", "bin"),
    ("licensing/public_key.pem", "licensing"),
]
binaries = _ifc_bins

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["hooks"],
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
