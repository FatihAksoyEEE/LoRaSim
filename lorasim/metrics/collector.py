"""Paket kayıtları ve özet kalite göstergeleri.

İki tür kayıt tutulur:
- PacketRecord: her veri gönderim denemesi (tekrar gönderimler dahil) için bir satır.
- PacketOutcome: üretilen her benzersiz paket için nihai sonuç.
"""

from __future__ import annotations

import math
import re
from collections import deque
from dataclasses import asdict, dataclass, fields
from enum import Enum
from typing import Optional

from lorasim.simulation.link_level_model import RxStatus


# Bu durumlarda alıcı sinyali hiç ölçemez; ortalama RSSI/SNR'ye katılmaz.
_UNMEASURED = {RxStatus.NOT_DETECTED.value, RxStatus.HALF_DUPLEX.value, RxStatus.FREQ_OFFSET.value}


class AckStatus(str, Enum):
    DISABLED = "disabled"
    ACKED = "acked"
    NOT_SENT = "not_sent"  # veri alınamadığı için ACK gönderilmedi
    BLOCKED = "blocked"  # alıcının duty-cycle'ı ACK'e izin vermedi
    LOST = "lost"  # ACK gönderildi ama vericide çözülemedi
    LATE = "late"  # ACK timeout'tan sonra ulaştı


class Outcome(str, Enum):
    CONFIRMED = "confirmed"  # ACK alındı
    DELIVERED = "delivered"  # alıcıya hatasız ulaştı, ACK yok/alınamadı
    FAILED = "failed"
    QUEUE_DROP = "queue_drop"


