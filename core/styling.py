"""
F2 (part 2) — Surface styles & assignment.

Builds one opaque IfcSurfaceStyle per color group and assigns it to an element's representation
ITEMS, recursing through IfcMappedItem. Type-authored geometry (IfcWallType/IfcSlabType) is shared
via IfcMappedItem; assigning to the per-instance pointer colors nothing -> grey GLB (D12). Ported
from the validated screening implementation.
"""
from __future__ import annotations

import ifcopenshell.api.style

from . import filtering


def build_styles(model) -> dict[str, object]:
    """Create the 4 group surface styles in `model`; return {group_name: IfcSurfaceStyle}."""
    styles = {}
    for group, (_classes, rgb) in filtering.COLOR_GROUPS.items():
        style = ifcopenshell.api.style.add_style(model, name=group)
        ifcopenshell.api.style.add_surface_style(
            model, style=style, ifc_class="IfcSurfaceStyleShading",
            attributes={
                "SurfaceColour": {"Name": None, "Red": rgb[0], "Green": rgb[1], "Blue": rgb[2]},
                "Transparency": 0.0,
            },
        )
        styles[group] = style
    return styles


def _assign_to_item(model, item, style, stats):
    if item.is_a("IfcMappedItem"):
        stats["mapped"] += 1
        for sub in item.MappingSource.MappedRepresentation.Items:
            _assign_to_item(model, sub, style, stats)
    else:
        ifcopenshell.api.style.assign_item_style(model, item=item, style=style)
        stats["items"] += 1


def color_element(model, element, style, stats) -> None:
    """Assign `style` to every representation item of `element` (mapped-item-aware)."""
    if not element.Representation:
        return
    for rep in element.Representation.Representations:
        for item in rep.Items:
            _assign_to_item(model, item, style, stats)
