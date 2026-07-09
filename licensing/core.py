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


# Spec §6.2: the RSA public key is HARD-CODED here, not read from a swappable file. In a release build
# this module is Cython-compiled to licensing/core.pyd (scripts/obfuscate_licensing.py), so the key lives
# in native machine code. This closes the key-substitution bypass — an attacker can no longer replace a
# loose public_key.pem on disk to self-sign licenses; forging one still requires the vendor private key.
_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAsupK+KQwz34PnODBfiII
0AWU76kfIonMU/Ca04vtno9nXESx1bdFOX7L4wIWUE/AhNrFdkOF6kqRwbcOb2bd
4rasTQTha30fViBI8nOocNgzdVEcx42svq2CJ7yhBMrMqkfTaJqWVfQtCPQ1frv5
hF8fesmyTKqCsGp1KxMgnYYf3U83OUo3oPqpc3XHFC5PgnoHblehE+BXfmRQPft4
xMg87iP4wN23ouYLEh9J2/g9+xnO49lLqN6ni8L2Njnu7iviQpRbGTnv6p8WtUNf
Mjo1Ji4AbSJGB2YwqXFUWvXufDqSH26JOTRkPHrJkTsa2oRcyapKf0he1GhvXRbN
ECh7oxKeb4BigZFb0M7hVt7GLSieo2Ri0KKLfG2X8siEXQhCKtdo+q7iimXTafQM
J+3tQ0lQK2PPmJIg+M+92n0HV722bOdxdh/qdMwO3E7+oTyXooX9QxjthWP19LEe
alw45j2UD0O8NkFqP1vvLYmDxpTtmYEfkpDceG1S/iKE+wbGrH4SVT1GYrsgIVad
yGMxklUOQTneiy5XgFf55h+eJrpBOUdJyVbxBlQoMwyS3H+U6AYn0NWQ302fEg3j
NtCrd+bNXtzHnyvGIakY6lGM04JKEqt2TOCHBRTm1RQkxUMSf78CRaXVdzxd0che
eW39iuJdUi3KBsVL3Ag0/c0CAwEAAQ==
-----END PUBLIC KEY-----
"""


def load_public_key_pem() -> bytes:
    """Return the hard-coded RSA public key PEM (§6.2 — embedded in code, not read from disk)."""
    return _PUBLIC_KEY_PEM


def canonical_payload(machine_hash_: str, expiry: str) -> bytes:
    """Deterministic signed bytes for a license (sorted keys, no whitespace); signer/verifier must match."""
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


def verify_file(path: str | None) -> LicenseResult:
    """Verify a license file on disk for THIS machine. Any problem — missing/unreadable path, invalid
    JSON, bad signature, wrong machine, expired — returns the single generic failure."""
    if not path:
        return LicenseResult(False, "Invalid license - contact vendor")
    try:
        with open(path, encoding="utf-8") as f:
            lic = json.load(f)
    except (OSError, ValueError):
        return LicenseResult(False, "Invalid license - contact vendor")
    if not isinstance(lic, dict):
        return LicenseResult(False, "Invalid license - contact vendor")
    return verify_license(lic, load_public_key_pem(), current_machine=machine_hash())


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
        # Spec §6.2 step 5: all license-validation failures show the single generic message.
        return LicenseResult(False, "Invalid license - contact vendor")
    return LicenseResult(True, "")
