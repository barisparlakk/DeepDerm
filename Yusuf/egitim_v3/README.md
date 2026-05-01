# Aşama 03 v3 — Eğitim Döngüsü

## v2 → v3 Değişiklikler
| Parametre | v2 | v3 | Sebep |
|-----------|----|----|-------|
| imgsz | 640 | 1024 | Piksel yokoluşu |
| batch | 24 | 8 | VRAM (1024px) |
| box | 7.5 | 10.0 | Kutu hassasiyeti |
| copy_paste | 0.15 | 0.25 | Tek-sınıf illüzyonu |
| Focal Loss | Yok | gamma=2.0 (patch) | Sınıf dengesi |
| base_model | yolo11s.pt | v2/best.pt | Fine-tune |
| lr0 | 0.001 | 0.0005 | Fine-tune |
| ES patience | 15 | 20 | 1024px yavaş öğrenir |

## Monkey-patch'ler
- `box_iou` → CPU (nvrtc compute_120 hatası)
- `v8DetectionLoss.bce` → `FocalBCE(gamma=2.0)`

## Çıktı
```
egitim_v3/
├── logs/egitim_metrikleri.csv
├── checkpoints/best.pt
└── ultralytics_runs/akne_yolo11s_v3/
```
