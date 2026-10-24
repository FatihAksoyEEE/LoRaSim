"""Sonuç paneli: özet tablo, verici tablosu, paket logu ve dışa aktarma ayarları."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QTableView, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from lorasim.export.report_exporter import STATUS_LABELS, SUMMARY_FIELDS
from lorasim.metrics.collector import PacketRecord

MAX_LOG_ROWS = 20_000


def fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "evet" if v else "hayır"
    if isinstance(v, float):
        if not math.isfinite(v):
            return "∞" if v > 0 else "—"
        return f"{v:.4g}"
    return str(v)


class SummaryPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.table = QTableWidget(len(SUMMARY_FIELDS) + 3, 2)
        self.table.setHorizontalHeaderLabels(["Metrik", "Değer"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.labels = [label for _, label in SUMMARY_FIELDS] + ["Alım durumları", "ACK durumları", "Paket sonuçları"]
        for i, label in enumerate(self.labels):
            self.table.setItem(i, 0, QTableWidgetItem(label))
            self.table.setItem(i, 1, QTableWidgetItem("—"))
        self.devices = QTableWidget(0, 7)
        self.devices.setHorizontalHeaderLabels(["Verici", "Üretilen", "Başarılı", "Başarı oranı", "Gönderim",
                                                "Çakışma", "Ort. RSSI (dBm)"])
        self.devices.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.devices.verticalHeader().setVisible(False)
        lay = QHBoxLayout(self)
        left, right = QGroupBox("Özet"), QGroupBox("Vericiler")
        QVBoxLayout(left).addWidget(self.table)
        QVBoxLayout(right).addWidget(self.devices)
        lay.addWidget(left, 1)
        lay.addWidget(right, 1)

    def value(self, label: str) -> str:
        return self.table.item(self.labels.index(label), 1).text()

    def show_summary(self, s: dict) -> None:
        values = [s.get(k) for k, _ in SUMMARY_FIELDS]
        counts = lambda d: ", ".join(f"{STATUS_LABELS.get(k, k)}={v}" for k, v in d.items() if v) or "—"  # noqa: E731
        values += [counts(s["status_counts"]), counts(s["ack_counts"]), counts(s["outcome_counts"])]
        for i, v in enumerate(values):
            self.table.item(i, 1).setText(fmt(v))
        devs = s.get("per_device", {})
        self.devices.setRowCount(len(devs))
        for r, (k, d) in enumerate(devs.items()):
            for c, v in enumerate((k, d["generated"], d["delivered"], d["success_rate"], d["transmissions"],
                                   d["collisions"], d["mean_rssi_dbm"])):
                self.devices.setItem(r, c, QTableWidgetItem(fmt(v)))

    def clear(self) -> None:
        for i in range(self.table.rowCount()):
            self.table.item(i, 1).setText("—")
        self.devices.setRowCount(0)


class PacketLogModel(QAbstractTableModel):
    COLUMNS = (("time_s", "Zaman (s)"), ("tx_id", "Verici"), ("rx_id", "Alıcı"), ("seq", "Paket no"),
               ("retransmissions", "Tekrar"), ("status", "Alım durumu"), ("ack_status", "ACK"),
               ("rssi_dbm", "RSSI (dBm)"), ("snr_db", "SNR (dB)"), ("distance_m", "Mesafe (m)"),
               ("bit_errors", "Bit hata"), ("latency_s", "Gecikme (s)"), ("interferers", "Girişim"))

    def __init__(self):
        super().__init__()
        self.rows: list[PacketRecord] = []

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 (Qt adı)
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return len(self.COLUMNS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or not index.isValid():
            return None
        key = self.COLUMNS[index.column()][0]
        v = getattr(self.rows[index.row()], key)
        if key == "status":
            return STATUS_LABELS.get(v, v)
        return fmt(round(v, 4) if isinstance(v, float) and math.isfinite(v) else v)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section][1]
        return None

    def append(self, records: list[PacketRecord]) -> None:
        if not records:
            return
        overflow = len(self.rows) + len(records) - MAX_LOG_ROWS
        if overflow > 0:
            drop = min(overflow, len(self.rows))
            self.beginRemoveRows(QModelIndex(), 0, drop - 1)
            del self.rows[:drop]
            self.endRemoveRows()
            records = records[-MAX_LOG_ROWS:]
        start = len(self.rows)
        self.beginInsertRows(QModelIndex(), start, start + len(records) - 1)
        self.rows.extend(records)
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self.rows.clear()
        self.endResetModel()


class PacketLog(QWidget):
    def __init__(self):
        super().__init__()
        self.model = PacketLogModel()
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.verticalHeader().setVisible(False)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.info = QLabel(f"Son {MAX_LOG_ROWS:,} gönderim gösterilir; tamamı CSV olarak kaydedilebilir.")
        lay = QVBoxLayout(self)
        lay.addWidget(self.info)
        lay.addWidget(self.view)

    def append(self, records: list[PacketRecord]) -> None:
        at_bottom = self.view.verticalScrollBar().value() >= self.view.verticalScrollBar().maximum() - 2
        self.model.append(records)
        if at_bottom:
            self.view.scrollToBottom()


class ExportBar(QGroupBox):
    """Kayıt klasörü ve dosya adı seçimi + dışa aktarma düğmeleri."""

    export_requested = Signal(str)  # "csv" | "json" | "png" | "pdf" | "all"

    def __init__(self):
        super().__init__("Kayıt")
        self.folder = QLineEdit(str(Path.cwd() / "output"))
        self.name = QLineEdit(self.default_name())
        browse = QPushButton("Klasör seç…")
        browse.clicked.connect(self.choose_folder)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Kayıt klasörü:"))
        row1.addWidget(self.folder, 1)
        row1.addWidget(browse)
        row1.addWidget(QLabel("Dosya adı:"))
        row1.addWidget(self.name, 1)
        row2 = QHBoxLayout()
        self.buttons = {}
        for key, label in (("csv", "CSV (paket kayıtları)"), ("json", "JSON (ayarlar + özet)"), ("png", "PNG (grafikler)"),
                           ("pdf", "PDF rapor"), ("all", "Tümünü kaydet")):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, k=key: self.export_requested.emit(k))
            self.buttons[key] = b
            row2.addWidget(b)
        lay = QVBoxLayout(self)
        lay.addLayout(row1)
        lay.addLayout(row2)

    @staticmethod
    def default_name() -> str:
        return f"lorasim_{datetime.now():%Y%m%d_%H%M%S}"

    def choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Kayıt klasörü seç", self.folder.text())
        if path:
            self.folder.setText(path)

    def path_for(self, ext: str) -> Path:
        folder = Path(self.folder.text()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        name = self.name.text().strip() or self.default_name()
        return folder / f"{name}.{ext}"
