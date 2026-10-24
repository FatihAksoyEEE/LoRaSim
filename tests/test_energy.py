import pytest

from lorasim.config import SimConfig
from lorasim.metrics.energy import RX_CURRENT_MA, SUPPLY_VOLTAGE_V, device_energy, tx_current_ma
from lorasim.simulation.simulation_engine import SimulationEngine


def test_tx_current_table():
    assert tx_current_ma(20) == 120 and tx_current_ma(13) == 29
    assert tx_current_ma(14) == pytest.approx(43.5)
    assert tx_current_ma(30) == 120  # sınırların dışında kırpılır


def test_device_energy_formula():
    e = device_energy(1.0, 2.0, 10.0, 20.0, 125e3)
    assert e["tx_energy_j"] == pytest.approx(0.120 * SUPPLY_VOLTAGE_V)
    assert e["rx_energy_j"] == pytest.approx(2 * RX_CURRENT_MA[125e3] / 1000 * SUPPLY_VOLTAGE_V)
    assert e["sleep_time_s"] == pytest.approx(7.0)
    assert e["energy_j"] == pytest.approx(e["tx_energy_j"] + e["rx_energy_j"] + e["sleep_energy_j"])


def test_engine_energy_accounting():
    c = SimConfig()
    c.run.mode, c.run.seed = "accelerated", 1
    c.traffic.max_packets = 20
    c.topology.distance_m = 100.0
    e = SimulationEngine(c)
    s = e.run()
    tx = s["energy"]["TX1"]
    assert tx["tx_time_s"] == pytest.approx(s["transmissions"] * e.airtime_s)
    # ACK alınana kadar dinleme süresi: dönüş gecikmesi + ACK airtime
    assert tx["rx_time_s"] == pytest.approx(20 * (c.ack.turnaround_s + e.ack_airtime_s))
    rx = s["energy"]["RX1"]
    assert rx["tx_time_s"] == pytest.approx(20 * e.ack_airtime_s)
    assert rx["rx_time_s"] + rx["tx_time_s"] == pytest.approx(s["elapsed_sim_time_s"])
    assert s["energy_per_delivered_packet_mj"] == pytest.approx(tx["energy_j"] * 1e3 / 20)
    # Daha yüksek güç daha fazla enerji
    c.lora.tx_power_dbm = 20.0
    assert SimulationEngine(c).run()["tx_energy_j"] > s["tx_energy_j"]
