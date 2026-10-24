"""Paket kayıtlarından zaman serileri (grafikler ve raporlar için)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

from lorasim.metrics.collector import PacketRecord


@dataclass
class TimeSeries:
    t: np.ndarray  # pencere sonu zamanları (s)
    per: np.ndarray  # pencere içi frame hata oranı
    ber: np.ndarray
    throughput_bps: np.ndarray
    latency_s: np.ndarray  # pencere içindeki başarılı gönderimlerin ortalama gecikmesi
    success_rate: np.ndarray  # 1 - per


def auto_window_s(duration_s: float, target_bins: int = 60) -> float:
    if duration_s <= 0:
        return 1.0
    raw = duration_s / target_bins
    mag = 10 ** math.floor(math.log10(raw))
    return min((m * mag for m in (1, 2, 5, 10) if m * mag >= raw), default=raw)


def windowed(records: Iterable[PacketRecord], window_s: Optional[float] = None) -> TimeSeries:
    recs = list(records)
    if not recs:
        e = np.array([])
        return TimeSeries(e, e, e, e, e, e)
    t = np.array([r.time_s for r in recs])
    w = window_s or auto_window_s(t.max() - t.min())
    start = math.floor(t.min() / w) * w
    idx = ((t - start) // w).astype(int)
    n = idx.max() + 1
    count = np.bincount(idx, minlength=n).astype(float)
    ok = np.bincount(idx, weights=[r.success for r in recs], minlength=n)
    bit_err = np.bincount(idx, weights=[r.bit_errors for r in recs], minlength=n)
    bits = np.bincount(idx, weights=[r.bits_compared for r in recs], minlength=n)
    good_bits = np.bincount(idx, weights=[8 * r.payload_bytes if r.success and not r.duplicate else 0
                                          for r in recs], minlength=n)
    lat = np.bincount(idx, weights=[r.latency_s if r.success else 0.0 for r in recs], minlength=n)
    with np.errstate(divide="ignore", invalid="ignore"):
        per = np.where(count > 0, 1 - ok / count, np.nan)
        ber = np.where(bits > 0, bit_err / bits, np.nan)
        latency = np.where(ok > 0, lat / ok, np.nan)
    ends = start + w * (np.arange(n) + 1)
    return TimeSeries(ends, per, ber, good_bits / w, latency, 1 - per)
