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
  [switch]$SkipBuild
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $SkipBuild) {
  Write-Host "[1/3] fetch binaries ($Variant)"
  if ($Variant -eq "draco") { python scripts/fetch_binaries.py --with-draco }
  else { python scripts/fetch_binaries.py }

  Write-Host "[2/3] build bundle"
  pyinstaller main.spec --noconfirm --clean

  Write-Host "[3/3] self-test"
  $env:QT_QPA_PLATFORM = "offscreen"
  & dist/IFC_Converter/IFC_Converter.exe --selftest
  if ($LASTEXITCODE -ne 0) { Write-Error "self-test failed"; exit 1 }
}

if (-not (Test-Path "dist/IFC_Converter/IFC_Converter.exe")) { Write-Error "no bundle in dist/"; exit 1 }
$suffix = if ($Variant -eq "draco") { "-draco" } else { "" }
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
