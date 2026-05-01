"""
=============================================================================
AŞAMA 03 v4 — Eğitim Döngüsü (asama_03_egitim_dongusu_v4.py)
=============================================================================
Proje   : YOLOv11 Tabanlı Akne Tespit ve Şiddet Derecelendirme Sistemi
Versiyon: 4.0 — "Saf YOLO" stratejisi

v3'te neler oldu? (Acımasız teşhis):
    v3'te mAP@50 0.221 → 0.140 düştü. Sebep:
    1. v2 best.pt + 1024px = ağırlık şoku (catastrophic forgetting)
    2. box=10.0 + 1024px = aşırı kutu üretimi → NMS time limit
    3. Focal Loss monkey-patch riski (kanıtlanmadı ama temizlik için kaldırıldı)

v4 stratejisi:
    YOLO'nun kurallarına göre oyna. Çekirdek loss'a dokunma.
    Sadece native parametrelerle 1024px'in çözünürlük gücünü kullan.

v3 → v4 Değişiklikler:
    - base_model: v2/best.pt → yolo11s.pt (sıfırdan COCO pretrained)
      Sebep: Ağırlık şokunu önler. 1024px'i baştan öğrensin.
    - box: 10.0 → 7.5 (varsayılan)
      Sebep: NMS time limit'in gerçek sebebi. 1024px feature map zaten
      4x büyük, agresif box weight ile model her piksele kutu çiziyordu.
    - lr0: 0.0005 → 0.001
      Sebep: Sıfırdan başladık, normal hız.
    - mixup: 0.15 → 0.10, copy_paste: 0.25 → 0.10
      Sebep: 1024px'de detay zaten net, gürültüyü azalt.
    - Focal Loss monkey-patch KALDIRILDI
      Sebep: Risk minimizasyonu. YOLO'nun kendi loss'u stabil çalışıyor.
    - multi_scale: 0.5 EKLENDİ
      Sebep: Model 512-1536px arası rastgele görür, çözünürlüğe daha
      iyi adapte olur. v3'teki tek-çözünürlük şoku yok.
    - es_patience: 20 → 25
      Sebep: Sıfırdan 1024px yavaş öğrenir, sabır artırıldı.
    - backbone_coz_epoch: 10 → 15
      Sebep: Sıfırdan başlayan model warmup'a daha çok ihtiyaç duyar.

Korunanlar:
    - imgsz=1024 (piksel yokoluşu çözümü)
    - batch=8 (VRAM güvenli)
    - cos_lr=True (cosine LR)
    - close_mosaic=15 (son fine-tune)
    - box_iou CPU patch (nvrtc compute_120 hatası, zorunlu)

Kullanım:
    from asama_03_egitim_dongusu_v4 import EgitimYoneticisi
    EgitimYoneticisi().calistir()
=============================================================================
"""

# =============================================================================
# IMPORTS
# =============================================================================

import csv
import logging
import shutil
import time
import warnings
from copy import deepcopy
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import torch
import yaml

warnings.filterwarnings("ignore", category=UserWarning)

try:
    from ultralytics import YOLO
    _ULTRALYTICS_OK = True
except ImportError as e:
    _ULTRALYTICS_OK = False
    warnings.warn(f"ultralytics yüklenemedi: {e}")


# =============================================================================
# 1. KONFİGÜRASYON
# =============================================================================

