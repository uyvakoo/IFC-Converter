"""
Licensing core (F7) — machine-locked RSA license + clock-rollback guard.

Isolated package (intended PyArmor target per D2). Qt-free and unit-testable with a throwaway key
pair. The application's public key is loaded from PEM (hard-coded/bundled in production); the private
key stays with the vendor and is only used by the offline signing tool.
"""

from .clockguard import InMemoryStore, RegistryStore, check_clock, ntp_utc
from .core import (
    LicenseResult,
    canonical_payload,
    load_public_key_pem,
    machine_hash,
    sign_license,
    verify_license,
)

__all__ = [
    "LicenseResult",
    "machine_hash",
    "canonical_payload",
    "sign_license",
    "verify_license",
    "load_public_key_pem",
    "InMemoryStore",
    "RegistryStore",
    "check_clock",
    "ntp_utc",
]
