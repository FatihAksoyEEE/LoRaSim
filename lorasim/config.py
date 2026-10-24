"""Simülasyon yapılandırma sınıfları, doğrulama ve JSON dönüşümü."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Optional

from lorasim.lora import sx1276_config as hw

ENVIRONMENTS = ("free_space", "open_area", "rural", "urban", "dense_urban", "indoor")
PATH_LOSS_MODELS = ("free_space", "log_distance")
FADING_MODELS = ("none", "rayleigh", "rician")
SHADOWING_MODES = ("off", "per_link", "per_packet")
SIM_MODELS = ("link_level", "css_phy")
RUN_MODES = ("realtime", "accelerated")
DUTY_CYCLE_POLICIES = ("warn", "enforce")
POSITIONING_MODES = ("distance", "cartesian", "random")
DEVICE_ROLES = ("tx", "rx")
MOVING_GROUPS = ("none", "transmitters", "receivers", "all")
MOBILITY_MODELS = ("constant", "random_walk", "route", "circular")
INTERFERENCE_TYPES = ("lora", "wideband")


class ConfigError(ValueError):
    """Bir veya daha fazla geçersiz parametreyi kullanıcıya okunur biçimde bildirir."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Geçersiz yapılandırma:\n- " + "\n- ".join(errors))


@dataclass
class LoRaConfig:
    frequency_mhz: float = 868.1
    spreading_factor: int = 7
    bandwidth_khz: float = 125.0
    coding_rate: int = 5  # 4/5 → 5
    tx_power_dbm: float = 14.0
    payload_bytes: int = 20
    crc_enabled: bool = True
    preamble_symbols: int = 8
    implicit_header: bool = False
    sync_word: int = hw.SYNC_WORD_PRIVATE
    iq_inverted: bool = False
    ldro: Optional[bool] = None  # None → sembol süresine göre otomatik

    def validate(self) -> list[str]:
        e = []
        if not hw.FREQ_MIN_MHZ <= self.frequency_mhz <= hw.FREQ_MAX_MHZ:
            e.append(f"Frekans {hw.FREQ_MIN_MHZ:g}–{hw.FREQ_MAX_MHZ:g} MHz aralığında olmalı "
                     f"(girilen: {self.frequency_mhz:g}).")
        if self.spreading_factor not in hw.SPREADING_FACTORS:
            e.append(f"SF 7–12 arasında olmalı (girilen: {self.spreading_factor}).")
        if self.bandwidth_khz not in hw.BANDWIDTHS_KHZ:
            e.append(f"Bant genişliği 125, 250 veya 500 kHz olmalı (girilen: {self.bandwidth_khz:g}).")
        if self.coding_rate not in hw.CODING_RATES:
            e.append(f"Kodlama oranı 4/5–4/8 olmalı (girilen: 4/{self.coding_rate}).")
        if not hw.TX_POWER_MIN_DBM <= self.tx_power_dbm <= hw.TX_POWER_MAX_DBM:
            e.append(f"Gönderim gücü {hw.TX_POWER_MIN_DBM:g}–{hw.TX_POWER_MAX_DBM:g} dBm aralığında "
                     f"olmalı (girilen: {self.tx_power_dbm:g}).")
        from lorasim.simulation.packet_manager import HEADER_BYTES
        if not HEADER_BYTES <= self.payload_bytes <= hw.PAYLOAD_MAX_BYTES:
            e.append(f"Payload {HEADER_BYTES}–{hw.PAYLOAD_MAX_BYTES} byte olmalı; ilk {HEADER_BYTES} "
                     f"byte paket numarası ve zaman bilgisidir (girilen: {self.payload_bytes}).")
        if not hw.PREAMBLE_MIN_SYMBOLS <= self.preamble_symbols <= hw.PREAMBLE_MAX_SYMBOLS:
            e.append(f"Preamble uzunluğu {hw.PREAMBLE_MIN_SYMBOLS}–{hw.PREAMBLE_MAX_SYMBOLS} sembol "
                     f"olmalı (girilen: {self.preamble_symbols}).")
        if not 0 <= self.sync_word <= 0xFF:
            e.append(f"Sync Word 0x00–0xFF olmalı (girilen: {self.sync_word}).")
        return e


