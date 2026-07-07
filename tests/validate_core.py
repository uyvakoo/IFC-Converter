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
from core import analyze, cropping, filtering, paths, pipeline, postprocess, styling


def _glb_extensions_required(path):
    import json
    import struct

    data = open(path, "rb").read()
    clen = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20 : 20 + clen]).get("extensionsRequired", [])


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
        compress_mode="meshopt",  # this test is the gltfpack/meshopt path (default is now draco)
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


def m5_draco():
    print("M5d AR compress — Draco (F5, gltf-pipeline -> KHR_draco_mesh_compression)")
    import shutil as _sh

    plain = pipeline.process(REAL, OUT, list(filtering.ALL_GROUPS), targets=("glb",), ifcconvert=IFCCONVERT)
    plain_tris = glbtools.triangle_count(plain.glb)
    # Wiring/error path is CI-safe (no Node needed): draco mode must fail clearly without its tools.
    err = ""
    try:
        postprocess.compress_glb(GLTFPACK, plain.glb, mode="draco", node=None, gltf_pipeline=None)
    except RuntimeError as e:
        err = str(e)
    check("draco without Node -> clear error", "Node" in err, err)

    # Real Draco run when a Node + gltf-pipeline is available (bundled by default, or system Node).
    node = paths.node() if os.path.isfile(paths.node()) else _sh.which("node")
    gp = paths.gltf_pipeline()
    if not (node and os.path.isfile(gp)):
        print("      skip real Draco run (node/gltf-pipeline not fetched — see fetch_binaries --no-draco)")
        return
    comp = pipeline.process(
        REAL,
        OUT,
        list(filtering.ALL_GROUPS),
        targets=("glb",),
        ifcconvert=IFCCONVERT,
        gltfpack=GLTFPACK,
        compress=True,
        compress_mode="draco",
        node=node,
        gltf_pipeline=gp,
        simplify=0.5,
    )
    cs = comp.compress_stats
    check("draco compress stats (mode=draco)", cs and cs.get("mode") == "draco", str(cs))
    exts = _glb_extensions_required(comp.glb)
    check("GLB declares KHR_draco_mesh_compression", "KHR_draco_mesh_compression" in exts, str(exts))
    check("draco keeps materials/colors", len(glbtools.material_names(comp.glb)) > 0)
    check("draco shrinks the GLB", cs["bytes_after"] < cs["bytes_before"], str(cs))
    # real_building is hard-edged box geometry, which gltfpack's border-aware simplifier correctly does
    # NOT collapse — triangles are preserved here (a wall must stay a wall). The low-poly/-si decimation
    # stage is proven on a genuinely decimatable mesh in m5_lowpoly().
    draco_tris = glbtools.triangle_count(comp.glb)
    check(
        "draco preserves box-geometry triangles (no corruption)",
        draco_tris == plain_tris,
        f"{plain_tris}->{draco_tris}",
    )
    print(
        f"      info: tris {plain_tris}->{draco_tris}, "
        f"bytes {cs['bytes_before']}->{cs['bytes_after']} (x{cs['ratio']})"
    )


def m5_lowpoly():
    print("M5l AR low-poly — -si decimation (spec §1 'low-poly'/--optimize) on a decimatable mesh")
    import tempfile

    fd, dense = tempfile.mkstemp(suffix=".glb")
    os.close(fd)
    try:
        n0 = glbtools.make_dense_glb(dense, n=40)  # 3200-triangle smooth curved surface
        # meshopt path (CI-safe, no Node): -si must roughly halve the triangles at simplify=0.5.
        import shutil as _sh

        mo = dense + ".mo.glb"
        _sh.copy(dense, mo)
        postprocess.compress_glb(GLTFPACK, mo, mode="meshopt", simplify=0.5)
        mo_tris = glbtools.triangle_count(mo)
        check("meshopt -si decimates ~50% (low-poly)", mo_tris <= n0 * 0.65, f"{n0}->{mo_tris}")
        check("decimated mesh keeps its material", len(glbtools.material_names(mo)) > 0)
        # draco path (needs Node): decimate THEN Draco — must be both low-poly and KHR_draco.
        node = paths.node() if os.path.isfile(paths.node()) else __import__("shutil").which("node")
        gp = paths.gltf_pipeline()
        if node and os.path.isfile(gp):
            dr = dense + ".dr.glb"
            _sh.copy(dense, dr)
            postprocess.compress_glb(GLTFPACK, dr, mode="draco", simplify=0.5, node=node, gltf_pipeline=gp)
            dr_tris = glbtools.triangle_count(dr)
            exts = _glb_extensions_required(dr)
            check("draco is low-poly (triangles reduced)", dr_tris <= n0 * 0.65, f"{n0}->{dr_tris}")
            check("draco low-poly output still declares KHR_draco_mesh_compression",
                  "KHR_draco_mesh_compression" in exts, str(exts))
            print(f"      info: dense {n0} tris -> meshopt {mo_tris}, draco {dr_tris}")
        else:
            print(f"      info: dense {n0} tris -> meshopt {mo_tris} (skip draco leg — no Node)")
    finally:
        for p in (dense, dense + ".mo.glb", dense + ".dr.glb"):
            if os.path.exists(p):
                os.remove(p)


