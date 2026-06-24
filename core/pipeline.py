"""
Per-file orchestration (F1->F5 glue, headless).

  open -> analyze (F1) -> resolve crop box -> keep-set (filter+crop, F2/F3) -> apply crop (F3, mutate)
  -> color kept elements (F2) -> write UNIQUE temp ifc (D9) -> IfcConvert GLB/STP (F4) -> cleanup.

Pure and Qt-free; a UI worker (Phase B) will call `process` and forward `progress_cb`.
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass, field

import ifcopenshell

from . import analyze, convert, cropping, filtering, postprocess, styling


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
    glb_bytes: int | None = None
    stp_bytes: int | None = None
    compress_stats: dict | None = None
    elapsed_s: float = 0.0


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
    simplify=0.5,
    progress_cb=None,
) -> Result:
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    model = ifcopenshell.open(input_path)
    res = Result(input_path=input_path, schema=model.schema)

    analysis = analyze.run(model, progress_cb=progress_cb)
    box, res.crop_desc = _resolve_box(model, analysis, storey_name, xyz)

    keep = cropping.keep_guids(model, analysis, selected_groups, box)
    res.kept = len(keep)
    res.removed = cropping.apply(model, keep, analysis)

    styles = styling.build_styles(model)
    stats = {"items": 0, "mapped": 0}
    for guid in keep:
        el = model.by_guid(guid)
        group = filtering.group_of(el)
        if group:
            styling.color_element(model, el, styles[group], stats)
    res.style_stats = stats

    stem = os.path.splitext(os.path.basename(input_path))[0]
    fd, temp_ifc = tempfile.mkstemp(suffix=".ifc", prefix=f"{stem}_")
    os.close(fd)
    try:
        model.write(temp_ifc)
        if "glb" in targets:
            res.glb = convert.to_glb(ifcconvert, temp_ifc, os.path.join(out_dir, stem + ".glb"))
            if compress and gltfpack:  # F5: AR Draco/decimate post-step (D1)
                res.compress_stats = postprocess.compress_glb(gltfpack, res.glb, simplify=simplify)
            res.glb_bytes = os.path.getsize(res.glb)
        if "stp" in targets:
            res.stp = convert.to_stp(ifcconvert, temp_ifc, os.path.join(out_dir, stem + ".stp"))
            res.stp_bytes = os.path.getsize(res.stp)
    finally:
        if os.path.exists(temp_ifc):
            os.remove(temp_ifc)  # guaranteed cleanup (D9)

    res.elapsed_s = round(time.time() - t0, 3)
    return res
