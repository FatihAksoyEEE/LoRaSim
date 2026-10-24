"""Hareket modelleri.

Her model konumu ve hızı zamanın saf fonksiyonu olarak verir: position(t), velocity(t).
Böylece kanal hesabı ve arayüz aynı anda, kilit gerektirmeden konum sorgulayabilir.
Koordinatlar metre; yön açısı +x ekseninden saat yönünün tersine derece.
"""

from __future__ import annotations

import math
import threading

import numpy as np


def _heading_vector(heading_deg: float) -> np.ndarray:
    a = math.radians(heading_deg)
    return np.array([math.cos(a), math.sin(a), 0.0])


class Trajectory:
    def position(self, t: float) -> np.ndarray:
        raise NotImplementedError

    def velocity(self, t: float) -> np.ndarray:
        raise NotImplementedError

    @property
    def is_moving(self) -> bool:
        return True


class Static(Trajectory):
    def __init__(self, p0):
        self.p0 = np.asarray(p0, dtype=float)

    def position(self, t: float) -> np.ndarray:
        return self.p0.copy()

    def velocity(self, t: float) -> np.ndarray:
        return np.zeros(3)

    @property
    def is_moving(self) -> bool:
        return False


class ConstantVelocity(Trajectory):
    def __init__(self, p0, speed_mps: float, heading_deg: float):
        self.p0 = np.asarray(p0, dtype=float)
        self.v = speed_mps * _heading_vector(heading_deg)

    def position(self, t: float) -> np.ndarray:
        return self.p0 + self.v * t

    def velocity(self, t: float) -> np.ndarray:
        return self.v.copy()


class RandomWalk(Trajectory):
    """Sabit hızla, her `turn_interval_s` saniyede rastgele yeni bir yöne giden hareket.

    Segmentler ihtiyaç duyuldukça cihaza özel bir rastgele üreteçten üretilir; aynı seed
    ile her zaman aynı yol izlenir.
    """

    def __init__(self, p0, speed_mps: float, turn_interval_s: float, rng: np.random.Generator):
        self.speed = speed_mps
        self.dt = turn_interval_s
        self.rng = rng
        self._starts = [np.asarray(p0, dtype=float)]
        self._velocities: list[np.ndarray] = []
        self._lock = threading.Lock()

    def _segment(self, t: float) -> int:
        k = max(int(t // self.dt), 0)
        with self._lock:
            while len(self._velocities) <= k:
                v = self.speed * _heading_vector(self.rng.uniform(0, 360))
                self._velocities.append(v)
                self._starts.append(self._starts[-1] + v * self.dt)
        return k

    def position(self, t: float) -> np.ndarray:
        k = self._segment(t)
        return self._starts[k] + self._velocities[k] * (t - k * self.dt)

    def velocity(self, t: float) -> np.ndarray:
        return self._velocities[self._segment(t)].copy()


class Route(Trajectory):
    """Nokta listesi boyunca sabit hızla hareket. loop=True ise başa dönüp tekrarlar."""

    def __init__(self, points, speed_mps: float, loop: bool):
        pts = [np.asarray(p, dtype=float) for p in points]
        if loop and len(pts) > 1 and not np.allclose(pts[0], pts[-1]):
            pts.append(pts[0])
        self.points = pts
        self.speed = speed_mps
        self.loop = loop
        self.lengths = [float(np.linalg.norm(b - a)) for a, b in zip(pts, pts[1:])]
        self.total = sum(self.lengths)

    def _locate(self, t: float) -> tuple[int, float]:
        if self.total == 0 or self.speed == 0:
            return -1, 0.0
        s = self.speed * max(t, 0.0)
        if self.loop:
            s %= self.total
        elif s >= self.total:
            return -1, 0.0
        for i, seg in enumerate(self.lengths):
            if s <= seg or i == len(self.lengths) - 1:
                return i, s
            s -= seg
        return -1, 0.0

    def position(self, t: float) -> np.ndarray:
        i, s = self._locate(t)
        if i < 0:
            return (self.points[-1] if self.total and self.speed and t > 0 else self.points[0]).copy()
        a, b = self.points[i], self.points[i + 1]
        return a + (b - a) * (s / self.lengths[i] if self.lengths[i] else 0.0)

    def velocity(self, t: float) -> np.ndarray:
        i, _ = self._locate(t)
        if i < 0 or not self.lengths[i]:
            return np.zeros(3)
        return (self.points[i + 1] - self.points[i]) / self.lengths[i] * self.speed


class Circular(Trajectory):
    """Başlangıç noktasından geçen, merkezi başlangıcın `radius` kadar -x yönünde olduğu çember."""

    def __init__(self, p0, radius_m: float, speed_mps: float):
        self.p0 = np.asarray(p0, dtype=float)
        self.r = radius_m
        self.center = self.p0 - np.array([radius_m, 0.0, 0.0])
        self.omega = speed_mps / radius_m

    def position(self, t: float) -> np.ndarray:
        a = self.omega * t
        return self.center + self.r * np.array([math.cos(a), math.sin(a), 0.0])

    def velocity(self, t: float) -> np.ndarray:
        a = self.omega * t
        return self.r * self.omega * np.array([-math.sin(a), math.cos(a), 0.0])
