"""
Application entry point.

Flow: clock-rollback guard -> License Activation modal (gates the app) -> Main window.
The license public key and binaries resolve via core.paths (._MEIPASS-aware for the bundle).
"""

from __future__ import annotations

import os
import sys


def selftest() -> int:
    """Headless bundle self-check (no GUI/display). Proves bundled native deps + binaries load.
    This is the on-this-machine proxy for the clean-VM smoke test (§8.4)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import subprocess

    import ifcopenshell

    import licensing
    from core import paths

    oks = []

    def ck(name, cond):
        oks.append(bool(cond))
        print(("  OK   " if cond else "  FAIL ") + name)

    ck(f"ifcopenshell {ifcopenshell.version} imports (native libs)", True)
    ck("IfcConvert bundled", os.path.isfile(paths.ifcconvert()))
    ck("gltfpack bundled", os.path.isfile(paths.gltfpack()))
    ck("public_key bundled", os.path.isfile(paths.public_key()))
    try:
        r = subprocess.run([paths.ifcconvert(), "--version"], capture_output=True)
        ck("IfcConvert runs", r.returncode == 0)
    except Exception as e:
        ck(f"IfcConvert runs ({e})", False)
    try:
        licensing.load_public_key_pem()
        ck("public key loads", True)
    except Exception as e:
        ck(f"public key loads ({e})", False)

    # Real end-to-end conversion INSIDE the bundle: build an IFC, then run the full
    # pipeline (filter -> color -> crop -> IfcConvert -> gltfpack) and inspect the GLB.
    try:
        import json
        import struct
        import tempfile

        import ifcopenshell.api.context
        import ifcopenshell.api.geometry
        import ifcopenshell.api.project
        import ifcopenshell.api.root
        import ifcopenshell.api.unit

        from core import pipeline

        with tempfile.TemporaryDirectory() as td:
            m = ifcopenshell.api.project.create_file("IFC4")
            ifcopenshell.api.root.create_entity(m, ifc_class="IfcProject", name="selftest")
            ifcopenshell.api.unit.assign_unit(m, length={"is_metric": True, "raw": "METERS"})
            ctx = ifcopenshell.api.context.add_context(m, context_type="Model")
            body = ifcopenshell.api.context.add_context(
                m,
                context_type="Model",
                context_identifier="Body",
                target_view="MODEL_VIEW",
                parent=ctx,
            )
            wall = ifcopenshell.api.root.create_entity(m, ifc_class="IfcWall", name="W")
            rep = ifcopenshell.api.geometry.add_wall_representation(
                m, context=body, length=4.0, height=3.0, thickness=0.2
            )
            ifcopenshell.api.geometry.assign_representation(m, product=wall, representation=rep)
            ifc_path = os.path.join(td, "selftest.ifc")
            m.write(ifc_path)

            res = pipeline.process(
                ifc_path,
                td,
                ["Structural"],
                targets=("glb",),
                ifcconvert=paths.ifcconvert(),
                gltfpack=paths.gltfpack(),
                compress=True,
            )
            glb_ok = bool(res.glb) and os.path.isfile(res.glb) and os.path.getsize(res.glb) > 0
            ck("real IFC -> GLB conversion (IfcConvert + gltfpack)", glb_ok)
            if glb_ok:
                data = open(res.glb, "rb").read()
                clen = struct.unpack_from("<I", data, 12)[0]
                mats = [x.get("name") for x in json.loads(data[20 : 20 + clen]).get("materials", [])]
                ck("converted GLB carries the 'Structural' material", "Structural" in mats)
    except Exception as e:
        ck(f"real IFC -> GLB conversion ({type(e).__name__}: {e})", False)

    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow

    MainWindow()
    ck("Qt + UI construct (offscreen)", True)

    print(f"selftest: {sum(oks)}/{len(oks)} OK")
    return 0 if all(oks) else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()

    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

    import licensing
    from ui import theme
    from ui.license_window import LicenseDialog
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    theme.apply_theme(app)

    # Clock-rollback guard up front (§6.2). Lock immediately if tampered.
    store = licensing.RegistryStore()
    ok, reason = licensing.check_clock(store)
    if not ok:
        QMessageBox.critical(None, "License", reason)
        return 1

    dlg = LicenseDialog(clock_store=store)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return 0  # not licensed -> exit

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
