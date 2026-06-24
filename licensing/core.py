"""
RSA license validation (spec §6.1/§6.2).

License = JSON {machine_hash, expiry (YYYY-MM-DD), signature (base64)}. The signature is over a
CANONICAL serialization of {machine_hash, expiry} (sorted keys, no whitespace) — signer and verifier
must produce identical bytes or verification silently fails. PKCS1v15 + SHA-256, `cryptography`
hazmat only (pycryptodome forbidden by spec §10).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date

import machineid
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


@dataclass
class LicenseResult:
    ok: bool
    reason: str = ""


def machine_hash() -> str:
    """Stable per-machine id (Windows UUID / motherboard serial), no admin required."""
    return machineid.id()


def load_public_key_pem() -> bytes:
    """Load the bundled public key PEM (resolved via _MEIPASS in a frozen build)."""
    from core import paths

    with open(paths.public_key(), "rb") as f:
        return f.read()


def canonical_payload(machine_hash_: str, expiry: str) -> bytes:
    return json.dumps(
        {"machine_hash": machine_hash_, "expiry": expiry}, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sign_license(private_key, machine_hash_: str, expiry: str) -> dict:
    """VENDOR/test side: produce a license dict signed with the RSA private key."""
    sig = private_key.sign(canonical_payload(machine_hash_, expiry), padding.PKCS1v15(), hashes.SHA256())
    return {
        "machine_hash": machine_hash_,
        "expiry": expiry,
        "signature": base64.b64encode(sig).decode("ascii"),
    }


def verify_license(
    license: dict, public_key_pem: bytes, *, current_machine: str | None = None, today: date | None = None
) -> LicenseResult:
    """APP side: verify signature, machine binding, and expiry. Returns LicenseResult."""
    current_machine = current_machine or machine_hash()
    today = today or date.today()
    try:
        pub = serialization.load_pem_public_key(public_key_pem)
        sig = base64.b64decode(license["signature"])
        payload = canonical_payload(license["machine_hash"], license["expiry"])
        pub.verify(sig, payload, padding.PKCS1v15(), hashes.SHA256())
    except (KeyError, ValueError, InvalidSignature):
        return LicenseResult(False, "Invalid license - contact vendor")
    if license["machine_hash"] != current_machine:
        return LicenseResult(False, "Invalid license - contact vendor")  # wrong machine
    try:
        exp = date.fromisoformat(license["expiry"])
    except ValueError:
        return LicenseResult(False, "Invalid license - contact vendor")
    if today > exp:
        return LicenseResult(False, "License expired - contact vendor")
    return LicenseResult(True, "")
