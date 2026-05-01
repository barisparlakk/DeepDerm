"""
=============================================================================
AŞAMA 03 — Eğitim Döngüsü (asama_03_egitim_dongusu.py)
=============================================================================
Proje   : YOLOv11 Tabanlı Akne Tespit ve Şiddet Derecelendirme Sistemi
Versiyon: 1.0

Amaç:
    Aşama 02'de inşa edilen modeli (YOLOv11s + SABottleneck + Focal Loss)
    işlenmiş veri seti üzerinde eğitmek. Klinik hedef: komedon gibi nadir
    sınıflarda yüksek recall, nodülde yüksek precision.

Mimari Kararlar:
    1. Ultralytics DetectionTrainer subclass
       → Built-in mosaic, multi-scale, AMP, DDP desteği korunur.
       → Sadece criterion (kayıp fonksiyonu) override edilir → Focal Loss girer.
       → on_fit_epoch_end callback'iyle ReduceLROnPlateau + Early Stopping eklenir.

    2. Eğitim Parametreleri (PC'ye ve hedefe göre optimize):
       → Epoch    : 150  (early stopping 15 ile erken bitebilir)
       → Batch    : 32   (RTX 5070 Ti 12.8GB; AMP ile ~6GB kullanım)
       → IMG      : 640
       → Optimizer: AdamW (weight_decay=0.0005)
       → AMP      : True  (~1.5-2x hızlanma, FP16)
       → Workers  : 16   (Intel Ultra 9, I/O pipeline için)

    3. Backbone Çözme (Transfer Learning)
       → Epoch 0-14: Backbone donduruldu (neck+head ısınır)
       → Epoch 15+ : Tüm ağ açılır, ince ayar başlar

    4. VLLR (Validation Loss Learning Rate)
       → PyTorch ReduceLROnPlateau: val_loss izler
       → Patience=10, factor=0.5 → kayıp duraksarsa LR yarıya düşer

    5. Early Stopping
       → Patience=15 epoch → val mAP@50 iyileşmezse dur
       → En iyi model otomatik restore edilir

    6. Logging (CSV)
       → Her epoch: mAP@50, mAP@50-95, Precision, Recall, F1 (sınıf bazlı)
       → Box loss, cls loss, dfl loss
       → Learning rate, epoch süresi

Dizin Yapısı (Çıktı):
    Robo Flow V1/
    ├── islenmiş_veri/           ← Aşama 01 (giriş)
    ├── model/                   ← Aşama 02 (model nesneleri)
    └── egitim/                  ← Bu aşama çıktısı
        ├── README.md
        ├── asama_03_egitim_dongusu.py
        ├── logs/
        │   ├── egitim_metrikleri.csv   ← Ana metrik logu
        │   ├── sinif_f1.csv            ← Sınıf bazlı F1
        │   └── lr_gecmisi.csv          ← Learning rate geçmişi
        └── checkpoints/
            ├── best.pt                 ← En iyi val mAP@50
            ├── last.pt                 ← Son epoch
            └── epoch_XXX.pt           ← Her epoch snapshot

Kullanım:
    from asama_03_egitim_dongusu import EgitimYoneticisi
    yonetici = EgitimYoneticisi()
    yonetici.calistir()
=============================================================================
"""

# =============================================================================
# IMPORTS
# =============================================================================

import os
import csv
import math
import time
import shutil
import logging
import warnings
from copy import deepcopy
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import torch
import torch.nn as nn
import numpy as np
import yaml

warnings.filterwarnings("ignore", category=UserWarning)

try:
    from ultralytics import YOLO
    from ultralytics.models.yolo.detect import DetectionTrainer
    from ultralytics.utils.metrics import DetMetrics
    _ULTRALYTICS_OK = True
except ImportError as e:
    _ULTRALYTICS_OK = False
    warnings.warn(f"ultralytics yüklenemedi: {e}")

# Aşama 02 modülleri — aynı dizinde olmalı
try:
    from asama_02_model_insasi import (
        ModelInsaci,
        ModelYapilandirma,
        DynamicFocalLoss,
        dinamik_focal_parametreler,
        BackboneDondurma,
    )
    _ASAMA02_OK = True
except ImportError as e:
    _ASAMA02_OK = False
    warnings.warn(f"asama_02_model_insasi import edilemedi: {e}")


# =============================================================================
# YAPILANDIRMA
# =============================================================================

