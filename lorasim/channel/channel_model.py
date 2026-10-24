"""Link bütçesi ve iki cihaz arasındaki zamana bağlı kanal.

Alınan güç:
    RSSI = P_tx + G_tx - L_tx + G_rx - L_rx - PL(d) - gölgeleme + sönümleme

Küçük ölçekli sönümleme bir gecikme hattıyla (tapped delay line) modellenir.
Çok yollu yayılım kapalıyken tek tap, açıkken ortam profilinin tapları
kullanılır. LoRa chirp'i tüm bandı taradığı için etkin kazanç, frekans yanıtının
bant üzerindeki ortalama gücüdür: |H(f)|² ortalaması. Gecikme yayılımı arttıkça
bu ortalama frekans çeşitliliği sağlar.

Zamana bağlı kanal (time_varying=True):
- Sönümleme: her tap AR(1) süreci, ρ = J0(2π·fD·Δt) (Jakes),
  fD = saçıcı Doppler'i + cihaz hızlarından gelen azami Doppler.
- Gölgeleme: Gudmundson modeli, ρ = exp(-Δd / d_corr); Δd cihazların aldığı yol.
Kapalıyken her paket bağımsız bir sönümleme örneği alır (blok sönümleme).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from lorasim.channel.doppler import doppler_shift_hz, jakes_correlation, max_doppler_hz
from lorasim.channel.environment import PROFILES
from lorasim.channel.path_loss import free_space_path_loss_db, log_distance_path_loss_db
from lorasim.config import ChannelConfig, LoRaConfig, RadioConfig
from lorasim.lora.sensitivity import noise_floor_dbm

_FREQ_POINTS = 16  # bant içi frekans yanıtı örnek sayısı
MIN_DISTANCE_M = 1.0


@dataclass(frozen=True)
class ResolvedChannel:
    """Ortam profili ile kullanıcı değerleri birleştirilmiş kanal parametreleri."""

    environment: str
    path_loss_model: str
    path_loss_exponent: float
    shadowing: str
    shadowing_sigma_db: float
    fading: str
    rician_k_db: float
    awgn_enabled: bool
    extra_noise_db: float
    multipath_enabled: bool
    multipath_taps: tuple
    time_varying: bool
    scatterer_doppler_hz: float
    shadowing_decorrelation_m: float
    doppler_enabled: bool
    frequency_offset_enabled: bool
    crystal_ppm: float
    interference_enabled: bool
    interference_type: str
    interference_power_dbm: float
    interference_rate_hz: float
    interference_sf: int
    interference_duration_s: float
    collisions_enabled: bool
    capture_threshold_db: float

    @classmethod
    def from_config(cls, cfg: ChannelConfig) -> "ResolvedChannel":
        p = PROFILES[cfg.environment]
        pick = lambda v, d: d if v is None else v  # noqa: E731
        return cls(
            environment=cfg.environment,
            path_loss_model=cfg.path_loss_model,
            path_loss_exponent=2.0 if cfg.path_loss_model == "free_space"
            else pick(cfg.path_loss_exponent, p.path_loss_exponent),
            shadowing=cfg.shadowing,
            shadowing_sigma_db=pick(cfg.shadowing_sigma_db, p.shadowing_sigma_db),
            fading=pick(cfg.fading, p.fading),
            rician_k_db=pick(cfg.rician_k_db, p.rician_k_db),
            awgn_enabled=cfg.awgn_enabled,
            extra_noise_db=cfg.extra_noise_db,
            multipath_enabled=cfg.multipath_enabled,
            multipath_taps=tuple(tuple(map(float, tap)) for tap in p.multipath_taps),
            time_varying=cfg.time_varying,
            scatterer_doppler_hz=cfg.scatterer_doppler_hz,
            shadowing_decorrelation_m=cfg.shadowing_decorrelation_m,
            doppler_enabled=cfg.doppler_enabled,
            frequency_offset_enabled=cfg.frequency_offset_enabled,
            crystal_ppm=cfg.crystal_ppm,
            interference_enabled=cfg.interference_enabled,
            interference_type=cfg.interference_type,
            interference_power_dbm=cfg.interference_power_dbm,
            interference_rate_hz=cfg.interference_rate_hz,
            interference_sf=cfg.interference_sf,
            interference_duration_s=cfg.interference_duration_s,
            collisions_enabled=cfg.collisions_enabled,
            capture_threshold_db=cfg.capture_threshold_db,
        )

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass(frozen=True)
class LinkSample:
    path_loss_db: float
    shadowing_db: float
    fading_db: float
    rssi_dbm: float
    noise_dbm: float
    distance_m: float = 0.0
    doppler_hz: float = 0.0

    @property
    def snr_db(self) -> float:
        return self.rssi_dbm - self.noise_dbm


class _Fading:
    """Gecikme hattı tap'larının karmaşık kazançları ve zaman evrimi."""

    def __init__(self, ch: ResolvedChannel, bandwidth_hz: float, rng: np.random.Generator):
        taps = ch.multipath_taps if ch.multipath_enabled else ((0.0, 0.0),)
        self.delays = np.array([d * 1e-9 for d, _ in taps])
        powers = np.array([10 ** (p / 10) for _, p in taps])
        self.powers = powers / powers.sum()
        self.kind = ch.fading
        k = 10 ** (ch.rician_k_db / 10) if self.kind == "rician" else 0.0
        self.los = np.zeros(len(taps), dtype=complex)
        self.los[0] = math.sqrt(self.powers[0] * k / (k + 1))
        self.scatter_var = self.powers.copy()
        self.scatter_var[0] /= k + 1
        self.rng = rng
        self.active = ch.multipath_enabled or self.kind != "none"
        self.time_varying = ch.time_varying
        f = np.linspace(-bandwidth_hz / 2, bandwidth_hz / 2, _FREQ_POINTS)
        self._steering = np.exp(-2j * np.pi * np.outer(f, self.delays))  # (frekans, tap)
        # "none" + çok yollu: sabit genlikli taplar, rastgele faz; faz dönme hızları tap başına.
        self._angles = rng.uniform(0, 2 * np.pi, len(taps))
        self._h = None
        self._t = None

    def _fresh(self) -> np.ndarray:
        n = len(self.powers)
        if self.kind == "none":
            return np.sqrt(self.powers) * np.exp(1j * self.rng.uniform(0, 2 * np.pi, n))
        w = (self.rng.standard_normal(n) + 1j * self.rng.standard_normal(n)) * np.sqrt(self.scatter_var / 2)
        return w

    def gain_db(self, t: float, max_doppler: float) -> float:
        if not self.active:
            return 0.0
        if not self.time_varying or self._h is None:
            self._h = self._fresh()
        elif t != self._t:
            dt = abs(t - self._t)
            if self.kind == "none":
                self._h = self._h * np.exp(2j * np.pi * max_doppler * dt * np.cos(self._angles))
            else:
                rho = jakes_correlation(max_doppler, dt)
                self._h = rho * self._h + math.sqrt(max(1 - rho * rho, 0.0)) * self._fresh()
        self._t = t
        h = self._h + self.los
        gain = float(np.mean(np.abs(self._steering @ h) ** 2))
        return 10 * math.log10(max(gain, 1e-12))


