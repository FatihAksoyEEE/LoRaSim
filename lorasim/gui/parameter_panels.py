"""Parametre panelleri: SimConfig alanlarını bildirimsel bir tanımdan form olarak üretir.

Her alan bir `Field` ile tanımlanır; `ConfigForm.get_config()` formdan SimConfig
üretir, `set_config()` formu bir SimConfig'ten doldurur. Doğrulama SimConfig.validate()
ile yapılır, böylece CLI ve arayüz aynı kuralları ve hata mesajlarını kullanır.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QToolBox, QVBoxLayout, QWidget,
)

from lorasim.config import ConfigError, DeviceSpec, SimConfig
from lorasim.lora import sx1276_config as hw

ENV_LABELS = (("free_space", "Serbest uzay"), ("open_area", "Açık alan"), ("rural", "Kırsal alan"),
              ("urban", "Kentsel alan"), ("dense_urban", "Yoğun kentsel alan"), ("indoor", "Kapalı alan"))


@dataclass(frozen=True)
class Field:
    section: str
    name: str
    label: str
    kind: str  # float | int | bool | choice | hex | route
    minimum: float = 0.0
    maximum: float = 1e9
    step: float = 1.0
    decimals: int = 2
    suffix: str = ""
    choices: tuple = ()  # (değer, etiket)
    optional: str = ""  # boş değilse alan None olabilir; bu metin None anlamına gelen onay kutusudur
    scale: float = 1.0  # gösterilen = değer × scale (ör. oran → yüzde)
    tooltip: str = ""


F = Field
PANELS: list[tuple[str, list[Field]]] = [
    ("LoRa ayarları", [
        F("lora", "frequency_mhz", "Frekans", "float", hw.FREQ_MIN_MHZ, hw.FREQ_MAX_MHZ, 0.1, 3, " MHz"),
        F("lora", "spreading_factor", "Spreading Factor", "choice",
          choices=tuple((sf, f"SF{sf}") for sf in hw.SPREADING_FACTORS)),
        F("lora", "bandwidth_khz", "Bant genişliği", "choice", choices=tuple((b, f"{b:g} kHz") for b in hw.BANDWIDTHS_KHZ)),
        F("lora", "coding_rate", "Kodlama oranı", "choice", choices=tuple((c, f"4/{c}") for c in hw.CODING_RATES)),
        F("lora", "tx_power_dbm", "Gönderim gücü", "float", hw.TX_POWER_MIN_DBM, hw.TX_POWER_MAX_DBM, 1, 1, " dBm"),
        F("lora", "payload_bytes", "Payload uzunluğu", "int", 6, hw.PAYLOAD_MAX_BYTES, 1, suffix=" byte",
          tooltip="İlk 6 byte paket numarası ve zaman bilgisidir."),
        F("lora", "crc_enabled", "CRC", "bool"),
    ]),
    ("Gelişmiş paket ve donanım", [
        F("lora", "preamble_symbols", "Preamble uzunluğu", "int", hw.PREAMBLE_MIN_SYMBOLS, 1000, 1, suffix=" sembol"),
        F("lora", "implicit_header", "Implicit header", "bool"),
        F("lora", "sync_word", "Sync Word", "hex", 0, 255),
        F("lora", "iq_inverted", "IQ inversion", "bool"),
        F("lora", "ldro", "Low Data Rate Opt.", "choice", choices=((None, "Otomatik"), (True, "Açık"), (False, "Kapalı"))),
        F("radio", "tx_antenna_gain_dbi", "Verici anten kazancı", "float", -20, 30, 0.5, 1, " dBi"),
        F("radio", "rx_antenna_gain_dbi", "Alıcı anten kazancı", "float", -20, 30, 0.5, 1, " dBi"),
        F("radio", "tx_losses_db", "Verici kayıpları", "float", 0, 50, 0.5, 1, " dB"),
        F("radio", "rx_losses_db", "Alıcı kayıpları", "float", 0, 50, 0.5, 1, " dB"),
        F("radio", "noise_figure_db", "Gürültü figürü", "float", 0, 30, 0.5, 1, " dB"),
        F("radio", "sensitivity_override_dbm", "Alıcı hassasiyeti", "float", -160, -50, 0.5, 1, " dBm",
          optional="Otomatik hesapla"),
    ]),
    ("Kanal ve ortam", [
        F("channel", "environment", "Ortam", "choice", choices=ENV_LABELS),
        F("channel", "path_loss_model", "Yol kaybı modeli", "choice",
          choices=(("log_distance", "Log-distance"), ("free_space", "Serbest uzay (FSPL)"))),
        F("channel", "path_loss_exponent", "Yol kaybı üssü", "float", 1.5, 6, 0.1, 2, optional="Ortam varsayılanı"),
        F("channel", "shadowing", "Gölgeleme", "choice",
          choices=(("per_link", "Link başına"), ("per_packet", "Paket başına"), ("off", "Kapalı"))),
        F("channel", "shadowing_sigma_db", "Gölgeleme σ", "float", 0, 20, 0.5, 1, " dB", optional="Ortam varsayılanı"),
        F("channel", "fading", "Sönümleme", "choice",
          choices=((None, "Ortam varsayılanı"), ("none", "Yok"), ("rayleigh", "Rayleigh"), ("rician", "Rician"))),
        F("channel", "rician_k_db", "Rician K", "float", -10, 30, 0.5, 1, " dB", optional="Ortam varsayılanı"),
        F("channel", "awgn_enabled", "AWGN gürültüsü", "bool"),
        F("channel", "extra_noise_db", "Ek gürültü", "float", 0, 60, 0.5, 1, " dB"),
        F("channel", "multipath_enabled", "Çok yollu yayılım", "bool"),
        F("channel", "time_varying", "Zamana bağlı kanal", "bool"),
        F("channel", "scatterer_doppler_hz", "Saçıcı Doppler", "float", 0, 100, 0.1, 2, " Hz"),
        F("channel", "shadowing_decorrelation_m", "Gölgeleme ilinti mesafesi", "float", 1, 10000, 5, 0, " m"),
        F("channel", "doppler_enabled", "Doppler kayması", "bool"),
        F("channel", "frequency_offset_enabled", "Kristal frekans kayması", "bool"),
        F("channel", "crystal_ppm", "Kristal hatası (±)", "float", 0, 100, 1, 1, " ppm"),
        F("channel", "collisions_enabled", "Paket çakışmaları", "bool"),
        F("channel", "capture_threshold_db", "Capture eşiği", "float", 0, 30, 0.5, 1, " dB"),
        F("channel", "interference_enabled", "Harici girişim", "bool"),
        F("channel", "interference_type", "Girişim tipi", "choice", choices=(("lora", "LoRa"), ("wideband", "Geniş bant"))),
        F("channel", "interference_power_dbm", "Girişim gücü", "float", -160, 0, 1, 1, " dBm"),
        F("channel", "interference_rate_hz", "Girişim hızı", "float", 0, 100, 0.1, 2, " /s"),
        F("channel", "interference_sf", "Girişim SF", "choice", choices=tuple((sf, f"SF{sf}") for sf in hw.SPREADING_FACTORS)),
        F("channel", "interference_duration_s", "Girişim darbe süresi", "float", 0.001, 60, 0.01, 3, " s"),
    ]),
    ("Cihazlar ve hareket", [
        F("topology", "mode", "Konumlandırma", "choice",
          choices=(("distance", "Mesafe"), ("cartesian", "Kartezyen koordinat"), ("random", "Rastgele"))),
        F("topology", "distance_m", "Verici–alıcı mesafesi", "float", 1, 1e6, 10, 1, " m"),
        F("topology", "num_transmitters", "Verici sayısı", "int", 1, 500),
        F("topology", "num_receivers", "Alıcı sayısı", "int", 1, 100),
        F("topology", "area_width_m", "Alan genişliği", "float", 1, 1e6, 100, 0, " m"),
        F("topology", "area_height_m", "Alan yüksekliği", "float", 1, 1e6, 100, 0, " m"),
        F("mobility", "moving", "Hareketli cihazlar", "choice",
          choices=(("none", "Tümü sabit"), ("transmitters", "Yalnızca vericiler"), ("receivers", "Yalnızca alıcılar"),
                   ("all", "Verici ve alıcılar"))),
        F("mobility", "model", "Hareket modeli", "choice",
          choices=(("constant", "Sabit hız ve yön"), ("random_walk", "Rastgele hareket"), ("route", "Önceden tanımlı rota"),
                   ("circular", "Dairesel"))),
        F("mobility", "speed_mps", "Hız", "float", 0, 350, 0.5, 2, " m/s"),
        F("mobility", "heading_deg", "Yön", "float", -360, 360, 5, 1, "°"),
        F("mobility", "random_turn_interval_s", "Yön değiştirme aralığı", "float", 0.1, 3600, 1, 1, " s"),
        F("mobility", "circle_radius_m", "Çember yarıçapı", "float", 1, 1e5, 10, 1, " m"),
        F("mobility", "route", "Rota (dx,dy; ...)", "route"),
        F("mobility", "route_loop", "Rotayı tekrarla", "bool"),
    ]),
    ("ACK ve trafik", [
        F("traffic", "interval_s", "Paket gönderim aralığı", "float", 0.001, 86400, 0.1, 3, " s"),
        F("traffic", "random_start", "Rastgele başlangıç", "bool"),
        F("traffic", "tx_queue_size", "Gönderim kuyruğu", "int", 1, 10000, suffix=" paket"),
        F("traffic", "duty_cycle_limit", "Duty-cycle sınırı", "float", 0.01, 100, 0.1, 2, " %",
          optional="Kontrol yok", scale=100.0),
        F("traffic", "duty_cycle_policy", "Duty-cycle politikası", "choice",
          choices=(("warn", "Uyar (ihlali say)"), ("enforce", "Uygula (beklet)"))),
        F("traffic", "max_packets", "Maks. paket (verici başına)", "int", 1, 10**9, optional="Sınırsız"),
        F("traffic", "duration_s", "Süre sınırı", "float", 0.001, 1e9, 10, 1, " s", optional="Sınırsız"),
        F("ack", "enabled", "ACK kullan", "bool"),
        F("ack", "max_retries", "Maks. tekrar gönderim", "int", 0, 255),
        F("ack", "timeout_s", "ACK timeout", "float", 0.001, 600, 0.01, 3, " s", optional="Otomatik"),
        F("ack", "turnaround_s", "ACK dönüş gecikmesi", "float", 0, 60, 0.001, 3, " s"),
        F("ack", "packet_timeout_s", "Paket timeout", "float", 0.001, 1e6, 1, 2, " s", optional="Yok"),
        F("ack", "retry_backoff_max_s", "Tekrar bekleme (maks.)", "float", 0, 600, 0.1, 2, " s"),
    ]),
    ("Simülasyon", [
        F("run", "model", "Model", "choice", choices=(("link_level", "Link-level"), ("css_phy", "CSS fiziksel katman"))),
        F("run", "mode", "Çalışma modu", "choice", choices=(("realtime", "Gerçek zamanlı"), ("accelerated", "Hızlandırılmış"))),
        F("run", "speed", "Zaman ölçeği", "float", 0.01, 10000, 1, 2, "×"),
        F("run", "seed", "Seed", "int", 0, 2**31 - 1, optional="Rastgele"),
        F("run", "max_records", "Bellekte tutulan kayıt", "int", 100, 10**8, 1000, optional="Sınırsız"),
    ]),
]


def _route_text(route) -> str:
    return "; ".join(f"{x:g},{y:g}" for x, y in route)


def _parse_route(text: str) -> list:
    pts = []
    for part in filter(None, (p.strip() for p in text.split(";"))):
        try:
            x, y = (float(v) for v in part.split(","))
        except ValueError:
            raise ConfigError([f"Rota noktası okunamadı: '{part}'. Biçim: 'x,y; x,y'."])
        pts.append([x, y])
    return pts


class _OptionalWidget(QWidget):
    """Sayı kutusu + 'None' anlamına gelen onay kutusu."""

    def __init__(self, spin, label: str):
        super().__init__()
        self.spin = spin
        self.none_box = QCheckBox(label)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(spin, 1)
        lay.addWidget(self.none_box)
        self.none_box.toggled.connect(lambda on: spin.setEnabled(not on))


class DeviceTable(QWidget):
    """Kartezyen konumlandırma için cihaz listesi."""

    COLUMNS = ("Kimlik", "Rol (tx/rx)", "x (m)", "y (m)", "Hedef alıcı", "Hız (m/s)", "Yön (°)")

    def __init__(self):
        super().__init__()
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(160)
        add_tx, add_rx, remove = QPushButton("Verici ekle"), QPushButton("Alıcı ekle"), QPushButton("Seçiliyi sil")
        add_tx.clicked.connect(lambda: self.add_device("tx"))
        add_rx.clicked.connect(lambda: self.add_device("rx"))
        remove.clicked.connect(self.remove_selected)
        buttons = QHBoxLayout()
        for b in (add_tx, add_rx, remove):
            buttons.addWidget(b)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("Kartezyen modda kullanılan cihazlar (boş hücre = varsayılan):"))
        lay.addWidget(self.table)
        lay.addLayout(buttons)

    def add_device(self, role: str, spec: Optional[DeviceSpec] = None) -> None:
        if spec is None:
            n = sum(1 for r in range(self.table.rowCount()) if self._text(r, 1) == role) + 1
            spec = DeviceSpec(f"{role.upper()}{n}", role, 100.0 * self.table.rowCount(), 0.0)
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = (spec.id, spec.role, f"{spec.x:g}", f"{spec.y:g}", spec.target or "",
                  "" if spec.speed_mps is None else f"{spec.speed_mps:g}",
                  "" if spec.heading_deg is None else f"{spec.heading_deg:g}")
        for c, v in enumerate(values):
            self.table.setItem(row, c, QTableWidgetItem(v))

    def remove_selected(self) -> None:
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)

    def _text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def devices(self) -> list[DeviceSpec]:
        out, errors = [], []
        for r in range(self.table.rowCount()):
            def num(col, default=None):
                t = self._text(r, col)
                if not t:
                    return default
                try:
                    return float(t)
                except ValueError:
                    errors.append(f"Cihaz tablosu satır {r + 1}: '{t}' sayı değil.")
                    return default
            out.append(DeviceSpec(self._text(r, 0), self._text(r, 1).lower(), num(2, 0.0), num(3, 0.0),
                                  target=self._text(r, 4) or None, speed_mps=num(5), heading_deg=num(6)))
        if errors:
            raise ConfigError(errors)
        return out

    def set_devices(self, devices: list[DeviceSpec]) -> None:
        self.table.setRowCount(0)
        for d in devices:
            self.add_device(d.role, d)


class ConfigForm(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.widgets: dict[tuple[str, str], tuple[Field, Any]] = {}
        self.toolbox = QToolBox()
        for title, fields in PANELS:
            page = QWidget()
            form = QFormLayout(page)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for f in fields:
                w = self._make(f)
                label = QLabel(f.label)
                if f.tooltip:
                    label.setToolTip(f.tooltip)
                    w.setToolTip(f.tooltip)
                form.addRow(label, w)
                self.widgets[(f.section, f.name)] = (f, w)
            if title == "Cihazlar ve hareket":
                self.device_table = DeviceTable()
                form.addRow(self.device_table)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.toolbox.addItem(scroll, title)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toolbox)
        self.set_config(SimConfig())

    # --- widget üretimi -------------------------------------------------------
    def _make(self, f: Field):
        if f.kind == "bool":
            w = QCheckBox()
            w.toggled.connect(self.changed)
            return w
        if f.kind == "choice":
            w = QComboBox()
            for value, label in f.choices:
                w.addItem(label, value)
            w.currentIndexChanged.connect(self.changed)
            return w
        if f.kind == "route":
            w = QLineEdit()
            w.setPlaceholderText("ör. 500,0; 500,500; 0,500")
            w.textChanged.connect(self.changed)
            return w
        if f.kind in ("int", "hex"):
            spin = QSpinBox()
            spin.setRange(int(f.minimum), int(min(f.maximum, 2**31 - 1)))
            spin.setSingleStep(int(f.step))
            if f.kind == "hex":
                spin.setDisplayIntegerBase(16)
                spin.setPrefix("0x")
        else:
            spin = QDoubleSpinBox()
            spin.setDecimals(f.decimals)
            spin.setRange(f.minimum, f.maximum)
            spin.setSingleStep(f.step)
        spin.setSuffix(f.suffix)
        spin.setKeyboardTracking(False)
        spin.valueChanged.connect(self.changed)
        if f.optional:
            w = _OptionalWidget(spin, f.optional)
            w.none_box.toggled.connect(self.changed)
            return w
        return spin

    # --- okuma / yazma ------------------------------------------------------
    def _read(self, f: Field, w):
        if f.kind == "bool":
            return w.isChecked()
        if f.kind == "choice":
            return w.currentData()
        if f.kind == "route":
            return _parse_route(w.text())
        if f.optional:
            if w.none_box.isChecked():
                return None
            spin = w.spin
        else:
            spin = w
        v = spin.value()
        if f.kind in ("int", "hex"):
            return int(v)
        return v / f.scale

    def _write(self, f: Field, w, value) -> None:
        w.blockSignals(True)
        try:
            if f.kind == "bool":
                w.setChecked(bool(value))
            elif f.kind == "choice":
                idx = next((i for i in range(w.count()) if w.itemData(i) == value), -1)
                if idx < 0:  # listede olmayan değer (ör. JSON'dan gelen)
                    w.addItem(str(value), value)
                    idx = w.count() - 1
                w.setCurrentIndex(idx)
            elif f.kind == "route":
                w.setText(_route_text(value))
            else:
                spin = w.spin if f.optional else w
                if f.optional:
                    w.none_box.setChecked(value is None)
                if value is not None:
                    spin.setValue(value * f.scale if f.kind == "float" else value)
        finally:
            w.blockSignals(False)

    def get_config(self) -> SimConfig:
        cfg = SimConfig()
        for (section, name), (f, w) in self.widgets.items():
            setattr(getattr(cfg, section), name, self._read(f, w))
        cfg.topology.devices = self.device_table.devices()
        return cfg

    def set_config(self, cfg: SimConfig) -> None:
        for (section, name), (f, w) in self.widgets.items():
            self._write(f, w, getattr(getattr(cfg, section), name))
        self.device_table.set_devices(cfg.topology.devices)
        self.changed.emit()

    def widget(self, section: str, name: str):
        return self.widgets[(section, name)][1]

    def set_value(self, section: str, name: str, value) -> None:
        f, w = self.widgets[(section, name)]
        self._write(f, w, value)
        self.changed.emit()


def default_cartesian_devices() -> list[DeviceSpec]:
    return [DeviceSpec("RX1", "rx", 0, 0), DeviceSpec("TX1", "tx", 1000, 0), DeviceSpec("TX2", "tx", 0, 800)]

