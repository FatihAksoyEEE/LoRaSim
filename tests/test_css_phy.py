import itertools

import numpy as np
import pytest

from lorasim.config import LoRaConfig, SimConfig
from lorasim.lora.demodulation import dechirp_bins, estimate_cfo_bins
from lorasim.lora.error_model import symbol_error_rate
from lorasim.lora.lora_parameters import LoRaPhy
from lorasim.lora.modulation import (
    chirp, chirp_matrix, deinterleave, gray_decode, gray_encode, hamming_decode, hamming_encode, header_nibbles,
    interleave, parse_header, whiten,
)
from lorasim.simulation.css_phy_model import CssPhyModel
from lorasim.simulation.link_level_model import LinkLevelModel, RxStatus
from lorasim.simulation.packet_manager import PacketFactory
from lorasim.simulation.simulation_engine import SimulationEngine


def model(seed=0, **kw):
    cfg = LoRaConfig(**kw)
    return CssPhyModel(LoRaPhy.from_config(cfg), -200.0, np.random.default_rng(seed)), cfg


def frame(cfg, seed=0):
    return PacketFactory("T", "R", cfg.payload_bytes, cfg.crc_enabled, np.random.default_rng(seed)).create(0).frame


# --- yapı taşları -------------------------------------------------------------
def test_gray_roundtrip():
    v = np.arange(4096)
    assert np.array_equal(gray_decode(gray_encode(v)), v)
    assert all(bin(int(gray_encode(k)) ^ int(gray_encode(k + 1))).count("1") == 1 for k in range(4095))


def test_whitening_is_involution():
    data = bytes(range(256))
    assert whiten(whiten(data)) == data and whiten(data) != data


@pytest.mark.parametrize("cr", [7, 8])
def test_hamming_corrects_single_errors(cr):
    for nib in range(16):
        cw = hamming_encode(nib, cr)
        assert hamming_decode(cw, cr) == (nib, False)
        for i in range(cr):
            bad = list(cw)
            bad[i] ^= 1
            assert hamming_decode(bad, cr)[0] == nib


def test_hamming_48_detects_double_errors():
    cw = hamming_encode(0b1011, 8)
    bad = list(cw)
    bad[0] ^= 1
    bad[1] ^= 1
    assert hamming_decode(bad, 8)[1] is True


@pytest.mark.parametrize("cr", [5, 6])
def test_hamming_low_rates_detect(cr):
    cw = hamming_encode(0b0110, cr)
    bad = list(cw)
    bad[1] ^= 1
    assert hamming_decode(bad, cr)[1] is True


@pytest.mark.parametrize("sf_eff, n", [(5, 8), (7, 5), (10, 8), (12, 6)])
def test_interleaver_roundtrip(sf_eff, n):
    rng = np.random.default_rng(0)
    cws = rng.integers(0, 2, (sf_eff, n)).tolist()
    assert deinterleave(interleave(cws, sf_eff), sf_eff) == cws


def test_interleaver_spreads_symbol_error_over_codewords():
    """Bir sembolün bozulması her kod sözcüğünde en fazla bir biti etkiler."""
    cws = [[0] * 8 for _ in range(7)]
    syms = interleave(cws, 7)
    syms[3] ^= 0x7F
    damaged = deinterleave(syms, 7)
    assert all(sum(cw) == 1 for cw in damaged)


def test_header_roundtrip_and_checksum():
    for pl, cr, crc in itertools.product((0, 20, 255), (5, 6, 7, 8), (True, False)):
        assert parse_header(header_nibbles(pl, cr, crc)) == (pl, cr, crc)
    bad = header_nibbles(20, 5, True)
    bad[0] ^= 1
    assert parse_header(bad) is None


