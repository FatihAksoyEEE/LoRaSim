"""ACK paket yapısı ve otomatik ACK timeout hesabı.

ACK payload'ı (3 byte):  | Onaylanan paket no (2 B) | 0xAC |
ACK, veri paketiyle aynı LoRa ayarlarıyla (SF, BW, CR, CRC) gönderilir.
"""

from __future__ import annotations

from typing import Optional

from lorasim.lora.crc import append_crc
from lorasim.lora.lora_parameters import LoRaPhy

ACK_MARKER = 0xAC
ACK_PAYLOAD_BYTES = 3
GUARD_SYMBOLS = 4  # preamble algılama ve zamanlama belirsizliği payı
GUARD_S = 0.010  # işlemci/SPI gecikme payı


def build_ack(seq: int, crc_enabled: bool) -> bytes:
    payload = (seq & 0xFFFF).to_bytes(2, "big") + bytes([ACK_MARKER])
    return append_crc(payload) if crc_enabled else payload


def parse_ack(frame: bytes) -> Optional[int]:
    """Geçerli bir ACK ise onaylanan paket numarasını döndürür."""
    if len(frame) < ACK_PAYLOAD_BYTES or frame[2] != ACK_MARKER:
        return None
    return int.from_bytes(frame[0:2], "big")


def ack_airtime_s(phy: LoRaPhy) -> float:
    return phy.time_on_air_s(ACK_PAYLOAD_BYTES)


def auto_ack_timeout_s(phy: LoRaPhy, turnaround_s: float) -> float:
    """Verinin bitişinden itibaren: dönüş gecikmesi + ACK airtime + koruma payı."""
    return turnaround_s + ack_airtime_s(phy) + GUARD_SYMBOLS * phy.symbol_duration_s + GUARD_S
