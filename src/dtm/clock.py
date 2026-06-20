from __future__ import annotations

from datetime import datetime, timedelta, timezone


class DeterministicClock:
    def __init__(self, start: str = "2026-01-01T00:00:00Z", step_ms: int = 250):
        self.current = datetime.fromisoformat(start.replace("Z", "+00:00"))
        self.step = timedelta(milliseconds=step_ms)

    def now(self) -> str:
        value = self.current.astimezone(timezone.utc).isoformat(timespec="milliseconds")
        self.current += self.step
        return value.replace("+00:00", "Z")

