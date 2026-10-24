import numpy as np

from lorasim.lora.crc import append_crc, check_crc, crc16
from lorasim.simulation.packet_manager import HEADER_BYTES, PacketFactory, parse_header


def test_crc16_xmodem_check_value():
    assert crc16(b"123456789") == 0x31C3


def test_crc_detects_single_bit_errors():
    frame = bytearray(append_crc(b"hello lora payload"))
    assert check_crc(bytes(frame))
    for bit in range(len(frame) * 8):
        corrupted = bytearray(frame)
        corrupted[bit // 8] ^= 1 << (bit % 8)
        assert not check_crc(bytes(corrupted))


def test_packet_structure():
    f = PacketFactory("TX1", "RX1", 20, True, np.random.default_rng(0))
    p0, p1 = f.create(0.0), f.create(1.5)
    assert (p0.seq, p1.seq) == (0, 1)
    assert len(p1.payload) == 20 and len(p1.frame) == 22
    assert parse_header(p1.payload) == (1, 1.5)
    assert check_crc(p1.frame)
    assert p0.payload[HEADER_BYTES:] != p1.payload[HEADER_BYTES:]


def test_no_crc_frame_is_payload():
    p = PacketFactory("TX1", "RX1", 10, False, np.random.default_rng(0)).create(0.0)
    assert p.frame == p.payload
