# 10 — Packaging & Distribution (PyInstaller One-Folder)

> ✔ **APPROVED (2026-06-23):** no `--key` (use **PyArmor**), keep `--strip`/`--noupx` (D2); **bundle a
> Draco post-processor** (gltfpack / gltf-pipeline) in the `.exe` (D1). See
> [02 — decision log](02-defects-and-remedies.md#decision-log).

## Purpose
Bundle the app + the IfcConvert binary + native libraries into a **single-folder** Windows build that
runs on a clean, Python-less, offline VM.

## Inputs / Outputs
- **In:** the source, `requirements.txt` (pinned), `bin/ifcconvert.exe`, the PyArmor-obfuscated
  licensing modules, a `main.spec`.
- **Out:** `dist/IFC_Converter/` one-folder bundle + a signed test report (the payment gate, spec §8.4).

## Architecture & how to handle (corrected per D2, D4)
- **One-folder** (`--onedir`), not one-file — faster startup and easier native-lib handling.
- **Drive the build from `main.spec`**, not a long CLI flag list (D4: a `.spec` argument makes most CLI
  flags no-ops). Put `datas`, `binaries`, `hiddenimports`, `strip`, `noupx` in the spec; build with
  `pyinstaller main.spec`.
- **Bundle IfcConvert** as data/binary: `bin/ifcconvert.exe` → resolved at runtime via `sys._MEIPASS`
  (spec §8.2). Pin **one** IfcConvert version matching the ifcopenshell wheel (D10; 0.8.5 recommended).
- **Bundle the AR post-tool** (gltfpack / gltf-pipeline) the same way — air-gapped means no downloads
  at runtime (D1).
- **Hidden imports** (spec §8.3, mandatory): `ifcopenshell.express.express_parser` (without it the
  build crashes looking for `express_parser.py`), plus `ifcopenshell.util.unit`,
  `ifcopenshell.geom.serializers`. Add PySide6/Qt plugin collection.
- **Native libraries:** ifcopenshell ships compiled `.pyd` + OpenCASCADE DLLs that PyInstaller does not
  auto-detect. Use `--collect-all ifcopenshell` (or `collect_dynamic_libs`/`collect_data_files` in the
  spec) or imports fail off the build host. Collect Qt platform/style plugins similarly.
- **No `--key`** (removed in PyInstaller 6.0; D2). Obfuscate licensing with **PyArmor** before/around
  the PyInstaller build. Keep `--strip`, `--noupx`.
- **Hooks folder** (spec §8.1): custom PyInstaller hooks for ifcopenshell native libs if `--collect-all`
  is insufficient.

## Code-signing (spec §8.5, optional but recommended)
- Sign the final `.exe` with a code-signing certificate (`signtool`) to reduce SmartScreen/AV friction.
  This helps trust far more than obfuscation does.

## Key tooling (named, no code)
- `pyinstaller main.spec`; spec entries: `Analysis(datas=…, binaries=…, hiddenimports=…)`,
  `EXE(..., strip=True)`, `COLLECT(...)`.
- `sys._MEIPASS` runtime path base for bundled resources.
- `pyarmor gen …` on the licensing package.
- `signtool sign /f cert.pfx …` (optional).

## Defects & risks
- **D2** (High) — `--key` incompatibility; use PyArmor.
- **D4** (Med) — flags + `.spec` mixing; consolidate into the spec.
- **D10** (Low) — IfcConvert version drift; pin one.
- Missing native DLLs only fail on a **clean** machine, not the build host — hence the mandatory
  clean-VM test (spec §8.4).
- UPX (`--noupx` correctly disables) can cause AV false-positives; obfuscated bytecode can too — sign
  the exe to mitigate.
- Antivirus may quarantine machine-locking/obfuscated binaries — test on the target AV.

## Proposed remedies
- Maintain a hand-tuned `main.spec` as the single source of build truth; keep a `hooks/` folder for
  ifcopenshell/Qt native collection.
- Automate a clean-VM smoke test (launch, run a known batch, capture screenshots) as the acceptance
  artifact for §8.4.

## Verification (E2E)
- Build on the dev host; copy `dist/IFC_Converter/` to a **fresh Windows VM with no Python, offline**.
- Launch → license window appears → activate with a test key → run a known batch → GLB + STP produced,
  report written. Capture screenshots → the signed test report (payment gate).
- Confirm IfcConvert and the AR post-tool resolve via `_MEIPASS` (not a dev path) inside the bundle.