def schema_compat():
    print("SC  schema compatibility — styling on IFC2X3 (regression: no Transparency attr)")
    # IFC2X3's IfcSurfaceStyleShading has no Transparency (added in IFC4). Real-world IFC2x3 models
    # (e.g. schependomlaan) crashed here before the schema-aware fix.
    m23 = ifcopenshell.file(schema="IFC2X3")
    ok23 = True
    try:
        s = styling.build_styles(m23)
    except Exception as e:
        ok23 = False
        s = str(e)
    check("build_styles works on IFC2X3 (4 styles, no crash)", ok23 and len(s) == 4, str(s)[:80])
    m4 = ifcopenshell.file(schema="IFC4")
    check("build_styles still works on IFC4 (4 styles)", len(styling.build_styles(m4)) == 4)


def crop_cascade_safe():
    print("CR  crop apply() survives a cascade-removed element (real-model regression)")
    import types

    import ifcopenshell.api.root

    # Real models (e.g. schependomlaan) crashed here: removing a product cascaded a dependent, then
    # by_guid for the already-gone guid raised "Instance with GlobalId not found".
    m = ifcopenshell.file(schema="IFC4")
    w1 = ifcopenshell.api.root.create_entity(m, ifc_class="IfcWall")
    w2 = ifcopenshell.api.root.create_entity(m, ifc_class="IfcWall")
    fake = types.SimpleNamespace(elements={w1.GlobalId: None, w2.GlobalId: None})
    ifcopenshell.api.root.remove_product(m, product=w1)  # simulate a prior cascade removal
    ok, n = True, None
    try:
        n = cropping.apply(m, set(), fake)  # must not raise on the now-missing w1
    except Exception as e:
        ok, n = False, str(e)
    check("apply() skips an already-removed element (no crash, removes the rest)", ok and n == 1, str(n))

    # filter completeness: a non-group element (e.g. IfcBuildingElementProxy) must be dropped even if
    # the analyze pass never captured it (real models leak such geometry into the GLB otherwise).
    m2 = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.root.create_entity(m2, ifc_class="IfcWall")  # Structural -> kept
    ifcopenshell.api.root.create_entity(m2, ifc_class="IfcBuildingElementProxy")  # no group -> dropped
    nrm = cropping.remove_unselected(m2, ["Structural"])
    check(
        "remove_unselected drops non-group proxy, keeps selected class",
        nrm == 1 and len(m2.by_type("IfcWall")) == 1 and len(m2.by_type("IfcBuildingElementProxy")) == 0,
        f"removed={nrm}",
    )


def usdz_export():
    """F6: GLB -> USDZ (iOS-native AR). Spec-compliant .usdz, geometry + our 4 colours preserved."""
    import glob
    import json
    import re
    import struct
    import zipfile

    r = pipeline.process(
        FIXTURE,
        OUT,
        ["Structural", "MEP", "Architectural", "Cables"],
        targets=("glb", "usdz"),
        ifcconvert=IFCCONVERT,
    )
    check("usdz produced", bool(r.usdz) and os.path.isfile(r.usdz), str(r.usdz))
    check("usdz_stats has geometry", bool(r.usdz_stats) and r.usdz_stats["vertices"] > 0, str(r.usdz_stats))

    zf = zipfile.ZipFile(r.usdz)
    names = zf.namelist()
    check(
        "usdz is a valid *stored* zip",
        zf.testzip() is None and zf.infolist()[0].compress_type == zipfile.ZIP_STORED,
    )
    check("usdz first entry is the .usda layer", bool(names) and names[0].endswith(".usda"), str(names))

    raw = open(r.usdz, "rb").read()
    nlen, elen = struct.unpack_from("<HH", raw, 26)
    data_off = 30 + nlen + elen
    check("usdz first-file data is 64-byte aligned (Apple USDZ)", data_off % 64 == 0, f"offset={data_off}")

    usda = zf.read(names[0]).decode("utf-8")
    check("usda header + Y-up", usda.startswith("#usda 1.0") and 'upAxis = "Y"' in usda)
    cols = set(re.findall(r"displayColor = \[\(([^)]+)\)\]", usda))
    want = {"0.8, 0.8, 0.8", "0.2, 0.4, 0.8", "0.6, 0.3, 0.1", "0.9, 0.2, 0.2"}
    check("usdz preserves all 4 AR group colours", want <= cols, str(cols))

    # independent geometry cross-check: sum POSITION accessor counts straight from the GLB JSON
    gdata = open(r.glb, "rb").read()
    clen = struct.unpack_from("<I", gdata, 12)[0]
    gj = json.loads(gdata[20 : 20 + clen])
    vtot = sum(
        gj["accessors"][prim["attributes"]["POSITION"]]["count"]
        for mesh in gj.get("meshes", [])
        for prim in mesh.get("primitives", [])
    )
    check(
        "usdz vertex count matches GLB POSITION accessors",
        r.usdz_stats["vertices"] == vtot,
        f"{r.usdz_stats['vertices']} vs {vtot}",
    )

    # usdz-only target: a throwaway GLB is used then cleaned — none must be left behind
    tmp = os.path.join(OUT, "usdzonly")
    os.makedirs(tmp, exist_ok=True)
    r2 = pipeline.process(FIXTURE, tmp, ["Structural", "MEP"], targets=("usdz",), ifcconvert=IFCCONVERT)
    check(
        "usdz-only leaves no stray GLB",
        not glob.glob(os.path.join(tmp, "*.glb")) and os.path.isfile(r2.usdz),
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
    m5_draco()
    m5_lowpoly()
    schema_compat()
    crop_cascade_safe()
    usdz_export()
    p = sum(_results)
    t = len(_results)
    print(f"\n==== {p}/{t} checks passed ====")
    sys.exit(0 if p == t else 1)


if __name__ == "__main__":
    main()
