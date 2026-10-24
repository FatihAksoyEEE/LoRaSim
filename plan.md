# SX1276 LoRa Haberleşme Kalitesi Simülasyon Planı

## 1. Proje amacı

Bu projenin amacı, SX1276 tabanlı LoRa verici ve alıcı arasındaki haberleşme kalitesini bilgisayar ortamında gerçekçi biçimde incelemektir.

Simülasyon; farklı LoRa ayarları, mesafeler, ortamlar, kanal bozucu etkileri, cihaz hareketleri ve paket gönderim stratejileri altında çalıştırılacaktır. Sonuçlar grafiksel kullanıcı arayüzünde gösterilecek ve CSV, JSON, PNG/PDF formatlarında dışa aktarılabilecektir.

## 2. Belirlenen gereksinimler

### 2.1 Donanım ve haberleşme teknolojisi

- Haberleşme teknolojisi: LoRa
- Modül: Semtech SX1276
- Frekans: Kullanıcı tarafından girilebilir
- Verici sayısı: Kullanıcı tarafından belirlenebilir
- Alıcı sayısı: Kullanıcı tarafından belirlenebilir
- Anten ve donanım kayıpları: Kullanıcı tarafından ayarlanabilir
- Verici gücü: Kullanıcı ayarı ve otomatik tarama desteklenecek
- Alıcı hassasiyeti: Otomatik hesaplama ve kullanıcı tarafından üzerine yazma desteklenecek

### 2.2 LoRa parametreleri

Aşağıdaki temel parametreler kullanıcı tarafından değiştirilebilecektir:

- Spreading Factor: SF7–SF12
- Bandwidth: 125, 250 ve 500 kHz
- Coding Rate: 4/5, 4/6, 4/7 ve 4/8
- Gönderim gücü
- Frekans
- Payload uzunluğu
- CRC açık/kapalı
- Paket gönderim aralığı
- Duty-cycle

Gelişmiş ayarlar isteğe bağlı bir panelde sunulacaktır:

- Preamble uzunluğu
- Explicit/implicit header modu
- Sync Word
- IQ inversion
- Low Data Rate Optimization

### 2.3 Veri ve paket yapısı

- Sistem sürekli paket gönderimini destekleyecek.
- Paket payload'ı rastgele byte verisinden oluşacak.
- Payload uzunluğu kullanıcı tarafından değiştirilebilecek.
- Paketlerde paket numarası ve zaman bilgisi tutulabilecek.
- CRC kontrolü desteklenecek.
- Paket gönderim aralığı kullanıcı tarafından ayarlanabilecek.
- Simülasyon kullanıcı durdurana kadar çalışabilecek.
- İsteğe bağlı süre ve maksimum paket sayısı sınırları bulunacak.

Örnek mantıksal paket yapısı:

```text
Paket numarası | Zaman bilgisi | Rastgele byte payload | CRC
```

## 3. Simülasyon modelleri

### 3.1 Link-level model

Hızlı analiz için kullanılacaktır. Bu modelde gerçek LoRa dalga şekli üretilmeden aşağıdaki bilgiler kullanılarak paket başarı durumu hesaplanacaktır:

- Link budget
- Yol kaybı
- RSSI
- SNR
- Alıcı hassasiyeti
- SF, BW ve CR
- Paket uzunluğu
- Gürültü ve sönümleme
- CRC ve hata olasılığı

Bu model çok sayıda cihaz ve uzun süreli simülasyonlarda kullanılacaktır.

### 3.2 LoRa CSS fiziksel katman modeli

Ayrıntılı analiz ve doğrulama için kullanılacaktır. Bu modelde:

- LoRa chirp sinyalleri üretilecek
- Modülasyon ve demodülasyon gerçekleştirilecek
- Kanal etkileri sinyal üzerinde uygulanacak
- Gürültü ve sönümleme modellenecek
- Sinyal alıcıda işlenecek
- Paket ve bit hataları hesaplanacak

Kullanıcı arayüzünden link-level veya fiziksel katman modeli seçilebilecektir.

## 4. Kanal ve ortam modelleri

### 4.1 Ortam seçenekleri

Kullanıcı aşağıdaki ortam modellerinden birini seçebilecek veya birden fazla ortamı karşılaştırabilecektir:

- Serbest uzay
- Açık alan
- Kırsal alan
- Kentsel alan
- Yoğun kentsel alan
- Kapalı alan

