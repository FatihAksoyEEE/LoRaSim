"""Küçük ölçekli sönümleme ve gölgeleme örnekleyicileri (dB cinsinden güç kazancı)."""

from __future__ import annotations

import math

import numpy as np


def rayleigh_gain_db(rng: np.random.Generator) -> float:
    """|h|², ortalaması 1 olan üstel dağılım."""
    return 10 * math.log10(max(rng.exponential(1.0), 1e-12))


def rician_gain_db(rng: np.random.Generator, k_db: float) -> float:
    """Ortalama gücü 1 olan Rician kanal: K = LOS gücü / saçılan güç."""
    k = 10 ** (k_db / 10)
    los = math.sqrt(k / (k + 1))
    sigma = math.sqrt(1 / (2 * (k + 1)))
    h = complex(los + sigma * rng.standard_normal(), sigma * rng.standard_normal())
    return 10 * math.log10(max(abs(h) ** 2, 1e-12))


def shadowing_db(rng: np.random.Generator, sigma_db: float) -> float:
    """Log-normal gölgeleme: ek kayıp (pozitif = daha fazla kayıp)."""
    return float(rng.normal(0.0, sigma_db)) if sigma_db > 0 else 0.0
