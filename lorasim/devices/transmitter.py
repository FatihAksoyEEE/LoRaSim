"""Verici durum bilgisi (motor tarafından yönetilir)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from lorasim.devices.device import Device
from lorasim.simulation.duty_cycle import DutyCycleTracker
from lorasim.simulation.packet_manager import Packet, PacketFactory


@dataclass
class TransmitterState:
    device: Device
    factory: PacketFactory
    duty: DutyCycleTracker
    queue: deque = field(default_factory=deque)
    busy: bool = False  # gönderim, ACK bekleme veya duty-cycle beklemesi
    pending: Optional[object] = None  # ACK beklenen deneme
    generated: int = 0
    tx_time_s: float = 0.0
    listen_time_s: float = 0.0  # ACK beklerken alıcının açık kaldığı süre

    @property
    def id(self) -> str:
        return self.device.id

    def next_packet(self) -> Optional[Packet]:
        return self.queue.popleft() if self.queue else None
