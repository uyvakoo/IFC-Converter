"""
F3 — Spatial cropping (core IP).

Cropping is a MODEL MUTATION, not an iterator skip (D7): elements that fail the class filter or fall
outside the crop box are removed with `remove_deep2` so references don't orphan (D8). Bounds come from
the F1 analyze pass (world coordinates) — no re-triangulation.

Crop box = (xmin, xmax, ymin, ymax, zmin, zmax); any axis may be None (unbounded). Storey mode produces
a Z-only box. Partial-overlap policy: keep an element if its bbox has POSITIVE-length overlap with the
box on every bounded axis (touching a boundary does not count — controlled by `tol`).
"""

from __future__ import annotations

import ifcopenshell.api.root

from . import filtering

Box = tuple  # (xmin, xmax, ymin, ymax, zmin, zmax), entries may be None


def storey_contained_guids(storey) -> set[str]:
    """GlobalIds of the elements a storey directly contains (via IfcRelContainedInSpatialStructure)."""
    guids = set()
    for rel in getattr(storey, "ContainsElements", None) or []:
        for el in rel.RelatedElements:
            if getattr(el, "GlobalId", None):
                guids.add(el.GlobalId)
    return guids


def storey_z_box(storey, analysis, pad: float = 3.0) -> Box:
    """Z-only crop box for a storey: min/max Z of its contained elements; fallback Elevation +/- pad."""
    guids = storey_contained_guids(storey)
    zb = analysis.z_bounds(guids)
    if zb is None:
        elev = getattr(storey, "Elevation", None) or 0.0
        return (None, None, None, None, elev - pad, elev + pad)
    return (None, None, None, None, zb[0], zb[1])


def _overlaps(info, box: Box, tol: float = 1e-6) -> bool:
    """True if the element's bbox has positive-length overlap with the box on every bounded axis."""
    mn, mx = info.bbox_min, info.bbox_max
    axes = [
        (box[0], box[1], mn[0], mx[0]),
        (box[2], box[3], mn[1], mx[1]),
        (box[4], box[5], mn[2], mx[2]),
    ]
    for lo, hi, blo, bhi in axes:
        if lo is not None and bhi <= lo + tol:
            return False
        if hi is not None and blo >= hi - tol:
            return False
    return True


def keep_guids(model, analysis, selected_groups, box: Box | None) -> set[str]:
    """GUIDs whose group is selected AND (if a box is given) whose bbox overlaps it."""
    selected = set(selected_groups)
    out = set()
    for guid, info in analysis.elements.items():
        el = model.by_guid(guid)
        if filtering.group_of(el) not in selected:
            continue
        if box is not None and not _overlaps(info, box):
            continue
        out.add(guid)
    return out


def remove_unselected(model, selected_groups) -> int:
    """Remove every IfcElement whose class is not in a selected group (filter completeness).

    `apply` only removes elements the analyze pass captured; real models also contain geometry the
    iterator missed (e.g. IfcBuildingElementProxy) that IfcConvert would still render — uncoloured and
    outside the chosen classes. Dropping anything outside the selected groups keeps the output to only
    the chosen, coloured geometry (spec §3.1 "the user selects what to keep").
    """
    selected = set(selected_groups)
    removed = 0
    for el in list(model.by_type("IfcElement")):
        try:
            if filtering.group_of(el) in selected:
                continue
            ifcopenshell.api.root.remove_product(model, product=el)
        except RuntimeError:
            continue  # already removed via a prior cascade
        removed += 1
    return removed


def apply(model, keep: set[str], analysis) -> int:
    """Remove every analyzed (geometric) element NOT in `keep`. Returns count removed.

    On real models a `remove_product` can cascade dependents (aggregated/nested/voided elements), so a
    later target may already be gone — `by_guid` then *raises* (it does not return None). Guard it and
    skip the already-removed instance instead of crashing the whole file.
    """
    removed = 0
    for guid in list(analysis.elements):
        if guid in keep:
            continue
        try:
            el = model.by_guid(guid)
        except RuntimeError:
            continue  # already removed via a prior cascade (nested/aggregated/voided element)
        ifcopenshell.api.root.remove_product(model, product=el)  # clean product removal
        removed += 1
    return removed
