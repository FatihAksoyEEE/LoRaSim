import numpy as np
import pytest

from lorasim.lora.error_model import bit_error_rate_uncoded, symbol_error_rate


@pytest.mark.parametrize("sf", range(7, 13))
def test_ser_monotonic_and_bounded(sf):
    s = [symbol_error_rate(sf, x) for x in np.arange(-35, 10, 0.5)]
    assert all(0 <= v <= 1 for v in s)
    assert all(a >= b for a, b in zip(s, s[1:]))


def test_higher_sf_more_robust():
    assert symbol_error_rate(12, -15) < symbol_error_rate(9, -15) < symbol_error_rate(7, -15)


def test_infinite_snr():
    assert symbol_error_rate(7, float("inf")) == 0.0


@pytest.mark.parametrize("snr_db", [-12.0, -10.0, -8.0])
def test_ser_matches_monte_carlo_sf7(snr_db):
    """Dechirp sonrası FFT bin modeli: sinyal tek bir binde, gürültü tüm binlerde."""
    rng = np.random.default_rng(123)
    m, trials = 128, 30000
    bins = (rng.standard_normal((trials, m)) + 1j * rng.standard_normal((trials, m))) / np.sqrt(2)
    bins[:, 0] += np.sqrt(10 ** (snr_db / 10) * m)
    mc = np.mean(np.argmax(np.abs(bins), axis=1) != 0)
    model = symbol_error_rate(7, snr_db)
    sigma = np.sqrt(model * (1 - model) / trials)
    assert abs(mc - model) < 4 * sigma + 1e-4


def test_ber_relation():
    ser = symbol_error_rate(8, -12)
    assert bit_error_rate_uncoded(8, -12) == pytest.approx(ser * 128 / 255)
