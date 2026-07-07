"""
Per-file orchestration (F1->F5 glue, headless).

  open -> analyze (F1) -> resolve crop box -> keep-set (filter+crop, F2/F3) -> apply crop (F3, mutate)
  -> color kept elements (F2) -> write UNIQUE temp ifc (D9) -> IfcConvert GLB/STP (F4) -> cleanup.

Pure and Qt-free; a UI worker (Phase B) will call `process` and forward `progress_cb`.
"""

from __future__ import annotations

import errno
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field

import ifcopenshell
import ifcopenshell.util.unit

from . import analyze, convert, cropping, filtering, postprocess, styling, usdz
from .errors import FatalError, FileError

# Disk-space floor (bytes) kept free on top of the input size before we start writing (§9.3).
_DISK_FLOOR = 10 * 1024 * 1024


@dataclass
class Result:
    input_path: str
    schema: str = ""
    crop_desc: str = ""
    kept: int = 0
    removed: int = 0
    style_stats: dict = field(default_factory=dict)
    glb: str | None = None
    stp: str | None = None
    usdz: str | None = None
    glb_bytes: int | None = None
    stp_bytes: int | None = None
    usdz_bytes: int | None = None
    compress_stats: dict | None = None
    usdz_stats: dict | None = None
    unit_scale: float | None = None  # project length unit -> metres (§5.1; reporting only, D5)
    elapsed_s: float = 0.0


def _open_model(input_path):
    """Open an IFC, mapping missing/corrupt/invalid inputs to a clear FileError (§9.1, scenario 1)."""
    name = os.path.basename(input_path)
    if not os.path.isfile(input_path):
        raise FileError(f"File not found: {input_path}")
    # Sniff the STEP/SPF header first. Every conformant IFC-SPF file starts with "ISO-10303-21;".
    # Rejecting non-IFC bytes here keeps garbage out of the native parser (which can stall or take a
    # native error path on some hosts) and gives a clean message fast.
    try:
        with open(input_path, "rb") as f:
            head = f.read(4096)
    except OSError as e:
        raise FileError(f"Cannot read IFC (corrupt or invalid): {name} — {e}") from e
    if b"ISO-10303-21" not in head:
        raise FileError(f"Cannot read IFC (corrupt or invalid): {name} — not an IFC-SPF file")
    try:
        return ifcopenshell.open(input_path)
    except FileError:
        raise
    except Exception as e:  # ifcopenshell raises bare RuntimeError on otherwise-malformed input
        raise FileError(f"Cannot read IFC (corrupt or invalid): {name} — {e}") from e


def _ensure_disk_space(out_dir, input_path):
    """Preflight free space at the output before writing; abort the run if short (§9.3, scenario 3)."""
    try:
        free = shutil.disk_usage(out_dir).free
    except OSError:
        return  # cannot probe -> let the actual write surface any real ENOSPC
    need = os.path.getsize(input_path) + _DISK_FLOOR
    if free < need:
        raise FatalError(
            f"Insufficient disk space in {out_dir}: need ~{need // (1024 * 1024)} MB, "
            f"have {free // (1024 * 1024)} MB — free space and retry"
        )


def _resolve_box(model, analysis, storey_name, xyz):
    if xyz is not None:
        return tuple(xyz), f"xyz{xyz}"
    if storey_name:
        for st in model.by_type("IfcBuildingStorey"):
            if (st.Name or "") == storey_name:
                return cropping.storey_z_box(st, analysis), f"storey:{storey_name}"
        raise ValueError(f"storey not found: {storey_name!r}")
    return None, "none"


