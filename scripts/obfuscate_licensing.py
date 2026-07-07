"""
Free licensing obfuscation (no PyArmor) — compile the licensing modules to native Windows `.pyd`.

Spec §6.3 wants the licensing/hashing modules obfuscated. PyArmor needs a paid licence; **Cython** is a
free alternative that compiles the pure-Python modules to native machine code (`.pyd` C extensions). The
shipped bundle then carries compiled code for the licence/clock logic instead of decompilable `.pyc`, a
real bar against patching the check out of the compiled app.

What it does (in place, intended for a RELEASE checkout — it removes source):
  1. cythonize `licensing/core.py` and `licensing/clockguard.py` -> `*.pyd` (via MSVC),
  2. delete the `.py` (and generated `.c`), leaving `__init__.py` + the `.pyd` + `public_key.pem`,
  3. smoke-import the compiled package so the build fails loudly if the extension is broken.

Then build as usual: `pyinstaller main.spec` bundles the `.pyd` (extensions win over source on import).

Prerequisites (build host only): `pip install cython` + a C compiler — MSVC **Build Tools for Visual
Studio** (free; e.g. VS 2019/2022 Build Tools). Not needed at runtime; nothing here ships.

Usage:
    python scripts/obfuscate_licensing.py            # compile + strip sources (release)
    python scripts/obfuscate_licensing.py --keep-sources   # compile but keep .py (inspect only)
    python scripts/obfuscate_licensing.py --check    # just verify Cython + a compiler are available
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "licensing")
MODULES = ("core", "clockguard")  # __init__.py stays a thin re-export; public_key.pem is data


def _have_compiler() -> bool:
    """True if setuptools can find a C compiler (MSVC on Windows)."""
    try:
        from setuptools._distutils import ccompiler, errors

        c = ccompiler.new_compiler()
        try:
            c.initialize()  # MSVCCompiler.initialize() finds VS Build Tools via vswhere
        except (errors.DistutilsPlatformError, AttributeError):
            return False
        return True
    except Exception:
        return False


def _check() -> int:
    try:
        import Cython  # noqa: F401

        cy = True
    except ImportError:
        cy = False
    cc = _have_compiler()
    print(f"Cython installed : {cy}")
    print(f"C compiler found : {cc}")
    if not cy:
        print("  -> pip install cython")
    if not cc:
        print("  -> install MSVC 'Build Tools for Visual Studio' (free)")
    return 0 if (cy and cc) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cython-obfuscate the licensing package (no PyArmor).")
    ap.add_argument("--keep-sources", action="store_true", help="keep the .py after compiling (inspect)")
    ap.add_argument("--check", action="store_true", help="only report Cython + compiler availability")
    args = ap.parse_args(argv)

    if args.check:
        return _check()
    if _check() != 0:
        print("\nERROR: prerequisites missing (see above).")
        return 2

    # Build in an ISOLATED temp dir that holds only the `licensing/` package. Running cythonize -i from
    # the repo root trips setuptools' flat-layout auto-discovery ("multiple top-level packages"); a lone
    # package sidesteps it. The produced `licensing.<mod>` .pyd is then copied back into the real package.
    print(f"\ncythonize -> .pyd: {', '.join(MODULES)}")
    tmp = tempfile.mkdtemp(prefix="obf_licensing_")
    try:
        build_pkg = os.path.join(tmp, "licensing")
        os.makedirs(build_pkg)
        shutil.copy2(os.path.join(PKG, "__init__.py"), build_pkg)
        for m in MODULES:
            shutil.copy2(os.path.join(PKG, f"{m}.py"), build_pkg)
        r = subprocess.run(
            [sys.executable, "-m", "Cython.Build.Cythonize", "-i", "-3"]
            + [os.path.join("licensing", f"{m}.py") for m in MODULES],
            cwd=tmp,
        )
        if r.returncode != 0:
            print("ERROR: cythonize failed")
            return 2
        for m in MODULES:
            built = glob.glob(os.path.join(build_pkg, f"{m}.*.pyd"))
            if not built:
                print(f"ERROR: no .pyd produced for {m}")
                return 2
            shutil.copy2(built[0], os.path.join(PKG, os.path.basename(built[0])))
            if not args.keep_sources:
                os.remove(os.path.join(PKG, f"{m}.py"))
            print(f"  {m}: {os.path.basename(built[0])}" + ("" if args.keep_sources else "  (.py removed)"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # smoke-import the compiled package so a broken build fails here, not at runtime
    smoke = "import licensing; assert licensing.core.__file__.endswith('.pyd'); print('compiled OK')"
    chk = subprocess.run([sys.executable, "-c", smoke], cwd=ROOT)
    if chk.returncode != 0:
        print("ERROR: compiled licensing package failed to import")
        return 2
    print("\nlicensing/ obfuscated (native .pyd). Now run: pyinstaller main.spec")
    return 0


if __name__ == "__main__":
    sys.exit(main())
