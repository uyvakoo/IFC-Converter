# 09 — Licensing & Security

> ✔ **APPROVED (2026-06-23):** drop PyInstaller `--key`; obfuscate licensing/hashing with **PyArmor**;
> keep `--strip`/`--noupx` (D2). See [02 — decision log](02-defects-and-remedies.md#decision-log).

## Purpose
Gate the app behind a vendor-signed, machine-locked license with expiry and basic clock-rollback
protection, and harden the sensitive modules — all offline.

## Inputs / Outputs
- **In:** the current machine; a `license.key` JSON the user loads.
- **Out:** unlock/deny decision; a stored activation timestamp (registry).

## Machine hash (spec §6.1)
- `machineid.id()` derives a stable per-machine hash (Windows UUID / motherboard serials) **without
  admin**. Show it in a copyable text box on the License window for the user to email the vendor.

## RSA license validation (spec §6.2)
- License file = JSON `{ machine_hash, expiry, signature }`.
- A **4096-bit RSA public key is hard-coded** in the app (PEM). The private key stays with the vendor.
- **Validation order:** (1) read `license.key`; (2) verify the RSA signature over a **canonical
  serialization** of the signed fields using the public key + PKCS1v15 + SHA-256; (3) check
  `machine_hash` == current machine; (4) check `expiry` not passed; (5) unlock, else show
  "Invalid license - contact vendor."
- **Crypto library:** `cryptography` **hazmat** only — the spec forbids pycryptodome (licensing
  concerns). Use `cryptography.hazmat.primitives.asymmetric.padding.PKCS1v15` + `hashes.SHA256`.

**Critical detail:** sign and verify the **exact same canonical bytes** (fixed field order, encoding,
no whitespace ambiguity). Mismatched serialization between signer and verifier is the usual cause of
"valid license fails to validate."

## Clock-rollback protection (spec §6.2) — D11
- On first successful activation, store the current UTC timestamp in **HKCU registry** (no admin).
- On each startup: if `now < stored` → lock with "System clock tampered - license revoked"; else set
  `stored = max(stored, now)`.
- Optionally cross-check `pool.ntp.org` via `ntplib`; air-gapped → NTP usually fails, so the registry
  check is the real guard.
- **Threat model (be honest):** this stops casual clock-winding only. A user with local admin can edit
  or clear the HKCU key. Document it as anti-casual-tamper, not strong security (D11). Treat a missing
  key as "first run."

## Anti-debug / obfuscation (spec §6.3) — D2
- **Do not** use PyInstaller `--key` (removed in 6.0; D2). Obfuscate `licensing/*` and the hashing code
  with **PyArmor**.
- `--strip` debug symbols; `--noupx` (UPX trips AV false-positives).
- No `print()`/tracebacks that leak licensing logic to users.
- **Reality:** obfuscation raises effort, not impossibility. Code-signing the `.exe` (see
  [10](10-packaging-distribution.md)) does more for trust/AV than obfuscation does for secrecy.

## Key APIs (named, no code)
- `machineid.id()`.
- `cryptography.hazmat.primitives.serialization.load_pem_public_key`,
  `…asymmetric.padding.PKCS1v15`, `…hashes.SHA256`, `public_key.verify(...)`.
- Windows registry under HKCU (via `winreg`) for the activation timestamp.
- `ntplib.NTPClient` (optional, best-effort).

## Defects & risks
- **D2** (High) — `--key` contradiction; resolve with PyArmor.
- **D11** (Info) — clock guard is deterrence; document honestly.
- Canonical-serialization mismatch → false rejects (most common licensing bug).
- Hard-coded public key must be the counterpart of the vendor's private key; protect the private key
  off the build machine.
- Time zone bugs: store/compare **UTC** consistently.

## Proposed remedies
- Isolate all of this in a `licensing/` package with a tiny, well-tested public surface
  (`activate(path) -> Result`, `check_clock() -> Result`), so it can be PyArmor-obfuscated as a unit
  and unit-tested with a throwaway test key pair.
- Ship a vendor-side signing script (kept private) that emits `license.key` from {machine_hash, expiry}.

## Verification (E2E)
- Matrix test with a **test** key pair: valid → unlock; wrong machine → deny; expired → deny; tampered
  signature → deny; rolled-back clock → lock; missing registry key → treated as first run.
- Confirm the canonical bytes signed by the vendor script verify in the app (round-trip).
- Confirm no licensing strings/logic are visible in plain text in the built artifact (post-PyArmor).
