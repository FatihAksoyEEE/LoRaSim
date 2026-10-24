"""LoRa CSS fiziksel katman alım modeli.

Link-level modelle aynı arayüzü sunar (receive), ancak paketi gerçek LoRa
dalga şekli olarak üretir, kanal etkilerini sinyal üzerine uygular ve alıcıda
dechirp+FFT ile çözer:

    çerçeve → semboller → chirp dalga şekli → × kanal (genlik, faz, CFO) + AWGN
            → senkronizasyon/CFO düzeltme → demodülasyon → Hamming çözme → CRC

Kanal kazancı (yol kaybı, gölgeleme, sönümleme) SNR'ye zaten yansıdığından
burada yalnızca rastgele faz ve frekans kayması eklenir. Örnekleme fs = BW
olduğundan LoRa için tipik olan µs mertebesindeki çok yollu gecikmeler bir
örnekten kısadır; çok yollu yayılımın etkisi kanal kazancında modellenir.
"""

from __future__ import annotations

import math

import numpy as np

from lorasim.lora import sx1276_config as hw
from lorasim.lora.demodulation import demodulate
from lorasim.lora.lora_parameters import LoRaPhy
from lorasim.lora.modulation import SymbolLayout, encode_symbols, modulate
from lorasim.lora.crc import check_crc
from lorasim.simulation.link_level_model import RxResult, RxStatus


class CssPhyModel:
    def __init__(self, phy: LoRaPhy, sensitivity_dbm: float, rng: np.random.Generator,
                 sync_word: int = hw.SYNC_WORD_PRIVATE, iq_inverted: bool = False,
                 rx_sync_word: int | None = None, rx_iq_inverted: bool | None = None):
        self.phy = phy
        self.sensitivity_dbm = sensitivity_dbm
        self.rng = rng
        self.sync_word = sync_word
        self.iq_inverted = iq_inverted
        # Alıcı ayarları varsayılan olarak verici ile aynıdır; farklı verilirse uyumsuzluk sınanabilir.
        self.rx_sync_word = sync_word if rx_sync_word is None else rx_sync_word
        self.rx_iq_inverted = iq_inverted if rx_iq_inverted is None else rx_iq_inverted
        self.layout = SymbolLayout(phy.sf, phy.coding_rate, phy.ldro, phy.implicit_header)

    def transmit(self, frame: bytes) -> tuple[np.ndarray, list[int]]:
        symbols = encode_symbols(frame, self.phy.crc_enabled, self.layout)
        signal = modulate(symbols, self.phy.sf, self.phy.preamble_symbols, self.sync_word, self.iq_inverted)
        return signal, symbols

    def channel(self, signal: np.ndarray, snr_db: float, freq_offset_hz: float) -> np.ndarray:
        n = np.arange(len(signal))
        phase = self.rng.uniform(0, 2 * np.pi)
        rx = signal * np.exp(1j * (phase + 2 * np.pi * freq_offset_hz * n / self.phy.bandwidth_hz))
        if math.isfinite(snr_db):
            sigma = math.sqrt(10 ** (-snr_db / 10) / 2)
            rx = rx + sigma * (self.rng.standard_normal(len(rx)) + 1j * self.rng.standard_normal(len(rx)))
        return rx

    def receive(self, frame: bytes, rssi_dbm: float, snr_db: float, freq_offset_hz: float = 0.0) -> RxResult:
        phy = self.phy
        if rssi_dbm < self.sensitivity_dbm:
            return RxResult(RxStatus.NOT_DETECTED, None, 0, 0, 0, 0)
        signal, symbols = self.transmit(frame)
        rx = self.channel(signal, snr_db, freq_offset_hz)
        payload_len = len(frame) - (2 if phy.crc_enabled else 0)
        res = demodulate(rx, phy.sf, phy.bandwidth_hz, phy.coding_rate, phy.crc_enabled, phy.preamble_symbols,
                         self.layout, payload_len, self.rx_sync_word, self.rx_iq_inverted,
                         hw.FREQ_OFFSET_TOLERANCE_BW * phy.bandwidth_hz)
        n_sym = len(symbols)
        if not res.detected:
            return RxResult(RxStatus.FREQ_OFFSET, None, 0, 0, 0, 0)
        if not res.sync_ok:
            return RxResult(RxStatus.NOT_DETECTED, None, 0, 0, 0, 0)
        sym_err = int(np.sum(res.symbols[:n_sym] != np.asarray(symbols)))
        if not res.header_ok or res.frame is None or len(res.frame) != len(frame):
            return RxResult(RxStatus.HEADER_ERROR, None, 0, 0, sym_err, n_sym)
        received = res.frame
        bits = 8 * len(frame)
        bit_errors = int(np.unpackbits(np.frombuffer(bytes(a ^ b for a, b in zip(frame, received)),
                                                     dtype=np.uint8)).sum())
        if phy.crc_enabled and not check_crc(received):
            status = RxStatus.CRC_ERROR
        elif bit_errors:
            status = RxStatus.CORRUPTED
        else:
            status = RxStatus.OK
        return RxResult(status, received, bit_errors, bits, sym_err, n_sym)
