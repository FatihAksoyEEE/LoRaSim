import numpy as np
import pytest

from lorasim.config import ConfigError, SimConfig
from lorasim.lora.lora_parameters import LoRaPhy
from lorasim.config import LoRaConfig
from lorasim.simulation.ack_manager import auto_ack_timeout_s, build_ack, parse_ack
from lorasim.simulation.duty_cycle import DutyCycleTracker
from lorasim.simulation.simulation_engine import SimulationEngine


def make(distance=100.0, packets=50, **traffic) -> SimConfig:
    cfg = SimConfig()
    cfg.run.mode = "accelerated"
    cfg.run.seed = 11
    cfg.topology.distance_m = distance
    cfg.traffic.max_packets = packets
    for k, v in traffic.items():
        setattr(cfg.traffic, k, v)
    return cfg


def run(cfg):
    e = SimulationEngine(cfg)
    return e, e.run()


# --- ACK yapısı ve timeout ---------------------------------------------------
@pytest.mark.parametrize("crc", [True, False])
def test_ack_roundtrip(crc):
    frame = build_ack(70000, crc)
    assert len(frame) == (5 if crc else 3)
    assert parse_ack(frame) == 70000 & 0xFFFF


def test_parse_rejects_non_ack():
    assert parse_ack(b"\x00\x01\x00") is None
    assert parse_ack(b"\x00") is None


def test_auto_ack_timeout_sf7():
    # ACK airtime: 12.25 + 8 + ceil(40/28)·5 = 30.25 sembol × 1.024 ms = 30.976 ms
    phy = LoRaPhy.from_config(LoRaConfig())
    assert auto_ack_timeout_s(phy, 0.01) == pytest.approx(0.01 + 0.030976 + 4 * 0.001024 + 0.01)


def test_auto_timeout_grows_with_sf():
    t7 = auto_ack_timeout_s(LoRaPhy.from_config(LoRaConfig(spreading_factor=7)), 0.01)
    t12 = auto_ack_timeout_s(LoRaPhy.from_config(LoRaConfig(spreading_factor=12)), 0.01)
    assert t12 > 10 * t7


# --- ACK ve tekrar gönderim -------------------------------------------------
def test_good_link_confirms_every_packet_first_try():
    e, s = run(make())
    assert s["packets_confirmed"] == 50 and s["retransmissions"] == 0
    assert s["ack_success_rate"] == 1.0
    expected = e.airtime_s + e.config.ack.turnaround_s + e.ack_airtime_s
    assert s["mean_confirm_latency_s"] == pytest.approx(expected)
    assert s["mean_latency_s"] == pytest.approx(e.airtime_s)


def test_ack_disabled():
    cfg = make()
    cfg.ack.enabled = False
    _, s = run(cfg)
    assert s["transmissions"] == 50 and s["retransmissions"] == 0
    assert s["ack_counts"]["disabled"] == 50
    assert s["outcome_counts"]["delivered"] == 50 and s["ack_success_rate"] is None


@pytest.mark.parametrize("retries", [0, 1, 3, 5])
def test_dead_link_uses_all_retries(retries):
    cfg = make(distance=900_000.0, packets=10)
    cfg.ack.max_retries = retries
    e, s = run(cfg)
    assert s["packets_failed"] == 10
    assert s["transmissions"] == 10 * (retries + 1)
    assert s["retransmissions"] == 10 * retries
    assert {r.ack_status for r in e.metrics.records} == {"not_sent"}
    assert max(r.retransmissions for r in e.metrics.records) == retries


def test_retransmission_after_timeout():
    cfg = make(distance=900_000.0, packets=1)
    cfg.ack.retry_backoff_max_s = 0.0
    e, _ = run(cfg)
    starts = [r.time_s - r.airtime_s for r in e.metrics.records]
    # Backoff yokken her deneme, öncekinin alım zamanı + ACK timeout anında başlar.
    for prev, cur in zip(e.metrics.records, starts[1:]):
        assert cur == pytest.approx(prev.time_s + e.ack_timeout_s)


