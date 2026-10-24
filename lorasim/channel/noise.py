"""Gürültü ve güç toplama yardımcıları."""

from __future__ import annotations

import math
from typing import Iterable

from lorasim.lora.sensitivity import noise_floor_dbm  # noqa: F401  (kanal paketinden erişim için)


def dbm_sum(values_dbm: Iterable[float]) -> float:
    """dBm cinsinden güçlerin doğrusal toplamı; boş liste için -inf."""
    total = sum(10 ** (v / 10) for v in values_dbm if v != -math.inf)
    return 10 * math.log10(total) if total > 0 else -math.inf
