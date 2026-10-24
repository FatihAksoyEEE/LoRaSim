"""Ortam profilleri.

Değerler literatürdeki tipik aralıklardan seçilmiş başlangıç değerleridir
(ör. Rappaport, "Wireless Communications", Tablo 4.2; LoRa saha ölçümleri).
Kalibre edilmiş değildir; kullanıcı her alanı ChannelConfig üzerinden ezebilir.
Referans mesafe d0 = 1 m'dir.

Çok yollu gecikme profilleri (gecikme ns, bağıl güç dB) COST 207 (RA, TU, BU) ve
ITU-R M.1225 (Indoor A) kanal modellerinden alınmıştır.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvironmentProfile:
    name: str
    label: str
    path_loss_exponent: float
    shadowing_sigma_db: float
    fading: str
    rician_k_db: float = 0.0
    multipath_taps: tuple = ((0.0, 0.0),)  # (gecikme ns, bağıl güç dB)


PROFILES = {
    p.name: p
    for p in (
        EnvironmentProfile("free_space", "Serbest uzay", 2.0, 0.0, "none"),
        EnvironmentProfile("open_area", "Açık alan", 2.2, 2.0, "rician", 10.0,
                           ((0, 0), (100, -10), (300, -20))),
        EnvironmentProfile("rural", "Kırsal alan", 2.7, 4.0, "rician", 6.0,
                           ((0, 0), (100, -4), (200, -8), (300, -12), (400, -16), (500, -20))),
        EnvironmentProfile("urban", "Kentsel alan", 3.2, 6.0, "rayleigh", 0.0,
                           ((0, -3), (200, 0), (500, -2), (1600, -6), (2300, -8), (5000, -10))),
        EnvironmentProfile("dense_urban", "Yoğun kentsel alan", 3.6, 8.0, "rayleigh", 0.0,
                           ((0, -3), (400, 0), (1000, -3), (1600, -5), (5000, -2), (6600, -4))),
        EnvironmentProfile("indoor", "Kapalı alan", 3.0, 7.0, "rayleigh", 0.0,
                           ((0, 0), (50, -3), (110, -10), (170, -18), (290, -26), (310, -32))),
    )
}
