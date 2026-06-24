# 05 — Spatial Cropping (Core IP)

> This is the most under-specified and highest-risk feature. The spec spends few words here but it is
> where the real engineering — and the acceptance risk — lives.

## Purpose
Reduce a model to the elements within a chosen **storey's Z-range** or a manual **XYZ box**, so the
exported STP/GLB contains only the region of interest.

## Inputs / Outputs
- **In:** the model; a crop spec = either `{storey}` or `{xmin..xmax, ymin..ymax, zmin..zmax}`.
- **Out:** a mutated model containing only the kept elements (ready to write to the temp IFC).

## Two cropping modes (spec §3.2)
**A) Storey dropdown (primary)**
- Parse all `IfcBuildingStorey`; populate the dropdown with their names.
- On selection, compute the storey's Z-bounds:
  - Gather elements contained in the storey via the `IfcRelContainedInSpatialStructure` inverse
    (`storey.ContainsElements`).
  - For each, triangulate with `ifcopenshell.geom.create_shape()` and read its world-space bounds;
    take min Z and max Z across all of them.
  - **Fallback:** if no geometry, use `storey.Elevation ± 3.0 m`.

**B) Manual XYZ box (advanced)** — user min/max for X/Y/Z (meters). When the toggle is on, the box
**overrides** the storey crop.

## The architectural correction (D7, D8) — how cropping actually works
The spec's §4.1 implies "filter with `continue` in the iterator loop." That does **not** crop the
written model (the iterator is a read pass; the element still serializes). Cropping must **mutate the
entity model** before `model.write()`:

1. **Decide keep/drop per element** = passes class filter (see [04](04-filtering-coloring.md)) **AND**
   its bounding box satisfies the crop test.
2. **Remove the dropped elements** with `ifcopenshell.util.element.remove_deep(model, element)` so
   placements, materials, and spatial/aggregation relationships don't orphan (D8). Bare
   `model.remove()` leaves a corrupt file.
3. Alternatively, **rebuild** a fresh model containing only kept elements (cleaner for heavy crops,
   more work to wire spatial structure). Pick one strategy and document it.

## Decisions to settle (🔶)
- **Partial-overlap policy:** keep an element if *any* part is inside the box, or only if its
  centroid/whole bbox is inside? Affects walls that straddle a storey boundary. Recommend
  "keep if bbox intersects crop box," documented.
- **Z-only vs full box for storey mode:** storey crop is Z-range only; XYZ mode constrains all axes.
- **Coordinate space:** element bounds must be evaluated in **world coordinates** (apply the element
  placement) before comparing to the crop box. Local-vs-world mismatch is the classic bug here.
- **"Cropping" excludes whole elements; it does not slice solids.** True geometric clipping at the box
  plane is a much larger scope and is not what the spec describes — confirm with the client.

## Key APIs (named, no code)
- `model.by_type("IfcBuildingStorey")`; `storey.Elevation`; `storey.ContainsElements` (inverse of
  `IfcRelContainedInSpatialStructure`).
- `ifcopenshell.geom.create_shape(settings, element)` → shape with world bounds (reuse the analyze
  pass results rather than recomputing).
- `ifcopenshell.util.element.remove_deep(model, element)`.
- `ifcopenshell.util.placement` / `util.shape` helpers for world-space bounds.

## Defects & risks
- **D7** (High) — iterator `continue` ≠ crop. The whole feature hinges on mutation.
- **D8** (Med) — orphaned references from naive removal.
- Recompute cost: triangulating to get bounds is expensive; **reuse the analyze pass bounds** instead
  of calling `create_shape` twice.
- Storey containment is not always complete in real models (elements attached to the building, not a
  storey) — the storey crop may miss/keep unexpected elements; the XYZ box is the deterministic fallback.

## Proposed remedies
- Single source of per-element world bounds computed once in the analyze pass ([03](03-ingestion-streaming.md)),
  consumed by both cropping and the report.
- A pure `core/cropping.keep_set(model, crop_spec, class_keep) -> set[ids]` then a
  `core/cropping.apply(model, keep_set)` that does `remove_deep` on the complement — both unit-testable.

## Verification (E2E)
- Storey mode: assert kept elements' Z-bounds ⊆ [zmin, zmax] (± tolerance) and that elements from other
  storeys are gone from the written temp IFC.
- XYZ mode: assert no kept element's bbox lies fully outside the box; dropped count matches expectation.
- Re-open the written temp IFC and validate it parses cleanly (no dangling refs after `remove_deep`).
- Element-count deltas logged to the report match the crop decision.