### 4.2 Kanal bozucu etkileri

Aşağıdaki etkiler bağımsız olarak açılıp kapatılabilecek:

- AWGN gürültüsü
- Serbest uzay yol kaybı
- Log-distance yol kaybı
- Rayleigh sönümleme
- Rician sönümleme
- Çok yollu yayılım
- Doppler etkisi
- Frekans kayması
- Diğer LoRa/RF cihazlarından girişim
- Paket çakışmaları

### 4.3 Mesafe ve konumlandırma

Kullanıcı aşağıdaki yöntemlerden birini seçebilecek:

- Doğrudan verici–alıcı mesafesi girme
- Kartezyen koordinatlarla konumlandırma
- ~~Harita üzerinde konumlandırma~~ (ilk sürüm kapsamı dışında, bkz. §16 K1)
- Rastgele konumlandırma
- Birden fazla cihazın konumlarını tanımlama

## 5. Hareket modeli

Verici ve alıcıların hareket durumu kullanıcı tarafından seçilebilecek:

- Tüm cihazlar sabit
- Yalnızca vericiler hareketli
- Yalnızca alıcılar hareketli
- Verici ve alıcılar hareketli

Desteklenecek hareket modelleri:

- Sabit hız ve yön
- Rastgele hareket
- Önceden tanımlı rota
- Kullanıcı tanımlı hız ve yön
- Dairesel hareket

Hareketli senaryolarda Doppler etkisi ve zamana bağlı kanal değişimi hesaba katılabilecektir.

## 6. Paket teslimi ve tekrar gönderim

Sistem ACK tabanlı tekrar gönderimi destekleyecektir.

Kullanıcı tarafından ayarlanabilecek özellikler:

- ACK kullanımını açma/kapatma
- ACK bekleme süresi
- Maksimum tekrar gönderim sayısı
- Paket timeout değeri
- Otomatik veya kullanıcı tanımlı ACK timeout

ACK timeout değeri, seçilen SF, BW, CR ve payload uzunluğuna göre otomatik hesaplanabilecek; kullanıcı isterse bu değeri değiştirebilecektir.

## 7. Simülasyon çalışma modları

### 7.1 Gerçek zamanlı mod

- Paketler belirlenen gönderim aralığına göre işlenir.
- Grafikler simülasyon sırasında güncellenir.
- Kullanıcı cihaz hareketlerini ve anlık haberleşme durumunu izleyebilir.

### 7.2 Hızlandırılmış analiz modu

- Gerçek zaman beklenmeden çok sayıda paket işlenir.
- Parametre taraması ve ortam karşılaştırması için kullanılır.
- İstatistiksel sonuçların daha hızlı elde edilmesini sağlar.

## 8. Ölçülecek kalite göstergeleri

Simülasyon aşağıdaki ölçümleri hesaplayacaktır:

- BER: Bit Error Rate
- SER: Symbol Error Rate
- PER/FER: Paket veya frame hata oranı
- Paket kayıp oranı
- Başarılı paket sayısı
- Hatalı paket sayısı
- Tekrar gönderim sayısı
- RSSI
- SNR
- Throughput
- Paket gecikmesi
- ACK başarısı
- Ortalama ve anlık başarı oranı
- Toplam simülasyon süresi
- Başarılı haberleşme mesafesi
- Duty-cycle ihlal sayısı
- Enerji tüketimi için tahmini istatistikler

## 9. Grafiksel kullanıcı arayüzü

Uygulama PySide6 veya PyQt tabanlı masaüstü arayüzü olarak geliştirilecektir. Kütüphane seçimi proje başlangıcında kesinleştirilecek; varsayılan tercih PySide6 olacaktır.

### 9.1 Ana arayüz bölümleri

1. **Simülasyon kontrol paneli**
   - Başlat
   - Durdur
   - Duraklat/devam ettir
   - Sıfırla
   - Gerçek zamanlı/hızlandırılmış mod seçimi

2. **LoRa ayarları paneli**
   - Frekans
   - SF
   - BW
   - CR
   - Gönderim gücü
   - Payload uzunluğu
   - CRC
   - Gelişmiş paket ayarları

3. **Kanal ve ortam paneli**
   - Ortam seçimi
   - Mesafe/konumlandırma
   - Gürültü seviyesi
   - Sönümleme
   - Yol kaybı
   - Doppler
   - Frekans kayması
   - Girişim

