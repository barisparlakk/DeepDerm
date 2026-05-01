# Aşama 02 v2.1 — Model İnşası

## Değişiklikler (v2.0 → v2.1 bugfix)
- `parametre_sayisi()` düzeltildi: `requires_grad=True` filtresi eklendi
- `BackboneDondurma` artık doğru scope'ta çalışıyor (Sequential)
- `_dogrula()` eval/train geçişi tutarlı hale getirildi

## Model
| Bileşen | Detay |
|---------|-------|
| Base | yolo11s.pt (COCO pretrained) |
| Attention | C2PSA built-in (Layer 10) |
| Toplam param | 9.46M |
| Eğitilebilir | 5.01M (%52.9) |
| Dondurulmuş | 4.45M (Layer 0-9) |

## Focal Loss
fl_gamma=2.0 → Aşama 03 `model.train()` parametresiyle verilir.
Aşama 03'te `freeze=` parametresi VERİLMEMELİ.

## Dizin
```
model_v2/
├── README.md
├── asama_02_model_insasi_v2.py
├── yolo11s_akne_v2.yaml
└── checkpoints/    ← Aşama 03 eğitim çıktıları
```