@dataclass(frozen=True)
class PacketRecord:
    time_s: float  # alımın tamamlandığı simülasyon zamanı
    seq: int
    tx_id: str
    rx_id: str
    payload_bytes: int
    airtime_s: float
    distance_m: float
    environment: str
    path_loss_db: float
    shadowing_db: float
    fading_db: float
    rssi_dbm: float
    noise_dbm: float
    snr_db: float
    status: str
    delivered: bool
    success: bool
    bit_errors: int
    bits_compared: int
    symbol_errors: int
    symbols_compared: int
    latency_s: float  # paket üretiminden bu denemenin alımına kadar
    retransmissions: int = 0  # 0 = ilk gönderim
    ack_status: str = AckStatus.DISABLED.value
    duplicate: bool = False
    duty_cycle_violation: bool = False
    freq_offset_hz: float = 0.0  # kristal hatası + Doppler
    doppler_hz: float = 0.0
    interferers: int = 0  # zamanda örtüşen girişim/gönderim sayısı

    @classmethod
    def field_names(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PacketOutcome:
    tx_id: str
    seq: int
    created_at_s: float
    resolved_at_s: float
    outcome: str
    attempts: int
    delivery_latency_s: Optional[float]  # üretim → alıcıda ilk hatasız alım
    confirm_latency_s: Optional[float]  # üretim → ACK'in vericiye ulaşması


def _natural(s: str):
    """TX2 < TX10 olacak biçimde doğal sıralama anahtarı."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", s)]


def _new_device_stats() -> dict:
    return {"generated": 0, "delivered": 0, "confirmed": 0, "failed": 0, "queue_drop": 0,
            "transmissions": 0, "frames_ok": 0, "collisions": 0, "rssi_sum": 0.0, "detected": 0}


class MetricsCollector:
    """Özet metrikler sayaçlardan hesaplanır; `records`/`outcomes` yalnızca son `max_records` kaydı tutar."""

    def __init__(self, max_records: Optional[int] = None):
        self.records: deque[PacketRecord] = deque(maxlen=max_records)
        self.outcomes: deque[PacketOutcome] = deque(maxlen=max_records)
        self.per_device: dict[str, dict] = {}
        self._n_records = 0
        self._n_outcomes = 0
        self._n_latency = 0
        self.status_counts = {s.value: 0 for s in RxStatus}
        self.ack_counts = {s.value: 0 for s in AckStatus}
        self.outcome_counts = {o.value: 0 for o in Outcome}
        self.duty_cycle_violations = 0
        self.ack_duty_cycle_violations = 0
        self._bit_errors = self._bits = 0
        self._sym_errors = self._syms = 0
        self._rssi_sum = self._snr_sum = 0.0
        self._detected = 0
        self._good_payload_bits = 0
        self._airtime_sum = 0.0
        self._delivery_latency_sum = 0.0
        self._confirm_latency_sum = 0.0
        self.elapsed_s = 0.0

    def _dev(self, tx_id: str) -> dict:
        return self.per_device.setdefault(tx_id, _new_device_stats())

    def add(self, r: PacketRecord) -> None:
        self.records.append(r)
        self._n_records += 1
        dev = self._dev(r.tx_id)
        dev["transmissions"] += 1
        dev["frames_ok"] += int(r.success)
        dev["collisions"] += int(r.status == RxStatus.COLLISION.value)
        self.status_counts[r.status] += 1
        self.ack_counts[r.ack_status] += 1
        self.duty_cycle_violations += int(r.duty_cycle_violation)
        self._bit_errors += r.bit_errors
        self._bits += r.bits_compared
        self._sym_errors += r.symbol_errors
        self._syms += r.symbols_compared
        self._airtime_sum += r.airtime_s
        if r.status not in _UNMEASURED:
            dev["detected"] += 1
            dev["rssi_sum"] += r.rssi_dbm
            self._detected += 1
            self._rssi_sum += r.rssi_dbm
            if math.isfinite(r.snr_db):
                self._snr_sum += r.snr_db
        if r.success and not r.duplicate:
            self._good_payload_bits += 8 * r.payload_bytes
        self.elapsed_s = max(self.elapsed_s, r.time_s)

    def add_outcome(self, o: PacketOutcome) -> None:
        self.outcomes.append(o)
        self._n_outcomes += 1
        self.outcome_counts[o.outcome] += 1
        dev = self._dev(o.tx_id)
        dev["generated"] += 1
        dev[{"confirmed": "confirmed", "delivered": "delivered", "failed": "failed",
             "queue_drop": "queue_drop"}[o.outcome]] += 1
        if o.outcome == Outcome.CONFIRMED.value:
            dev["delivered"] += 1
        if o.delivery_latency_s is not None:
            self._n_latency += 1
            self._delivery_latency_sum += o.delivery_latency_s
        if o.confirm_latency_s is not None:
            self._confirm_latency_sum += o.confirm_latency_s
        self.elapsed_s = max(self.elapsed_s, o.resolved_at_s)

    @property
    def transmissions(self) -> int:
        return self._n_records

    @property
    def packets_resolved(self) -> int:
        return self._n_outcomes

    @property
    def packets_delivered(self) -> int:
        return self.outcome_counts[Outcome.CONFIRMED.value] + self.outcome_counts[Outcome.DELIVERED.value]

    def summary(self) -> dict:
        n_tx = self.transmissions
        n_pkt = self.packets_resolved
        oc = self.outcome_counts
        delivered = self.packets_delivered
        confirmed = oc[Outcome.CONFIRMED.value]
        n_sent = n_pkt - oc[Outcome.QUEUE_DROP.value]
        frame_ok = self.status_counts[RxStatus.OK.value]
        ack_expected = n_tx - self.ack_counts[AckStatus.DISABLED.value]
        n_latency = self._n_latency
        div = lambda a, b: a / b if b else None  # noqa: E731
        return {
            # Benzersiz paketler (tekrar gönderimler sonrası nihai durum)
            "packets_generated": n_pkt,
            "packets_sent": n_sent,
            "packets_successful": delivered,
            "packets_confirmed": confirmed,
            "packets_failed": oc[Outcome.FAILED.value],
            "packets_dropped_queue": oc[Outcome.QUEUE_DROP.value],
            "outcome_counts": dict(oc),
            "success_rate": div(delivered, n_pkt),
            "packet_loss_rate": div(n_pkt - delivered, n_pkt),
            # Tek tek gönderimler (frame düzeyi)
            "transmissions": n_tx,
            "retransmissions": n_tx - n_sent,
            "status_counts": dict(self.status_counts),
            "per": div(n_tx - frame_ok, n_tx),
            "ber": div(self._bit_errors, self._bits),
            "ser": div(self._sym_errors, self._syms),
            "mean_rssi_dbm": div(self._rssi_sum, self._detected),
            "mean_snr_db": div(self._snr_sum, self._detected),
            # ACK
            "ack_counts": dict(self.ack_counts),
            "ack_success_rate": div(self.ack_counts[AckStatus.ACKED.value], ack_expected),
            # Performans
            "throughput_bps": div(self._good_payload_bits, self.elapsed_s),
            "mean_latency_s": div(self._delivery_latency_sum, n_latency),
            "mean_confirm_latency_s": div(self._confirm_latency_sum, confirmed),
            "total_airtime_s": self._airtime_sum,
            # Verici başına ortalama duty-cycle (veri gönderimleri)
            "duty_cycle": div(self._airtime_sum, self.elapsed_s * max(len(self.per_device), 1)),
            "duty_cycle_violations": self.duty_cycle_violations,
            "ack_duty_cycle_violations": self.ack_duty_cycle_violations,
            "elapsed_sim_time_s": self.elapsed_s,
            "per_device": {k: self._device_summary(self.per_device[k]) for k in sorted(self.per_device, key=_natural)},
        }

    @staticmethod
    def _device_summary(d: dict) -> dict:
        n = d["generated"]
        return {
            "generated": n,
            "delivered": d["delivered"],
            "confirmed": d["confirmed"],
            "failed": d["failed"],
            "queue_drop": d["queue_drop"],
            "transmissions": d["transmissions"],
            "collisions": d["collisions"],
            "success_rate": d["delivered"] / n if n else None,
            "per": 1 - d["frames_ok"] / d["transmissions"] if d["transmissions"] else None,
            "mean_rssi_dbm": d["rssi_sum"] / d["detected"] if d["detected"] else None,
        }