@dataclass
class EgitimYapilandirma:
    """v4 eğitim parametreleri — Saf YOLO stratejisi."""

    # ── Yollar ────────────────────────────────────────────────────────────────
    roboflow_root: str = (
        "/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi/Robo Flow V1"
    )
    islenmis_veri: str = ""
    egitim_cikti:  str = ""

    # ── Model — SIFIRDAN COCO PRETRAINED ──────────────────────────────────────
    # v3 dersi: 640px best.pt'den 1024px'e geçiş ağırlık şoku yaratır.
    # v4: yolo11s.pt (COCO) ile 1024px'i baştan öğren.
    base_model: str = "yolo11s.pt"

    # ── Temel eğitim ──────────────────────────────────────────────────────────
    epochs:    int   = 150
    batch:     int   = 8        # 1024px için VRAM güvenli (~9-10GB)
    img_boyut: int   = 1024     # Piksel yokoluşu çözümü
    workers:   int   = 8

    # ── Optimizer ─────────────────────────────────────────────────────────────
    optimizer:    str   = "AdamW"
    lr0:          float = 0.001    # Sıfırdan başlıyoruz, normal hız
    lrf:          float = 0.01     # Cosine bitiş çarpanı
    weight_decay: float = 0.0005
    momentum:     float = 0.937

    # ── Loss ağırlıkları — VARSAYILAN ─────────────────────────────────────────
    # v3 dersi: box=10.0 → NMS time limit. 1024px feature map zaten büyük,
    # ekstra ağırlık vermeye gerek yok.
    box: float = 7.5    # YOLO varsayılanı
    cls: float = 0.5
    dfl: float = 1.5

    # ── Augmentasyon — HAFİFLETİLDİ ───────────────────────────────────────────
    # v3 dersi: copy_paste=0.25 + mixup=0.15 + 1024px = aşırı gürültü.
    # 1024px'de detay zaten net, agresif augment etiket gürültüsünü artırıyor.
    mosaic:       float = 1.0
    mixup:        float = 0.10   # v3: 0.15
    copy_paste:   float = 0.10   # v3: 0.25
    close_mosaic: int   = 15
    degrees:      float = 10.0   # v3: 15.0
    shear:        float = 10.0
    hsv_s:        float = 0.7
    hsv_v:        float = 0.4

    # ── Multi-scale — YENİ ────────────────────────────────────────────────────
    # YOLO her batch'te imgsz'yi ±%50 rastgele değiştirir (512-1536 arası).
    # Model farklı çözünürlüklere adapte olur, tek-çözünürlük şoku olmaz.
    multi_scale: float = 0.5

    # ── Backbone dondurma ─────────────────────────────────────────────────────
    # v3: 10. v4: 15 — sıfırdan başlayan model warmup'a daha çok ihtiyaç duyar.
    backbone_coz_epoch: int = 15

    # ── Early Stopping — SABIR ARTIRILDI ──────────────────────────────────────
    # 1024px sıfırdan yavaş öğrenir, erken durdurma kötü.
    es_patience: int = 25   # v3: 20

    # ── AMP ───────────────────────────────────────────────────────────────────
    amp: bool = True

    # ── CUDA ──────────────────────────────────────────────────────────────────
    device: str = ""

    # ── Seed ──────────────────────────────────────────────────────────────────
    seed: int = 42

    def __post_init__(self):
        root = Path(self.roboflow_root)
        if not self.islenmis_veri:
            self.islenmis_veri = str(root / "islenmiş_veri")
        if not self.egitim_cikti:
            self.egitim_cikti = str(root / "egitim_v4")
        if not self.device:
            self.device = "0" if torch.cuda.is_available() else "cpu"


# =============================================================================
# 2. LOGGER
# =============================================================================

def logger_kur(isim: str, log_dosya: Optional[str] = None) -> logging.Logger:
    log = logging.getLogger(isim)
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    if log_dosya:
        Path(log_dosya).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dosya, encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
    return log


# =============================================================================
# 3. NVRTC PATCH — Tek kalan patch (donanım zorunluluğu)
# =============================================================================
# RTX 5070 Ti (compute_120) + torch 2.11 dev build kombinasyonunda
# box_iou CUDA kernel nvrtc JIT derleme hatası verir.
# Eğitim GPU'da, box_iou hesabı CPU'da yapılır.
# Bu patch v3'ten korundu — donanım sorunu, model davranışını etkilemez.

