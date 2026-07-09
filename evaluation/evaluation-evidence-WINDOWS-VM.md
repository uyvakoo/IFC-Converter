# IFC Converter — Windows VM Evaluation Evidence (pre-§8.4 acceptance)

Evaluation run of the packaged Windows bundle on an isolated cloud VM (no dev tooling). This is
**evaluation evidence toward the §8.4 clean-VM acceptance — not a signed acceptance yet.** It becomes
the acceptance once the sign-off below is completed (ideally on a strictly no-Python host — see Note 1).

## Environment
| Field | Value |
|-------|-------|
| Host | Microsoft **Windows Server 2025** Datacenter (AWS EC2) |
| RAM | ~1.8 GB |
| Python installed | **Detected on PATH** — see Note 1 (bundle uses its own embedded interpreter) |
| Bundle | `IFC_Converter.exe` (one-folder, self-contained) |
| Bundle SHA256 | `8194EAA45C7565F5A94882A8C69A810BF0FC3119F3E8E59663B97FF4EC8526A4` |
| Date (UTC) | 2026-07-01 |

## Results
| Check | Result |
|-------|--------|
| `--selftest` (native libs + bundled binaries + real IFC→GLB) | **9/9 OK** |
| Real conversion (`sample-large-building.ifc`, IFC4, 0.2 MB, 18 elements) | **status=Done** in 3.673 s |
| GLB produced | 27,408 bytes |
| STP produced | 1,047,113 bytes |
| Entities kept / removed | 10 / 8 |
| Unit scale (mm→m) reported | 0.001 |
| Peak RAM during conversion | **142 MB** (bounded) |
| License activation (RSA-4096, machine-locked) | signed key for the VM's machine hash; activates |
| Output GLB rendered | `evidence/vm_conversion_render.png` — recognizable building, coloured Structural/Architectural, **only our groups** (no leaked materials) |

**Self-test output**
```
OK ifcopenshell 0.8.5 imports (native libs) · OK IfcConvert bundled · OK gltfpack bundled
OK public_key bundled · OK IfcConvert runs · OK public key loads
OK real IFC -> GLB conversion (IfcConvert + gltfpack)
OK converted GLB carries the 'Structural' material · OK Qt + UI construct (offscreen)
selftest: 9/9 OK
```

**Conversion report line**
```
timestamp=2026-07-01T22:00:34+00:00 | input=...\sample-large-building.ifc | crop=none |
filter=Structural,Cables,Architectural,MEP | entities_processed=10 | entities_removed=8 |
unit_scale_to_m=0.001 | glb_bytes=27408 | stp_bytes=1047113 | elapsed_s=3.673 | status=Done
```

## Notes
1. **Python on PATH.** The VM had a `python` on PATH, so it is not a strictly Python-free host as §8.4
   requests. It does not affect the result: a PyInstaller one-folder app runs its **own embedded CPython
   and native libraries from `_internal\`**, never the system PATH — proven by `--selftest` loading
   ifcopenshell/OpenCASCADE from the bundle and completing a real conversion. For a strictly literal
   §8.4 sign-off, re-run on a host with Python uninstalled (or a minimal AMI).
2. **Model size.** `sample-large-building.ifc` is a 0.2 MB real IFC4 building (18 elements) — a valid
   acceptance conversion, not a heavy-model stress test. Heavy-model behaviour (49 MB IFC2x3, 3,714
   elements, bounded ~0.85 GB RAM) was validated separately on the dev machine.

## Checklist
- [x] Bundle runs on a clean cloud VM (no dev toolchain)
- [x] `--selftest` → 9/9 OK
- [x] Real IFC → GLB + STP, `status=Done`
- [x] `conversion_report.txt` written with the full schema
- [x] Peak RAM bounded (142 MB)
- [x] Output GLB verified + rendered (only our group colours) — `evidence/vm_conversion_render.png`
- [ ] (optional/strict) host with **no Python** — see Note 1
- [ ] GUI conversion + screenshots (optional; headless conversion + render verified above)

## Sign-off
| Field | Value |
|-------|-------|
| Tester (name) | __________________________ |
| Date | __________________________ |
| Environment | AWS EC2 Windows Server 2025, ~1.8 GB RAM |
| Result | ☐ PASS  ☐ PASS with notes  ☐ FAIL |
| Signature | __________________________ |