@dataclass
class RadioConfig:
    tx_antenna_gain_dbi: float = 0.0
    rx_antenna_gain_dbi: float = 0.0
    tx_losses_db: float = 0.0  # kablo, konnektör vb.
    rx_losses_db: float = 0.0
    noise_figure_db: float = hw.DEFAULT_NOISE_FIGURE_DB
    sensitivity_override_dbm: Optional[float] = None

    def validate(self) -> list[str]:
        e = []
        if self.tx_losses_db < 0 or self.rx_losses_db < 0:
            e.append("Donanım kayıpları negatif olamaz.")
        if not 0 <= self.noise_figure_db <= 30:
            e.append(f"Gürültü figürü 0–30 dB olmalı (girilen: {self.noise_figure_db:g}).")
        if self.sensitivity_override_dbm is not None and not -160 <= self.sensitivity_override_dbm <= -50:
            e.append(f"Alıcı hassasiyeti -160 ile -50 dBm arasında olmalı "
                     f"(girilen: {self.sensitivity_override_dbm:g}).")
        return e


@dataclass
class ChannelConfig:
    """Ortam profili varsayılanları verir; None olan alanlar profilden alınır."""

    environment: str = "free_space"
    path_loss_model: str = "log_distance"
    path_loss_exponent: Optional[float] = None
    shadowing: str = "per_link"
    shadowing_sigma_db: Optional[float] = None
    fading: Optional[str] = None
    rician_k_db: Optional[float] = None
    awgn_enabled: bool = True
    extra_noise_db: float = 0.0
    multipath_enabled: bool = False  # ortam profilinin gecikme hattı (tapped delay line)
    time_varying: bool = False  # sönümleme/gölgeleme zamana (Doppler) ve konuma bağlı ilintili
    scatterer_doppler_hz: float = 0.5  # sabit cihazlarda çevredeki hareketin yarattığı Doppler yayılımı
    shadowing_decorrelation_m: float = 50.0  # Gudmundson ilinti mesafesi
    doppler_enabled: bool = False  # hareketten kaynaklı Doppler frekans kayması
    frequency_offset_enabled: bool = False  # kristal kaynaklı taşıyıcı frekans kayması
    crystal_ppm: float = 10.0  # cihaz başına ±ppm (düzgün dağılım)
    interference_enabled: bool = False  # simülasyon dışı RF/LoRa girişim kaynağı
    interference_type: str = "lora"
    interference_power_dbm: float = -115.0  # alıcıdaki girişim gücü
    interference_rate_hz: float = 0.5  # Poisson geliş hızı
    interference_sf: int = 7  # lora tipi için
    interference_duration_s: float = 0.05  # wideband tipi için darbe süresi
    collisions_enabled: bool = True
    capture_threshold_db: float = 6.0

    def validate(self) -> list[str]:
        e = []
        if self.environment not in ENVIRONMENTS:
            e.append(f"Bilinmeyen ortam: {self.environment}. Seçenekler: {', '.join(ENVIRONMENTS)}.")
        if self.path_loss_model not in PATH_LOSS_MODELS:
            e.append(f"Bilinmeyen yol kaybı modeli: {self.path_loss_model}.")
        if self.path_loss_exponent is not None and not 1.5 <= self.path_loss_exponent <= 6:
            e.append(f"Yol kaybı üssü 1.5–6 olmalı (girilen: {self.path_loss_exponent:g}).")
        if self.shadowing not in SHADOWING_MODES:
            e.append(f"Bilinmeyen gölgeleme modu: {self.shadowing}.")
        if self.shadowing_sigma_db is not None and not 0 <= self.shadowing_sigma_db <= 20:
            e.append(f"Gölgeleme sapması 0–20 dB olmalı (girilen: {self.shadowing_sigma_db:g}).")
        if self.fading is not None and self.fading not in FADING_MODELS:
            e.append(f"Bilinmeyen sönümleme modeli: {self.fading}.")
        if self.extra_noise_db < 0:
            e.append("Ek gürültü negatif olamaz.")
        if self.scatterer_doppler_hz < 0:
            e.append("Saçıcı Doppler yayılımı negatif olamaz.")
        if self.shadowing_decorrelation_m <= 0:
            e.append("Gölgeleme ilinti mesafesi pozitif olmalı.")
        if not 0 <= self.crystal_ppm <= 100:
            e.append(f"Kristal hatası 0–100 ppm olmalı (girilen: {self.crystal_ppm:g}).")
        if self.interference_type not in INTERFERENCE_TYPES:
            e.append(f"Bilinmeyen girişim tipi: {self.interference_type}.")
        if self.interference_rate_hz < 0:
            e.append("Girişim geliş hızı negatif olamaz.")
        if self.interference_sf not in hw.SPREADING_FACTORS:
            e.append(f"Girişim SF'si 7–12 olmalı (girilen: {self.interference_sf}).")
        if self.interference_duration_s <= 0:
            e.append("Girişim darbe süresi pozitif olmalı.")
        if not 0 <= self.capture_threshold_db <= 30:
            e.append(f"Capture eşiği 0–30 dB olmalı (girilen: {self.capture_threshold_db:g}).")
        return e


