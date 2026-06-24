"""
Clock-rollback guard (spec §6.2, defect D11).

Stores a monotonic "last seen" UTC timestamp; if the system clock is ever earlier than the stored
value, the app locks. The store is abstracted so the logic is testable headless; the production store
is HKCU registry (no admin). This is anti-CASUAL-tamper only — a local admin can clear the key
(documented in D11). A missing stored value is treated as first run.
"""
from __future__ import annotations

from datetime import datetime, timezone


class InMemoryStore:
    """Test/abstract store."""
    def __init__(self, value: str | None = None):
        self._v = value

    def get(self) -> str | None:
        return self._v

    def set(self, value: str) -> None:
        self._v = value


class RegistryStore:
    """Production store: HKEY_CURRENT_USER (no admin). Windows only."""
    def __init__(self, subkey=r"Software\\IFCConverter", name="last_seen_utc"):
        self.subkey, self.name = subkey, name

    def get(self):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.subkey) as k:
                return winreg.QueryValueEx(k, self.name)[0]
        except OSError:
            return None

    def set(self, value: str):
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.subkey) as k:
            winreg.SetValueEx(k, self.name, 0, winreg.REG_SZ, value)


def check_clock(store, now: datetime | None = None) -> tuple[bool, str]:
    """Return (ok, reason). Locks if now < stored. Advances stored to max(stored, now)."""
    now = now or datetime.now(timezone.utc)
    stored_raw = store.get()
    if stored_raw:
        stored = datetime.fromisoformat(stored_raw)
        if now < stored:
            return False, "System clock tampered - license revoked"
        if now > stored:
            store.set(now.isoformat())
    else:
        store.set(now.isoformat())  # first run
    return True, ""