4. **Cihaz ve hareket paneli**
   - Verici/alıcı sayısı
   - Cihaz konumları
   - Hareket modeli
   - Hız, yön ve rota ayarları

5. **ACK ve trafik paneli**
   - Paket gönderim aralığı
   - Duty-cycle
   - ACK kullanımı
   - ACK timeout
   - Maksimum tekrar sayısı
   - Süre ve paket sayısı sınırları

6. **Sonuç paneli**
   - Anlık istatistikler
   - Özet tablo
   - Paket logları
   - Dışa aktarma seçenekleri

### 9.2 Canlı grafikler

Kullanıcı aşağıdaki grafiklerin her birini açıp kapatabilecek:

- RSSI–zaman
- SNR–zaman
- Paket başarı/hata durumu
- BER/PER–zaman
- Throughput–zaman
- Gecikme–zaman
- Cihaz konumları ve hareketleri
- Ortam karşılaştırma grafikleri
- Mesafe–başarı oranı grafiği
- Güç–başarı oranı grafiği

## 10. Veri kaydetme ve dışa aktarma

### 10.1 CSV çıktısı

Paket bazında aşağıdaki bilgiler kaydedilebilecek:

- Zaman
- Paket numarası
- Verici ve alıcı kimliği
- Paket uzunluğu
- Gönderim durumu
- Alım durumu
- RSSI
- SNR
- Hata durumu
- Gecikme
- Tekrar gönderim sayısı
- Ortam ve kanal bilgileri

### 10.2 JSON çıktısı

- Simülasyon ayarları
- LoRa parametreleri
- Kanal parametreleri
- Ortam bilgisi
- Cihaz konumları
- Hareket ayarları
- Özet sonuçlar
- Çalışma modu

### 10.3 Grafik çıktıları

- PNG
- PDF

## 11. Önerilen yazılım mimarisi

> Gerçekleşen yapı `lorasim/` paketi altındadır (K16); güncel ağaç için `README.md` → *Proje yapısı*.

```text
project/
├── main.py
├── gui/
│   ├── main_window.py
│   ├── parameter_panels.py
│   ├── results_panel.py
│   └── plotting_widgets.py
├── simulation/
│   ├── simulation_engine.py
│   ├── link_level_model.py
│   ├── css_phy_model.py
│   ├── packet_manager.py
│   ├── ack_manager.py
│   └── scheduler.py
├── lora/
│   ├── sx1276_config.py
│   ├── lora_parameters.py
│   ├── modulation.py
│   ├── demodulation.py
│   └── sensitivity.py
├── channel/
│   ├── path_loss.py
│   ├── noise.py
│   ├── fading.py
│   ├── interference.py
│   ├── doppler.py
│   └── environment.py
├── devices/
│   ├── transmitter.py
│   ├── receiver.py
│   ├── device.py
│   └── mobility.py
├── metrics/
│   ├── ber.py
│   ├── per.py
│   ├── rssi_snr.py
│   ├── throughput.py
│   └── latency.py
├── export/
│   ├── csv_exporter.py
│   ├── json_exporter.py
│   └── report_exporter.py
├── config/
│   └── default_config.json
├── tests/
└── requirements.txt
```

## 12. Geliştirme aşamaları

### Aşama 1 — Temel proje altyapısı

- Python proje yapısının oluşturulması
- Sanal ortam ve bağımlılıkların tanımlanması
- Temel yapılandırma sınıflarının hazırlanması
- SX1276 parametre sınıflarının oluşturulması

### Aşama 2 — Link-level LoRa modeli

- Paket üretimi
- Payload ve CRC modeli
- SF, BW ve CR ilişkileri
- Alıcı hassasiyeti hesabı
- Link budget hesabı
- RSSI ve SNR hesabı
- Paket başarı/hata modeli

### Aşama 3 — Kanal ve ortam modelleri

- Serbest uzay yol kaybı
- Log-distance modeli
- Ortam profilleri
- AWGN
- Rayleigh/Rician sönümleme
- Girişim ve paket çakışması

### Aşama 4 — Trafik, ACK ve tekrar gönderim

- Sürekli paket zamanlayıcısı
- Paket gönderim aralığı
- Duty-cycle kontrolü
- ACK mekanizması
- Timeout hesaplama
- Tekrar gönderim yönetimi

