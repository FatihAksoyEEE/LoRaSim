import pytest

from lorasim.config import SimConfig
from lorasim.simulation.simulation_engine import SimulationEngine


def make(**kw) -> SimConfig:
    cfg = SimConfig()
    cfg.run.mode = "accelerated"
    cfg.run.seed = 5
    cfg.traffic.max_packets = 300
    cfg.channel.environment = "urban"
    cfg.topology.distance_m = kw.pop("distance", 1500.0)
    for k, v in kw.items():
        setattr(cfg.lora, k, v)
    return cfg


def test_reproducible_with_seed():
    a = SimulationEngine(make()).run()
    b = SimulationEngine(make()).run()
    assert a == b


def test_seed_generated_when_missing():
    cfg = make()
    cfg.run.seed = None
    e = SimulationEngine(cfg)
    assert isinstance(e.seed, int)


def test_packet_limit_and_timing():
    cfg = make()
    cfg.ack.enabled = False
    cfg.traffic.interval_s = 2.0
    e = SimulationEngine(cfg)
    s = e.run()
    assert s["packets_sent"] == 300
    times = [r.time_s for r in e.metrics.records]
    assert times[1] - times[0] == pytest.approx(2.0)


def test_interval_shorter_than_airtime_queues_and_drops():
    cfg = make(spreading_factor=12, distance=100.0)
    cfg.ack.enabled = False
    cfg.traffic.interval_s = 0.1
    cfg.traffic.max_packets = 50
    cfg.traffic.tx_queue_size = 3
    e = SimulationEngine(cfg)
    s = e.run()
    times = [r.time_s for r in e.metrics.records]
    assert times[1] - times[0] == pytest.approx(e.airtime_s)  # gönderimler arka arkaya
    assert s["packets_dropped_queue"] > 0
    assert s["packets_generated"] == 50


def test_duration_limit():
    cfg = make()
    cfg.traffic.max_packets = None
    cfg.traffic.duration_s = 10.0
    cfg.ack.enabled = False
    s = SimulationEngine(cfg).run()
    # Süre sınırı yeni paket üretimini durdurur; yoldaki paketler tamamlanır.
    assert s["packets_generated"] == 10
    assert s["elapsed_sim_time_s"] < 11.0


def test_duration_limit_lets_inflight_packets_finish():
    cfg = make()
    cfg.traffic.max_packets = None
    cfg.traffic.duration_s = 10.0
    e = SimulationEngine(cfg)
    s = e.run()
    assert s["packets_generated"] == 10
    # Tüm paketler sonuçlandı (kuyrukta veya yolda kalan yok).
    assert sum(s["outcome_counts"].values()) == 10
    # Kuyrukta bekleyen paketler de tamamlanacağı için en kötü durum birkaç paketin tüm denemeleridir.
    worst = (cfg.ack.max_retries + 1) * (e.airtime_s + e.ack_timeout_s + cfg.ack.retry_backoff_max_s)
    assert s["elapsed_sim_time_s"] < 10.0 + 4 * worst


def test_higher_sf_reaches_further():
    def success(**kw):
        cfg = make(distance=4000.0, **kw)
        cfg.traffic.interval_s = 5.0  # SF12 airtime'ı (1.3 s) kuyruğu taşırmasın
        return SimulationEngine(cfg).run()["success_rate"]
    assert success(spreading_factor=12) > success(spreading_factor=7)


def test_realtime_mode_paces_and_stops():
    import threading, time
    cfg = make()
    cfg.run.mode = "realtime"
    cfg.run.speed = 20.0  # 1 s aralık → 50 ms
    cfg.traffic.max_packets = None
    cfg.ack.enabled = False
    e = SimulationEngine(cfg)
    threading.Timer(0.5, e.stop).start()
    t0 = time.monotonic()
    s = e.run()
    assert 0.45 < time.monotonic() - t0 < 1.5
    assert 5 <= s["packets_sent"] <= 15