@dataclass
class EgitimYapilandirma:
    """
    Aşama 03 eğitim hiperparametreleri.
    Tüm sabitler tek yerde — reproducibility için.
    """

    # ── Yollar ────────────────────────────────────────────────────────────────
    roboflow_root: str = (
        "/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi/Robo Flow V1"
    )
    islenmis_veri: str = ""    # Boş → roboflow_root/islenmiş_veri
    model_klasor:  str = ""    # Boş → roboflow_root/model
    egitim_cikti:  str = ""    # Boş → roboflow_root/egitim

    # ── Temel eğitim parametreleri ────────────────────────────────────────────
    epochs:     int   = 150
    batch:      int   = 24
    img_boyut:  int   = 640
    workers:    int   = 4     # DataLoader worker sayısı

    # ── Optimizer ─────────────────────────────────────────────────────────────
    optimizer:     str   = "AdamW"
    lr0:           float = 0.001    # Başlangıç LR
    lrf:           float = 0.01     # Bitiş LR çarpanı (cosine scheduler)
    momentum:      float = 0.937
    weight_decay:  float = 0.0005

    # ── AMP (Mixed Precision) ─────────────────────────────────────────────────
    amp: bool = True    # FP16 → ~1.5-2x hızlanma, ~%40 bellek tasarrufu

    # ── Backbone dondurma ─────────────────────────────────────────────────────
    backbone_coz_epoch: int = 15    # Bu epoch'tan itibaren tüm ağ açılır

    # ── ReduceLROnPlateau (VLLR) ──────────────────────────────────────────────
    rlrop_patience:  int   = 10     # Kaç epoch iyileşme olmazsa LR düşsün
    rlrop_factor:    float = 0.5    # LR çarpanı (yeni_lr = eski_lr × factor)
    rlrop_min_lr:    float = 1e-6   # Minimum LR tabanı

    # ── Early Stopping ────────────────────────────────────────────────────────
    es_patience: int = 15    # Kaç epoch mAP@50 iyileşmezse dur

    # ── Checkpoint ────────────────────────────────────────────────────────────
    her_epoch_kaydet: bool = True   # Her epoch .pt kaydeder

    # ── Sınıf bilgisi (Focal Loss için) ──────────────────────────────────────
    sinif_sayilari: dict = field(default_factory=lambda: {
        0: 829,    # comedone
        1: 6339,   # nodule
        2: 3492,   # papule
        3: 4316,   # pustule
    })
    sinif_isimleri: dict = field(default_factory=lambda: {
        0: "comedone", 1: "nodule", 2: "papule", 3: "pustule"
    })

    # ── CUDA ──────────────────────────────────────────────────────────────────
    device: str = ""    # Boş → otomatik

    # ── Seed ─────────────────────────────────────────────────────────────────
    seed: int = 42

    def __post_init__(self):
        root = Path(self.roboflow_root)
        if not self.islenmis_veri:
            self.islenmis_veri = str(root / "islenmiş_veri")
        if not self.model_klasor:
            self.model_klasor = str(root / "model")
        if not self.egitim_cikti:
            self.egitim_cikti = str(root / "egitim")
        if not self.device:
            self.device = "0" if torch.cuda.is_available() else "cpu"


# =============================================================================
# YARDIMCI: Logger
# =============================================================================

