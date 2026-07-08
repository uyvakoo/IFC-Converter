"""
Clock-rollback guard (spec §6.2, defect D11).

Stores a monotonic "last seen" UTC timestamp; if the system clock is ever earlier than the stored
value, the app locks. The store is abstracted so the logic is testable headless; the production store
is HKCU registry (no admin). This is anti-CASUAL-tamper only — a local admin can clear the key
(documented in D11). A missing stored value is treated as first run.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


class InMemoryStore:
    """Test/abstract store — holds the stamp in memory instead of the registry."""

    def __init__(self, value: str | None = None):
        """Start with an optional pre-seeded stored value (None = no prior stamp)."""
        self._v = value

    def get(self) -> str | None:
        """Return the stored ISO timestamp, or None if never set."""
        return self._v

    def set(self, value: str) -> None:
        """Overwrite the stored ISO timestamp."""
        self._v = value


class RegistryStore:
    """Production store: HKEY_CURRENT_USER (no admin). Windows only."""

    def __init__(self, subkey=r"Software\IFCConverter", name="last_seen_utc"):
        """Bind to the HKCU value (``subkey``\\``name``) that holds the last-seen UTC stamp."""
        self.subkey, self.name = subkey, name

    def get(self):
        """Read the stored ISO timestamp from HKCU, or None if the key/value is absent."""
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.subkey) as k:
                return winreg.QueryValueEx(k, self.name)[0]
        except OSError:
            return None

    def set(self, value: str):
        """Write the ISO timestamp to HKCU, creating the key if needed. May raise OSError."""
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.subkey) as k:
            winreg.SetValueEx(k, self.name, 0, winreg.REG_SZ, value)


_TAMPERED = "System clock tampered - license revoked"


def ntp_utc(server: str = "pool.ntp.org", timeout: float = 2.0) -> datetime | None:
    """Best-effort UTC time from an NTP server (spec §6.2). Returns None when unreachable
    (the air-gapped/offline case), so the caller falls back to the registry check."""
    try:
        import ntplib

        resp = ntplib.NTPClient().request(server, version=3, timeout=timeout)
        return datetime.fromtimestamp(resp.tx_time, tz=timezone.utc)
    except Exception:
        return None


def check_clock(
    store, now: datetime | None = None, ntp: datetime | None = None, ntp_tolerance_days: int = 1
) -> tuple[bool, str]:
    """Return (ok, reason). Locks if the system clock rolled back vs the stored stamp, or (when an NTP
    time is supplied) if it sits well behind real time; advances the stamp on success.

    Fails SAFE, never fatal: an unreadable registry or a corrupt/hand-edited stamp degrades to "first
    run" and a failed write is swallowed, so this anti-casual-tamper guard (D11) can never crash the app
    at launch."""
    now = now or datetime.now(timezone.utc)
    # NTP cross-check (optional): system clock far behind true time => rolled back.
    if ntp is not None and now < ntp - timedelta(days=ntp_tolerance_days):
        return False, _TAMPERED
    try:
        stored_raw = store.get()
    except OSError:
        stored_raw = None  # registry unreadable -> treat as first run
    stored = None
    if stored_raw:
        try:
            stored = datetime.fromisoformat(stored_raw)
        except (ValueError, TypeError):
            stored = None  # corrupt / hand-edited stamp -> treat as first run, don't crash at launch
    if stored is not None:
        if now < stored:
            return False, _TAMPERED
        if now > stored:
            _safe_set(store, now)
    else:
        _safe_set(store, now)  # first run (or unreadable/corrupt stamp)
    return True, ""


def _safe_set(store, now: datetime) -> None:
    """Persist the stamp, swallowing a registry write failure so the guard degrades, never crashes."""
    try:
        store.set(now.isoformat())
    except OSError:
        pass
