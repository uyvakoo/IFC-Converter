"""
Headless UI smoke test (offscreen Qt — no display). Validates that the PySide6 shell constructs,
the license activation logic works against the bundled key, and the worker drives the core.
    python tests/validate_ui.py
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import licensing
from PySide6.QtWidgets import QApplication

from core import filtering, paths
from ui.license_window import LicenseDialog
from ui.main_window import MainWindow
from ui.worker import BatchWorker

FIXTURE = os.path.join(HERE, "fixtures", "fixture.ifc")
OUT = os.path.join(HERE, "_out_ui")

app = QApplication.instance() or QApplication([])
_results = []


def check(name, cond, detail=""):
    _results.append(bool(cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def ui_widgets():
    print("UI  window construction + state")
    w = MainWindow()
    check("4 class checkboxes match groups", list(w.group_checks) == list(filtering.ALL_GROUPS))
    check("Start disabled before files/output", not w.btn_start.isEnabled())
    w.add_files([FIXTURE])
    check("file queued in table", w.table.rowCount() == 1)
    check("storey dropdown populated (Ground/Level 1)", w.storey_combo.count() >= 3,
          f"{w.storey_combo.count()} items")
    w.set_output(OUT)
    check("Start enabled after files+output", w.btn_start.isEnabled())
    opts = w.build_opts()
    check("build_opts has all groups + ifcconvert path",
          opts["groups"] == list(filtering.ALL_GROUPS) and opts["ifcconvert"].endswith("IfcConvert.exe"))


def license_flow():
    print("UI  license activation")
    # Self-contained: generate a keypair, inject the public key, sign a license for THIS machine.
    from datetime import date, timedelta

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    store = licensing.InMemoryStore()
    dlg = LicenseDialog(public_key_pem=pub_pem, clock_store=store)

    lic = licensing.sign_license(priv, dlg.machine, (date.today() + timedelta(days=30)).isoformat())
    lic_path = os.path.join(OUT, "license.key")
    json.dump(lic, open(lic_path, "w"))
    check("valid license activates", dlg.activate_with(lic_path).ok)

    bad = dict(lic)
    bad["expiry"] = "2099-01-01"
    bad_path = os.path.join(OUT, "_bad_license.key")
    json.dump(bad, open(bad_path, "w"))
    check("tampered license rejected", not dlg.activate_with(bad_path).ok)


def worker_run():
    print("UI  worker drives core (synchronous run)")
    opts = dict(out_dir=OUT, groups=["Structural"], storey_name=None, xyz=None, targets=("glb",),
                ifcconvert=paths.ifcconvert(), gltfpack=paths.gltfpack(), compress=False)
    states, done = [], []
    w = BatchWorker([FIXTURE], opts)
    w.status.connect(lambda i, s, e: states.append(s))
    w.finished.connect(lambda: done.append(True))
    w.run()
    check("worker reached Done", "Done" in states, str(states))
    check("worker emitted finished", bool(done))
    check("GLB produced", os.path.exists(os.path.join(OUT, "fixture.glb")))


def main():
    import shutil
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    ui_widgets()
    license_flow()
    worker_run()
    p, t = sum(_results), len(_results)
    print(f"\n==== {p}/{t} checks passed ====")
    sys.exit(0 if p == t else 1)


if __name__ == "__main__":
    main()