def test_retry_backoff_is_random_and_bounded():
    cfg = make(distance=900_000.0, packets=20)
    cfg.traffic.interval_s = 30.0
    cfg.ack.retry_backoff_max_s = 2.0
    e, _ = run(cfg)
    recs = list(e.metrics.records)
    waits = [b.time_s - b.airtime_s - (a.time_s + e.ack_timeout_s)
             for a, b in zip(recs, recs[1:]) if b.seq == a.seq]
    assert len(waits) == 60
    assert all(-1e-9 <= w <= 2.0 + 1e-9 for w in waits)
    assert np.std(waits) > 0.3


def test_too_short_user_timeout_gives_late_acks_and_duplicates():
    cfg = make(packets=5)
    cfg.traffic.interval_s = 10.0
    cfg.ack.timeout_s = 0.001  # ACK dönüş gecikmesinden bile kısa
    cfg.ack.max_retries = 2
    e, s = run(cfg)
    recs = list(e.metrics.records)
    first = [r for r in recs if r.retransmissions == 0]
    assert all(r.ack_status == "late" for r in first)
    # Tekrar gönderim, alıcı ACK gönderirken gelirse half-duplex nedeniyle alınamaz.
    for r in recs:
        assert r.status in ("ok", "half_duplex")
        assert r.ack_status == ("late" if r.status == "ok" else "not_sent")
    # Veri alıcıya ulaştı ama hiçbiri onaylanamadı.
    assert s["outcome_counts"]["delivered"] == 5 and s["packets_confirmed"] == 0
    ok = sum(r.status == "ok" for r in recs)
    assert sum(r.duplicate for r in recs) == ok - 5
    # Throughput yalnızca benzersiz paketleri sayar.
    assert s["throughput_bps"] == pytest.approx(5 * 8 * 20 / s["elapsed_sim_time_s"])


def test_packet_timeout_stops_retries():
    cfg = make(distance=900_000.0, packets=1)
    cfg.ack.max_retries = 10
    cfg.ack.retry_backoff_max_s = 0.0
    e, _ = run(cfg)
    per_attempt = e.airtime_s + e.ack_timeout_s
    cfg.ack.packet_timeout_s = 2.5 * per_attempt
    _, s = run(cfg)
    assert s["transmissions"] == 3


# --- Duty-cycle --------------------------------------------------------------
def test_tracker_off_time_rule():
    d = DutyCycleTracker(0.01)
    assert not d.would_violate(0.0)
    d.register(0.0, 0.1)
    assert d.would_violate(9.99)
    assert not d.would_violate(10.0)
    assert d.next_allowed(5.0) == pytest.approx(10.0)


def test_tracker_disabled():
    d = DutyCycleTracker(None)
    d.register(0.0, 1.0)
    assert not d.would_violate(0.0) and d.next_allowed(0.5) == 0.5


def test_warn_policy_counts_violations_without_delaying():
    e, s = run(make(interval_s=1.0, duty_cycle_policy="warn"))
    assert s["duty_cycle_violations"] == 49  # ilk paket hariç hepsi
    starts = [r.time_s for r in e.metrics.records]
    assert starts[1] - starts[0] == pytest.approx(1.0)


def test_enforce_policy_respects_limit():
    e, s = run(make(interval_s=1.0, duty_cycle_policy="enforce", tx_queue_size=100, packets=30))
    assert s["duty_cycle_violations"] == 0 and s["ack_duty_cycle_violations"] == 0
    starts = [r.time_s - r.airtime_s for r in e.metrics.records]
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert min(gaps) >= e.airtime_s / 0.01 - 1e-9
    # Ölçüm penceresi son gönderimin bitişinde kapandığı için n paket için üst sınır n/(n-1)·%1.
    assert s["duty_cycle"] <= 0.01 * 30 / 29 + 1e-9


def test_no_duty_cycle_limit():
    _, s = run(make(interval_s=0.2, duty_cycle_limit=None))
    assert s["duty_cycle_violations"] == 0


def test_invalid_traffic_and_ack_config():
    cfg = make(duty_cycle_limit=1.5, duty_cycle_policy="strict", tx_queue_size=0)
    cfg.ack.max_retries = -1
    with pytest.raises(ConfigError) as exc:
        cfg.validate()
    assert len(exc.value.errors) == 4
