"""Ayrık olay zamanlayıcısı.

Gerçek zamanlı ve hızlandırılmış modlar aynı olay kuyruğunu kullanır;
gerçek zamanlı mod yalnızca olaylar arasında duvar saatine göre bekler.
"""

from __future__ import annotations

import heapq
import itertools
from typing import Callable

Event = Callable[[float], None]


class EventScheduler:
    def __init__(self):
        self._queue: list[tuple[float, int, Event]] = []
        self._counter = itertools.count()  # aynı zamanlı olaylarda ekleme sırasını korur
        self.now = 0.0

    def schedule(self, time_s: float, event: Event) -> None:
        if time_s < self.now:
            raise ValueError(f"Geçmişe olay planlanamaz: {time_s} < {self.now}")
        heapq.heappush(self._queue, (time_s, next(self._counter), event))

    def peek_time(self) -> float | None:
        return self._queue[0][0] if self._queue else None

    def run_next(self) -> bool:
        if not self._queue:
            return False
        time_s, _, event = heapq.heappop(self._queue)
        self.now = time_s
        event(time_s)
        return True

    def __len__(self) -> int:
        return len(self._queue)
