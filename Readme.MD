# DeepDerm — Uzaktan Akne Tedavi Takip Sistemi

Dermatologlar için geliştirilmiş, yapay zeka destekli uzaktan hasta takip ve akne tedavi yönetim platformu.

---

## Proje Mimarisi

```
DeepDerm/
├── frontend/      # React + Vite + Tailwind CSS  →  Doktor Paneli (Web)
├── backend/       # Spring Boot 3.3 + PostgreSQL  →  REST API
├── dermai-ai/     # FastAPI + YOLO + MediaPipe    →  AI Analiz Servisi
└── mobile/        # React Native + Expo SDK 54    →  Hasta Uygulaması (iOS)
```

### Servis Portları

| Servis | Port | Açıklama |
|--------|------|----------|
| PostgreSQL | 5432 | Veritabanı |
| Spring Boot | 8080 | Ana REST API |
| DermAI | 8000 | AI analiz mikro servisi |
| Frontend | 5173 | Doktor web paneli |
| Metro | 8081 | React Native bundler |

---

## Bileşenler

### 1. Frontend — Doktor Paneli

React 18 + Vite + Tailwind CSS ile geliştirilmiş web uygulaması. Doktorların hastalarını takip etmesi için tasarlanmıştır.

**Sayfalar**

| Sayfa | Yol | Açıklama |
|-------|-----|----------|
| Giriş | `/login` | JWT tabanlı doktor girişi |
| Panel | `/dashboard` | İstatistikler, son hastalar, bildirimler |
| Hastalar | `/patients` | Tüm hastalar, arama & filtre |
| Hasta Detayı | `/patients/:id` | Fotoğraf galerisi, AI analiz sonuçları, ilaçlar, notlar, yan etkiler, acil uyarılar |
| Bildirimler | `/notifications` | Birleşik bildirim gelen kutusu |

**Kurulum & Çalıştırma**

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

### 2. Backend — Spring Boot API

Spring Boot 3.3 + Spring Security + JWT ile geliştirilmiş RESTful API.

**Gereksinimler**
- Java 21+
- Maven 3.9+
- PostgreSQL 16+

**Çevre Değişkenleri**

```properties
DB_USERNAME=deepderm_user
DB_PASSWORD=yourpassword
JWT_SECRET=your-secret-key-minimum-32-characters
```

**Çalıştırma**

```bash
cd backend
mvn spring-boot:run
# → http://localhost:8080
```

**Temel API Endpoint'leri**

```
# Kimlik Doğrulama
POST   /auth/login                              → Doktor JWT token
POST   /auth/patient/register                  → Hasta kaydı
POST   /auth/patient/login                     → Hasta JWT token

# Doktor → Hasta Yönetimi
GET    /patients                               → Hasta listesi
GET    /patients/{id}                          → Hasta detayı
GET    /patients/{id}/photos                   → Fotoğraflar
GET    /patients/{id}/medications              → İlaçlar
POST   /patients/{id}/medications              → İlaç ekle
GET    /patients/{id}/side-effects             → Yan etkiler
GET    /patients/{id}/emergency-alerts         → Acil uyarılar
GET    /patients/{id}/notes                    → Doktor notları
POST   /patients/{id}/notes                    → Not ekle

# Hasta (Self)
GET    /patients/me                            → Profil bilgisi
PUT    /patients/me/password                   → Şifre değiştir
GET    /patients/me/photos                     → Kendi fotoğrafları
POST   /patients/me/photos                     → Fotoğraf yükle
GET    /patients/me/medications                → Kendi ilaçları
POST   /patients/me/medication-confirm         → İlaç dozu onayla
GET    /patients/me/doctor-notes               → Doktor notları
GET    /patients/me/doctor-notes/unread-count  → Okunmamış not sayısı
POST   /patients/me/side-effects               → Yan etki bildir
GET    /patients/me/emergency-alert/status     → Acil uyarı durumu
POST   /patients/me/emergency-alert            → Acil uyarı gönder

# AI Analiz
GET    /ai/analysis/{photoId}                  → Analiz sonucu
POST   /photos/{id}/analyze                    → AI analizini tetikle

# Bildirimler
GET    /notifications                          → Tüm bildirimler
PATCH  /notifications/{id}/read                → Okundu işaretle
```

**Kimlik Doğrulama**

`/auth/**` dışındaki tüm endpoint'ler için:
```
Authorization: Bearer <jwt_token>
```

---

### 3. DermAI — AI Analiz Servisi

FastAPI + YOLO + MediaPipe tabanlı yapay zeka mikro servisi. Spring Boot tarafından çağrılır.

**Gereksinimler**
- Python 3.10+
- `.venv/` sanal ortamı

**Kurulum**

```bash
cd dermai-ai
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Çalıştırma**

```bash
cd dermai-ai
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# → http://localhost:8000
```

**Çevre Değişkenleri** (`dermai-ai/.env`)

```env
DERMAI_MODEL_PATH=best.pt          # Özel eğitilmiş YOLO modeli
DERMAI_MODEL_VERSION=best-v1
DERMAI_CONF_THRESHOLD=0.25
DERMAI_IOU_THRESHOLD=0.45
DERMAI_HEURISTIC_FALLBACK=false
```

**Endpoint'ler**

```
GET   /health                   → Servis sağlık durumu & model bilgisi
POST  /analyze                  → Fotoğraf analizi (YOLO inferans)
GET   /results/{photo_id}       → Analiz sonucu getir
GET   /compare                  → İki analiz karşılaştır

