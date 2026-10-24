"""Uzun süreli ve büyük yüklü simülasyonlarda kararlılık, bellek ve tutarlılık testleri."""

import tracemalloc

import numpy as np
import pytest

from lorasim.config import SimConfig
from lorasim.lora.error_model import symbol_error_rate
from lorasim.simulation.css_phy_model import CssPhyModel
from lorasim.simulation.link_level_model import RxStatus
from lorasim.simulation.simulation_engine import SimulationEngine


def cfg(**kw) -> SimConfig:
    c = SimConfig()
    c.run.mode, c.run.seed = "accelerated", 11
    c.channel.environment, c.topology.distance_m = "urban", 1500.0
    for k, v in kw.items():
        section, name = k.split("__")
        setattr(getattr(c, section), name, v)
    return c


def test_long_run_memory_is_bounded_and_counters_consistent():
    symbol_error_rate(7, 0.0)  # SER tablosunu ölçüm dışında hazırla
    c = cfg(traffic__max_packets=30_000, run__max_records=500)
    tracemalloc.start()
    e = SimulationEngine(c)
    s = e.run()
    current, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert current < 5e6  # kayıt sayısı sınırlı; bellek paket sayısıyla büyümez
    assert len(e.metrics.records) == 500
    assert s["packets_generated"] == 30_000
    assert sum(s["outcome_counts"].values()) == 30_000
    assert sum(s["status_counts"].values()) == s["transmissions"]
    assert len(e.scheduler) == 0 and len(e._air) < 10


def test_multi_device_long_run_resolves_every_packet():
    c = cfg(topology__num_transmitters=25, traffic__max_packets=400, traffic__interval_s=3.0,
            mobility__moving="transmitters", mobility__model="random_walk", channel__time_varying=True,
            channel__doppler_enabled=True, channel__frequency_offset_enabled=True)
    e = SimulationEngine(c)
    s = e.run()
    assert s["packets_generated"] == 25 * 400
    assert sum(d["generated"] for d in s["per_device"].values()) == 10_000
    assert all(not tx.busy and not tx.queue and tx.pending is None for tx in e.transmitters.values())
    assert 0 < s["success_rate"] < 1


def test_realtime_and_accelerated_give_same_results():
    a = cfg(traffic__max_packets=30, traffic__interval_s=0.5)
    b = cfg(traffic__max_packets=30, traffic__interval_s=0.5, run__mode="realtime", run__speed=200.0)
    sa, sb = SimulationEngine(a).run(), SimulationEngine(b).run()
    for k in ("packets_successful", "transmissions", "status_counts", "mean_rssi_dbm", "elapsed_sim_time_s"):
        assert sa[k] == sb[k]


def test_css_long_run_and_large_packets():
    c = cfg(run__model="css_phy", traffic__max_packets=600, traffic__interval_s=2.0)
    s = SimulationEngine(c).run()
    assert s["packets_generated"] == 600 and s["transmissions"] >= 600
    # SF12, 255 byte, gürültülü kanalda arka arkaya çok paket
    c = cfg(lora__spreading_factor=12, lora__payload_bytes=255, lora__coding_rate=8)
    from lorasim.lora.lora_parameters import LoRaPhy
    from lorasim.simulation.packet_manager import PacketFactory
    phy = LoRaPhy.from_config(c.lora)
    rng = np.random.default_rng(0)
    m = CssPhyModel(phy, -200.0, rng)
    f = PacketFactory("T", "R", 255, True, rng)
    res = [m.receive(f.create(0).frame, -100.0, -15.0) for _ in range(30)]
    assert all(r.status == RxStatus.OK for r in res)
    assert sum(r.symbols_compared for r in res) == 30 * phy.payload_symbols(255)


def test_pause_resume_during_long_realtime_run():
    import threading
    import time
    c = cfg(run__mode="realtime", run__speed=100.0, traffic__max_packets=None, ack__enabled=False)
    e = SimulationEngine(c)
    th = threading.Thread(target=e.run)
    th.start()
    time.sleep(0.3)
    e.pause()
    time.sleep(0.05)
    n = e.metrics.transmissions
    time.sleep(0.3)
    assert e.metrics.transmissions == n  # duraklatılmışken ilerlemez
    e.resume()
    time.sleep(0.3)
    assert e.metrics.transmissions > n
    e.stop()
    th.join(2)
    assert not th.is_alive()
