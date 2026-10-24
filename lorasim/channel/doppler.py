"""Doppler kayması ve zaman ilintisi."""

from __future__ import annotations

import numpy as np
from scipy.special import j0

from lorasim.channel.path_loss import SPEED_OF_LIGHT


def doppler_shift_hz(pos_a, vel_a, pos_b, vel_b, frequency_hz: float) -> float:
    """İki cihaz birbirine yaklaşırken pozitif olan Doppler kayması (iki yönde de aynıdır)."""
    d = np.asarray(pos_b, dtype=float) - np.asarray(pos_a, dtype=float)
    dist = float(np.linalg.norm(d))
    if dist == 0:
        return 0.0
    closing = float(np.dot(np.asarray(vel_a) - np.asarray(vel_b), d / dist))
    return closing / SPEED_OF_LIGHT * frequency_hz


def max_doppler_hz(speed_mps: float, frequency_hz: float) -> float:
    return speed_mps / SPEED_OF_LIGHT * frequency_hz


def jakes_correlation(max_doppler: float, dt_s: float) -> float:
    """Clarke/Jakes modeli: R(Δt) = J0(2π·fD·Δt)."""
    return float(j0(2 * np.pi * max_doppler * dt_s))
