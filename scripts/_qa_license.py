"""
Mint a machine-locked license for **local QA** that drives the hardened `--cli` gate (PR #14).

Since `IFC_Converter.exe --cli …` now refuses to run without a valid `--license` key, the QA tools that
drive it (`acceptance_report.py`, `cli_exit_codes.py`, `draco_check.py`) must sign one for the current
machine and pass it. This signs with the vendor key in `_vendor/private_key.pem`.

Not shipped (lives under scripts/, alongside the other dev tooling). Never bundle this or the private key.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

from cryptography.hazmat.primitives import serialization

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from licensing.core import machine_hash, sign_license  # noqa: E402  (after sys.path bootstrap)

_PRIV = os.path.join(ROOT, "_vendor", "private_key.pem")


def available() -> bool:
    """True if the vendor private key is present (QA can sign a license)."""
    return os.path.isfile(_PRIV)


def mint(expiry: str = "2099-12-31", out: str | None = None) -> str:
    """Sign a license for THIS machine and return its path (a temp .key by default).

    `expiry` is far-future so the QA key never lapses mid-run. Raises SystemExit with a clear message
    if the vendor key is missing — QA cannot exercise the hardened `--cli` gate without it.
    """
    if not available():
        raise SystemExit(
            f"vendor private key not found: {_PRIV}\n"
            "QA drives the licensed `--cli` gate (PR #14) and needs it to sign a `--license` key."
        )
    with open(_PRIV, "rb") as f:
        priv = serialization.load_pem_private_key(f.read(), password=None)
    key = sign_license(priv, machine_hash(), expiry)
    if out is None:
        fd, out = tempfile.mkstemp(suffix=".key", prefix="qa_license_")
        os.close(fd)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(key, f)
    return out


if __name__ == "__main__":  # `python scripts/_qa_license.py [out]` — handy for manual runs
    path = mint(out=sys.argv[1] if len(sys.argv) > 1 else None)
    print(path)
