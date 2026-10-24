"""SX1276 enerji tüketimi tahmini.

Akım değerleri SX1276 veri sayfası Tablo 6'dan (3,3 V, 868 MHz bandı):
- Gönderim: +7 dBm (RFO) 20 mA, +13 dBm (RFO) 29 mA, +17 dBm (PA_BOOST) 87 mA,
  +20 dBm (PA_BOOST) 120 mA. Ara değerler doğrusal ara değerleme; -4 dBm için
  ~16 mA varsayılmıştır.
- Alım (LoRa, LnaBoost açık): 125 kHz 10,8 mA, 250 kHz 11,6 mA, 500 kHz 12,4 mA.
- Uyku: 0,2 µA.
Mikrodenetleyici ve sensör tüketimi dahil değildir.
"""

from __future__ import annotations

import numpy as np

SUPPLY_VOLTAGE_V = 3.3
_TX_POINTS_DBM = (-4.0, 7.0, 13.0, 17.0, 20.0)
_TX_POINTS_MA = (16.0, 20.0, 29.0, 87.0, 120.0)
RX_CURRENT_MA = {125e3: 10.8, 250e3: 11.6, 500e3: 12.4}
SLEEP_CURRENT_MA = 0.0002


def tx_current_ma(power_dbm: float) -> float:
    return float(np.interp(power_dbm, _TX_POINTS_DBM, _TX_POINTS_MA))


def device_energy(tx_time_s: float, rx_time_s: float, total_time_s: float, tx_power_dbm: float,
                  bandwidth_hz: float) -> dict:
    sleep_s = max(total_time_s - tx_time_s - rx_time_s, 0.0)
    tx_mas = tx_current_ma(tx_power_dbm) * tx_time_s
    rx_mas = RX_CURRENT_MA[bandwidth_hz] * rx_time_s
    sleep_mas = SLEEP_CURRENT_MA * sleep_s
    to_j = SUPPLY_VOLTAGE_V / 1000
    total_mas = tx_mas + rx_mas + sleep_mas
    return {
        "tx_time_s": tx_time_s,
        "rx_time_s": rx_time_s,
        "sleep_time_s": sleep_s,
        "tx_energy_j": tx_mas * to_j,
        "rx_energy_j": rx_mas * to_j,
        "sleep_energy_j": sleep_mas * to_j,
        "energy_j": total_mas * to_j,
        "mean_current_ma": total_mas / total_time_s if total_time_s > 0 else None,
    }
