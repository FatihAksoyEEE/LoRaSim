import csv
import json

from lorasim.config import SimConfig
from lorasim.export.csv_exporter import write_csv
from lorasim.export.json_exporter import write_json
from lorasim.simulation.simulation_engine import SimulationEngine


def test_csv_and_json(tmp_path):
    cfg = SimConfig()
    cfg.run.mode, cfg.run.seed, cfg.traffic.max_packets = "accelerated", 3, 20
    cfg.channel.awgn_enabled = False  # inf SNR'in JSON'a null olarak yazıldığını da sınar
    e = SimulationEngine(cfg)
    summary = e.run()
    write_csv(e.metrics.records, tmp_path / "r.csv")
    write_json(cfg, summary, tmp_path / "r.json")

    rows = list(csv.DictReader(open(tmp_path / "r.csv", encoding="utf-8")))
    assert len(rows) == 20 and rows[0]["seq"] == "0"
    report = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert report["summary"]["packets_sent"] == 20
    assert report["config"]["lora"]["spreading_factor"] == 7
    assert SimConfig.from_dict(report["config"]) == cfg
