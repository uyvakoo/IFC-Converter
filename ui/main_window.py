"""Main application window (spec §7.2 Window 2)."""
from __future__ import annotations

import os

import ifcopenshell
from PySide6.QtCore import QThread
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
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(900, 560)
        self._files: list[str] = []
        self._out_dir: str | None = None
        self._thread: QThread | None = None
        self._worker: BatchWorker | None = None

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
        self.cb_compress = QCheckBox("Compress GLB for AR (gltfpack)")
        lay.addWidget(self.cb_stp)
        lay.addWidget(self.cb_compress)
        lay.addStretch(1)
        return box

    def _build_center(self):
        box = QGroupBox("Batch")
        lay = QVBoxLayout(box)
        btn_add = QPushButton("Add Files…")
        btn_add.clicked.connect(self._add_files)
        lay.addWidget(btn_add)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["File", "Status"])
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)
        self.progress = QProgressBar()
        lay.addWidget(self.progress)
        return box

    def _build_bottom(self):
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
        self.xyz_box.setVisible(on)

    def _add_files(self):
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
        try:
            m = ifcopenshell.open(ifc_path)
            for st in m.by_type("IfcBuildingStorey"):
                self.storey_combo.addItem(st.Name or "(unnamed)")
        except Exception:
            pass

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder")
        if d:
            self.set_output(d)

    def set_output(self, d):
        self._out_dir = d
        self.out_label.setText(d)
        self._update_start_enabled()

    def _open_report(self):
        if self._out_dir:
            rp = os.path.join(self._out_dir, "conversion_report.txt")
            if os.path.exists(rp):
                os.startfile(rp)  # opens conversion_report.txt in the OS default editor (Windows)
                return
        QMessageBox.information(self, "Report", "No report yet.")

    def selected_groups(self):
        return [g for g, cb in self.group_checks.items() if cb.isChecked()]

    def build_opts(self):
        targets = ("glb",) + (("stp",) if self.cb_stp.isChecked() else ())
        xyz = None
        if self.xyz_toggle.isChecked():
            xyz = [self.xyz_spins[k].value() for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")]
        storey = None if self.storey_combo.currentIndex() == 0 else self.storey_combo.currentText()
        return dict(out_dir=self._out_dir, groups=self.selected_groups(), storey_name=storey,
                    xyz=xyz, targets=targets, ifcconvert=paths.ifcconvert(), gltfpack=paths.gltfpack(),
                    compress=self.cb_compress.isChecked())

    def _update_start_enabled(self):
        ready = bool(self._files) and bool(self._out_dir)
        self.btn_start.setEnabled(ready and self._thread is None)

    def _start(self):
        for r in range(self.table.rowCount()):
            self.table.setItem(r, 1, QTableWidgetItem("Pending"))
        self.progress.setValue(0)
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

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
        self.btn_cancel.setEnabled(False)

    def _on_progress(self, idx, pct):
        self.progress.setValue(pct)

    def _on_status(self, idx, state, error):
        self.table.setItem(idx, 1, QTableWidgetItem(state if not error else f"Error: {error}"))

    def _on_fatal(self, msg):
        QMessageBox.critical(self, "Fatal", msg)

    def _on_finished(self):
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self.btn_cancel.setEnabled(False)
        self._update_start_enabled()

    def closeEvent(self, event):  # §9.5 graceful close
        if self._thread is not None:
            if QMessageBox.question(self, "Quit", "A conversion is running. Cancel and quit?") \
                    != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self._worker:
                self._worker.cancel()
            self._thread.quit()
            self._thread.wait()
        event.accept()
