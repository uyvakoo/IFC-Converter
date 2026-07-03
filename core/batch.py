"""
F6 (core) — sequential batch orchestration, headless.

Processes files ONE AT A TIME (parallel IFC parsing is unsafe), with per-file isolation (a bad file
becomes Error and the queue continues), cooperative cancellation (a `cancel()` predicate checked
between files), and progress/status callbacks. This is the Qt-free core that the Phase-B PySide6
QThread worker will wrap — the worker forwards `progress_cb`/`status_cb` to signals and supplies a
`cancel` backed by a UI flag (never QThread.terminate(), which would corrupt temp files).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import convert, pipeline, report
from .errors import FatalError


@dataclass
class FileStatus:
    path: str
    state: str = "Pending"  # Pending | Processing | Done | Error | Cancelled
    result: object = None
    error: str | None = None


def run_batch(
    files,
    *,
    out_dir,
    groups,
    storey_name=None,
    xyz=None,
    targets=("glb",),
    ifcconvert=None,
    gltfpack=None,
    compress=False,
    compress_mode="meshopt",
    node=None,
    gltf_pipeline=None,
    simplify=0.5,
    progress_cb=None,
    status_cb=None,
    cancel=None,
):
    """Run the pipeline over `files` sequentially. Returns the list of FileStatus.

    Pre-flights bundled binaries once (FatalError aborts the whole batch, §9.3).
    """
    convert.ensure_available(ifcconvert)
    if compress:
        if compress_mode == "draco":
            convert.ensure_available(node, gltf_pipeline)
        else:
            convert.ensure_available(gltfpack)

    report_path = os.path.join(out_dir, "conversion_report.txt")
    statuses = [FileStatus(f) for f in files]
    for i, fs in enumerate(statuses):
        if cancel and cancel():
            fs.state = "Cancelled"
            if status_cb:
                status_cb(i, fs)
            # mark the rest cancelled too
            for fs2 in statuses[i + 1 :]:
                fs2.state = "Cancelled"
            break
        fs.state = "Processing"
        if status_cb:
            status_cb(i, fs)
        try:
            fs.result = pipeline.process(
                fs.path,
                out_dir,
                groups,
                storey_name=storey_name,
                xyz=xyz,
                targets=targets,
                ifcconvert=ifcconvert,
                gltfpack=gltfpack,
                compress=compress,
                compress_mode=compress_mode,
                node=node,
                gltf_pipeline=gltf_pipeline,
                simplify=simplify,
                progress_cb=(lambda p, idx=i: progress_cb(idx, p)) if progress_cb else None,
            )
            fs.state = "Done"
            r = fs.result
            report.append(
                report_path,
                {
                    "input": fs.path,
                    "crop": r.crop_desc,
                    "filter": groups,
                    "entities_processed": r.kept,
                    "entities_removed": r.removed,
                    "unit_scale": r.unit_scale,
                    "glb_bytes": r.glb_bytes,
                    "stp_bytes": r.stp_bytes,
                    "usdz_bytes": r.usdz_bytes,
                    "elapsed_s": r.elapsed_s,
                    "status": "Done",
                },
            )
        except FatalError:
            raise  # abort whole batch
        except Exception as e:  # per-file isolation (§9.1)
            fs.state = "Error"
            fs.error = str(e)
            report.append(
                report_path, {"input": fs.path, "filter": groups, "status": "Error", "error": str(e)}
            )
        if status_cb:
            status_cb(i, fs)
    return statuses
