import numpy as np
import pytest

from lorasim.channel import fading
from lorasim.channel.channel_model import Link, ResolvedChannel
from lorasim.devices.device import Device
from lorasim.devices.mobility import Static


def link(distance, lora=None, radio=None, channel=None, seed=0):
    a = Device("A", "tx", Static((0, 0, 0)))
    b = Device("B", "rx", Static((distance, 0, 0)))
    return Link(a, b, lora or LoRaConfig(), radio or RadioConfig(),
                ResolvedChannel.from_config(channel or ChannelConfig()), np.random.default_rng(seed))
from lorasim.channel.path_loss import free_space_path_loss_db, log_distance_path_loss_db
from lorasim.config import ChannelConfig, LoRaConfig, RadioConfig


def test_fspl_reference_values():
    # FSPL(dB) = 20log10(d_km) + 20log10(f_MHz) + 32.44
    assert free_space_path_loss_db(1000, 868e6) == pytest.approx(20 * np.log10(868) + 32.44, abs=0.01)
    assert free_space_path_loss_db(2000, 868e6) - free_space_path_loss_db(1000, 868e6) == pytest.approx(6.02, abs=0.01)


def test_log_distance_n2_equals_fspl():
    assert log_distance_path_loss_db(5000, 868e6, 2.0) == pytest.approx(free_space_path_loss_db(5000, 868e6))


def test_log_distance_slope():
    a = log_distance_path_loss_db(100, 868e6, 3.5)
    b = log_distance_path_loss_db(1000, 868e6, 3.5)
    assert b - a == pytest.approx(35.0)


def test_fading_mean_power_is_unity():
    rng = np.random.default_rng(0)
    ray = np.mean([10 ** (fading.rayleigh_gain_db(rng) / 10) for _ in range(40000)])
    ric = np.mean([10 ** (fading.rician_gain_db(rng, 6.0) / 10) for _ in range(40000)])
    assert ray == pytest.approx(1.0, abs=0.03)
    assert ric == pytest.approx(1.0, abs=0.03)


def test_profile_defaults_and_overrides():
    r = ResolvedChannel.from_config(ChannelConfig(environment="urban"))
    assert (r.path_loss_exponent, r.fading) == (3.2, "rayleigh")
    r = ResolvedChannel.from_config(ChannelConfig(environment="urban", fading="none", path_loss_exponent=2.9))
    assert (r.path_loss_exponent, r.fading) == (2.9, "none")
    r = ResolvedChannel.from_config(ChannelConfig(environment="urban", path_loss_model="free_space"))
    assert r.path_loss_exponent == 2.0


def test_link_budget_free_space():
    lora = LoRaConfig(tx_power_dbm=14.0)
    radio = RadioConfig(tx_antenna_gain_dbi=2.0, rx_antenna_gain_dbi=3.0, tx_losses_db=1.0, rx_losses_db=0.5)
    lb = link(1000.0, lora, radio)
    s = lb.sample(0.0)
    assert s.rssi_dbm == pytest.approx(14 + 2 - 1 + 3 - 0.5 - free_space_path_loss_db(1000, 868.1e6))
    assert s.snr_db == pytest.approx(s.rssi_dbm - lb.noise_dbm)


def test_awgn_off_gives_infinite_snr():
    lb = link(1000.0, channel=ChannelConfig(awgn_enabled=False))
    assert lb.sample(0.0).snr_db == float("inf")
