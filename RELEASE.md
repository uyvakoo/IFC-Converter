# Releasing IFC Converter

Releases are built and published automatically by `.github/workflows/release.yml` when a version tag
is pushed. Each release ships one self-contained Windows bundle built (and licence-obfuscated) on a
clean `windows-latest` runner.

## Artifacts

| Asset | Notes |
|-------|-------|
| `IFC_Converter-vX.Y.Z-win64.zip` | The one-folder app. Ships the **default Draco** AR backend (`KHR_draco_mesh_compression`, low-poly) — bundles IfcConvert + gltfpack + Node + gltf-pipeline; licence modules Cython-compiled to `.pyd` with the hard-coded public key baked in. |
| `IFC_Converter-vX.Y.Z-win64.zip.sha256` | SHA256 checksum sidecar. |

Self-contained — unzip and run `IFC_Converter.exe` (no Python required). A smaller meshopt-only bundle
(no Node/Draco) can be built locally with `scripts\fetch_binaries.py --no-draco` (see `BUILD.md` §3); the
released artifact is the full Draco bundle since Draco is the spec default.

## Cutting a release

1. Bump the version in **`ui/__init__.py`** (`APP_VERSION`) and `pyproject.toml`; commit on `main`.
2. Tag and push:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
3. The workflow verifies the tag matches `ui.APP_VERSION`, obfuscates the licence modules, builds the
   bundle, **gates on `--selftest` (9/9)**, and publishes a GitHub Release with the zip + `.sha256` +
   auto-generated notes.

The tag is the single trigger; the workflow needs only the repo's default `GITHUB_TOKEN`
(`contents: write`). No secrets required.

## Local dry-run (no GitHub Release)

Build + package a bundle exactly as CI does, to validate the packaging step:
```powershell
# full build + package
powershell -ExecutionPolicy Bypass -File scripts\make_release.ps1 -Variant draco -Tag v0.1.0

# or package an already-built dist/ (fast)
powershell -ExecutionPolicy Bypass -File scripts\make_release.ps1 -Variant draco -Tag v0.1.0 -SkipBuild
```
Produces `IFC_Converter-v0.1.0-win64.zip` + `.sha256` (the default Draco bundle; `-Variant meshopt`
makes the minimal `…-win64-minimal.zip`).

## Obfuscated production build (licensing hardening, free — no PyArmor)

Release builds hardening the licence check (spec §6.3) are now the **default**: both `make_release.ps1`
and the GitHub `release.yml` workflow Cython-compile `licensing/` to native `.pyd` before packaging, so
the shipped bundle carries no licence `.py`/`.pyc` and the §6.2 hard-coded public key lives inside
`core.pyd`. Needs `cython` + MSVC Build Tools on the host (see `BUILD.md` §4). Use `-NoObfuscate` to skip:
```powershell
# on a FRESH checkout (obfuscation strips licensing .py sources), e.g.
git clone https://github.com/MutugiD/ifc-conversion-engine.git rel && cd rel
powershell -ExecutionPolicy Bypass -File scripts\make_release.ps1 -Variant draco -Tag v0.1.0
```
The resulting bundle ships compiled `licensing\*.pyd` (no licence `.py`/`.pyc`); the RSA private key is
never involved. `--selftest` and the licence flow are unchanged. The GitHub `release.yml` workflow runs
the obfuscation step on its fresh checkout, so tagged releases are obfuscated by default.

## Publishing (this repo: `MutugiD/ifc-conversion-engine`, private)

`release.yml` triggers on a `v*` tag and needs only the default `GITHUB_TOKEN` (`contents: write`) — no
secrets. On a **private** repo the published Release is private too (visible to collaborators), which
matches the licensing model (source stays closed; hand out the built `.exe`, not the source). Cutting a
tag on `main` builds + publishes the bundle (zip + SHA256 sidecar) automatically.

## Verifying a download
```powershell
Get-FileHash -Algorithm SHA256 IFC_Converter-v0.1.0-win64.zip
# compare against the .sha256 file
.\IFC_Converter\IFC_Converter.exe --selftest   # should print: selftest: 9/9 OK
```
