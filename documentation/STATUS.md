# IFC Converter — Project Tracker

Standalone, air-gapped Windows desktop app that batch-converts heavy IFC files to **STP** (CAD solids),
**GLB (glTF + Draco)** (AR assets), and **USDZ** (iOS AR), with class filtering, colour coding, spatial
cropping, RSA machine-locked licensing, and a one-folder PyInstaller bundle. Python does
filter/crop/colour; **IfcConvert.exe** does format conversion; a bundled post-processor
(**gltfpack + gltf-pipeline**) produces the compressed, low-poly Draco GLB.

- **Status:** **Shipped on `main`, CI + CodeQL green.** Features F1–F8, all five §9 error scenarios, RSA
  licensing (**4096-bit key + NTP** cross-check + clock-rollback guard), **Draco-compressed low-poly GLB
  as the default AR output** (`KHR_draco_mesh_compression`), **USDZ** for iOS Quick Look, headless
  `--cli` (licence-gated), and a tag-triggered **release workflow** (meshopt + Draco Windows bundles,
  obfuscated by default). Frozen exe **`--selftest` 9/9**.
  Suites: core **45/45**, phase-B **29/29**, UI **33/33**, errors **14/14**; core coverage ≥ 80%.
  Every defect **D1–D12 resolved in code**.
- **Spec review:** complete — see [FINDINGS-SUMMARY.md](FINDINGS-SUMMARY.md) and the defect register
  [02-defects-and-remedies.md](02-defects-and-remedies.md).
- **Architecture:** [01-architecture-e2e.md](01-architecture-e2e.md).
- **Docs are Markdown-only** (no image rendering).

---

## Accepted decisions (locked)
| ID | Date | Decision | Impact on scope |
|----|------|----------|-----------------|
| **D1** | 2026-06-23 | `IfcConvert --draco/--optimize` don't exist; **bundle a Draco post-processor** (gltfpack decimation + gltf-pipeline Draco) in the `.exe` to produce a compressed, low-poly GLB — now the **default** AR output. | GLB post-processing stage + bundled Node/gltf-pipeline in `./bin/`. Feature 5 owns it. |
| **D2** | 2026-06-23 | **Drop PyInstaller `--key`** (removed in 6.0); obfuscate licensing/hashing with **free Cython → native `.pyd`** (not PyArmor, which is paid); keep `--strip` and `--noupx`. | `scripts/obfuscate_licensing.py`; default in release builds. |

These supersede the spec's literal text in §5.1 (GLB command) and §6.3/§8.3 (`--key`). §6.3 obfuscation
is *"strongly recommended"* — satisfied for free with Cython.

## Closed decisions
- **D3** → pin **Python 3.11.x** for the production/bundle build. `requirements.txt`/`main.spec` target 3.11.
- **D10** → pin **IfcConvert 0.8.5** (+ gltfpack 1.1).
- **Cropping** → keep an element if its bbox has **positive-length overlap** with the crop box (touching
  excluded); crop excludes whole elements, no solid slicing (doc 05).
- **D1 sub-item (Draco vs meshopt):** resolved — **Draco is the default**; meshopt/quantize remain
  selectable (`--compress-mode` / UI dropdown). The client picks the backend their AR decoder supports.

## Still needs the client / owner
- **Clean-VM signed acceptance (§8.4):** signed report + screenshots from a fresh Windows VM (the frozen
  `--selftest` 9/9 + `scripts/acceptance_report.py` 5/5 + evidence pack are the on-host proxy).
- **A1 (client acceptance):** the Draco/low-poly post-step realizes §5.1's `--draco --optimize` (those
  flags don't exist) — a sign-off, not a code change.
- Commercial: terms / milestones before handing over full source.

## Standardized stack (pinned)
Python 3.11.x · ifcopenshell 0.8.5 · **IfcConvert 0.8.5** · PySide6 6.6+ · cryptography 42+ ·
py-machineid · ntplib · **gltfpack 1.1** (decimation/meshopt) · **Node + gltf-pipeline** (Draco) ·
**Cython** (free licensing obfuscation, D2) · PyInstaller 6.5+ driven by `main.spec` (no `--key`).

