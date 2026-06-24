# 06 — Conversion Pipeline (Temp IFC → IfcConvert → GLB/STP)

## Purpose
Turn the filtered/colored/cropped in-memory model into the two final outputs by writing a temporary
IFC and delegating format conversion to the bundled `IfcConvert.exe`.

## Inputs / Outputs
- **In:** the mutated, colored model; output folder; output targets (GLB and/or STP).
- **Out:** `output.glb` and/or `output.stp` in the output folder; a deleted temp file; a report row.

## Architecture & how to handle (the per-file pipeline)
1. **Write temp IFC** — serialize the model to a **unique** temp path (D9), not the fixed
   `cropped_model.ifc`. Use `tempfile.mkstemp(suffix=".ifc")` or a `TemporaryDirectory`, and clean up
   in a `finally` so an abort never leaks temp files (spec §10 "clean temp after each conversion").
2. **GLB** — `IfcConvert --y-up --use-material-names <temp>.ifc <out>.glb`.
   - `--use-material-names` is **mandatory** to preserve the colors assigned in Python (verified:
     styles become named glTF materials).
   - **Do not** pass `--draco`/`--optimize` — they don't exist (D1). Draco/decimation is the separate
     post-step in [07](07-ar-output-units-draco.md).
3. **STP** — `IfcConvert --convert-back-units <temp>.ifc <out>.stp`. No colors (STEP carries none here).
   STP has **no native Python serializer** — CLI only (spec §10).
4. **Run as subprocess** — capture stdout/stderr and the return code. On Windows the binary prints
   **UTF-16**; decode accordingly when logging (a plain text capture shows space-separated characters).
5. **Resolve the binary** via `sys._MEIPASS` at runtime in the bundle; keep a dev fallback path.
6. **Cleanup + report** — delete temp, record sizes/time/etc.

## Fallback & abort rules (spec §4.3, §9)
- If any **Python-side** step (open/filter/crop/color/write, i.e. steps 1–5 of the canonical sequence)
  raises → log to `conversion_report.txt`, abort **this** file, **do not** invoke the CLI, continue
  the queue.
- If **IfcConvert** returns non-zero → log stderr, mark the file Error, continue the queue.
- If **IfcConvert.exe is missing** from the bundle → fatal: message box + abort the whole run (spec §9.3).

## Key APIs / tools (named, no code)
- `model.write(temp_path)`.
- `tempfile.mkstemp` / `tempfile.TemporaryDirectory`.
- `subprocess.run([...], capture_output=True)` (decode stdout as UTF-16 on Windows).
- `sys._MEIPASS` for bundled-binary path resolution (see [10](10-packaging-distribution.md)).
- IfcConvert flags (verified present in 0.8.5): `--y-up`, `--use-material-names`, `--convert-back-units`,
  `--use-element-*`, `--center-model`, `--ecef`, `-j/--threads`.

## Defects & risks
- **D1** — non-existent `--draco/--optimize`; would error the GLB command. High.
- **D9** — fixed temp name → collisions/leftovers. Med.
- UTF-16 CLI output mis-logged as garbage if decoded as UTF-8.
- Output path with no write permission → see [11](11-error-handling-reporting.md) (block before start).
- Large models: IfcConvert can be slow; the UI must stay responsive via the worker thread
  ([08](08-batch-threading-ui.md)).
- `--use-material-names` flag availability can vary by build (verify on the pinned 0.8.5 binary, D10).

## Proposed remedies
- A single `core/convert.to_glb(...)` / `core/convert.to_stp(...)` wrapping subprocess + decoding +
  return-code handling, with the binary path injected (so tests can stub it).
- Verify, on app startup, that the bundled IfcConvert exists and reports a version (fail fast, D-note).

## Verification (E2E)
- Run GLB + STP on a known model; assert both files exist and are non-empty; assert exit code 0.
- Parse the GLB and confirm the expected materials/meshes (color check) — see [04](04-filtering-coloring.md).
- Confirm the temp file is gone after success and after a forced mid-pipeline error.
- Confirm input IFC is untouched (write goes to temp only) — sha256 before/after (used this session).
