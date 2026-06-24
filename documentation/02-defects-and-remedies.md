# 02 — Defect Register & Remedies

The spec contains factual errors, internal contradictions, and under-specified areas. Each is
logged below with **evidence**, **severity**, a **remedy**, and the **question to put to the client**
later (not now). Severity: High = blocks a payment-gated deliverable as written; Med = wrong but
recoverable; Low/Info = note for honesty/quality.

Legend: ✅ verified on the real stack this session. · ✔ **APPROVED** = remedy signed off by the
project owner (see [decision log](#decision-log)).

---

## D1 — `--draco` / `--optimize` do not exist in IfcConvert 0.8.x  ✅ ✔ APPROVED  High
**Status:** ✔ **APPROVED by project owner (2026-06-23).** Owner confirmed the flags do not exist and
**authorized bundling a Draco post-processor in the final `.exe`.**
**Spec:** §5.1 mandates `IfcConvert --y-up --draco --optimize --use-material-names temp.ifc output.glb`,
and §1 sells GLB as "glTF + Draco … highly compressed, low-poly."
**Evidence:** `IfcConvert.exe -h` on 0.8.5 lists glTF output as plain "Binary glTF v2.0"; the only
glTF-related flags are `--y-up`, `--use-material-names`, `--use-element-*`, `--ecef`. There is **no**
`--draco` and **no** `--optimize`. The mandated command errors on an unrecognized option.
**Impact:** "compressed low-poly AR GLB" is not achievable from IfcConvert alone — it is a **separate
post-processing stage**, i.e. extra tooling that must be bundled for an air-gapped build.
**Approved remedy:** IfcConvert produces a plain GLB, then a **bundled post-processor** compresses it:
- **gltfpack** (meshoptimizer) — recommended: single native exe, easiest to bundle offline; does
  decimate + quantize + optional Draco in one pass, **or**
- `gltf-pipeline -i in.glb -o out.glb -d` (Node-based Draco).
Both are authorized for inclusion in the `.exe`. See [07-ar-output-units-draco](07-ar-output-units-draco.md).
**Still open (🔶):** compression target (triangle/size budget) and confirmation the client's ARKit
decoder supports Draco (else ship quantized-but-undracoed GLB via gltfpack).

## D2 — `--key` removed in PyInstaller 6.0; spec demands 6.5+ *and* `--key`  ✔ APPROVED  High
**Status:** ✔ **APPROVED by project owner (2026-06-23).** Drop `--key`; use **PyArmor** on the
licensing/hashing modules; **keep `--strip` and `--noupx`.**
**Spec:** §2 pins PyInstaller 6.5.0+; §6.3 + §8.3 require `--key "…"` for bytecode encryption.
**Evidence:** PyInstaller removed the bytecode cipher / `--key` option in 6.0 (deprecated in 5.x).
Passing `--key` to a 6.x build is rejected. The two requirements are mutually exclusive.
**Approved remedy:** drop `--key`; obfuscate the licensing/hashing modules with **PyArmor** (spec lists
it as acceptable in §6.3). Keep `--strip`, `--noupx`. See [10](10-packaging-distribution.md),
[09](09-licensing-security.md).

## D3 — "Python 3.11 only, never 3.12" is not true for ifcopenshell 0.8.x  ✅ Med
**Spec:** §2 "CRITICAL WARNING: Use Python 3.11 exactly. Do not use 3.12 or later."
**Evidence:** ifcopenshell 0.8.5 installed and ran end-to-end on **Python 3.12.8** this session
(open, iterator, style API, GLB conversion all fine).
**Remedy:** for a paid deliverable, pinning **3.11** to satisfy the client literally is fine and
lowest-friction — but the stated rationale is outdated. Document that 3.12 works if they prefer it.
🔶 Decision: pin 3.11 (client-literal) vs 3.12 (validated).
**Client question:** "3.11 is fine; note 0.8.x also works on 3.12 if you'd rather. Which do you want pinned?"

## D4 — `main.spec` passed alongside CLI flags (flags get ignored)  Med
**Spec:** §8.3 build command lists many flags **and** ends with `main.spec`.
**Evidence:** when a `.spec` file is given, PyInstaller ignores most command-line build options and
uses the spec. The command is self-contradictory.
**Remedy:** put everything (datas, hiddenimports, binaries, strip/noupx) **in the `.spec`** and run
`pyinstaller main.spec`. See [10](10-packaging-distribution.md).

## D5 — Manual vertex unit-scaling double-applies with IfcConvert  Med
**Spec:** §5.1 says divide vertices by 1000 (mm) / ×0.3048 (ft) in Python, *and* convert the GLB via
IfcConvert (which already emits meters).
**Evidence:** the GLB is produced by IfcConvert, not by serializing Python-scaled vertices; scaling
in both places = wrong scale. Python here only edits the IFC entity model, not mesh vertices.
**Remedy:** let IfcConvert own units; use `ifcopenshell.util.unit.calculate_unit_scale(model)` for
**reporting/validation only**. See [07](07-ar-output-units-draco.md).

## D6 — `shape.geometry.ifc_element` is not the 0.8 iterator bridge  Low
**Spec:** §4.1 "get the element using `shape.geometry.ifc_element`."
**Evidence:** in 0.8 the iterator yields a shape exposing `.guid` / `.id`; you bridge via
`model.by_guid(shape.guid)` / `model.by_id(shape.id)`.
**Remedy:** use `by_guid`/`by_id`. Cosmetic but the snippet won't run as written.
See [03](03-ingestion-streaming.md).

## D7 — Iterator "continue" filter does NOT crop the written model  High
**Spec:** §4.1 implies skipping elements with `continue` inside the iterator loop performs the filter.
**Evidence:** the iterator is a **read/triangulation** pass; skipping an element in the loop only
changes what you *analyze/color*. The element still exists in `model` and is written to the temp IFC,
so IfcConvert still converts it. Real cropping requires editing the model.
**Remedy:** treat iteration as analysis; perform cropping by **removing** unwanted entities from the
model before `model.write()`. See [05](05-spatial-cropping.md).

## D8 — Bare entity removal orphans references  Med
**Evidence:** deleting an element with `model.remove(element)` leaves dangling placements, materials,
`IfcRelContainedInSpatialStructure`/aggregation references, producing an invalid IFC.
**Remedy:** use `ifcopenshell.util.element.remove_deep(model, element)` (cascades dependents safely),
or build a fresh model containing only kept elements. See [05](05-spatial-cropping.md).

## D9 — Fixed temp filename in shared temp dir  Med
**Spec:** §4.3 hard-codes `temp_path = os.path.join(tempfile.gettempdir(), "cropped_model.ifc")`.
**Evidence:** a fixed name in the shared system temp risks collisions (only one file safe at a time,
future-proofing against any concurrency) and leftover files if a run aborts before cleanup.
**Remedy:** unique temp per file via `tempfile.mkstemp(suffix=".ifc")` or a `TemporaryDirectory`;
guarantee cleanup in a `finally`. See [06](06-conversion-pipeline.md).

## D10 — Bundle pinned to IfcConvert 0.8.0; 0.8.5 is current  Low
**Spec:** §8.2 says download IfcConvert 0.8.0.
**Evidence:** 0.8.5 is the current 0.8.x release and is what was validated.
**Remedy:** pin **one** IfcConvert version that matches the bundled ifcopenshell wheel; document it.
0.8.5 recommended. (Flag behavior — e.g. `--use-material-names` — can vary across builds; verify on
the exact pinned binary.)

## D11 — Registry clock-guard is deterrence, not real security  Info
**Spec:** §6.2 stores a timestamp in the registry to detect clock rollback; optional NTP.
**Evidence:** air-gapped = NTP usually unreachable; a user with local admin can edit/clear the HKCU
key. This stops casual clock-tampering only.
**Remedy:** implement as specified but **document the threat model honestly** (anti-casual-tamper).
See [09](09-licensing-security.md).

## D12 — Grey-GLB trap: `assign_item_style` needs IfcMappedItem recursion  ✅ High
**Spec:** §3.1 says assign colors to representation items — but does not mention mapped items.
**Evidence:** type-authored geometry (`IfcWallType`/`IfcSlabType`) is shared via `IfcMappedItem`;
assigning a style to the per-instance mapped item colors nothing → grey GLB. Proven this session that
recursing into `MappingSource.MappedRepresentation.Items` fixes it.
**Remedy:** in styling, recurse through `IfcMappedItem` before assigning. See [04](04-filtering-coloring.md).

---

## Summary table
| ID | Severity | Status | One-line remedy |
|----|----------|--------|-----------------|
| D1 | High | ✔ Approved | Bundle gltfpack/gltf-pipeline post-step (authorized in the `.exe`), not IfcConvert flags |
| D2 | High | ✔ Approved | Drop `--key`; use PyArmor; keep `--strip`/`--noupx` |
| D3 | Med | Proposed | Pin 3.11 to satisfy client, but 3.12 works (decide) |
| D4 | Med | Proposed | Drive build from `main.spec`, not flags+spec |
| D5 | Med | Proposed | IfcConvert owns units; `calculate_unit_scale` for reporting only |
| D6 | Low | Proposed | `by_guid`/`by_id`, not `shape.geometry.ifc_element` |
| D7 | High | Proposed | Crop by mutating the model before write, not iterator `continue` |
| D8 | Med | Proposed | `remove_deep`, not bare `model.remove` |
| D9 | Med | Proposed | Unique temp file + guaranteed cleanup |
| D10 | Low | Proposed | Pin one IfcConvert version (0.8.5) matching the wheel |
| D11 | Info | Proposed | Document clock-guard as anti-casual-tamper only |
| D12 | High | Proposed | Recurse `IfcMappedItem` when assigning styles |

**Net:** three High defects (D1, D7, D12) are technical must-fixes; D2 is a hard contradiction in the
build command. None are blockers to *building a correct product* — they are blockers to building the
product **exactly as the spec literally reads**. That distinction is the core message for the client.

---

## Decision log
| Date | Item | Decision | By |
|------|------|----------|----|
| 2026-06-23 | **D2** PyInstaller `--key` | Drop `--key`; **PyArmor** on licensing/hashing modules; keep `--strip`, `--noupx`. | Project owner |
| 2026-06-23 | **D1** Draco/optimize | Confirmed flags don't exist; **authorized bundling a Draco post-processor** (gltfpack recommended, or gltf-pipeline) in the final `.exe`. | Project owner |

Remaining open (🔶): D1 compression target + ARKit Draco-decoder confirmation; D3 (3.11 vs 3.12);
cropping partial-overlap policy / "no solid slicing"; D10 version pin. D4–D9, D11, D12 are
implementation remedies to apply during the build (no client sign-off needed).
