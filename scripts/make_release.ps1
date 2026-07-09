<#
.SYNOPSIS
  Build + package a release bundle locally (the same steps release.yml runs in CI).

.DESCRIPTION
  Builds the one-folder bundle for a variant, self-tests it, and produces a versioned zip + SHA256.
  meshopt = default backend; draco = also bundles Node + gltf-pipeline (KHR_draco_mesh_compression).
  Use -SkipBuild to package an already-built dist/ (e.g. to validate the packaging step).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\make_release.ps1 -Variant draco -Tag v0.1.0
#>
param(
  [ValidateSet("meshopt", "draco")][string]$Variant = "meshopt",
  [string]$Tag = "v0.1.0",
  [switch]$SkipBuild,
  [switch]$NoObfuscate  # skip Cython obfuscation (default: ON). Obfuscation removes licensing .py — use a fresh checkout.
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $SkipBuild) {
  Write-Host "[1/4] fetch binaries ($Variant)"
  # Draco is the default fetch; the meshopt variant is the minimal (no Node/Draco) bundle.
  if ($Variant -eq "meshopt") { python scripts/fetch_binaries.py --no-draco }
  else { python scripts/fetch_binaries.py }

  if (-not $NoObfuscate) {
    Write-Host "[2/4] obfuscate licensing (Cython -> .pyd) — spec §6.3; use -NoObfuscate to skip"
    python scripts/obfuscate_licensing.py
    if ($LASTEXITCODE -ne 0) { Write-Error "obfuscation failed"; exit 1 }
  }

  Write-Host "[3/4] build bundle"
  pyinstaller main.spec --noconfirm --clean

  Write-Host "[4/4] self-test"
  $env:QT_QPA_PLATFORM = "offscreen"
  & dist/IFC_Converter/IFC_Converter.exe --selftest
  if ($LASTEXITCODE -ne 0) { Write-Error "self-test failed"; exit 1 }
}

if (-not (Test-Path "dist/IFC_Converter/IFC_Converter.exe")) { Write-Error "no bundle in dist/"; exit 1 }
# Draco is the default deliverable -> win64.zip; the meshopt variant is the minimal -> win64-minimal.zip
$suffix = if ($Variant -eq "meshopt") { "-minimal" } else { "" }
$zip = "IFC_Converter-$Tag-win64$suffix.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path dist/IFC_Converter/* -DestinationPath $zip -Force
$hash = (Get-FileHash -Algorithm SHA256 $zip).Hash
"$hash  $zip" | Out-File "$zip.sha256" -Encoding ascii

$mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host ""
Write-Host "==== RELEASE PACKAGE ($Variant) ===="
Write-Host "  $zip  ($mb MB)"
Write-Host "  SHA256 $hash"
