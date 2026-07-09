# 12 — Build Order & Verification

## Purpose
Sequence the work to de-risk early, and define how each layer is proven end-to-end. Documentation only
— this is the recommended plan, not an implementation.

## Recommended build order (de-risk first)
1. **Headless core pipeline** — open → filter → crop → color → temp → IfcConvert → GLB/STP, driven by a
   tiny CLI harness (no Qt, no licensing). *This is the screening pipeline extended with cropping + STP.*
   Prove on a synthetic fixture **and** a real model. ← highest technical value, lowest scaffolding.
2. **Spatial cropping correctness** — storey Z-bounds + XYZ box + entity removal (`remove_deep`),
   validated by element membership and re-parse of the written temp IFC (D7/D8).
3. **AR optimization** — Draco/decimation post-step (gltfpack/gltf-pipeline), validated in a glTF viewer
   and on an ARKit device (D1).
4. **Batch + UI** — wrap the proven core in a `QThread` worker + PySide6 windows; progress + cancel.
5. **Licensing + clock guard** — isolated, unit-tested with a throwaway key pair (D2/D11).
6. **PyInstaller one-folder + clean-VM test** — native-dep collection, `_MEIPASS`, signed test report
   (payment gate, §8.4).
7. **Hardening** — free Cython obfuscation of licensing (`.pyd`, hard-coded key), code-signing the exe.

Rationale: layers 1–3 are real engineering and de-riskable today; layers 5–7 are where schedule risk
hides (native-dep gaps, Cython-obfuscation/PyInstaller integration, AV behavior). Don't let the GUI/DRM
block proving the geometry.

## End-to-end verification / acceptance matrix
| Area | Check | How |
|------|-------|-----|
| Ingestion ([03](03-ingestion-streaming.md)) | bounded memory; correct enumeration | sample RSS during iterator loop; assert counts |
| Filtering ([04](04-filtering-coloring.md)) | only selected classes kept; inheritance-aware | element counts pre/post; include a `*StandardCase` model |
| Coloring ([04](04-filtering-coloring.md)) | each group's GLB material color correct; mapped-item path works | GLB node→GlobalId→material map; type-authored model |
| Cropping ([05](05-spatial-cropping.md)) | kept set within Z/box; temp IFC re-parses cleanly | bounds assertions; re-open written IFC |
| Conversion ([06](06-conversion-pipeline.md)) | GLB+STP+USDZ produced; input untouched; temp cleaned | exit codes; sha256 of input; temp absence |
| AR output ([07](07-ar-output-units-draco.md)) | Y-up, real scale, size/triangle budget | glTF viewer + ARKit device; size/tri counts |
| Batch/UI ([08](08-batch-threading-ui.md)) | sequential; responsive ≥2s; graceful cancel | multi-file run incl. corrupt; long-run; cancel |
| Licensing ([09](09-licensing-security.md)) | valid/expired/wrong-machine/tampered matrix | test key pair |
| Packaging ([10](10-packaging-distribution.md)) | runs on clean offline VM | fresh VM smoke test + screenshots |
| Errors ([11](11-error-handling-reporting.md)) | 5 scenarios behave per spec | targeted fault injection |

## Proven technique to reuse (from this session)
The **GLB node → IFC GlobalId → glTF material** mapping was used to prove, on a real buildingSMART
model, that all walls/slabs were recolored while non-targets kept original materials. Reuse this exact
assertion approach for the color/crop acceptance tests here (parse the GLB JSON chunk, map
`product-<expanded-GUID>-body` node names back to entities via `ifcopenshell.guid.expand`, read each
mesh's material).

## Acceptance artifacts (spec §8)
- Clean, documented source + pinned `requirements.txt` + `hooks/` (build phase).
- Bundled IfcConvert (pinned version) + AR post-tool.
- `main.spec` one-folder build.
- Signed clean-VM test report with screenshots.
- Step-by-step Windows build guide (Python install → venv → `pip install -r requirements.txt` →
  `pyinstaller main.spec` → optional code-signing).

## Open decisions to settle before quoting (🔶)
- Draco target (ratio/size) and ARKit decoder support (D1).
- Python 3.11 vs 3.12 pin (D3).
- Cropping partial-overlap policy and "no solid slicing" confirmation ([05](05-spatial-cropping.md)).
- IfcConvert version pin (D10).
- Commercial terms / milestones before handing over full source (see README top-line note).
