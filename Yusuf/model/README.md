# Aşama 02 — Model İnşası

## Genel Bakış
YOLOv11s tabanlı akne tespit modeli.
COCO pretrained transfer learning + SABottleneck (FPN) + Dinamik Focal Loss.

## Dizin Yapısı
```
model/
├── README.md                  ← Bu dosya
├── asama_02_model_insasi.py   ← Kaynak kod
├── yolo11s_akne.yaml          ← Model konfigürasyonu
└── checkpoints/               ← Aşama 03 eğitim çıktıları
```

## Modifikasyonlar

### 1. SABottleneck (Spatial Attention)
- FPN Layer 15 (P3, 256ch) → Küçük lezyonlar
- FPN Layer 18 (P4, 512ch) → Orta lezyonlar  
- FPN Layer 21 (P5, 512ch) → Büyük lezyonlar
- Kanal + Uzamsal dikkat + Residual bağlantı

### 2. Dinamik Focal Loss
Formül: γ = 2.0 × sqrt(max_count / class_count)

| Sınıf    | Sayı  | γ     | α     |
|----------|-------|-------|-------|
| comedone |   829 | 5.530 | 0.602 |
| nodule   |  6339 | 2.000 | 0.100 |
| papule   |  3492 | 2.695 | 0.162 |
| pustule  |  4316 | 2.424 | 0.136 |

### 3. Transfer Learning
- Base: yolo11s.pt (COCO pretrained)
- Backbone dondurma: İlk 10 layer (ısınma süresince)
- Çözme: Aşama 03 eğitim döngüsünde belirli epoch'ta

## Giriş / Çıkış
- Giriş (data): `/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi/Robo Flow V1/islenmiş_veri/data.yaml`
- Device: `cuda:0`
- Checkpoint çıkışı: `/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi/Robo Flow V1/model/checkpoints/`

## Sonraki Adım
`asama_03_egitim_dongusu.py` → Model bu aşamanın çıktısını yükler.
