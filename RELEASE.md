# Releasing IFC Converter

Releases are built and published automatically by `.github/workflows/release.yml` when a version tag
is pushed. Each release ships **two** Windows bundles built on a clean `windows-latest` runner.

## Artifacts

| Asset | Backend | Notes |
|-------|---------|-------|
| `IFC_Converter-vX.Y.Z-win64.zip` | meshopt (default) | gltfpack `EXT_meshopt_compression`. Smaller download. |
| `IFC_Converter-vX.Y.Z-win64-draco.zip` | meshopt **+ Draco** | also bundles Node + gltf-pipeline for `KHR_draco_mesh_compression` (~70 MB larger). |

Each zip has a matching `.sha256` checksum file. Both bundles are self-contained one-folder apps —
unzip and run `IFC_Converter.exe` (no Python required).

## Cutting a release

1. Bump the version in **`ui/__init__.py`** (`APP_VERSION`) and `pyproject.toml`; commit on `main`.
2. Tag and push:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
3. The workflow verifies the tag matches `ui.APP_VERSION`, builds both bundles, runs `--selftest` on
   each, and publishes a GitHub Release with the four assets + auto-generated notes.

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
Produces `IFC_Converter-v0.1.0-win64-draco.zip` + `.sha256`.

## Obfuscated production build (licensing hardening, free — no PyArmor)

For a build that hardens the licence check (spec §6.3), Cython-compile `licensing/` to native `.pyd`
before packaging. Add `-Obfuscate` (needs `cython` + MSVC Build Tools on the host — see `BUILD.md` §4):
```powershell
# on a FRESH checkout (it strips licensing .py sources), e.g.
git clone https://github.com/MutugiD/ifc-conversion-engine.git rel && cd rel
powershell -ExecutionPolicy Bypass -File scripts\make_release.ps1 -Variant draco -Tag v0.1.0 -Obfuscate
```
The resulting bundle ships compiled `licensing\*.pyd` (no licence `.py`/`.pyc`); the RSA private key is
never involved. `--selftest` and the licence flow are unchanged. The default GitHub release workflow
builds the **un-obfuscated** tree — cut the obfuscated bundle locally (or add the step to a private
release workflow) so the free obfuscation stays a deliberate, key-holder action.

## Publishing (this repo: `MutugiD/ifc-conversion-engine`, private)

`release.yml` triggers on a `v*` tag and needs only the default `GITHUB_TOKEN` (`contents: write`) — no
secrets. On a **private** repo the published Release is private too (visible to collaborators), which
matches the licensing model (source stays closed; hand out the built `.exe`, not the source). Cutting a
tag on `main` builds + publishes the meshopt and Draco zips with SHA256 sidecars automatically.

## Verifying a download
```powershell
Get-FileHash -Algorithm SHA256 IFC_Converter-v0.1.0-win64-draco.zip
# compare against the .sha256 file
.\IFC_Converter\IFC_Converter.exe --selftest   # should print: selftest: 9/9 OK
```
