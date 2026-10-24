"""LoRa CSS verici zinciri: whitening → Hamming → interleaving → Gray → chirp.

Örnekleme hızı fs = BW (sembol başına M = 2^SF örnek). Bu hızda chirp'in
frekans sarması (wrap-around) ayrık zamanda kendiliğinden gerçekleşir.

Paket yapısı (Semtech AN1200.22 ve gr-lora çalışmalarındaki yapıya uygun):

    preamble (n upchirp) | sync word (2 sembol) | SFD (2.25 downchirp) | header+payload sembolleri

İlk blok her zaman 8 sembol, CR 4/8 ve SF-2 bit/sembol (düşük hız) ile kodlanır;
explicit modda header'ın 5 nibble'ını ve payload'ın ilk nibble'larını taşır.
Kalan bloklar CR+4 sembol uzunluğundadır ve SF-2·LDRO bit/sembol taşır.
Bu yapı airtime formülüyle aynı sembol sayısını üretir.

Basitleştirmeler: Whitening dizisi ve header sağlama toplamı gerçek SX1276
dizileriyle bit düzeyinde aynı değildir (yapı ve uzunluk aynıdır); interleaver
çapraz yapıdadır ama bit sırası Semtech'in tescilli sırasıyla birebir değildir.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

HEADER_NIBBLES = 5
FIRST_BLOCK_SYMBOLS = 8
SFD_SYMBOLS = 2.25


# --- yardımcılar -------------------------------------------------------------
def gray_encode(v: np.ndarray | int):
    return v ^ (v >> 1)


def gray_decode(g: np.ndarray | int):
    v = g
    shift = 1
    while True:
        s = v >> shift
        if np.all(s == 0):
            return v
        v = v ^ s
        shift <<= 1


def whitening_sequence(n: int) -> np.ndarray:
    """8 bitlik LFSR (x^8 + x^6 + x^5 + x^4 + 1), başlangıç 0xFF."""
    out = np.empty(n, dtype=np.uint8)
    state = 0xFF
    for i in range(n):
        out[i] = state
        for _ in range(8):
            fb = ((state >> 7) ^ (state >> 5) ^ (state >> 4) ^ (state >> 3)) & 1
            state = ((state << 1) | fb) & 0xFF
    return out


def whiten(data: bytes) -> bytes:
    return (np.frombuffer(data, dtype=np.uint8) ^ whitening_sequence(len(data))).tobytes()


def bytes_to_nibbles(data: bytes) -> list[int]:
    out = []
    for b in data:
        out += [b & 0x0F, b >> 4]
    return out


def nibbles_to_bytes(nibbles: list[int]) -> bytes:
    return bytes((nibbles[i] & 0xF) | ((nibbles[i + 1] & 0xF) << 4) for i in range(0, len(nibbles) - 1, 2))


# --- Hamming kodları -----------------------------------------------------------
def hamming_encode(nibble: int, cr: int) -> list[int]:
    """4 veri biti → cr (5..8) bitlik kod sözcüğü: [d0 d1 d2 d3 p...]."""
    d = [(nibble >> i) & 1 for i in range(4)]
    if cr == 5:
        return d + [d[0] ^ d[1] ^ d[2] ^ d[3]]
    if cr == 6:
        return d + [d[0] ^ d[1] ^ d[2], d[1] ^ d[2] ^ d[3]]
    p = [d[0] ^ d[1] ^ d[3], d[0] ^ d[2] ^ d[3], d[1] ^ d[2] ^ d[3]]
    if cr == 7:
        return d + p
    return d + p + [(sum(d) + sum(p)) & 1]


# Hamming(7,4) sendromu → hatalı bit konumu ([d0 d1 d2 d3 p0 p1 p2] düzeninde)
_SYNDROME_POS = {(1, 1, 0): 0, (1, 0, 1): 1, (0, 1, 1): 2, (1, 1, 1): 3, (1, 0, 0): 4, (0, 1, 0): 5, (0, 0, 1): 6}


def hamming_decode(bits: list[int], cr: int) -> tuple[int, bool]:
    """Kod sözcüğü → (nibble, hata_tespit_edildi). CR 4/7 ve 4/8 tek bit hatasını düzeltir."""
    b = list(bits)
    error = False
    if cr == 5:
        error = (sum(b[:5]) & 1) == 1
    elif cr == 6:
        error = (b[0] ^ b[1] ^ b[2]) != b[4] or (b[1] ^ b[2] ^ b[3]) != b[5]
    else:
        s = (b[0] ^ b[1] ^ b[3] ^ b[4], b[0] ^ b[2] ^ b[3] ^ b[5], b[1] ^ b[2] ^ b[3] ^ b[6])
        overall_ok = cr == 7 or (sum(b[:8]) & 1) == 0
        if s != (0, 0, 0):
            if cr == 8 and overall_ok:
                error = True  # çift hata: düzeltilemez
            else:
                b[_SYNDROME_POS[s]] ^= 1
        elif not overall_ok:
            pass  # yalnızca genel parite biti hatalı
    return b[0] | (b[1] << 1) | (b[2] << 2) | (b[3] << 3), error


# --- interleaving --------------------------------------------------------------
def interleave(codewords: list[list[int]], sf_eff: int) -> list[int]:
    """sf_eff kod sözcüğü (her biri n bit) → n sembol (her biri sf_eff bit). Çapraz yerleşim."""
    n = len(codewords[0])
    symbols = []
    for j in range(n):
        v = 0
        for i in range(sf_eff):
            v |= codewords[(i + j) % sf_eff][j] << i
        symbols.append(v)
    return symbols


def deinterleave(symbols: list[int], sf_eff: int) -> list[list[int]]:
    n = len(symbols)
    cws = [[0] * n for _ in range(sf_eff)]
    for j, v in enumerate(symbols):
        for i in range(sf_eff):
            cws[(i + j) % sf_eff][j] = (v >> i) & 1
    return cws


# --- header --------------------------------------------------------------------
def header_nibbles(payload_len: int, cr: int, crc: bool) -> list[int]:
    n0, n1 = payload_len & 0xF, payload_len >> 4
    n2 = ((cr - 4) << 1) | int(crc)
    chk = n0 ^ n1 ^ n2
    parity = bin((n0 << 8) | (n1 << 4) | n2).count("1") & 1
    return [n0, n1, n2, chk, parity]


def parse_header(nibbles: list[int]) -> tuple[int, int, bool] | None:
    n0, n1, n2, chk, parity = nibbles[:5]
    if chk != (n0 ^ n1 ^ n2) or parity != (bin((n0 << 8) | (n1 << 4) | n2).count("1") & 1) or (n2 >> 1) == 0:
        return None
    cr = (n2 >> 1) + 4
    if cr not in (5, 6, 7, 8):
        return None
    return n0 | (n1 << 4), cr, bool(n2 & 1)


# --- sembol kodlayıcı ----------------------------------------------------------
@dataclass(frozen=True)
class SymbolLayout:
    sf: int
    cr: int
    ldro: bool
    implicit_header: bool

    @property
    def first_block_nibbles(self) -> int:
        return self.sf - 2

    @property
    def payload_bits_per_symbol(self) -> int:
        return self.sf - 2 * int(self.ldro)


def encode_symbols(frame: bytes, crc: bool, layout: SymbolLayout) -> list[int]:
    """Çerçeve (payload + varsa CRC) → FFT bin değerleri (0..M-1)."""
    payload = frame[:-2] if crc else frame
    crc_bytes = frame[-2:] if crc else b""
    nibbles = bytes_to_nibbles(whiten(payload) + crc_bytes)
    if not layout.implicit_header:
        nibbles = header_nibbles(len(payload), layout.cr, crc) + nibbles
    symbols: list[int] = []
    # İlk blok: SF-2 bit/sembol, CR 4/8, 8 sembol
    k = layout.first_block_nibbles
    first, rest = nibbles[:k], nibbles[k:]
    first += [0] * (k - len(first))
    symbols += [s * 4 for s in _block(first, 8, k)]
    # Kalan bloklar
    k = layout.payload_bits_per_symbol
    scale = 4 if layout.ldro else 1
    for i in range(0, len(rest), k):
        chunk = rest[i:i + k]
        chunk += [0] * (k - len(chunk))
        symbols += [s * scale for s in _block(chunk, layout.cr, k)]
    return symbols


def _block(nibbles: list[int], cr: int, sf_eff: int) -> list[int]:
    cws = [hamming_encode(n, cr) for n in nibbles]
    return [int(gray_decode(v)) for v in interleave(cws, sf_eff)]


# --- dalga şekli ---------------------------------------------------------------
def chirp(sf: int, symbol: int = 0, down: bool = False) -> np.ndarray:
    m = 2 ** sf
    n = np.arange(m)
    c = np.exp(2j * np.pi * (n * n / (2 * m) + (symbol / m - 0.5) * n))
    return np.conj(c) if down else c


def chirp_matrix(sf: int, symbols: np.ndarray) -> np.ndarray:
    """Sembol dizisi → (sembol sayısı, M) chirp matrisi."""
    m = 2 ** sf
    n = np.arange(m)
    base = n * n / (2 * m) - 0.5 * n
    return np.exp(2j * np.pi * (base[None, :] + np.outer(np.asarray(symbols) / m, n)))


def sync_word_symbols(sync_word: int) -> tuple[int, int]:
    """SX127x: sync word'ün iki nibble'ı 8 ile çarpılarak iki sembole yerleştirilir."""
    return (sync_word >> 4) * 8, (sync_word & 0xF) * 8


def modulate(symbols: list[int], sf: int, preamble: int, sync_word: int, iq_inverted: bool) -> np.ndarray:
    m = 2 ** sf
    sw = sync_word_symbols(sync_word)
    parts = [chirp_matrix(sf, np.zeros(preamble)).ravel(), chirp_matrix(sf, np.array(sw)).ravel()]
    down = chirp(sf, 0, down=True)
    parts.append(np.concatenate([down, down, down[: m // 4]]))
    parts.append(chirp_matrix(sf, np.array(symbols)).ravel())
    signal = np.concatenate(parts)
    return np.conj(signal) if iq_inverted else signal
