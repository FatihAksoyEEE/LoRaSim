import pytest

from lorasim.config import LoRaConfig
from lorasim.lora.lora_parameters import LoRaPhy, ldro_required
from lorasim.lora.sensitivity import noise_floor_dbm, sensitivity_dbm


def phy(**kw):
    return LoRaPhy.from_config(LoRaConfig(**kw))


# Referans değerler AN1200.13 formülüyle elle hesaplandı:
#   toplam sembol = (preamble + 4.25) + 8 + ceil((8PL-4SF+28+16CRC-20IH) / (4(SF-2DE))) · CR
@pytest.mark.parametrize("kw, payload, toa_ms", [
    # 12.25 + 8 + ceil(176/28)·5 = 55.25 sembol × 1.024 ms
    (dict(spreading_factor=7), 20, 56.576),
    # LDRO açık: 12.25 + 8 + ceil(156/40)·5 = 40.25 sembol × 32.768 ms
    (dict(spreading_factor=12), 20, 1318.912),
    # 12.25 + 8 + ceil(416/36)·8 = 116.25 sembol × 2.048 ms
    (dict(spreading_factor=9, bandwidth_khz=250.0, coding_rate=8), 51, 238.08),
    # CRC yok, implicit header: 12.25 + 8 + ceil(48/40)·5 = 30.25 sembol × 8.192 ms
    (dict(spreading_factor=10, crc_enabled=False, implicit_header=True), 10, 247.808),
])
def test_time_on_air(kw, payload, toa_ms):
    assert phy(**kw).time_on_air_s(payload) * 1e3 == pytest.approx(toa_ms, abs=1e-3)


def test_ldro_auto():
    assert not ldro_required(10, 125e3)          # 8.192 ms
    assert ldro_required(11, 125e3)              # 16.384 ms
    assert not ldro_required(11, 250e3)
    assert phy(spreading_factor=12).ldro
    assert not phy(spreading_factor=12, ldro=False).ldro


def test_bitrate_sf7_bw125_cr45():
    assert phy().bitrate_bps == pytest.approx(5468.75)


@pytest.mark.parametrize("sf, expected", [(7, -124.5), (9, -129.5), (12, -137.0)])
def test_sensitivity_bw125(sf, expected):
    assert sensitivity_dbm(sf, 125e3) == pytest.approx(expected, abs=0.05)


def test_sensitivity_override():
    assert sensitivity_dbm(7, 125e3, override_dbm=-120.0) == -120.0


def test_noise_floor():
    assert noise_floor_dbm(125e3, 6.0) == pytest.approx(-117.03, abs=0.01)
