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
        attrs = {"SurfaceColour": {"Name": None, "Red": rgb[0], "Green": rgb[1], "Blue": rgb[2]}}
        # Transparency was added to IfcSurfaceStyleShading in IFC4; it does not exist in IFC2X3
        # (which is opaque by default), so only set it on schemas that have it.
        if model.schema != "IFC2X3":
            attrs["Transparency"] = 0.0
        ifcopenshell.api.style.add_surface_style(
            model, style=style, ifc_class="IfcSurfaceStyleShading", attributes=attrs
        )
        styles[group] = style
    return styles


def _assign_to_item(model, item, style, stats):
    """Assign the surface style to a representation item, recursing through IfcMappedItem instances."""
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


def strip_material_associations(model) -> int:
    """Remove all IfcRelAssociatesMaterial so IfcConvert colours by OUR per-group surface styles only.

    Real models attach named materials (e.g. "01 Hout - hardhout", style "Hout- Meranti") whose style
    IfcConvert would otherwise prefer over our assigned colour — leaving kept elements the wrong colour
    (spec §3.1 says our colour overrides). Materials aren't needed for the GLB colour (we own it) or the
    STP solids (geometry only), so dropping the associations is safe and makes our override complete.
    """
    n = 0
    for rel in list(model.by_type("IfcRelAssociatesMaterial")):
        model.remove(rel)
        n += 1
    return n
