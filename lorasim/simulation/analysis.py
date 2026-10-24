"""Parametre taramaları ve ortam karşılaştırması (hızlandırılmış modda toplu çalıştırma).

Tüm noktalar aynı seed ile çalıştırılır (ortak rastgele sayılar), böylece noktalar
arasındaki fark yalnızca taranan parametreden gelir.
"""

from __future__ import annotations

import copy
import math
import secrets
from typing import Callable, Iterable, Optional

import numpy as np

from lorasim.config import ENVIRONMENTS, ConfigError, SimConfig
from lorasim.lora import sx1276_config as hw
from lorasim.simulation.simulation_engine import SimulationEngine

SWEEPS = {
    "distance": ("topology.distance_m", "Mesafe (m)"),
    "power": ("lora.tx_power_dbm", "Gönderim gücü (dBm)"),
    "sf": ("lora.spreading_factor", "Spreading Factor"),
    "environment": ("channel.environment", "Ortam"),
}

ROW_KEYS = ("success_rate", "per", "packet_loss_rate", "ber", "mean_rssi_dbm", "mean_snr_db", "throughput_bps",
            "mean_latency_s", "retransmissions", "energy_per_delivered_packet_mj", "packets_generated")

Progress = Callable[[int, int], None]


def default_values(kind: str, config: SimConfig) -> list:
    if kind == "distance":
        return [float(round(d, 1)) for d in np.geomspace(50, 50_000, 16)]
    if kind == "power":
        return [float(p) for p in range(int(hw.TX_POWER_MIN_DBM), int(hw.TX_POWER_MAX_DBM) + 1, 2)]
    if kind == "sf":
        return list(hw.SPREADING_FACTORS)
    if kind == "environment":
        return list(ENVIRONMENTS)
    raise ValueError(kind)


def _set(config: SimConfig, path: str, value) -> None:
    section, name = path.split(".")
    setattr(getattr(config, section), name, value)


def run_sweep(base: SimConfig, kind: str, values: Optional[Iterable] = None, packets: int = 200,
              progress: Optional[Progress] = None, should_stop: Optional[Callable[[], bool]] = None) -> list[dict]:
    """Her değer için bir simülasyon çalıştırır ve özet metrikleri satır olarak döndürür."""
    if kind not in SWEEPS:
        raise ConfigError([f"Bilinmeyen tarama: {kind}. Seçenekler: {', '.join(SWEEPS)}."])
    if kind == "distance" and base.topology.mode != "distance":
        raise ConfigError(["Mesafe taraması yalnızca 'distance' konumlandırma modunda yapılabilir."])
    path, _ = SWEEPS[kind]
    values = list(values) if values is not None else default_values(kind, base)
    seed = base.run.seed if base.run.seed is not None else secrets.randbits(32)
    rows = []
    for i, v in enumerate(values):
        if should_stop and should_stop():
            break
        cfg = copy.deepcopy(base)
        cfg.run.mode, cfg.run.seed = "accelerated", seed
        cfg.traffic.duration_s = None
        cfg.traffic.max_packets = packets
        _set(cfg, path, v)
        summary = SimulationEngine(cfg).run()
        row = {"parameter": kind, "value": v, "seed": seed}
        row.update({k: summary[k] for k in ROW_KEYS})
        rows.append(row)
        if progress:
            progress(i + 1, len(values))
    return rows


def environment_comparison(base: SimConfig, environments: Optional[Iterable[str]] = None, packets: int = 200,
                           progress: Optional[Progress] = None, should_stop=None) -> list[dict]:
    return run_sweep(base, "environment", environments, packets, progress, should_stop)


def max_range_m(rows: list[dict], threshold: float = 0.9) -> Optional[float]:
    """Başarı oranının `threshold` altına ilk düştüğü noktayı log-mesafede ara değerler.

    Tüm noktalar eşiğin üstündeyse en büyük mesafe, ilk nokta bile altındaysa None döner.
    """
    pts = sorted((r["value"], r["success_rate"] or 0.0) for r in rows)
    if not pts or pts[0][1] < threshold:
        return None
    for (d0, s0), (d1, s1) in zip(pts, pts[1:]):
        if s1 < threshold <= s0:
            frac = (s0 - threshold) / (s0 - s1)
            return float(math.exp(math.log(d0) + frac * (math.log(d1) - math.log(d0))))
    return float(pts[-1][0])


def find_max_range(base: SimConfig, threshold: float = 0.9, packets: int = 200, points: int = 24,
                   lo_m: float = 10.0, hi_m: float = 1e6, progress: Optional[Progress] = None,
                   should_stop=None) -> tuple[Optional[float], list[dict]]:
    """Başarılı haberleşme mesafesi: başarı oranının eşiği sağladığı en büyük mesafe."""
    coarse = run_sweep(base, "distance", np.geomspace(lo_m, hi_m, points), packets, progress, should_stop)
    estimate = max_range_m(coarse, threshold)
    if estimate is None or estimate >= hi_m:
        return estimate, coarse
    # Eşik çevresinde daha sık ikinci geçiş
    fine = run_sweep(base, "distance", np.geomspace(estimate / 1.6, estimate * 1.6, 12), packets, None, should_stop)
    rows = sorted(coarse + fine, key=lambda r: r["value"])
    return max_range_m(rows, threshold), rows


def compare_models(base: SimConfig, snrs_db: Optional[Iterable[float]] = None, packets: int = 200,
                   progress: Optional[Progress] = None, should_stop=None) -> list[dict]:
    """Aynı SNR değerlerinde link-level ve CSS modellerinin PER/SER değerleri.

    Modeller doğrudan (motor olmadan) çağrılır; algılama eşiğinin üstünde, yalnızca
    AWGN altında karşılaştırma yapılır.
    """
    from lorasim.lora.error_model import symbol_error_rate
    from lorasim.simulation.css_phy_model import CssPhyModel
    from lorasim.simulation.link_level_model import LinkLevelModel, RxStatus
    from lorasim.simulation.packet_manager import PacketFactory
    from lorasim.lora.lora_parameters import LoRaPhy

    base.validate()
    phy = LoRaPhy.from_config(base.lora)
    req = hw.SNR_REQUIRED_DB[phy.sf]
    snrs = list(snrs_db) if snrs_db is not None else [req + d for d in np.arange(-5.0, 2.01, 0.5)]
    seed = base.run.seed if base.run.seed is not None else secrets.randbits(32)
    models = {
        "link_level": LinkLevelModel(phy, -1e9, None),
        "css_phy": CssPhyModel(phy, -1e9, None, base.lora.sync_word, base.lora.iq_inverted),
    }
    rows = []
    for i, snr in enumerate(snrs):
        if should_stop and should_stop():
            break
        row = {"snr_db": float(snr), "ser_theory": symbol_error_rate(phy.sf, snr)}
        for name, m in models.items():
            rng = np.random.default_rng(seed)
            m.rng = rng
            f = PacketFactory("TX", "RX", base.lora.payload_bytes, base.lora.crc_enabled, rng)
            res = [m.receive(f.create(0).frame, 0.0, snr) for _ in range(packets)]
            row[f"per_{name}"] = float(np.mean([r.status != RxStatus.OK for r in res]))
            sym = sum(r.symbols_compared for r in res)
            row[f"ser_{name}"] = sum(r.symbol_errors for r in res) / sym if sym else None
            bits = sum(r.bits_compared for r in res)
            row[f"ber_{name}"] = sum(r.bit_errors for r in res) / bits if bits else None
        rows.append(row)
        if progress:
            progress(i + 1, len(snrs))
    return rows
