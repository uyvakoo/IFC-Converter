# 03 — IFC Ingestion & Geometry Streaming

## Purpose
Open potentially large IFC files and process their geometry **element-by-element** without loading
all triangulated meshes into RAM at once. Provide a progress signal for the UI.

## Inputs / Outputs
- **In:** a path to an `.ifc` file (IFC2X3 / IFC4 / IFC4X3).
- **Out:** an in-memory `ifcopenshell` model (entity graph) + a per-element enumeration used by the
  analyze pass (cropping bounds, class inventory, progress).

## Architecture & how to handle
Two distinct concepts that the spec blurs (see D7):
1. **The entity model** — `ifcopenshell.open(path)` parses the STEP file into an in-memory object
   graph (entities and their attributes). This is comparatively light: it is *not* triangulated
   geometry. Filtering/coloring/cropping all operate here, then `model.write()` serializes it.
2. **Triangulated geometry** — produced lazily by the **geometry iterator**, which runs the OCC/CGAL
   kernel per element. This is the heavy part and the reason for streaming.

**Streaming pattern (the analyze pass):**
- Build `ifcopenshell.geom.settings()`.
- Construct `ifcopenshell.geom.iterator(settings, model, num_threads)`.
- `initialize()` (returns False if the file has no geometry at all → handle gracefully).
- Loop: `get()` the current shape → bridge to the entity → record what you need → `next()` until exhausted.
- Each shape carries triangulated data and bounds; only one element's mesh is materialized at a time.

**Bridging shape → entity (D6):** use `model.by_guid(shape.guid)` (stable) or `model.by_id(shape.id)`.
Do **not** rely on `shape.geometry.ifc_element` (not the 0.8 API).

**Why not load everything:** the spec's §10 rule — never use `ifcopenshell.file(..., apply=True)` or
otherwise force all geometry — is correct. The iterator is the memory-safe path.

## Key APIs (named, no code)
- `ifcopenshell.open(path)` → model.
- `ifcopenshell.geom.settings()` → settings object.
- `ifcopenshell.geom.iterator(settings, model, n_threads)` → `initialize()`, `get()`, `next()`.
- `iterator.progress()` → integer percent for the UI.
- `model.by_guid(guid)` / `model.by_id(id)` → entity bridge.
- `model.schema` → IFC2X3 / IFC4 / IFC4X3 (log it; entity availability differs slightly).

## Role of the iterator in THIS app
- ✅ **Enumerator + bounds source + progress driver** for the analyze pass.
- ❌ **Not** the mechanism that crops or colors. Skipping an element with `continue` here does not
  remove it from the written model (D7). Cropping/coloring happen on the entity model afterward.
- It also conveniently skips spatial/abstract entities (only yields things with geometry), which is
  useful when computing storey bounds.

## Defects & risks
- **D7** — treating iterator `continue` as the filter. Mitigate by keeping iteration read-only and
  mutating the model separately. See [05](05-spatial-cropping.md).
- **D6** — wrong shape→entity bridge.
- **Threading:** the iterator's `num_threads` (geometry kernel) is independent of the Qt worker
  thread. Keep IFC parsing itself sequential across files (spec §4.2, D-note).
- **Progress granularity:** emit on a timer/cadence (≥2 s) rather than every element to avoid UI
  signal floods (spec §9.4).

## Proposed remedies
- Encapsulate as a headless `core/pipeline.analyze(model)` returning `(bounds_by_element,
  class_inventory)` plus a progress callback — fully testable without Qt.
- Guard `initialize() == False` (no geometry) as a clean "nothing to convert" outcome, logged.

## Verification (E2E)
- Open a known IFC; assert `schema` and entity counts by class (e.g. via `model.by_type`).
- Run the analyze pass; assert it yields the expected number of geometric elements and a monotonic
  progress sequence 0→100.
- Confirm peak memory stays bounded on a large model (process RSS sampled during the loop).
- Bridge check: every yielded `shape.guid` resolves to a real entity via `by_guid`.
