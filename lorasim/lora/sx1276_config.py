"""SX1276 donanım sınırları ve sabitleri.

Kaynak: Semtech SX1276/77/78/79 veri sayfası (Rev. 7) ve AN1200.13.
"""

FREQ_MIN_MHZ = 137.0
FREQ_MAX_MHZ = 1020.0

# RFO çıkışı -4 dBm'e kadar iner, PA_BOOST yüksek güç modunda +20 dBm'e çıkar.
TX_POWER_MIN_DBM = -4.0
TX_POWER_MAX_DBM = 20.0

SPREADING_FACTORS = (7, 8, 9, 10, 11, 12)
BANDWIDTHS_KHZ = (125.0, 250.0, 500.0)
# Kodlama oranı 4/x olarak tutulur; burada yalnızca payda (x) saklanır.
CODING_RATES = (5, 6, 7, 8)

PAYLOAD_MAX_BYTES = 255
PREAMBLE_MIN_SYMBOLS = 6
PREAMBLE_MAX_SYMBOLS = 65535

DEFAULT_NOISE_FIGURE_DB = 6.0

# Sembol süresi bu değeri aştığında Low Data Rate Optimization zorunludur.
LDRO_SYMBOL_TIME_THRESHOLD_S = 16e-3

# Demodülatörün çözebildiği minimum SNR (veri sayfası Tablo 13).
SNR_REQUIRED_DB = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}

SYNC_WORD_PRIVATE = 0x12
SYNC_WORD_PUBLIC = 0x34

THERMAL_NOISE_DBM_HZ = -174.0

# Verici ile alıcı arasında tolere edilen azami taşıyıcı frekans farkı (BW'nin oranı olarak).
FREQ_OFFSET_TOLERANCE_BW = 0.25
