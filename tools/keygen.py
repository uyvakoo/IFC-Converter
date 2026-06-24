"""
Vendor key generation (run ONCE, offline). Writes:
  licensing/public_key.pem   -> bundled in the app (hard-coded public key, spec §6.2)
  _vendor/private_key.pem    -> KEPT BY VENDOR ONLY, never bundled/committed

Production uses 4096-bit (spec). Pass a size arg to override (tests use 2048 for speed).
    python tools/keygen.py [bits]
"""

import os
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(bits=4096):
    priv = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )

    pub_path = os.path.join(ROOT, "licensing", "public_key.pem")
    with open(pub_path, "wb") as f:
        f.write(pub_pem)
    vend_dir = os.path.join(ROOT, "_vendor")
    os.makedirs(vend_dir, exist_ok=True)
    with open(os.path.join(vend_dir, "private_key.pem"), "wb") as f:
        f.write(priv_pem)
    print(f"wrote {pub_path}")
    print(f"wrote {vend_dir}\\private_key.pem  ({bits}-bit) — keep this private, do NOT bundle")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4096)