@dataclass
class DeviceSpec:
    """Kartezyen modda tek bir cihaz. Hareket alanları None ise MobilityConfig kullanılır."""

    id: str
    role: str  # "tx" | "rx"
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    target: Optional[str] = None  # yalnızca verici: hedef alıcı; None → en yakın alıcı
    speed_mps: Optional[float] = None  # kullanıcı tanımlı hız
    heading_deg: Optional[float] = None  # kullanıcı tanımlı yön (0° = +x, saat yönü tersine)
    route: Optional[list] = None  # [[x, y], ...] mutlak rota noktaları
    frequency_offset_ppm: Optional[float] = None  # None → rastgele kristal hatası


@dataclass
class TopologyConfig:
    """Konumlandırma.

    distance: tek alıcı orijinde, vericiler ona `distance_m` uzaklıkta bir çember üzerinde.
    cartesian: `devices` listesindeki koordinatlar.
    random: cihazlar `area_width_m` × `area_height_m` alanına düzgün dağılır.
    """

    mode: str = "distance"
    distance_m: float = 1000.0
    num_transmitters: int = 1
    num_receivers: int = 1
    area_width_m: float = 2000.0
    area_height_m: float = 2000.0
    devices: list = field(default_factory=list)

    def __post_init__(self):
        self.devices = [d if isinstance(d, DeviceSpec) else DeviceSpec(**d) for d in self.devices]

    def validate(self) -> list[str]:
        e = []
        if self.mode not in POSITIONING_MODES:
            e.append(f"Bilinmeyen konumlandırma modu: {self.mode}. Seçenekler: {', '.join(POSITIONING_MODES)}.")
        if not 1.0 <= self.distance_m <= 1e6:
            e.append(f"Mesafe 1 m – 1000 km arasında olmalı (girilen: {self.distance_m:g}).")
        if not 1 <= self.num_transmitters <= 500:
            e.append(f"Verici sayısı 1–500 olmalı (girilen: {self.num_transmitters}).")
        if not 1 <= self.num_receivers <= 100:
            e.append(f"Alıcı sayısı 1–100 olmalı (girilen: {self.num_receivers}).")
        if self.mode == "distance" and self.num_receivers != 1:
            e.append("Mesafe modunda yalnızca bir alıcı olabilir; birden fazla alıcı için kartezyen veya "
                     "rastgele konumlandırma seçin.")
        if self.area_width_m <= 0 or self.area_height_m <= 0:
            e.append("Alan boyutları pozitif olmalı.")
        if self.mode == "cartesian":
            ids = [d.id for d in self.devices]
            if len(set(ids)) != len(ids):
                e.append("Cihaz kimlikleri benzersiz olmalı.")
            if any(d.role not in DEVICE_ROLES for d in self.devices):
                e.append("Cihaz rolü 'tx' veya 'rx' olmalı.")
            rx_ids = {d.id for d in self.devices if d.role == "rx"}
            if not any(d.role == "tx" for d in self.devices) or not rx_ids:
                e.append("Kartezyen modda en az bir verici ve bir alıcı tanımlanmalı.")
            for d in self.devices:
                if d.target is not None and d.target not in rx_ids:
                    e.append(f"{d.id} için hedef alıcı bulunamadı: {d.target}.")
                if d.route is not None and (len(d.route) < 1 or any(len(p) != 2 for p in d.route)):
                    e.append(f"{d.id} rotası [[x, y], ...] biçiminde olmalı.")
                if d.speed_mps is not None and d.speed_mps < 0:
                    e.append(f"{d.id} hızı negatif olamaz.")
        return e


