# IFC Converter — Project Tracker

Standalone, air-gapped Windows desktop app that batch-converts heavy IFC files to **STP** (CAD solids)
and **GLB** (AR assets), with class filtering, color coding, spatial cropping, RSA machine-locked
licensing, and a one-folder PyInstaller bundle. Python does filter/crop/color; **IfcConvert.exe** does
format conversion; a bundled post-processor does GLB compression.

- **Status:** **Shipped on `main` (PRs #2–#9 merged, CI + CodeQL green).** Features F1–F8, all five §9
  error scenarios, RSA licensing (**4096-bit key + NTP** cross-check), AR compression in **both**
  meshopt (default) **and** real **Draco** (`KHR_draco_mesh_compression`), headless `--cli`, and a
  tag-triggered **release workflow** (meshopt + Draco Windows bundles). Frozen exe **`--selftest` 9/9**.
  Suites: core **26/26**, phase-B **20/20**, UI **27/27**, errors **14/14**; core coverage **92%**.
  Every defect **D1–D12 resolved in code**. Residual (owner): clean-VM signed acceptance + a PyArmor
  production license. A real-world evidence pack (GUI + GLB renders + CI status) was captured. See
  [Progress](#progress).
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

**Resolved (as-built):**
- **D1 sub-item (Draco vs meshopt):** no longer a blocker — the product ships **both**. meshopt
  (`EXT_meshopt_compression`, default) **and** real **Draco** (`KHR_draco_mesh_compression` via
  gltf-pipeline) are implemented and selectable (`--compress-mode` / UI dropdown); the release publishes
  a separate Draco bundle. The client picks the backend their decoder supports — no code change.

**Still needs the client / owner:**
- Commercial: terms / milestones before handing over full source.
- Clean-VM signed acceptance (§8.4) + a PyArmor production license (trial integration proven).

## Standardized stack (pinned)
Python 3.11.x · ifcopenshell 0.8.5 · **IfcConvert 0.8.5** · PySide6 6.6+ · cryptography 42+ ·
machineid 0.3+ · ntplib · **+ gltfpack** (GLB Draco/decimate, D1) · **+ PyArmor** (obfuscation, D2) ·
PyInstaller 6.5+ driven by `main.spec` (no `--key`).

**Corrected commands**
- GLB: `IfcConvert --y-up --use-material-names temp.ifc out.glb` → `gltfpack -i out.glb -o out.glb -cc`
- STP: `IfcConvert --convert-back-units temp.ifc out.stp`
- Build: `pyinstaller main.spec` (`--collect-all ifcopenshell`, hidden imports, `--strip --noupx`, no `--key`)

## Roadmap
**Phase A — headless core pipeline (features 1–5)** ✅ done.
Open → analyze → crop → color → temp → IfcConvert (GLB/STP) → gltfpack/Draco post.

**Phase B — application shell (features 6–10)** ✅ done. Batch queue + PySide6 UI (6/08), licensing +
clock guard (7/09), PyInstaller one-folder + `--cli` (8/10), full §9 error handling + report (9/11),
build/verify + release workflow (10/12).

**Phase C — distribution** ✅ done. Tag-triggered `release.yml` → meshopt + Draco Windows bundles.

## Progress
Full product built, validated, and packaged. Frozen exe runs real conversions (GLB/STP/crop/meshopt/
Draco) headlessly (`--cli`) and via the GUI; `--selftest` 9/9.

| Milestone | Feature | Status | Evidence |
|-----------|---------|--------|----------|
| M0 | scaffold + venv + IfcConvert + fixture | ✅ Done | `core/`, `bin/IfcConvert.exe`, `tests/fixtures/make_fixture.py` |
| M1 | F1 ingestion/analyze | ✅ Done | `core/analyze.py` — 7 elems, world Z-bounds, progress 0→100 |
| M2 | F2 filter + color | ✅ Done | `core/filtering.py`,`core/styling.py` — GLB material per element (Structural/MEP/Cables/Arch); IfcMappedItem-aware |
| M3 | F3 spatial crop | ✅ Done | `core/cropping.py` — storey Z-box + XYZ, `root.remove_product`; cropped IFC re-parses clean |
| M4 | F4 conversion | ✅ Done | `core/convert.py`,`core/pipeline.py` — GLB+STP, unique temp + cleanup, `-y`, preflight (fatal), input-untouched |
| M5 | F5 AR compress | ✅ Done | `core/postprocess.py` — meshopt (gltfpack) **27,408→9,248 B (×0.34)** *and* real **Draco** (gltf-pipeline, `KHR_draco_mesh_compression`) **→9,736 B (×0.36)**, materials kept; selectable CLI/UI |
| F6 | batch/threading core | ✅ Core done | `core/batch.py` — sequential, per-file isolation, cooperative cancel, fatal preflight (UI worker = Phase B) |
| F7 | licensing core | ✅ Core done | `licensing/` — machine id, RSA PKCS1v15 verify, expiry, clock-rollback guard |
| F6/F7 | PySide6 UI shell | ✅ Done (headless-validated) | `ui/` (theme, worker, license_window, main_window) + `main.py` — two windows, QThread worker, cooperative cancel, license gate + RegistryStore |
| F8 | packaging | ✅ Built | `main.spec` → `dist/IFC_Converter/`; frozen **`--selftest` 9/9**; `--cli` headless mode; `bin/`+key bundled, strip/noupx, no `--key`. Tag-triggered `release.yml` publishes meshopt + Draco bundles (`RELEASE.md`). Remaining: clean-VM + PyArmor prod license |
| — | obfuscation (D2) | ✅ Proven (trial) | PyArmor on `licensing/` proven; path documented in `BUILD.md` §4; prod needs a paid license |
| — | D1 | ✅ Built (both) | `core/postprocess.py` meshopt (default) **+ real Draco** (gltf-pipeline); `--with-draco` fetch + Draco release artifact |
| F9 | error/report | ✅ Done | All five §9 scenarios: corrupt/missing input, no-write-permission, disk-full (preflight+ENOSPC), >1h liveness, no-match; FatalError/per-file isolation; `core/report.py` schema; exit codes asserted |
| F10 | acceptance | 🟡 Owner | frozen `--selftest` + `scripts/acceptance_report.py` (5/5) + evidence pack done; clean-VM signed report pending an isolated VM |

Suites: `tests/validate_core.py` **26/26** (M1–M5 + real Draco), `tests/validate_phaseb.py` **20/20**
(F6+F7, 4096-bit key, NTP, real registry), `tests/validate_ui.py` **27/27** (offscreen UI: widgets,
license activate, worker→GLB, §9.4 liveness, non-blank render), `tests/validate_errors.py` **14/14**
(§9 scenarios + in-process exit codes). Core coverage **92%**.

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
The product is feature-complete, validated, and packaged on `main`. Items 3 and 4 below are **done**;
only the two owner/external residuals remain:
1. **Clean-VM acceptance (F10):** copy `dist/IFC_Converter/` to a fresh Windows VM (no Python, offline),
   run `IFC_Converter.exe --selftest` then a real GUI conversion, capture the **signed test report +
   screenshots** (spec §8.4). Needs a VM — frozen `--selftest` + `scripts/acceptance_report.py` (5/5) +
   the evidence pack are the on-host proxy.
2. **PyArmor production license:** re-run `pyarmor gen --recursive licensing` under a paid license (the
   trial proved integration) and wire the obfuscated `licensing/` into the build before shipping.
3. ~~Close D1 with the client~~ — **done:** both meshopt and real Draco ship; selectable at runtime/build.
4. ~~`--cli` passthrough~~ — **done** (PR #6); the frozen exe runs headless batches; build pinned to 3.11.
5. **Cut the first release** when ready: push a `vX.Y.Z` tag → `release.yml` publishes the meshopt +
   Draco bundles (see `RELEASE.md`).

## Reused, validated assets (from the screening task)
`d:\commercial\ifc-recolor-glb\` — `ifc_recolor_to_glb.py` (styling + IfcMappedItem recursion +
IfcConvert wrapper), `make_test_ifc.py` (synthetic fixture), `validate.py` (assertion harness incl.
GLB node→GlobalId→material proof). These seed features 2 and 4 and the test approach.
