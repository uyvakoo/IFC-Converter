# 00 — System Overview

## What it is
A **standalone Windows desktop application** that batch-converts heavy IFC (BIM) files into three
target formats, fully offline (air-gapped), behind a hardware-locked license, shipped as a
single-folder PyInstaller bundle.

- **Target 1 — STP (STEP):** precise CAD-grade solid geometry, no colors.
- **Target 2 — GLB (glTF + Draco, default):** Draco-compressed, low-poly visual assets for mobile AR
  (iPad / ARKit).
- **Target 3 — USDZ:** Apple ARKit / Quick Look format, produced dependency-free from the GLB by
  `core/usdz.py`.

The application's own Python code performs **filtering, spatial cropping, and recoloring**; the
actual format conversion is delegated to the bundled **IfcConvert.exe** CLI. Everything else (GUI,
batch queue, licensing, packaging) is scaffolding around that core pipeline.

## Goals / non-negotiables (from the spec)
- 100% local: no cloud, no telemetry.
- Handle large IFC files without exhausting RAM (streaming geometry).
- Per-class color coding for AR visibility.
- Storey-based and manual XYZ cropping.
- Sequential batch processing with a responsive UI.
- RSA machine-locked licensing with clock-rollback protection.
- Distributable as a one-folder `.exe` that runs on a clean, Python-less, offline Windows VM.

## The two value layers (keep them separate)
1. **Geometry pipeline** — open → filter → crop → color → temp IFC → IfcConvert → GLB/STP/USDZ →
   (GLB) Draco/decimate. This is genuine BIM engineering and is **de-riskable today**; it is the
   exact pipeline validated during the screening, extended with cropping and additional outputs.
2. **Commercial hardening** — licensing, anti-tamper/obfuscation, PyInstaller packaging, clean-VM
   testing, code-signing. This is where **schedule and acceptance risk** concentrate (clean-VM
   native-dep gaps, Cython-obfuscation/PyInstaller integration, AV false-positives).

Architecturally these are independent. Build and prove layer 1 headless first; wrap it in layer 2.

## Scope boundaries / non-goals
- **Cropping = element inclusion/exclusion, not solid slicing.** A Z-range or XYZ box decides which
  whole elements survive; it does **not** cut a wall in half at the box plane (true geometric
  clipping is a much larger effort and is not what the spec describes). 🔶 Confirm this reading.
- **No STP coloring** — STEP carries no material styles here; colors apply to GLB only.
- **No manual geometry math in Python** — units and Y-up are owned by IfcConvert; Python must not
  also rotate/scale vertices (see D5).
- **AR runtime is not in scope** — we produce the GLB; the iPad/ARKit app that consumes it is the
  client's.

## What this documentation does NOT include (deferred to build phase) 🔒
Application source code, `requirements.txt`, PyInstaller spec/build, the `.exe`, signed test
report, and any message to the client. Those are follow-on work once this pack has been studied.

## Reference platform
- Windows 10/11 (64-bit), **Python 3.11.x** (the pinned target — validated on 3.11.9),
  **ifcopenshell 0.8.5**, **IfcConvert 0.8.5** (OCC 7.8.1), **gltfpack 1.1**.
- The geometry pipeline is confirmed end-to-end (filter → color → crop → GLB/STP) on both a synthetic
  IFC4 fixture and a real buildingSMART model, on Python 3.11 locally and on the Windows CI runner.
  See [12-build-order-verification](12-build-order-verification.md).
