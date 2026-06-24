"""
F2 (part 1) — Entity class filtering & color-group mapping.

The four color groups from the spec (§3.1). Matching is INHERITANCE-AWARE: `element.is_a("IfcWall")`
also matches `IfcWallStandardCase`. Each element maps to exactly ONE group via `group_of`, evaluated in
the dict order below — **Cables is intentionally listed before MEP** because `IfcCableSegment` is a
subtype of `IfcDistributionFlowElement` (the broad MEP class) and must not be swallowed by it.
Membership/keep is group-based (an element is kept iff its group is selected), not a raw `is_a` against
the union of class strings — that is what prevents the cable/MEP bleed.
"""

from __future__ import annotations

# group -> (classes, rgb 0..1). Hex in comments per spec. ORDER = precedence for group_of.
COLOR_GROUPS: dict[str, tuple[tuple[str, ...], tuple[float, float, float]]] = {
    "Structural": (("IfcWall", "IfcSlab", "IfcColumn", "IfcBeam"), (0.8, 0.8, 0.8)),  # #CCCCCC
    "Cables": (("IfcCableSegment",), (0.9, 0.2, 0.2)),  # #E63333
    "Architectural": (
        ("IfcFurnishingElement", "IfcDoor", "IfcWindow", "IfcSpace"),
        (0.6, 0.3, 0.1),
    ),  # #994D1A
    "MEP": (("IfcPipeSegment", "IfcDistributionFlowElement", "IfcDuctSegment"), (0.2, 0.4, 0.8)),  # #3366CC
}

ALL_GROUPS = tuple(COLOR_GROUPS.keys())


def group_of(element) -> str | None:
    """The single color-group an element belongs to (inheritance-aware, precedence by dict order)."""
    for group, (classes, _rgb) in COLOR_GROUPS.items():
        if any(element.is_a(c) for c in classes):
            return group
    return None


def is_kept(element, selected_groups) -> bool:
    """Kept iff the element's group is among the selected groups."""
    return group_of(element) in set(selected_groups)
