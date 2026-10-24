# SX1276 LoRa Simülasyonu — To-Do Listesi

> Bu dosya `plan.md` içindeki **Geliştirme Aşamaları** bölümüyle senkron tutulacaktır.
>
> Durum işaretleri:
> - `[ ]` Başlanmadı
> - `[-]` Devam ediyor
> - `[x]` Tamamlandı
> - `[!]` Engellendi veya karar bekliyor

## Aşama 1 — Temel proje altyapısı

- [x] Python proje klasör yapısını oluştur
- [x] Sanal ortamı oluştur ve etkinleştir
- [x] `requirements.txt` dosyasını oluştur
- [x] PySide6 veya PyQt seçimini kesinleştir
- [x] NumPy, SciPy, Matplotlib ve PyQtGraph bağımlılıklarını ekle
- [x] Temel yapılandırma sınıflarını oluştur
- [x] SX1276 parametre sınıfını oluştur
- [x] Varsayılan simülasyon yapılandırmasını oluştur
- [x] Frekans, güç, SF, BW, CR ve payload doğrulamalarını ekle
- [x] Temel uygulama giriş noktasını oluştur
- [x] Rastgele sayı tohumu (seed) ile tekrarlanabilir çalışma (K2)

## Aşama 2 — Link-level LoRa modeli

- [x] Rastgele byte payload üretimini geliştir
- [x] Paket numarası ve zaman bilgisi ekle
- [x] CRC hesaplama ve kontrol mekanizmasını oluştur
- [x] Paket başarı/hata durum modelini oluştur
- [x] SF, BW ve CR arasındaki ilişkiyi modelle
- [x] LoRa sembol hızını hesapla
- [x] Paket airtime hesaplama fonksiyonunu oluştur
- [x] Alıcı hassasiyeti hesaplama fonksiyonunu oluştur
- [x] Kullanıcı tarafından girilen hassasiyet üzerine yazma özelliğini ekle
- [x] Link budget hesabını geliştir
- [x] RSSI hesaplama fonksiyonunu oluştur
- [x] SNR hesaplama fonksiyonunu oluştur
- [x] Temel paket hata olasılığı modelini oluştur
- [x] Link-level modeli birim testlerle doğrula

## Aşama 3 — Kanal ve ortam modelleri

- [x] Serbest uzay yol kaybı modelini ekle
- [x] Log-distance yol kaybı modelini ekle
- [x] Serbest uzay ortam profilini oluştur
- [x] Açık alan ortam profilini oluştur
- [x] Kırsal alan ortam profilini oluştur
- [x] Kentsel alan ortam profilini oluştur
- [x] Yoğun kentsel alan ortam profilini oluştur
- [x] Kapalı alan ortam profilini oluştur
- [x] AWGN gürültü modelini ekle
- [x] Rayleigh sönümleme modelini ekle
- [x] Rician sönümleme modelini ekle
- [x] Çok yollu yayılım için temel model oluştur
- [x] Frekans kayması modelini ekle
- [x] Girişim sinyali modelini ekle
- [x] Paket çakışması modelini ekle
- [x] Capture effect ve SF'ler arası SIR eşik matrisi (K14)
- [x] Kanal etkilerini bağımsız açıp kapatma özelliğini ekle
- [x] Tekli ortam karşılaştırma testlerini yap
- [x] Çoklu ortam karşılaştırma testlerini yap

## Aşama 4 — Trafik, ACK ve tekrar gönderim

- [x] Sürekli paket zamanlayıcısını oluştur
- [x] Kullanıcı tanımlı paket gönderim aralığını ekle
- [x] Gerçek zamanlı paket gönderimini ekle
- [x] Hızlandırılmış paket üretim modunu ekle
- [x] Duty-cycle hesaplama ve kontrolünü ekle
- [x] Duty-cycle ihlal uyarısını ekle
- [x] ACK paket yapısını tanımla
- [x] ACK gönderme ve alma mekanizmasını oluştur
- [x] Otomatik ACK timeout hesaplamasını ekle
- [x] Kullanıcı tanımlı ACK timeout değerini destekle
- [x] Maksimum tekrar gönderim sayısını ekle
- [x] Tekrar gönderim yönetimini oluştur
- [x] Başarısız paketlerin loglanmasını sağla
- [x] Başlat, durdur, duraklat ve devam ettir kontrollerini ekle
- [x] Süre sınırı ekle
- [x] Maksimum paket sayısı sınırı ekle
- [x] Gönderim kuyruğu ve kuyruk taşmasında paket düşürme (K15)
- [x] Paket timeout değeri (`packet_timeout_s`)
- [x] Tekrar gönderimde rastgele backoff (Aşama 5, çakışma modeliyle birlikte)