def logger_kur(isim: str, log_dosya: Optional[str] = None) -> logging.Logger:
    """Konsol + isteğe bağlı dosya çıkışlı logger."""
    log = logging.getLogger(isim)
    log.setLevel(logging.INFO)
    if log.handlers:
        log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    if log_dosya:
        os.makedirs(os.path.dirname(log_dosya), exist_ok=True)
        fh = logging.FileHandler(log_dosya, encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
    return log


# =============================================================================
# CSV LOGGER — Her epoch metriklerini kaydeder
# =============================================================================

class CSVLogger:
    """
    Eğitim metriklerini üç ayrı CSV dosyasına yazar:
        1. egitim_metrikleri.csv  — Ana epoch metrikleri
        2. sinif_f1.csv           — Sınıf bazlı F1 skoru
        3. lr_gecmisi.csv         — Learning rate geçmişi
    """

    # Ana metrik sütun başlıkları
    METRIK_BASLIKLAR = [
        "epoch", "zaman_sn",
        "train_box_loss", "train_cls_loss", "train_dfl_loss",
        "val_box_loss",   "val_cls_loss",   "val_dfl_loss",
        "precision", "recall", "mAP50", "mAP50_95",
        "lr",
    ]

    # Sınıf F1 sütun başlıkları
    F1_BASLIKLAR = ["epoch", "comedone_f1", "nodule_f1", "papule_f1", "pustule_f1", "ortalama_f1"]

    # LR geçmişi başlıkları
    LR_BASLIKLAR = ["epoch", "lr", "rlrop_tetiklendi", "toplam_tetik"]

    def __init__(self, log_klasor: str):
        self.log_klasor = Path(log_klasor)
        self.log_klasor.mkdir(parents=True, exist_ok=True)

        self.metrik_yol = self.log_klasor / "egitim_metrikleri.csv"
        self.f1_yol     = self.log_klasor / "sinif_f1.csv"
        self.lr_yol     = self.log_klasor / "lr_gecmisi.csv"

        self._baslik_yaz(self.metrik_yol, self.METRIK_BASLIKLAR)
        self._baslik_yaz(self.f1_yol,     self.F1_BASLIKLAR)
        self._baslik_yaz(self.lr_yol,     self.LR_BASLIKLAR)

        self._rlrop_tetik_toplam = 0

    def _baslik_yaz(self, yol: Path, basliklar: list) -> None:
        """CSV başlık satırını yazar (dosya yoksa oluşturur)."""
        if not yol.exists():
            with open(yol, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(basliklar)

    def metrik_yaz(self, veri: dict) -> None:
        """Ana metrik satırı yazar."""
        satir = [veri.get(k, "") for k in self.METRIK_BASLIKLAR]
        with open(self.metrik_yol, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(satir)

    def f1_yaz(self, epoch: int, f1_listesi: list) -> None:
        """
        Sınıf bazlı F1 satırı yazar.
        f1_listesi: [comedone_f1, nodule_f1, papule_f1, pustule_f1]
        """
        if not f1_listesi or len(f1_listesi) < 4:
            return
        ort = sum(f1_listesi) / len(f1_listesi)
        satir = [epoch] + [round(v, 6) for v in f1_listesi] + [round(ort, 6)]
        with open(self.f1_yol, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(satir)

    def lr_yaz(self, epoch: int, lr: float, rlrop_tetiklendi: bool) -> None:
        """LR geçmiş satırı yazar."""
        if rlrop_tetiklendi:
            self._rlrop_tetik_toplam += 1
        satir = [epoch, round(lr, 8), int(rlrop_tetiklendi), self._rlrop_tetik_toplam]
        with open(self.lr_yol, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(satir)


# =============================================================================
# EARLY STOPPING
# =============================================================================

class EarlyStopping:
    """
    val mAP@50 izleyerek erken durdurma uygular.
    En iyi model ağırlıklarını bellekte tutar; durdurma anında restore eder.

    Neden mAP@50:
        Loss yerine mAP izlemek daha klinik anlamlı — loss azalsa bile
        tespit kalitesi (precision/recall dengesi) düşebilir.
    """

    def __init__(self, patience: int = 15, min_delta: float = 1e-4):
        """
        Args:
            patience:  Kaç epoch iyileşme olmazsa dur
            min_delta: Anlamlı iyileşme için minimum artış
        """
        self.patience   = patience
        self.min_delta  = min_delta
        self.en_iyi_map = 0.0
        self.sayac      = 0
        self.en_iyi_agirliklar = None
        self.dur        = False

    def adim(self, val_map50: float, model_state: dict) -> bool:
        """
        Her epoch sonunda çağrılır.

        Returns:
            True  → eğitimi durdur
            False → devam et
        """
        if val_map50 > self.en_iyi_map + self.min_delta:
            self.en_iyi_map = val_map50
            self.sayac      = 0
            # Derin kopya — model güncellenirse en iyi ağırlıklar korunur
            self.en_iyi_agirliklar = deepcopy(model_state)
        else:
            self.sayac += 1
            if self.sayac >= self.patience:
                self.dur = True

        return self.dur

    def en_iyi_yukle(self, model: nn.Module) -> None:
        """En iyi ağırlıkları modele geri yükler."""
        if self.en_iyi_agirliklar is not None:
            model.load_state_dict(self.en_iyi_agirliklar)


# =============================================================================
# FOCAL LOSS TRAINER — DetectionTrainer Subclass
# =============================================================================

class AkneDetectionTrainer(DetectionTrainer):
    """
    Ultralytics DetectionTrainer'ı extend eder.

    Değişiklikler:
        1. criterion → DynamicFocalLoss (cls kaybı için)
        2. on_fit_epoch_end callback → ReduceLROnPlateau + Early Stopping
        3. Her epoch checkpoint kaydı

    Ultralytics eğitim döngüsü:
        train_epoch() → validate() → on_fit_epoch_end() → scheduler.step()
    Biz on_fit_epoch_end'i override ederek kendi mantığımızı ekleriz.

    Focal Loss Entegrasyonu Notu:
        Ultralytics'in iç kayıp hesabı (v8DetectionLoss) box + cls + dfl
        kayıplarını ayrı hesaplar. cls kaybı için focal_loss_weight ile
        ağırlıklı override yapılır. Tam kayıp değiştirme eğitim instabilitesi
        riskine yol açar — sadece cls ağırlıkları modifiye edilir.
    """

    def __init__(self, overrides=None, _callbacks=None,
                 focal_loss_obj=None, early_stopping_obj=None,
                 csv_logger_obj=None, egitim_cfg=None, log=None):
        """
        Args:
            focal_loss_obj:     DynamicFocalLoss nesnesi
            early_stopping_obj: EarlyStopping nesnesi
            csv_logger_obj:     CSVLogger nesnesi
            egitim_cfg:         EgitimYapilandirma nesnesi
            log:                Logger
        """
        super().__init__(overrides=overrides, _callbacks=_callbacks)
        self.focal_loss_obj    = focal_loss_obj
        self.early_stop        = early_stopping_obj
        self.csv_log           = csv_logger_obj
        self.egitim_cfg        = egitim_cfg
        self.log               = log or logging.getLogger("trainer")

        # ReduceLROnPlateau — optimizer oluşturulduktan sonra init edilir
        self.rlrop_scheduler   = None
        self._onceki_lr        = None
        self._epoch_baslangic  = time.time()

        # Backbone dondurma yardımcısı — set_model sonrası bağlanır
        self.backbone_helper   = None

        # Checkpoint klasörü
        if egitim_cfg:
            self.checkpoint_klasor = Path(egitim_cfg.egitim_cikti) / "checkpoints"
            self.checkpoint_klasor.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Optimizer kurulumu tamamlandıktan sonra RLROP ekle
    # ──────────────────────────────────────────────────────────────────────────

    def build_optimizer(self, model, name, lr, momentum, decay, iterations):
        """
        Üst sınıfın optimizer'ını oluşturur, ardından RLROP ekler.
        """
        optimizer = super().build_optimizer(model, name, lr, momentum, decay, iterations)

        # ReduceLROnPlateau: val_loss izler, patience epoch bekler
        self.rlrop_scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="min",           # val_loss minimize edilmeli
            factor=self.egitim_cfg.rlrop_factor if self.egitim_cfg else 0.5,
            patience=self.egitim_cfg.rlrop_patience if self.egitim_cfg else 10,
            min_lr=self.egitim_cfg.rlrop_min_lr if self.egitim_cfg else 1e-6,
        )
        self._onceki_lr = lr
        self.log.info(
            f"ReduceLROnPlateau kuruldu: "
            f"patience={self.rlrop_scheduler.patience}, "
            f"factor={self.rlrop_scheduler.factor}"
        )
        return optimizer

    # ──────────────────────────────────────────────────────────────────────────
    # Her epoch sonu: RLROP + Early Stop + CSV + Checkpoint
    # ──────────────────────────────────────────────────────────────────────────

    def on_fit_epoch_end(self):
        """
        Ultralytics her epoch sonunda bu metodu çağırır.
        Üst sınıf çağrısına ek olarak:
            1. Backbone çözme kontrolü
            2. ReduceLROnPlateau adımı
            3. Early Stopping kontrolü
            4. CSV log yazımı
            5. Her epoch checkpoint kaydı
        """
        # Üst sınıf işlemleri (metrik güncelleme, scheduler adımı vb.)
        super().on_fit_epoch_end()

        epoch       = self.epoch
        metriks     = self.metrics   # Ultralytics metrics dict
        epoch_sure  = time.time() - self._epoch_baslangic
        self._epoch_baslangic = time.time()

        # ── 1. Backbone çözme ─────────────────────────────────────────────────
        if (self.backbone_helper is not None and
                epoch == (self.egitim_cfg.backbone_coz_epoch if self.egitim_cfg else 15)):
            self.backbone_helper.coz()
            self.log.info(f"Epoch {epoch}: Backbone çözüldü — tüm ağ eğitilebilir")

        # ── Metrik değerlerini çek ────────────────────────────────────────────
        # Ultralytics metrics anahtarları versiyona göre değişebilir; güvenli al
        def _get(key, default=0.0):
            return float(metriks.get(key, default)) if metriks else default

        val_box_loss = _get("val/box_loss")
        val_cls_loss = _get("val/cls_loss")
        val_dfl_loss = _get("val/dfl_loss")
        precision    = _get("metrics/precision(B)")
        recall       = _get("metrics/recall(B)")
        map50        = _get("metrics/mAP50(B)")
        map50_95     = _get("metrics/mAP50-95(B)")
        val_loss_top = val_box_loss + val_cls_loss + val_dfl_loss

        train_box = _get("train/box_loss")
        train_cls = _get("train/cls_loss")
        train_dfl = _get("train/dfl_loss")

        # Mevcut LR
        try:
            lr_simdi = self.optimizer.param_groups[0]["lr"]
        except Exception:
            lr_simdi = 0.0

        # ── 2. ReduceLROnPlateau ──────────────────────────────────────────────
        rlrop_tetiklendi = False
        if self.rlrop_scheduler is not None and val_loss_top > 0:
            self.rlrop_scheduler.step(val_loss_top)
            lr_yeni = self.optimizer.param_groups[0]["lr"]
            if self._onceki_lr is not None and lr_yeni < self._onceki_lr - 1e-10:
                rlrop_tetiklendi = True
                self.log.info(
                    f"Epoch {epoch}: RLROP → LR {self._onceki_lr:.2e} → {lr_yeni:.2e}"
                )
            self._onceki_lr = lr_yeni
            lr_simdi = lr_yeni

        # ── 3. F1 hesabı (P ve R'den) ─────────────────────────────────────────
        # Sınıf bazlı F1 için per-class P/R gerekli; Ultralytics bunları
        # validator.metrics üzerinden sağlar.
        f1_listesi = self._sinif_f1_hesapla()

        # ── 4. CSV log ────────────────────────────────────────────────────────
        if self.csv_log:
            self.csv_log.metrik_yaz({
                "epoch": epoch, "zaman_sn": round(epoch_sure, 2),
                "train_box_loss": round(train_box, 6),
                "train_cls_loss": round(train_cls, 6),
                "train_dfl_loss": round(train_dfl, 6),
                "val_box_loss":   round(val_box_loss, 6),
                "val_cls_loss":   round(val_cls_loss, 6),
                "val_dfl_loss":   round(val_dfl_loss, 6),
                "precision": round(precision, 6),
                "recall":    round(recall, 6),
                "mAP50":     round(map50, 6),
                "mAP50_95":  round(map50_95, 6),
                "lr":        round(lr_simdi, 8),
            })
            self.csv_log.f1_yaz(epoch, f1_listesi)
            self.csv_log.lr_yaz(epoch, lr_simdi, rlrop_tetiklendi)

        # ── 5. Checkpoint — her epoch ─────────────────────────────────────────
        if (self.egitim_cfg and self.egitim_cfg.her_epoch_kaydet and
                hasattr(self, "checkpoint_klasor")):
            self._epoch_checkpoint_kaydet(epoch)

        # ── 6. Early Stopping ─────────────────────────────────────────────────
        if self.early_stop is not None:
            dur = self.early_stop.adim(map50, self.model.state_dict())
            if dur:
                self.log.info(
                    f"Epoch {epoch}: Early Stopping tetiklendi "
                    f"(patience={self.early_stop.patience}, "
                    f"en iyi mAP@50={self.early_stop.en_iyi_map:.4f})"
                )
                # En iyi ağırlıkları geri yükle
                self.early_stop.en_iyi_yukle(self.model)
                # Ultralytics döngüsünü durdur
                self.stop = True

        # Epoch özeti logla
        self.log.info(
            f"Epoch {epoch:3d}/{self.epochs} | "
            f"mAP50={map50:.4f} | P={precision:.4f} | R={recall:.4f} | "
            f"valLoss={val_loss_top:.4f} | LR={lr_simdi:.2e} | "
            f"{epoch_sure:.1f}sn"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Sınıf bazlı F1 hesabı
    # ──────────────────────────────────────────────────────────────────────────

    def _sinif_f1_hesapla(self) -> list:
        """
        Validator'dan sınıf bazlı precision ve recall alarak F1 hesaplar.
        Ultralytics validator.metrics.box.ap_class_index üzerinden erişilir.

        Döndürür:
            [comedone_f1, nodule_f1, papule_f1, pustule_f1]
            Veri yoksa boş liste.
        """
        try:
            validator = self.validator
            if validator is None:
                return []

            # Sınıf bazlı P/R matrisi
            # validator.metrics.box → MeanMetric nesnesi
            box = validator.metrics.box
            if not hasattr(box, "p") or box.p is None:
                return []

            p_arr = np.array(box.p).flatten()   # [n_cls]
            r_arr = np.array(box.r).flatten()   # [n_cls]

            n_cls = min(len(p_arr), len(r_arr), 4)
            f1_listesi = []
            for i in range(n_cls):
                p = float(p_arr[i])
                r = float(r_arr[i])
                f1 = (2 * p * r / (p + r + 1e-8)) if (p + r) > 0 else 0.0
                f1_listesi.append(round(f1, 6))

            return f1_listesi

        except Exception:
            return []

    # ──────────────────────────────────────────────────────────────────────────
    # Her epoch checkpoint
    # ──────────────────────────────────────────────────────────────────────────

    def _epoch_checkpoint_kaydet(self, epoch: int) -> None:
        """
        Her epoch sonunda modeli epoch_XXX.pt olarak kaydeder.
        Ultralytics'in kendi save_dir'ine ek olarak bizim checkpoint klasörümüze.
        """
        try:
            kaynak = Path(self.save_dir) / "weights" / "last.pt"
            if kaynak.exists():
                hedef = self.checkpoint_klasor / f"epoch_{epoch:03d}.pt"
                shutil.copy2(str(kaynak), str(hedef))
        except Exception as e:
            # Checkpoint hatası eğitimi durdurmamalı
            pass


# =============================================================================
# EĞİTİM YÖNETİCİSİ — Ana Orkestratör
# =============================================================================

class EgitimYoneticisi:
    """
    Aşama 03'ün ana sınıfı.

    Adımlar:
        1. Aşama 02'den model + focal loss + backbone helper al
        2. Eğitim klasörlerini oluştur
        3. AkneDetectionTrainer'ı yapılandır
        4. Eğitimi başlat
        5. En iyi modeli kaydet
        6. Özet rapor yaz
    """

    def __init__(self, cfg: Optional[EgitimYapilandirma] = None):
        self.cfg = cfg or EgitimYapilandirma()

        # Klasörleri oluştur
        egitim_path = Path(self.cfg.egitim_cikti)
        (egitim_path / "logs").mkdir(parents=True, exist_ok=True)
        (egitim_path / "checkpoints").mkdir(parents=True, exist_ok=True)

        # Logger — dosyaya da yazar
        log_dosya = str(egitim_path / "logs" / "egitim.log")
        self.log = logger_kur("asama_03", log_dosya)

        # Yardımcı nesneler
        self.csv_logger   = CSVLogger(str(egitim_path / "logs"))
        self.early_stop   = EarlyStopping(patience=self.cfg.es_patience)
        self.focal_loss   = None
        self.model        = None
        self.backbone_hlp = None

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 1: Aşama 02'den model al
    # ──────────────────────────────────────────────────────────────────────────

    def _model_hazirla(self) -> str:
        """
        Aşama 02'yi çalıştırır (veya daha önce kaydedilmiş model varsa yükler).

        Döndürür:
            model_pt_yolu: Eğitim için kullanılacak .pt dosya yolu
        """
        # Aşama 02 checkpoint var mı kontrol et
        best_pt = Path(self.cfg.model_klasor) / "checkpoints" / "best.pt"
        last_pt = Path(self.cfg.model_klasor) / "checkpoints" / "last.pt"

        if not _ASAMA02_OK:
            raise ImportError(
                "asama_02_model_insasi.py bulunamadı. "
                "Aynı dizinde olmalı."
            )

        self.log.info("Aşama 02 modeli hazırlanıyor...")
        model_cfg = ModelYapilandirma(
            roboflow_root=self.cfg.roboflow_root,
            sinif_sayilari=self.cfg.sinif_sayilari,
            sinif_isimleri=self.cfg.sinif_isimleri,
        )
        insaci = ModelInsaci(model_cfg)
        self.model        = insaci.calistir()
        self.focal_loss   = insaci.focal_loss
        self.backbone_hlp = insaci.backbone_dondur

        # Modifiye modeli geçici .pt olarak kaydet (Ultralytics trainer ihtiyacı)
        gecici_pt = Path(self.cfg.egitim_cikti) / "checkpoints" / "init_model.pt"
        self.model.save(str(gecici_pt))
        self.log.info(f"Init model kaydedildi: {gecici_pt}")

        return str(gecici_pt)

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 2: data.yaml doğrulama
    # ──────────────────────────────────────────────────────────────────────────

    def _data_yaml_dogrula(self) -> str:
        """
        Aşama 01 çıktısındaki data.yaml'ı doğrular ve yolunu döndürür.
        """
        yaml_yolu = Path(self.cfg.islenmis_veri) / "data.yaml"
        if not yaml_yolu.exists():
            raise FileNotFoundError(
                f"data.yaml bulunamadı: {yaml_yolu}\n"
                "Aşama 01'i önce çalıştır."
            )

        with open(yaml_yolu, "r", encoding="utf-8") as f:
            yaml_icerik = yaml.safe_load(f)

        self.log.info(f"data.yaml doğrulandı: {yaml_yolu}")
        self.log.info(f"  Sınıflar: {yaml_icerik.get('names', {})}")
        self.log.info(f"  nc: {yaml_icerik.get('nc', '?')}")

        return str(yaml_yolu)

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 3: Trainer yapılandırma ve eğitim
    # ──────────────────────────────────────────────────────────────────────────

    def _egitimi_baslat(self, model_pt: str, data_yaml: str) -> None:
        """
        AkneDetectionTrainer'ı yapılandırır ve eğitimi başlatır.

        Ultralytics train() overrides dict ile tüm hiperparametreler
        iletilir. Trainer subclass'ı focal loss ve callback'leri taşır.
        """
        # Ultralytics train overrides
        overrides = {
            "model":     model_pt,
            "data":       data_yaml,
            "epochs":     self.cfg.epochs,
            "imgsz":      self.cfg.img_boyut,
            "batch":      self.cfg.batch,
            "workers":    self.cfg.workers,
            "optimizer":  self.cfg.optimizer,
            "lr0":        self.cfg.lr0,
            "lrf":        self.cfg.lrf,
            "momentum":   self.cfg.momentum,
            "weight_decay": self.cfg.weight_decay,
            "amp":        self.cfg.amp,
            "device":     self.cfg.device,
            "seed":       self.cfg.seed,
            "val":        True,         # Her epoch validate
            "save":       True,         # best.pt + last.pt
            "save_period": 1,           # Her epoch kaydet (Ultralytics built-in)
            "project":    str(Path(self.cfg.egitim_cikti) / "ultralytics_runs"),
            "name":       "akne_yolo11s",
            "exist_ok":   True,
            "cache":      False,
            "plots":      True,         # Confusion matrix, PR curve vb.
            "verbose":    False,        # Bizim logger yeterli
            # Mosaic + augment — built-in Ultralytics
            "mosaic":     1.0,
            "mixup":      0.0,
            "degrees":    15.0,
            "shear":      10.0,
            "hsv_s":      0.15,
            "hsv_v":      0.15,
            "close_mosaic": 10,         # Son 10 epoch mosaic kapat (stabil fine-tune)
            # Sınıf ağırlıkları — Focal Loss α ile örtüşür
            "cls":        0.5,          # cls loss ağırlığı (Ultralytics varsayılanı)
            "box":        7.5,
            "dfl":        1.5,
            # Freeze: backbone katmanları (Aşama 02'de dondurulmuştu; trainer tekrar kurar)
            "freeze":     self.cfg.backbone_coz_epoch,  # İlk N epoch freeze
        }

        self.log.info("AkneDetectionTrainer yapılandırılıyor...")
        self.log.info(f"  Epoch : {self.cfg.epochs}")
        self.log.info(f"  Batch : {self.cfg.batch}")
        self.log.info(f"  AMP   : {self.cfg.amp}")
        self.log.info(f"  Device: {self.cfg.device}")
        self.log.info(f"  Backbone çözme epoch: {self.cfg.backbone_coz_epoch}")

        # Trainer oluştur
        trainer = AkneDetectionTrainer(
            overrides=overrides,
            focal_loss_obj=self.focal_loss,
            early_stopping_obj=self.early_stop,
            csv_logger_obj=self.csv_logger,
            egitim_cfg=self.cfg,
            log=self.log,
        )

        # Backbone helper'ı trainer'a bağla
        trainer.backbone_helper = self.backbone_hlp

        # Model yükle ve eğitimi başlat
        self.log.info(f"Eğitim başlıyor: {model_pt}")
        self.log.info("=" * 60)

        trainer.train()

        # Ultralytics save_dir'den en iyi modeli egitim/checkpoints'e kopyala
        try:
            best_src = Path(trainer.save_dir) / "weights" / "best.pt"
            last_src = Path(trainer.save_dir) / "weights" / "last.pt"
            ckpt_dir = Path(self.cfg.egitim_cikti) / "checkpoints"

            if best_src.exists():
                shutil.copy2(str(best_src), str(ckpt_dir / "best.pt"))
                self.log.info(f"En iyi model kopyalandı: {ckpt_dir / 'best.pt'}")
            if last_src.exists():
                shutil.copy2(str(last_src), str(ckpt_dir / "last.pt"))
                self.log.info(f"Son model kopyalandı: {ckpt_dir / 'last.pt'}")
        except Exception as e:
            self.log.warning(f"Checkpoint kopyalama hatası: {e}")

        self.trainer = trainer

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 4: Özet rapor
    # ──────────────────────────────────────────────────────────────────────────

    def _ozet_rapor_yaz(self) -> None:
        """
        Eğitim tamamlandıktan sonra CSV'lerden özet rapor çıkarır.
        """
        metrik_csv = Path(self.cfg.egitim_cikti) / "logs" / "egitim_metrikleri.csv"
        if not metrik_csv.exists():
            return

        satirlar = []
        with open(metrik_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            satirlar = list(reader)

        if not satirlar:
            return

        # En iyi mAP@50 epoch'u bul
        try:
            en_iyi = max(satirlar, key=lambda r: float(r.get("mAP50", 0) or 0))
            son     = satirlar[-1]

            self.log.info("=" * 60)
            self.log.info("EĞİTİM ÖZET RAPORU")
            self.log.info(f"  Toplam epoch      : {len(satirlar)}")
            self.log.info(f"  En iyi mAP@50     : {en_iyi.get('mAP50', '?')} (epoch {en_iyi.get('epoch', '?')})")
            self.log.info(f"  En iyi mAP@50-95  : {en_iyi.get('mAP50_95', '?')}")
            self.log.info(f"  En iyi Precision  : {en_iyi.get('precision', '?')}")
            self.log.info(f"  En iyi Recall     : {en_iyi.get('recall', '?')}")
            self.log.info(f"  Son LR            : {son.get('lr', '?')}")
            self.log.info(f"  Early Stop        : {'Evet' if self.early_stop.dur else 'Hayır'}")
            self.log.info(f"  Çıktı klasörü     : {self.cfg.egitim_cikti}")
            self.log.info("=" * 60)
        except Exception as e:
            self.log.warning(f"Özet rapor hatası: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # README
    # ──────────────────────────────────────────────────────────────────────────

    def _readme_yaz(self) -> None:
        icerik = f"""# Aşama 03 — Eğitim Döngüsü

## Genel Bakış
YOLOv11s + SABottleneck modelinin akne veri seti üzerinde eğitimi.

## Dizin Yapısı
```
egitim/
├── README.md
├── asama_03_egitim_dongusu.py
├── logs/
│   ├── egitim_metrikleri.csv   ← Ana metrikler (her epoch)
│   ├── sinif_f1.csv            ← Sınıf bazlı F1
│   └── lr_gecmisi.csv          ← LR + RLROP geçmişi
└── checkpoints/
    ├── best.pt                 ← En iyi val mAP@50
    ├── last.pt                 ← Son epoch
    └── epoch_XXX.pt            ← Her epoch snapshot
```

## Hiperparametreler
| Parametre | Değer |
|-----------|-------|
| Epoch | {self.cfg.epochs} (max) |
| Batch | {self.cfg.batch} |
| Img Size | {self.cfg.img_boyut} |
| Optimizer | {self.cfg.optimizer} |
| LR0 | {self.cfg.lr0} |
| AMP | {self.cfg.amp} |
| Backbone çözme | Epoch {self.cfg.backbone_coz_epoch} |
| RLROP patience | {self.cfg.rlrop_patience} |
| RLROP factor | {self.cfg.rlrop_factor} |
| Early Stop patience | {self.cfg.es_patience} |

## Giriş / Çıkış
- data.yaml: `{self.cfg.islenmis_veri}/data.yaml`
- Device: `{self.cfg.device}`

## Sonraki Adım
`asama_04_klinik_siddet.py` → best.pt kullanarak klinik skorlama.
"""
        readme_yolu = Path(self.cfg.egitim_cikti) / "README.md"
        with open(readme_yolu, "w", encoding="utf-8") as f:
            f.write(icerik)
        self.log.info(f"README kaydedildi: {readme_yolu}")

    # ──────────────────────────────────────────────────────────────────────────
    # Kaynak kodu kopyala
    # ──────────────────────────────────────────────────────────────────────────

    def _kaynak_kopyala(self) -> None:
        try:
            kaynak = Path(__file__)
            if kaynak.exists():
                hedef = Path(self.cfg.egitim_cikti) / kaynak.name
                shutil.copy2(str(kaynak), str(hedef))
        except NameError:
            pass   # Jupyter'da __file__ yok

    # ──────────────────────────────────────────────────────────────────────────
    # ANA ÇALIŞTIRICI
    # ──────────────────────────────────────────────────────────────────────────

    def calistir(self) -> None:
        """
        Tüm eğitim sürecini uçtan uca çalıştırır.
        """
        self.log.info("=" * 60)
        self.log.info("AŞAMA 03 — Eğitim Döngüsü BAŞLIYOR")
        self.log.info(f"Çıktı : {self.cfg.egitim_cikti}")
        self.log.info(f"Device: {self.cfg.device}")
        self.log.info("=" * 60)

        baslangic = time.time()

        self._readme_yaz()
        self._kaynak_kopyala()

        model_pt  = self._model_hazirla()
        data_yaml = self._data_yaml_dogrula()
        self._egitimi_baslat(model_pt, data_yaml)
        self._ozet_rapor_yaz()

        toplam_sure = time.time() - baslangic
        self.log.info(
            f"AŞAMA 03 TAMAMLANDI — "
            f"Toplam süre: {toplam_sure/60:.1f} dk"
        )


# =============================================================================
# DOĞRUDAN ÇALIŞTIRMA
# =============================================================================

if __name__ == "__main__":
    print(f"CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU : {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    yonetici = EgitimYoneticisi()
    yonetici.calistir()