**Corrected commands**
- GLB (default, Draco): `IfcConvert --y-up --use-material-names temp.ifc out.glb` →
  `gltfpack -si <r> out.glb` (low-poly) → `gltf-pipeline -d out.glb` (`KHR_draco_mesh_compression`)
- STP: `IfcConvert --convert-back-units temp.ifc out.stp`
- Build: `pyinstaller main.spec` (`collect_all` ifcopenshell, hidden imports, `--strip --noupx`, no `--key`)

## Progress
Full product built, validated, and packaged. Frozen exe runs real conversions (GLB/STP/USDZ/crop/Draco)
headlessly (`--cli`, licence-gated) and via the GUI; `--selftest` 9/9.

| Milestone | Feature | Status | Evidence |
|-----------|---------|--------|----------|
| M1 | F1 ingestion/analyze | ✅ | `core/analyze.py` — lazy geom iterator, world Z-bounds, progress 0→100 |
| M2 | F2 filter + colour | ✅ | `core/filtering.py`,`core/styling.py` — exact per-group colours, IfcMappedItem-aware, material override |
| M3 | F3 spatial crop | ✅ | `core/cropping.py` — storey Z-box + XYZ, `root.remove_product`; cropped IFC re-parses clean |
| M4 | F4 conversion | ✅ | `core/convert.py`,`core/pipeline.py` — GLB+STP+USDZ, unique temp + cleanup, `-y`, preflight (fatal), input-untouched |
| M5 | F5 AR compress | ✅ | `core/postprocess.py` — **Draco default** (gltfpack `-si` low-poly → gltf-pipeline `-d`, `KHR_draco_mesh_compression`), meshopt/quantize selectable; colours kept |
| M6 | F6 USDZ | ✅ | `core/usdz.py` — dependency-free GLB→USDZ (Apple ARKit / Quick Look), Y-up, colours preserved |
| F6 | batch/threading | ✅ | `core/batch.py`,`ui/worker.py` — sequential, per-file isolation, cooperative cancel, fatal preflight |
| F7 | licensing | ✅ | `licensing/` — machine id, RSA PKCS1v15 verify (**hard-coded 4096-bit public key**), expiry, clock-rollback guard (fail-safe) |
| F8 | UI shell | ✅ | `ui/` + `main.py` — two windows, QThread worker, cooperative cancel, licence gate + RegistryStore |
| F8 | packaging | ✅ | `main.spec` → `dist/IFC_Converter/`; frozen **`--selftest` 9/9**; licence-gated `--cli`; strip/noupx, no `--key`. Tag-triggered `release.yml` publishes meshopt + Draco bundles (obfuscated) |
| — | obfuscation (D2) | ✅ | `scripts/obfuscate_licensing.py` — free Cython `licensing/*.pyd` with the hard-coded key baked in; default in release builds |
| F9 | error/report | ✅ | All five §9 scenarios; FatalError/per-file isolation; `core/report.py` schema (§5.2); exit codes asserted (`scripts/cli_exit_codes.py` 12/12) |
| F10 | acceptance | 🟡 Owner | frozen `--selftest` + `scripts/acceptance_report.py` (5/5) + `scripts/draco_check.py` + evidence pack done; clean-VM signed report pending an isolated VM |

Suites: `validate_core.py` **45/45** (M1–M6 + Draco/low-poly proof), `validate_phaseb.py` **29/29**
(F6+F7, 4096-bit key, NTP, real registry, clock-guard fail-safe, hard-coded-key swap rejected),
`validate_ui.py` **33/33** (offscreen UI), `validate_errors.py` **14/14** (§9 + exit codes).

## Next course of action
Feature-complete, validated, and packaged on `main`. Remaining:
1. **Clean-VM acceptance (F10):** copy `dist/IFC_Converter/` to a fresh Windows VM (no Python, offline),
   run `--selftest` then a real GUI conversion, capture the **signed report + screenshots** (§8.4).
2. **A1 client sign-off:** accept the Draco/low-poly post-step as the realization of §5.1.
3. **Cut the first release:** push a `vX.Y.Z` tag → `release.yml` publishes the obfuscated meshopt +
   Draco bundles (see `RELEASE.md`).
