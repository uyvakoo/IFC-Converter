# 13 — Implementation Plan: Features 1–5 (Headless Core Pipeline)

> **Status — AS-BUILT (2026-06-25):** this plan is **fully delivered and superseded.** Phase A (M0–M5,
> incl. M5 meshopt **and** real Draco) ✅ — `tests/validate_core.py` **26/26**; Phase B (UI, licensing,
> packaging) and Phase C (release) ✅ too. Suites: core 26/26, phase-B 20/20, UI 27/27, errors 14/14.
> Shipped on `main` (PRs #2–#9). The plan below is kept as the historical de-risk roadmap; for current
> state see [STATUS.md](STATUS.md).

Incremental, de-risk-first plan for the **geometry core** — open → analyze → crop → color → temp →
IfcConvert (GLB/STP) → gltfpack post — built **headless** (no Qt, no licensing) behind a CLI harness so
each feature is provable in isolation. Phase B (UI, licensing, packaging — features 6–10) comes after.

Maps to the README feature numbering: **F1**=ingestion (03), **F2**=filtering/coloring (04),
**F3**=spatial cropping (05), **F4**=conversion pipeline (06), **F5**=AR output/units/Draco (07).
Incorporates accepted decisions **D1** (bundle gltfpack) and **D2** (no `--key`; PyArmor — Phase B).

## Guiding principles
- **`core/*` stays pure and Qt-free** — driven by `cli.py`; this is what makes F1–F5 testable now.
- **Reuse the validated screening code** in `d:\commercial\ifc-recolor-glb\` (`ifc_recolor_to_glb.py`,
  `make_test_ifc.py`, `validate.py`) — don't re-derive styling, mapped-item recursion, the IfcConvert
  wrapper, or the GLB node→GlobalId→material test technique.
- **Every feature ships with assertions** (extend the `validate.py` pattern), run on a **synthetic
  fixture + the real `Building-Architecture.ifc`** already used this session.
- One feature = one merge-able increment with a clear Definition of Done (DoD).

## Target layout (created incrementally)
```
IFC-Converter/
  cli.py                 # headless harness: drives core/ for one or many files
  core/
    pipeline.py          # orchestrates open→analyze→crop→color→write→convert→post (F1..F5 glue)
    analyze.py           # F1: iterator pass → per-element world bounds, class inventory, progress
    filtering.py         # F2: class checklist → keep-set; class→color-group map
    styling.py           # F2: build 4 surface styles; assign (IfcMappedItem-aware)
    cropping.py          # F3: storey Z-bounds, XYZ box, remove_deep mutation
    convert.py           # F4/F5: IfcConvert GLB/STP subprocess + gltfpack post
    report.py            # conversion_report.txt row (shared, lands early)
  bin/                   # IfcConvert.exe (0.8.5), gltfpack.exe (D1)
  tests/
    fixtures/            # synthetic IFCs + a copy/ref of the real model
    test_*.py            # per-feature assertions (validate.py pattern)
  requirements.txt
```

---

## M0 — Skeleton & harness (prerequisite, ~0.5 day)
- Create the project venv (Python 3.11 pinned per D3 decision; 3.12 known-good), `requirements.txt`
  (ifcopenshell 0.8.5, numpy; test deps), and `bin/` with **IfcConvert 0.8.5** + **gltfpack**.
- Port `make_test_ifc.py` into `tests/fixtures` (extend it to emit the 4 color-group classes +
  non-targets + multiple storeys for cropping tests).
- Stub `cli.py` (args: input(s), output dir, targets GLB/STP, classes, storey/XYZ) → calls
  `core/pipeline` (initially a no-op) and writes a report row via `core/report`.
- **DoD:** `python cli.py fixture.ifc out/ --glb` runs end-to-end as a pass-through and writes a report.

## M1 — Feature 1: Ingestion & analyze pass (03)
- `core/pipeline.open(path)`; `core/analyze.run(model, progress_cb)` → returns
  `{bounds_by_id, class_inventory}` using `ifcopenshell.geom.iterator` (lazy), bridging via
  `by_guid`/`by_id` (fixes D6). Emit progress on a cadence.
- Memory-safe: never force-load all geometry; handle `initialize()==False` (no-geometry) cleanly.
- **Reuse:** iterator pattern from `ifc_recolor_to_glb.iter_target_elements` (generalized to "all
  geometric elements", returning bounds too).
- **DoD / verify:** assert class counts vs `model.by_type`; monotonic 0→100 progress; every yielded
  shape resolves to an entity; bounded RSS on the real model. Bounds reused downstream (no double
  triangulation).

## M2 — Feature 2: Filtering & coloring (04)
- `core/filtering`: `class→(group,rgb)` table (Structural #CCCCCC, MEP #3366CC, Architectural #994D1A,
  Cables #E63333); `keep_set(model, selected_groups)` using **inheritance-aware** `is_a`.
- `core/styling`: build the 4 `IfcSurfaceStyle`s once; `assign(model, element, style)` walking
  representation items and **recursing through `IfcMappedItem`** (D12). Direct port of the validated
  `make_red_style` / `_assign_to_item`, generalized to 4 colors.
- **DoD / verify:** one `IfcStyledItem` per styled item, none on excluded elements; after a test
  GLB convert, map each mesh node→GlobalId→material and assert the correct group color (reuse
  `validate.py` T4/T7 technique); a type-authored model exercises the mapped-item branch.

## M3 — Feature 3: Spatial cropping (05) — core IP
- `core/cropping`: `storey_bounds(model, storey)` (via `ContainsElements` + reuse M1 bounds; fallback
  `Elevation ± 3 m`); `xyz_box` override; `keep_set` = class-keep ∩ inside-crop; `apply(model,
  keep_set)` removing the complement with `ifcopenshell.util.element.remove_deep` (fixes D7, D8).
- Evaluate bounds in **world coordinates** (apply placements). Document partial-overlap policy
  (default: keep if bbox intersects).
- **DoD / verify:** kept elements' Z within [zmin,zmax] (±tol); other-storey elements absent from the
  written temp IFC; the written IFC **re-parses cleanly** (no dangling refs); element-count deltas
  logged. This is the highest-risk feature — most test effort here.

## M4 — Feature 4: Conversion pipeline (06)
- `core/convert`: write a **unique** temp IFC (`mkstemp`/`TemporaryDirectory`, guaranteed cleanup —
  fixes D9); `to_glb(temp, out)` = `IfcConvert --y-up --use-material-names` (no `--draco/--optimize`,
  D1); `to_stp(temp, out)` = `IfcConvert --convert-back-units`. Decode UTF-16 CLI output; raise on
  non-zero; **abort-without-CLI** if a Python step raised (matches §4.3).
- **Reuse:** `ifc_recolor_to_glb.convert_to_glb` (subprocess + flag fallback) as the base.
- **DoD / verify:** GLB + STP produced non-empty, exit 0; input IFC sha256 unchanged (write→temp only);
  temp gone after success *and* after a forced mid-pipeline error.

## M5 — Feature 5: AR output — units & Draco/decimation (07)
- `core/convert` post-stage: after the plain GLB, run **gltfpack** (`-i out.glb -o out.glb -cc`) for
  decimate + quantize + Draco (D1, accepted). Bundle `gltfpack.exe` in `bin/`.
- Units: IfcConvert owns scale + `--y-up`; use `ifcopenshell.util.unit.calculate_unit_scale` for the
  **report/sanity check only** (no Python vertex scaling — fixes D5).
- **DoD / verify:** optimized GLB opens in a glTF viewer with correct **Y-up + real-world scale +
  colors**; triangle count / file size reduced within target budget; (client-side) loads on ARKit.
  🔶 still-open: compression target + ARKit Draco-decoder confirmation (track in STATUS.md).

---

## End-to-end exit criteria for Phase A
`python cli.py <real>.ifc out/ --glb --stp --classes Structural,MEP --storey "Level 1"` produces:
- a cropped, correctly colored, Draco-compressed `out.glb` (verified by node→GlobalId→material +
  size/triangle budget), and a clean `out.stp`,
- an accurate `conversion_report.txt` row,
- with the input untouched and no temp residue — all asserted by `tests/`.

This headless core is then wrapped by Phase B (QThread worker + PySide6 UI, licensing, PyInstaller).

## Suggested sequencing / effort (rough)
M0 ~0.5d · M1 ~1d · M2 ~1d (mostly reuse) · **M3 ~2–3d (riskiest)** · M4 ~1d (mostly reuse) ·
M5 ~1–2d (gltfpack tuning + ARKit check). Build in this order; do not let later features start before
the prior DoD passes.
