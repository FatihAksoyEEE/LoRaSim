"""LoRa payload CRC'si: CRC-16/CCITT (polinom 0x1021, başlangıç 0x0000, XMODEM varyantı)."""

from __future__ import annotations


def _make_table() -> list[int]:
    table = []
    for byte in range(256):
        crc = byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
        table.append(crc & 0xFFFF)
    return table


_TABLE = _make_table()


def crc16(data: bytes) -> int:
    crc = 0x0000
    for b in data:
        crc = ((crc << 8) & 0xFFFF) ^ _TABLE[((crc >> 8) ^ b) & 0xFF]
    return crc


def append_crc(data: bytes) -> bytes:
    return data + crc16(data).to_bytes(2, "big")


def check_crc(frame: bytes) -> bool:
    """Son iki byte'ı CRC olan bir çerçeveyi doğrular."""
    return len(frame) >= 2 and crc16(frame[:-2]) == int.from_bytes(frame[-2:], "big")