@pytest.mark.parametrize("sf", range(7, 13))
def test_chirps_are_orthogonal(sf):
    m = 2 ** sf
    syms = np.array([0, 1, m // 2, m - 1])
    bins, _ = dechirp_bins(chirp_matrix(sf, syms).ravel(), sf)
    assert np.array_equal(bins, syms)
    assert np.allclose(chirp(sf, 0, down=True), np.conj(chirp(sf)))


def test_cfo_estimator():
    sf, m = 8, 256
    pre = chirp_matrix(sf, np.zeros(8)).ravel()
    n = np.arange(len(pre))
    for cfo in (0.0, 3.3, -7.45, 40.2):
        assert estimate_cfo_bins(pre * np.exp(2j * np.pi * cfo * n / m), sf) == pytest.approx(cfo, abs=1e-6)


# --- uçtan uca ---------------------------------------------------------------
@pytest.mark.parametrize("sf, cr, crc, ih, ldro", [
    (sf, cr, crc, ih, ldro) for sf in (7, 9, 12) for cr in (5, 8) for crc in (True, False) for ih in (False, True)
    for ldro in (None, True)])
def test_noiseless_roundtrip_and_symbol_count(sf, cr, crc, ih, ldro):
    m, cfg = model(spreading_factor=sf, coding_rate=cr, crc_enabled=crc, implicit_header=ih, ldro=ldro,
                   payload_bytes=23)
    f = frame(cfg)
    sig, syms = m.transmit(f)
    phy = m.phy
    assert len(syms) == phy.payload_symbols(23)
    # Dalga şekli uzunluğu = (preamble + 2 sync + 2.25 SFD + payload) sembol
    assert len(sig) == pytest.approx((phy.preamble_symbols + 4.25 + len(syms)) * 2 ** sf)
    r = m.receive(f, -50.0, float("inf"))
    assert r.status == RxStatus.OK and r.received_frame == f and r.bit_errors == 0


def test_max_payload_sf12_roundtrip():
    m, cfg = model(spreading_factor=12, coding_rate=8, payload_bytes=255)
    f = frame(cfg)
    assert m.receive(f, -50.0, float("inf")).status == RxStatus.OK


@pytest.mark.parametrize("fraction", [0.0, 0.05, -0.12, 0.2, -0.24])
def test_frequency_offset_within_tolerance_is_corrected(fraction):
    m, cfg = model(spreading_factor=8)
    r = m.receive(frame(cfg), -50.0, 10.0, fraction * 125e3 + 17.0)
    assert r.status == RxStatus.OK


def test_frequency_offset_beyond_tolerance():
    m, cfg = model(spreading_factor=8)
    assert m.receive(frame(cfg), -50.0, 10.0, 0.3 * 125e3).status == RxStatus.FREQ_OFFSET


def test_sync_word_and_iq_mismatch_not_detected():
    m, cfg = model()
    m.rx_sync_word = 0x34
    assert m.receive(frame(cfg), -50.0, 20.0).status == RxStatus.NOT_DETECTED
    m, cfg = model(iq_inverted=False)
    m.rx_iq_inverted = True
    assert m.receive(frame(cfg), -50.0, 20.0).status == RxStatus.NOT_DETECTED
    m, cfg = model()
    m.iq_inverted = m.rx_iq_inverted = True
    assert m.receive(frame(cfg), -50.0, 20.0).status == RxStatus.OK


def test_below_sensitivity():
    m, cfg = model()
    m.sensitivity_dbm = -120.0
    assert m.receive(frame(cfg), -125.0, 20.0).status == RxStatus.NOT_DETECTED


def _stats(m, snr, n, seed=1):
    rng = np.random.default_rng(seed)
    m.rng = rng
    f = PacketFactory("T", "R", 20, True, rng)
    res = [m.receive(f.create(0).frame, -100.0, snr) for _ in range(n)]
    per = np.mean([r.status != RxStatus.OK for r in res])
    ser = sum(r.symbol_errors for r in res) / max(sum(r.symbols_compared for r in res), 1)
    return per, ser


@pytest.mark.parametrize("sf, snr", [(7, -10.5), (7, -9.5), (9, -15.5)])
def test_css_ser_matches_theory(sf, snr):
    m, _ = model(spreading_factor=sf)
    _, ser = _stats(m, snr, 200)
    assert ser == pytest.approx(symbol_error_rate(sf, snr), rel=0.25)


@pytest.mark.parametrize("sf, cr, snrs", [(7, 5, (-10.5, -9.5, -8.5)), (7, 8, (-11.5, -10.5, -9.5)),
                                          (9, 5, (-15.5, -14.5))])
def test_css_and_link_level_per_agree(sf, cr, snrs):
    """İki model aynı SNR'de benzer PER vermeli (fark < 0.15)."""
    css, cfg = model(spreading_factor=sf, coding_rate=cr)
    ll = LinkLevelModel(LoRaPhy.from_config(cfg), -200.0, np.random.default_rng(0))
    for snr in snrs:
        p_css, _ = _stats(css, snr, 200)
        p_ll, _ = _stats(ll, snr, 400)
        assert abs(p_css - p_ll) < 0.15, (snr, p_css, p_ll)


def test_engine_with_css_model_matches_link_level():
    def run(model_name):
        c = SimConfig()
        c.run.mode, c.run.seed, c.run.model = "accelerated", 2, model_name
        c.traffic.max_packets, c.traffic.interval_s, c.traffic.duty_cycle_limit = 150, 5.0, None
        c.ack.enabled = False
        c.channel.environment, c.topology.distance_m = "urban", 1200.0
        return SimulationEngine(c).run()
    css, ll = run("css_phy"), run("link_level")
    assert css["model"] == "css_phy"
    assert css["success_rate"] == pytest.approx(ll["success_rate"], abs=0.1)


def test_compare_models_analysis(tmp_path):
    from lorasim.export.report_exporter import model_comparison_lines, plot_model_comparison
    from lorasim.simulation.analysis import compare_models
    c = SimConfig()
    c.run.seed = 3
    rows = compare_models(c, [-12.0, -9.5, -6.0], packets=80)
    assert [r["snr_db"] for r in rows] == [-12.0, -9.5, -6.0]
    assert rows[0]["per_css_phy"] > 0.9 and rows[-1]["per_css_phy"] < 0.05
    assert rows[0]["per_link_level"] > 0.9 and rows[-1]["per_link_level"] < 0.05
    assert abs(rows[1]["per_css_phy"] - rows[1]["per_link_level"]) < 0.2
    plot_model_comparison(rows, tmp_path / "c.png")
    assert (tmp_path / "c.png").stat().st_size > 1000
    assert len(model_comparison_lines(rows)) == 4
