"""Shared conversion_report.txt writer (spec §5.2). Append-only, best-effort."""

from __future__ import annotations

import os
from datetime import datetime, timezone


def append(report_path: str, row: dict) -> None:
    """Append one `key=value | ...` line to conversion_report.txt (spec §5.2), skipping None fields."""
    fields = [
        ("timestamp", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        ("input", row.get("input")),
        ("crop", row.get("crop")),
        ("filter", ",".join(row.get("filter") or [])),
        ("entities_processed", row.get("entities_processed")),
        ("entities_removed", row.get("entities_removed")),
        ("unit_scale_to_m", row.get("unit_scale")),
        ("glb_bytes", row.get("glb_bytes")),
        ("stp_bytes", row.get("stp_bytes")),
        ("usdz_bytes", row.get("usdz_bytes")),
        ("elapsed_s", row.get("elapsed_s")),
        ("status", row.get("status")),
        ("error", row.get("error")),
    ]
    line = " | ".join(f"{k}={v}" for k, v in fields if v is not None)
    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
    with open(report_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