### Aşama 5 — Cihaz konumları ve hareket

- Çoklu verici/alıcı desteği
- Koordinat tabanlı konumlandırma
- Rastgele yerleşim
- Hareket modelleri
- Doppler modelinin eklenmesi

### Aşama 6 — CSS fiziksel katman modeli

- LoRa chirp üretimi
- Modülasyon
- Kanal üzerinden sinyal iletimi
- Demodülasyon
- Fiziksel katman BER/PER hesabı
- Link-level sonuçlarıyla karşılaştırma

### Aşama 7 — PySide6/PyQt arayüzü

- Ana pencere
- Parametre panelleri
- Başlat/durdur kontrolleri
- Gerçek zamanlı grafikler
- Paket logları
- Ortam karşılaştırma ekranı

### Aşama 8 — Kayıt ve raporlama

- CSV dışa aktarma
- JSON dışa aktarma
- PNG/PDF grafik kaydı
- Simülasyon özet raporu

### Aşama 9 — Test ve doğrulama

- Parametre doğrulama testleri
- CRC testleri
- Paket hata testleri
- Yol kaybı doğrulaması
- Alıcı hassasiyeti doğrulaması
- Teorik LoRa sonuçlarıyla karşılaştırma
- Uzun süreli ve çoklu cihaz testleri

## 13. Başlangıç varsayılanları

İlk çalışan prototip için aşağıdaki varsayılanlar kullanılabilir:

```text
Modül: SX1276
Simülasyon modeli: Link-level
Frekans: Kullanıcı tanımlı
SF: 7
BW: 125 kHz
CR: 4/5
Gönderim gücü: 14 dBm
Payload: Kullanıcı tanımlı, başlangıçta 20 byte
CRC: Açık
Ortam: Serbest uzay
Mesafe: Kullanıcı tanımlı
Verici sayısı: 1
Alıcı sayısı: 1
Paket aralığı: 1 saniye
ACK: Açık
Maksimum tekrar: 3
Çalışma modu: Gerçek zamanlı
```

## 14. Başarı kriterleri

Projenin ilk sürümü aşağıdaki koşulları sağlamalıdır:

- Kullanıcı arayüzünden LoRa parametreleri değiştirilebilmeli.
- Sürekli rastgele byte paketleri üretilebilmeli.
- En az bir verici ve bir alıcı ile simülasyon çalışabilmeli.
- RSSI, SNR, PER, throughput ve gecikme hesaplanabilmeli.
- En az üç farklı ortam modeli karşılaştırılabilmeli.
- Gerçek zamanlı ve hızlandırılmış çalışma desteklenmeli.
- ACK ve tekrar gönderim mekanizması çalışmalı.
- Sonuçlar CSV, JSON ve grafik formatında kaydedilebilmeli.
- Parametre hataları kullanıcıya anlaşılır şekilde bildirilmeli.
- Link-level model ile temel simülasyon sonuçları tekrarlanabilir olmalı.

## 15. Teknik notlar

- SX1276 gerçek bir donanım modülüdür; bilgisayar simülasyonunda donanımın tüm iç davranışları birebir modellenemeyebilir.
- CSS fiziksel katman modeli daha doğru sonuç verir ancak link-level modele göre daha fazla işlem gücü ve geliştirme süresi gerektirir.
- Frekans alanı kullanıcı tarafından girilebilir olsa da gerçek kullanımda ülke ve bölge mevzuatına uygunluk kontrol edilmelidir.
- Duty-cycle, gönderim gücü ve kullanılan bant için yasal sınırlamalar gerçek saha uygulamasında ayrıca değerlendirilmelidir.
- İlk sürümde link-level modelin tamamlanması, daha sonra CSS modelinin eklenmesi önerilir.

## 16. Alınan kararlar

Bu bölüm, plandaki açık noktalar için verilen kararları kaydeder. Kod bu kararlara göre yazılır.

