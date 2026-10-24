"""Yol kaybı modelleri."""

from __future__ import annotations

import math

SPEED_OF_LIGHT = 299_792_458.0
REFERENCE_DISTANCE_M = 1.0


def free_space_path_loss_db(distance_m: float, frequency_hz: float) -> float:
    """FSPL = 20·log10(4π·d·f / c)."""
    return 20 * math.log10(4 * math.pi * distance_m * frequency_hz / SPEED_OF_LIGHT)


def log_distance_path_loss_db(distance_m: float, frequency_hz: float, exponent: float,
                              d0_m: float = REFERENCE_DISTANCE_M) -> float:
    """PL(d) = FSPL(d0) + 10·n·log10(d/d0); d < d0 için serbest uzay kullanılır."""
    if distance_m <= d0_m:
        return free_space_path_loss_db(distance_m, frequency_hz)
    return free_space_path_loss_db(d0_m, frequency_hz) + 10 * exponent * math.log10(distance_m / d0_m)
