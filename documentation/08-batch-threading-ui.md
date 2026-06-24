# 08 — Batch Queue, Threading & UI

## Purpose
Process multiple files sequentially while keeping the GUI responsive, showing per-file status and
global progress, with safe cancellation.

## Inputs / Outputs
- **In:** a user-selected list of IFC files; settings (classes, storey/XYZ, output folder, targets).
- **Out:** per-file status updates, a moving progress bar, and the converted outputs.

## Threading model (spec §4.2, §9.4, §9.5)
- **One background `QThread` worker** runs the entire batch. The UI/main thread only renders and
  collects input.
- **Strictly sequential** file processing — no parallel IFC parsing (spec: causes memory corruption).
- Worker → UI **exclusively via Qt signals**: `progress(int)`, `status(file, state)`, `error(msg)`,
  `finished()`. The worker must never call widget methods directly (Qt is not thread-safe for UI).
- **Progress cadence ≥ every 2 s** (spec §9.4) even on hour-long files, sourced from the iterator's
  progress during the analyze pass plus coarse step markers (crop/convert/post).
- **Cooperative cancellation**: a shared `should_cancel` flag checked between elements and between
  files. On request: stop after the current safe point, clean the temp file, emit `finished`. **Never**
  hard-kill the thread mid-`model.write()`/CLI (corrupts temp; spec §9.5). The spec says "terminate
  gracefully" — implement as cooperative, not `QThread.terminate()`.

## UI layout (spec §7)
**Window 1 — License Activation (modal gate)** — see [09](09-licensing-security.md):
- "Machine Hash:" + copyable text box; instruction to email it to the vendor; **Browse** (load
  `license.key`); **Activate** (validate → close on success, error dialog on failure).

**Window 2 — Main Application:**
- **Top bar:** app title + version.
- **Left panel (settings):** entity checklist (4 group checkboxes), storey dropdown (populated after a
  file loads), **"Manual XYZ Crop"** advanced toggle revealing X/Y/Z min/max fields.
- **Center panel (queue):** **Add Files**, a list view with status column (Pending / Processing / Done /
  Error), and a global progress bar.
- **Bottom bar:** **Start Conversion**, **Output Folder** selector, **Open Report** (opens
  `conversion_report.txt` in the default editor).

## Theming (spec §7.1)
- PySide6 + **qt-material** light theme with `invert_secondary=True`.
- Palette tokens: accent #3455FA, bg #FFFFFF, text #000000, secondary #555555, borders #E0E0E0,
  success/progress #34A853, error #EA4335. Centralize these tokens.

## Key APIs (named, no code)
- `QThread` + a worker `QObject` moved to it; `Signal(int)` / `Signal(str)` for progress/status/error.
- `QFileDialog` (add files / output folder / license), `QMessageBox` (errors/confirm),
  `QComboBox` (storey), `QCheckBox` (classes), `QListView`/`QTableView` (queue), `QProgressBar`.
- `qt_material.apply_stylesheet(app, theme="light_blue.xml", invert_secondary=True)`.

## Defects & risks
- Doing heavy work on the UI thread → frozen GUI (violates §9.4). Keep all conversion in the worker.
- `QThread.terminate()` mid-write → corrupt temp (§9.5). Cooperative cancel only.
- Storey dropdown populated before a file is loaded → empty/incorrect; gate on load.
- Enable **Start** only when: license valid **and** output folder writable **and** ≥1 file queued
  (ties to [11](11-error-handling-reporting.md) scenario 2).

## Proposed remedies
- A thin `ui/worker` that owns the `should_cancel` flag and wraps `core/pipeline`; the UI subscribes to
  its signals. Core stays Qt-free and testable.
- Debounce progress emission on a timer to avoid signal floods.

## Verification (E2E)
- Queue several files (incl. one corrupt): assert sequential processing, correct per-file states, the
  corrupt one marked Error and skipped, queue continues (§9.1).
- Start a long job: assert the bar updates at least every 2 s and the UI stays interactive.
- Cancel mid-run: assert graceful stop, no orphaned temp files, app closes cleanly.
