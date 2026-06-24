"""Error taxonomy for the pipeline (spec §9)."""


class FatalError(Exception):
    """Abort the entire run (e.g. bundled IfcConvert/gltfpack missing, §9.3)."""


class FileError(Exception):
    """Per-file failure: log, skip this file, continue the queue (§9.1)."""
