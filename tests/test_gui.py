"""Arayüz testleri (ekransız Qt platformunda)."""

import csv
import json
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from lorasim.config import DeviceSpec, SimConfig  # noqa: E402
from lorasim.gui.main_window import MainWindow  # noqa: E402
from lorasim.simulation.simulation_engine import SimulationEngine  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    w = MainWindow()
    w.show()
    yield w
    w.close()


@pytest.fixture
def dialogs(monkeypatch):
    calls = []
    for name in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, n=name: calls.append((n, a[2] if len(a) > 2 else ""))))
    return calls


def wait_until(app, cond, timeout=30.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            for _ in range(5):
                app.processEvents()
            return True
        time.sleep(0.01)
    return False


def quick_config(win, **values):
    f = win.form
    f.set_value("run", "mode", "accelerated")
    f.set_value("run", "seed", 5)
    f.set_value("traffic", "max_packets", 60)
    f.set_value("traffic", "interval_s", 5.0)
    for key, v in values.items():
        section, name = key.split("__")
        f.set_value(section, name, v)


def run_to_end(app, win):
    assert win.start()
    assert wait_until(app, lambda: not win.running and win.last_summary is not None)


def test_form_roundtrip(win):
    cfg = SimConfig()
    cfg.lora.spreading_factor, cfg.lora.bandwidth_khz, cfg.lora.coding_rate = 10, 250.0, 7
    cfg.lora.tx_power_dbm, cfg.lora.payload_bytes, cfg.lora.crc_enabled = 17.0, 51, False
    cfg.lora.sync_word, cfg.lora.ldro, cfg.lora.implicit_header = 0x34, False, True
    cfg.radio.sensitivity_override_dbm = -130.0
    cfg.channel.environment, cfg.channel.fading, cfg.channel.path_loss_exponent = "rural", "rayleigh", 3.1
    cfg.channel.multipath_enabled = cfg.channel.time_varying = cfg.channel.interference_enabled = True
    cfg.channel.interference_type = "wideband"
    cfg.topology.mode = "cartesian"
    cfg.topology.devices = [DeviceSpec("GW", "rx", 0, 0), DeviceSpec("N1", "tx", 250, -40, target="GW",
                                                                     speed_mps=3.0, heading_deg=45.0)]
    cfg.mobility.moving, cfg.mobility.model, cfg.mobility.route = "all", "route", [[100.0, 0.0], [100.0, 50.0]]
    cfg.traffic.duty_cycle_limit, cfg.traffic.duty_cycle_policy, cfg.traffic.max_packets = 0.1, "enforce", 500
    cfg.ack.timeout_s, cfg.ack.max_retries, cfg.ack.enabled = 1.5, 7, False
    cfg.run.model, cfg.run.mode, cfg.run.seed, cfg.run.max_records = "css_phy", "accelerated", 99, None
    win.form.set_config(cfg)
    assert win.form.get_config() == cfg


def test_none_choices_do_not_leak_none_refcount(win):
    # PySide6 (Linux, Python 3.11) boş QComboBox verisini döndürürken None'ın referans sayısını
    # azaltıyordu; birikince yorumlayıcı kapanışta "none_dealloc" ile çöküyordu.
    cfg = SimConfig()
    cfg.lora.ldro = None
    cfg.channel.fading = None
    win.form.set_config(cfg)
    before = sys.getrefcount(None)
    for _ in range(200):
        win.form.set_config(cfg)
        assert win.form.get_config().lora.ldro is None
    assert sys.getrefcount(None) >= before - 50


def test_invalid_input_shows_error_and_does_not_start(win, dialogs):
    win.form.set_value("topology", "num_receivers", 2)  # mesafe modunda yalnızca bir alıcı olabilir
    assert not win.start()
    assert not win.running and win.sim is None
    assert dialogs and dialogs[0][0] == "warning" and "Mesafe modunda" in dialogs[0][1]
    win.form.set_value("topology", "num_receivers", 1)
    win.form.set_value("topology", "mode", "cartesian")
    win.form.device_table.table.item(0, 2).setText("abc")
    assert not win.start()
    assert "sayı değil" in dialogs[-1][1]


def test_accelerated_run_fills_plots_log_and_summary(app, win):
    quick_config(win, topology__num_transmitters=3, mobility__moving="transmitters", mobility__speed_mps=5.0)
    run_to_end(app, win)
    s = win.last_summary
    assert s["packets_generated"] == 180
    assert win.log.model.rowCount() == s["transmissions"] == len(win.records)
    assert win.summary.value("Üretilen paket") == "180"
    assert win.summary.devices.rowCount() == 3
    assert len(win.plots.rssi_scatter.data) == s["transmissions"]
    assert len(win.plots.thr_curve.getData()[0]) > 0
    assert set(win.plots._labels) == {"RX1", "TX1", "TX2", "TX3"}
    assert len(win.plots.trails["TX1"]) > 50  # tüm yol çizildi
    assert win.act_start.isEnabled() and not win.act_stop.isEnabled() and win.form.isEnabled()


def test_gui_result_matches_engine_with_same_seed(app, win):
    quick_config(win, channel__environment="urban", topology__num_transmitters=4)
    cfg = win.form.get_config()
    run_to_end(app, win)
    direct = SimulationEngine(cfg).run()
    for k in ("packets_successful", "transmissions", "status_counts", "mean_rssi_dbm", "ack_counts"):
        assert win.last_summary[k] == direct[k]


def test_realtime_pause_resume_stop(app, win):
    quick_config(win, run__mode="realtime", run__speed=50.0, traffic__interval_s=1.0, ack__enabled=False)
    win.form.set_value("traffic", "max_packets", None)
    assert win.start()
    assert wait_until(app, lambda: len(win.records) >= 3, 10)
    assert not win.form.isEnabled() and win.act_stop.isEnabled()
    win.toggle_pause()
    assert win.act_pause.text().endswith("Devam et")
    wait_until(app, lambda: False, 0.2)
    n = win.sim.engine.metrics.transmissions
    wait_until(app, lambda: False, 0.4)
    assert win.sim.engine.metrics.transmissions == n
    win.toggle_pause()
    assert wait_until(app, lambda: win.sim.engine.metrics.transmissions > n, 5)
    win.stop()
    assert wait_until(app, lambda: not win.running, 5)
    assert win.act_start.isEnabled()


def test_reset_clears_everything(app, win):
    quick_config(win)
    run_to_end(app, win)
    win.reset()
    assert win.sim is None and win.records == [] and win.log.model.rowCount() == 0
    assert win.summary.value("Üretilen paket") == "—"


def test_plot_toggles(win):
    win.plots.toggles["rssi"].setChecked(False)
    assert "rssi" not in win.plots.visible_plots() and not win.plots.plots["rssi"].isVisible()
    win.plots.toggles["rssi"].setChecked(True)
    assert win.plots.plots["rssi"].isVisible()


def test_exports(app, win, tmp_path, dialogs):
    win.export("csv")
    assert dialogs[-1][0] == "information"  # henüz simülasyon yok
    quick_config(win, topology__num_transmitters=2)
    run_to_end(app, win)
    win.export_bar.folder.setText(str(tmp_path / "kayit"))
    win.export_bar.name.setText("deneme")
    saved = win.export("all")
    names = sorted(p.name for p in saved)
    assert names == ["deneme.csv", "deneme.json", "deneme.pdf", "deneme.png", "deneme_konumlar.png"]
    rows = list(csv.DictReader(open(tmp_path / "kayit" / "deneme.csv", encoding="utf-8")))
    assert len(rows) == win.last_summary["transmissions"]
    data = json.loads((tmp_path / "kayit" / "deneme.json").read_text(encoding="utf-8"))
    assert data["summary"]["packets_generated"] == 120 and data["config"]["run"]["seed"] == 5
    assert (tmp_path / "kayit" / "deneme.pdf").read_bytes()[:5] == b"%PDF-"


def test_config_save_and_load(win, tmp_path, dialogs):
    win.form.set_value("lora", "spreading_factor", 11)
    path = tmp_path / "ayar.json"
    assert win.save_config(str(path))
    win.form.set_config(SimConfig())
    assert win.load_config(str(path))
    assert win.form.get_config().lora.spreading_factor == 11
    bad = tmp_path / "bozuk.json"
    bad.write_text('{"lora": {"sf": 7}}', encoding="utf-8")
    assert not win.load_config(str(bad))
    assert dialogs[-1][0] == "warning"


def test_toolbar_mode_syncs_with_form(win):
    win.mode_combo.setCurrentIndex(win.mode_combo.findData("accelerated"))
    assert win.form.get_config().run.mode == "accelerated"
    win.form.set_value("run", "mode", "realtime")
    assert win.mode_combo.currentData() == "realtime"


def test_cartesian_mode_gets_default_devices(win):
    win.form.device_table.set_devices([])
    win.form.set_value("topology", "mode", "cartesian")
    win.form.widget("topology", "mode").currentIndexChanged.emit(0)
    assert win.form.device_table.table.rowCount() == 3
    win.form.device_table.add_device("tx")
    assert win.form.get_config().topology.devices[-1].id == "TX3"


@pytest.mark.parametrize("kind, rows", [("environment", 6), ("sf", 6), ("models", 15)])
def test_analysis_tab(app, win, tmp_path, kind, rows):
    quick_config(win, channel__environment="urban", topology__distance_m=2000.0)
    win.export_bar.folder.setText(str(tmp_path))
    a = win.analysis
    a.combo.setCurrentIndex(a.combo.findData(kind))
    a.packets.setValue(20)
    assert a.start()
    assert wait_until(app, lambda: not a.running and a.rows, 120)
    assert a.table.rowCount() == rows
    for k in ("csv", "json", "png", "pdf"):
        assert a.save(k).stat().st_size > 100


def test_engine_failure_is_reported_not_crash(app, win, dialogs, monkeypatch):
    def boom(self):
        raise RuntimeError("deneme hatası")
    monkeypatch.setattr(SimulationEngine, "run", boom)
    quick_config(win)
    assert win.start()
    assert wait_until(app, lambda: not win.running and dialogs, 10)
    assert dialogs[-1][0] == "critical" and "deneme hatası" in dialogs[-1][1]
    assert win.act_start.isEnabled()


def test_close_while_running_stops_thread(app):
    w = MainWindow()
    w.show()
    w.form.set_value("run", "mode", "realtime")
    w.form.set_value("traffic", "max_packets", None)
    assert w.start()
    wait_until(app, lambda: False, 0.2)
    sim = w.sim
    w.close()
    assert not sim.isRunning() and sim.engine.stopped


def test_screenshot(app, win, tmp_path):
    quick_config(win, topology__num_transmitters=4, channel__environment="urban")
    run_to_end(app, win)
    path = tmp_path / "ekran.png"
    assert win.grab().save(str(path))
    assert path.stat().st_size > 10_000


def test_reset_while_running_ignores_stale_finish(app, win, monkeypatch):
    errors = []
    monkeypatch.setattr("sys.excepthook", lambda *exc: errors.append(exc))
    win.form.set_value("run", "mode", "realtime")
    win.form.set_value("traffic", "max_packets", None)
    assert win.start()
    wait_until(app, lambda: False, 0.2)
    win.reset()
    wait_until(app, lambda: False, 0.3)
    assert not errors
    assert win.sim is None and win.last_summary is None and win.summary.value("Üretilen paket") == "—"
