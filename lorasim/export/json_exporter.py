"""Simülasyon ayarları ve özet sonuçların JSON çıktısı."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from lorasim import __version__
from lorasim.config import SimConfig


def _clean(value):
    """JSON standardında olmayan inf/NaN değerlerini null yapar."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


def build_report(config: SimConfig, summary: dict) -> dict:
    return _clean({
        "lorasim_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": config.to_dict(),
        "summary": summary,
    })


def write_json(config: SimConfig, summary: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(build_report(config, summary), indent=2, ensure_ascii=False),
                          encoding="utf-8")


def write_sweep_json(config: SimConfig, rows: list[dict], path: str | Path, extra: dict | None = None) -> None:
    report = {"lorasim_version": __version__,
              "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "base_config": config.to_dict(), "results": rows}
    report.update(extra or {})
    Path(path).write_text(json.dumps(_clean(report), indent=2, ensure_ascii=False), encoding="utf-8")
