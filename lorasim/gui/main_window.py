"""Ana pencere: parametre panelleri, simülasyon kontrolleri, canlı grafikler, sonuçlar ve analiz."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDockWidget, QDoubleSpinBox, QFileDialog, QLabel, QMainWindow, QMessageBox, QTabWidget,
    QToolBar, QVBoxLayout, QWidget,
)

from lorasim import __version__
from lorasim.config import ConfigError, SimConfig
from lorasim.export import report_exporter
from lorasim.export.csv_exporter import write_csv
from lorasim.export.json_exporter import write_json
from lorasim.gui.analysis_panel import AnalysisPanel
from lorasim.gui.parameter_panels import ConfigForm, default_cartesian_devices
from lorasim.gui.plotting_widgets import LivePlots
from lorasim.gui.results_panel import ExportBar, PacketLog, SummaryPanel
from lorasim.gui.workers import SimulationThread

UPDATE_INTERVAL_MS = 200
MAX_GUI_RECORDS = 50_000


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"LoRaSim {__version__} — SX1276 LoRa Haberleşme Simülatörü")
        self.resize(1500, 950)
        self.sim: Optional[SimulationThread] = None
        self.records: list = []
        self.last_summary: Optional[dict] = None
        self.last_config: Optional[SimConfig] = None

        # Sol: parametre panelleri
        self.form = ConfigForm()
        dock = QDockWidget("Parametreler", self)
        dock.setWidget(self.form)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        dock.setMinimumWidth(400)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

        # Orta: sekmeler
        self.plots = LivePlots()
        self.summary = SummaryPanel()
        self.export_bar = ExportBar()
        self.export_bar.export_requested.connect(self.export)
        results = QWidget()
        rl = QVBoxLayout(results)
        rl.addWidget(self.summary, 1)
        rl.addWidget(self.export_bar)
        self.log = PacketLog()
        self.analysis = AnalysisPanel(self._config_for_analysis, self.analysis_export_path)
        self.analysis.status.connect(self.set_status)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.plots, "Canlı grafikler")
        self.tabs.addTab(results, "Sonuçlar")
        self.tabs.addTab(self.log, "Paket logu")
        self.tabs.addTab(self.analysis, "Analiz")
        self.setCentralWidget(self.tabs)

        self._build_toolbar()
        self._build_menu()
        self.status_label = QLabel("Hazır.")
        self.statusBar().addWidget(self.status_label, 1)
        self.form.changed.connect(self._sync_toolbar)
        self.form.changed.connect(self._topology_mode_changed)
        self._sync_toolbar()
        self._update_buttons()

        self.timer = QTimer(self)
        self.timer.setInterval(UPDATE_INTERVAL_MS)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    # --- arayüz kurulumu ----------------------------------------------------
    def _build_toolbar(self) -> None:
        tb = QToolBar("Simülasyon")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.act_start = QAction("▶ Başlat", self, shortcut=QKeySequence("F5"), triggered=self.start)
        self.act_pause = QAction("⏸ Duraklat", self, shortcut=QKeySequence("F6"), triggered=self.toggle_pause)
        self.act_stop = QAction("■ Durdur", self, shortcut=QKeySequence("F7"), triggered=self.stop)
        self.act_reset = QAction("↺ Sıfırla", self, triggered=self.reset)
        for a in (self.act_start, self.act_pause, self.act_stop, self.act_reset):
            tb.addAction(a)
        tb.addSeparator()
        tb.addWidget(QLabel(" Mod: "))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Gerçek zamanlı", "realtime")
        self.mode_combo.addItem("Hızlandırılmış", "accelerated")
        self.mode_combo.currentIndexChanged.connect(
            lambda: self.form.set_value("run", "mode", self.mode_combo.currentData()))
        tb.addWidget(self.mode_combo)
        tb.addWidget(QLabel(" Zaman ölçeği: "))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.01, 10000)
        self.speed_spin.setSuffix("×")
        self.speed_spin.valueChanged.connect(lambda v: self.form.set_value("run", "speed", v))
        tb.addWidget(self.speed_spin)

    def _build_menu(self) -> None:
        m = self.menuBar().addMenu("&Dosya")
        m.addAction(QAction("Ayarları yükle…", self, shortcut=QKeySequence.StandardKey.Open,
                            triggered=lambda: self.load_config()))
        m.addAction(QAction("Ayarları kaydet…", self, shortcut=QKeySequence.StandardKey.Save,
                            triggered=lambda: self.save_config()))
        m.addAction(QAction("Varsayılan ayarlar", self, triggered=lambda: self.form.set_config(SimConfig())))
        m.addSeparator()
        for key, label in (("csv", "Paket kayıtlarını CSV kaydet"), ("json", "Özeti JSON kaydet"),
                           ("png", "Grafikleri PNG kaydet"), ("pdf", "PDF rapor oluştur"), ("all", "Tümünü kaydet")):
            m.addAction(QAction(label, self, triggered=lambda _=False, k=key: self.export(k)))
        m.addSeparator()
        m.addAction(QAction("Çıkış", self, shortcut=QKeySequence.StandardKey.Quit, triggered=self.close))
        h = self.menuBar().addMenu("&Yardım")
        h.addAction(QAction("Hakkında", self, triggered=self._about))

    def _about(self) -> None:
        QMessageBox.about(self, "Hakkında", f"<b>LoRaSim {__version__}</b><br>SX1276 LoRa haberleşme kalitesi "
                          "simülatörü.<br>Link-level ve CSS fiziksel katman modelleri, çoklu cihaz, hareket, ACK ve "
                          "kanal etkileri.<br><br>© 2026 Mehmet Fatih Aksoy · MIT Lisansı<br>"
                          "<a href='https://github.com/FatihAksoyEEE/LoRaSim'>github.com/FatihAksoyEEE/LoRaSim</a>")

    def _sync_toolbar(self) -> None:
        cfg_mode = self.form.widget("run", "mode").currentData()
        speed_w = self.form.widget("run", "speed")
        for w, fn in ((self.mode_combo, lambda: self.mode_combo.setCurrentIndex(self.mode_combo.findData(cfg_mode))),
                      (self.speed_spin, lambda: self.speed_spin.setValue(speed_w.value()))):
            w.blockSignals(True)
            fn()
            w.blockSignals(False)

    def _topology_mode_changed(self) -> None:
        if self.form.widget("topology", "mode").currentData() == "cartesian" \
                and self.form.device_table.table.rowCount() == 0:
            self.form.device_table.set_devices(default_cartesian_devices())

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    # --- simülasyon kontrolü -------------------------------------------------
    @property
    def running(self) -> bool:
        return bool(self.sim and self.sim.isRunning())

    def _update_buttons(self) -> None:
        running = self.running
        self.act_start.setEnabled(not running)
        self.act_pause.setEnabled(running)
        self.act_stop.setEnabled(running)
        self.form.setEnabled(not running)
        self.act_pause.setText("⏵ Devam et" if running and self.sim.engine.paused else "⏸ Duraklat")

    def read_config(self) -> Optional[SimConfig]:
        """Formu okur ve doğrular; hata varsa kullanıcıya gösterir ve None döner."""
        try:
            cfg = self.form.get_config()
            cfg.validate()
            return cfg
        except ConfigError as e:
            QMessageBox.warning(self, "Geçersiz parametre",
                                "Simülasyon başlatılamadı, lütfen şu alanları düzeltin:\n\n• "
                                + "\n• ".join(e.errors))
            return None

    def _config_for_analysis(self) -> SimConfig:
        return self.form.get_config()

    def start(self) -> bool:
        if self.running:
            return False
        cfg = self.read_config()
        if cfg is None:
            return False
        try:
            sim = SimulationThread(cfg)
        except ConfigError as e:
            QMessageBox.warning(self, "Geçersiz parametre", str(e))
            return False
        self._clear_results()
        self.sim, self.last_config = sim, cfg
        self.export_bar.name.setText(self.export_bar.default_name())
        # Sıfırla/yeniden başlat sonrası kuyrukta kalan eski sinyaller yok sayılır.
        sim.finished_ok.connect(lambda summary, sim=sim: sim is self.sim and self._finished(summary))
        sim.failed.connect(lambda message, sim=sim: sim is self.sim and self._failed(message))
        sim.finished.connect(self._update_buttons)
        sim.start()
        self.set_status(f"Çalışıyor — {'gerçek zamanlı' if cfg.run.mode == 'realtime' else 'hızlandırılmış'} mod, "
                        f"seed {sim.engine.seed}")
        self._update_buttons()
        self.tabs.setCurrentWidget(self.plots)
        return True

    def toggle_pause(self) -> None:
        if not self.running:
            return
        engine = self.sim.engine
        if engine.paused:
            engine.resume()
            self.set_status("Devam ediyor.")
        else:
            engine.pause()
            self.set_status("Duraklatıldı.")
        self._update_buttons()

    def stop(self) -> None:
        if self.running:
            self.sim.engine.stop()
            self.set_status("Durduruluyor…")

    def reset(self) -> None:
        self.shutdown_simulation()
        self.sim = None
        self.last_summary = None
        self._clear_results()
        self._update_buttons()
        self.set_status("Sıfırlandı.")

    def shutdown_simulation(self, timeout_ms: int = 5000) -> None:
        if self.sim and self.sim.isRunning():
            self.sim.engine.stop()
            self.sim.wait(timeout_ms)

    def _clear_results(self) -> None:
        self.records = []
        self.plots.clear()
        self.log.model.clear()
        self.summary.clear()

    def _tick(self) -> None:
        if not self.sim:
            return
        new = self.sim.drain()
        engine = self.sim.engine
        if new:
            self.records.extend(new)
            if len(self.records) > MAX_GUI_RECORDS:
                del self.records[: len(self.records) - MAX_GUI_RECORDS]
            self.log.append(new)
            self.plots.update_records(self.records)
        if self.plots.toggles["positions"].isChecked():
            self.plots.update_positions(engine.device_positions(engine.now))
        if self.running and new:
            try:
                self.summary.show_summary(engine.live_summary())
            except RuntimeError:
                pass  # sayaçlar o anda güncelleniyordu; bir sonraki adımda tekrar okunur
            self.set_status(f"Çalışıyor — simülasyon zamanı {engine.now:,.1f} s, {engine.metrics.transmissions:,} "
                            f"gönderim{' (duraklatıldı)' if engine.paused else ''}")

    def _finished(self, summary: dict) -> None:
        self._tick()
        self.last_summary = summary
        self.summary.show_summary(summary)
        self.plots.show_trajectories(report_exporter.trajectories_from_engine(self.sim.engine))
        self.last_config.run.seed = summary["seed"]
        warn = ""
        if summary["duty_cycle_violations"] or summary["ack_duty_cycle_violations"]:
            warn = " — UYARI: duty-cycle sınırı aşıldı"
        self.set_status(f"Tamamlandı: {summary['packets_generated']:,} paket, başarı oranı "
                        f"{(summary['success_rate'] or 0):.3f}{warn}")
        self._update_buttons()

    def _failed(self, message: str) -> None:
        self.set_status("Simülasyon hata ile durdu.")
        QMessageBox.critical(self, "Simülasyon hatası", message)
        self._update_buttons()

    # --- kayıt ---------------------------------------------------------------
    def analysis_export_path(self, suffix: str, ext: str) -> Path:
        base = self.export_bar.path_for(ext)
        return base.with_name(f"{base.stem}_{suffix}.{ext}")

    def export(self, kind: str) -> list[Path]:
        if not self.sim:
            QMessageBox.information(self, "Kayıt", "Önce bir simülasyon çalıştırın.")
            return []
        engine = self.sim.engine
        records = list(self.records) if self.running else list(engine.metrics.records)
        summary = self.last_summary if (self.last_summary and not self.running) else engine.live_summary()
        cfg = self.last_config
        saved = []
        kinds = ("csv", "json", "png", "pdf") if kind == "all" else (kind,)
        try:
            for k in kinds:
                path = self.export_bar.path_for(k)
                if k == "csv":
                    write_csv(records, path)
                elif k == "json":
                    write_json(cfg, summary, path)
                elif k == "png":
                    report_exporter.plot_time_series(records, path)
                    pos = path.with_name(f"{path.stem}_konumlar.png")
                    report_exporter.plot_positions(report_exporter.trajectories_from_engine(engine), pos)
                    saved.append(pos)
                else:
                    if self.running:
                        QMessageBox.information(self, "PDF", "PDF raporu simülasyon bittikten sonra oluşturulabilir.")
                        continue
                    report_exporter.write_pdf_report(path, cfg, summary, records,
                                                     report_exporter.trajectories_from_engine(engine))
                saved.append(path)
        except OSError as e:
            QMessageBox.critical(self, "Kayıt hatası", f"Dosya yazılamadı: {e}")
            return saved
        if saved:
            self.set_status("Kaydedildi: " + ", ".join(p.name for p in saved))
        return saved

    def load_config(self, path: Optional[str] = None) -> bool:
        path = path or QFileDialog.getOpenFileName(self, "Ayarları yükle", "", "JSON (*.json)")[0]
        if not path:
            return False
        try:
            data = SimConfig.load(path)
        except (ConfigError, ValueError, TypeError, OSError) as e:
            QMessageBox.warning(self, "Ayarlar yüklenemedi", str(e))
            return False
        self.form.set_config(data)
        self.set_status(f"Ayarlar yüklendi: {path}")
        return True

    def save_config(self, path: Optional[str] = None) -> bool:
        try:
            cfg = self.form.get_config()
        except ConfigError as e:
            QMessageBox.warning(self, "Geçersiz parametre", str(e))
            return False
        path = path or QFileDialog.getSaveFileName(self, "Ayarları kaydet", "ayarlar.json", "JSON (*.json)")[0]
        if not path:
            return False
        cfg.save(path)
        self.set_status(f"Ayarlar kaydedildi: {path}")
        return True

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt adı)
        self.timer.stop()
        self.shutdown_simulation()
        self.analysis.shutdown()
        event.accept()


def main(argv: Optional[list[str]] = None) -> int:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("LoRaSim")
    win = MainWindow()
    win.show()
    return app.exec()