## Aşama 5 — Cihaz konumları ve hareket

- [x] Verici ve alıcı cihaz sınıflarını oluştur
- [x] Birden fazla verici desteğini ekle
- [x] Birden fazla alıcı desteğini ekle
- [x] Verici/alıcı kimliklendirme sistemini oluştur
- [x] Doğrudan mesafe ile konumlandırmayı ekle
- [x] Kartezyen koordinatlarla konumlandırmayı ekle
- [x] Rastgele konumlandırmayı ekle
- [x] Harita tabanlı konumlandırma ilk sürüm kapsamı dışında bırakıldı
- [x] Cihazların sabit konum modunu ekle
- [x] Sabit hız ve yön hareketini ekle
- [x] Rastgele hareket modelini ekle
- [x] Önceden tanımlı rota desteğini ekle
- [x] Kullanıcı tanımlı hız ve yön desteğini ekle
- [x] Dairesel hareket modelini ekle
- [x] Zamana bağlı kanal değişimini ekle
- [x] Doppler etkisini hareket modeliyle ilişkilendir
- [x] Çoklu cihaz çakışma testlerini yap

## Aşama 6 — CSS fiziksel katman modeli

- [x] LoRa chirp üretimini araştır ve tasarla
- [x] Temel chirp sinyali üretimini geliştir
- [x] LoRa sembol modülasyonunu ekle
- [x] Paket bitlerini sembollere dönüştür
- [x] Preamble üretimini ekle
- [x] Explicit/implicit header modelini ekle
- [x] Sync Word modelini ekle
- [x] IQ inversion desteğini ekle
- [x] Low Data Rate Optimization desteğini ekle
- [x] Kanal etkilerini fiziksel sinyale uygula
- [x] Gürültülü sinyal alımını oluştur
- [x] Chirp tabanlı demodülasyonu geliştir
- [x] Sembol ve bit hata hesaplamasını ekle
- [x] Fiziksel katman CRC kontrolünü ekle
- [x] Fiziksel katman BER/PER ölçümlerini ekle
- [x] CSS modelini link-level modeliyle karşılaştır
- [x] Büyük paket ve uzun süre testleri yap

## Aşama 7 — PySide6 arayüzü

- [x] Ana pencereyi oluştur
- [x] Simülasyon kontrol panelini oluştur
- [x] LoRa ayarları panelini oluştur
- [x] Gelişmiş paket ayarları panelini oluştur
- [x] Kanal ve ortam ayarları panelini oluştur
- [x] Cihaz ve hareket ayarları panelini oluştur
- [x] ACK ve trafik ayarları panelini oluştur
- [x] Sonuç ve özet panelini oluştur
- [x] Başlat/durdur kontrollerini bağla
- [x] Duraklat/devam ettir kontrollerini bağla
- [x] Gerçek zamanlı/hızlandırılmış mod seçimini bağla
- [x] Girdi doğrulama ve hata mesajlarını ekle
- [x] RSSI–zaman grafiğini ekle
- [x] SNR–zaman grafiğini ekle
- [x] Paket başarı/hata grafiğini ekle
- [x] BER/PER–zaman grafiğini ekle
- [x] Throughput–zaman grafiğini ekle
- [x] Gecikme–zaman grafiğini ekle
- [x] Cihaz konum ve hareket grafiğini ekle
- [x] Ortam karşılaştırma grafiklerini ekle
- [x] Mesafe–başarı oranı grafiğini ekle
- [x] Güç–başarı oranı grafiğini ekle
- [x] Grafiklerin açılıp kapatılabilmesini sağla
- [x] Arayüzün simülasyon iş parçacığıyla güvenli iletişimini sağla

## Aşama 8 — Kayıt ve raporlama

- [x] Paket bazlı sonuç veri yapısını oluştur
- [x] CSV dışa aktarma modülünü geliştir
- [x] JSON yapılandırma ve sonuç dışa aktarmasını geliştir
- [x] PNG grafik kaydını ekle
- [x] PDF rapor kaydını ekle
- [x] Simülasyon ayarlarını sonuçlarla birlikte kaydet
- [x] Ortam karşılaştırma sonuçlarını kaydet
- [x] ACK ve tekrar gönderim istatistiklerini kaydet
- [x] Duty-cycle ihlallerini raporla
- [x] Simülasyon özet raporunu oluştur
- [x] SER metriğini ekle
- [x] ACK başarı oranı metriğini ekle
- [x] Başarılı haberleşme mesafesi (mesafe taraması) metriğini ekle
- [x] Tahmini enerji tüketimi metriğini ekle (SX1276 TX/RX/uyku akımları)
- [x] Dosya adı ve kayıt klasörü seçimini arayüze ekle

