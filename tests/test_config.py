import json
from pathlib import Path

import pytest

from lorasim.config import ConfigError, SimConfig

DEFAULT_JSON = Path(__file__).parent.parent / "lorasim" / "config" / "default_config.json"


def test_default_config_is_valid():
    SimConfig().validate()


def test_default_json_matches_dataclass_defaults():
    assert json.loads(DEFAULT_JSON.read_text(encoding="utf-8")) == SimConfig().to_dict()


def test_roundtrip(tmp_path):
    cfg = SimConfig()
    cfg.lora.spreading_factor = 10
    cfg.channel.environment = "urban"
    cfg.run.seed = 7
    path = tmp_path / "c.json"
    cfg.save(path)
    assert SimConfig.load(path) == cfg


@pytest.mark.parametrize("section, name, value", [
    ("lora", "frequency_mhz", 100.0),
    ("lora", "frequency_mhz", 1100.0),
    ("lora", "spreading_factor", 6),
    ("lora", "bandwidth_khz", 62.5),
    ("lora", "coding_rate", 4),
    ("lora", "tx_power_dbm", 21.0),
    ("lora", "payload_bytes", 5),
    ("lora", "payload_bytes", 256),
    ("lora", "preamble_symbols", 5),
    ("radio", "tx_losses_db", -1.0),
    ("channel", "environment", "space"),
    ("channel", "fading", "nakagami"),
    ("topology", "distance_m", 0.5),
    ("traffic", "interval_s", 0.0),
    ("run", "mode", "slow"),
])
def test_invalid_values_are_reported(section, name, value):
    cfg = SimConfig()
    setattr(getattr(cfg, section), name, value)
    with pytest.raises(ConfigError) as exc:
        cfg.validate()
    assert len(exc.value.errors) == 1


def test_all_errors_reported_together():
    cfg = SimConfig()
    cfg.lora.spreading_factor = 13
    cfg.lora.frequency_mhz = 50
    with pytest.raises(ConfigError) as exc:
        cfg.validate()
    assert len(exc.value.errors) == 2


def test_unknown_field_rejected():
    with pytest.raises(ConfigError):
        SimConfig.from_dict({"lora": {"spreadingfactor": 7}})
