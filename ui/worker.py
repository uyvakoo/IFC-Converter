"""
QThread worker (spec §4.2/§9.4/§9.5) — wraps the Qt-free `core.batch.run_batch`.

Lives in a QThread; emits signals to the UI thread; cancellation is cooperative (a flag the batch
checks between files) — never QThread.terminate(), which would corrupt temp files.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from core import batch


class BatchWorker(QObject):
    progress = Signal(int, int)  # file_index, percent
    status = Signal(int, str, str)  # file_index, state, error
    fatal = Signal(str)  # whole-run abort (missing binary, §9.3)
    finished = Signal()

    def __init__(self, files, opts: dict):
        """Hold the file list + pipeline options for a batch run on this worker's thread."""
        super().__init__()
        self._files = files
        self._opts = opts
        self._cancel = False

    def cancel(self) -> None:
        """Request cooperative cancellation (checked between files); never force-terminates."""
        self._cancel = True

    @Slot()
    def run(self) -> None:
        """Run the batch, forwarding progress/status signals and emitting fatal/finished at the end."""
        try:
            batch.run_batch(
                self._files,
                cancel=lambda: self._cancel,
                progress_cb=lambda i, p: self.progress.emit(i, p),
                status_cb=lambda i, fs: self.status.emit(i, fs.state, fs.error or ""),
                **self._opts,
            )
        except batch.FatalError as e:
            self.fatal.emit(str(e))
        except Exception as e:  # defensive; per-file errors handled inside run_batch
            self.fatal.emit(str(e))
        finally:
            self.finished.emit()
