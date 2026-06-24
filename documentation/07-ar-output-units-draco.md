# 07 — AR Output: Units, Y-up, and Draco/Decimation

> ✔ **APPROVED (2026-06-23):** project owner confirmed `--draco`/`--optimize` don't exist and
> **authorized bundling a Draco post-processor** (gltfpack recommended / gltf-pipeline) in the final
> `.exe` (D1). See [02 — decision log](02-defects-and-remedies.md#decision-log).

## Purpose
Make the GLB AR-ready for iPad/ARKit: correct real-world scale, +Y up axis, and "highly compressed,
low-poly." This doc separates what IfcConvert does for free from what needs a **separate tool** (D1).

## Inputs / Outputs
- **In:** the plain GLB produced by IfcConvert; the model's unit info.
- **Out:** an AR-grade GLB (correct scale, Y-up, Draco-compressed, decimated).

## Units (spec §5.1, corrected per D5)
- IfcConvert emits **meters** and handles unit conversion itself. **Do not** also scale vertices in
  Python — that double-applies and produces wrong scale.
- Use `ifcopenshell.util.unit.calculate_unit_scale(model)` **only for reporting/validation** (record
  the source unit; sanity-check output extents).
- The spec's "divide by 1000 / ×0.3048 in Python" applies only if you serialize geometry yourself,
  which this design does not.

## Y-up (spec §5.1)
- IFC is Z-up; ARKit/glTF expect +Y up. `IfcConvert --y-up` performs the axis swap during GLB export.
- **Do not** rotate shapes manually in Python (spec §10 agrees) — let the CLI own the transform.

## Draco + decimation — the missing piece (D1)
IfcConvert 0.8.x has **no** `--draco` and **no** `--optimize` (verified). So "glTF + Draco, low-poly"
is a **post-processing stage** on the plain GLB, with a tool that must be bundled for the air-gapped build:

| Need | Tool option | Notes |
|------|-------------|-------|
| Draco mesh compression | `gltf-pipeline -i in.glb -o out.glb -d` | Node tool; widely used; ARKit decoder must support Draco |
| Decimation + quantization + Draco | `gltfpack` (meshoptimizer) | Single native exe; strong size wins; tune to avoid wrecking thin walls |
| Raw Draco encode | Google `draco_encoder` | Lower-level; usually via gltf-pipeline instead |

**Recommendation:** `gltfpack` (single native binary, easy to bundle offline, does decimate +
quantize + optional Draco in one pass). Validate output opens in a glTF viewer **and** on an actual
ARKit device.

## Key APIs / tools (named, no code)
- `ifcopenshell.util.unit.calculate_unit_scale(model)` → (scale, unit) for reporting.
- `IfcConvert --y-up --use-material-names` (scale + axis + colors).
- Post-step: `gltfpack` or `gltf-pipeline -d` (bundled binary, invoked via subprocess).

## Defects & risks
- **D1** (High) — without the post-step there is no compression/low-poly; the "one flag" framing hides
  a whole deliverable (tool selection, bundling, tuning, ARKit verification).
- **D5** (Med) — double unit scaling if Python also scales vertices.
- Draco requires a compatible decoder on the AR side — confirm the client's ARKit pipeline supports it;
  otherwise ship quantized-but-undracoed GLB.
- Aggressive decimation degrades thin/curved geometry — needs per-project ratio tuning.

## Proposed remedies
- Treat AR optimization as its own `core/convert` post-stage with a configurable target (max triangles
  / target size), tested against a real model in an ARKit viewer.
- Add an output-extents sanity check using the unit scale to catch accidental ×1000 errors early.

## Verification (E2E)
- Open the optimized GLB in a glTF viewer: correct orientation (Y-up), real-world size (a 3 m wall is
  ~3 m), colors intact.
- Compare triangle count and file size pre/post optimization; assert within target budget.
- Device test on iPad/ARKit (client-side) — placement scale correct, loads without decoder errors.
