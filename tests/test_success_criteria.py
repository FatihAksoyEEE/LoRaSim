"""plan.md §14 "Başarı kriterleri": her kriter için bir doğrulama.

Bu dosya ilk sürümün kabul testidir; kriterlerden biri bozulursa hangisinin
bozulduğu test adından anlaşılır.
"""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from lorasim.config import ConfigError, SimConfig  # noqa: E402
from lorasim.export.csv_exporter import write_csv  # noqa: E402
from lorasim.export.json_exporter import write_json  # noqa: E402
from lorasim.export.report_exporter import plot_time_series  # noqa: E402
from lorasim.simulation.analysis import environment_comparison  # noqa: E402
from lorasim.simulation.packet_manager import HEADER_BYTES, parse_header  # noqa: E402
from lorasim.simulation.simulation_engine import SimulationEngine  # noqa: E402


def cfg(**kw) -> SimConfig:
    c = SimConfig()
    c.run.mode, c.run.seed = "accelerated", 21
    c.traffic.max_packets = 50
    c.channel.environment, c.topology.distance_m = "urban", 1500.0
    for k, v in kw.items():
        section, name = k.split("__")
        setattr(getattr(c, section), name, v)
    return c


def test_k1_lora_parameters_changeable_from_gui():
    from PySide6.QtWidgets import QApplication
    from lorasim.gui.main_window import MainWindow
    QApplication.instance() or QApplication([])
    w = MainWindow()
    for name, value in (("spreading_factor", 10), ("bandwidth_khz", 500.0), ("coding_rate", 8), ("tx_power_dbm", 5.0),
                        ("payload_bytes", 100), ("crc_enabled", False), ("frequency_mhz", 433.5)):
        w.form.set_value("lora", name, value)
        assert getattr(w.form.get_config().lora, name) == value
    w.close()


def test_k2_continuous_random_byte_packets():
    c = cfg(traffic__max_packets=None, traffic__duration_s=60.0, ack__enabled=False)
    e = SimulationEngine(c)
    payloads = []
    e.on_record = None
    orig = e.model.receive
    e.model.receive = lambda frame, *a: payloads.append(frame) or orig(frame, *a)
    e.run()
    assert len(payloads) == 60  # süre boyunca her saniye bir paket
    seqs = [parse_header(p)[0] for p in payloads]
    assert seqs == list(range(60))
    bodies = {p[HEADER_BYTES:-2] for p in payloads}
    assert len(bodies) == 60  # her paketin rastgele içeriği farklı


def test_k3_one_transmitter_one_receiver():
    s = SimulationEngine(cfg()).run()
    assert s["num_transmitters"] == 1 and s["num_receivers"] == 1 and s["packets_generated"] == 50


def test_k4_core_metrics_computed():
    s = SimulationEngine(cfg()).run()
    for key in ("mean_rssi_dbm", "mean_snr_db", "per", "throughput_bps", "mean_latency_s"):
        assert s[key] is not None, key


def test_k5_at_least_three_environments_compared():
    rows = environment_comparison(cfg(), ["free_space", "rural", "urban", "dense_urban"], packets=40)
    assert len({r["value"] for r in rows}) >= 3
    rates = [r["success_rate"] for r in rows]
    assert rates[0] >= rates[-1] and len(set(rates)) > 1


def test_k6_realtime_and_accelerated():
    acc = SimulationEngine(cfg(traffic__max_packets=10)).run()
    rt = SimulationEngine(cfg(traffic__max_packets=10, run__mode="realtime", run__speed=500.0)).run()
    assert acc["packets_generated"] == rt["packets_generated"] == 10


def test_k7_ack_and_retransmission():
    s = SimulationEngine(cfg(topology__distance_m=3000.0, traffic__max_packets=100)).run()
    assert s["retransmissions"] > 0 and s["packets_confirmed"] > 0
    assert s["ack_counts"]["acked"] == s["packets_confirmed"]


def test_k8_csv_json_and_graphics(tmp_path):
    c = cfg()
    e = SimulationEngine(c)
    s = e.run()
    write_csv(e.metrics.records, tmp_path / "a.csv")
    write_json(c, s, tmp_path / "a.json")
    plot_time_series(e.metrics.records, tmp_path / "a.png")
    assert (tmp_path / "a.csv").read_text(encoding="utf-8").count("\n") == s["transmissions"] + 1
    assert json.loads((tmp_path / "a.json").read_text(encoding="utf-8"))["summary"]["packets_generated"] == 50
    assert (tmp_path / "a.png").stat().st_size > 10_000


def test_k9_parameter_errors_are_clear():
    c = cfg(lora__spreading_factor=13, lora__tx_power_dbm=30.0)
    with pytest.raises(ConfigError) as exc:
        c.validate()
    msgs = exc.value.errors
    assert len(msgs) == 2
    assert any("SF 7–12" in m and "13" in m for m in msgs)
    assert any("Gönderim gücü" in m and "30" in m for m in msgs)


def test_k10_link_level_results_reproducible():
    a = SimulationEngine(cfg(topology__num_transmitters=5)).run()
    b = SimulationEngine(cfg(topology__num_transmitters=5)).run()
    a.pop("resolved_channel"), b.pop("resolved_channel")
    assert a == b