class Link:
    """İki cihaz arasındaki karşılıklı (reciprocal) kanal: a→b ve b→a aynı örnekleri paylaşır."""

    def __init__(self, dev_a, dev_b, lora: LoRaConfig, radio: RadioConfig, channel: ResolvedChannel,
                 rng: np.random.Generator):
        self.a, self.b = dev_a, dev_b
        self.channel = channel
        self.rng = rng
        self.frequency_hz = lora.frequency_mhz * 1e6
        self.static_gain_db = (lora.tx_power_dbm + radio.tx_antenna_gain_dbi - radio.tx_losses_db
                               + radio.rx_antenna_gain_dbi - radio.rx_losses_db)
        self.noise_dbm = (noise_floor_dbm(lora.bandwidth_khz * 1e3, radio.noise_figure_db, channel.extra_noise_db)
                          if channel.awgn_enabled else -math.inf)
        self._fading = _Fading(channel, lora.bandwidth_khz * 1e3, rng)
        sigma = channel.shadowing_sigma_db
        self._shadow = float(rng.normal(0.0, sigma)) if sigma > 0 and channel.shadowing != "off" else 0.0
        self._shadow_pos = None
        self.moving = dev_a.trajectory.is_moving or dev_b.trajectory.is_moving

    def path_loss_db(self, distance_m: float) -> float:
        ch = self.channel
        if ch.path_loss_model == "free_space":
            return free_space_path_loss_db(distance_m, self.frequency_hz)
        return log_distance_path_loss_db(distance_m, self.frequency_hz, ch.path_loss_exponent)

    def distance_m(self, t: float) -> float:
        return max(float(np.linalg.norm(self.a.position(t) - self.b.position(t))), MIN_DISTANCE_M)

    def _shadowing(self, pa: np.ndarray, pb: np.ndarray) -> float:
        ch = self.channel
        sigma = ch.shadowing_sigma_db
        if ch.shadowing == "off" or sigma == 0:
            return 0.0
        if ch.shadowing == "per_packet":
            return float(self.rng.normal(0.0, sigma))
        if ch.time_varying and self.moving:
            if self._shadow_pos is not None:
                moved = float(np.linalg.norm(pa - self._shadow_pos[0]) + np.linalg.norm(pb - self._shadow_pos[1]))
                if moved > 0:
                    rho = math.exp(-moved / ch.shadowing_decorrelation_m)
                    self._shadow = rho * self._shadow + math.sqrt(1 - rho * rho) * float(self.rng.normal(0.0, sigma))
            self._shadow_pos = (pa, pb)
        return self._shadow

    def sample(self, t: float) -> LinkSample:
        pa, pb = self.a.position(t), self.b.position(t)
        va, vb = self.a.velocity(t), self.b.velocity(t)
        d = max(float(np.linalg.norm(pa - pb)), MIN_DISTANCE_M)
        pl = self.path_loss_db(d)
        shadow = self._shadowing(pa, pb)
        speed = float(np.linalg.norm(va) + np.linalg.norm(vb))
        fd_max = self.channel.scatterer_doppler_hz + max_doppler_hz(speed, self.frequency_hz)
        fade = self._fading.gain_db(t, fd_max)
        doppler = doppler_shift_hz(pa, va, pb, vb, self.frequency_hz) if self.channel.doppler_enabled else 0.0
        rssi = self.static_gain_db - pl - shadow + fade
        return LinkSample(pl, shadow, fade, rssi, self.noise_dbm, d, doppler)
