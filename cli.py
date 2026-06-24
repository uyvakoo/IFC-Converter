"""
Headless CLI harness for the core pipeline (features 1-5). No Qt, no licensing.

Examples:
  python cli.py tests/fixtures/fixture.ifc --out out --classes Structural,MEP --storey Ground --glb
  python cli.py a.ifc b.ifc --out out --classes Structural --xyz 0,10,0,10,0,3 --glb --stp
"""

from __future__ import annotations

import argparse
import os
import sys

from core import convert, filtering, paths, pipeline, report
from core.errors import FatalError

# _MEIPASS-aware so this also works when invoked from the frozen bundle (main.py --cli ...).
DEFAULT_IFCCONVERT = paths.ifcconvert()
DEFAULT_GLTFPACK = paths.gltfpack()


def _output_writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def main(argv=None):
    p = argparse.ArgumentParser(description="IFC -> filtered/cropped/colored GLB/STP (core pipeline)")
    p.add_argument("inputs", nargs="+", help="input .ifc file(s)")
    p.add_argument("--out", default="out", help="output folder")
    p.add_argument(
        "--classes",
        default=",".join(filtering.ALL_GROUPS),
        help="comma list of groups: " + ",".join(filtering.ALL_GROUPS),
    )
    p.add_argument("--storey", default=None, help="storey name to crop to (Z bounds)")
    p.add_argument("--xyz", default=None, help="manual crop box xmin,xmax,ymin,ymax,zmin,zmax")
    p.add_argument("--glb", action="store_true", help="emit GLB")
    p.add_argument("--stp", action="store_true", help="emit STP")
    p.add_argument("--compress", action="store_true", help="gltfpack decimate+compress the GLB (F5)")
    p.add_argument("--simplify", type=float, default=0.5, help="gltfpack triangle ratio 0..1")
    p.add_argument("--ifcconvert", default=DEFAULT_IFCCONVERT)
    p.add_argument("--gltfpack", default=DEFAULT_GLTFPACK)
    args = p.parse_args(argv)

    groups = [g.strip() for g in args.classes.split(",") if g.strip()]
    xyz = [float(v) for v in args.xyz.split(",")] if args.xyz else None
    targets = tuple(t for t in ("glb", "stp") if getattr(args, t))
    if not targets:
        targets = ("glb",)

    # Pre-flight (fatal aborts the whole run, spec §9.2/§9.3)
    try:
        convert.ensure_available(args.ifcconvert)
        if args.compress:
            convert.ensure_available(args.gltfpack)
    except FatalError as e:
        print(f"[FATAL] {e}")
        return 2
    if not _output_writable(args.out):
        print(f"[FATAL] output folder not writable: {args.out}")
        return 2

    report_path = os.path.join(args.out, "conversion_report.txt")
    rc = 0
    for path in args.inputs:
        try:
            r = pipeline.process(
                path,
                args.out,
                groups,
                storey_name=args.storey,
                xyz=xyz,
                targets=targets,
                ifcconvert=args.ifcconvert,
                gltfpack=args.gltfpack,
                compress=args.compress,
                simplify=args.simplify,
                progress_cb=lambda pct: None,
            )
            cs = r.compress_stats
            print(
                f"[OK] {os.path.basename(path)} schema={r.schema} crop={r.crop_desc} "
                f"kept={r.kept} removed={r.removed} styled_items={r.style_stats.get('items')} "
                f"glb={r.glb_bytes} stp={r.stp_bytes}"
                + (f" compress={cs['bytes_before']}->{cs['bytes_after']} (x{cs['ratio']})" if cs else "")
                + f" {r.elapsed_s}s"
            )
            report.append(
                report_path,
                {
                    "input": path,
                    "crop": r.crop_desc,
                    "filter": groups,
                    "entities_processed": r.kept,
                    "entities_removed": r.removed,
                    "unit_scale": r.unit_scale,
                    "glb_bytes": r.glb_bytes,
                    "stp_bytes": r.stp_bytes,
                    "elapsed_s": r.elapsed_s,
                    "status": "Done",
                },
            )
        except Exception as e:  # per-file isolation (spec §9.1)
            rc = 1
            print(f"[ERROR] {os.path.basename(path)}: {e}")
            report.append(report_path, {"input": path, "filter": groups, "status": "Error", "error": str(e)})
    return rc


if __name__ == "__main__":
    sys.exit(main())
