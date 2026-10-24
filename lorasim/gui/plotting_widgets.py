"""Canlı grafikler (PyQtGraph): her grafik ayrı açılıp kapatılabilir."""

from __future__ import annotations

import math
from collections import defaultdict, deque

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from lorasim.export.report_exporter import STATUS_COLORS, STATUS_LABELS
from lorasim.gui.parameter_panels import ENV_LABELS
from lorasim.metrics.collector import PacketRecord
from lorasim.metrics.timeseries import windowed

pg.setConfigOptions(antialias=True, background="w", foreground="k")

MAX_SCATTER_POINTS = 4000
TRAIL_POINTS = 400
STATUS_ORDER = list(STATUS_LABELS)


def _plot(title: str, xlabel: str, ylabel: str) -> pg.PlotWidget:
    w = pg.PlotWidget(title=title)
    w.setLabel("bottom", xlabel)
    w.setLabel("left", ylabel)
    w.showGrid(x=True, y=True, alpha=0.3)
    w.setMinimumHeight(180)
    for axis in ("left", "bottom"):
        w.getAxis(axis).enableAutoSIPrefix(False)  # oranlar "×0.001" gibi ölçeklenmesin
    return w


class LivePlots(QWidget):
    """RSSI, SNR, paket durumu, BER/PER, throughput, gecikme ve konum grafikleri."""

    PLOTS = {
        "rssi": "RSSI–zaman", "snr": "SNR–zaman", "status": "Paket başarı/hata", "error": "BER/PER–zaman",
        "throughput": "Throughput–zaman", "latency": "Gecikme–zaman", "positions": "Cihaz konumları",
    }

    def __init__(self):
        super().__init__()
        self.plots: dict[str, pg.PlotWidget] = {}
        self.toggles: dict[str, QCheckBox] = {}
        toggles = QHBoxLayout()
        toggles.addWidget(QLabel("Grafikler:"))
        for key, title in self.PLOTS.items():
            cb = QCheckBox(title)
            cb.setChecked(True)
            cb.toggled.connect(self._relayout)
            self.toggles[key] = cb
            toggles.addWidget(cb)
        toggles.addStretch()

        p = self.plots
        p["rssi"] = _plot("RSSI – zaman", "Zaman (s)", "RSSI (dBm)")
        p["snr"] = _plot("SNR – zaman", "Zaman (s)", "SNR (dB)")
        p["status"] = _plot("Paket başarı/hata durumu", "Zaman (s)", "")
        p["error"] = _plot("BER/PER – zaman", "Zaman (s)", "Oran")
        p["throughput"] = _plot("Throughput – zaman", "Zaman (s)", "bit/s")
        p["latency"] = _plot("Gecikme – zaman", "Zaman (s)", "ms")
        p["positions"] = _plot("Cihaz konumları ve hareketleri", "x (m)", "y (m)")
        p["positions"].setAspectLocked(True)
        p["status"].getAxis("left").setTicks([[(i, STATUS_LABELS[s]) for i, s in enumerate(STATUS_ORDER)]])
        p["status"].setYRange(-0.5, len(STATUS_ORDER) - 0.5)
        p["error"].addLegend()

        self.rssi_scatter = pg.ScatterPlotItem(size=5, pen=None)
        self.snr_scatter = pg.ScatterPlotItem(size=5, pen=None)
        self.status_scatter = pg.ScatterPlotItem(size=6, pen=None)
        p["rssi"].addItem(self.rssi_scatter)
        p["snr"].addItem(self.snr_scatter)
        p["status"].addItem(self.status_scatter)
        self.per_curve = p["error"].plot(pen=pg.mkPen("#c62828", width=2), name="PER")
        self.ber_curve = p["error"].plot(pen=pg.mkPen("#1565c0", width=2), name="BER")
        self.thr_curve = p["throughput"].plot(pen=pg.mkPen("#2e7d32", width=2))
        self.lat_curve = p["latency"].plot(pen=pg.mkPen("#6d4c41", width=2))
        self.tx_scatter = pg.ScatterPlotItem(size=10, brush=pg.mkBrush("#1565c0"), symbol="o")
        self.rx_scatter = pg.ScatterPlotItem(size=14, brush=pg.mkBrush("#c62828"), symbol="t1")
        p["positions"].addItem(self.tx_scatter)
        p["positions"].addItem(self.rx_scatter)
        self._trail_items: dict[str, pg.PlotDataItem] = {}
        self._labels: dict[str, pg.TextItem] = {}
        self.trails: dict[str, deque] = defaultdict(lambda: deque(maxlen=TRAIL_POINTS))

        self.grid = QGridLayout()
        lay = QVBoxLayout(self)
        lay.addLayout(toggles)
        lay.addLayout(self.grid, 1)
        self._relayout()

    def _relayout(self) -> None:
        for w in self.plots.values():
            self.grid.removeWidget(w)
            w.setVisible(False)
        visible = [k for k in self.PLOTS if self.toggles[k].isChecked()]
        for i, k in enumerate(visible):
            self.grid.addWidget(self.plots[k], i // 2, i % 2)
            self.plots[k].setVisible(True)

    def visible_plots(self) -> list[str]:
        return [k for k in self.PLOTS if self.toggles[k].isChecked()]

    def clear(self) -> None:
        for item in (self.rssi_scatter, self.snr_scatter, self.status_scatter, self.tx_scatter, self.rx_scatter):
            item.clear()
        for c in (self.per_curve, self.ber_curve, self.thr_curve, self.lat_curve):
            c.setData([], [])
        for item in list(self._trail_items.values()) + list(self._labels.values()):
            self.plots["positions"].removeItem(item)
        self._trail_items.clear()
        self._labels.clear()
        self.trails.clear()

    def update_records(self, records: list[PacketRecord]) -> None:
        if not records:
            return
        recent = records[-MAX_SCATTER_POINTS:]
        t = np.array([r.time_s for r in recent])
        brushes = [pg.mkBrush(STATUS_COLORS[r.status]) for r in recent]
        if self.toggles["rssi"].isChecked():
            self.rssi_scatter.setData(t, [r.rssi_dbm for r in recent], brush=brushes)
        if self.toggles["snr"].isChecked():
            snr = [r.snr_db if math.isfinite(r.snr_db) else np.nan for r in recent]
            keep = ~np.isnan(snr)
            self.snr_scatter.setData(t[keep], np.array(snr)[keep], brush=[b for b, k in zip(brushes, keep) if k])
        if self.toggles["status"].isChecked():
            self.status_scatter.setData(t, [STATUS_ORDER.index(r.status) for r in recent], brush=brushes)
        if any(self.toggles[k].isChecked() for k in ("error", "throughput", "latency")):
            ts = windowed(records)
            self.per_curve.setData(ts.t, np.nan_to_num(ts.per), connect="finite")
            self.ber_curve.setData(ts.t, np.nan_to_num(ts.ber), connect="finite")
            self.thr_curve.setData(ts.t, ts.throughput_bps)
            self.lat_curve.setData(ts.t, np.nan_to_num(ts.latency_s * 1e3), connect="finite")

    def show_trajectories(self, trajectories: dict[str, tuple[str, list[tuple[float, float]]]]) -> None:
        """Simülasyon sonunda tüm yolu çizer (hızlandırılmış modda canlı örnekleme seyrek kalır)."""
        for dev_id, (_, pts) in trajectories.items():
            if len(pts) > 1:
                self.trails[dev_id] = deque(pts, maxlen=max(TRAIL_POINTS, len(pts)))
        final = {d: (role, *pts[-1]) for d, (role, pts) in trajectories.items()}
        self.update_positions(final)

    def update_positions(self, positions: dict[str, tuple[str, float, float]]) -> None:
        plot = self.plots["positions"]
        tx, rx = [], []
        for dev_id, (role, x, y) in positions.items():
            (rx if role == "rx" else tx).append((x, y))
            trail = self.trails[dev_id]
            if not trail or trail[-1] != (x, y):
                trail.append((x, y))
            if len(trail) > 1:
                if dev_id not in self._trail_items:
                    color = "#c62828" if role == "rx" else "#1565c0"
                    self._trail_items[dev_id] = plot.plot(pen=pg.mkPen(color, width=1, alpha=120))
                xs, ys = zip(*trail)
                self._trail_items[dev_id].setData(xs, ys)
            if dev_id not in self._labels:
                label = pg.TextItem(dev_id, color="k", anchor=(-0.1, 1.1))
                plot.addItem(label)
                self._labels[dev_id] = label
            self._labels[dev_id].setPos(x, y)
        self.tx_scatter.setData(*zip(*tx)) if tx else self.tx_scatter.clear()
        self.rx_scatter.setData(*zip(*rx)) if rx else self.rx_scatter.clear()


class AnalysisPlot(pg.PlotWidget):
    """Tarama ve karşılaştırma sonuçları: kategorik eksende çubuk, sayısal eksende çizgi."""

    def __init__(self):
        super().__init__()
        self.showGrid(x=True, y=True, alpha=0.3)
        self.addLegend()

    def show_rows(self, rows: list[dict], kind: str) -> None:
        self.clear()
        self.getAxis("bottom").setTicks(None)
        self.setLogMode(x=False, y=False)
        if not rows:
            return
        if kind == "models":
            x = [r["snr_db"] for r in rows]
            self.setLogMode(y=True)
            self.plot(x, [max(r["per_link_level"], 1e-3) for r in rows], pen=pg.mkPen("#1565c0", width=2),
                      symbol="o", name="PER link-level")
            self.plot(x, [max(r["per_css_phy"], 1e-3) for r in rows], pen=pg.mkPen("#c62828", width=2, style=Qt.PenStyle.DashLine),
                      symbol="s", name="PER CSS")
            self.setLabel("bottom", "SNR (dB)")
            self.setLabel("left", "PER")
            return
        y = [r["success_rate"] or 0.0 for r in rows]
        if kind == "environment":
            labels = dict(ENV_LABELS)
            xs = list(range(len(rows)))
            self.addItem(pg.BarGraphItem(x=xs, height=y, width=0.6, brush="#1565c0"))
            self.getAxis("bottom").setTicks([[(i, labels.get(r["value"], str(r["value"]))) for i, r in enumerate(rows)]])
            self.setLabel("bottom", "Ortam")
        else:
            x = [float(r["value"]) for r in rows]
            if kind in ("distance", "range"):
                self.setLogMode(x=True)
            self.plot(x, y, pen=pg.mkPen("#1565c0", width=2), symbol="o", name="Başarı oranı")
            self.setLabel("bottom", {"distance": "Mesafe (m)", "range": "Mesafe (m)", "power": "Gönderim gücü (dBm)",
                                     "sf": "SF"}[kind])
        self.setLabel("left", "Başarı oranı")
        self.setYRange(0, 1.05)
