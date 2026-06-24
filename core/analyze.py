"""
F1 — Ingestion & analyze pass.

The geometry iterator is used as a READ-ONLY enumerator: it lazily triangulates one element at a
time (memory-safe), and for each element we record its world-space bounding box and class. The
result feeds filtering (F2), cropping (F3), and the report. It never edits the model.
"""
from __future__ import annotations

import multiprocessing
from dataclasses import dataclass, field

import ifcopenshell.geom
import ifcopenshell.util.shape
import numpy as np


@dataclass
class ElementInfo:
    guid: str
    ifc_class: str
    name: str | None
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]


@dataclass
class Analysis:
    elements: dict[str, ElementInfo] = field(default_factory=dict)  # keyed by GlobalId
    class_counts: dict[str, int] = field(default_factory=dict)

    def z_bounds(self, guids):
        zs = [(self.elements[g].bbox_min[2], self.elements[g].bbox_max[2])
              for g in guids if g in self.elements]
        if not zs:
            return None
        return min(z[0] for z in zs), max(z[1] for z in zs)


def run(model, progress_cb=None) -> Analysis:
    """Enumerate every element that has geometry; record class + world bbox.

    progress_cb(percent:int) is called as the iterator advances (0..100).
    """
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)  # verts already world-space -> bbox is min/max of verts

    iterator = ifcopenshell.geom.iterator(settings, model, multiprocessing.cpu_count())
    analysis = Analysis()
    if not iterator.initialize():
        return analysis  # no geometry at all

    last_pct = -1
    while True:
        shape = iterator.get()
        element = model.by_guid(shape.guid)  # bridge geometry -> entity (D6)
        verts = ifcopenshell.util.shape.get_vertices(shape.geometry)  # Nx3 world coords
        if len(verts):
            mn = np.min(verts, axis=0)
            mx = np.max(verts, axis=0)
            info = ElementInfo(
                guid=shape.guid,
                ifc_class=element.is_a(),
                name=getattr(element, "Name", None),
                bbox_min=(float(mn[0]), float(mn[1]), float(mn[2])),
                bbox_max=(float(mx[0]), float(mx[1]), float(mx[2])),
            )
            analysis.elements[shape.guid] = info
            analysis.class_counts[info.ifc_class] = analysis.class_counts.get(info.ifc_class, 0) + 1

        if progress_cb:
            pct = iterator.progress()
            if pct != last_pct:
                progress_cb(pct)
                last_pct = pct

        if not iterator.next():
            break

    if progress_cb and last_pct != 100:
        progress_cb(100)
    return analysis
