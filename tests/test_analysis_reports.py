import csv
import json
import math

import numpy as np
import pytest

from lorasim.config import ConfigError, SimConfig
from lorasim.export import report_exporter
from lorasim.export.csv_exporter import write_rows_csv
from lorasim.export.json_exporter import write_sweep_json
from lorasim.metrics.timeseries import auto_window_s, windowed
from lorasim.simulation import analysis
from lorasim.simulation.simulation_engine import SimulationEngine


def base() -> SimConfig:
    c = SimConfig()
    c.run.seed = 7
    c.run.mode = "accelerated"
    c.traffic.duty_cycle_limit = None
    c.traffic.interval_s = 5.0
    c.ack.enabled = False
    return c


def test_distance_sweep_monotonic():
    rows = analysis.run_sweep(base(), "distance", [100, 1000, 10_000, 100_000, 500_000], packets=50)
    rates = [r["success_rate"] for r in rows]
    assert rates == sorted(rates, reverse=True) and rates[0] == 1.0 and rates[-1] == 0.0
    assert all(r["parameter"] == "distance" and r["seed"] == 7 for r in rows)


def test_power_sweep_monotonic():
    c = base()
    c.channel.environment = "urban"
    c.channel.shadowing = "per_packet"
    c.topology.distance_m = 1500.0
    rows = analysis.run_sweep(c, "power", None, packets=100)
    assert [r["value"] for r in rows] == list(range(-4, 21, 2))
    rates = [r["success_rate"] for r in rows]
    assert all(b >= a - 0.05 for a, b in zip(rates, rates[1:]))
    assert rates[-1] > rates[0] + 0.3


def test_sf_sweep_and_environment_comparison():
    c = base()
    c.channel.environment = "urban"
    c.topology.distance_m = 3000.0
    rows = analysis.run_sweep(c, "sf", None, packets=50)
    assert [r["value"] for r in rows] == [7, 8, 9, 10, 11, 12]
    assert rows[-1]["success_rate"] >= rows[0]["success_rate"]
    env = analysis.environment_comparison(c, packets=30)
    assert [r["value"] for r in env] == ["free_space", "open_area", "rural", "urban", "dense_urban", "indoor"]


def test_sweep_progress_and_stop():
    calls = []
    rows = analysis.run_sweep(base(), "sf", None, packets=10, progress=lambda i, n: calls.append((i, n)),
                              should_stop=lambda: len(calls) >= 2)
    assert len(rows) == 2 and calls == [(1, 6), (2, 6)]


def test_distance_sweep_requires_distance_mode():
    c = base()
    c.topology.mode = "random"
    with pytest.raises(ConfigError):
        analysis.run_sweep(c, "distance", [100], packets=5)


def test_max_range_interpolation():
    rows = [{"value": 100, "success_rate": 1.0}, {"value": 1000, "success_rate": 0.8},
            {"value": 10_000, "success_rate": 0.0}]
    assert analysis.max_range_m(rows, 0.9) == pytest.approx(10 ** 2.5)
    assert analysis.max_range_m(rows[:1], 0.9) == 100
    assert analysis.max_range_m([{"value": 10, "success_rate": 0.5}], 0.9) is None


def test_find_max_range_matches_free_space_theory():
    """Serbest uzay, sönümleme yok: menzil, yol kaybının hassasiyete eşit olduğu mesafedir."""
    c = base()
    budget = c.lora.tx_power_dbm - (-124.5)  # SF7/125 kHz hassasiyeti
    f = c.lora.frequency_mhz * 1e6
    theory = 10 ** (budget / 20) * 299_792_458 / (4 * math.pi * f)
    rng, rows = analysis.find_max_range(c, 0.9, packets=40)
    assert rng == pytest.approx(theory, rel=0.05)
    assert len(rows) > 24


def test_windowed_timeseries():
    c = base()
    c.traffic.max_packets = 100
    c.traffic.interval_s = 1.0
    c.topology.distance_m = 10_000.0
    c.channel.environment = "urban"
    e = SimulationEngine(c)
    e.run()
    ts = windowed(e.metrics.records, 10.0)
    assert len(ts.t) == 10
    total_ok = sum(r.success for r in e.metrics.records)
    assert np.nansum(ts.throughput_bps * 10.0) == pytest.approx(total_ok * 160)
    assert np.all((ts.per[~np.isnan(ts.per)] >= 0) & (ts.per[~np.isnan(ts.per)] <= 1))
    assert auto_window_s(3600) == 100 and auto_window_s(10) == 0.2


def _pdf_pages(path) -> int:
    return path.read_bytes().count(b"/Type /Page\n") + path.read_bytes().count(b"/Type /Page ")


def test_png_pdf_csv_json_outputs(tmp_path):
    c = base()
    c.traffic.max_packets = 40
    c.topology.num_transmitters = 3
    c.mobility.moving = "transmitters"
    c.ack.enabled = True
    e = SimulationEngine(c)
    s = e.run()
    png = tmp_path / "ts.png"
    report_exporter.plot_time_series(e.metrics.records, png)
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    traj = report_exporter.trajectories_from_engine(e)
    assert len(traj["TX1"][1]) == 200 and len(traj["RX1"][1]) == 1
    report_exporter.plot_positions(traj, tmp_path / "pos.png")
    rows = analysis.run_sweep(c, "sf", [7, 9], packets=10)
    report_exporter.plot_sweep(rows, tmp_path / "sweep.png")
    pdf = tmp_path / "r.pdf"
    report_exporter.write_pdf_report(pdf, c, s, e.metrics.records, traj, [rows])
    assert pdf.read_bytes()[:5] == b"%PDF-"
    assert _pdf_pages(pdf) >= 6  # özet, ayarlar, zaman, konum, tarama grafiği, tarama tablosu
    write_rows_csv(rows, tmp_path / "s.csv")
    parsed = list(csv.DictReader(open(tmp_path / "s.csv", encoding="utf-8")))
    assert [int(r["value"]) for r in parsed] == [7, 9]
    write_sweep_json(c, rows, tmp_path / "s.json", {"max_range_m": float("inf")})
    data = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert data["results"][1]["value"] == 9 and data["max_range_m"] is None
    assert SimConfig.from_dict(data["base_config"]) == c


def test_summary_text_contains_key_metrics():
    c = base()
    c.traffic.max_packets = 5
    s = SimulationEngine(c).run()
    text = "\n".join(report_exporter.summary_lines(s))
    for label in ("Başarı oranı", "PER (frame)", "Throughput", "Enerji / başarılı paket", "Duty-cycle"):
        assert label in text
