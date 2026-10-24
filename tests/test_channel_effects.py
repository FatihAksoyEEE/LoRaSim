import numpy as np
import pytest

from lorasim.channel.channel_model import Link, ResolvedChannel
from lorasim.channel.doppler import doppler_shift_hz, jakes_correlation
from lorasim.channel.interference import ExternalInterference, Interferer, SIR_THRESHOLD_DB, survives_capture
from lorasim.channel.noise import dbm_sum
from lorasim.config import ChannelConfig, LoRaConfig, RadioConfig
from lorasim.devices.device import Device
from lorasim.devices.mobility import ConstantVelocity, Static


def make_link(channel: ChannelConfig, traj_a=None, traj_b=None, seed=0, distance=1000.0):
    a = Device("A", "tx", traj_a or Static((0, 0, 0)))
    b = Device("B", "rx", traj_b or Static((distance, 0, 0)))
    return Link(a, b, LoRaConfig(), RadioConfig(), ResolvedChannel.from_config(channel), np.random.default_rng(seed))


def gains(link, times):
    return np.array([10 ** (link.sample(t).fading_db / 10) for t in times])


def test_multipath_gives_frequency_diversity():
    flat = gains(make_link(ChannelConfig(environment="dense_urban")), range(4000))
    mp = gains(make_link(ChannelConfig(environment="dense_urban", multipath_enabled=True)), range(4000))
    assert flat.mean() == pytest.approx(1.0, abs=0.06)
    assert mp.mean() == pytest.approx(1.0, abs=0.06)
    # Geniş bantlı chirp bant üzerinde ortalama aldığı için derin sönümler azalır.
    assert np.mean(mp < 0.1) < 0.5 * np.mean(flat < 0.1)
    assert mp.std() < flat.std()


def test_multipath_without_random_fading_still_varies():
    g = gains(make_link(ChannelConfig(environment="urban", fading="none", multipath_enabled=True)), range(200))
    assert g.std() > 0.05


def test_time_varying_fading_correlation():
    ch = ChannelConfig(environment="urban", time_varying=True, scatterer_doppler_hz=1.0)
    link = make_link(ch)
    close = gains(link, np.arange(0, 2000) * 0.005)   # 5 ms aralık: ρ ≈ 1
    link = make_link(ch, seed=1)
    far = gains(link, np.arange(0, 2000) * 5.0)       # 5 s aralık: ρ ≈ J0(31) ≈ 0
    corr = lambda x: np.corrcoef(x[:-1], x[1:])[0, 1]  # noqa: E731
    assert corr(close) > 0.95
    assert abs(corr(far)) < 0.15


def test_jakes_correlation():
    assert jakes_correlation(10.0, 0.0) == pytest.approx(1.0)
    assert jakes_correlation(10.0, 2.405 / (2 * np.pi * 10)) == pytest.approx(0.0, abs=1e-3)


def test_independent_fading_when_not_time_varying():
    g = gains(make_link(ChannelConfig(environment="urban")), np.arange(0, 2000) * 0.001)
    assert abs(np.corrcoef(g[:-1], g[1:])[0, 1]) < 0.1


def test_doppler_shift_sign_and_magnitude():
    f = 868e6
    expected = 30 / 299_792_458 * f
    assert doppler_shift_hz((0, 0, 0), (30, 0, 0), (1000, 0, 0), (0, 0, 0), f) == pytest.approx(expected)
    assert doppler_shift_hz((0, 0, 0), (-30, 0, 0), (1000, 0, 0), (0, 0, 0), f) == pytest.approx(-expected)
    assert doppler_shift_hz((0, 0, 0), (0, 30, 0), (1000, 0, 0), (0, 0, 0), f) == pytest.approx(0.0, abs=1e-9)


def test_link_reports_doppler_only_when_enabled():
    tx = ConstantVelocity((0, 0, 0), 30.0, 0.0)
    on = make_link(ChannelConfig(doppler_enabled=True), traj_a=tx).sample(1.0)
    off = make_link(ChannelConfig(doppler_enabled=False), traj_a=tx).sample(1.0)
    assert on.doppler_hz == pytest.approx(30 / 299_792_458 * 868.1e6, rel=1e-3)
    assert off.doppler_hz == 0.0


def test_distance_updates_for_moving_device():
    link = make_link(ChannelConfig(), traj_a=ConstantVelocity((0, 0, 0), 10.0, 180.0))
    s0, s1 = link.sample(0.0), link.sample(100.0)
    assert s1.distance_m == pytest.approx(2000.0)
    assert s1.path_loss_db - s0.path_loss_db == pytest.approx(6.02, abs=0.01)


def test_gudmundson_shadowing():
    ch = ChannelConfig(environment="urban", fading="none", time_varying=True, shadowing_decorrelation_m=50.0)
    static = make_link(ch)
    assert len({round(static.sample(t).shadowing_db, 9) for t in range(20)}) == 1
    moving = make_link(ch, traj_a=ConstantVelocity((0, 0, 0), 10.0, 90.0))
    sh = np.array([moving.sample(t).shadowing_db for t in np.arange(0, 3000) * 1.0])
    assert sh.std() == pytest.approx(6.0, rel=0.25)
    assert np.corrcoef(sh[:-1], sh[1:])[0, 1] == pytest.approx(np.exp(-10 / 50), abs=0.08)


def test_capture_same_sf():
    i = [Interferer(-100.0, 7, 0, 1)]
    assert survives_capture(-93.9, 7, i, 6.0)
    assert not survives_capture(-94.1, 7, i, 6.0)
    # Aynı SF'deki girişimler güç olarak toplanır.
    two = [Interferer(-100.0, 7, 0, 1), Interferer(-100.0, 7, 0, 1)]
    assert not survives_capture(-92.0, 7, two, 6.0)
    assert survives_capture(-90.9, 7, two, 6.0)


def test_capture_inter_sf_matrix():
    assert SIR_THRESHOLD_DB[12][7] == -25 and SIR_THRESHOLD_DB[7][12] == -9
    # SF12 sinyali, kendisinden 20 dB güçlü SF7 girişimine dayanır.
    assert survives_capture(-120.0, 12, [Interferer(-100.0, 7, 0, 1)], 6.0)
    assert not survives_capture(-120.0, 7, [Interferer(-100.0, 12, 0, 1)], 6.0)


def test_wideband_interferer_ignored_by_capture():
    assert survives_capture(-120.0, 7, [Interferer(-100.0, None, 0, 1)], 6.0)


def test_external_interference_poisson_rate():
    ext = ExternalInterference(2.0, 0.01, -110.0, 7, np.random.default_rng(0))
    n = 0
    for k in range(5000):
        n += len([b for b in ext.overlapping(k, k + 1) if b.start_s >= k])
    assert n / 5000 == pytest.approx(2.0, rel=0.05)


def test_dbm_sum():
    assert dbm_sum([-100.0, -100.0]) == pytest.approx(-96.99, abs=0.01)
    assert dbm_sum([]) == float("-inf")
