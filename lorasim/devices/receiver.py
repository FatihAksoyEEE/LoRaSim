"""Alıcı durum bilgisi (motor tarafından yönetilir)."""

from __future__ import annotations

from dataclasses import dataclass, field

from lorasim.devices.device import Device
from lorasim.simulation.duty_cycle import DutyCycleTracker


@dataclass
class ReceiverState:
    device: Device
    duty: DutyCycleTracker
    # Hatasız alınan paketler: (verici kimliği, paket no) → ilk alım zamanı
    delivered: dict = field(default_factory=dict)
    tx_time_s: float = 0.0  # ACK gönderimleri

    @property
    def id(self) -> str:
        return self.device.id
