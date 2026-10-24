import numpy as np

from lorasim.config import LoRaConfig
from lorasim.lora.lora_parameters import LoRaPhy
from lorasim.simulation.link_level_model import LinkLevelModel, RxStatus
from lorasim.simulation.packet_manager import PacketFactory


def run(snr_db, n=400, rssi=-100.0, **kw):
    cfg = LoRaConfig(**kw)
    rng = np.random.default_rng(1)
    model = LinkLevelModel(LoRaPhy.from_config(cfg), -124.5, rng)
    f = PacketFactory("T", "R", cfg.payload_bytes, cfg.crc_enabled, rng)
    return [model.receive(f.create(0).frame, rssi, snr_db) for _ in range(n)]


def per(results):
    return np.mean([r.status != RxStatus.OK for r in results])


def test_high_snr_error_free():
    res = run(10.0)
    assert all(r.status == RxStatus.OK and r.bit_errors == 0 for r in res)


def test_below_sensitivity_not_detected():
    assert all(r.status == RxStatus.NOT_DETECTED for r in run(10.0, n=10, rssi=-130.0))


def test_low_snr_fails():
    assert per(run(-12.0)) > 0.99


def test_per_decreases_with_snr():
    assert per(run(-11.0)) > per(run(-9.0)) > per(run(-7.0))


def test_strong_coding_helps():
    assert per(run(-9.0, coding_rate=8)) < per(run(-9.0, coding_rate=5))


def test_crc_catches_errors_and_off_lets_them_through():
    with_crc = run(-9.5)
    assert any(r.status == RxStatus.CRC_ERROR for r in with_crc)
    assert not any(r.status == RxStatus.CORRUPTED for r in with_crc)
    without = run(-9.5, crc_enabled=False)
    corrupted = [r for r in without if r.status == RxStatus.CORRUPTED]
    assert corrupted and all(r.bit_errors > 0 for r in corrupted)
