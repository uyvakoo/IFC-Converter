# IFC Converter — Spatial Cropping & AR Suite

Standalone, air-gapped **Windows** desktop app that batch-converts heavy IFC (BIM) files into:

- **STP (STEP)** — precise CAD-grade solid geometry
- **GLB (glTF)** — compressed, low-poly visual assets for mobile AR (iPad / ARKit)

with per-class **color coding**, **storey / XYZ spatial cropping**, RSA **machine-locked licensing**,
and a single-folder **PyInstaller** bundle. Python does filtering / cropping / coloring; the bundled
**IfcConvert** CLI does format conversion; **gltfpack** compresses the GLB.

> Full specification: [project.md](project.md). Architecture, defect register, and live status:
> [documentation/](documentation/) (start at [documentation/README.md](documentation/README.md),
> status in [documentation/STATUS.md](documentation/STATUS.md)).

## Quickstart (development)

```powershell
# Python 3.11 (64-bit)
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts\fetch_binaries.py      # downloads IfcConvert + gltfpack into bin\
```

Headless pipeline (no GUI):

```powershell
.\.venv\Scripts\python cli.py model.ifc --out out --classes Structural,MEP --storey "Ground" --glb --stp --compress
```

GUI:

```powershell
.\.venv\Scripts\python main.py
```

## Build (one-folder .exe)

```powershell
.\.venv\Scripts\pyinstaller main.spec        # -> dist\IFC_Converter\IFC_Converter.exe
.\dist\IFC_Converter\IFC_Converter.exe --selftest
```

## Tests

```powershell
.\.venv\Scripts\python tests\validate_core.py      # geometry pipeline (F1-F5)
.\.venv\Scripts\python tests\validate_phaseb.py    # batch + licensing (F6-F7)
.\.venv\Scripts\python tests\validate_ui.py        # offscreen UI smoke (F8)
```

## Layout
```
core/          geometry pipeline (analyze, filter, color, crop, convert, compress) — Qt-free
licensing/     machine id + RSA license verify + clock-rollback guard
ui/            PySide6 two-window shell + QThread worker
tools/         vendor keygen + license signing (offline)
scripts/       fetch_binaries.py
tests/         assertion suites + fixtures
documentation/ architecture, defect register, status
```

## Notes
- Target Python is **3.11.x** (spec §2). The native binaries are fetched, not committed.
- Licensing modules are obfuscated with PyArmor for production builds.
