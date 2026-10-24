"""Simülasyon ve analizleri arayüzü dondurmadan çalıştıran iş parçacıkları.

İş parçacığı güvenliği:
- Motor kayıtlarını `on_record` ile thread-safe bir deque'ya ekler; arayüz bunları
  bir QTimer ile kendi thread'inde boşaltır (kayıt başına sinyal gönderilmez).
- Durdur/duraklat/devam et motorun threading.Event tabanlı yöntemleriyle yapılır.
- Bitiş ve hata bilgisi Qt sinyalleriyle (kuyruklu bağlantı) arayüz thread'ine taşınır.
"""

from __future__ import annotations

import threading
import traceback
from collections import deque
from typing import Callable

from PySide6.QtCore import QThread, Signal

from lorasim.config import ConfigError, SimConfig
from lorasim.simulation.simulation_engine import SimulationEngine


class SimulationThread(QThread):
    finished_ok = Signal(object)  # özet sözlüğü
    failed = Signal(str)

    def __init__(self, config: SimConfig):
        super().__init__()
        self.buffer: deque = deque()
        self.engine = SimulationEngine(config, on_record=self.buffer.append)

    def run(self) -> None:
        try:
            self.finished_ok.emit(self.engine.run())
        except Exception:  # arayüz çökmesin; hata kullanıcıya gösterilir
            self.failed.emit(traceback.format_exc())

    def drain(self) -> list:
        out = []
        while True:
            try:
                out.append(self.buffer.popleft())
            except IndexError:
                return out


class AnalysisThread(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(object, object)  # satırlar, ek bilgi
    failed = Signal(str)

    def __init__(self, job: Callable[..., tuple[list, dict]]):
        super().__init__()
        self.job = job
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            rows, extra = self.job(progress=self.progress.emit, should_stop=self._stop.is_set)
            self.finished_ok.emit(rows, extra)
        except ConfigError as e:
            self.failed.emit(str(e))
        except Exception:
            self.failed.emit(traceback.format_exc())
