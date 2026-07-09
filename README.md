# IFC Converter — Spatial Cropping & AR Suite

Standalone, air-gapped **Windows** desktop app that batch-converts heavy IFC (BIM) files into:

- **STP (STEP)** — precise CAD-grade solid geometry
- **GLB (glTF + Draco)** — highly compressed, low-poly assets for mobile AR (default AR output)
- **USDZ** — Apple ARKit / Quick Look native format (iOS AR), derived dependency-free from the GLB

with per-class **colour coding**, **storey / XYZ spatial cropping**, RSA **machine-locked licensing**,
and a single-folder **PyInstaller** bundle (no Python on the target). Python does
filter / crop / colour; the bundled **IfcConvert** CLI does format conversion; **gltfpack** (decimation)
and **gltf-pipeline** (Draco) produce the compressed low-poly AR GLB.

> Spec: [project.md](project.md) · Architecture / defects / status: [documentation/](documentation/) ·
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
    --storey "Ground" --glb --stp --usdz --compress   # --compress-mode draco (default) | meshopt | quantize
```
Classes map to four colour groups (Structural / MEP / Architectural / Cables); `--storey` or
`--xyz xmin,xmax,…` crops; each run writes `conversion_report.txt` (spec §5.2). The `--cli` gate
requires a valid machine-locked `--license` key.

### AR output — Draco + low-poly (default)
The spec asks for a "GLB (glTF + Draco), highly compressed, low-poly" AR asset. IfcConvert has no
`--draco`/`--optimize`, so the app reproduces both as a post-step and makes it the **default**:
`gltfpack -si` decimation (low-poly) → `gltf-pipeline -d` (`KHR_draco_mesh_compression`). On real
detailed geometry this both decimates and compresses (e.g. a 49 MB model: 166,794 → 67,322 triangles,
GLB ×0.12); box geometry (walls/slabs) is already minimal and stays intact. **USDZ** is also produced
for iOS Quick Look, which decodes USDZ natively. See
[documentation/07-ar-output-units-draco.md](documentation/07-ar-output-units-draco.md).

## Licensing & security (§6)
RSA-4096, machine-locked. A licence is `{machine_hash, expiry, signature}`; the vendor signs
`(machine_hash, expiry)` with the **private key** (kept only by the vendor, never shipped). The app
verifies with the **public key** (PKCS#1 v1.5 + SHA-256), checks the machine hash and expiry, and a
**clock-rollback guard** (HKCU registry + optional NTP) blocks setting the clock back. Failures show a
single "Invalid license - contact vendor". The guard fails safe — a corrupt/unreadable registry stamp
degrades to first-run rather than crashing at launch.

Production builds **hard-code the public key** in `licensing/core.py` and **Cython-compile** the
licensing modules to native `licensing/*.pyd` (free — no PyArmor), so there is no loose `public_key.pem`
to swap and no licence `.py`/`.pyc` to decompile. See
[documentation/09-licensing-security.md](documentation/09-licensing-security.md) and BUILD.md §4.

## Testing each component
```powershell
.\.venv\Scripts\python tests\validate_core.py     # F1-F5 geometry: analyze, filter, colour, crop, GLB/STP/USDZ, Draco + low-poly proof
.\.venv\Scripts\python tests\validate_phaseb.py   # F6-F7: batch queue + RSA licensing (4096-bit, NTP, clock-guard, hard-coded key)
.\.venv\Scripts\python tests\validate_ui.py       # F8 UI (offscreen): widgets, worker, render, §9.4 liveness, §4.2 queue
.\.venv\Scripts\python tests\validate_errors.py   # §9 error handling: corrupt/missing input, disk-full, no-match, exit codes
```
CI runs all four on Windows under coverage (core ≥ 80%) plus ruff lint/format, pip-audit, and CodeQL.
Frozen-bundle acceptance: `scripts/draco_check.py`, `scripts/cli_exit_codes.py`, `scripts/acceptance_report.py`.

## Bundling (one-folder .exe)
```powershell
.\.venv\Scripts\pyinstaller main.spec                         # -> dist\IFC_Converter\
.\dist\IFC_Converter\IFC_Converter.exe --selftest             # expect: selftest: 9/9 OK
.\dist\IFC_Converter\IFC_Converter.exe --cli model.ifc --out out --classes Structural --glb --license key.key
```
Everything is driven by `main.spec` (`collect_all` for the native OpenCASCADE libs, mandatory hidden
imports, bundled `bin\`; `--strip`, no `--key`). The `.exe` is self-contained — copy
`dist\IFC_Converter\` to any Windows machine and run it. Details in [BUILD.md](BUILD.md).

## Packaging / release
Push a version tag and `release.yml` builds (obfuscated by default, §6.3), self-tests, checksums, and
publishes **both** Windows bundles (meshopt and Draco) to a GitHub Release:
```powershell
git tag v0.1.0; git push origin v0.1.0
```
Local dry-run: `scripts\make_release.ps1 -Variant draco -Tag v0.1.0` (add `-NoObfuscate` to skip the
Cython step). See [RELEASE.md](RELEASE.md).

## Layout
```
core/          geometry pipeline (analyze, filter, colour, crop, convert, compress, usdz) — Qt-free
licensing/     machine id + RSA license verify (hard-coded key) + clock-rollback guard
ui/            PySide6 two-window shell + QThread worker
scripts/       fetch_binaries, obfuscate_licensing, acceptance_report, draco_check, cli_exit_codes, make_release
tools/         vendor keygen + sign_license (RSA keypair, offline)
tests/         four validate_*.py suites + fixtures
documentation/ architecture, defect register, status
```

## Notes
- Native binaries are **fetched, not committed**; the vendor RSA private key never ships.
- Licensing hardening uses **free Cython** compilation to `.pyd` (spec §6.3 "strongly recommended";
  PyArmor is not required) — default in release builds, see BUILD.md §4.
