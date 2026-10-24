import numpy as np
import pytest

from lorasim.config import DeviceSpec, SimConfig
from lorasim.simulation.simulation_engine import SimulationEngine


def base(n_tx=1, packets=100, interval=10.0, ack=False, seed=1) -> SimConfig:
    c = SimConfig()
    c.run.mode, c.run.seed = "accelerated", seed
    c.traffic.max_packets, c.traffic.interval_s = packets, interval
    c.traffic.duty_cycle_limit = None
    c.ack.enabled = ack
    c.topology.num_transmitters = n_tx
    c.topology.distance_m = 500.0
    return c


def run(c):
    e = SimulationEngine(c)
    return e, e.run()


def collision_rate(s):
    return s["status_counts"]["collision"] / s["transmissions"]


def test_collisions_grow_with_number_of_transmitters():
    rates = [collision_rate(run(base(n_tx=n, interval=2.0))[1]) for n in (1, 5, 20, 50)]
    assert rates[0] == 0
    assert rates == sorted(rates) and rates[-1] > 0.3


def test_collision_rate_matches_aloha_theory():
    """Eşit güçlü, periyodik vericiler: bir verici, diğer n-1 vericinin fazı ±Ta içinde değilse başarılıdır.

    P(başarı) = (1 - 2·Ta/T)^(n-1) ≈ e^{-2G} (saf ALOHA), G = n·Ta/T. Fazlar tek seferde çekildiği
    için tek bir çalıştırmanın varyansı yüksektir; birkaç seed'in ortalaması alınır.
    """
    n, interval = 30, 3.0
    rates = []
    for seed in range(12):
        e, s = run(base(n_tx=n, packets=20, interval=interval, seed=seed))
        rates.append(s["status_counts"]["ok"] / s["transmissions"])
    expected = (1 - 2 * e.airtime_s / interval) ** (n - 1)
    assert np.mean(rates) == pytest.approx(expected, abs=0.06)


def test_collisions_can_be_disabled():
    c = base(n_tx=30, interval=1.0)
    c.channel.collisions_enabled = False
    assert run(c)[1]["status_counts"]["collision"] == 0


def test_capture_effect_strong_transmitter_wins():
    c = base(packets=50, interval=5.0)
    c.traffic.random_start = False  # iki verici her seferinde aynı anda gönderir
    c.topology.mode = "cartesian"
    c.topology.devices = [DeviceSpec("RX", "rx"), DeviceSpec("NEAR", "tx", 100, 0), DeviceSpec("FAR", "tx", 2000, 0)]
    e, s = run(c)
    assert s["per_device"]["NEAR"]["success_rate"] == 1.0
    assert s["per_device"]["FAR"]["collisions"] == 50


def test_equal_power_simultaneous_both_lost():
    c = base(packets=20, interval=5.0)
    c.traffic.random_start = False
    c.topology.mode = "cartesian"
    c.topology.devices = [DeviceSpec("RX", "rx"), DeviceSpec("A", "tx", 500, 0), DeviceSpec("B", "tx", -500, 0)]
    _, s = run(c)
    assert s["status_counts"]["collision"] == 40


def test_half_duplex_receiver_misses_data_while_sending_ack():
    c = base(n_tx=20, packets=100, interval=2.0, ack=True)
    _, s = run(c)
    assert s["status_counts"]["half_duplex"] > 0


def test_multiple_receivers_nearest_assignment():
    c = base(packets=10)
    c.topology.mode = "cartesian"
    c.topology.devices = [DeviceSpec("G1", "rx", 0, 0), DeviceSpec("G2", "rx", 3000, 0),
                          DeviceSpec("T1", "tx", 200, 0), DeviceSpec("T2", "tx", 2900, 0)]
    e, s = run(c)
    pairs = {(r.tx_id, r.rx_id) for r in e.metrics.records}
    assert pairs == {("T1", "G1"), ("T2", "G2")}
    assert s["num_receivers"] == 2


