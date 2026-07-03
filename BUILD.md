# Build Guide (Windows)

Step-by-step build of the one-folder `.exe` bundle (spec §8.5).

## 1. Prerequisites
- **Windows 10/11, 64-bit.**
- **Python 3.11.x (64-bit)** — https://www.python.org/downloads/release/python-3119/
  (the project is pinned to 3.11; 3.12 is **not** supported because some pinned wheels — e.g. numpy —
  resolve differently there).
- Git.

## 2. Set up the environment
```powershell
git clone https://github.com/uyvakoo/IFC-Converter.git
cd IFC-Converter

py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install --require-hashes -r requirements-dev.txt
```
`--require-hashes` enforces the locked, hash-pinned dependency set (any tampered/changed wheel fails
the install).

## 3. Fetch the bundled native binaries
```powershell
.\.venv\Scripts\python scripts\fetch_binaries.py
```
Downloads `IfcConvert.exe` (IfcOpenShell 0.8.5) and `gltfpack.exe` (meshoptimizer 1.1) into `bin\`.
They are not committed; the PyInstaller bundle embeds them.

**Optional — Draco backend.** The default AR compression is meshopt (gltfpack). To also bundle the
Draco backend (`KHR_draco_mesh_compression` via gltf-pipeline), fetch it (needs `npm` on the build
host) and it will be embedded automatically by `main.spec` when present:
```powershell
.\.venv\Scripts\python scripts\fetch_binaries.py --with-draco
```
This adds a portable `bin\node.exe` and `bin\gltfpipe\` (the gltf-pipeline package). The app then
offers `--compress-mode draco` (CLI) / the "draco" mode in the UI. Without it, only meshopt is built.

## 4. (Production) Obfuscate the licensing modules — free, no PyArmor
Spec §6.3 wants `licensing/` obfuscated. Instead of **PyArmor** (paid), compile the licence/clock modules
to native Windows `.pyd` with **Cython** — free, and stronger than shipping decompilable `.pyc`: the
bundle carries machine code for the licence logic, so patching the check out of the compiled app is much
harder. (PyInstaller's `--key` was removed in v6, so this replaces it.)

**Prerequisites (build host only, nothing ships):**
```powershell
.\.venv\Scripts\python -m pip install cython
# + a C compiler: MSVC "Build Tools for Visual Studio" (free, e.g. VS 2019/2022 Build Tools).
.\.venv\Scripts\python scripts\obfuscate_licensing.py --check   # verifies both are present
```

**On a fresh release checkout, before building:**
```powershell
.\.venv\Scripts\python scripts\obfuscate_licensing.py
```
This compiles `licensing\core.py` + `clockguard.py` to `*.pyd`, **removes the `.py` sources**, and
smoke-imports the compiled package. `licensing\` then holds only `__init__.py`, the two `.pyd`, and
`public_key.pem`. The next `pyinstaller main.spec` bundles the `.pyd` (extensions win over source on
import) — verified: the frozen exe still validates licences, and no licence `.py`/`.pyc` ships.

> It **removes source in place** — run it on a throwaway release checkout, not your working tree
> (`git checkout -- licensing` restores the `.py`). The default CI (`ci.yml`) builds the un-obfuscated
> tree; obfuscation is a release-only step. The RSA private key is never involved (it isn't in the repo).

## 5. Build the one-folder bundle
```powershell
.\.venv\Scripts\pyinstaller main.spec
```
Output: `dist\IFC_Converter\IFC_Converter.exe` (+ `_internal\`). The `.spec` drives everything
(`collect_all("ifcopenshell")` for the native OpenCASCADE libraries, the mandatory hidden imports,
bundling of `bin\` and `licensing\public_key.pem`, `strip`, `noupx`).

## 6. Verify the bundle
```powershell
.\dist\IFC_Converter\IFC_Converter.exe --selftest
```
The self-test loads the native libraries from `_MEIPASS` and performs a **real IFC → GLB conversion**
(IfcConvert + gltfpack) — it should print `selftest: 9/9 OK`.

The bundle can also run **headless batch conversions** (no GUI). The frozen `--cli` requires a valid
machine-locked license key (`--license`, hardened in PR #14):
```powershell
.\dist\IFC_Converter\IFC_Converter.exe --cli model.ifc --out out --classes Structural,MEP `
    --glb --stp --usdz --compress --license C:\key.key
```

**AR outputs.** `--glb` (glTF, meshopt/Draco-compressible) and `--usdz` (Apple ARKit / Quick Look) are
both Y-up and carry the four group colours. USDZ is produced by `core/usdz.py` directly from the GLB —
**no extra dependency or bundled binary** (it authors USD + packages a spec-compliant `.usdz` in-process),
so nothing needs adding to the build. STP (`--stp`) is CAD-grade solid geometry via IfcConvert.

### Acceptance / §8.4 test report
Drive the built bundle through real conversions and emit the signable §8.4 test report:
```powershell
.\.venv\Scripts\python scripts\acceptance_report.py .\dist\IFC_Converter\IFC_Converter.exe acceptance_out
```
Produces `acceptance_out\ACCEPTANCE-REPORT.md` with the **bundle SHA256**, the `--selftest` result, the
real-conversion table, and a **clean-VM checklist + sign-off block**. Run it once **on the clean VM**
(step 9), tick the checklist, attach the GUI/output screenshots, and sign. (Not run in CI — repeatedly
launching the windowed bundle on a headless runner can stall; the package job's `--selftest` is the CI
gate.)

## 7. Air-gapped install (no internet on the target)
On a networked machine with the same OS + Python 3.11:
```powershell
.\.venv\Scripts\python scripts\vendor_wheels.py
```
Copy `wheels\` to the target and install with `pip install --no-index --find-links wheels -r requirements.txt`.

## 8. (Optional) Code-sign the executable
```powershell
signtool sign /fd SHA256 /a /f cert.pfx /p <password> dist\IFC_Converter\IFC_Converter.exe
```
Signing reduces SmartScreen/AV friction for distribution.

## 9. Acceptance (spec §8.4)
Copy `dist\IFC_Converter\` to a clean Windows VM with **no Python installed**, offline, and run
`IFC_Converter.exe --selftest` plus a real GUI conversion; capture the signed test report + screenshots.