| No | Konu | Karar |
|----|------|-------|
| K1 | Harita konumlandırma | İlk sürüm kapsamı dışında. Mesafe, kartezyen koordinat ve rastgele yerleşim yeterli. |
| K2 | Tekrarlanabilirlik | Tüm rastgelelik tek bir `numpy.random.Generator` üzerinden yürür. `run.seed` verilmezse rastgele bir seed seçilir ve sonuç JSON'una yazılır; aynı seed ile çalıştırma aynı sonucu verir. |
| K3 | Low Data Rate Optimization | Varsayılan **otomatik**: sembol süresi > 16 ms ise açılır (ör. 125 kHz'de SF11/12). Kullanıcı `ldro: true/false` ile zorlayabilir. |
| K4 | Frekans | Geçerli aralık 137–1020 MHz (SX1276). Varsayılan 868,1 MHz (EU868, Türkiye için uygun). Mevzuat kontrolü yapılmaz, yalnızca not düşülür. |
| K5 | Payload uzunluğu | `payload_bytes` LoRa PHY payload'ıdır (airtime formülündeki PL). İlk 6 byte paket numarası (2 B) ve zaman bilgisi (4 B, ms), kalanı rastgele byte. CRC, PHY'nin eklediği 2 byte'tır ve PL'ye dahil değildir. Minimum payload 6 byte. |
| K6 | CRC | CRC-16/CCITT (polinom 0x1021, başlangıç 0x0000). Link-level modelde bozulan bitler gerçekten çevrilir ve CRC gerçekten hesaplanır; CRC'nin kaçırdığı bozulmalar "corrupted_undetected" olarak sayılır. |
| K7 | Simülasyon çekirdeği | Ayrık olay tabanlı zamanlayıcı (heapq). Gerçek zamanlı mod aynı motoru duvar saatine göre bekleterek çalıştırır (`run.speed` zaman ölçeği). Durdur/duraklat/devam et thread-safe'tir; arayüz motoru ayrı bir iş parçacığında çalıştıracak. |
| K8 | Link-level hata modeli | SER, LoRa'nın evreuyumsuz M=2^SF ortogonal modülasyon eşdeğerinden sayısal integralle hesaplanır (Monte Carlo ile doğrulandı). Paket kararı: hassasiyet altı → algılanmadı; header (8 sembol, CR 4/8) → header hatası; payload interleaver blokları → CR 4/7 ve 4/8 blok başına 1 sembol hatası düzeltir, 4/5 ve 4/6 düzeltmez. |
| K9 | Hassasiyet | `S = -174 + 10·log10(BW) + NF + SNR_gerekli(SF)`, NF = 6 dB, SNR eşikleri veri sayfası Tablo 13. Kullanıcı değeri girilirse o kullanılır. Not: Teorik SER modeli, veri sayfası eşiklerinden 0,5–2,5 dB daha iyimserdir. Bu yüzden pratikte paket kaybını hassasiyet eşiği belirler; bu fark Aşama 6'da CSS modeliyle karşılaştırılacak. |
| K10 | Ortam profilleri | Log-distance modeli, d0 = 1 m, referans kayıp FSPL(d0). Profiller (n, σ_gölgeleme, sönümleme): serbest uzay (2.0, 0, yok), açık alan (2.2, 2, Rician K=10 dB), kırsal (2.7, 4, Rician K=6 dB), kentsel (3.2, 6, Rayleigh), yoğun kentsel (3.6, 8, Rayleigh), kapalı alan (3.0, 7, Rayleigh). Bunlar literatürdeki tipik değerlerdir, kalibre edilmemiştir; her biri ayrı ayrı ezilebilir. |
| K11 | Gölgeleme | `off` / `per_link` (sabit cihazlar için link başına bir kez, varsayılan) / `per_packet`. Hareketli cihazlarda (Aşama 5) zamana bağlı ilintili gölgelemeye geçilecek. |
| K12 | Sönümleme | Paket başına blok sönümleme (paket süresince kanal sabit). Ortalama güç kazancı 1. |
| K13 | Çoklu alıcı (Aşama 5) | Her verici yayın yapar; menzildeki tüm alıcılar paketi duyar (çakışma hesabı için). Her vericinin bir hedef alıcısı vardır (varsayılan: en yakın alıcı); ACK'i yalnızca hedef alıcı gönderir. ACK de kanaldan geçen bir pakettir ve duty-cycle'a tabidir. SX1276 half-duplex olduğu için gönderim yapan cihaz o sırada alım yapamaz. |
| K14 | Paket çakışması (Aşama 3) | Capture effect: aynı SF'de istenen sinyal, girişimlerin toplam gücünden ≥ 6 dB güçlüyse alınır. Farklı SF'ler için Croce vd. (2018) SIR eşik matrisi kullanılır. |
| K15 | Gönderim aralığı ve kuyruk | Paketler gönderimden bağımsız olarak `interval_s` aralıkla üretilir. Verici aynı anda tek paketle uğraşır (gönderim, ACK bekleme, duty-cycle beklemesi); bu sırada üretilenler FIFO kuyruğunda bekler (`tx_queue_size`, varsayılan 16), kuyruk doluysa paket düşürülür (`queue_drop`). Gecikme, kuyrukta bekleme süresini de içerir. |
| K16 | Paket düzeni | Kod `lorasim/` paketi altında toplanır (`channel`, `devices` gibi genel adların çakışmasını önlemek için). Metrikler tek bir `metrics/collector.py` modülünde toplanır (§11'deki ber/per/... dosyaları yerine). |
| K17 | Arayüz | PySide6 ve canlı grafikler için PyQtGraph. Matplotlib yalnızca PNG/PDF rapor çıktısı için. |
| K18 | Python | Python ≥ 3.11 (sistemdeki 3.9 değil, Homebrew 3.11 ile `.venv`). |
| K19 | Dil | Kod tanımlayıcıları İngilizce; açıklamalar, docstring'ler ve kullanıcıya gösterilen tüm mesajlar Türkçe. |
| K20 | Duty-cycle | LoRaWAN/ETSI "off-time" kuralı: Ta süreli gönderimden sonra cihaz Ta·(1/dc − 1) susar. Varsayılan sınır %1 (EU868), varsayılan politika `warn` (gönderir ve ihlali sayar); `enforce` gönderimi izin verilen ana erteler. Verici ve alıcı (ACK) için ayrı ayrı takip edilir. |
| K21 | ACK yapısı | 3 byte payload: onaylanan paket no (2 B) + 0xAC işareti. Veriyle aynı LoRa ayarlarıyla gönderilir. Alıcı, veriyi bitirdikten `turnaround_s` (varsayılan 10 ms) sonra ACK gönderir; bozuk ama teslim edilmiş (CRC kapalı) paketler de onaylanır. |
| K22 | Otomatik ACK timeout | Veri gönderiminin bitişinden itibaren: `turnaround + ACK airtime + 4·Tsym + 10 ms`. Kullanıcı `ack.timeout_s` ile ezebilir; timeout'tan sonra gelen ACK yok sayılır ve `late` olarak işaretlenir. |
| K23 | ACK kanalı | ACK, verinin kanal örneğini (yol kaybı, gölgeleme, sönümleme) kullanır; yalnızca gürültü (SER çekilişi) bağımsızdır. Gerekçe: Sabit cihazlarda kanal ~10 ms'de değişmez ve karşılıklıdır. Tekrar gönderimler yeni kanal örneği alır (zaman/frekans çeşitliliği varsayımı). |
| K24 | Tekrar gönderim | Timeout dolunca aynı paket (aynı seq ve payload) hemen tekrar gönderilir (duty-cycle `enforce` ise ertelenebilir). `max_retries` (varsayılan 3) veya `packet_timeout_s` aşılınca paketten vazgeçilir. Rastgele backoff, çakışma modeliyle birlikte Aşama 5'te eklenecek. Alıcı tekrar gelen paketleri `duplicate` olarak işaretler; throughput yalnızca benzersiz paketleri sayar. |
| K25 | Metrik tanımları | `success_rate`: alıcıya en az bir kez hatasız ulaşan benzersiz paketlerin oranı. `per`: tek tek gönderimler (frame) bazında hata oranı. `ack_success_rate`: ACK beklenen gönderimlerden onaylananların oranı. `mean_latency_s`: üretimden alıcıda ilk hatasız alıma kadar geçen süre. `mean_confirm_latency_s`: üretimden ACK'in vericiye ulaşmasına kadar geçen süre. |
| K26 | Çoklu cihaz | Mesafe modunda tek alıcı orijinde, N verici ona `distance_m` uzaklıkta bir çember üzerinde eşit aralıklıdır. Kartezyen modda cihazlar listeden, rastgele modda alana düzgün dağılımla yerleşir. Hedef alıcı verilmezse başlangıçta en yakın alıcıdır. `max_packets` verici başınadır. |
| K27 | Girişim | Simülasyon içindeki tüm gönderimler (veri ve ACK) birbirine girişimdir. Harici girişim Poisson sürecidir: `lora` tipi bir SF ile capture/SIR matrisine girer, `wideband` tipi gürültü tabanına güç olarak eklenir. Zamanda herhangi bir örtüşme girişim sayılır (muhafazakâr). |
| K28 | Half-duplex | Bir cihaz gönderim yaparken aynı anda gelen paketi alamaz (`half_duplex` durumu). Bu, ağır trafikte alıcının ACK gönderirken veri kaçırmasını da kapsar. |
| K29 | Çok yollu yayılım | Ortam profilleri COST 207 (RA/TU/BU) ve ITU Indoor A gecikme profillerini taşır. Link-level kazanç, gecikme hattının frekans yanıtının bant üzerindeki ortalama gücüdür (chirp tüm bandı taradığı için); bu, geniş gecikme yayılımında frekans çeşitliliği sağlar. |
| K30 | Zamana bağlı kanal | `time_varying` açıkken sönümleme tap'ları AR(1) süreciyle evrilir: ρ = J0(2π·fD·Δt), fD = saçıcı Doppler'i + hızlardan gelen azami Doppler. Gölgeleme hareketli cihazlarda Gudmundson modeliyle (ρ = e^(−Δd/d_corr)) değişir. Kapalıyken K12 ve K23 geçerlidir; açıkken ACK kanalı o anda örneklenir (zaten yüksek ilintilidir). |
| K31 | Frekans kayması | Kristal hatası cihaz başına ±ppm aralığında düzgün dağılır. Toplam kayma = (ppm_tx − ppm_rx)·f + Doppler. ±%25 BW'yi aşarsa paket çözülemez. Tolerans içinde link-level modelde ek kayıp yoktur (preamble ile kestirilip düzeltildiği varsayılır); CSS modeli bu kestirimi gerçekten yapar. |
| K32 | Hareket modelleri | Sabit hız ve yön, rastgele yürüyüş (sabit hız, periyodik rastgele yön), rota (nokta listesi, isteğe bağlı döngü), dairesel. Cihaz bazında hız/yön/rota ezilebilir. Konumlar zamanın saf fonksiyonudur (arayüz kilitsiz okuyabilir). |
| K33 | Trafik varsayılanları | `random_start` açık: her verici ilk paketini [0, aralık) içinde rastgele gönderir (aksi halde eş zamanlı vericiler sürekli çakışır). Tekrar gönderim öncesi [0, `retry_backoff_max_s` = 1 s] rastgele bekleme (K24'ün ertelenen kısmı). |
| K34 | CSS fiziksel katman | fs = BW, preamble + 2 sembol sync word + 2.25 SFD + header/payload; whitening, Hamming 4/5–4/8, çapraz interleaving, Gray, LDRO ve düşük hızlı ilk blok airtime formülüyle aynı sembol sayısını üretir. Zamanlama bilinir varsayılır; CFO preamble'dan kestirilir. Whitening dizisi ve header sağlaması SX1276 ile bit düzeyinde aynı değildir. Ölçülen SER teoriyle ve PER link-level modelle uyumludur (testlerle sınanır). |
| K35 | Enerji | SX1276 veri sayfası akımları (TX güce göre ara değerleme, RX BW'ye göre, uyku 0,2 µA), 3,3 V. Verici ACK beklerken alımda, alıcı sürekli alımda sayılır. |
| K36 | Analiz | Taramalar hızlandırılmış modda ve tüm noktalarda aynı seed ile (ortak rastgele sayılar) çalışır. Başarılı haberleşme mesafesi: başarı oranının eşiğin (varsayılan 0,9) altına düştüğü nokta, log-mesafede ara değerlenir; eşik çevresinde ikinci, daha sık bir tarama yapılır. |
| K37 | Arayüz–motor iletişimi | Motor ayrı bir QThread'de çalışır; kayıtlar thread-safe bir deque'ya eklenir ve arayüz 200 ms'de bir boşaltır. Çalışma sırasında özet `live_summary()` ile okunur; bu yöntem link oluşturmaz ve RNG'ye dokunmaz, böylece aynı seed arayüzde ve CLI'de aynı sonucu verir. |
| K38 | Bellek | Özet metrikler sayaçlardan hesaplanır; bellekte yalnızca son `max_records` (varsayılan 200.000) kayıt tutulur. Uzun çalıştırmalarda bellek sabit kalır (testle sınanır). |