## Aşama 9 — Test ve doğrulama

- [x] Parametre doğrulama testlerini yaz
- [x] CRC testlerini yaz
- [x] Paket üretim testlerini yaz
- [x] Paket hata testlerini yaz
- [x] Link budget doğrulama testini yap
- [x] Yol kaybı sonuçlarını teorik değerlerle karşılaştır
- [x] Alıcı hassasiyeti sonuçlarını kontrol et
- [x] RSSI hesaplarını doğrula
- [x] SNR hesaplarını doğrula
- [x] BER/PER hesaplarını doğrula
- [x] ACK timeout davranışını test et
- [x] Tekrar gönderim davranışını test et
- [x] Duty-cycle kontrolünü test et
- [x] Gerçek zamanlı çalışma testini yap
- [x] Hızlandırılmış çalışma testini yap
- [x] Çoklu cihaz testini yap
- [x] Hareketli cihaz testini yap
- [x] CSS ve link-level sonuçlarını karşılaştır
- [x] Uzun süreli simülasyon testi yap
- [x] CSV/JSON/PNG/PDF çıktılarının doğruluğunu kontrol et
- [x] Arayüz kullanılabilirlik testini yap (otomatik arayüz testleri + ekran görüntüleriyle görsel inceleme)
- [x] Hata durumlarını ve uygulama kapanmalarını test et

## Başlangıç prototipi için minimum görevler

> İlk çalışan sürüm için önce aşağıdaki görevlerin tamamlanması yeterlidir.

- [x] Aşama 1'in tamamlanması
- [x] Rastgele payload ve CRC desteği
- [x] Tek verici ve tek alıcı desteği
- [x] Link-level modelin tamamlanması
- [x] Serbest uzay ve AWGN kanalının eklenmesi
- [x] RSSI, SNR, PER ve throughput hesaplarının eklenmesi
- [x] Basit sürekli paket gönderimi
- [x] Temel ACK ve tekrar gönderim desteği
- [x] Basit PySide6 arayüzü
- [x] Başlat/durdur kontrolleri
- [x] En az iki canlı grafik
- [x] CSV ve JSON çıktı desteği

## Sürüm hedefleri

### v0.1 — Temel model

- [x] Tek verici–tek alıcı
- [x] Link-level model
- [x] Temel LoRa parametreleri
- [x] Serbest uzay + AWGN
- [x] PER, RSSI, SNR ve throughput
- [x] Komut satırı veya temel arayüz

### v0.2 — Trafik ve kanal genişletmeleri

- [x] Sürekli paket gönderimi
- [x] ACK ve tekrar gönderim
- [x] Duty-cycle kontrolü
- [x] Farklı ortam modelleri
- [x] Rayleigh/Rician sönümleme
- [x] CSV/JSON dışa aktarma

### v0.3 — Çoklu cihaz ve hareket

- [x] Çoklu verici/alıcı
- [x] Konumlandırma seçenekleri
- [x] Hareket modelleri
- [x] Doppler etkisi
- [x] Paket çakışmaları
- [x] Canlı konum grafiği

### v0.4 — Grafiksel uygulama

- [x] Tam PySide6 arayüzü
- [x] Tüm parametre panelleri
- [x] Canlı grafik seçimi
- [x] Ortam karşılaştırma ekranı
- [x] PNG/PDF raporlama

### v1.0 — Ayrıntılı ve doğrulanmış sürüm

- [x] CSS fiziksel katman modeli
- [x] Link-level ve CSS karşılaştırması
- [x] Kapsamlı test paketi (272 test, 19 dosya: yapılandırma, CRC, airtime, SER, kanal etkileri, ortamlar, hareket, çoklu cihaz/çakışma, ACK/duty-cycle, CSS, analiz/rapor, enerji, uzun süreli, arayüz, başarı kriterleri)
- [x] Uzun süreli simülasyon kararlılığı
- [x] Kullanım dokümantasyonu (README.md ve docs/KULLANIM.md)
- [x] Sonuçların yeniden üretilebilirliği
- [x] Başarı kriterlerinin tamamının karşılanması (tests/test_success_criteria.py, 10/10)
