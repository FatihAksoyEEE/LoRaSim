"""Link-level alım modeli: dalga şekli üretmeden paket başına hata kararı.

Adımlar:
1. Algılama: RSSI < hassasiyet ise paket algılanmaz. Verici–alıcı frekans farkı
   (kristal hatası + Doppler) ±%25 BW toleransını aşarsa paket çözülemez; tolerans
   içindeki fark preamble ile kestirilip düzeltildiği için ek kayıp yaratmaz.
2. Explicit header: 8 sembol, CR 4/8 (tek sembol hatası düzeltilir). Header
   bozulursa paket alıcıda düşer.
3. Payload: Çerçeve bitleri, her biri (4/CR'nin paydası) sembol uzunluğunda
   ve 4·(SF-2·DE) veri biti taşıyan interleaver bloklarına bölünür. Bloktaki
   sembol hataları Binom(n, SER) ile çekilir. CR 4/5 ve 4/6 hata düzeltemez;
   CR 4/7 ve 4/8 blok başına bir sembol hatasını düzeltir.
4. Bozulan bloklarda, hatalı her sembol için ilgili bit aralığında rastgele
   bitler çevrilir; ardından gerçek CRC kontrolü yapılır. Böylece CRC'nin
   yakalayamadığı bozulmalar da kendiliğinden ortaya çıkar.

Bu bir yaklaşımdır: Header bloğunun SF-2 düşük hız kipi ve Gray eşlemenin
bit dağılımı basitleştirilmiştir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np

from lorasim.lora.crc import check_crc
from lorasim.lora.error_model import symbol_error_rate
from lorasim.lora import sx1276_config as hw
from lorasim.lora.lora_parameters import LoRaPhy

HEADER_SYMBOLS = 8
HEADER_CODEWORD = 8  # header her zaman CR 4/8 ile kodlanır


class RxStatus(str, Enum):
    OK = "ok"
    NOT_DETECTED = "not_detected"
    HEADER_ERROR = "header_error"
    CRC_ERROR = "crc_error"
    CORRUPTED = "corrupted_undetected"  # CRC kapalıyken ya da CRC yakalayamadığında
    COLLISION = "collision"  # capture eşiğini sağlamayan girişim/çakışma
    HALF_DUPLEX = "half_duplex"  # alıcı o sırada kendisi gönderim yapıyordu
    FREQ_OFFSET = "freq_offset"  # frekans farkı toleransı aşıldı


@dataclass(frozen=True)
class RxResult:
    status: RxStatus
    received_frame: bytes | None
    bit_errors: int
    bits_compared: int
    symbol_errors: int
    symbols_compared: int

    @property
    def delivered(self) -> bool:
        """Paket üst katmana teslim edildi mi (içeriği bozuk olsa bile)."""
        return self.status in (RxStatus.OK, RxStatus.CORRUPTED)


def _block_ok(errors: int, codeword_len: int) -> bool:
    return errors == 0 or (codeword_len >= 7 and errors == 1)


class LinkLevelModel:
    def __init__(self, phy: LoRaPhy, sensitivity_dbm: float, rng: np.random.Generator):
        self.phy = phy
        self.sensitivity_dbm = sensitivity_dbm
        self.rng = rng

    def receive(self, frame: bytes, rssi_dbm: float, snr_db: float, freq_offset_hz: float = 0.0) -> RxResult:
        phy, rng = self.phy, self.rng
        if rssi_dbm < self.sensitivity_dbm:
            return RxResult(RxStatus.NOT_DETECTED, None, 0, 0, 0, 0)
        if abs(freq_offset_hz) > hw.FREQ_OFFSET_TOLERANCE_BW * phy.bandwidth_hz:
            return RxResult(RxStatus.FREQ_OFFSET, None, 0, 0, 0, 0)

        ser = symbol_error_rate(phy.sf, snr_db)
        symbol_errors = 0
        symbols = 0

        if not phy.implicit_header:
            k = int(rng.binomial(HEADER_SYMBOLS, ser)) if ser > 0 else 0
            symbol_errors += k
            symbols += HEADER_SYMBOLS
            if not _block_ok(k, HEADER_CODEWORD):
                return RxResult(RxStatus.HEADER_ERROR, None, 0, 0, symbol_errors, symbols)

        n = phy.coding_rate
        bits_per_block = 4 * phy.bits_per_symbol
        total_bits = 8 * len(frame)
        n_blocks = math.ceil(total_bits / bits_per_block)
        errors = rng.binomial(n, ser, n_blocks) if ser > 0 else np.zeros(n_blocks, dtype=int)
        symbol_errors += int(errors.sum())
        symbols += n * n_blocks

        bits = np.unpackbits(np.frombuffer(frame, dtype=np.uint8))
        flip_prob = 0.5 * 4 / n  # hatalı sembolün veri bitine düşen ortalama hata payı
        for b in np.flatnonzero(errors):
            k = int(errors[b])
            if _block_ok(k, n):
                continue
            lo = b * bits_per_block
            hi = min(lo + bits_per_block, total_bits)
            n_flip = min(hi - lo, sum(max(1, int(rng.binomial(phy.bits_per_symbol, flip_prob)))
                                      for _ in range(k)))
            bits[lo + rng.choice(hi - lo, n_flip, replace=False)] ^= 1

        received = np.packbits(bits).tobytes()
        bit_errors = int(np.unpackbits(np.frombuffer(bytes(a ^ b for a, b in zip(frame, received)),
                                                     dtype=np.uint8)).sum())
        if phy.crc_enabled and not check_crc(received):
            status = RxStatus.CRC_ERROR
        elif bit_errors:
            status = RxStatus.CORRUPTED
        else:
            status = RxStatus.OK
        return RxResult(status, received, bit_errors, total_bits, symbol_errors, symbols)
