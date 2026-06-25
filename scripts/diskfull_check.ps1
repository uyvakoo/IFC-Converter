<#
.SYNOPSIS
  Genuinely exercise the spec section 9.3 disk-full guard by filling a REAL (virtual) NTFS volume.

.DESCRIPTION
  Creates a small fixed VHD with diskpart, formats it NTFS, fills it so free space drops below the
  pipeline's (input + 10 MB) floor, then runs the BUILT bundle "--cli ... --out <VHD>:\out --glb"
  against it. Asserts the exe prints the disk-space FatalError and exits 2. The VHD is always
  detached and deleted in the finally block. No mocks: real shutil.disk_usage read and/or real ENOSPC.

  Requires Administrator (VHD create/attach + fsutil).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\diskfull_check.ps1 dist\IFC_Converter\IFC_Converter.exe
#>
param(
  [string]$Exe = "dist\IFC_Converter\IFC_Converter.exe",
  [string]$Fixture = "tests\fixtures\fixture.ifc"
)

$ErrorActionPreference = "Stop"
$Exe = (Resolve-Path $Exe).Path
$Fixture = (Resolve-Path $Fixture).Path
$code = 1

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) { Write-Host "[SKIP] not elevated - re-run this script as Administrator"; exit 3 }

# pick a free drive letter
$used = (Get-PSDrive -PSProvider FileSystem).Name
$letter = ('Y','Z','W','V','U','T' | Where-Object { $used -notcontains $_ } | Select-Object -First 1)
$vhd = Join-Path $env:TEMP ("ifcdf_{0}.vhd" -f $PID)
$mk = Join-Path $env:TEMP ("ifcdf_mk_{0}.txt" -f $PID)
$rm = Join-Path $env:TEMP ("ifcdf_rm_{0}.txt" -f $PID)

try {
  @"
create vdisk file="$vhd" maximum=24 type=fixed
attach vdisk
create partition primary
format fs=ntfs quick label=ifcdf
assign letter=$letter
"@ | Out-File -Encoding ascii $mk
  diskpart /s $mk | Out-Null

  $root = ($letter + ":")
  $free = (Get-PSDrive $letter).Free
  Write-Host ("[setup] VHD volume {0} free after format = {1} MB" -f $root, [int]($free/1MB))
  # leave ~2 MB free -> well under the 10 MB floor
  $fill = [int64]($free - 2MB)
  if ($fill -gt 0) { fsutil file createnew "$root\filler.bin" $fill | Out-Null }
  $freeNow = (Get-PSDrive $letter).Free
  New-Item -ItemType Directory -Force "$root\out" | Out-Null
  Write-Host ("[setup] free now = {0} MB (pipeline needs input + 10 MB)" -f [int]($freeNow/1MB))

  Write-Host ("[run] {0} --cli <fixture> --out {1}\out --glb" -f $Exe, $root)
  $out = & $Exe --cli $Fixture --out "$root\out" --glb 2>&1 | Out-String
  $rc = $LASTEXITCODE
  Write-Host "----- exe output -----"; Write-Host $out.Trim(); Write-Host "----------------------"
  Write-Host ("[result] exit={0}" -f $rc)

  $glb = Test-Path "$root\out\fixture.glb"
  $okExit = ($rc -eq 2)
  $okMsg  = ($out -match "disk space")
  $okNoGlb = (-not $glb)
  Write-Host ("[check] exit==2            : {0}" -f $okExit)
  Write-Host ("[check] FatalError 'disk'  : {0}" -f $okMsg)
  Write-Host ("[check] no GLB written     : {0}" -f $okNoGlb)
  if ($okExit -and $okMsg -and $okNoGlb) { Write-Host "`n==== DISK-FULL PASS (real VHD) ===="; $code = 0 }
  else { Write-Host "`n==== DISK-FULL FAIL ===="; $code = 1 }
}
finally {
  @"
select vdisk file="$vhd"
detach vdisk
"@ | Out-File -Encoding ascii $rm
  try { diskpart /s $rm | Out-Null } catch {}
  Remove-Item $vhd, $mk, $rm -Force -ErrorAction SilentlyContinue
  Write-Host "[cleanup] VHD detached and deleted"
}
exit $code
