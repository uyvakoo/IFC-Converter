# 11 — Error Handling & Reporting

## Purpose
Define robust behavior for the spec's five mandatory failure scenarios and the structure of the debug
report.

## Inputs / Outputs
- **In:** runtime failures (bad files, permissions, missing binary, long runs, user close).
- **Out:** user-facing dialogs, per-file states, and `conversion_report.txt` rows.

## The five scenarios (spec §9)
| # | Scenario | Required behavior | Notes |
|---|----------|-------------------|-------|
| 1 | IFC corrupt/unreadable | Log to report, **skip** file, continue queue | Per-file isolation — one bad file never kills the batch |
| 2 | Output folder not writable | Error dialog immediately; force re-pick; **block Start** until valid | Pre-flight check before processing; ties to [08](08-batch-threading-ui.md) enablement |
| 3 | IfcConvert.exe missing from bundle | Log **fatal**, message box, **abort entire run** | Best caught at startup (fail fast), not mid-batch |
| 4 | Run > 1 hour | UI stays responsive; progress updates **≥ every 2 s** | Worker thread + cadence (see [08](08-batch-threading-ui.md)) |
| 5 | User closes during conversion | Confirm dialog → if yes, **graceful** cancel, no temp corruption | Cooperative cancel, never `terminate()` ([08](08-batch-threading-ui.md)) |

## Architecture & how to handle
- **Per-file try/abort boundary:** wrap steps 1–5 (Python side) so any exception → report row + skip,
  no CLI call (matches [06](06-conversion-pipeline.md) abort rule). CLI non-zero → Error state, continue.
- **Pre-flight gates** (before the queue starts): license valid, output folder writable, IfcConvert
  present, ≥1 file. Scenario 2 & 3 are best handled here.
- **Temp safety:** every file's temp lives in a `finally`-guaranteed cleanup so aborts/cancels leave no
  residue (D9, spec §10).
- **No leaking tracebacks** to users (spec §6.3) — log details to the report/log file, show friendly
  dialogs.

## conversion_report.txt schema (spec §5.2)
One record per file (append-only), in the **output folder**, containing:
- Timestamp
- Input filename
- Cropping coordinates or storey name used
- Active filter list (which entity classes were kept)
- Number of entities processed
- Final file sizes in bytes (GLB and/or STP)
- Elapsed time in seconds
- (Recommended additions) status (Done/Error), and the error message on failure.

## Key APIs (named, no code)
- `QMessageBox` (error/confirm dialogs), `QFileDialog` (re-pick output folder).
- `os.access(path, os.W_OK)` / attempt-write probe for the writability pre-flight.
- A single `core/report.append(row)` writer (one source of truth; also used on success path).
- `logging` to a separate technical log if deeper diagnostics are wanted (kept out of user view).

## Defects & risks
- Writability via `os.access` can be unreliable on Windows ACLs — prefer an actual probe write to a
  temp file in the chosen folder.
- Report writer must itself handle the output folder becoming unwritable mid-run.
- Scenario 5 must join the worker thread before exit to avoid a corrupt temp/half-written output.

## Proposed remedies
- Centralize all user-facing error copy in one place for consistency and easy localization.
- Make `core/report` resilient (best-effort; never let a logging failure crash a conversion).

## Verification (E2E)
- Feed a deliberately corrupt IFC in a multi-file queue: assert it's logged, skipped, and the rest
  complete (scenario 1).
- Point output at a read-only folder: assert Start is blocked with a clear dialog (scenario 2).
- Remove/rename the bundled IfcConvert: assert fatal handling at startup (scenario 3).
- Inspect `conversion_report.txt`: assert every required field is present and correct per file.
