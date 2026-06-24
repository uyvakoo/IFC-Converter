"""License Activation modal (spec §7.2 Window 1)."""
from __future__ import annotations

import json

import licensing
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class LicenseDialog(QDialog):
    def __init__(self, parent=None, public_key_pem: bytes | None = None, clock_store=None):
        super().__init__(parent)
        self.setWindowTitle("License Activation")
        self.setModal(True)
        self._pub = public_key_pem or licensing.load_public_key_pem()
        self._store = clock_store if clock_store is not None else licensing.RegistryStore()
        self.machine = licensing.machine_hash()
        self._license_path: str | None = None

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Machine Hash:"))
        row = QHBoxLayout()
        self.hash_edit = QLineEdit(self.machine)
        self.hash_edit.setReadOnly(True)
        row.addWidget(self.hash_edit)
        btn_copy = QPushButton("Copy")
        btn_copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.machine))
        row.addWidget(btn_copy)
        lay.addLayout(row)

        info = QLabel("Email this hash to your vendor to receive a license key.")
        info.setObjectName("secondary")
        lay.addWidget(info)

        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        lay.addWidget(btn_browse)
        self.path_label = QLabel("")
        self.path_label.setObjectName("secondary")
        lay.addWidget(self.path_label)

        btn_activate = QPushButton("Activate")
        btn_activate.setObjectName("primary")
        btn_activate.clicked.connect(self._activate)
        lay.addWidget(btn_activate)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select license.key", "",
                                              "License (*.key *.json);;All files (*)")
        if path:
            self._license_path = path
            self.path_label.setText(path)

    def activate_with(self, path: str) -> "licensing.LicenseResult":
        """Headless-testable activation: clock guard -> load -> verify. Returns LicenseResult."""
        ok, reason = licensing.check_clock(self._store)
        if not ok:
            return licensing.LicenseResult(False, reason)
        try:
            with open(path, encoding="utf-8") as f:
                lic = json.load(f)
        except (OSError, ValueError):
            return licensing.LicenseResult(False, "Invalid license - contact vendor")
        return licensing.verify_license(lic, self._pub, current_machine=self.machine)

    def _activate(self):
        if not self._license_path:
            QMessageBox.warning(self, "License", "Choose a license.key file first.")
            return
        res = self.activate_with(self._license_path)
        if res.ok:
            self.accept()
        else:
            QMessageBox.critical(self, "License", res.reason)