def process(
    input_path,
    out_dir,
    selected_groups,
    *,
    storey_name=None,
    xyz=None,
    targets=("glb",),
    ifcconvert=None,
    gltfpack=None,
    compress=False,
    compress_mode="meshopt",
    node=None,
    gltf_pipeline=None,
    simplify=0.5,
    progress_cb=None,
) -> Result:
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    model = _open_model(input_path)  # §9.1 scenario 1: corrupt/missing -> clear FileError
    _ensure_disk_space(out_dir, input_path)  # §9.3 scenario 3: disk-full preflight -> FatalError
    res = Result(input_path=input_path, schema=model.schema)
    # §5.1: read the project unit scale (to metres) for the report. Units are owned by
    # IfcConvert at export time; this is for logging/validation only (D5 — no Python rescaling).
    res.unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)

    analysis = analyze.run(model, progress_cb=progress_cb)
    box, res.crop_desc = _resolve_box(model, analysis, storey_name, xyz)

    keep = cropping.keep_guids(model, analysis, selected_groups, box)
    res.kept = len(keep)
    if res.kept == 0:  # §9 scenario 5: nothing matched the classes/crop -> clear FileError, no empty GLB
        raise FileError("No elements matched the selected classes / crop region — nothing to export")
    res.removed = cropping.apply(model, keep, analysis)
    # Also drop any element outside the selected classes that the analyze pass missed (real models
    # carry geometry — e.g. IfcBuildingElementProxy — IfcConvert would otherwise render uncoloured).
    res.removed += cropping.remove_unselected(model, selected_groups)

    styles = styling.build_styles(model)
    stats = {"items": 0, "mapped": 0}
    # Colour by the class filter over the SURVIVING elements — not the analyze-based keep set. Real
    # models contain selected-class geometry the iterator missed (e.g. some IFC2x3 IfcWallStandardCase);
    # those survive the crop and must still get our colour, not fall back to their material/class name.
    selected = set(selected_groups)
    for el in model.by_type("IfcElement"):
        group = filtering.group_of(el)
        if group in selected:
            styling.color_element(model, el, styles[group], stats)
    res.style_stats = stats
    # §3.1: our colours must override existing named materials — drop material associations so
    # IfcConvert colours by our surface styles only (real models otherwise keep e.g. "Hout- Meranti").
    styling.strip_material_associations(model)

    stem = os.path.splitext(os.path.basename(input_path))[0]
    fd, temp_ifc = tempfile.mkstemp(suffix=".ifc", prefix=f"{stem}_")
    os.close(fd)
    try:
        try:
            model.write(temp_ifc)
        except OSError as e:  # §9.3 scenario 3: ran out of space mid-write
            if e.errno == errno.ENOSPC:
                raise FatalError("Out of disk space while writing output — free space and retry") from e
            raise
        # GLB is also the source for USDZ (F6). When USDZ is requested without GLB, build a throwaway
        # GLB just to derive the USDZ. Always derive USDZ from the PLAIN GLB — before the F5 compression
        # step encodes the buffers (core.usdz reads plain glTF accessors only).
        if "glb" in targets or "usdz" in targets:
            if "glb" in targets:
                glb_path = os.path.join(out_dir, stem + ".glb")
                keep_glb = True
            else:
                gfd, glb_path = tempfile.mkstemp(suffix=".glb", prefix=f"{stem}_")
                os.close(gfd)
                keep_glb = False
            convert.to_glb(ifcconvert, temp_ifc, glb_path)
            try:
                if "usdz" in targets:  # F6: iOS-native AR — GLB -> USDZ (dependency-free)
                    res.usdz = os.path.join(out_dir, stem + ".usdz")
                    res.usdz_stats = usdz.glb_to_usdz(glb_path, res.usdz)
                    res.usdz_bytes = os.path.getsize(res.usdz)
                if "glb" in targets:
                    res.glb = glb_path
                    if compress:  # F5: AR post-step — gltfpack meshopt (D1) or gltf-pipeline Draco
                        res.compress_stats = postprocess.compress_glb(
                            gltfpack,
                            res.glb,
                            mode=compress_mode,
                            simplify=simplify,
                            node=node,
                            gltf_pipeline=gltf_pipeline,
                        )
                    res.glb_bytes = os.path.getsize(res.glb)
            finally:
                if not keep_glb and os.path.exists(glb_path):
                    os.remove(glb_path)  # temp GLB existed only to derive the USDZ
        if "stp" in targets:
            res.stp = convert.to_stp(ifcconvert, temp_ifc, os.path.join(out_dir, stem + ".stp"))
            res.stp_bytes = os.path.getsize(res.stp)
    finally:
        if os.path.exists(temp_ifc):
            os.remove(temp_ifc)  # guaranteed cleanup (D9)

    res.elapsed_s = round(time.time() - t0, 3)
    return res
