"""Alıcı hassasiyeti ve termal gürültü tabanı."""

from __future__ import annotations

import math
from typing import Optional

from lorasim.lora import sx1276_config as hw


def noise_floor_dbm(bandwidth_hz: float, noise_figure_db: float, extra_noise_db: float = 0.0) -> float:
    return hw.THERMAL_NOISE_DBM_HZ + 10 * math.log10(bandwidth_hz) + noise_figure_db + extra_noise_db


def sensitivity_dbm(sf: int, bandwidth_hz: float, noise_figure_db: float = hw.DEFAULT_NOISE_FIGURE_DB,
                    override_dbm: Optional[float] = None) -> float:
    """S = -174 + 10·log10(BW) + NF + SNR_gerekli. Kullanıcı değeri verilirse o kullanılır."""
    if override_dbm is not None:
        return override_dbm
    return noise_floor_dbm(bandwidth_hz, noise_figure_db) + hw.SNR_REQUIRED_DB[sf]
