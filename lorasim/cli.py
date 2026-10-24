"""Komut satırı arayüzü.

Örnek:
    python -m lorasim --sf 9 --distance 3000 --env urban --packets 1000 --mode accelerated \\
        --seed 42 --csv output/run.csv --json output/run.json
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

from lorasim.config import ENVIRONMENTS, ConfigError, SimConfig
from lorasim.export.csv_exporter import write_csv, write_rows_csv
from lorasim.export.json_exporter import write_json, write_sweep_json
from lorasim.simulation.simulation_engine import SimulationEngine


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lorasim", description="SX1276 LoRa haberleşme simülasyonu")
    p.add_argument("--config", type=Path, help="JSON yapılandırma dosyası (diğer seçenekler üzerine yazar)")
    p.add_argument("--save-config", type=Path, help="Kullanılan yapılandırmayı JSON olarak kaydet")
    g = p.add_argument_group("LoRa")
    g.add_argument("--freq", type=float, dest="frequency_mhz", help="Frekans (MHz)")
    g.add_argument("--sf", type=int, dest="spreading_factor")
    g.add_argument("--bw", type=float, dest="bandwidth_khz", help="Bant genişliği (kHz)")
    g.add_argument("--cr", type=int, dest="coding_rate", help="Kodlama oranı paydası (5–8 → 4/5–4/8)")
    g.add_argument("--power", type=float, dest="tx_power_dbm", help="Gönderim gücü (dBm)")
    g.add_argument("--payload", type=int, dest="payload_bytes", help="Payload uzunluğu (byte)")
    g.add_argument("--no-crc", action="store_false", dest="crc_enabled", default=None)
    g = p.add_argument_group("Kanal")
    g.add_argument("--env", choices=ENVIRONMENTS, dest="environment")
    g.add_argument("--fading", choices=("none", "rayleigh", "rician"))
    g.add_argument("--shadowing", choices=("off", "per_link", "per_packet"))
    g.add_argument("--distance", type=float, dest="distance_m", help="Verici–alıcı mesafesi (m)")
    g.add_argument("--multipath", action="store_true", dest="multipath_enabled", default=None,
                   help="Ortam profilinin çok yollu gecikme hattını kullan")
    g.add_argument("--time-varying", action="store_true", dest="time_varying", default=None,
                   help="Zamana/konuma bağlı ilintili sönümleme ve gölgeleme")
    g.add_argument("--doppler", action="store_true", dest="doppler_enabled", default=None)
    g.add_argument("--freq-offset", type=float, dest="crystal_ppm",
                   help="Kristal frekans hatası (±ppm); verilirse frekans kayması açılır")
    g.add_argument("--interference", choices=("lora", "wideband"), dest="interference_type",
                   help="Harici girişim kaynağını aç")
    g.add_argument("--interference-power", type=float, dest="interference_power_dbm")
    g.add_argument("--interference-rate", type=float, dest="interference_rate_hz")
    g.add_argument("--no-collisions", action="store_false", dest="collisions_enabled", default=None)
    g = p.add_argument_group("Cihazlar ve hareket")
    g.add_argument("--positioning", choices=("distance", "cartesian", "random"), dest="topology_mode")
    g.add_argument("--tx-count", type=int, dest="num_transmitters")
    g.add_argument("--rx-count", type=int, dest="num_receivers")
    g.add_argument("--area", type=float, help="Rastgele yerleşim için kare alan kenarı (m)")
    g.add_argument("--moving", choices=("none", "transmitters", "receivers", "all"))
    g.add_argument("--mobility", choices=("constant", "random_walk", "route", "circular"), dest="mobility_model")
    g.add_argument("--speed-mps", type=float, dest="speed_mps")
    g.add_argument("--heading", type=float, dest="heading_deg")
    g = p.add_argument_group("Trafik ve çalışma")
    g.add_argument("--interval", type=float, dest="interval_s", help="Paket aralığı (s)")
    g.add_argument("--packets", type=int, dest="max_packets", help="Maksimum paket sayısı")
    g.add_argument("--duration", type=float, dest="duration_s", help="Süre sınırı (simülasyon saniyesi)")
    g.add_argument("--queue", type=int, dest="tx_queue_size", help="Gönderim kuyruğu boyutu")
    g.add_argument("--duty-cycle", type=float, dest="duty_cycle_percent",
                   help="Duty-cycle sınırı (%%); 0 → kontrol yok")
    g.add_argument("--duty-policy", choices=("warn", "enforce"), dest="duty_cycle_policy")
    g.add_argument("--mode", choices=("realtime", "accelerated"))
    g.add_argument("--model", choices=("link_level", "css_phy"), help="Simülasyon modeli")
    g.add_argument("--speed", type=float, help="Gerçek zamanlı modda zaman ölçeği")
    g.add_argument("--seed", type=int)
    g = p.add_argument_group("ACK")
    g.add_argument("--no-ack", action="store_false", dest="ack_enabled", default=None)
    g.add_argument("--retries", type=int, dest="max_retries", help="Maksimum tekrar gönderim sayısı")
    g.add_argument("--ack-timeout", type=float, dest="ack_timeout_s", help="ACK timeout (s); verilmezse otomatik")
    g.add_argument("--packet-timeout", type=float, dest="packet_timeout_s", help="Paket timeout (s)")
    g = p.add_argument_group("Çıktı")
    g.add_argument("--csv", type=Path, help="Paket bazlı CSV çıktısı")
    g.add_argument("--json", type=Path, help="Ayarlar ve özet JSON çıktısı")
    g.add_argument("--png", type=Path, help="Grafikleri PNG olarak kaydet (zaman serileri veya tarama)")
    g.add_argument("--report", type=Path, help="PDF simülasyon raporu")
    g = p.add_argument_group("Analiz")
    g.add_argument("--sweep", choices=("distance", "power", "sf", "environment"),
                   help="Parametre taraması / ortam karşılaştırması yap")
    g.add_argument("--sweep-values", help="Virgülle ayrılmış tarama değerleri (verilmezse varsayılan)")
    g.add_argument("--sweep-packets", type=int, default=200, help="Tarama noktası başına paket (varsayılan 200)")
    g.add_argument("--compare-models", action="store_true",
                   help="Link-level ve CSS fiziksel katman modellerini SNR'ye göre karşılaştır")
    g.add_argument("--max-range", type=float, nargs="?", const=0.9, metavar="EŞİK",
                   help="Başarı oranının EŞİK (varsayılan 0.9) üstünde kaldığı en büyük mesafeyi bul")
    g.add_argument("-q", "--quiet", action="store_true", help="Paket satırlarını yazdırma")
    return p


_OVERRIDES = {
    "lora": ("frequency_mhz", "spreading_factor", "bandwidth_khz", "coding_rate", "tx_power_dbm",
             "payload_bytes", "crc_enabled"),
    "channel": ("environment", "fading", "shadowing", "multipath_enabled", "time_varying", "doppler_enabled",
                "crystal_ppm", "interference_type", "interference_power_dbm", "interference_rate_hz",
                "collisions_enabled"),
    "topology": ("distance_m", ("topology_mode", "mode"), "num_transmitters", "num_receivers"),
    "mobility": ("moving", ("mobility_model", "model"), "speed_mps", "heading_deg"),
    "traffic": ("interval_s", "max_packets", "duration_s", "tx_queue_size", "duty_cycle_policy"),
    "ack": (("ack_enabled", "enabled"), "max_retries", ("ack_timeout_s", "timeout_s"), "packet_timeout_s"),
    "run": ("mode", "speed", "seed", "model"),
}


def config_from_args(args: argparse.Namespace) -> SimConfig:
    cfg = SimConfig.load(args.config) if args.config else SimConfig()
    for section, names in _OVERRIDES.items():
        target = getattr(cfg, section)
        for name in names:
            arg, attr = name if isinstance(name, tuple) else (name, name)
            value = getattr(args, arg)
            if value is not None:
                setattr(target, attr, value)
    if args.crystal_ppm is not None:
        cfg.channel.frequency_offset_enabled = True
    if args.interference_type is not None:
        cfg.channel.interference_enabled = True
    if args.area is not None:
        cfg.topology.area_width_m = cfg.topology.area_height_m = args.area
    if args.duty_cycle_percent is not None:
        cfg.traffic.duty_cycle_limit = args.duty_cycle_percent / 100 if args.duty_cycle_percent > 0 else None
    return cfg


def _fmt(v, unit="", digits=3):
    if v is None:
        return "—"
    return f"{v:.{digits}g}{unit}" if isinstance(v, float) else f"{v}{unit}"


def _counts(d: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in d.items() if v) or "—"


def print_summary(s: dict) -> None:
    rows = [
        ("Seed", s["seed"]),
        ("Airtime", _fmt(s["airtime_s"] * 1e3, " ms", 5)),
        ("Hassasiyet", _fmt(s["sensitivity_dbm"], " dBm", 4)),
        ("Yol kaybı", _fmt(s["path_loss_db"], " dB", 4)),
        ("LDRO", "açık" if s["ldro"] else "kapalı"),
        ("ACK timeout", _fmt(None if s["ack_timeout_s"] is None else s["ack_timeout_s"] * 1e3, " ms", 5)),
        ("Üretilen paket", s["packets_generated"]),
        ("Başarılı paket", f'{s["packets_successful"]} (ACK ile onaylanan: {s["packets_confirmed"]})'),
        ("Paket sonuçları", _counts(s["outcome_counts"])),
        ("Başarı oranı", _fmt(s["success_rate"])),
        ("Paket kayıp oranı", _fmt(s["packet_loss_rate"])),
        ("Gönderim / tekrar", f'{s["transmissions"]} / {s["retransmissions"]}'),
        ("Alım durumları", _counts(s["status_counts"])),
        ("PER (frame)", _fmt(s["per"])),
        ("ACK durumları", _counts(s["ack_counts"])),
        ("ACK başarı oranı", _fmt(s["ack_success_rate"])),
        ("BER", _fmt(s["ber"])),
        ("SER", _fmt(s["ser"])),
        ("Ortalama RSSI", _fmt(s["mean_rssi_dbm"], " dBm", 4)),
        ("Ortalama SNR", _fmt(s["mean_snr_db"], " dB", 3)),
        ("Throughput", _fmt(s["throughput_bps"], " bit/s", 4)),
        ("Ortalama gecikme", _fmt(None if s["mean_latency_s"] is None else s["mean_latency_s"] * 1e3, " ms", 4)),
        ("Ort. onay gecikmesi",
         _fmt(None if s["mean_confirm_latency_s"] is None else s["mean_confirm_latency_s"] * 1e3, " ms", 4)),
        ("Duty-cycle", _fmt(None if s["duty_cycle"] is None else s["duty_cycle"] * 100, " %", 3)),
        ("Duty-cycle ihlali", f'veri: {s["duty_cycle_violations"]}, ACK: {s["ack_duty_cycle_violations"]}'),
        ("Simülasyon süresi", _fmt(s["elapsed_sim_time_s"], " s", 5)),
        ("Verici enerjisi", _fmt(s["tx_energy_j"] * 1e3, " mJ", 4)),
        ("Enerji / başarılı paket", _fmt(s["energy_per_delivered_packet_mj"], " mJ", 4)),
    ]
    rows.insert(0, ("Model / cihaz", f'{s["model"]}, {s["num_transmitters"]} verici, {s["num_receivers"]} alıcı'))
    width = max(len(k) for k, _ in rows)
    print("\n=== Özet ===")
    for k, v in rows:
        print(f"{k:<{width}} : {v}")
    if len(s["per_device"]) > 1:
        print("\n=== Vericiler ===")
        print(f"{'Verici':<8} {'Üretilen':>9} {'Başarılı':>9} {'Oran':>6} {'Gönderim':>9} {'Çakışma':>8} {'Ort. RSSI':>10}")
        for k, d in s["per_device"].items():
            rate = "—" if d["success_rate"] is None else f'{d["success_rate"]:.3f}'
            rssi = "—" if d["mean_rssi_dbm"] is None else f'{d["mean_rssi_dbm"]:.1f}'
            print(f"{k:<8} {d['generated']:>9} {d['delivered']:>9} {rate:>6} {d['transmissions']:>9} "
                  f"{d['collisions']:>8} {rssi:>10}")


def _ensure_dirs(*paths) -> None:
    for path in paths:
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)


def run_analysis(args, cfg: SimConfig) -> int:
    from lorasim.export import report_exporter
    from lorasim.simulation import analysis

    progress = lambda i, n: print(f"\r  {i}/{n} nokta", end="", file=sys.stderr, flush=True)  # noqa: E731
    _ensure_dirs(args.csv, args.json, args.png, args.report)
    extra = {}
    if args.compare_models:
        rows = analysis.compare_models(cfg, packets=args.sweep_packets, progress=progress)
        print(file=sys.stderr)
        for line in report_exporter.model_comparison_lines(rows):
            print(line)
        if args.csv:
            write_rows_csv(rows, args.csv)
        if args.json:
            write_sweep_json(cfg, rows, args.json, {"analysis": "model_comparison"})
        if args.png:
            report_exporter.plot_model_comparison(rows, args.png)
        return 0
    if args.max_range is not None:
        cfg.validate()
        print(f"Başarılı haberleşme mesafesi aranıyor (başarı ≥ {args.max_range:g})...", file=sys.stderr)
        rng_m, rows = analysis.find_max_range(cfg, args.max_range, args.sweep_packets, progress=progress)
        print(file=sys.stderr)
        msg = "bulunamadı (en kısa mesafede bile eşik sağlanmıyor)" if rng_m is None else f"{rng_m:,.0f} m"
        print(f"Başarılı haberleşme mesafesi: {msg}")
        extra = {"max_range_m": rng_m, "threshold": args.max_range}
    else:
        values = None
        if args.sweep_values:
            raw = [v.strip() for v in args.sweep_values.split(",") if v.strip()]
            values = raw if args.sweep == "environment" else [
                int(v) if args.sweep == "sf" else float(v) for v in raw]
        cfg.validate()
        rows = analysis.run_sweep(cfg, args.sweep, values, args.sweep_packets, progress=progress)
        print(file=sys.stderr)
    for line in report_exporter.sweep_lines(rows):
        print(line)
    if args.csv:
        write_rows_csv(rows, args.csv)
        print(f"CSV kaydedildi: {args.csv}")
    if args.json:
        write_sweep_json(cfg, rows, args.json, extra)
        print(f"JSON kaydedildi: {args.json}")
    if args.png:
        report_exporter.plot_sweep(rows, args.png)
        print(f"PNG kaydedildi: {args.png}")
    if args.report:
        from matplotlib.backends.backend_pdf import PdfPages
        import matplotlib.pyplot as plt
        with PdfPages(args.report) as pdf:
            fig = report_exporter.plot_sweep(rows)
            pdf.savefig(fig)
            plt.close(fig)
        print(f"PDF kaydedildi: {args.report}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = config_from_args(args)
        if args.sweep or args.max_range is not None or args.compare_models:
            return run_analysis(args, cfg)
        if cfg.traffic.max_packets is None and cfg.traffic.duration_s is None and cfg.run.mode == "accelerated":
            raise ConfigError(["Hızlandırılmış modda --packets veya --duration ile bir sınır verilmeli."])

        def on_record(r):
            if not args.quiet:
                retry = f"(tekrar {r.retransmissions})" if r.retransmissions else ""
                print(f"t={r.time_s:9.3f}s  {r.tx_id}→{r.rx_id} #{r.seq:<5}{retry:<11} {r.status:<20} ACK={r.ack_status:<8} "
                      f"RSSI={r.rssi_dbm:7.1f} dBm  SNR={r.snr_db:6.1f} dB  bit hata={r.bit_errors}"
                      + ("  [duty-cycle ihlali]" if r.duty_cycle_violation else ""))

        engine = SimulationEngine(cfg, on_record=on_record)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 2

    signal.signal(signal.SIGINT, lambda *_: engine.stop())
    summary = engine.run()
    print_summary(summary)
    if summary["duty_cycle_violations"] or summary["ack_duty_cycle_violations"]:
        limit = cfg.traffic.duty_cycle_limit * 100
        print(f"\nUYARI: %{limit:g} duty-cycle sınırı aşıldı. Paket aralığını artırın, SF'yi düşürün "
              f"ya da --duty-policy enforce ile sınırı uygulayın.", file=sys.stderr)

    cfg.run.seed = engine.seed  # tekrar üretilebilirlik için kullanılan seed'i kaydet
    _ensure_dirs(args.csv, args.json, args.save_config, args.png, args.report)
    if args.png or args.report:
        from lorasim.export import report_exporter
        if args.png:
            report_exporter.plot_time_series(engine.metrics.records, args.png)
            print(f"PNG kaydedildi: {args.png}")
        if args.report:
            report_exporter.write_pdf_report(args.report, cfg, summary, engine.metrics.records,
                                             report_exporter.trajectories_from_engine(engine))
            print(f"PDF kaydedildi: {args.report}")
    if args.csv:
        write_csv(engine.metrics.records, args.csv)
        print(f"CSV kaydedildi: {args.csv}")
    if args.json:
        write_json(cfg, summary, args.json)
        print(f"JSON kaydedildi: {args.json}")
    if args.save_config:
        cfg.save(args.save_config)
    return 0
