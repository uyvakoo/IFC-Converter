# Findings Summary — Spec Review, Results & Remedies

Standalone executive review of the **"IFC Spatial Cropping & AR Suite"** spec. For each finding:
the **spec section**, the **requirement as written**, the **result/finding** (✅ = empirically
verified on ifcopenshell 0.8.5 + IfcConvert 0.8.5 this session), and the **proposed remedy**.
Full per-feature context: see [README](README.md) and [02-defects-and-remedies](02-defects-and-remedies.md).

**Headline:** 12 findings, **4 critical** (D1, D2, D7, D12). **D1 and D2 are now ✔ APPROVED by the
project owner (2026-06-23)** — see the [decision log](#decision-log). D7 and D12 remain technical
must-fixes to apply during the build. The product is fully buildable *correctly*; adopt the
standardized package (end of doc).

---

## Critical findings

### D1 — IfcConvert has no `--draco` / `--optimize`  ✅ ✔ APPROVED  HIGH
- **Status:** ✔ **APPROVED (2026-06-23)** — owner confirmed the flags don't exist and **authorized
  bundling a Draco post-processor in the `.exe`.**
- **Section:** §5.1 (GLB command) and §1 (System Overview: "GLB — glTF + Draco … highly compressed, low-poly").
- **Requirement as written:** run `IfcConvert --y-up --draco --optimize --use-material-names temp.ifc output.glb`.
- **Result/finding:** verified on IfcConvert 0.8.5 (`-h`): GLB output is plain "Binary glTF v2.0"; the
  only glTF flags are `--y-up`, `--use-material-names`, `--use-element-*`, `--ecef`. **No `--draco`,
  no `--optimize`.** The mandated command fails on an unrecognized option, and no compression/low-poly
  happens from IfcConvert at all.
- **Impact:** "compressed low-poly AR GLB" is a **separate deliverable** (extra tool, bundled offline) —
  not a flag. This is the biggest hidden scope item.
- **Approved remedy:** IfcConvert produces a plain GLB; a **bundled post-processor** does Draco +
  decimation: `gltfpack -i out.glb -o out.glb -cc` (recommended — single native exe), or
  `gltf-pipeline -i in -o out -d`. Both authorized for the bundle.
- **Still open (🔶):** size/triangle target, and confirm the client's ARKit decoder supports Draco
  (else ship quantized-but-undracoed GLB via gltfpack).

### D2 — `--key` removed in PyInstaller 6.0, but spec mandates 6.5+ **and** `--key`  ✔ APPROVED  HIGH
- **Status:** ✔ **APPROVED (2026-06-23)** — **drop `--key`; PyArmor on licensing/hashing; keep
  `--strip` and `--noupx`.**
- **Section:** §2 (PyInstaller 6.5.0+), §6.3 (Anti-Debug: "Use PyInstaller's `--key` option"), §8.3 (build command).
- **Requirement as written:** encrypt bytecode with `--key "…"` on a PyInstaller 6.5+ build.
- **Result/finding:** PyInstaller removed the bytecode cipher / `--key` option in **6.0** (deprecated in
  5.x). Passing `--key` to a 6.x build is rejected — the two requirements are mutually exclusive.
- **Approved remedy:** drop `--key`; obfuscate the licensing/hashing modules with **PyArmor** (the spec
  itself lists PyArmor as acceptable in §6.3). Keep `--strip` and `--noupx`.

### D7 — Iterator `continue` filter does **not** crop the written model  HIGH
- **Section:** §4.1 ("if `element.is_a()` is not in the selected classes, use `continue` to skip it"),
  with §4.3 step 2 ("Filter Elements").
- **Requirement as written:** filtering/cropping achieved by skipping elements inside the geometry-iterator loop.
- **Result/finding:** the iterator is a **read/triangulation pass**. Skipping an element with `continue`
  only changes what you *analyze/color* — the element still exists in the model and is serialized to the
  temp IFC, so IfcConvert still converts it. **No crop occurs.**
- **Remedy:** treat iteration as analysis only; perform cropping by **mutating the model** — remove
  out-of-scope entities **before** `model.write()`. (Pairs with D8.)

### D12 — Coloring needs `IfcMappedItem` recursion or the GLB is grey  ✅ HIGH
- **Section:** §3.1 ("Use `assign_item_style()` to apply colours directly to representation items").
- **Requirement as written:** assign the group color to representation items.
- **Result/finding:** type-authored geometry (`IfcWallType`/`IfcSlabType`) is shared via `IfcMappedItem`;
  assigning a style to the per-instance mapped item colors nothing → grey GLB. **Proven this session**
  that recursing into `MappingSource.MappedRepresentation.Items` fixes it.
- **Remedy:** in the styling step, when an item is an `IfcMappedItem`, recurse into the mapped
  representation's items and assign there.

---

## Minor / cleanup findings

### D3 — "Python 3.11 only, never 3.12" is outdated  ✅ MED
- **Section:** §2 ("CRITICAL WARNING: Use Python 3.11 exactly. Do not use 3.12 or later.").
- **Requirement:** pin Python 3.11; avoid 3.12+.
- **Result/finding:** ifcopenshell 0.8.5 installed and ran the full pipeline on **Python 3.12.8** this
  session. The stated rationale ("wheels not stable") is false for 0.8.x.
- **Remedy:** pin **3.11** to satisfy the client literally (lowest friction); document that 3.12 works. 🔶 decide.

### D4 — Build command mixes flags **and** `main.spec`  MED
- **Section:** §8.3.
- **Requirement:** the exact `pyinstaller … <many flags> … main.spec` command.
- **Result/finding:** when a `.spec` file is supplied, PyInstaller ignores most CLI build flags — the
  command is self-contradictory.
- **Remedy:** put everything (`datas`, `binaries`, `hiddenimports`, strip/noupx) **in `main.spec`**; build
  with `pyinstaller main.spec`.

### D5 — Manual vertex unit-scaling double-applies  MED
- **Section:** §5.1 ("If MILLIMETER: divide vertices by 1000.0", etc.) combined with CLI GLB export.
- **Requirement:** scale vertices in Python by the unit factor, and also convert via IfcConvert.
- **Result/finding:** the GLB is produced by IfcConvert (which already emits meters); Python here edits
  the IFC entity model, not mesh vertices. Doing both = wrong scale.
- **Remedy:** let IfcConvert own units; use `ifcopenshell.util.unit.calculate_unit_scale(model)` for
  **reporting/validation only**.

### D6 — `shape.geometry.ifc_element` is not the 0.8 bridge  LOW
- **Section:** §4.1.
- **Requirement:** get the element from the shape via `shape.geometry.ifc_element`.
- **Result/finding:** in 0.8 the iterator shape exposes `.guid`/`.id`; bridge with
  `model.by_guid(shape.guid)` / `model.by_id(shape.id)`.
- **Remedy:** use `by_guid` / `by_id`.

### D8 — Bare entity removal orphans references  MED
- **Section:** §4.3 (implied by "Filter Elements … write … model").
- **Requirement:** produce a filtered/cropped model.
- **Result/finding:** `model.remove(element)` leaves dangling placements, materials, and spatial/
  aggregation relations → invalid IFC.
- **Remedy:** use `ifcopenshell.util.element.remove_deep(model, element)`, or rebuild a kept-only model.

### D9 — Fixed temp filename in shared temp dir  MED
- **Section:** §4.3 step 4 (`temp_path = os.path.join(tempfile.gettempdir(), "cropped_model.ifc")`).
- **Requirement:** that exact temp path/name.
- **Result/finding:** a fixed name in the shared system temp risks collisions and leaves residue if a run
  aborts before cleanup.
- **Remedy:** unique temp per file (`tempfile.mkstemp(suffix=".ifc")` / `TemporaryDirectory`); guarantee
  cleanup in a `finally`.

### D10 — Bundle pinned to IfcConvert 0.8.0; 0.8.5 is current  LOW
- **Section:** §8.2 (download IfcConvert 0.8.0) vs §2 (ifcopenshell 0.8.0+).
- **Requirement:** bundle IfcConvert 0.8.0.
- **Result/finding:** 0.8.5 is the current 0.8.x release and what was validated; flag behavior can vary
  across builds.
- **Remedy:** pin **one** IfcConvert version matching the bundled wheel (**0.8.5**); verify flags on it.

### D11 — Registry clock-rollback guard is deterrence only  INFO
- **Section:** §6.2 (System Time Rollback Protection; optional NTP).
- **Requirement:** store an activation timestamp in the registry; lock if the clock goes backward; optional NTP.
- **Result/finding:** air-gapped → NTP usually unreachable; a user with local admin can edit/clear the
  HKCU key. Stops casual clock-winding only.
- **Remedy:** implement as specified, but **document the threat model honestly** (anti-casual-tamper).
  Treat a missing key as first run; store/compare UTC consistently.

---

## Results table (at a glance)

| ID | Sev | Status | Section | Finding (result) | Remedy |
|----|-----|--------|---------|------------------|--------|
| D1 | High✅ | ✔ Approved | §5.1, §1 | `--draco`/`--optimize` absent in IfcConvert 0.8.x | bundle `gltfpack` post-step (authorized) |
| D2 | High | ✔ Approved | §2, §6.3, §8.3 | `--key` removed in PyInstaller 6.0 | PyArmor; keep `--strip`/`--noupx` |
| D7 | High | Proposed | §4.1, §4.3 | iterator `continue` doesn't crop the written model | mutate model before write |
| D12 | High✅ | Proposed | §3.1 | no `IfcMappedItem` recursion → grey GLB | recurse mapped representation |
| D3 | Med✅ | Proposed | §2 | 3.12 works; "never 3.12" false | pin 3.11 (note 3.12 ok) |
| D4 | Med | Proposed | §8.3 | `.spec` + flags conflict | drive from `main.spec` |
| D5 | Med | Proposed | §5.1 | Python + CLI unit scaling double-applies | IfcConvert owns units |
| D6 | Low | Proposed | §4.1 | wrong shape→element bridge | `by_guid`/`by_id` |
| D8 | Med | Proposed | §4.3 | bare remove orphans refs | `remove_deep` |
| D9 | Med | Proposed | §4.3 | fixed temp name collisions/residue | unique temp + cleanup |
| D10 | Low | Proposed | §8.2 | IfcConvert 0.8.0 vs 0.8.5 | pin 0.8.5 |
| D11 | Info | Proposed | §6.2 | clock guard is deterrence only | document threat model |

### Decision log
| Date | Item | Decision | By |
|------|------|----------|----|
| 2026-06-23 | **D2** `--key` | Drop `--key`; **PyArmor** on licensing/hashing; keep `--strip`, `--noupx`. | Project owner |
| 2026-06-23 | **D1** Draco | Flags confirmed nonexistent; **bundle a Draco post-processor** (gltfpack rec. / gltf-pipeline) in the `.exe`. | Project owner |

---

## Proposed standardized package

**One coherent, pinned stack** (resolves D3, D10, version drift):

| Component | Standardize to | Reason |
|---|---|---|
| Python | 3.11.x (note: 3.12 validated) | D3 |
| ifcopenshell | 0.8.5 | matches binary |
| **IfcConvert** | **0.8.5** (not 0.8.0) | D10 |
| PySide6 / cryptography / machineid / ntplib | 6.6+ / 42+ / 0.3+ / latest | per spec |
| **+ gltfpack** (or gltf-pipeline) | bundled in `./bin/` | **D1 ✔ approved** — real Draco/low-poly |
| **+ PyArmor** | obfuscate `licensing/*` | **D2 ✔ approved** — replaces `--key` |
| PyInstaller | 6.5+, via `main.spec` | D2, D4 |

**Corrected commands**
- GLB: `IfcConvert --y-up --use-material-names temp.ifc out.glb` → `gltfpack -i out.glb -o out.glb -cc`
- STP: `IfcConvert --convert-back-units temp.ifc out.stp`
- Build: `pyinstaller main.spec` — with `--collect-all ifcopenshell` (native OCC DLLs), hidden imports
  (`ifcopenshell.express.express_parser`, `…util.unit`, `…geom.serializers`), `--strip --noupx`,
  **no `--key`**; optional `signtool` code-signing.

**Standardized per-file pipeline contract**
open → **analyze** (iterator: bounds + inventory + progress) → **crop = mutate** (`remove_deep` on
rejects; D7/D8) → **color** (mapped-item-aware; D12) → **write unique temp** (D9) → **IfcConvert**
(GLB/STP) → **gltfpack** post (D1) → cleanup + report. Units owned by IfcConvert (D5); element bridge
via `by_guid` (D6).

**Approved (2026-06-23):** D1 — bundle a Draco post-processor in the `.exe`; D2 — PyArmor instead of
`--key`, keep `--strip`/`--noupx`.

**Open decisions before quoting (🔶):** Draco compression target + ARKit decoder support (D1 sub-item);
Python 3.11 vs 3.12 (D3); cropping partial-overlap policy and "no solid slicing" confirmation;
commercial terms/milestones before handing over full source.
