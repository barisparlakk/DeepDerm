# Aşama 03 v2 — Eğitim Döngüsü

## v1 → v2 Değişiklikler
- Custom DetectionTrainer KALDIRILDI → standart model.train()
- DynamicFocalLoss KALDIRILDI → fl_gamma=2.0 native
- ReduceLROnPlateau KALDIRILDI → cos_lr=True native
- copy_paste=0.15, mixup=0.15 eklendi

## Hiperparametreler
| Parametre | Değer |
|-----------|-------|
| Base model | yolo11s.pt |
| Epoch | 150 |
| Batch | 24 |
| fl_gamma | 2.0 |
| mosaic | 1.0 |
| mixup | 0.15 |
| copy_paste | 0.15 |
| Backbone çözme | epoch 15 |
| Early stop patience | 15 |

## Dizin
```
egitim_v2/
├── logs/
│   ├── egitim_metrikleri.csv
│   └── egitim.log
├── checkpoints/
│   ├── best.pt
│   └── last.pt
└── ultralytics_runs/
    └── akne_yolo11s_v2/   ← YOLO otomatik çıktı
```

## Sonraki
asama_04_klinik_siddet.py → best.pt ile klinik skorlama
