# NoteMaster 🧠📄

**NoteMaster**, klasik sınav okuma ve notlandırma sürecini yapay zeka ile dijitalleştiren, **öğretmen-benzeri puanlama** yapabilen masaüstü ve mobil destekli bir sınav değerlendirme sistemidir.

Amaç; öğretmenin karar mantığını taklit eden, gerekçeli, kısmi puanlama yapabilen ve görsel bağlamı dikkate alan bir AI asistanı sunmaktır.

---

## 📸 Ekran Görüntüleri

> Aşağıdaki görseller örnek yer tutucudur. Kendi repo yapına göre `assets/` altına ekleyebilirsin.

---

## ✨ Temel Özellikler

### 🧠 Öğretmen-Benzeri AI Puanlama

* **Kısmi Puanlama:** Tek hata yüzünden 0 yok. (0.25 / 0.50 / 0.75 gibi oranlar)
* **Gerekçeli Değerlendirme:**

  * *"Tabloda 1 hata bulundu, %75 puan verildi"*
* **Öğretmen Notları:**

  * "Yazım yanlışlarını dikkate alma"
  * "Sadece sonuca bak"
  * "İşlem adımlarına puan ver"

---

### 🖼️ Görsel Bağlamlı Analiz

* Sorular; grafik, tablo veya metin bağlamına bağlanabilir
* AI, cevabı **bağlama bakarak** değerlendirir
* **Anti-halüsinasyon:** Görselde bilgi yoksa uydurma yapılmaz

---

### 📄 Şablon (Model) Sistemi

* Boş sınav PDF’lerinden tekrar kullanılabilir modeller
* Her soru için:

  * Bölge tanımı
  * Puan
  * AI değerlendirme talimatı

---

### 📱 Mobil Tarama Entegrasyonu

* Telefonun **kendi kamera uygulaması** kullanılır
* 48MP+ / Gece Modu destekli
* Wi-Fi üzerinden PC’ye otomatik aktarım
* Otomatik hizalama ve görüntü iyileştirme

---

### 🧪 Deneysel: Otomatik Soru Tespiti (YOLO)

* Yeni model oluştururken sorular otomatik tespit edilebilir (Deneysel)
* Manuel düzenleme her zaman mümkündür

---

### 📊 Raporlama

* Sınıf geneli analiz
* PDF ve Excel çıktıları

---

## 🛠 Kullanılan Teknolojiler

* **Python 3.10+** (Qt tabanlı masaüstü uygulama)
* **Flutter** (Mobil tarayıcı)
* **Google Gemini API** (Değerlendirme & mantık)
* **Google Cloud Vision OCR**
* **OpenCV** (Görüntü işleme)
* **YOLO** (Deneysel otomatik bölge tespiti)

---

## ⚙️ Kurulum

### Gereksinimler

* Python 3.10+
* Flutter SDK
* Google Cloud API Anahtarları:

  * Gemini API Key
  * Vision Service Account (JSON)

---

### API Ayarları

Uygulamanın çalışması için gerekli anahtarları aşağıdaki gibi konfigüre edin `NoteMasterAI` klasörü içinde:

1.  **Google Vision:** `service-account.json` dosyasını ana klasöre kopyalayın.
2.  **Gemini API:** Program ilk açılışta sizden API anahtarını isteyecektir. Girilen anahtar `secrets.json` dosyasına otomatik kaydedilir.
    *   İsterseniz manuel olarak `secrets.json` adında bir dosya oluşturup içine anahtarınızı aşağıdaki gibi yazabilirsiniz:
    ```json
    {
        "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE"
    }
    ```

> 🔐 `service-account.json` ve `secrets.json` dosyalarını repoya **commit etmeyin**.

---

### Masaüstü Uygulaması

```bash
cd NoteMaster/NoteMasterAI
pip install -r requirements.txt
python main_qt.py
```

---

### Mobil Uygulama

```bash
cd NoteMaster/notemaster_mobile_scanner
flutter pub get
flutter run
```

---

## 🧭 Adım Adım Kullanım Kılavuzu

NoteMaster üç ana aşamadan oluşur: **Şablon Oluşturma**, **Sınav Kağıtlarını Tarama** ve **AI Puanlama**.

---

### 1️⃣ Şablon Oluşturma (Teaching Sekmesi)

1. Masaüstü uygulamasını açın ve sol üstten **Teaching** sekmesine geçin.
2. **➕ Yeni Model Oluştur** butonuna tıklayın.
3. Boş sınav kağıdının **PDF** dosyasını seçin.
4. Sistem size **"Soru alanları otomatik tespit edilsin mi?"** diye sorar.

   * **Evet:** AI (YOLO) soruları algılayıp kutular çizer (deneysel).
   * **Hayır:** Kutuları tamamen manuel çizersiniz.

#### ✏️ Düzenleme Ekranı

* **➕ Kutu Çiz:** Soru cevap alanlarını manuel olarak belirleyin.
* **Sağ Panel Ayarları:**

  * **Soru Etiketi:** (Örn: Soru 3)
  * **Puan:** (Örn: 10 puan)
  * **Öğretmen Notu:**

    * "Gidiş yoluna puan ver"
    * "Sadece sonucu değerlendir"
    * "Yazım yanlışlarını görmezden gel"

#### 📷 Soru Bağlamı Ekleme

* Eğer soru; üstteki bir **grafik, tablo veya metne** bağlıysa:

  * **📷 Soru Bağlamı Ekle** butonuna basın
  * İlgili alanı seçin
* AI, cevabı bu bağlama bakarak değerlendirir.

5. Tüm sayfalar tamamlandığında **💾 Kaydet ve Çık** ile modeli oluşturun.

---

### 2️⃣ Sınav Kağıtlarını Tarama (Mobil → PC)

1. **PC:** Grading sekmesine geçin, modeli ve kayıt klasörünü seçin.
2. Ekranda **IP adresi** görüntülenecektir.
3. **Mobil:** NoteMaster mobil uygulamasını açın ve IP adresini girin.(Portu girmenize gerek yok.)
4. **📷 Kamera** ikonuna basın:

   * Telefonun **kendi kamera uygulaması** açılır
   * Fotoğraf çekilir ve onaylanır
5. Görüntü otomatik olarak PC’ye aktarılır, hizalanır ve kaydedilir.

> 💡 İpucu: En iyi sonuç için **en yüksek megapiksell** ile çekim yapın

---

### 3️⃣ AI Puanlama (Grading Sekmesi)

1. **Puanlamayı Başlat** butonuna basın.

2. Sistem sırasıyla:

   * Görüntü iyileştirme (kontrast, keskinlik)
   * OCR (Google Vision)
   * AI değerlendirme (Gemini)

3. Her soru için:

   * Verilen puan
   * Gerekçe
   * Hata açıklaması listelenir

4. İşlem sonunda **PDF / Excel** raporu oluşturabilirsiniz.

---

## 🛠 Sorun Giderme

* **Mobil bağlanmıyor:** Aynı Wi-Fi ağı + güvenlik duvarı kontrolü
* **Yanlış okuma:** Öğretmen notlarına spesifik uyarılar ekleyin

  * Örn: *"31 ile 5'i karıştırma"*

---

## 👨‍💻 Geliştirici

**İbrahim Nuryağınlı**

---

## 📄 Lisans

Bu proje **MIT Lisansı** ile lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakınız.

---

> ✍️ Geliştirici Notu: Bu projede AI bir **hakem değil**, öğretmenin karar sürecini destekleyen bir **asistan** olarak konumlandırılmıştır.
