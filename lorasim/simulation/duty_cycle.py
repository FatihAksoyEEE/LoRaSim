"""Duty-cycle takibi (LoRaWAN/ETSI "off-time" kuralı).

Süresi Ta olan bir gönderimden sonra cihaz Ta·(1/dc - 1) boyunca susmalıdır;
yani bir sonraki gönderim en erken başlangıç + Ta/dc anında yapılabilir.
"""

from __future__ import annotations

from typing import Optional


class DutyCycleTracker:
    def __init__(self, limit: Optional[float]):
        self.limit = limit
        self.total_airtime_s = 0.0
        self.violations = 0
        self._blocked_until = 0.0

    def would_violate(self, now: float) -> bool:
        return self.limit is not None and now < self._blocked_until - 1e-12

    def next_allowed(self, now: float) -> float:
        return max(now, self._blocked_until) if self.limit is not None else now

    def register(self, start_s: float, airtime_s: float, violation: bool = False) -> None:
        self.total_airtime_s += airtime_s
        self.violations += int(violation)
        if self.limit is not None:
            self._blocked_until = start_s + airtime_s / self.limit
