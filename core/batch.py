"""
F6 (core) — sequential batch orchestration, headless.

Processes files ONE AT A TIME (parallel IFC parsing is unsafe), with per-file isolation (a bad file
becomes Error and the queue continues), cooperative cancellation (a `cancel()` predicate checked
between files), and progress/status callbacks. This is the Qt-free core that the Phase-B PySide6
QThread worker will wrap — the worker forwards `progress_cb`/`status_cb` to signals and supplies a
`cancel` backed by a UI flag (never QThread.terminate(), which would corrupt temp files).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import convert, pipeline
from .errors import FatalError


@dataclass
class FileStatus:
    path: str
    state: str = "Pending"          # Pending | Processing | Done | Error | Cancelled
    result: object = None
    error: str | None = None


def run_batch(files, *, out_dir, groups, storey_name=None, xyz=None, targets=("glb",),
              ifcconvert=None, gltfpack=None, compress=False, simplify=0.5,
              progress_cb=None, status_cb=None, cancel=None):
    """Run the pipeline over `files` sequentially. Returns the list of FileStatus.

    Pre-flights bundled binaries once (FatalError aborts the whole batch, §9.3).
    """
    convert.ensure_available(ifcconvert)
    if compress:
        convert.ensure_available(gltfpack)

    statuses = [FileStatus(f) for f in files]
    for i, fs in enumerate(statuses):
        if cancel and cancel():
            fs.state = "Cancelled"
            if status_cb:
                status_cb(i, fs)
            # mark the rest cancelled too
            for fs2 in statuses[i + 1:]:
                fs2.state = "Cancelled"
            break
        fs.state = "Processing"
        if status_cb:
            status_cb(i, fs)
        try:
            fs.result = pipeline.process(
                fs.path, out_dir, groups, storey_name=storey_name, xyz=xyz, targets=targets,
                ifcconvert=ifcconvert, gltfpack=gltfpack, compress=compress, simplify=simplify,
                progress_cb=(lambda p, idx=i: progress_cb(idx, p)) if progress_cb else None)
            fs.state = "Done"
        except FatalError:
            raise  # abort whole batch
        except Exception as e:  # per-file isolation (§9.1)
            fs.state = "Error"
            fs.error = str(e)
        if status_cb:
            status_cb(i, fs)
    return statuses
