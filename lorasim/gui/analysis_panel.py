"""Analiz sekmesi: ortam karşılaştırması, mesafe/güç/SF taramaları, menzil ve model karşılaştırması."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QProgressBar, QPushButton, QSpinBox,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from lorasim.config import ConfigError, SimConfig
from lorasim.export import report_exporter
from lorasim.export.csv_exporter import write_rows_csv
from lorasim.export.json_exporter import write_sweep_json
from lorasim.gui.plotting_widgets import AnalysisPlot
from lorasim.gui.results_panel import fmt
from lorasim.gui.workers import AnalysisThread
from lorasim.simulation import analysis

COLUMN_LABELS = {
    "parameter": "Parametre", "value": "Değer", "seed": "Seed", "success_rate": "Başarı oranı", "per": "PER",
    "packet_loss_rate": "Kayıp oranı", "ber": "BER", "mean_rssi_dbm": "Ort. RSSI (dBm)", "mean_snr_db": "Ort. SNR (dB)",
    "throughput_bps": "Throughput (bit/s)", "mean_latency_s": "Gecikme (s)", "retransmissions": "Tekrar gönderim",
    "energy_per_delivered_packet_mj": "Enerji/paket (mJ)", "packets_generated": "Paket", "snr_db": "SNR (dB)",
    "ser_theory": "SER (teori)", "per_link_level": "PER link-level", "ser_link_level": "SER link-level",
    "ber_link_level": "BER link-level", "per_css_phy": "PER CSS", "ser_css_phy": "SER CSS", "ber_css_phy": "BER CSS",
}

ANALYSES = (
    ("environment", "Ortam karşılaştırması"),
    ("distance", "Mesafe – başarı oranı"),
    ("power", "Güç – başarı oranı"),
    ("sf", "SF karşılaştırması"),
    ("range", "Başarılı haberleşme mesafesi"),
    ("models", "Link-level ↔ CSS model karşılaştırması"),
)


class AnalysisPanel(QWidget):
    status = Signal(str)

    def __init__(self, get_config: Callable[[], SimConfig], export_path: Callable[[str, str], object]):
        super().__init__()
        self.get_config = get_config
        self.export_path = export_path
        self.thread: Optional[AnalysisThread] = None
        self.rows: list[dict] = []
        self.kind = "environment"
        self.extra: dict = {}
        self.base_config: Optional[SimConfig] = None

        self.combo = QComboBox()
        for key, label in ANALYSES:
            self.combo.addItem(label, key)
        self.packets = QSpinBox()
        self.packets.setRange(10, 100_000)
        self.packets.setValue(200)
        self.packets.setSuffix(" paket/nokta")
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.01, 0.999)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(0.9)
        self.run_btn, self.stop_btn = QPushButton("Analizi başlat"), QPushButton("Durdur")
        self.stop_btn.setEnabled(False)
        self.run_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.progress = QProgressBar()
        self.result_label = QLabel("")
        top = QHBoxLayout()
        for w in (QLabel("Analiz:"), self.combo, self.packets, QLabel("Başarı eşiği:"), self.threshold,
                  self.run_btn, self.stop_btn, self.progress):
            top.addWidget(w)

        self.plot = AnalysisPlot()
        self.table = QTableWidget(0, 0)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.plot)
        split.addWidget(self.table)
        save = QHBoxLayout()
        self.save_buttons = {}
        for key, label in (("csv", "Sonuçları CSV kaydet"), ("json", "JSON kaydet"), ("png", "Grafiği PNG kaydet"),
                           ("pdf", "PDF kaydet")):
            b = QPushButton(label)
            b.setEnabled(False)
            b.clicked.connect(lambda _=False, k=key: self.save(k))
            self.save_buttons[key] = b
            save.addWidget(b)
        save.addStretch()
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.result_label)
        lay.addWidget(split, 1)
        lay.addLayout(save)

    # --- çalıştırma ---------------------------------------------------------
    def start(self) -> bool:
        try:
            cfg = self.get_config()
            cfg.validate()
        except ConfigError as e:
            QMessageBox.warning(self, "Geçersiz parametre", str(e))
            return False
        kind = self.combo.currentData()
        packets, threshold = self.packets.value(), self.threshold.value()

        def job(progress, should_stop):
            if kind == "models":
                return analysis.compare_models(cfg, packets=packets, progress=progress, should_stop=should_stop), {}
            if kind == "range":
                rng_m, rows = analysis.find_max_range(cfg, threshold, packets, progress=progress, should_stop=should_stop)
                return rows, {"max_range_m": rng_m, "threshold": threshold}
            return analysis.run_sweep(cfg, kind, None, packets, progress=progress, should_stop=should_stop), {}

        self.kind, self.base_config = kind, cfg
        self.thread = AnalysisThread(job)
        self.thread.progress.connect(self._progress)
        self.thread.finished_ok.connect(self._finished)
        self.thread.failed.connect(self._failed)
        self.thread.finished.connect(lambda: self._set_running(False))
        self._set_running(True)
        self.progress.setValue(0)
        self.result_label.setText("Çalışıyor…")
        self.thread.start()
        return True

    def stop(self) -> None:
        if self.thread:
            self.thread.stop()

    def shutdown(self, timeout_ms: int = 10_000) -> None:
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait(timeout_ms)

    @property
    def running(self) -> bool:
        return bool(self.thread and self.thread.isRunning())

    def _set_running(self, running: bool) -> None:
        self.run_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.combo.setEnabled(not running)

    def _progress(self, i: int, n: int) -> None:
        self.progress.setMaximum(n)
        self.progress.setValue(i)

    def _failed(self, message: str) -> None:
        self.result_label.setText("Analiz başarısız.")
        QMessageBox.critical(self, "Analiz hatası", message)

    def _finished(self, rows: list, extra: dict) -> None:
        self.rows, self.extra = rows, extra
        self.plot.show_rows(rows, self.kind)
        self._fill_table(rows)
        if self.kind == "range":
            r = extra.get("max_range_m")
            text = "bulunamadı" if r is None else f"{r:,.0f} m"
            self.result_label.setText(f"Başarılı haberleşme mesafesi (başarı ≥ {extra['threshold']:g}): {text}")
        else:
            self.result_label.setText(f"{len(rows)} nokta tamamlandı.")
        for b in self.save_buttons.values():
            b.setEnabled(bool(rows))
        self.status.emit("Analiz tamamlandı.")

    def _fill_table(self, rows: list[dict]) -> None:
        keys = list(rows[0]) if rows else []
        self.table.clear()
        self.table.setColumnCount(len(keys))
        self.table.setRowCount(len(rows))
        self.table.setHorizontalHeaderLabels([COLUMN_LABELS.get(k, k) for k in keys])
        for r, row in enumerate(rows):
            for c, k in enumerate(keys):
                self.table.setItem(r, c, QTableWidgetItem(fmt(row[k])))

    # --- kayıt ---------------------------------------------------------------
    def save(self, kind: str):
        if not self.rows:
            return None
        path = self.export_path(f"analiz_{self.kind}", kind)
        if kind == "csv":
            write_rows_csv(self.rows, path)
        elif kind == "json":
            write_sweep_json(self.base_config, self.rows, path, dict(self.extra, analysis=self.kind))
        elif kind == "png":
            if self.kind == "models":
                report_exporter.plot_model_comparison(self.rows, path)
            else:
                report_exporter.plot_sweep(self.rows, path)
        elif self.kind == "models":
            report_exporter.write_model_comparison_pdf(path, self.rows)
        else:
            report_exporter.write_pdf_report(path, self.base_config, _empty_summary(), [], None, [self.rows])
        self.status.emit(f"Kaydedildi: {path}")
        return path


def _empty_summary() -> dict:
    """Yalnızca tarama içeren PDF raporu için boş özet."""
    return {"status_counts": {}, "ack_counts": {}, "per_device": {}}
