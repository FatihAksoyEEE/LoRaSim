"""LoRa CSS alıcı zinciri: senkronizasyon, CFO düzeltme, dechirp+FFT, çözme.

Varsayım: Çerçeve başlangıcı (zamanlama) bilinir. Taşıyıcı frekans kayması
(CFO) preamble üzerinden kestirilir: tam sayı kısmı dechirp edilmiş preamble
sembollerinin en büyük FFT bininden, kesirli kısmı ardışık preamble
sembollerindeki o binin faz ilerlemesinden.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from lorasim.lora.modulation import (
    FIRST_BLOCK_SYMBOLS, HEADER_NIBBLES, SymbolLayout, chirp, deinterleave, gray_encode, hamming_decode,
    nibbles_to_bytes, parse_header, sync_word_symbols, whiten,
)


@dataclass
class DemodResult:
    detected: bool
    sync_ok: bool
    header_ok: bool
    frame: Optional[bytes]  # çözülen payload (+ alınan CRC baytları)
    symbols: Optional[np.ndarray]  # alınan FFT binleri (header+payload)
    cfo_hz: float = 0.0


def dechirp_bins(rx: np.ndarray, sf: int) -> tuple[np.ndarray, np.ndarray]:
    """(sembol sayısı × M) matris → (en büyük bin, FFT matrisi)."""
    m = 2 ** sf
    spec = np.fft.fft(rx.reshape(-1, m) * np.conj(chirp(sf))[None, :], axis=1)
    return np.argmax(np.abs(spec), axis=1), spec


def estimate_cfo_bins(preamble: np.ndarray, sf: int) -> float:
    m = 2 ** sf
    peaks, spec = dechirp_bins(preamble, sf)
    k = int(np.bincount(peaks, minlength=m).argmax())
    phasors = spec[:, k]
    eps = np.angle(np.sum(phasors[1:] * np.conj(phasors[:-1]))) / (2 * np.pi)
    k_signed = k - m if k >= m // 2 else k
    # Kesirli kısım tam sayı binine göre ±0.5 aralığına sarılır.
    return k_signed + float(eps)


def demodulate(rx: np.ndarray, sf: int, bandwidth_hz: float, cr: int, crc: bool, preamble: int,
               layout: SymbolLayout, payload_len: Optional[int], sync_word: int, iq_inverted: bool,
               cfo_tolerance_hz: float) -> DemodResult:
    m = 2 ** sf
    if iq_inverted:
        rx = np.conj(rx)
    pre = rx[: preamble * m]
    cfo_bins = estimate_cfo_bins(pre, sf)
    cfo_hz = cfo_bins * bandwidth_hz / m
    if abs(cfo_hz) > cfo_tolerance_hz:
        return DemodResult(False, False, False, None, None, cfo_hz)
    n = np.arange(len(rx))
    rx = rx * np.exp(-2j * np.pi * cfo_bins * n / m)

    sw_start = preamble * m
    sw_bins, _ = dechirp_bins(rx[sw_start: sw_start + 2 * m], sf)
    expected = sync_word_symbols(sync_word)
    if any(min(abs(int(b) - e), m - abs(int(b) - e)) > 2 for b, e in zip(sw_bins, expected)):
        return DemodResult(True, False, False, None, None, cfo_hz)

    data_start = sw_start + 2 * m + int(2.25 * m)
    data = rx[data_start:]
    data = data[: (len(data) // m) * m]
    bins, _ = dechirp_bins(data, sf)

    # İlk blok: SF-2 bit/sembol, CR 4/8
    k1 = sf - 2
    first = [int(gray_encode(round(int(b) / 4) % (2 ** k1))) for b in bins[:FIRST_BLOCK_SYMBOLS]]
    nibbles = [hamming_decode(cw, 8)[0] for cw in deinterleave(first, k1)]
    if not layout.implicit_header:
        hdr = parse_header(nibbles)
        if hdr is None:
            return DemodResult(True, True, False, None, bins, cfo_hz)
        payload_len, cr, crc = hdr
        nibbles = nibbles[HEADER_NIBBLES:]
    k = layout.payload_bits_per_symbol
    scale = 4 if layout.ldro else 1
    rest = bins[FIRST_BLOCK_SYMBOLS:]
    for i in range(0, len(rest) - cr + 1, cr):
        block = [int(gray_encode(round(int(b) / scale) % (2 ** k))) for b in rest[i:i + cr]]
        nibbles += [hamming_decode(cw, cr)[0] for cw in deinterleave(block, k)]
    n_bytes = payload_len + (2 if crc else 0)
    raw = nibbles_to_bytes(nibbles[: 2 * n_bytes])
    payload = whiten(raw[:payload_len])
    return DemodResult(True, True, True, payload + raw[payload_len:n_bytes], bins, cfo_hz)
