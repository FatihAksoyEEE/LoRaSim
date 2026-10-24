"""Girişim ve paket çakışmaları.

Capture effect: Bir alım, onunla zamanda örtüşen her gönderime karşı aşağıdaki
SIR (sinyal/girişim) eşiklerini sağlıyorsa başarılıdır:
- Aynı SF: istenen sinyal, aynı SF'deki tüm girişimlerin toplam gücünden en az
  `capture_threshold_db` (varsayılan 6 dB) güçlü olmalı.
- Farklı SF: her girişim için Croce vd. (2018) eşik matrisi. LoRa SF'leri yarı
  ortogonal olduğundan eşikler negatiftir: istenen sinyal girişimden zayıf olsa
  bile alınabilir.

D. Croce, M. Gucciardo, S. Mangione, G. Santaromita, I. Tinnirello,
"Impact of LoRa Imperfect Orthogonality: Analysis of Link-Level Performance",
IEEE Communications Letters, 2018.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

# SIR_THRESHOLD_DB[istenen SF][girişim SF] (dB)
_SFS = (7, 8, 9, 10, 11, 12)
_MATRIX = (
    (1, -8, -9, -9, -9, -9),
    (-11, 1, -11, -12, -13, -13),
    (-15, -13, 1, -13, -14, -15),
    (-19, -18, -17, 1, -17, -18),
    (-22, -22, -21, -20, 1, -20),
    (-25, -25, -25, -24, -23, 1),
)
SIR_THRESHOLD_DB = {a: {b: float(_MATRIX[i][j]) for j, b in enumerate(_SFS)} for i, a in enumerate(_SFS)}


@dataclass(frozen=True)
class Interferer:
    power_dbm: float
    sf: Optional[int]  # None → geniş bantlı (LoRa olmayan) girişim
    start_s: float
    end_s: float


def survives_capture(signal_dbm: float, sf: int, interferers: list[Interferer], co_sf_threshold_db: float) -> bool:
    same = [i.power_dbm for i in interferers if i.sf == sf]
    if same:
        total = 10 * np.log10(sum(10 ** (p / 10) for p in same))
        if signal_dbm - total < co_sf_threshold_db:
            return False
    for i in interferers:
        if i.sf is not None and i.sf != sf and signal_dbm - i.power_dbm < SIR_THRESHOLD_DB[sf][i.sf]:
            return False
    return True


class ExternalInterference:
    """Simülasyon dışındaki bir kaynaktan Poisson süreciyle gelen girişim darbeleri.

    Darbeler zaman ekseninde ihtiyaç duyuldukça üretilir; tüm alıcılarda aynı güçte
    görüldüğü varsayılır.
    """

    def __init__(self, rate_hz: float, duration_s: float, power_dbm: float, sf: Optional[int],
                 rng: np.random.Generator):
        self.rate = rate_hz
        self.duration = duration_s
        self.power = power_dbm
        self.sf = sf
        self.rng = rng
        self._bursts: list[Interferer] = []
        self._next = rng.exponential(1 / rate_hz) if rate_hz > 0 else float("inf")

    def overlapping(self, start_s: float, end_s: float) -> list[Interferer]:
        while self._next < end_s:
            self._bursts.append(Interferer(self.power, self.sf, self._next, self._next + self.duration))
            self._next += self.rng.exponential(1 / self.rate)
        horizon = start_s - 10 * self.duration - 60.0
        if self._bursts and self._bursts[0].end_s < horizon:
            self._bursts = [b for b in self._bursts if b.end_s >= horizon]
        return [b for b in self._bursts if b.start_s < end_s and b.end_s > start_s]
