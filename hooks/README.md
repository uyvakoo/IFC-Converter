# PyInstaller hooks

Custom hooks for the one-folder build (referenced by `main.spec` via `hookspath=["hooks"]`).

Currently empty — `collect_all("ifcopenshell")` in `main.spec` plus the PySide6 bundled hook cover the
native dependencies. Add `hook-<module>.py` files here only if a clean-VM smoke test surfaces a missing
native lib (the usual suspects: OpenCASCADE DLLs, Qt platform plugins).
