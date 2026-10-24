"""Ortam profillerinin tek tek ve birbirleriyle karşılaştırmalı doğrulanması."""

import numpy as np
import pytest

from lorasim.channel.environment import PROFILES
from lorasim.config import ENVIRONMENTS, SimConfig
from lorasim.simulation.simulation_engine import SimulationEngine


def success(env: str, distance: float, packets=300, seed=3) -> float:
    c = SimConfig()
    c.run.mode, c.run.seed = "accelerated", seed
    c.channel.environment = env
    c.channel.shadowing = "per_packet"  # tek bir gölgeleme çekilişine bağlı kalmamak için
    c.topology.distance_m = distance
    c.traffic.max_packets, c.traffic.interval_s = packets, 5.0
    c.traffic.duty_cycle_limit = None
    c.ack.enabled = False
    return SimulationEngine(c).run()["success_rate"]


def test_all_environments_have_profiles():
    assert set(ENVIRONMENTS) == set(PROFILES)
    for p in PROFILES.values():
        assert sum(10 ** (d / 10) for _, d in p.multipath_taps) > 0


@pytest.mark.parametrize("env", ENVIRONMENTS)
def test_single_environment_success_decreases_with_distance(env):
    """Her ortam kendi içinde: mesafe arttıkça başarı oranı düşmeli, yakında ~1, uzakta ~0 olmalı."""
    distances = np.geomspace(20, 1_000_000, 8)
    rates = [success(env, d) for d in distances]
    assert rates[0] > 0.95 and rates[-1] < 0.05
    assert all(b <= a + 0.05 for a, b in zip(rates, rates[1:]))


def test_environments_ordered_by_harshness():
    """Aynı mesafede ortamlar sertlik sırasına göre dizilmeli."""
    order = ["free_space", "open_area", "rural", "urban", "dense_urban"]
    rates = {env: success(env, 1500.0) for env in order}
    vals = [rates[e] for e in order]
    assert all(b <= a + 0.03 for a, b in zip(vals, vals[1:]))
    assert vals[0] == 1.0 and vals[-1] < 0.5


def test_indoor_shorter_range_than_open_area():
    assert success("indoor", 400.0) < success("open_area", 400.0)