def box_iou_cpu_patch(log: Optional[logging.Logger] = None) -> None:
    """RTX 5070 Ti nvrtc uyumsuzluğu için box_iou CPU patch."""
    import ultralytics.utils.metrics as _m
    import ultralytics.models.yolo.detect.val as _v

    _orig = _m.box_iou

    def _cpu(box1, box2, eps=1e-7):
        return _orig(box1.cpu(), box2.cpu(), eps).to(box1.device)

    _m.box_iou = _cpu
    _v.box_iou = _cpu

    if log:
        log.info("box_iou CPU patch (nvrtc compute_120 fix) ✓")


# =============================================================================
# 4. CSV LOGGER
# =============================================================================

class CSVLogger:
    BASLIKLAR = [
        "epoch", "zaman_sn",
        "train_box_loss", "train_cls_loss", "train_dfl_loss",
        "val_box_loss", "val_cls_loss", "val_dfl_loss",
        "precision", "recall", "mAP50", "mAP50_95", "f1", "lr",
    ]

    def __init__(self, log_klasor: str):
        self.yol = Path(log_klasor) / "egitim_metrikleri.csv"
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        with open(self.yol, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(self.BASLIKLAR)

    def yaz(self, veri: dict) -> None:
        satir = [veri.get(k, "") for k in self.BASLIKLAR]
        with open(self.yol, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(satir)


# =============================================================================
# 5. EARLY STOPPING
# =============================================================================

class EarlyStopping:
    def __init__(self, patience: int = 25):
        self.patience       = patience
        self.en_iyi_map     = 0.0
        self.en_iyi_epoch   = 0
        self.sayac          = 0
        self.dur            = False
        self.en_iyi_weights = None

    def adim(self, epoch: int, map50: float, model_state: dict) -> bool:
        if map50 > self.en_iyi_map + 1e-4:
            self.en_iyi_map     = map50
            self.en_iyi_epoch   = epoch
            self.sayac          = 0
            self.en_iyi_weights = deepcopy(model_state)
        else:
            self.sayac += 1
            if self.sayac >= self.patience:
                self.dur = True
        return self.dur


# =============================================================================
# 6. CALLBACK'LER
# =============================================================================

class BackboneCallback:
    """
    Belirli epoch'ta backbone'u açar.
    YOLO yüklenince tüm parametreler requires_grad=False gelir.
    """

    def __init__(self, coz_epoch: int, log: logging.Logger):
        self.coz_epoch = coz_epoch
        self.log       = log
        self._cozuldu  = False

    def __call__(self, trainer) -> None:
        epoch = trainer.epoch

        # Epoch 0: backbone dondur
        if epoch == 0 and not self._cozuldu:
            seq = trainer.model.model
            for p in seq.parameters():
                p.requires_grad = True
            for i, katman in enumerate(seq):
                if i < 10:
                    for p in katman.parameters():
                        p.requires_grad = False
            egitilir = sum(p.numel() for p in seq.parameters() if p.requires_grad)
            toplam   = sum(p.numel() for p in seq.parameters())
            self.log.info(
                f"Epoch 0: Backbone donduruldu — "
                f"{egitilir/1e6:.2f}M / {toplam/1e6:.2f}M eğitilebilir"
            )

        # backbone_coz_epoch: tümünü aç
        if not self._cozuldu and epoch >= self.coz_epoch:
            for p in trainer.model.parameters():
                p.requires_grad = True
            egitilir = sum(p.numel() for p in trainer.model.parameters() if p.requires_grad)
            toplam   = sum(p.numel() for p in trainer.model.parameters())
            self._cozuldu = True
            self.log.info(
                f"Epoch {epoch}: Backbone çözüldü — "
                f"{egitilir/1e6:.2f}M / {toplam/1e6:.2f}M eğitilebilir"
            )


class EpochCallback:
    """Her epoch sonu CSV loglama + early stopping."""

    def __init__(
        self,
        csv_logger: CSVLogger,
        early_stop: EarlyStopping,
        log: logging.Logger,
    ):
        self.csv      = csv_logger
        self.es       = early_stop
        self.log      = log
        self._epoch_t = time.time()

    def __call__(self, trainer) -> None:
        epoch      = trainer.epoch
        metriks    = trainer.metrics or {}
        epoch_sure = time.time() - self._epoch_t
        self._epoch_t = time.time()

        def g(key, default=0.0):
            try: return float(metriks.get(key, default) or default)
            except: return default

        map50     = g("metrics/mAP50(B)")
        map5095   = g("metrics/mAP50-95(B)")
        precision = g("metrics/precision(B)")
        recall    = g("metrics/recall(B)")
        val_box   = g("val/box_loss")
        val_cls   = g("val/cls_loss")
        val_dfl   = g("val/dfl_loss")
        trn_box   = g("train/box_loss")
        trn_cls   = g("train/cls_loss")
        trn_dfl   = g("train/dfl_loss")
        f1        = 2*precision*recall/(precision+recall+1e-8) if (precision+recall) > 0 else 0.0

        try:
            lr = float(trainer.optimizer.param_groups[0]["lr"])
        except Exception:
            lr = 0.0

        self.csv.yaz({
            "epoch": epoch, "zaman_sn": round(epoch_sure, 1),
            "train_box_loss": round(trn_box, 6),
            "train_cls_loss": round(trn_cls, 6),
            "train_dfl_loss": round(trn_dfl, 6),
            "val_box_loss":   round(val_box, 6),
            "val_cls_loss":   round(val_cls, 6),
            "val_dfl_loss":   round(val_dfl, 6),
            "precision": round(precision, 6),
            "recall":    round(recall, 6),
            "mAP50":     round(map50, 6),
            "mAP50_95":  round(map5095, 6),
            "f1":        round(f1, 6),
            "lr":        round(lr, 8),
        })

        self.log.info(
            f"Epoch {epoch:3d} | mAP50={map50:.4f} | "
            f"P={precision:.3f} R={recall:.3f} F1={f1:.3f} | "
            f"box={val_box:.4f} cls={val_cls:.4f} | "
            f"LR={lr:.2e} | {epoch_sure:.0f}sn"
        )

        try:
            model_state = trainer.model.state_dict()
        except Exception:
            model_state = {}

        if self.es.adim(epoch, map50, model_state):
            self.log.info(
                f"Early Stopping: {self.es.patience} epoch iyileşme yok. "
                f"En iyi mAP@50={self.es.en_iyi_map:.4f} "
                f"(epoch {self.es.en_iyi_epoch})"
            )
            trainer.stop = True


# =============================================================================
# 7. EĞİTİM YÖNETİCİSİ
# =============================================================================

class EgitimYoneticisi:
    """
    Aşama 03 v4 — Saf YOLO eğitim orkestratörü.

    Adımlar:
        1. nvrtc patch (donanım zorunluluğu)
        2. data.yaml doğrula
        3. Modeli yükle (yolo11s.pt — COCO pretrained, sıfırdan)
        4. Callback'leri kaydet
        5. model.train() başlat (saf native parametreler)
        6. Checkpoint kopyala
        7. Özet rapor
    """

    def __init__(self, cfg: Optional[EgitimYapilandirma] = None):
        self.cfg = cfg or EgitimYapilandirma()

        egitim = Path(self.cfg.egitim_cikti)
        (egitim / "logs").mkdir(parents=True, exist_ok=True)

        self.log = logger_kur(
            "asama_03_v4",
            str(egitim / "logs" / "egitim.log"),
        )
        self.csv_logger = CSVLogger(str(egitim / "logs"))
        self.early_stop = EarlyStopping(patience=self.cfg.es_patience)
        self.model      = None

    # ── data.yaml doğrula ─────────────────────────────────────────────────────

    def _data_yaml_dogrula(self) -> str:
        yol = Path(self.cfg.islenmis_veri) / "data.yaml"
        if not yol.exists():
            raise FileNotFoundError(f"data.yaml bulunamadı: {yol}")
        with open(yol, encoding="utf-8") as f:
            icerik = yaml.safe_load(f)
        self.log.info(f"data.yaml: {yol}")
        self.log.info(f"  nc={icerik.get('nc')} | {icerik.get('names')}")
        return str(yol)

    # ── Model yükle — SIFIRDAN ────────────────────────────────────────────────

    def _model_yukle(self) -> None:
        """
        yolo11s.pt (COCO pretrained) — sıfırdan başla.
        v3 hatası: best.pt'den 1024px'e geçiş ağırlık şoku yaratıyor.
        v4: COCO ağırlıkları + 1024px → temiz adaptasyon.
        """
        self.log.info(f"Model yükleniyor: {self.cfg.base_model} (sıfırdan)")
        self.model = YOLO(self.cfg.base_model)
        toplam = sum(p.numel() for p in self.model.model.parameters())
        self.log.info(f"Model hazır: {toplam/1e6:.2f}M parametre (COCO pretrained)")

    # ── Eğitim ────────────────────────────────────────────────────────────────

    def _egitimi_baslat(self, data_yaml: str) -> None:
        # Callback'ler
        backbone_cb = BackboneCallback(
            coz_epoch=self.cfg.backbone_coz_epoch,
            log=self.log,
        )
        epoch_cb = EpochCallback(
            csv_logger=self.csv_logger,
            early_stop=self.early_stop,
            log=self.log,
        )
        self.model.add_callback("on_train_epoch_start", backbone_cb)
        self.model.add_callback("on_fit_epoch_end",     epoch_cb)

        egitim_klasor = str(
            Path(self.cfg.egitim_cikti) / "ultralytics_runs"
        )

        self.log.info("=" * 60)
        self.log.info("Eğitim başlıyor (v4 — Saf YOLO)...")
        self.log.info(f"  base_model  : {self.cfg.base_model} (SIFIRDAN)")
        self.log.info(f"  imgsz       : {self.cfg.img_boyut}px")
        self.log.info(f"  batch       : {self.cfg.batch}")
        self.log.info(f"  multi_scale : {self.cfg.multi_scale} (yeni!)")
        self.log.info(f"  box weight  : {self.cfg.box} (varsayılan)")
        self.log.info(f"  copy_paste  : {self.cfg.copy_paste} (hafifletildi)")
        self.log.info(f"  mixup       : {self.cfg.mixup} (hafifletildi)")
        self.log.info(f"  Focal Loss  : YOK (saf YOLO)")
        self.log.info(f"  ES patience : {self.cfg.es_patience}")
        self.log.info(f"  backbone    : epoch {self.cfg.backbone_coz_epoch}'de çözülür")
        self.log.info("=" * 60)

        self.model.train(
            data=data_yaml,
            epochs=self.cfg.epochs,
            imgsz=self.cfg.img_boyut,
            batch=self.cfg.batch,
            workers=self.cfg.workers,
            optimizer=self.cfg.optimizer,
            lr0=self.cfg.lr0,
            lrf=self.cfg.lrf,
            momentum=self.cfg.momentum,
            weight_decay=self.cfg.weight_decay,
            amp=self.cfg.amp,
            device=self.cfg.device,
            seed=self.cfg.seed,
            # Loss ağırlıkları — varsayılan
            box=self.cfg.box,
            cls=self.cfg.cls,
            dfl=self.cfg.dfl,
            # LR
            cos_lr=True,
            # Multi-scale — YENİ
            multi_scale=self.cfg.multi_scale,
            # Augmentasyon — hafifletildi
            mosaic=self.cfg.mosaic,
            mixup=self.cfg.mixup,
            copy_paste=self.cfg.copy_paste,
            close_mosaic=self.cfg.close_mosaic,
            degrees=self.cfg.degrees,
            shear=self.cfg.shear,
            hsv_s=self.cfg.hsv_s,
            hsv_v=self.cfg.hsv_v,
            # Kayıt
            project=egitim_klasor,
            name="akne_yolo11s_v4",
            exist_ok=True,
            save=True,
            val=True,
            plots=True,
            verbose=False,
        )

    # ── Checkpoint kopyala ────────────────────────────────────────────────────

    def _checkpoint_kopyala(self) -> None:
        ckpt = Path(self.cfg.egitim_cikti) / "checkpoints"
        ckpt.mkdir(parents=True, exist_ok=True)

        kaynak = (
            Path(self.cfg.egitim_cikti)
            / "ultralytics_runs"
            / "akne_yolo11s_v4"
            / "weights"
        )

        for isim in ["best.pt", "last.pt"]:
            src = kaynak / isim
            if src.exists():
                dst = ckpt / isim
                shutil.copy2(str(src), str(dst))
                self.log.info(f"Kopyalandı: {dst}")
            else:
                self.log.warning(f"Bulunamadı: {src}")

        self.log.info(
            f"En iyi epoch: {self.early_stop.en_iyi_epoch} "
            f"(mAP@50={self.early_stop.en_iyi_map:.4f})"
        )

    # ── Özet ──────────────────────────────────────────────────────────────────

    def _ozet(self) -> None:
        csv_yol = Path(self.cfg.egitim_cikti) / "logs" / "egitim_metrikleri.csv"
        if not csv_yol.exists():
            return
        with open(csv_yol, encoding="utf-8") as f:
            satirlar = list(csv.DictReader(f))
        if not satirlar:
            return
        try:
            en_iyi = max(satirlar, key=lambda r: float(r.get("mAP50") or 0))
            self.log.info("=" * 60)
            self.log.info("EĞİTİM ÖZET (v4)")
            self.log.info(f"  Toplam epoch  : {len(satirlar)}")
            self.log.info(f"  En iyi mAP@50 : {en_iyi.get('mAP50')} (epoch {en_iyi.get('epoch')})")
            self.log.info(f"  Precision     : {en_iyi.get('precision')}")
            self.log.info(f"  Recall        : {en_iyi.get('recall')}")
            self.log.info(f"  F1            : {en_iyi.get('f1')}")
            self.log.info(f"  Early Stop    : {'Evet' if self.early_stop.dur else 'Hayır'}")
            self.log.info(f"  Çıktı         : {self.cfg.egitim_cikti}")
            self.log.info("=" * 60)
        except Exception as e:
            self.log.warning(f"Özet hata: {e}")

    # ── README ────────────────────────────────────────────────────────────────

    def _readme_yaz(self) -> None:
        icerik = f"""# Aşama 03 v4 — Saf YOLO

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
"""
        yol = Path(self.cfg.egitim_cikti) / "README.md"
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(icerik, encoding="utf-8")

    # ── ANA ÇALIŞTIRICI ───────────────────────────────────────────────────────

    def calistir(self) -> None:
        if not _ULTRALYTICS_OK:
            raise ImportError("ultralytics kurulu değil.")

        self.log.info("=" * 60)
        self.log.info("AŞAMA 03 v4 — Saf YOLO Eğitim Döngüsü BAŞLIYOR")
        self.log.info(f"Çıktı : {self.cfg.egitim_cikti}")
        self.log.info(f"Device: {self.cfg.device}")
        self.log.info("=" * 60)

        t0 = time.time()

        # SADECE donanım patch'i — model davranışına müdahale yok
        box_iou_cpu_patch(self.log)

        self._readme_yaz()
        data_yaml = self._data_yaml_dogrula()
        self._model_yukle()
        self._egitimi_baslat(data_yaml)
        self._checkpoint_kopyala()
        self._ozet()

        self.log.info(
            f"AŞAMA 03 v4 TAMAMLANDI — {(time.time()-t0)/60:.1f} dk"
        )


# =============================================================================
# DOĞRUDAN ÇALIŞTIRMA
# =============================================================================

if __name__ == "__main__":
    print(f"CUDA : {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU  : {torch.cuda.get_device_name(0)}")
        print(f"VRAM : {torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB")

    EgitimYoneticisi().calistir()