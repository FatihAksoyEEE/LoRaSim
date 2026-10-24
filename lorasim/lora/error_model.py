"""LoRa sembol hata olasılığı (SER) modeli.

LoRa demodülasyonu (dechirp + FFT + en büyük bin seçimi) M = 2^SF elemanlı
evreuyumsuz (non-coherent) ortogonal modülasyona eşdeğerdir. AWGN altında,
gürültü varyansı 1'e normalize edildiğinde:

    Es/N0 = SNR · M                      (SNR, BW üzerinden ölçülür)
    X     = sinyal bin enerjisi,         2X ~ χ'²(2, 2·Es/N0)
    Y     = M-1 gürültü bininin en büyüğü, F_Y(y) = (1 - e^{-y})^{M-1}
    SER   = P(Y > X) = ∫ f_Y(y) · P(X < y) dy

f_Y her SNR için ln(M) civarında yoğunlaştığından integral sabit bir ızgarada
tüm SNR değerleri için birlikte hesaplanır (Monte Carlo ile doğrulandı,
bkz. tests/test_error_model.py). Sonuçlar log(SER) üzerinden ara değerlenir.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy import integrate, stats

SNR_GRID_DB = np.arange(-35.0, 10.0 + 1e-9, 0.25)
_SER_FLOOR = 1e-300


def symbol_error_rate_exact(sf: int, snr_db: np.ndarray | float) -> np.ndarray:
    m = 2 ** sf
    y = np.linspace(0.0, math.log(m) + 60.0, 8001)[1:]
    pdf_max = np.exp(math.log(m - 1) - y + (m - 2) * np.log1p(-np.exp(-y)))
    es_n0 = 10 ** (np.atleast_1d(snr_db) / 10) * m
    p_signal_below = stats.ncx2.cdf(2 * y[None, :], 2, 2 * es_n0[:, None])
    return np.clip(integrate.trapezoid(pdf_max[None, :] * p_signal_below, y, axis=1), 0.0, 1.0)


@lru_cache(maxsize=None)
def _log_ser_table(sf: int) -> np.ndarray:
    return np.log(np.maximum(symbol_error_rate_exact(sf, SNR_GRID_DB), _SER_FLOOR))


def symbol_error_rate(sf: int, snr_db: float) -> float:
    if math.isinf(snr_db) and snr_db > 0:
        return 0.0
    snr = min(max(snr_db, SNR_GRID_DB[0]), SNR_GRID_DB[-1])
    ser = float(np.exp(np.interp(snr, SNR_GRID_DB, _log_ser_table(sf))))
    return 0.0 if ser <= _SER_FLOOR * 10 else ser


def bit_error_rate_uncoded(sf: int, snr_db: float) -> float:
    """Ortogonal M'li modülasyonda BER = SER · (M/2)/(M-1)."""
    m = 2 ** sf
    return symbol_error_rate(sf, snr_db) * (m / 2) / (m - 1)
