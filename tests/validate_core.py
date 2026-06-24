"""
Assertion suite for the headless core (M1-M3). Run from project root:
    python tests/validate_core.py
"""

from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import ifcopenshell

import tests.glbtools as glbtools
from core import analyze, cropping, filtering, pipeline

FIXTURE = os.path.join(HERE, "fixtures", "fixture.ifc")
REAL = os.path.join(HERE, "fixtures", "real_building.ifc")
IFCCONVERT = os.path.join(ROOT, "bin", "IfcConvert.exe")
GLTFPACK = os.path.join(ROOT, "bin", "gltfpack.exe")
OUT = os.path.join(HERE, "_out")

_results = []


def check(name, cond, detail=""):
    _results.append(bool(cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


# ---- M1 -------------------------------------------------------------------
def m1():
    print("M1  analyze (F1)")
    m = ifcopenshell.open(FIXTURE)
    a = analyze.run(m)
    check("7 geometric elements", len(a.elements) == 7, f"{len(a.elements)}")
    check("2 IfcWall", a.class_counts.get("IfcWall") == 2)
    check("MEP duct present", a.class_counts.get("IfcDuctSegment") == 1)
    # world Z bounds correct
    walls = [i for i in a.elements.values() if i.ifc_class == "IfcWall"]
    zmaxes = sorted(round(w.bbox_max[2], 2) for w in walls)
    check("wall Z maxima are 3 and 6", zmaxes == [3.0, 6.0], str(zmaxes))


# ---- M2 -------------------------------------------------------------------
def m2():
    print("M2  filter + color (F2)  [classes=Structural,MEP, no crop]")
    r = pipeline.process(FIXTURE, OUT, ["Structural", "MEP"], targets=("glb",), ifcconvert=IFCCONVERT)
    # Structural: 2 walls + 1 slab; MEP: 1 duct  -> 4 kept; removed: door, cable, roof (3)
    check("kept == 4", r.kept == 4, f"{r.kept}")
    check("removed == 3", r.removed == 3, f"{r.removed}")
    nm = glbtools.node_class_material(r.glb, FIXTURE)
    check("GLB has exactly 4 mapped meshes", len(nm) == 4, f"{len(nm)}")
    by_cls = {}
    for cls, mat in nm:
        by_cls.setdefault(cls, set()).add(mat)
    check(
        "walls/slab use 'Structural' material",
        by_cls.get("IfcWall") == {"Structural"} and by_cls.get("IfcSlab") == {"Structural"},
        str(by_cls),
    )
    check("duct uses 'MEP' material", by_cls.get("IfcDuctSegment") == {"MEP"}, str(by_cls))
    check(
        "no Architectural/Cables/Roof in GLB", not ({"IfcDoor", "IfcCableSegment", "IfcRoof"} & set(by_cls))
    )


# ---- M3 -------------------------------------------------------------------
def m3():
    print("M3  spatial crop (F3)  [all classes, storey=Ground]")
    r = pipeline.process(
        FIXTURE,
        OUT,
        list(filtering.ALL_GROUPS),
        storey_name="Ground",
        targets=("glb",),
        ifcconvert=IFCCONVERT,
    )
    # Ground contains wall_g, slab_g, duct_g -> kept 3; removed wall_1, door, cable, roof (4)
    check("kept == 3 (ground only)", r.kept == 3, f"{r.kept}")
    check("removed == 4", r.removed == 4, f"{r.removed}")
    nm = glbtools.node_class_material(r.glb, FIXTURE)
    classes = sorted(c for c, _ in nm)
    check(
        "GLB has only the 3 ground classes", classes == ["IfcDuctSegment", "IfcSlab", "IfcWall"], str(classes)
    )

    # M3 mutation produces a VALID, re-parseable IFC with only ground geometry
    print("M3b mutated model re-parses cleanly")
    m = ifcopenshell.open(FIXTURE)
    a = analyze.run(m)
    st = next(s for s in m.by_type("IfcBuildingStorey") if s.Name == "Ground")
    box = cropping.storey_z_box(st, a)
    keep = cropping.keep_guids(m, a, list(filtering.ALL_GROUPS), box)
    cropping.apply(m, keep, a)
    fd, tmp = tempfile.mkstemp(suffix=".ifc")
    os.close(fd)
    try:
        m.write(tmp)
        reopened = ifcopenshell.open(tmp)
        with_geom = [e for e in reopened.by_type("IfcElement") if e.Representation]
        check("re-opened crop has 3 elements with geometry", len(with_geom) == 3, f"{len(with_geom)}")
        a2 = analyze.run(reopened)
        wall_zmax = [
            round(a2.elements[w.GlobalId].bbox_max[2], 1)
            for w in reopened.by_type("IfcWall")
            if w.GlobalId in a2.elements
        ]
        check("surviving wall is the ground wall (Zmax<=3)", wall_zmax == [3.0], str(wall_zmax))
    finally:
        os.remove(tmp)


# ---- M4 (hardening) -------------------------------------------------------
def m4():
    print("M4  conversion hardening")
    import glob
    import hashlib
    import tempfile

    import cli

    before = hashlib.sha256(open(FIXTURE, "rb").read()).hexdigest()
    pre = set(glob.glob(os.path.join(tempfile.gettempdir(), "fixture_*.ifc")))
    pipeline.process(FIXTURE, OUT, ["Structural"], targets=("glb", "stp"), ifcconvert=IFCCONVERT)
    after = hashlib.sha256(open(FIXTURE, "rb").read()).hexdigest()
    check("input IFC sha256 unchanged (write->temp only)", before == after)
    leftover = set(glob.glob(os.path.join(tempfile.gettempdir(), "fixture_*.ifc")))
    check("no leftover temp .ifc", leftover == pre)
    rc = cli.main([FIXTURE, "--out", OUT, "--glb", "--ifcconvert", os.path.join(ROOT, "bin", "NOPE.exe")])
    check("missing IfcConvert is fatal (rc==2)", rc == 2, f"rc={rc}")
    missing = os.path.join(OUT, "_does_not_exist.ifc")
    rc = cli.main([missing, "--out", OUT, "--glb", "--ifcconvert", IFCCONVERT])
    check("unreadable file -> per-file skip (rc==1)", rc == 1, f"rc={rc}")


# ---- M5 (AR compress) -----------------------------------------------------
def m5():
    print("M5  AR compress (F5, gltfpack) on real model")
    if not os.path.exists(REAL):
        check("real model fixture present", False, REAL)
        return
    plain = pipeline.process(REAL, OUT, list(filtering.ALL_GROUPS), targets=("glb",), ifcconvert=IFCCONVERT)
    plain_bytes, plain_tris = plain.glb_bytes, glbtools.triangle_count(plain.glb)
    comp = pipeline.process(
        REAL,
        OUT,
        list(filtering.ALL_GROUPS),
        targets=("glb",),
        ifcconvert=IFCCONVERT,
        gltfpack=GLTFPACK,
        compress=True,
        simplify=0.5,
    )
    cs = comp.compress_stats
    check("compress stats produced", cs is not None)
    check("GLB smaller after gltfpack", comp.glb_bytes < plain_bytes, f"{plain_bytes}->{comp.glb_bytes}")
    check(
        "compressed GLB valid + keeps materials",
        len(glbtools.material_names(comp.glb)) > 0,
        str(glbtools.material_names(comp.glb)),
    )
    print(
        f"      info: triangles {plain_tris}->{glbtools.triangle_count(comp.glb)}, "
        f"bytes {plain_bytes}->{comp.glb_bytes} (x{cs['ratio'] if cs else '?'})"
    )


def main():
    import shutil

    shutil.rmtree(OUT, ignore_errors=True)  # avoid stale outputs
    os.makedirs(OUT, exist_ok=True)
    m1()
    m2()
    m3()
    m4()
    m5()
    p = sum(_results)
    t = len(_results)
    print(f"\n==== {p}/{t} checks passed ====")
    sys.exit(0 if p == t else 1)


if __name__ == "__main__":
    main()