POST  /quality/check-angle      → Yüz açısı doğrulama (MediaPipe)
POST  /quality/mask-eyes        → Göz maskeleme (gizlilik)
```

**AI Pipeline**

1. Görüntü decode & ön işleme (640×640 RGB)
2. YOLO inferans (`best.pt` — özel eğitilmiş akne modeli)
3. Bounding box çizimi & annotated görüntü kaydı
4. Klinik sonuç hesaplama (şiddet skoru, lezyon sayısı)
5. Veritabanına kayıt

**Yüz Açısı Doğrulama**

MediaPipe FaceLandmarker kullanılarak 3 farklı açı tespit edilir:
- `front` — Ön görünüm
- `right` — Sağ yanak
- `left` — Sol yanak

---

### 4. Mobile — Hasta Uygulaması (iOS)

React Native + Expo SDK 54 ile geliştirilmiş iOS hasta uygulaması.

**Gereksinimler**
- Node.js 18+
- Expo CLI
- iOS fiziksel cihaz (custom dev build)

**Kurulum**

```bash
cd mobile
npm install
```

**IP Güncelleme**

Ağ değiştiğinde `.env` dosyasını otomatik güncellemek için:

```bash
bash update-ip.sh
```

**Çalıştırma**

```bash
# Metro başlatma
npx expo start --clear --port 8081

# Cihaza yükleme
npx expo run:ios --device <UDID>
```

**Ekranlar**

| Ekran | Açıklama |
|-------|----------|
| Giriş / Kayıt | JWT tabanlı hasta kimlik doğrulama |
| Ana Sayfa | Hızlı erişim menüsü, okunmamış not sayacı |
| Fotoğraf Yükleme | Kamera ile 3 açıdan fotoğraf çekme ve yükleme |
| İlaçlarım | İlaç listesi ve doz onaylama |
| Doktor Notları | Doktordan gelen notları görüntüleme |
| Yan Etki Bildirimi | İlaç yan etkisi raporlama |
| Acil Bildirim | Doktora anlık acil uyarı gönderme |
| Profil | Hesap bilgileri ve şifre değiştirme |

**Fotoğraf Yükleme Akışı**

1. Kamera ile fotoğraf çek
2. DermAI `/quality/check-angle` ile açı doğrula (front → sağ yanak → sol yanak)
3. 3 açı tamamlandıktan sonra Spring Boot'a yükle
4. Spring Boot → DermAI `/analyze` çağırır
5. AI sonuçları doktor panelinde görüntülenir

---

## Tüm Servisleri Başlatma

```bash
# 1. PostgreSQL
LC_ALL=C /opt/homebrew/opt/postgresql@16/bin/postgres -D /opt/homebrew/var/postgresql@16 &

# 2. Spring Boot
cd backend && mvn spring-boot:run -q &

# 3. DermAI
cd dermai-ai && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload &

# 4. Frontend
cd frontend && npm run dev &

# 5. Mobile (önce IP güncelle)
cd mobile && bash update-ip.sh
npx expo start --clear --port 8081 &
npx expo run:ios --device <UDID>
```

---

## Teknoloji Yığını

| Katman | Teknoloji |
|--------|-----------|
| Doktor Paneli | React 18, Vite, Tailwind CSS 3 |
| Hasta Mobil | React Native, Expo SDK 54, Vision Camera v4 |
| Backend API | Spring Boot 3.3, Java 21, Spring Security |
| AI Servisi | FastAPI, YOLO (best.pt), MediaPipe, OpenCV |
| Veritabanı | PostgreSQL 16 |
| ORM | Spring Data JPA / Hibernate |
| Migration | Flyway |
| Kimlik Doğrulama | JWT (doktor & hasta ayrı token) |
| Build | Maven, npm, Expo EAS |

---

## Güvenlik

- JWT kimlik doğrulama (doktor ve hasta için ayrı token'lar)
- BCrypt şifre hash (cost 12)
- Rol tabanlı erişim kontrolü (doktor / hasta)
- Fotoğraflarda göz maskeleme (gizlilik)
- CORS kısıtlaması
- Stateless oturum yönetimi
- KVKK uyumlu veri silme desteği

---

## Geliştirme Notları

- **Ağ değişikliği:** Mac farklı bir WiFi'ye bağlandığında `mobile/update-ip.sh` çalıştırılmalı ve Metro yeniden başlatılmalıdır.
- **Public WiFi:** İstemci izolasyonu nedeniyle cihaz-cihaz iletişimi engellenebilir. iPhone hotspot kullanılması önerilir.
- **Model:** `dermai-ai/best.pt` — özel eğitilmiş akne lezyon tespit modeli.
- **iOS Build:** Fiziksel cihaz gerektirir, Expo Go değil custom dev build kullanılmaktadır.
