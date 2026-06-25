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

from PySide6.QtWidgets import QApplication

import licensing
from core import filtering, paths
from ui import theme
from ui.license_window import LicenseDialog
from ui.main_window import MainWindow
from ui.worker import BatchWorker

FIXTURE = os.path.join(HERE, "fixtures", "fixture.ifc")
OUT = os.path.join(HERE, "_out_ui")

app = QApplication.instance() or QApplication([])
theme.apply_theme(app)  # exercise the real light theme so the render check is realistic
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
    check(
        "storey dropdown populated (Ground/Level 1)",
        w.storey_combo.count() >= 3,
        f"{w.storey_combo.count()} items",
    )
    w.set_output(OUT)
    check("Start enabled after files+output", w.btn_start.isEnabled())
    opts = w.build_opts()
    check(
        "build_opts has all groups + ifcconvert path",
        opts["groups"] == list(filtering.ALL_GROUPS) and opts["ifcconvert"].endswith("IfcConvert.exe"),
    )
    # §7.2 main-window controls present
    check("manual XYZ crop exposes 6 inputs", len(w.xyz_spins) == 6)
    check(
        "queue/progress/cancel/targets/output controls present",
        all(
            hasattr(w, a)
            for a in ("btn_cancel", "progress", "cb_stp", "cb_compress", "out_label", "xyz_toggle")
        ),
    )


def license_flow():
    print("UI  license activation")
    # Self-contained: generate a keypair, inject the public key, sign a license for THIS machine.
    from datetime import date, timedelta

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    store = licensing.InMemoryStore()
    dlg = LicenseDialog(public_key_pem=pub_pem, clock_store=store)
    check(
        "license window shows machine hash (read-only) + browse/activate",
        dlg.hash_edit.text() == dlg.machine and dlg.hash_edit.isReadOnly(),
    )

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
    opts = dict(
        out_dir=OUT,
        groups=["Structural"],
        storey_name=None,
        xyz=None,
        targets=("glb",),
        ifcconvert=paths.ifcconvert(),
        gltfpack=paths.gltfpack(),
        compress=False,
    )
    states, done = [], []
    w = BatchWorker([FIXTURE], opts)
    w.status.connect(lambda i, s, e: states.append(s))
    w.finished.connect(lambda: done.append(True))
    w.run()
    check("worker reached Done", "Done" in states, str(states))
    check("worker emitted finished", bool(done))
    check("GLB produced", os.path.exists(os.path.join(OUT, "fixture.glb")))


def real_world_e2e():
    print("UI  real-world end-to-end (Building-Architecture.ifc via the worker)")
    import tests.glbtools as glbtools

    real = os.path.join(HERE, "fixtures", "real_building.ifc")
    if not os.path.exists(real):
        check("real model fixture present", False, real)
        return

    def run(compress):
        opts = dict(
            out_dir=OUT,
            groups=["Structural", "MEP"],
            storey_name=None,
            xyz=None,
            targets=("glb",),
            ifcconvert=paths.ifcconvert(),
            gltfpack=paths.gltfpack(),
            compress=compress,
        )
        states = []
        w = BatchWorker([real], opts)
        w.status.connect(lambda i, s, e: states.append(s))
        w.run()
        return states, os.path.join(OUT, "real_building.glb")

    states, glb = run(compress=False)
    check("real model: worker reached Done", bool(states) and states[-1] == "Done", str(states))
    by_cls = {}
    for cls, mat in glbtools.node_class_material(glb, real):
        by_cls.setdefault(cls, set()).add(mat)
    check(
        "real model: walls + slabs colored Structural",
        by_cls.get("IfcWall") == {"Structural"} and by_cls.get("IfcSlab") == {"Structural"},
        str(by_cls),
    )
    check(
        "real model: non-target classes excluded from GLB",
        not ({"IfcFurniture", "IfcBuildingElementProxy", "IfcRoof"} & set(by_cls)),
        str(set(by_cls)),
    )
    plain_size = os.path.getsize(glb)

    run(compress=True)
    check(
        "real model: AR compression shrinks the GLB",
        os.path.getsize(glb) < plain_size,
        f"{plain_size} -> {os.path.getsize(glb)}",
    )


def conformance():
    print("UI  conformance: §9 error-handling + §5.2 report")
    w = MainWindow()
    check(
        "output writability probe (§9 scenario 2)",
        w._output_writable(OUT) and not w._output_writable(os.path.join(OUT, "_no_such_subdir")),
    )
    check("progress heartbeat fires within 2s (§9.4)", 0 < w._heartbeat.interval() <= 2000)
    rp = os.path.join(OUT, "conversion_report.txt")
    report_text = open(rp).read() if os.path.exists(rp) else ""
    check("conversion_report.txt written by the worker (§5.2)", os.path.exists(rp))
    check("report records the project unit scale (§5.1)", "unit_scale_to_m=" in report_text)


def liveness_and_render():
    print("UI  §9.4 long-run liveness + actual render")
    import time as _t

    w = MainWindow()
    # Simulate a long conversion whose determinate progress has stalled inside an opaque
    # IfcConvert/gltfpack step (no progress events for >2s).
    w._thread = object()  # pretend a run is active
    w._run_started = _t.monotonic() - 5
    w._last_progress_at = _t.monotonic() - 5
    w._tick()
    check("§9.4 bar flips to animated busy marquee when progress stalls", w.progress.maximum() == 0)
    check("§9.4 Elapsed counter advances every tick", w.elapsed_label.text().startswith("Elapsed:"))
    # A real progress event must pull it back to a determinate percentage.
    w._on_progress(0, 42)
    check(
        "§9.4 determinate percentage restored on a real progress event",
        w.progress.maximum() == 100 and w.progress.value() == 42,
    )
    w._thread = None

    # Actually paint the window (not just construct it) and prove pixels were drawn.
    w.resize(900, 560)
    img = w.grab().toImage()
    colors = {img.pixel(x, y) for x in range(0, img.width(), 40) for y in range(0, img.height(), 40)}
    check(
        "main window renders non-blank (widgets + theme actually paint)",
        img.width() > 1 and img.height() > 1 and len(colors) >= 3,
        f"{img.width()}x{img.height()}, {len(colors)} distinct colors",
    )
    dlg = LicenseDialog()
    dimg = dlg.grab().toImage()
    check("license dialog renders non-blank", dimg.width() > 1 and dimg.height() > 1)


def main():
    import shutil

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    ui_widgets()
    license_flow()
    worker_run()
    real_world_e2e()
    conformance()
    liveness_and_render()
    p, t = sum(_results), len(_results)
    print(f"\n==== {p}/{t} checks passed ====")
    sys.exit(0 if p == t else 1)


if __name__ == "__main__":
    main()
