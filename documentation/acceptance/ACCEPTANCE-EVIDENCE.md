# §8.4 Clean-VM Acceptance Evidence

Real-world acceptance of the shipped bundle on a **fresh Windows VM with no Python**, captured
2026-07-09. Screenshots and the conversion report are in [`evidence/`](evidence/) (referenced as links,
not embedded, per the docs-markdown-only convention).

## Environment
| Item | Value |
|------|-------|
| VM | Windows 10.0.26100 (Administrator), no Python installed |
| Bundle | `IFC_Converter/` one-folder, obfuscated release |
| Bundle provenance | built from `main` @ `de1b64d`; exe SHA256 `5e1ae7d3…` |
| Machine hash (this VM) | `05ea8f65-0b96-46e4-b95c-c5e45c4eed73` |
| Licence | machine-locked, expiry 2027-12-31, signed with the vendor key |

## Screenshots
| File | Shows |
|------|-------|
| [windows-app-info.png](evidence/windows-app-info.png) | The extracted bundle on the clean VM (no Python) |
| [9-9-selftest.png](evidence/9-9-selftest.png) | `--selftest` result: **`selftest: 9/9 OK`** |
| [license-activation.png](evidence/license-activation.png) | License Activation window with the machine hash |
| [license-key.png](evidence/license-key.png) | The machine hash / signed `license.key` used to activate |
| [build-processing.png](evidence/build-processing.png) | A conversion in progress (queue + progress bar, §4.2/§9.4) |
| [build-done.png](evidence/build-done.png) | Conversion completed (status Done) |
| [output-report.png](evidence/output-report.png) | `conversion_report.txt` opened via **Open Report** (§5.2) |
| [glf-viewer.png](evidence/glf-viewer.png) | The output GLB rendered in a glTF viewer with per-class colours |

## Verified results (independently checked, not just screenshots)

**Self-test** — `selftest: 9/9 OK` on the clean VM (native libs + bundled binaries + hard-coded key +
licence roundtrip + real IFC→GLB all pass). ✔

**Licence gate** — the app stayed at the License window until a machine-locked `license.key` (for
`05ea8f65-…`) was activated, then the main window opened. ✔

**Conversions** ([conversion_report.txt](evidence/conversion_report.txt), all §5.2 fields present):

| Model | Entities kept/removed | GLB | STP | USDZ | Elapsed | Status |
|-------|----------------------|-----|-----|------|---------|--------|
| Building-Architecture.ifc | 10 / 8 | 27,408 B | 1,047,113 B | 19,966 B | 7.3 s | Done |
| Building-Hvac.ifc | 3 / 3 | 22,260 B | 1,050,063 B | 19,161 B | 2.5 s | Done |

- **Colours (GLB, exact spec RGB):** Architecture → Structural `(0.8, 0.8, 0.8)` + Architectural
  `(0.6, 0.3, 0.1)`; HVAC → MEP `(0.2, 0.4, 0.8)`. ✔
- **USDZ:** valid Apple-aligned packages (single `.usda` layer, zip integrity OK). ✔
- **Report:** timestamp, input, crop, filter, entities processed/removed, `unit_scale_to_m=0.001`
  (mm model read correctly, §5.1), glb/stp/usdz bytes, elapsed, status. ✔

## Caveat — GLB compression was OFF in this run
The GLBs above are **plain, uncompressed** glTF (`extensionsRequired = None`); the **"Compress GLB for
AR"** checkbox was not ticked, so the spec's default **Draco-compressed, low-poly** output
(`KHR_draco_mesh_compression`, ~7.9 KB for Architecture) is **not** demonstrated in these screenshots.
The Draco/low-poly default is covered by the automated suites (`validate_core` M5/M5d/M5l), the
frozen-bundle `scripts/draco_check.py`, and the `acceptance_report.py` compress case. **To complete the
evidence, re-run one conversion with "Compress GLB for AR" ticked** and capture the resulting GLB
(it will be ~3–4× smaller and declare `KHR_draco_mesh_compression`).

## Sign-off (§8.4)
| Field | Value |
|-------|-------|
| Tester | __________________________ |
| Date | __________________________ |
| Clean VM (OS / build) | Windows 10.0.26100 |
| Python absent on VM? | ☑ confirmed |
| Self-test | ☑ `9/9 OK` |
| Licence activation | ☑ |
| GUI conversion (GLB/STP/USDZ + colours) | ☑ |
| Draco-compressed GLB captured | ☐ (see caveat — recommend a re-run) |
| Result | ☐ PASS  ☐ PASS w/ note  ☐ FAIL |
| Signature | __________________________ |
