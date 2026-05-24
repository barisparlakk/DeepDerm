# DeepDerm Geliştirme Yol Haritası

## Mevcut Mimari

```
DeepDerm/
├── backend/       Spring Boot 3 + Java 17 + PostgreSQL 16
├── dermai-ai/     FastAPI + YOLOv8 + MediaPipe (port 8000)
├── frontend/      React 19 + Vite + TailwindCSS (port 5173)
└── mobile/        React Native + Expo SDK 54 (hasta uygulaması)
```

**Veritabanı:** 17 hasta, 24 fotoğraf, 1 acil uyarı, 6 doktor notu

---

## Faz 1 — Bozuk Özellikleri Düzelt (Öncelikli)

### 1.1 Dashboard İstatistikleri (Şu an hepsi 0 gösteriyor)

**Sorun:** `frontend/src/services/api.js` içinde `apiGetDashboard` hardcoded stub döndürüyor.

**Backend:** `GET /dashboard` endpoint'i yok.

**Yapılacaklar:**
- [ ] `backend/.../controller/` altına `DashboardController.java` ekle
  - `GET /dashboard` → `{ totalPatients, pendingReviews, newPhotos, emergencyAlerts }`
- [ ] `frontend/src/services/api.js` içindeki stub'ları gerçek API çağrılarıyla değiştir:
  - `apiGetDashboard` → `GET /dashboard`
  - `apiGetNotifications` → `GET /notifications`
  - `apiMarkNotificationRead` → `PATCH /notifications/{id}/read`
  - `apiResolveAlert` → gerçek endpoint'e bağla

### 1.2 Bildirimler

**Sorun:** `apiGetNotifications`, `apiMarkNotificationRead`, `apiMarkAllRead`, `apiResolveAlert` hepsi stub.

Backend'de `NotificationController.java` çalışıyor — sadece frontend bağlantısı eksik.

---

## Faz 2 — Medikal Annotasyon Aracı (Video için Etkileyici Özellik)

### Konsept
Hasta fotoğrafları üzerine canvas tabanlı çizim/işaretleme aracı. Doktor lezyonları işaretleyip not ekleyebilir.

### Özellikler
- Dikdörtgen ve daire çizme (lezyon seçimi)
- Serbest çizim (freehand)
- Metin etiketi ekleme
- Renk seçici (farklı lezyon tipleri için)
- Annotasyonları kaydet (JSON olarak DB'ye)
- Kayıtlı annotasyonları yükle ve görüntüle

### Teknik Plan

**Backend:**
```sql
CREATE TABLE photo_annotation (
  id BIGSERIAL PRIMARY KEY,
  photo_id BIGINT REFERENCES photos(id),
  doctor_id BIGINT REFERENCES doctors(id),
  annotation_data JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
```
- `POST /photos/{id}/annotations`
- `GET /photos/{id}/annotations`

**Frontend (`PatientDetailPage.jsx`):**
- HTML5 Canvas overlay fotoğrafın üzerine
- Toolbar: seç, dikdörtgen, daire, kalem, metin, renk, sil
- Kaydet/Yükle butonları

---

## Faz 3 — Video Sunumu için Gösterişli Özellikler

### 3.1 Lezyon Trend Grafiği
- `recharts` kütüphanesi ile hasta bazında zaman-lezyon grafiği
- `PatientDetailPage` içinde, fotoğraf listesinin altında

### 3.2 Hasta PDF Raporu
- `jsPDF` + `html2canvas` ile tek tıkla PDF export
- Hasta bilgileri + fotoğraflar + AI analizleri + doktor notları

### 3.3 Karanlık Mod
- Tailwind `dark:` sınıfları
- Context/localStorage ile tema tercihi kalıcı

---

## Faz 4 — Ek İyileştirmeler

- [ ] Hasta listesinde arama ve filtreleme (isim, tarih, durum)
- [ ] Doktor not şablonları (sık kullanılan teşhis metinleri)
- [ ] Fotoğraf karşılaştırma modu (yan yana görüntüleme)
- [ ] AI güven skoru görselleştirmesi (progress bar / badge)

---

## Video Çekim Stratejisi

### Gösterilecek Akış
1. **Doktor girişi** → dashboard (gerçek istatistikler)
2. **Hasta listesi** → hasta seçimi
3. **Hasta detayı** → fotoğraf galerisi, AI analiz sonuçları
4. **Annotasyon aracı** → lezyon işaretleme, kaydetme
5. **Trend grafiği** → zaman içindeki değişim
6. **PDF export** → rapor indirme
7. **Bildirimler** → acil uyarı yönetimi
8. **Mobil** (kayıtlı ekran) → fotoğraf çekme, açı kontrolü, gönderme

### Teknik Derinlik Vurguları
- Spring Boot + JWT güvenlik katmanı
- FastAPI + YOLOv8 gerçek zamanlı deri analizi
- MediaPipe yüz açı tespiti
- PostgreSQL ilişkisel veri modeli
- React 19 + Expo cross-platform

---

## Öncelik Sırası

| Öncelik | Görev | Süre |
|---------|-------|------|
| 🔴 Kritik | Dashboard endpoint + frontend wiring | ~2 saat |
| 🔴 Kritik | Bildirim API bağlantısı | ~30 dk |
| 🟠 Yüksek | Annotasyon aracı (canvas) | ~4 saat |
| 🟡 Orta | Trend grafiği (recharts) | ~2 saat |
| 🟡 Orta | PDF export | ~1.5 saat |
| 🟢 Düşük | Karanlık mod | ~1 saat |
| 🟢 Düşük | Arama/filtreleme | ~1 saat |
