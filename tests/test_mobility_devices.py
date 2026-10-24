import math

import numpy as np
import pytest

from lorasim.config import ConfigError, DeviceSpec, SimConfig
from lorasim.devices.device import build_devices
from lorasim.devices.mobility import Circular, ConstantVelocity, RandomWalk, Route, Static


def test_static():
    s = Static((1, 2, 3))
    assert np.allclose(s.position(100), (1, 2, 3)) and np.allclose(s.velocity(5), 0) and not s.is_moving


def test_constant_velocity():
    c = ConstantVelocity((0, 0, 0), 10.0, 90.0)
    assert np.allclose(c.position(10), (0, 100, 0), atol=1e-9)
    assert np.allclose(c.velocity(3), (0, 10, 0), atol=1e-9)


def test_route_without_loop_stops_at_end():
    r = Route([(0, 0, 0), (100, 0, 0), (100, 50, 0)], 10.0, loop=False)
    assert np.allclose(r.position(5), (50, 0, 0))
    assert np.allclose(r.position(12), (100, 20, 0))
    assert np.allclose(r.velocity(12), (0, 10, 0))
    assert np.allclose(r.position(1000), (100, 50, 0)) and np.allclose(r.velocity(1000), 0)


def test_route_loop_returns_to_start():
    r = Route([(0, 0, 0), (30, 0, 0), (30, 40, 0)], 1.0, loop=True)  # 30 + 40 + 50 = 120 m
    assert r.total == pytest.approx(120)
    assert np.allclose(r.position(120), (0, 0, 0), atol=1e-9)
    assert np.allclose(r.position(135), (15, 0, 0), atol=1e-9)


def test_circular_keeps_radius_and_period():
    c = Circular((100, 0, 0), 100.0, 10.0)
    for t in np.linspace(0, 200, 17):
        assert np.linalg.norm(c.position(t) - c.center) == pytest.approx(100)
        assert np.linalg.norm(c.velocity(t)) == pytest.approx(10)
    assert np.allclose(c.position(2 * math.pi * 100 / 10), (100, 0, 0), atol=1e-6)


def test_random_walk_speed_and_reproducibility():
    a = RandomWalk((0, 0, 0), 5.0, 2.0, np.random.default_rng(1))
    b = RandomWalk((0, 0, 0), 5.0, 2.0, np.random.default_rng(1))
    c = RandomWalk((0, 0, 0), 5.0, 2.0, np.random.default_rng(2))
    for t in (0.5, 3.0, 17.3, 40.0):
        assert np.allclose(a.position(t), b.position(t))
        assert np.linalg.norm(a.velocity(t)) == pytest.approx(5.0)
    assert not np.allclose(a.position(40), c.position(40))
    # Bir segment içinde yol = hız × süre
    assert np.linalg.norm(a.position(1.5) - a.position(0.5)) == pytest.approx(5.0)


def cfg(**topo):
    c = SimConfig()
    for k, v in topo.items():
        setattr(c.topology, k, v)
    return c


def test_distance_mode_places_transmitters_on_circle():
    c = cfg(num_transmitters=6, distance_m=500.0)
    devs = build_devices(c, np.random.default_rng(0))
    rx = [d for d in devs if d.role == "rx"]
    txs = [d for d in devs if d.role == "tx"]
    assert len(rx) == 1 and len(txs) == 6
    assert all(np.linalg.norm(t.position(0) - rx[0].position(0)) == pytest.approx(500) for t in txs)
    assert {t.target for t in txs} == {"RX1"}
    assert len({t.id for t in devs}) == 7


def test_random_mode_within_area_and_reproducible():
    c = cfg(mode="random", num_transmitters=30, num_receivers=3, area_width_m=1000, area_height_m=400)
    a = build_devices(c, np.random.default_rng(5))
    b = build_devices(c, np.random.default_rng(5))
    for d in a:
        x, y, _ = d.position(0)
        assert 0 <= x <= 1000 and 0 <= y <= 400
    assert [tuple(d.position(0)) for d in a] == [tuple(d.position(0)) for d in b]


def test_cartesian_nearest_target_and_explicit_target():
    c = cfg(mode="cartesian", devices=[
        DeviceSpec("G1", "rx", 0, 0), DeviceSpec("G2", "rx", 1000, 0),
        DeviceSpec("A", "tx", 100, 0), DeviceSpec("B", "tx", 900, 0), DeviceSpec("C", "tx", 950, 0, target="G1"),
    ])
    c.validate()
    t = {d.id: d.target for d in build_devices(c, np.random.default_rng(0)) if d.role == "tx"}
    assert t == {"A": "G1", "B": "G2", "C": "G1"}


def test_moving_groups_and_user_override():
    c = cfg(num_transmitters=2)
    c.mobility.moving = "transmitters"
    c.mobility.speed_mps = 3.0
    devs = {d.id: d for d in build_devices(c, np.random.default_rng(0))}
    assert devs["TX1"].trajectory.is_moving and not devs["RX1"].trajectory.is_moving
    c = cfg(mode="cartesian", devices=[DeviceSpec("R", "rx"), DeviceSpec("T", "tx", 10, 0, speed_mps=7.0, heading_deg=180)])
    devs = {d.id: d for d in build_devices(c, np.random.default_rng(0))}
    assert np.allclose(devs["T"].velocity(0), (-7, 0, 0), atol=1e-9)


@pytest.mark.parametrize("model", ["constant", "random_walk", "route", "circular"])
def test_each_mobility_model_builds(model):
    c = cfg()
    c.mobility.moving = "all"
    c.mobility.model = model
    c.mobility.route = [[100, 0], [100, 100]]
    devs = build_devices(c, np.random.default_rng(0))
    assert all(d.trajectory.is_moving for d in devs)


def test_topology_validation():
    with pytest.raises(ConfigError):
        cfg(num_receivers=2).validate()  # mesafe modunda tek alıcı
    with pytest.raises(ConfigError):
        cfg(mode="cartesian", devices=[DeviceSpec("A", "tx")]).validate()
    with pytest.raises(ConfigError):
        cfg(mode="cartesian", devices=[DeviceSpec("A", "tx", target="X"), DeviceSpec("B", "rx")]).validate()
    c = cfg()
    c.mobility.moving, c.mobility.model = "all", "route"
    with pytest.raises(ConfigError):
        c.validate()
