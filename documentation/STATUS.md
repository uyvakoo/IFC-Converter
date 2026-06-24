# IFC Converter — Project Tracker

Standalone, air-gapped Windows desktop app that batch-converts heavy IFC files to **STP** (CAD solids)
and **GLB** (AR assets), with class filtering, color coding, spatial cropping, RSA machine-locked
licensing, and a one-folder PyInstaller bundle. Python does filter/crop/color; **IfcConvert.exe** does
format conversion; a bundled post-processor does GLB compression.

- **Status:** **Phase A + B implemented & packaged.** One-folder PyInstaller bundle **built** and the
  **frozen exe `--selftest` passes 7/7** (native OCC libs + bundled IfcConvert/gltfpack/key load from
  `_MEIPASS`). PyArmor obfuscation of `licensing/` proven (trial). GLB compressor made pluggable
  (meshopt/quantize/draco) for the open D1 decision. Suites: core **22/22**, phase-B **13/13**, UI
  **11/11**. Remaining to ship: real **clean-VM** run, **PyArmor production license**, close **D1** with
  the client. See [Progress](#progress).
- **Spec review:** complete — see [documentation/FINDINGS-SUMMARY.md](documentation/FINDINGS-SUMMARY.md)
  and the defect register [documentation/02-defects-and-remedies.md](documentation/02-defects-and-remedies.md).
- **Architecture:** [documentation/01-architecture-e2e.md](documentation/01-architecture-e2e.md).
- **Docs are Markdown-only** (no image rendering).

---

## Accepted decisions (locked)
| ID | Date | Decision | By | Impact on scope |
|----|------|----------|----|-----------------|
| **D1** | 2026-06-23 | `IfcConvert --draco/--optimize` don't exist; **bundle a Draco post-processor** (gltfpack recommended / gltf-pipeline) in the `.exe` to produce compressed low-poly GLB. | Project owner | Adds a GLB post-processing stage + an extra bundled binary in `./bin/`. Feature 5 owns it. |
| **D2** | 2026-06-23 | **Drop PyInstaller `--key`** (removed in 6.0); obfuscate licensing/hashing with **PyArmor**; keep `--strip` and `--noupx`. | Project owner | Packaging uses PyArmor pass + `main.spec`; no bytecode-cipher flag. |

These supersede the spec's literal text in §5.1 (GLB command) and §6.3/§8.3 (`--key`).

## Open decisions
**Closed (our call, 2026-06-24):**
- **D3** → **pin Python 3.11.x** for the production/bundle build (dev validated on 3.12; 3.11 satisfies
  the client literally and is lowest-risk). `requirements.txt`/`main.spec` target 3.11.
- **D10** → pin **IfcConvert 0.8.5** (+ gltfpack 1.1), matching the bundled wheel.
- **Cropping** → policy implemented = **keep if bbox has positive-length overlap** with the crop box
  (touching excluded); crop excludes **whole elements**, no solid slicing (documented in doc 05).

**Still needs the client:**
- **D1 sub-item (Draco vs meshopt):** gltfpack gives **meshopt** (EXT_meshopt_compression), not
  **KHR_draco**. Recommend meshopt (3× size win, validated) **iff** the client's ARKit/RealityKit
  decoder supports it; otherwise swap the post-step to **gltf-pipeline** for KHR_draco. Need the target
  decoder + compression budget. **Blocks final AR sign-off only**, not the rest of the build.
- Commercial: terms / milestones before handing over full source.

## Standardized stack (pinned)
Python 3.11.x · ifcopenshell 0.8.5 · **IfcConvert 0.8.5** · PySide6 6.6+ · cryptography 42+ ·
machineid 0.3+ · ntplib · **+ gltfpack** (GLB Draco/decimate, D1) · **+ PyArmor** (obfuscation, D2) ·
PyInstaller 6.5+ driven by `main.spec` (no `--key`).

**Corrected commands**
- GLB: `IfcConvert --y-up --use-material-names temp.ifc out.glb` → `gltfpack -i out.glb -o out.glb -cc`
- STP: `IfcConvert --convert-back-units temp.ifc out.stp`
- Build: `pyinstaller main.spec` (`--collect-all ifcopenshell`, hidden imports, `--strip --noupx`, no `--key`)

## Roadmap
**Phase A — headless core pipeline (features 1–5)** ← current.
See [documentation/13-implementation-plan.md](documentation/13-implementation-plan.md).
Open → analyze → crop → color → temp → IfcConvert (GLB/STP) → gltfpack post.

**Phase B — application shell (features 6–10).** Batch queue + PySide6 UI (6/08), licensing + clock
guard (7/09), PyInstaller one-folder + clean-VM (8/10), error handling + report (9/11), build/verify
acceptance (10/12). Planned after Phase A proves out.

## Progress
Headless core built and validated against the multi-storey fixture (`tests/fixtures/fixture.ifc`) —
`python tests/validate_core.py` → **15/15**. CLI works end-to-end (GLB+STP+report).

| Milestone | Feature | Status | Evidence |
|-----------|---------|--------|----------|
| M0 | scaffold + venv + IfcConvert + fixture | ✅ Done | `core/`, `bin/IfcConvert.exe`, `tests/fixtures/make_fixture.py` |
| M1 | F1 ingestion/analyze | ✅ Done | `core/analyze.py` — 7 elems, world Z-bounds, progress 0→100 |
| M2 | F2 filter + color | ✅ Done | `core/filtering.py`,`core/styling.py` — GLB material per element (Structural/MEP/Cables/Arch); IfcMappedItem-aware |
| M3 | F3 spatial crop | ✅ Done | `core/cropping.py` — storey Z-box + XYZ, `root.remove_product`; cropped IFC re-parses clean |
| M4 | F4 conversion | ✅ Done | `core/convert.py`,`core/pipeline.py` — GLB+STP, unique temp + cleanup, `-y`, preflight (fatal), input-untouched |
| M5 | F5 AR Draco | ✅ Done | `core/postprocess.py` + `bin/gltfpack.exe` — real model **27,408→9,248 B (×0.34)**, materials kept |
| F6 | batch/threading core | ✅ Core done | `core/batch.py` — sequential, per-file isolation, cooperative cancel, fatal preflight (UI worker = Phase B) |
| F7 | licensing core | ✅ Core done | `licensing/` — machine id, RSA PKCS1v15 verify, expiry, clock-rollback guard |
| F6/F7 | PySide6 UI shell | ✅ Done (headless-validated) | `ui/` (theme, worker, license_window, main_window) + `main.py` — two windows, QThread worker, cooperative cancel, license gate + RegistryStore |
| F8 | packaging | ✅ Built | `main.spec` → `dist/IFC_Converter/` (317 MB); frozen **`--selftest` 7/7**; `bin/`+key bundled, strip/noupx, no `--key`. Remaining: real clean-VM + PyArmor prod license |
| — | obfuscation (D2) | ✅ Proven (trial) | `pyarmor gen --recursive licensing` → opaque blob, roundtrip still passes; prod needs a PyArmor license |
| — | D1 readiness | ✅ Pluggable | `core/postprocess.py` modes: meshopt (default) / quantize / draco (gltf-pipeline) — flip when client confirms ARKit decoder |
| F9 | error/report | ✅ In code | FatalError/per-file isolation/output-writable/cancel/close-confirm wired; report schema in `core/report.py` |
| F10 | acceptance | 🟡 Matrix in doc 12 | frozen selftest done; full clean-VM signed report pending a VM |

Suites: `tests/validate_core.py` **22/22** (M1–M5), `tests/validate_phaseb.py` **13/13** (F6+F7),
`tests/validate_ui.py` **11/11** (offscreen UI: widgets, license activate, worker→GLB).

**Bugs found & fixed during build (notable):**
- Cables (`IfcCableSegment`) are subtypes of `IfcDistributionFlowElement` → switched to single-group
  precedence (`group_of`, Cables before MEP) instead of raw `is_a` union.
- `remove_deep2` does not delete a product → use `ifcopenshell.api.root.remove_product`.
- IfcConvert won't overwrite without `-y` → added it (was reading stale GLBs).
- `use-world-coords` settings flag makes per-element world bounds a simple vert min/max.
- gltfpack `-si` can't decimate box geometry (already minimal); size win comes from meshopt `-cc`.
- spec §8.3 hidden import `ifcopenshell.geom.serializers` **does not exist** in 0.8.5 (and is unneeded —
  IfcConvert.exe does serialization) → dropped from `main.spec` (build defect, logged).

## Next course of action
Everything build-able on this machine is done and validated. The residual items each need an external
input or asset:
1. **Clean-VM acceptance (F10):** copy `dist/IFC_Converter/` to a fresh Windows VM (no Python, offline),
   run `IFC_Converter.exe --selftest` then a real GUI conversion, capture the **signed test report +
   screenshots** (spec §8.4). Needs a VM — the frozen `--selftest` here is the on-host proxy.
2. **PyArmor production license:** re-run `pyarmor gen --recursive licensing` under a paid license (the
   trial proved integration) and wire the obfuscated `licensing/` into the build before shipping.
3. **Close D1 with the client:** confirm the ARKit/RealityKit decoder. If meshopt → keep default; if it
   needs KHR_draco → set `postprocess` mode `"draco"` and bundle `gltf-pipeline` (+Node) in `bin/`.
4. **Optional:** add a `--cli` passthrough to `main.py` so the frozen exe can run headless batches
   (currently CLI is dev-only via `cli.py`); rebuild on 3.11 for the production bundle (D3).

## Reused, validated assets (from the screening task)
`d:\commercial\ifc-recolor-glb\` — `ifc_recolor_to_glb.py` (styling + IfcMappedItem recursion +
IfcConvert wrapper), `make_test_ifc.py` (synthetic fixture), `validate.py` (assertion harness incl.
GLB node→GlobalId→material proof). These seed features 2 and 4 and the test approach.
