"""SF, BW ve CR'den türetilen LoRa büyüklükleri: sembol süresi, bit hızı, airtime.

Airtime formülü Semtech AN1200.13 (LoRa Modem Designer's Guide) ile aynıdır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from lorasim.config import LoRaConfig
from lorasim.lora import sx1276_config as hw


def symbol_duration_s(sf: int, bandwidth_hz: float) -> float:
    return (2 ** sf) / bandwidth_hz


def ldro_required(sf: int, bandwidth_hz: float) -> bool:
    return symbol_duration_s(sf, bandwidth_hz) > hw.LDRO_SYMBOL_TIME_THRESHOLD_S


@dataclass(frozen=True)
class LoRaPhy:
    """LoRaConfig'in hesaplamaya hazır, değişmez görünümü."""

    sf: int
    bandwidth_hz: float
    coding_rate: int
    preamble_symbols: int
    crc_enabled: bool
    implicit_header: bool
    ldro: bool

    @classmethod
    def from_config(cls, cfg: LoRaConfig) -> "LoRaPhy":
        bw = cfg.bandwidth_khz * 1e3
        ldro = ldro_required(cfg.spreading_factor, bw) if cfg.ldro is None else cfg.ldro
        return cls(cfg.spreading_factor, bw, cfg.coding_rate, cfg.preamble_symbols,
                   cfg.crc_enabled, cfg.implicit_header, ldro)

    @property
    def symbol_duration_s(self) -> float:
        return symbol_duration_s(self.sf, self.bandwidth_hz)

    @property
    def symbol_rate(self) -> float:
        return self.bandwidth_hz / (2 ** self.sf)

    @property
    def bitrate_bps(self) -> float:
        """Kodlama sonrası nominal veri hızı: SF · (4/CR) · BW / 2^SF."""
        return self.sf * (4 / self.coding_rate) * self.symbol_rate

    @property
    def bits_per_symbol(self) -> int:
        """LDRO açıkken her sembol SF-2 bit taşır."""
        return self.sf - 2 * int(self.ldro)

    def payload_symbols(self, payload_bytes: int) -> int:
        """Header dahil payload bölümünün sembol sayısı."""
        de = int(self.ldro)
        ih = int(self.implicit_header)
        crc = int(self.crc_enabled)
        num = 8 * payload_bytes - 4 * self.sf + 28 + 16 * crc - 20 * ih
        blocks = max(math.ceil(num / (4 * (self.sf - 2 * de))), 0)
        return 8 + blocks * self.coding_rate

    def preamble_duration_s(self) -> float:
        return (self.preamble_symbols + 4.25) * self.symbol_duration_s

    def time_on_air_s(self, payload_bytes: int) -> float:
        return self.preamble_duration_s() + self.payload_symbols(payload_bytes) * self.symbol_duration_s
