# DeepDerm — Uzaktan Akne Tedavi Takip Sistemi

Dermatologlar için uzaktan hasta takip ve akne tedavi yönetim paneli.

---

## Proje Yapısı

```
DeepDerm/
├── frontend/          # React + Vite + Tailwind CSS v3
└── backend/           # Spring Boot 3.3 + PostgreSQL + JWT
```

---

## Frontend

### Kurulum & Çalıştırma

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Sayfalar

| Sayfa | Yol | Açıklama |
|-------|-----|----------|
| Giriş | `/login` | JWT tabanlı doktor girişi |
| Panel | `/dashboard` | İstatistikler, son hastalar, bildirimler |
| Hastalar | `/patients` | Tüm hastalar, arama & filtre |
| Hasta Detayı | `/patients/:id` | Fotoğraf galerisi, ilaçlar, notlar, yan etkiler, acil uyarılar |
| Bildirimler | `/notifications` | Birleşik bildirim gelen kutusu |

### Demo Giriş
- **E-posta:** `ayse.kaya@deripoliklinigi.com`
- **Şifre:** herhangi 4+ karakter (mock mod)

---

## Backend

### Gereksinimler

- Java 21
- Maven 3.9+
- PostgreSQL 15+

### Veritabanı Kurulumu

```sql
CREATE DATABASE deepderm;
CREATE USER deepderm_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE deepderm TO deepderm_user;
```

### Çevre Değişkenleri

```bash
DB_USERNAME=deepderm_user
DB_PASSWORD=yourpassword
JWT_SECRET=your-secret-key-minimum-32-characters
```

### Çalıştırma

```bash
cd backend
./mvnw spring-boot:run
# → http://localhost:8080
```

Flyway migration otomatik çalışır ve şemayı oluşturur. Demo doktor hesabı otomatik eklenir.

### API Endpoint'leri

```
POST   /auth/login                         → JWT token al
GET    /patients                           → Hasta listesi
GET    /patients/{id}                      → Hasta detayı
GET    /patients/{id}/photos               → Fotoğraflar
GET    /patients/{id}/medications          → İlaçlar
POST   /patients/{id}/medications          → İlaç ekle
GET    /patients/{id}/side-effects         → Yan etkiler
GET    /patients/{id}/emergency-alerts     → Acil uyarılar
GET    /patients/{id}/notes                → Doktor notları
POST   /patients/{id}/notes                → Not ekle
GET    /notifications                      → Tüm bildirimler
PATCH  /notifications/{id}/read            → Okundu işaretle
POST   /photos/{id}/label                  → AI etiketi ekle
```

### Kimlik Doğrulama

Tüm `/auth/login` dışındaki endpoint'ler için Authorization header gereklidir:

```
Authorization: Bearer <jwt_token>
```

---

## Teknoloji Yığını

| Katman | Teknoloji |
|--------|-----------|
| Frontend | React 18, Vite, Tailwind CSS 3 |
| State | React Context + custom hooks |
| Routing | React Router v6 |
| Backend | Spring Boot 3.3, Java 21 |
| Güvenlik | Spring Security + JWT (JJWT 0.12) |
| Veritabanı | PostgreSQL 15 |
| Migration | Flyway |
| ORM | Spring Data JPA / Hibernate |
| Build | Maven |

---

## Güvenlik

- JWT kimlik doğrulama (24 saat geçerlilik)
- BCrypt şifre hash (cost 12)
- Role-based access: doktorlar yalnızca kendi hastalarına erişebilir
- CORS: sadece izin verilen origin'ler
- Stateless oturum (no server-side sessions)
- KVKK uyumu: veriler silinebilir tasarım

---

## Phase 2 (Gelecek)

- Python FastAPI AI modülü entegrasyonu
- AWS S3 fotoğraf depolama
- Fotoğraf kalite analizi
- AI tabanlı iyileşme skoru
