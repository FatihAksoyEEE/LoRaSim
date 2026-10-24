"""Paket üretimi.

Mantıksal paket yapısı (LoRa payload'ı, toplam `payload_bytes` byte):

    | Paket no (2 B, big-endian) | Zaman (4 B, ms) | Rastgele byte'lar | + PHY CRC (2 B, isteğe bağlı)

CRC, LoRa PHY'nin eklediği alandır ve payload uzunluğuna dahil değildir
(airtime formülündeki CRC terimiyle tutarlı).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from lorasim.lora.crc import append_crc

HEADER_BYTES = 6


@dataclass(frozen=True)
class Packet:
    seq: int
    tx_id: str
    rx_id: str
    created_at_s: float
    payload: bytes
    crc_enabled: bool

    @property
    def frame(self) -> bytes:
        """Havadan giden bayt dizisi (payload + varsa CRC)."""
        return append_crc(self.payload) if self.crc_enabled else self.payload


def build_payload(seq: int, timestamp_s: float, length: int, rng: np.random.Generator) -> bytes:
    header = (seq & 0xFFFF).to_bytes(2, "big") + (int(timestamp_s * 1000) & 0xFFFFFFFF).to_bytes(4, "big")
    return header + rng.integers(0, 256, length - HEADER_BYTES, dtype=np.uint8).tobytes()


def parse_header(payload: bytes) -> tuple[int, float]:
    return int.from_bytes(payload[0:2], "big"), int.from_bytes(payload[2:6], "big") / 1000


class PacketFactory:
    def __init__(self, tx_id: str, rx_id: str, payload_bytes: int, crc_enabled: bool,
                 rng: np.random.Generator):
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.payload_bytes = payload_bytes
        self.crc_enabled = crc_enabled
        self.rng = rng
        self._next_seq = 0

    def create(self, now_s: float) -> Packet:
        seq = self._next_seq
        self._next_seq += 1
        payload = build_payload(seq, now_s, self.payload_bytes, self.rng)
        return Packet(seq, self.tx_id, self.rx_id, now_s, payload, self.crc_enabled)
