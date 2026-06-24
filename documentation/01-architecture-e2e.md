# 01 — End-to-End Architecture

## Layered view
```
┌──────────────────────── PySide6 GUI (main / UI thread) ────────────────────────┐
│  License window (modal gate)  →  Main window                                    │
│  left: class checklist · storey dropdown · Manual-XYZ toggle                    │
│  center: file queue (status col) · global progress bar                          │
│  bottom: Start · Output folder · Open Report                                    │
└───────────────▲────────────────────────────────────────────────┬───────────────┘
        signals  │ progress(int), status(file,state), error(msg)  │ start / cancel
                 │                                                 ▼
        ┌────────┴───────────────── QThread worker (batch) ─────────────────────┐
        │  SEQUENTIAL for each file:                                            │
        │   1 open IFC            (core/pipeline)                               │
        │   2 ANALYZE             (core/cropping: storey bounds, inventory)     │
        │   3 CROP (mutate model) (core/cropping: remove out-of-scope entities) │
        │   4 COLOR               (core/styling: assign_item_style + mapped)    │
        │   5 WRITE temp .ifc     (unique temp)                                 │
        │   6 CONVERT             (core/convert: IfcConvert → GLB and/or STP)   │
        │   7 POST (GLB)          (core/convert: Draco / decimate)              │
        │   8 cleanup + report    (core/report)                                 │
        └───────────────────────────────────────────────────────────────────────┘
   Cross-cutting: licensing gate (startup) · logging · _MEIPASS resource paths
```

## Threading model
- **One** background `QThread` worker owns the whole batch. **No parallel IFC parsing** (spec §4.2;
  unsafe — memory corruption). Files processed strictly one at a time.
- Worker → UI **only via Qt signals** (`progress(int)`, `status`, `error`, `finished`). The worker
  never touches widgets directly.
- **Progress** is polled from the iterator's progress during the analyze pass and emitted on a
  cadence (≥ every 2 s, spec §9.4) so the UI shows liveness even on hour-long files.
- **Cancellation is cooperative**: a flag checked between elements and between files. Never hard
  `terminate()` a thread mid-write (corrupts the temp IFC). See [08](08-batch-threading-ui.md).

## Dataflow for ONE file (the canonical sequence)
1. `ifcopenshell.open(path)` → in-memory model (entity graph; cheap, not triangulated).
2. **Analyze**: enumerate via `geom.iterator` to (a) drive progress, (b) gather per-element world
   bounds for storey/box cropping, (c) inventory classes for the report. (Read-only pass.)
3. **Crop (mutate)**: remove elements that fail the class filter *or* fall outside the crop box,
   using `remove_deep` so references don't orphan (D7, D8). What remains is the kept set.
4. **Color**: build the 4 surface styles once; assign to each kept element's representation items,
   recursing through `IfcMappedItem` (D12).
5. `model.write(unique_temp.ifc)` (D9 — unique name, guaranteed cleanup).
6. **Convert** via subprocess:
   - GLB: `IfcConvert --y-up --use-material-names temp.ifc out.glb` (D1 — no `--draco/--optimize`).
   - STP: `IfcConvert --convert-back-units temp.ifc out.stp`.
7. **Post (GLB only)**: Draco compress + decimate with a bundled tool (D1).
8. Delete temp; append a row to `conversion_report.txt`; emit per-file status.

If any Python-side step (1–5) raises, log + abort **this** file, do not call the CLI, continue the
queue (spec §9.1).

## Module responsibility map (suggested; names are illustrative)
| Module | Responsibility | Talks to |
|--------|----------------|----------|
| `app/main` | entry point: license gate → launch UI | licensing, ui |
| `app/paths` | `sys._MEIPASS`-aware resource resolution (bin/ifcconvert.exe, keys) | everything |
| `core/pipeline` | orchestrate steps 1–8 for one file (UI-agnostic, unit-testable) | core/* |
| `core/cropping` | storey Z-bounds, XYZ box, entity removal | ifcopenshell |
| `core/filtering` | class checklist → keep/drop set; class→color map | — |
| `core/styling` | build + assign the 4 surface styles (mapped-item aware) | ifcopenshell.api.style |
| `core/convert` | IfcConvert subprocess (GLB/STP) + Draco post-step | bin tools |
| `core/report` | conversion_report.txt schema + append | filesystem |
| `licensing/*` | machine id, RSA verify, clock guard | cryptography, registry |
| `ui/*` | windows, theming, signal wiring | core via worker |

**Key principle:** `core/*` is pure and headless — it can be driven by a CLI harness with zero Qt.
That is what makes the geometry layer testable and de-riskable independent of the GUI and licensing.

## Cross-references
- Memory/streaming → [03](03-ingestion-streaming.md). Cropping correctness → [05](05-spatial-cropping.md).
- Conversion + Draco reality → [06](06-conversion-pipeline.md) / [07](07-ar-output-units-draco.md).
- All ⚠️ defects → [02-defects-and-remedies](02-defects-and-remedies.md).
