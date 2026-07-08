"""Main application window (spec §7.2 Window 2)."""

from __future__ import annotations

import os
import time

import ifcopenshell
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import filtering, paths
from ui import APP_NAME, APP_VERSION
from ui.worker import BatchWorker


class MainWindow(QMainWindow):
    def __init__(self):
        """Build the main window (§7.2 Window 2): settings panel, batch table, and action bar."""
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(900, 560)
        self._files: list[str] = []
        self._out_dir: str | None = None
        self._thread: QThread | None = None
        self._worker: BatchWorker | None = None
        # §9.4: keep the UI alive at <= 2s cadence during long conversions. IfcConvert/gltfpack
        # steps are opaque (no sub-progress), so the heartbeat updates an Elapsed counter and flips
        # the bar to an animated busy/indeterminate marquee whenever determinate progress stalls.
        self._run_started = 0.0
        self._last_progress_at = 0.0
        self._heartbeat = QTimer(self)
        self._heartbeat.setInterval(1000)  # fire every 1s -> guaranteed within the 2s minimum
        self._heartbeat.timeout.connect(self._tick)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.addWidget(QLabel(f"<b>{APP_NAME}</b>  v{APP_VERSION}"))  # top bar

        body = QHBoxLayout()
        root.addLayout(body, 1)
        body.addWidget(self._build_left(), 0)
        body.addWidget(self._build_center(), 1)
        root.addLayout(self._build_bottom())
        self._update_start_enabled()

    # ---- panels -----------------------------------------------------------
    def _build_left(self):
        """Build the left settings panel: class checklist, storey dropdown, XYZ crop, output toggles."""
        box = QGroupBox("Settings")
        lay = QVBoxLayout(box)
        lay.addWidget(QLabel("Keep classes:"))
        self.group_checks = {}
        for g in filtering.ALL_GROUPS:
            cb = QCheckBox(g)
            cb.setChecked(True)
            self.group_checks[g] = cb
            lay.addWidget(cb)

        lay.addWidget(QLabel("Storey:"))
        self.storey_combo = QComboBox()
        self.storey_combo.addItem("(whole model)")
        lay.addWidget(self.storey_combo)

        self.xyz_toggle = QCheckBox("Manual XYZ Crop")
        self.xyz_toggle.toggled.connect(self._toggle_xyz)
        lay.addWidget(self.xyz_toggle)
        self.xyz_box = QGroupBox()
        form = QFormLayout(self.xyz_box)
        self.xyz_spins = {}
        for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"):
            sp = QDoubleSpinBox()
            sp.setRange(-1e6, 1e6)
            self.xyz_spins[k] = sp
            form.addRow(k, sp)
        self.xyz_box.setVisible(False)
        lay.addWidget(self.xyz_box)

        self.cb_stp = QCheckBox("Also export STP")
        self.cb_usdz = QCheckBox("Also export USDZ (iOS AR)")
        self.cb_compress = QCheckBox("Compress GLB for AR")
        lay.addWidget(self.cb_stp)
        lay.addWidget(self.cb_usdz)
        lay.addWidget(self.cb_compress)
        crow = QHBoxLayout()
        crow.addWidget(QLabel("Mode:"))
        self.compress_mode_combo = QComboBox()
        # draco is the spec default (§1/§5.1: low-poly + KHR_draco_mesh_compression); meshopt is the
        # gltfpack alternative. Draco is first so it is selected by default.
        for label in ("draco (gltf-pipeline)", "meshopt (gltfpack)"):
            self.compress_mode_combo.addItem(label)
        crow.addWidget(self.compress_mode_combo, 1)
        lay.addLayout(crow)
        lay.addStretch(1)
        return box

    def _build_center(self):
        """Build the centre batch panel: Add Files, the file/status table, progress bar + elapsed."""
        box = QGroupBox("Batch")
        lay = QVBoxLayout(box)
        btn_add = QPushButton("Add Files…")
        btn_add.clicked.connect(self._add_files)
        lay.addWidget(btn_add)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["File", "Status"])
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)
        self.queue_label = QLabel("")  # §4.2: queue position + current file name
        lay.addWidget(self.queue_label)
        self.progress = QProgressBar()
        lay.addWidget(self.progress)
        self.elapsed_label = QLabel("")
        self.elapsed_label.setObjectName("secondary")
        lay.addWidget(self.elapsed_label)
        return box

    def _build_bottom(self):
        """Build the bottom action bar: Start, Cancel, Output Folder, and Open Report."""
        bar = QHBoxLayout()
        self.btn_start = QPushButton("Start Conversion")
        self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self._start)
        bar.addWidget(self.btn_start)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_cancel.setEnabled(False)
        bar.addWidget(self.btn_cancel)
        btn_out = QPushButton("Output Folder…")
        btn_out.clicked.connect(self._pick_output)
        bar.addWidget(btn_out)
        self.out_label = QLabel("(no output folder)")
        self.out_label.setObjectName("secondary")
        bar.addWidget(self.out_label, 1)
        btn_report = QPushButton("Open Report")
        btn_report.clicked.connect(self._open_report)
        bar.addWidget(btn_report)
        return bar

    # ---- actions ----------------------------------------------------------
    def _toggle_xyz(self, on):
        """Show/hide the manual XYZ crop inputs when the toggle changes."""
        self.xyz_box.setVisible(on)

    def _add_files(self):
        """Prompt for IFC files and queue the chosen ones."""
        files, _ = QFileDialog.getOpenFileNames(self, "Add IFC files", "", "IFC (*.ifc);;All (*)")
        if files:
            self.add_files(files)

    def add_files(self, files):
        """Headless-testable: queue files, populate table + storey dropdown from the first file."""
        first = not self._files
        for f in files:
            self._files.append(f)
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(os.path.basename(f)))
            self.table.setItem(r, 1, QTableWidgetItem("Pending"))
        if first and self._files:
            self._populate_storeys(self._files[0])
        self._update_start_enabled()

    def _populate_storeys(self, ifc_path):
        """Fill the storey dropdown from the IfcBuildingStorey entities of the given IFC (best-effort)."""
        try:
            m = ifcopenshell.open(ifc_path)
            for st in m.by_type("IfcBuildingStorey"):
                self.storey_combo.addItem(st.Name or "(unnamed)")
        except Exception:
            pass

    def _pick_output(self, d=None):
        """Choose the output folder; reject a non-writable one with a dialog (§9.2)."""
        d = d or QFileDialog.getExistingDirectory(self, "Output folder")
        if not d:
            return
        if not self._output_writable(d):  # §9 scenario 2
            QMessageBox.critical(self, "Output folder", "That folder is not writable. Please choose another.")
            return
        self.set_output(d)

    @staticmethod
    def _output_writable(path: str) -> bool:
        """True if a probe file can be written to `path` (output-folder writability check)."""
        try:
            probe = os.path.join(path, ".write_test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return True
        except OSError:
            return False

    def set_output(self, d):
        """Set the output folder and refresh the Start button's enabled state."""
        self._out_dir = d
        self.out_label.setText(d)
        self._update_start_enabled()

    def _open_report(self):
        """Open conversion_report.txt in the OS default editor, or note that none exists yet."""
        if self._out_dir:
            rp = os.path.join(self._out_dir, "conversion_report.txt")
            if os.path.exists(rp):
                os.startfile(rp)  # opens conversion_report.txt in the OS default editor (Windows)
                return
        QMessageBox.information(self, "Report", "No report yet.")

    def selected_groups(self):
        """The class groups currently ticked in the checklist."""
        return [g for g, cb in self.group_checks.items() if cb.isChecked()]

    def build_opts(self):
        """Assemble the batch options dict from the current UI state (groups, crop, targets, compress)."""
        targets = (
            ("glb",)
            + (("stp",) if self.cb_stp.isChecked() else ())
            + (("usdz",) if self.cb_usdz.isChecked() else ())
        )
        xyz = None
        if self.xyz_toggle.isChecked():
            xyz = [self.xyz_spins[k].value() for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")]
        storey = None if self.storey_combo.currentIndex() == 0 else self.storey_combo.currentText()
        return dict(
            out_dir=self._out_dir,
            groups=self.selected_groups(),
            storey_name=storey,
            xyz=xyz,
            targets=targets,
            ifcconvert=paths.ifcconvert(),
            gltfpack=paths.gltfpack(),
            compress=self.cb_compress.isChecked(),
            compress_mode="meshopt" if self.compress_mode_combo.currentIndex() == 1 else "draco",
            node=paths.node(),
            gltf_pipeline=paths.gltf_pipeline(),
        )

    def _update_start_enabled(self):
        """Enable Start only when files are queued, an output folder is set, and no run is active."""
        ready = bool(self._files) and bool(self._out_dir)
        self.btn_start.setEnabled(ready and self._thread is None)

    def _start(self):
        """Kick off the batch on a worker thread and start the §9.4 UI heartbeat."""
        for r in range(self.table.rowCount()):
            self.table.setItem(r, 1, QTableWidgetItem("Pending"))
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._run_started = time.monotonic()
        self._last_progress_at = self._run_started
        self.elapsed_label.setText("Elapsed: 0s")
        self._cur_idx = 0  # §4.2 queue position
        self.queue_label.setText(f"Queued: {len(self._files)} file(s)")
        self._worker = BatchWorker(list(self._files), self.build_opts())
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.status.connect(self._on_status)
        self._worker.fatal.connect(self._on_fatal)
        self._worker.finished.connect(self._on_finished)
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self._thread.start()
        self._heartbeat.start()  # §9.4: guarantee a UI refresh at least every 2s

    def _tick(self):
        """§9.4 heartbeat: advance the Elapsed counter and flip to a busy marquee if progress stalls."""
        # §9.4 heartbeat (fires every 1s): always advance the Elapsed counter (a guaranteed visible
        # update), and if determinate progress has stalled >2s (an opaque IfcConvert/gltfpack step),
        # flip the bar to an animated busy/indeterminate marquee so it visibly shows "still alive".
        if self._thread is None:
            return
        self.elapsed_label.setText(f"Elapsed: {int(time.monotonic() - self._run_started)}s")
        if time.monotonic() - self._last_progress_at > 2.0 and self.progress.maximum() != 0:
            self.progress.setRange(0, 0)  # busy marquee (Qt animates it on the main event loop)
        self.progress.update()

    def _cancel(self):
        """Request cooperative cancellation of the running batch."""
        if self._worker:
            self._worker.cancel()
        self.btn_cancel.setEnabled(False)

    def _on_progress(self, idx, pct):
        """Handle a determinate progress event: leave busy mode, show the percentage + queue position."""
        # A real (determinate) progress event arrived -> leave busy mode and show the percentage.
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
        self.progress.setValue(pct)
        self._last_progress_at = time.monotonic()
        self._set_queue_label(idx, pct)

    def _on_status(self, idx, state, error):
        """Update a file's row with its state (or error) and the queue label while processing."""
        self.table.setItem(idx, 1, QTableWidgetItem(state if not error else f"Error: {error}"))
        if state == "Processing":
            self._set_queue_label(idx)

    def _set_queue_label(self, idx, pct=None):
        """Show queue position, current file name and optional percentage (§4.2)."""
        # §4.2: show queue position, current file name, and percentage.
        total = len(self._files)
        name = os.path.basename(self._files[idx]) if 0 <= idx < total else ""
        tail = f" — {pct}%" if pct is not None else ""
        self.queue_label.setText(f"Processing {idx + 1} of {total}: {name}{tail}")

    def _on_fatal(self, msg):
        """Show a fatal-error dialog for a whole-run abort (e.g. a missing bundled binary, §9.3)."""
        QMessageBox.critical(self, "Fatal", msg)

    def _on_finished(self):
        """Finalize a run: stop the heartbeat, complete the bar, tear down the worker thread."""
        self._heartbeat.stop()
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.queue_label.setText(f"Finished {len(self._files)} file(s)")
        if self._run_started:
            self.elapsed_label.setText(f"Done in {int(time.monotonic() - self._run_started)}s")
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self.btn_cancel.setEnabled(False)
        self._update_start_enabled()

    def closeEvent(self, event):  # §9.5 graceful close
        """Confirm before quitting mid-run; on confirm, cancel cooperatively and join the thread (§9.5)."""
        if self._thread is not None:
            if (
                QMessageBox.question(self, "Quit", "A conversion is running. Cancel and quit?")
                != QMessageBox.StandardButton.Yes
            ):
                event.ignore()
                return
            if self._worker:
                self._worker.cancel()
            self._thread.quit()
            self._thread.wait()
        event.accept()
