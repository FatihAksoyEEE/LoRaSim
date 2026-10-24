"""Cihaz tanımı ve yapılandırmadan cihaz listesi oluşturma."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from lorasim.config import DeviceSpec, MobilityConfig, SimConfig
from lorasim.devices.mobility import Circular, ConstantVelocity, RandomWalk, Route, Static, Trajectory


@dataclass
class Device:
    id: str
    role: str  # "tx" | "rx"
    trajectory: Trajectory
    frequency_offset_ppm: float = 0.0
    target: Optional[str] = None  # verici için hedef alıcı kimliği

    def position(self, t: float) -> np.ndarray:
        return self.trajectory.position(t)

    def velocity(self, t: float) -> np.ndarray:
        return self.trajectory.velocity(t)


def _moves(role: str, moving: str) -> bool:
    return moving == "all" or (moving == "transmitters" and role == "tx") or (moving == "receivers" and role == "rx")


def _trajectory(spec: DeviceSpec, mob: MobilityConfig, rng: np.random.Generator) -> Trajectory:
    p0 = (spec.x, spec.y, spec.z)
    custom = spec.speed_mps is not None or spec.heading_deg is not None or spec.route is not None
    if not _moves(spec.role, mob.moving) and not custom:
        return Static(p0)
    speed = mob.speed_mps if spec.speed_mps is None else spec.speed_mps
    if spec.route is not None:
        return Route([p0] + [(x, y, spec.z) for x, y in spec.route], speed, mob.route_loop)
    if spec.heading_deg is not None:
        return ConstantVelocity(p0, speed, spec.heading_deg)
    if speed == 0:
        return Static(p0)
    if mob.model == "constant":
        return ConstantVelocity(p0, speed, mob.heading_deg)
    if mob.model == "random_walk":
        return RandomWalk(p0, speed, mob.random_turn_interval_s, np.random.default_rng(rng.integers(2**63)))
    if mob.model == "route":
        return Route([p0] + [(spec.x + dx, spec.y + dy, spec.z) for dx, dy in mob.route], speed, mob.route_loop)
    return Circular(p0, mob.circle_radius_m, speed)


def device_specs(config: SimConfig, rng: np.random.Generator) -> list[DeviceSpec]:
    topo = config.topology
    if topo.mode == "cartesian":
        return list(topo.devices)
    if topo.mode == "distance":
        specs = [DeviceSpec("RX1", "rx")]
        n = topo.num_transmitters
        for i in range(n):
            a = 2 * math.pi * i / n
            specs.append(DeviceSpec(f"TX{i + 1}", "tx", topo.distance_m * math.cos(a), topo.distance_m * math.sin(a)))
        return specs
    specs = [DeviceSpec(f"RX{i + 1}", "rx", *rng.uniform((0, 0), (topo.area_width_m, topo.area_height_m)))
             for i in range(topo.num_receivers)]
    specs += [DeviceSpec(f"TX{i + 1}", "tx", *rng.uniform((0, 0), (topo.area_width_m, topo.area_height_m)))
              for i in range(topo.num_transmitters)]
    return specs


def build_devices(config: SimConfig, rng: np.random.Generator) -> list[Device]:
    specs = device_specs(config, rng)
    ch = config.channel
    devices = []
    for s in specs:
        if s.frequency_offset_ppm is not None:
            ppm = s.frequency_offset_ppm
        elif ch.frequency_offset_enabled:
            ppm = float(rng.uniform(-ch.crystal_ppm, ch.crystal_ppm))
        else:
            ppm = 0.0
        devices.append(Device(s.id, s.role, _trajectory(s, config.mobility, rng), ppm, s.target))
    receivers = [d for d in devices if d.role == "rx"]
    for d in devices:
        if d.role == "tx" and d.target is None:
            p = d.position(0.0)
            d.target = min(receivers, key=lambda r: float(np.linalg.norm(r.position(0.0) - p))).id
    return devices