def test_random_topology_runs_and_per_device_totals_match():
    c = base(n_tx=15, packets=30, interval=5.0, ack=True)
    c.topology.mode, c.topology.num_receivers = "random", 3
    c.channel.environment = "urban"
    _, s = run(c)
    pd = s["per_device"]
    assert len(pd) == 15
    assert sum(d["generated"] for d in pd.values()) == s["packets_generated"] == 450
    assert sum(d["delivered"] for d in pd.values()) == s["packets_successful"]
    assert sum(d["transmissions"] for d in pd.values()) == s["transmissions"]


def test_external_lora_interference_causes_collisions():
    c = base(packets=200, interval=2.0)
    c.channel.interference_enabled = True
    c.channel.interference_power_dbm = -60.0  # alınan sinyalden çok güçlü
    c.channel.interference_rate_hz = 1.0
    _, s = run(c)
    assert s["status_counts"]["collision"] > 0
    c.channel.interference_power_dbm = -150.0  # çok zayıf: capture her zaman başarılı
    _, s = run(c)
    assert s["status_counts"]["collision"] == 0


def test_wideband_interference_raises_noise():
    c = base(packets=200, interval=2.0)
    c.topology.distance_m = 4000.0
    c.channel.interference_enabled = True
    c.channel.interference_type = "wideband"
    c.channel.interference_power_dbm = -75.0  # sinyal ≈ -89 dBm → SNR ≈ -14 dB
    c.channel.interference_rate_hz = 5.0
    c.channel.interference_duration_s = 0.5
    e, s = run(c)
    hit = [r for r in e.metrics.records if r.interferers > 0]
    clean = [r for r in e.metrics.records if r.interferers == 0]
    assert hit and clean
    assert np.mean([r.success for r in hit]) < np.mean([r.success for r in clean])


def test_frequency_offset_tolerance():
    c = base(packets=20)
    c.topology.mode = "cartesian"
    c.topology.devices = [DeviceSpec("R", "rx", frequency_offset_ppm=0.0),
                          DeviceSpec("OK", "tx", 200, 0, frequency_offset_ppm=20.0),   # 17.4 kHz < 31.25 kHz
                          DeviceSpec("BAD", "tx", -200, 0, frequency_offset_ppm=40.0)]  # 34.7 kHz > 31.25 kHz
    c.channel.collisions_enabled = False
    e, s = run(c)
    assert s["per_device"]["OK"]["success_rate"] == 1.0
    assert {r.status for r in e.metrics.records if r.tx_id == "BAD"} == {"freq_offset"}
    rec = next(r for r in e.metrics.records if r.tx_id == "OK")
    assert rec.freq_offset_hz == pytest.approx(20e-6 * 868.1e6)


def test_random_crystal_offsets_are_within_range():
    c = base(n_tx=20, packets=1)
    c.channel.frequency_offset_enabled = True
    c.channel.crystal_ppm = 10.0
    e, _ = run(c)
    assert all(abs(d.frequency_offset_ppm) <= 10.0 for d in e.devices.values())
    assert len({d.frequency_offset_ppm for d in e.devices.values()}) == 21


def test_moving_transmitter_loses_link_when_moving_away():
    c = base(packets=200, interval=5.0)
    c.topology.distance_m = 200.0
    c.channel.environment = "urban"
    c.channel.fading = "none"
    c.channel.shadowing = "off"
    c.channel.doppler_enabled = True
    c.mobility.moving = "transmitters"
    c.mobility.speed_mps = 10.0
    c.mobility.heading_deg = 0.0  # vericiler +x'te, alıcıdan uzaklaşıyor
    e, s = run(c)
    recs = list(e.metrics.records)
    dists = [r.distance_m for r in recs]
    assert dists == sorted(dists) and dists[-1] > 9000
    assert recs[0].success and not recs[-1].success
    assert all(r.doppler_hz < 0 for r in recs)  # uzaklaşma → negatif Doppler


def test_engine_positions_snapshot():
    c = base(n_tx=3)
    c.mobility.moving = "all"
    c.mobility.model = "circular"
    e, _ = run(c)
    pos = e.device_positions(0.0)
    assert set(pos) == {"RX1", "TX1", "TX2", "TX3"}
    assert pos["RX1"][0] == "rx"
    assert e.device_positions(10.0)["TX1"][1:] != pos["TX1"][1:]