@dataclass
class MobilityConfig:
    moving: str = "none"  # none | transmitters | receivers | all
    model: str = "constant"
    speed_mps: float = 1.4
    heading_deg: float = 0.0
    random_turn_interval_s: float = 10.0
    route: list = field(default_factory=list)  # [[dx, dy], ...] başlangıç konumuna göre rota
    route_loop: bool = True
    circle_radius_m: float = 100.0

    def validate(self) -> list[str]:
        e = []
        if self.moving not in MOVING_GROUPS:
            e.append(f"Bilinmeyen hareket grubu: {self.moving}. Seçenekler: {', '.join(MOVING_GROUPS)}.")
        if self.model not in MOBILITY_MODELS:
            e.append(f"Bilinmeyen hareket modeli: {self.model}. Seçenekler: {', '.join(MOBILITY_MODELS)}.")
        if not 0 <= self.speed_mps <= 350:
            e.append(f"Hız 0–350 m/s olmalı (girilen: {self.speed_mps:g}).")
        if self.random_turn_interval_s <= 0:
            e.append("Rastgele yön değiştirme aralığı pozitif olmalı.")
        if self.circle_radius_m <= 0:
            e.append("Dairesel hareket yarıçapı pozitif olmalı.")
        if any(len(p) != 2 for p in self.route):
            e.append("Rota [[dx, dy], ...] biçiminde olmalı.")
        if self.moving != "none" and self.model == "route" and not self.route:
            e.append("Rota hareket modeli için en az bir rota noktası girilmeli.")
        return e


@dataclass
class TrafficConfig:
    interval_s: float = 1.0
    max_packets: Optional[int] = None
    duration_s: Optional[float] = None  # yeni paket üretimini sınırlar; yoldaki paketler tamamlanır
    tx_queue_size: int = 16
    duty_cycle_limit: Optional[float] = 0.01  # oran (0.01 = %1); None → kontrol yok
    duty_cycle_policy: str = "warn"  # warn: gönder ve ihlali say, enforce: izin verilene kadar beklet
    random_start: bool = True  # her verici ilk paketini [0, interval) içinde rastgele bir anda gönderir

    def validate(self) -> list[str]:
        e = []
        if self.interval_s <= 0:
            e.append("Paket gönderim aralığı pozitif olmalı.")
        if self.max_packets is not None and self.max_packets < 1:
            e.append("Maksimum paket sayısı en az 1 olmalı.")
        if self.duration_s is not None and self.duration_s <= 0:
            e.append("Süre sınırı pozitif olmalı.")
        if self.tx_queue_size < 1:
            e.append("Gönderim kuyruğu en az 1 paket almalı.")
        if self.duty_cycle_limit is not None and not 0 < self.duty_cycle_limit <= 1:
            e.append(f"Duty-cycle sınırı 0 ile 1 arasında olmalı; ör. %1 için 0.01 "
                     f"(girilen: {self.duty_cycle_limit:g}).")
        if self.duty_cycle_policy not in DUTY_CYCLE_POLICIES:
            e.append(f"Bilinmeyen duty-cycle politikası: {self.duty_cycle_policy}. "
                     f"Seçenekler: {', '.join(DUTY_CYCLE_POLICIES)}.")
        return e


