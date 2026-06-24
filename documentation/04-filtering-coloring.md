# 04 — Entity Filtering & Color Coding

## Purpose
Let the user choose which IFC classes to keep (a checklist of 4 groups) and paint each surviving
group a fixed color so the AR GLB is visually legible.

## Inputs / Outputs
- **In:** the set of selected classes from the UI checklist; the in-memory model.
- **Out:** the model with the kept elements' representation items carrying the correct surface style.

## The color groups (spec §3.1)
| Group | Classes | Color (RGB 0–1) | Hex |
|-------|---------|-----------------|-----|
| Structural | `IfcWall`, `IfcSlab`, `IfcColumn`, `IfcBeam` | (0.8, 0.8, 0.8) | #CCCCCC |
| MEP | `IfcPipeSegment`, `IfcDistributionFlowElement`, `IfcDuctSegment` | (0.2, 0.4, 0.8) | #3366CC |
| Architectural | `IfcFurnishingElement`, `IfcDoor`, `IfcWindow`, `IfcSpace` | (0.6, 0.3, 0.1) | #994D1A |
| Cables | `IfcCableSegment` | (0.9, 0.2, 0.2) | #E63333 |

(These are placeholder AR colors and intentionally override existing materials.)

## Architecture & how to handle
**Filtering**
- Map each checkbox group → its class set; the union of selected groups is the **keep set**.
- Match **inheritance-aware**: `element.is_a("IfcWall")` also matches `IfcWallStandardCase`;
  `is_a("IfcSlab")` matches `IfcSlabStandardCase`. Exact class-string comparison silently drops the
  `*StandardCase` subtypes that dominate real IFC2X3 files. (Lesson carried from the screening task.)
- Filtering here is **set membership**; the *removal* of non-kept elements is the cropping step
  (D7) — see [05](05-spatial-cropping.md). Coloring only ever touches kept elements.

**Coloring (the validated technique)**
- Build **one** reusable `IfcSurfaceStyle` per color (4 total), each with an
  `IfcSurfaceStyleShading` whose `SurfaceColour` is the RGB triple and `Transparency` = 0 (opaque).
- For each kept element, walk `element.Representation.Representations[*].Items[*]` and assign the
  group's style to each representation **item** — not the element.
- **Recurse through `IfcMappedItem` (D12):** when an item is an `IfcMappedItem`, descend into
  `item.MappingSource.MappedRepresentation.Items` and assign there. Type-shared geometry routes
  through mapped items; assigning to the per-instance pointer colors nothing → grey GLB.
- `--use-material-names` at convert time makes IfcConvert bake each style into a named glTF material
  (verified: a style named e.g. "RED" becomes a glTF material named "RED").

## Key APIs (named, no code)
- `ifcopenshell.api.style.add_style(model, name=…)` → `IfcSurfaceStyle`.
- `ifcopenshell.api.style.add_surface_style(model, style=…, ifc_class="IfcSurfaceStyleShading",
  attributes={SurfaceColour:{Red,Green,Blue}, Transparency})`.
- `ifcopenshell.api.style.assign_item_style(model, item=…, style=…)`.
- `element.is_a("Ifc…")` (inheritance-aware), `element.Representation.Representations`,
  `rep.Items`, `item.MappingSource.MappedRepresentation.Items`.

## Defects & risks
- **D12** — missing `IfcMappedItem` recursion → uncolored output. High.
- RGB must be **0.0–1.0 floats**, not 0–255.
- `IfcDistributionFlowElement` is a broad MEP supertype — `is_a` on it captures many subtypes; confirm
  that is intended (it likely is, for "keep all MEP").
- Elements with no `Representation` (or only non-body reps) have nothing to color — skip safely.
- Overlap between groups is impossible here (disjoint class sets), but if the client later adds custom
  classes, define precedence.

## Proposed remedies
- Centralize the `class → (group, rgb)` table in `core/filtering` so UI, coloring, and the report all
  read one source of truth.
- Factor the assign-with-mapped-recursion into a single `core/styling` helper reused for all 4 colors.

## Verification (E2E)
- After coloring, assert one `IfcStyledItem` exists per styled representation item, and none on
  excluded elements.
- After conversion, map each GLB mesh node back to its IFC element by GlobalId and assert its glTF
  material equals the expected group color; non-kept classes retain original/absent materials. (This
  node→GlobalId→material proof was used successfully this session — see
  [12-build-order-verification](12-build-order-verification.md).)
- Force a type-authored (mapped-geometry) model and assert the mapped-item branch is exercised and the
  result is colored, not grey.
