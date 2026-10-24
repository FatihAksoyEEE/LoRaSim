# LoRaSim Kullanım Kılavuzu

Bu kılavuz, arayüzün ve komut satırının nasıl kullanılacağını, parametrelerin ne anlama
geldiğini ve sonuçların nasıl yorumlanacağını anlatır. Modellerin arkasındaki kararlar
ve varsayımlar `plan.md` §16'dadır.

## 1. Grafiksel arayüz

`python main.py` ile açılır.

### 1.1 Parametre panelleri (sol)

| Panel | İçerik |
|---|---|
| **LoRa ayarları** | Frekans, SF, bant genişliği, kodlama oranı, gönderim gücü, payload, CRC |
| **Gelişmiş paket ve donanım** | Preamble, implicit header, Sync Word, IQ inversion, LDRO (Otomatik/Açık/Kapalı), anten kazançları, kablo kayıpları, gürültü figürü, hassasiyet (otomatik ya da elle) |
| **Kanal ve ortam** | Ortam profili, yol kaybı modeli ve üssü, gölgeleme, sönümleme, AWGN, ek gürültü, çok yollu yayılım, zamana bağlı kanal, Doppler, kristal frekans kayması, çakışmalar ve capture eşiği, harici girişim |
| **Cihazlar ve hareket** | Konumlandırma modu (mesafe / kartezyen / rastgele), cihaz sayıları, alan boyutu, cihaz tablosu, hareket grubu ve modeli, hız, yön, rota |
| **ACK ve trafik** | Paket aralığı, rastgele başlangıç, kuyruk, duty-cycle sınırı ve politikası, paket/süre sınırları, ACK, tekrar sayısı, ACK timeout (otomatik ya da elle), paket timeout, tekrar bekleme süresi |
| **Simülasyon** | Model (link-level / CSS), çalışma modu, zaman ölçeği, seed, bellekte tutulan kayıt sayısı |

"Ortam varsayılanı", "Otomatik", "Sınırsız" gibi onay kutuları alanı boş (None) bırakır;
bu durumda değer ortam profilinden ya da otomatik hesaptan gelir.

Geçersiz bir değerle **Başlat**'a basılırsa simülasyon başlamaz ve düzeltilmesi gereken
tüm alanlar tek bir pencerede listelenir.

### 1.2 Kontroller (üst çubuk)

- **▶ Başlat (F5)**, **⏸ Duraklat / ⏵ Devam et (F6)**, **■ Durdur (F7)**, **↺ Sıfırla**
- **Mod:** Gerçek zamanlı (paketler duvar saatine göre işlenir, *Zaman ölçeği* ile
  hızlandırılabilir) veya Hızlandırılmış (bekleme olmadan, mümkün olan en hızlı).
- Simülasyon çalışırken parametre panelleri kilitlenir.

### 1.3 Sekmeler

- **Canlı grafikler:** RSSI–zaman, SNR–zaman, paket başarı/hata durumu, BER/PER–zaman,
  throughput–zaman, gecikme–zaman, cihaz konumları ve hareket izleri. Üstteki onay
  kutularıyla her grafik ayrı açılıp kapatılır. Noktaların rengi alım durumunu gösterir
  (yeşil başarılı, gri algılanmadı, mavi çakışma, kahverengi half-duplex, turuncu CRC
  hatası).
- **Sonuçlar:** Özet metrik tablosu, verici bazlı tablo ve kayıt çubuğu. Kayıt klasörü ve
  dosya adı seçilir; CSV, JSON, PNG, PDF ya da hepsi tek tuşla kaydedilir.
- **Paket logu:** Her gönderim denemesi bir satırdır (son 20.000 satır gösterilir).
- **Analiz:** Ortam karşılaştırması, mesafe–başarı, güç–başarı, SF karşılaştırması,
  başarılı haberleşme mesafesi ve link-level ↔ CSS model karşılaştırması. Sonuçlar grafik
  ve tablo olarak gösterilir, CSV/JSON/PNG/PDF olarak kaydedilir.

**Dosya** menüsünden ayarlar JSON olarak kaydedilip yüklenebilir.

## 2. Komut satırı

```bash
python -m lorasim [seçenekler]      # ya da: python main.py [seçenekler]
```

### 2.1 Sık kullanılan seçenekler

| Seçenek | Anlam |
|---|---|
| `--config dosya.json` | Ayarları dosyadan oku (diğer seçenekler üzerine yazar) |
| `--freq`, `--sf`, `--bw`, `--cr`, `--power`, `--payload`, `--no-crc` | LoRa ayarları (`--cr 5` = 4/5) |
| `--env`, `--fading`, `--shadowing`, `--distance` | Kanal ve mesafe |
| `--multipath`, `--time-varying`, `--doppler`, `--freq-offset PPM` | Ek kanal etkileri |
| `--interference lora\|wideband`, `--interference-power`, `--interference-rate`, `--no-collisions` | Girişim ve çakışma |
| `--positioning`, `--tx-count`, `--rx-count`, `--area` | Cihazlar |
| `--moving`, `--mobility`, `--speed-mps`, `--heading` | Hareket |
| `--interval`, `--packets`, `--duration`, `--queue` | Trafik (`--packets` verici başınadır) |
| `--duty-cycle YÜZDE`, `--duty-policy warn\|enforce` | Duty-cycle (`0` = kontrol yok) |
| `--no-ack`, `--retries`, `--ack-timeout`, `--packet-timeout` | ACK |
| `--mode realtime\|accelerated`, `--speed`, `--seed`, `--model link_level\|css_phy` | Çalışma |
| `--csv`, `--json`, `--png`, `--report`, `--save-config` | Çıktılar |
| `--sweep distance\|power\|sf\|environment`, `--sweep-values`, `--sweep-packets` | Tarama |
| `--max-range [EŞİK]` | Başarılı haberleşme mesafesi |
| `--compare-models` | Link-level ↔ CSS karşılaştırması |