@dataclass
class AckConfig:
    enabled: bool = True
    max_retries: int = 3
    timeout_s: Optional[float] = None  # None → SF/BW/CR/payload'a göre otomatik
    turnaround_s: float = 0.01  # alıcının veri bitişinden ACK gönderimine kadarki gecikmesi
    packet_timeout_s: Optional[float] = None  # paketin ilk üretiminden sonra vazgeçme süresi
    retry_backoff_max_s: float = 1.0  # tekrar gönderimden önce [0, değer] aralığında rastgele bekleme

    def validate(self) -> list[str]:
        e = []
        if not 0 <= self.max_retries <= 255:
            e.append(f"Maksimum tekrar sayısı 0–255 olmalı (girilen: {self.max_retries}).")
        if self.timeout_s is not None and self.timeout_s <= 0:
            e.append("ACK timeout pozitif olmalı.")
        if self.turnaround_s < 0:
            e.append("ACK dönüş gecikmesi negatif olamaz.")
        if self.packet_timeout_s is not None and self.packet_timeout_s <= 0:
            e.append("Paket timeout pozitif olmalı.")
        if self.retry_backoff_max_s < 0:
            e.append("Tekrar gönderim bekleme süresi negatif olamaz.")
        return e


@dataclass
class RunConfig:
    model: str = "link_level"
    mode: str = "realtime"
    speed: float = 1.0  # gerçek zamanlı modda zaman ölçeği
    seed: Optional[int] = None  # None → rastgele seçilir ve sonuçlara yazılır
    max_records: Optional[int] = 200_000  # bellekte tutulan son kayıt sayısı (özet metrikler etkilenmez)

    def validate(self) -> list[str]:
        e = []
        if self.model not in SIM_MODELS:
            e.append(f"Bilinmeyen simülasyon modeli: {self.model}.")
        if self.mode not in RUN_MODES:
            e.append(f"Bilinmeyen çalışma modu: {self.mode}.")
        if self.speed <= 0:
            e.append("Zaman ölçeği pozitif olmalı.")
        if self.seed is not None and self.seed < 0:
            e.append("Seed negatif olamaz.")
        if self.max_records is not None and self.max_records < 1:
            e.append("Bellekte tutulacak kayıt sayısı en az 1 olmalı.")
        return e


@dataclass
class SimConfig:
    lora: LoRaConfig = field(default_factory=LoRaConfig)
    radio: RadioConfig = field(default_factory=RadioConfig)
    channel: ChannelConfig = field(default_factory=ChannelConfig)
    topology: TopologyConfig = field(default_factory=TopologyConfig)
    mobility: MobilityConfig = field(default_factory=MobilityConfig)
    traffic: TrafficConfig = field(default_factory=TrafficConfig)
    ack: AckConfig = field(default_factory=AckConfig)
    run: RunConfig = field(default_factory=RunConfig)

    def validate(self) -> None:
        errors = []
        for f in fields(self):
            errors += getattr(self, f.name).validate()
        if errors:
            raise ConfigError(errors)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimConfig":
        return _from_dict(cls, data)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "SimConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _from_dict(cls, data: dict[str, Any]):
    known = {f.name: f for f in fields(cls)}
    unknown = set(data) - set(known)
    if unknown:
        raise ConfigError([f"{cls.__name__} içinde bilinmeyen alan(lar): {', '.join(sorted(unknown))}."])
    kwargs = {}
    for name, value in data.items():
        default = known[name].default_factory() if callable(known[name].default_factory) else None
        if is_dataclass(default) and isinstance(value, dict):
            kwargs[name] = _from_dict(type(default), value)
        else:
            kwargs[name] = value
    return cls(**kwargs)
