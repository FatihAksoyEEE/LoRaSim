"""Paket bazlı sonuçların CSV çıktısı."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from lorasim.metrics.collector import PacketRecord


def write_csv(records: Iterable[PacketRecord], path: str | Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PacketRecord.field_names())
        writer.writeheader()
        for r in records:
            writer.writerow(r.to_dict())


def write_rows_csv(rows: list[dict], path: str | Path) -> None:
    """Tarama/karşılaştırma sonuçları gibi sözlük satırlarını CSV olarak yazar."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
