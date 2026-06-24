"""
Vendor signing tool (offline). Produces a license.key for a customer's machine hash.
    python tools/sign_license.py <machine_hash> <expiry YYYY-MM-DD> [out=license.key]
Uses _vendor/private_key.pem. Never ship this script or the private key.
"""
import json
import os
import sys

from cryptography.hazmat.primitives import serialization

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from licensing.core import sign_license  # noqa: E402  (import after sys.path bootstrap)


def main():
    if len(sys.argv) < 3:
        print("usage: python tools/sign_license.py <machine_hash> <expiry> [out]")
        raise SystemExit(2)
    machine_hash, expiry = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else "license.key"
    with open(os.path.join(ROOT, "_vendor", "private_key.pem"), "rb") as f:
        priv = serialization.load_pem_private_key(f.read(), password=None)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sign_license(priv, machine_hash, expiry), f, indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main()