Gerçek zamanlı mod Ctrl+C ile durdurulur; hızlandırılmış modda `--packets` veya
`--duration` verilmelidir.

### 2.2 Örnekler

```bash
# Hareketli vericiler, zamana bağlı kanal ve Doppler
python -m lorasim --tx-count 5 --distance 1000 --env urban --moving transmitters \
    --mobility random_walk --speed-mps 15 --time-varying --doppler --packets 200 \
    --interval 5 --mode accelerated -q --report output/hareket.pdf

# Rastgele yerleşim: 3 alıcı, 40 verici, 3x3 km
python -m lorasim --positioning random --rx-count 3 --tx-count 40 --area 3000 \
    --packets 300 --interval 30 --mode accelerated -q

# Kartezyen yerleşim JSON'dan
python -m lorasim --config senaryo.json --mode accelerated --packets 500
```

Kartezyen senaryo örneği (`senaryo.json`):

```json
{
  "topology": {
    "mode": "cartesian",
    "devices": [
      {"id": "GW", "role": "rx", "x": 0, "y": 0},
      {"id": "Sensor1", "role": "tx", "x": 800, "y": 200},
      {"id": "Arac", "role": "tx", "x": -500, "y": 0, "speed_mps": 12, "heading_deg": 0},
      {"id": "Devriye", "role": "tx", "x": 0, "y": 300, "route": [[300, 300], [300, -300], [0, -300]]}
    ]
  },
  "channel": {"environment": "urban", "time_varying": true, "doppler_enabled": true}
}
```

## 3. Sonuçların yorumlanması

| Metrik | Tanım |
|---|---|
| **Başarı oranı** | Alıcıya en az bir kez hatasız ulaşan benzersiz paketlerin oranı (tekrar gönderimler dahil) |
| **Paket kayıp oranı** | 1 − başarı oranı (kuyrukta düşen paketler dahil) |
| **PER (frame)** | Tek tek gönderimlerin (tekrarlar dahil) hata oranı |
| **BER / SER** | Çözücüye ulaşan çerçevelerde bit / sembol hata oranı |
| **ACK başarı oranı** | ACK beklenen gönderimlerden onaylananların oranı |
| **Throughput** | Hatasız ve benzersiz teslim edilen payload biti / simülasyon süresi |
| **Gecikme** | Paket üretiminden alıcıda ilk hatasız alıma kadar (kuyruk ve tekrarlar dahil) |
| **Onay gecikmesi** | Paket üretiminden ACK'in vericiye ulaşmasına kadar |
| **Duty-cycle** | Verici başına ortalama yayın süresi oranı |
| **Enerji** | SX1276 TX/RX/uyku akımlarına göre (3,3 V); mikrodenetleyici hariç |

### Alım durumları

| Durum | Anlam |
|---|---|
| Başarılı (`ok`) | Paket hatasız alındı |
| Algılanmadı (`not_detected`) | RSSI hassasiyetin altında ya da sync word/IQ uyumsuz |
| Header hatası | Explicit header çözülemedi |
| CRC hatası | Payload bozuk, CRC yakaladı |
| Fark edilmeyen bozulma | CRC kapalı (veya CRC'nin kaçırdığı) bozuk paket teslim edildi |
| Çakışma (`collision`) | Örtüşen gönderim/girişim capture eşiğini bozdu |
| Half-duplex | Alıcı o sırada kendisi gönderim yapıyordu |
| Frekans kayması | Verici–alıcı frekans farkı ±%25 BW toleransını aştı |

### ACK durumları

`acked` (onaylandı), `not_sent` (veri alınamadığı için ACK yok), `lost` (ACK vericide
çözülemedi), `late` (ACK timeout'tan sonra geldi), `blocked` (alıcının duty-cycle'ı izin
vermedi), `disabled` (ACK kapalı).

## 4. Modeller hakkında notlar

- **Link-level model:** Sembol hata olasılığı, LoRa'nın evreuyumsuz ortogonal modülasyon
  eşdeğerinden sayısal olarak hesaplanır (Monte Carlo ve CSS modeliyle doğrulandı). Header
  ve interleaver blokları, Hamming düzeltmesi ve gerçek CRC kontrolü modellenir.
- **CSS fiziksel katman modeli:** Gerçek chirp dalga şekli üretilir (preamble, sync word,
  SFD, header, payload), kanal sinyale uygulanır, alıcı CFO'yu preamble'dan kestirip
  düzeltir, dechirp+FFT ile çözer. Link-level modelden yavaştır (ölçülen: SF7'de ~25 kat,
  SF12'de ~270 kat); uzun ve çok cihazlı çalıştırmalar için link-level model önerilir.
- **Hassasiyet:** Veri sayfasındaki SNR eşikleri teorik SER modelinden 0,5–2,5 dB daha
  kötümserdir; bu nedenle paket kaybını çoğunlukla hassasiyet eşiği belirler.
- **Ortam profilleri** literatürdeki tipik değerlerdir, saha ölçümüyle kalibre edilmemiştir;
  her değer elle değiştirilebilir.
- **Frekans:** Girilen frekansın ülke mevzuatına uygunluğu kontrol edilmez.

## 5. Tekrarlanabilirlik

Her çalıştırmanın seed'i JSON çıktısına yazılır. Aynı ayarlar ve aynı seed ile hem
arayüzde hem komut satırında birebir aynı sonuçlar elde edilir.
