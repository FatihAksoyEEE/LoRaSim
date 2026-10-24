"""PNG/PDF grafik ve simülasyon özet raporu (matplotlib, ekransız Agg arka ucu)."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from lorasim import __version__  # noqa: E402
from lorasim.config import SimConfig  # noqa: E402
from lorasim.metrics.collector import PacketRecord  # noqa: E402
from lorasim.metrics.timeseries import windowed  # noqa: E402
from lorasim.simulation.analysis import SWEEPS  # noqa: E402

STATUS_LABELS = {
    "ok": "Başarılı", "crc_error": "CRC hatası", "header_error": "Header hatası", "not_detected": "Algılanmadı",
    "corrupted_undetected": "Fark edilmeyen bozulma", "collision": "Çakışma", "half_duplex": "Half-duplex",
    "freq_offset": "Frekans kayması",
}
STATUS_COLORS = {
    "ok": "#2e7d32", "crc_error": "#ef6c00", "header_error": "#8e24aa", "not_detected": "#9e9e9e",
    "corrupted_undetected": "#c62828", "collision": "#1565c0", "half_duplex": "#6d4c41", "freq_offset": "#00838f",
}
SWEEP_LABELS = {
    "success_rate": "Başarı oranı", "per": "PER", "mean_rssi_dbm": "Ort. RSSI (dBm)", "mean_snr_db": "Ort. SNR (dB)",
    "throughput_bps": "Throughput (bit/s)", "mean_latency_s": "Ort. gecikme (s)",
    "energy_per_delivered_packet_mj": "Enerji / paket (mJ)",
}


def _finish(fig: Figure, path: Optional[str | Path]) -> Figure:
    fig.tight_layout()
    if path is not None:
        fig.savefig(path, dpi=150)
    return fig


def plot_time_series(records: Iterable[PacketRecord], path: Optional[str | Path] = None) -> Figure:
    recs = list(records)
    fig, axes = plt.subplots(3, 2, figsize=(12, 10))
    t = [r.time_s for r in recs]
    ax = axes[0, 0]
    ax.scatter(t, [r.rssi_dbm for r in recs], s=6, c=[STATUS_COLORS[r.status] for r in recs])
    ax.set(title="RSSI – zaman", xlabel="Zaman (s)", ylabel="RSSI (dBm)")
    ax = axes[0, 1]
    ax.scatter(t, [r.snr_db if math.isfinite(r.snr_db) else float("nan") for r in recs], s=6,
               c=[STATUS_COLORS[r.status] for r in recs])
    ax.set(title="SNR – zaman", xlabel="Zaman (s)", ylabel="SNR (dB)")
    ax = axes[1, 0]
    statuses = [s for s in STATUS_LABELS if any(r.status == s for r in recs)]
    for i, s in enumerate(statuses):
        pts = [r.time_s for r in recs if r.status == s]
        ax.scatter(pts, [i] * len(pts), s=8, color=STATUS_COLORS[s])
    ax.set_yticks(range(len(statuses)), [STATUS_LABELS[s] for s in statuses])
    ax.set(title="Paket başarı/hata durumu", xlabel="Zaman (s)")
    ts = windowed(recs)
    ax = axes[1, 1]
    ax.plot(ts.t, ts.per, label="PER", color="#c62828")
    ax.plot(ts.t, ts.ber, label="BER", color="#1565c0")
    ax.set(title="BER/PER – zaman", xlabel="Zaman (s)", ylabel="Oran")
    ax.legend()
    ax = axes[2, 0]
    ax.plot(ts.t, ts.throughput_bps, color="#2e7d32")
    ax.set(title="Throughput – zaman", xlabel="Zaman (s)", ylabel="bit/s")
    ax = axes[2, 1]
    ax.plot(ts.t, ts.latency_s * 1e3, color="#6d4c41")
    ax.set(title="Gecikme – zaman", xlabel="Zaman (s)", ylabel="ms")
    for a in axes.flat:
        a.grid(alpha=0.3)
    return _finish(fig, path)


def plot_positions(trajectories: dict[str, tuple[str, list[tuple[float, float]]]],
                   path: Optional[str | Path] = None) -> Figure:
    """trajectories: cihaz → (rol, [(x, y), ...]) — ilk nokta başlangıç konumudur."""
    fig, ax = plt.subplots(figsize=(7, 7))
    for dev_id, (role, pts) in trajectories.items():
        xs, ys = zip(*pts)
        color = "#c62828" if role == "rx" else "#1565c0"
        if len(pts) > 1:
            ax.plot(xs, ys, color=color, alpha=0.4, lw=1)
        ax.scatter(xs[-1], ys[-1], color=color, marker="^" if role == "rx" else "o", s=60, zorder=3)
        ax.annotate(dev_id, (xs[-1], ys[-1]), textcoords="offset points", xytext=(5, 5), fontsize=8)
    ax.set(title="Cihaz konumları ve hareketleri", xlabel="x (m)", ylabel="y (m)")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(alpha=0.3)
    return _finish(fig, path)


def plot_sweep(rows: list[dict], path: Optional[str | Path] = None,
               metrics: Iterable[str] = ("success_rate", "mean_snr_db", "throughput_bps")) -> Figure:
    metrics = list(metrics)
    kind = rows[0]["parameter"] if rows else "distance"
    xlabel = SWEEPS[kind][1]
    fig, axes = plt.subplots(1, len(metrics), figsize=(5 * len(metrics), 4))
    axes = [axes] if len(metrics) == 1 else axes
    xs = [r["value"] for r in rows]
    categorical = kind == "environment"
    for ax, m in zip(axes, metrics):
        ys = [float("nan") if r[m] is None else r[m] for r in rows]
        if categorical:
            ax.bar(range(len(xs)), ys, color="#1565c0")
            ax.set_xticks(range(len(xs)), xs, rotation=30, ha="right")
        else:
            ax.plot(xs, ys, marker="o", color="#1565c0")
            if kind == "distance":
                ax.set_xscale("log")
        ax.set(xlabel=xlabel, ylabel=SWEEP_LABELS.get(m, m))
        ax.grid(alpha=0.3)
    titles = {"distance": "Mesafe – başarı", "power": "Güç – başarı", "sf": "SF karşılaştırması",
              "environment": "Ortam karşılaştırması"}
    fig.suptitle(titles[kind])
    return _finish(fig, path)


def _fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def _text_page(pdf: PdfPages, title: str, lines: list[str]) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(0.07, 0.95, title, fontsize=16, weight="bold")
    y = 0.91
    for line in lines:
        if y < 0.05:
            pdf.savefig(fig)
            plt.close(fig)
            fig = plt.figure(figsize=(8.27, 11.69))
            y = 0.95
        fig.text(0.07, y, line, fontsize=8.5, family="monospace")
        y -= 0.0165
    pdf.savefig(fig)
    plt.close(fig)


SUMMARY_FIELDS = [
    ("model", "Model"), ("seed", "Seed"), ("num_transmitters", "Verici sayısı"), ("num_receivers", "Alıcı sayısı"),
    ("airtime_s", "Airtime (s)"), ("sensitivity_dbm", "Hassasiyet (dBm)"), ("packets_generated", "Üretilen paket"),
    ("packets_successful", "Başarılı paket"), ("packets_confirmed", "ACK ile onaylanan"),
    ("success_rate", "Başarı oranı"), ("packet_loss_rate", "Paket kayıp oranı"), ("transmissions", "Gönderim"),
    ("retransmissions", "Tekrar gönderim"), ("per", "PER (frame)"), ("ber", "BER"), ("ser", "SER"),
    ("mean_rssi_dbm", "Ort. RSSI (dBm)"), ("mean_snr_db", "Ort. SNR (dB)"), ("ack_success_rate", "ACK başarı oranı"),
    ("throughput_bps", "Throughput (bit/s)"), ("mean_latency_s", "Ort. gecikme (s)"),
    ("mean_confirm_latency_s", "Ort. onay gecikmesi (s)"), ("duty_cycle", "Duty-cycle (verici başına)"),
    ("duty_cycle_violations", "Duty-cycle ihlali (veri)"), ("ack_duty_cycle_violations", "Duty-cycle ihlali (ACK)"),
    ("tx_energy_j", "Verici enerjisi (J)"), ("energy_per_delivered_packet_mj", "Enerji / başarılı paket (mJ)"),
    ("elapsed_sim_time_s", "Simülasyon süresi (s)"),
]


def summary_lines(summary: dict) -> list[str]:
    lines = [f"{label:<34}{_fmt(summary.get(key))}" for key, label in SUMMARY_FIELDS]
    lines += ["", "Alım durumları:"]
    lines += [f"  {STATUS_LABELS.get(k, k):<32}{v}" for k, v in summary["status_counts"].items() if v]
    lines += ["", "ACK durumları:"]
    lines += [f"  {k:<32}{v}" for k, v in summary["ack_counts"].items() if v]
    if summary.get("per_device"):
        lines += ["", f"{'Verici':<10}{'Üretilen':>10}{'Başarılı':>10}{'Oran':>8}{'Gönderim':>10}{'Çakışma':>9}"]
        for k, d in summary["per_device"].items():
            lines.append(f"{k:<10}{d['generated']:>10}{d['delivered']:>10}{_fmt(d['success_rate']):>8}"
                         f"{d['transmissions']:>10}{d['collisions']:>9}")
    return lines


def config_lines(config: SimConfig) -> list[str]:
    lines = []
    for section, values in config.to_dict().items():
        lines.append(f"[{section}]")
        for k, v in values.items():
            if k == "devices":
                lines.append(f"  devices: {len(v)} cihaz")
                lines += [f"    {d['id']} ({d['role']}) x={d['x']:g} y={d['y']:g}" for d in v[:40]]
            else:
                lines.append(f"  {k}: {v}")
    return lines


def write_pdf_report(path: str | Path, config: SimConfig, summary: dict, records: Iterable[PacketRecord],
                     trajectories: Optional[dict] = None, sweeps: Optional[list[list[dict]]] = None) -> None:
    """Çok sayfalı PDF rapor: özet, ayarlar, zaman grafikleri, konumlar ve taramalar."""
    recs = list(records)
    with PdfPages(path) as pdf:
        head = [f"LoRaSim {__version__} — {datetime.now():%Y-%m-%d %H:%M}", ""]
        _text_page(pdf, "SX1276 LoRa Simülasyon Raporu", head + summary_lines(summary))
        _text_page(pdf, "Simülasyon ayarları", config_lines(config))
        if recs:
            fig = plot_time_series(recs)
            pdf.savefig(fig)
            plt.close(fig)
        if trajectories:
            fig = plot_positions(trajectories)
            pdf.savefig(fig)
            plt.close(fig)
        for rows in sweeps or []:
            if rows:
                fig = plot_sweep(rows)
                pdf.savefig(fig)
                plt.close(fig)
                _text_page(pdf, "Tarama sonuçları", sweep_lines(rows))
        info = pdf.infodict()
        info["Title"] = "SX1276 LoRa Simülasyon Raporu"
        info["Creator"] = f"LoRaSim {__version__}"


def sweep_lines(rows: list[dict]) -> list[str]:
    cols = [("value", "Değer", 12), ("success_rate", "Başarı", 9), ("per", "PER", 9), ("mean_rssi_dbm", "RSSI", 9),
            ("mean_snr_db", "SNR", 9), ("throughput_bps", "Thr(b/s)", 10), ("mean_latency_s", "Gecikme(s)", 11)]
    lines = [" ".join(f"{label:>{w}}" for _, label, w in cols)]
    for r in rows:
        lines.append(" ".join(f"{_fmt(r[k]):>{w}}" for k, _, w in cols))
    return lines


def trajectories_from_engine(engine, samples: int = 200) -> dict:
    """Motorun cihazlarının başlangıçtan simülasyon sonuna kadarki yollarını örnekler."""
    end = max(engine.metrics.elapsed_s, 1e-9)
    times = [end * i / (samples - 1) for i in range(samples)]
    out = {}
    for d in engine.devices.values():
        pts = [tuple(map(float, d.position(t)[:2])) for t in (times if d.trajectory.is_moving else [0.0])]
        out[d.id] = (d.role, pts)
    return out


def plot_model_comparison(rows: list[dict], path: Optional[str | Path] = None) -> Figure:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    snr = [r["snr_db"] for r in rows]
    ax = axes[0]
    ax.semilogy(snr, [max(r["per_link_level"], 1e-4) for r in rows], "o-", label="Link-level")
    ax.semilogy(snr, [max(r["per_css_phy"], 1e-4) for r in rows], "s--", label="CSS fiziksel katman")
    ax.set(title="PER – SNR", xlabel="SNR (dB)", ylabel="PER")
    ax = axes[1]
    ax.semilogy(snr, [max(r["ser_theory"], 1e-7) for r in rows], "-", color="k", label="Teori")
    ax.semilogy(snr, [max(r["ser_css_phy"] or 0, 1e-7) for r in rows], "s--", label="CSS ölçülen")
    ax.set(title="SER – SNR", xlabel="SNR (dB)", ylabel="SER")
    for a in axes:
        a.grid(alpha=0.3, which="both")
        a.legend()
    return _finish(fig, path)


def model_comparison_lines(rows: list[dict]) -> list[str]:
    lines = [f"{'SNR(dB)':>8} {'PER LL':>8} {'PER CSS':>8} {'SER teori':>10} {'SER LL':>10} {'SER CSS':>10}"]
    for r in rows:
        lines.append(f"{r['snr_db']:>8.2f} {r['per_link_level']:>8.3f} {r['per_css_phy']:>8.3f} "
                     f"{_fmt(r['ser_theory']):>10} {_fmt(r['ser_link_level']):>10} {_fmt(r['ser_css_phy']):>10}")
    return lines


def write_model_comparison_pdf(path: str | Path, rows: list[dict]) -> None:
    with PdfPages(path) as pdf:
        fig = plot_model_comparison(rows)
        pdf.savefig(fig)
        plt.close(fig)
        _text_page(pdf, "Link-level ↔ CSS model karşılaştırması", model_comparison_lines(rows))
