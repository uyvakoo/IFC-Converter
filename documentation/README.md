# IFC Converter — Planning Documentation

Study reference for the **"IFC Spatial Cropping & AR Suite"** spec. This is a planning /
architecture pack only — **no application code, no client communication yet.** The goal is to
understand the system feature-by-feature, surface every defect in the supplied spec, and propose
concrete remedies before any commitment.

The core stack (**ifcopenshell 0.8.5 + IfcConvert 0.8.5**) was exercised hands-on during the
screening task, so the technical claims here are empirical, not assumed. Where a doc says
"verified," it means observed on the real binary/library this session.

## How to read
1. Start with [00-system-overview](00-system-overview.md) → [01-architecture-e2e](01-architecture-e2e.md).
2. Read [02-defects-and-remedies](02-defects-and-remedies.md) next — it is the most important file.
   Everything else cross-references defect IDs (`D1`…`D12`).
3. Then walk the pipeline in order: [03](03-ingestion-streaming.md) → [04](04-filtering-coloring.md)
   → [05](05-spatial-cropping.md) → [06](06-conversion-pipeline.md) → [07](07-ar-output-units-draco.md).
4. Then the surrounding systems: [08](08-batch-threading-ui.md), [09](09-licensing-security.md),
   [10](10-packaging-distribution.md), [11](11-error-handling-reporting.md).
5. Close with [12-build-order-verification](12-build-order-verification.md).

## Per-feature doc template
Every feature doc follows the same shape:
**Purpose → Inputs/Outputs → Architecture & how to handle → Key APIs (named, no code) →
Defects & risks (cross-ref Dn) → Proposed remedies → Verification (E2E).**

## Document map
| # | File | Topic |
|---|------|-------|
| ★ | [FINDINGS-SUMMARY](FINDINGS-SUMMARY.md) | **Standalone exec review: section → requirement → result → remedy + standardized package** |
| — | [00-system-overview](00-system-overview.md) | What it is, goals, two value layers, scope/non-goals |
| — | [01-architecture-e2e](01-architecture-e2e.md) | Layers, threads, dataflow, one-file sequence |
| ★ | [02-defects-and-remedies](02-defects-and-remedies.md) | **Defect register D1–D12 + remedies + evidence** |
| 1 | [03-ingestion-streaming](03-ingestion-streaming.md) | Load + lazy iterator + RAM strategy |
| 2 | [04-filtering-coloring](04-filtering-coloring.md) | Class checklist, color groups, styling |
| 3 | [05-spatial-cropping](05-spatial-cropping.md) | **Core IP** — storey/XYZ crop, entity removal |
| 4 | [06-conversion-pipeline](06-conversion-pipeline.md) | Temp IFC → IfcConvert → GLB/STP |
| 5 | [07-ar-output-units-draco](07-ar-output-units-draco.md) | Units, Y-up, Draco/decimation post-step |
| 6 | [08-batch-threading-ui](08-batch-threading-ui.md) | Queue, QThread, progress, cancel, UI |
| 7 | [09-licensing-security](09-licensing-security.md) | Machine ID, RSA, clock guard, obfuscation |
| 8 | [10-packaging-distribution](10-packaging-distribution.md) | PyInstaller one-folder, native deps |
| 9 | [11-error-handling-reporting](11-error-handling-reporting.md) | 5 scenarios + report schema |
| 10 | [12-build-order-verification](12-build-order-verification.md) | De-risk order + acceptance matrix |
| ▶ | [13-implementation-plan](13-implementation-plan.md) | **Incremental code plan for features 1–5 (headless core)** |

Project tracker (status + accepted decisions + roadmap): [STATUS.md](STATUS.md).

## Status legend (used in docs)
- ✅ **Verified** — observed on the real stack this session.
- ⚠️ **Defect** — spec is wrong/contradictory; see register.
- 🔶 **Decision needed** — open question to settle (with client or internally).
- 🔒 **Out of scope here** — deferred to the build phase.

## Top-line takeaways
- The spec's headline conversion command **cannot run as written** (`--draco`/`--optimize` don't
  exist in IfcConvert 0.8.x). "Compressed low-poly AR GLB" is a **second tool**, not a flag (D1).
- The mandated build command is **internally contradictory** (`--key` removed in PyInstaller 6.0) (D2).
- The real engineering risk is **spatial cropping correctness** (entity removal), which the spec
  under-specifies (D7/D8) — not the parts it spends the most words on.
- The geometry pipeline is well-understood and de-riskable now; the DRM/packaging is where the
  schedule risk hides.
