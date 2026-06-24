"""
make_fixture.py — multi-storey IFC4 test model for the core pipeline (F1-F5).

Two storeys, all four color groups represented, plus a non-target class:

  Ground (elev 0):   IfcWall (z 0-3), IfcSlab (z 0),     IfcDuctSegment (MEP)
  Level 1 (elev 3):  IfcWall (z 3-6), IfcDoor (Arch),    IfcCableSegment (Cables)
  (building)         IfcRoof (z 6)  -> non-target control

Usage:  python make_fixture.py [out.ifc]   (default: fixture.ifc)
"""
import sys

import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import numpy as np


def _xlate(x=0.0, y=0.0, z=0.0):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def _box(model, body, cls, name, xdim, ydim, depth, at):
    el = ifcopenshell.api.root.create_entity(model, ifc_class=cls, name=name)
    prof = model.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=xdim, YDim=ydim)
    rep = ifcopenshell.api.geometry.add_profile_representation(model, context=body, profile=prof, depth=depth)
    ifcopenshell.api.geometry.assign_representation(model, product=el, representation=rep)
    ifcopenshell.api.geometry.edit_object_placement(model, product=el, matrix=_xlate(*at))
    return el


def build(out_path):
    model = ifcopenshell.api.project.create_file("IFC4")
    project = ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject", name="Fixture")
    ifcopenshell.api.unit.assign_unit(model, length={"is_metric": True, "raw": "METERS"})
    ctx = ifcopenshell.api.context.add_context(model, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        model, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=ctx)

    site = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuilding", name="Building")
    ground = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuildingStorey", name="Ground")
    ground.Elevation = 0.0
    level1 = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuildingStorey", name="Level 1")
    level1.Elevation = 3.0
    ifcopenshell.api.aggregate.assign_object(model, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(model, products=[building], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(model, products=[ground, level1], relating_object=building)

    def wall(name, z):
        w = ifcopenshell.api.root.create_entity(model, ifc_class="IfcWall", name=name)
        rep = ifcopenshell.api.geometry.add_wall_representation(
            model, context=body, length=4.0, height=3.0, thickness=0.2)
        ifcopenshell.api.geometry.assign_representation(model, product=w, representation=rep)
        ifcopenshell.api.geometry.edit_object_placement(model, product=w, matrix=_xlate(0.0, 0.0, z))
        return w

    # Ground storey
    wall_g = wall("Wall G", 0.0)
    slab_g = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSlab", name="Slab G")
    slab_rep = ifcopenshell.api.geometry.add_slab_representation(
        model, context=body, depth=0.2, polyline=[(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)])
    ifcopenshell.api.geometry.assign_representation(model, product=slab_g, representation=slab_rep)
    ifcopenshell.api.geometry.edit_object_placement(model, product=slab_g, matrix=_xlate(0.0, 0.0, 0.0))
    duct_g = _box(model, body, "IfcDuctSegment", "Duct G", 0.3, 0.3, 2.0, (2.0, 2.0, 1.0))
    ground_elems = [wall_g, slab_g, duct_g]

    # Level 1 storey
    wall_1 = wall("Wall 1", 3.0)
    door_1 = _box(model, body, "IfcDoor", "Door 1", 0.9, 0.05, 2.1, (1.0, 0.0, 3.0))
    cable_1 = _box(model, body, "IfcCableSegment", "Cable 1", 0.05, 0.05, 3.0, (3.0, 3.0, 3.0))
    level1_elems = [wall_1, door_1, cable_1]

    # Non-target control
    roof = _box(model, body, "IfcRoof", "Roof", 4.0, 4.0, 0.3, (0.0, 0.0, 6.0))

    ifcopenshell.api.spatial.assign_container(model, products=ground_elems, relating_structure=ground)
    ifcopenshell.api.spatial.assign_container(model, products=level1_elems, relating_structure=level1)
    ifcopenshell.api.spatial.assign_container(model, products=[roof], relating_structure=level1)

    model.write(out_path)
    print(f"wrote {out_path}  schema={model.schema}")
    print("  Ground: IfcWall, IfcSlab, IfcDuctSegment | "
          "Level 1: IfcWall, IfcDoor, IfcCableSegment | IfcRoof (non-target)")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "fixture.ifc")
