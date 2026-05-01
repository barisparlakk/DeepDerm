# Aşama 03 v4 — Saf YOLO

## v3 → v4 Değişiklikler
| Parametre | v3 | v4 | Sebep |
|-----------|----|----|-------|
| base_model | v2/best.pt | yolo11s.pt | Ağırlık şokunu önle |
| box weight | 10.0 | 7.5 | NMS time limit fix |
| lr0 | 0.0005 | 0.001 | Sıfırdan başlıyoruz |
| mixup | 0.15 | 0.10 | Gürültü azaltma |
| copy_paste | 0.25 | 0.10 | Gürültü azaltma |
| Focal Loss | gamma=2.0 patch | YOK | Risk minimizasyonu |
| multi_scale | YOK | 0.5 | Çözünürlük adaptasyonu |
| ES patience | 20 | 25 | Sıfırdan yavaş öğrenir |
| backbone | 10 | 15 | Daha uzun warmup |

## v3 hataları (öğrenilen dersler)
1. v2 best.pt + 1024px = catastrophic forgetting
2. box=10.0 + 1024px = NMS time limit (binlerce sahte kutu)
3. Monkey-patch'ler core mekanizmaya müdahale

## Korunan
- imgsz=1024 (piksel yokoluşu çözümü)
- box_iou CPU patch (donanım zorunluluğu, model davranışını etkilemez)

## Çıktı
```
egitim_v4/
├── logs/egitim_metrikleri.csv
├── checkpoints/best.pt
└── ultralytics_runs/akne_yolo11s_v4/
```
