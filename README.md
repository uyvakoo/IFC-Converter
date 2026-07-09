# IFC Converter — Spatial Cropping & AR Suite

Standalone, air-gapped **Windows** desktop app that batch-converts heavy IFC (BIM) files into:

- **STP (STEP)** — precise CAD-grade solid geometry
- **GLB (glTF)** — compressed, low-poly assets for mobile AR (iPad / ARKit)

with per-class **colour coding**, **storey / XYZ spatial cropping**, RSA **machine-locked licensing**,
and a single-folder **PyInstaller** bundle (no Python on the target). Python does
filter / crop / colour; the bundled **IfcConvert** CLI does format conversion; **gltfpack** (meshopt) or
**gltf-pipeline** (Draco) compresses the GLB.

> Spec: [project.md](project.md) · Architecture/defects/status: [documentation/](documentation/) ·
> Build: [BUILD.md](BUILD.md) · Release: [RELEASE.md](RELEASE.md)

## Setup (development)
Python **3.11.x** (64-bit), then:
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --require-hashes -r requirements-dev.txt
.\.venv\Scripts\python scripts\fetch_binaries.py            # IfcConvert + gltfpack + Draco (Node + gltf-pipeline)
.\.venv\Scripts\python scripts\fetch_binaries.py --no-draco     # minimal: skip the Draco toolchain (meshopt only)
```

## End-to-end usage
GUI: `.\.venv\Scripts\python main.py`

Headless pipeline:
```powershell
.\.venv\Scripts\python cli.py model.ifc --out out --classes Structural,MEP,Architectural `
    --storey "Ground" --glb --stp --compress   # --compress-mode draco (default) | meshopt | quantize
```
Classes map to four colour groups (Structural / MEP / Architectural / Cables); `--storey` or
`--xyz xmin,xmax,…` crops; each run writes `conversion_report.txt`.

## Testing each component
```powershell
.\.venv\Scripts\python tests\validate_core.py     # F1-F5 geometry: analyze, filter, colour, crop, GLB/STP, compress (meshopt+Draco)
.\.venv\Scripts\python tests\validate_phaseb.py   # F6-F7: batch queue + RSA licensing (4096-bit, NTP, clock-guard)
.\.venv\Scripts\python tests\validate_ui.py       # F8 UI (offscreen): widgets, worker, render, §9.4 liveness, §4.2 queue
.\.venv\Scripts\python tests\validate_errors.py   # §9 error handling: corrupt/missing input, disk-full, no-match, exit codes
```
CI runs all four on Windows under coverage (core ≥ 80%) plus ruff lint/format, pip-audit, and CodeQL.

## Bundling (one-folder .exe)
```powershell
.\.venv\Scripts\pyinstaller main.spec                         # -> dist\IFC_Converter\
.\dist\IFC_Converter\IFC_Converter.exe --selftest             # expect: selftest: 9/9 OK
.\dist\IFC_Converter\IFC_Converter.exe --cli model.ifc --out out --classes Structural --glb   # headless
```
Everything is driven by `main.spec` (`collect_all` for the native OpenCASCADE libs, mandatory hidden
imports, bundled `bin\` + public key; `--strip`, no `--key`). The `.exe` is self-contained — copy
`dist\IFC_Converter\` to any Windows machine and run it. Details in [BUILD.md](BUILD.md).

## Packaging / release
Push a version tag and `release.yml` builds, self-tests, checksums, and publishes **both** Windows
bundles (meshopt and Draco) to a GitHub Release:
```powershell
git tag v0.1.0; git push origin v0.1.0
```
Local dry-run: `scripts\make_release.ps1 -Variant draco -Tag v0.1.0`. See [RELEASE.md](RELEASE.md).

## Layout
```
core/          geometry pipeline (analyze, filter, colour, crop, convert, compress) — Qt-free
licensing/     machine id + RSA license verify + clock-rollback guard
ui/            PySide6 two-window shell + QThread worker
scripts/       fetch_binaries.py, acceptance_report.py, make_release.ps1
tools/         vendor keygen (RSA keypair)
tests/         four validate_*.py suites + fixtures
documentation/ architecture, defect register, status
```

## Notes
- Native binaries are **fetched, not committed**; the vendor RSA private key never ships.
- Licensing modules can be obfuscated with **PyArmor** (paid) for production builds — see BUILD.md §4.
