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

    import licensing
    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

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
