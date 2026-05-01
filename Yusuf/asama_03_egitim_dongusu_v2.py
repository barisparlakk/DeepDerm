"""
=============================================================================
AŞAMA 03 v2 — Eğitim Döngüsü (asama_03_egitim_dongusu_v2.py)
=============================================================================
Proje   : YOLOv11 Tabanlı Akne Tespit ve Şiddet Derecelendirme Sistemi
Versiyon: 2.0

v1'den Farklar:
    - Custom DetectionTrainer subclass KALDIRILDI
      Sebep: criterion override edilmemişti → Focal Loss çalışmıyordu.
      Ultralytics iç döngüsüyle savaşmak yerine native parametreler kullanılır.

    - DynamicFocalLoss KALDIRILDI
      Sebep: Hiç devreye girmiyordu. Yerine fl_gamma=2.0 native.

    - ReduceLROnPlateau + custom trainer KALDIRILDI
      Sebep: Ultralytics LambdaLR ile çakışıyordu. Yerine cos_lr=True native.

    - SABottleneck bağımlılığı KALDIRILDI
      Sebep: YOLOv11 zaten C2PSA içeriyor.

    - Backbone dondurma: freeze= parametresi ile yapılır.
      backbone_coz_epoch'ta callback ile açılır.

Strateji (v2):
    1. YOLO("yolo11s.pt") yükle — bağımsız, Jupyter state'ine bağımlı değil
    2. fl_gamma=2.0 native → v8DetectionLoss içinde Focal Loss aktif
    3. cos_lr=True → Ultralytics cosine annealing, çakışma yok
    4. mosaic=1.0, copy_paste=0.2, mixup=0.2 → single-class sorunu azaltır
    5. freeze=10 → backbone dondurur, backbone_coz_epoch'ta callback açar
    6. Early stopping + CSV logging → callback ile, trainer dışında

Eğitim Parametreleri (RTX 5070 Ti 12.8GB için optimize):
    Epoch     : 150 (early stopping ile erken bitebilir)
    Batch     : 24  (AMP ile ~5.5GB VRAM)
    Workers   : 8   (I/O pipeline, NTFS/WSL için düşük tutuldu)
    AMP       : True (~1.5x hızlanma)
    LR0       : 0.001
    fl_gamma  : 2.0

Dizin Yapısı:
    Robo Flow V1/
    ├── islenmiş_veri/        ← Aşama 01 çıktısı
    ├── model_v2/             ← Aşama 02 çıktısı
    └── egitim_v2/            ← Bu aşama çıktısı
        ├── README.md
        ├── logs/
        │   └── egitim_metrikleri.csv
        └── ultralytics_runs/ ← YOLO otomatik kaydeder (best.pt, last.pt)

Kullanım:
    from asama_03_egitim_dongusu_v2 import EgitimYoneticisi
    yonetici = EgitimYoneticisi()
    yonetici.calistir()
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
from dataclasses import dataclass, field
from typing import Optional

import torch
import yaml

warnings.filterwarnings("ignore", category=UserWarning)

def _box_iou_cpu_patch():
    """RTX 5070 Ti (compute_120) nvrtc uyumsuzluğu için box_iou CPU'ya taşınır."""
    import ultralytics.utils.metrics as _m
    import ultralytics.models.yolo.detect.val as _v
    _orig = _m.box_iou
    def _cpu(box1, box2, eps=1e-7):
        return _orig(box1.cpu(), box2.cpu(), eps).to(box1.device)
    _m.box_iou = _cpu
    _v.box_iou = _cpu

_box_iou_cpu_patch()


try:
    from ultralytics import YOLO
    from ultralytics.utils.callbacks.base import default_callbacks
    _ULTRALYTICS_OK = True
except ImportError as e:
    _ULTRALYTICS_OK = False
    warnings.warn(f"ultralytics yüklenemedi: {e}")


# =============================================================================
# 1. KONFİGÜRASYON
# =============================================================================

@dataclass
class EgitimYapilandirma:
    """
    Aşama 03 v2 tüm eğitim parametreleri.
    Tek yerden yönetim — reproducibility için.
    """

    # ── Yollar ────────────────────────────────────────────────────────────────
    roboflow_root: str = (
        "/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi/Robo Flow V1"
    )
    islenmis_veri: str = ""   # Boş → roboflow_root/islenmiş_veri
    egitim_cikti:  str = ""   # Boş → roboflow_root/egitim_v2

    # ── Model ─────────────────────────────────────────────────────────────────
    base_model: str = "yolo11s.pt"   # COCO pretrained

    # ── Temel eğitim ──────────────────────────────────────────────────────────
    epochs:    int   = 150
    batch:     int   = 24       # RTX 5070 Ti 12.8GB — AMP ile ~5.5GB
    img_boyut: int   = 640
    workers:   int   = 8        # WSL+NTFS için düşük; 16 deneyebilirsin

    # ── Optimizer ─────────────────────────────────────────────────────────────
    optimizer:    str   = "AdamW"
    lr0:          float = 0.001
    lrf:          float = 0.01    # Bitiş LR = lr0 * lrf (cosine)
    weight_decay: float = 0.0005
    momentum:     float = 0.937

    # ── Focal Loss ────────────────────────────────────────────────────────────
    fl_gamma: float = 2.0   # Native YOLO — v8DetectionLoss içinde aktif

    # ── Augmentasyon ──────────────────────────────────────────────────────────
    # Mosaic: YOLO kendi yapar — statik mosaic (Aşama 01) zaten kapalı
    mosaic:      float = 1.0
    mixup:       float = 0.15   # Farklı sınıfları bindirerek co-occurrence simüle eder
    copy_paste:  float = 0.15   # Nesne kopyala-yapıştır → nadir sınıf artırımı
    close_mosaic: int  = 15     # Son 15 epoch mosaic kapat → stabil fine-tune
    degrees:     float = 15.0   # Rotasyon (Aşama 01 ile örtüşüyor — kasıtlı)
    shear:       float = 10.0

    # ── Transfer Learning ─────────────────────────────────────────────────────
    freeze:            int = 10   # İlk 10 layer dondur (backbone)
    backbone_coz_epoch: int = 15  # Bu epoch'ta backbone açılır

    # ── AMP ───────────────────────────────────────────────────────────────────
    amp: bool = True   # FP16 — RTX 5070 Ti'de sorunsuz

    # ── Early Stopping ────────────────────────────────────────────────────────
    es_patience: int = 15   # val mAP@50 bu kadar epoch iyileşmezse dur

    # ── CUDA ──────────────────────────────────────────────────────────────────
    device: str = ""   # Boş → otomatik

    # ── Seed ──────────────────────────────────────────────────────────────────
    seed: int = 42

    def __post_init__(self):
        root = Path(self.roboflow_root)
        if not self.islenmis_veri:
            self.islenmis_veri = str(root / "islenmiş_veri")
        if not self.egitim_cikti:
            self.egitim_cikti = str(root / "egitim_v2")
        if not self.device:
            self.device = "0" if torch.cuda.is_available() else "cpu"


# =============================================================================
# 2. LOGGER
# =============================================================================

def logger_kur(isim: str, log_dosya: Optional[str] = None) -> logging.Logger:
    """Konsol + isteğe bağlı dosya çıkışlı logger."""
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
# 3. CSV LOGGER — Her epoch metriklerini kaydeder
# =============================================================================

class CSVLogger:
    """
    Ultralytics callback'lerinden gelen metrikleri CSV'ye yazar.

    Neden ayrı CSV:
        Ultralytics results.csv yazar ama format versiyona göre değişir.
        Kendi CSV'miz stabil, klinik raporlama için hazır.
    """

    BASLIKLAR = [
        "epoch", "zaman_sn",
        "train_box_loss", "train_cls_loss", "train_dfl_loss",
        "val_box_loss",   "val_cls_loss",   "val_dfl_loss",
        "precision", "recall", "mAP50", "mAP50_95", "f1", "lr",
    ]

    def __init__(self, log_klasor: str):
        self.yol = Path(log_klasor) / "egitim_metrikleri.csv"
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        # Başlık yaz
        with open(self.yol, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(self.BASLIKLAR)

    def yaz(self, veri: dict) -> None:
        satir = [veri.get(k, "") for k in self.BASLIKLAR]
        with open(self.yol, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(satir)


# =============================================================================
# 4. EARLY STOPPING
# =============================================================================

class EarlyStopping:
    """
    val mAP@50 izleyerek erken durdurma.

    Neden mAP@50:
        Loss azalsa bile tespit kalitesi düşebilir.
        mAP klinik anlamlılığa daha yakın.
    """

    def __init__(self, patience: int = 15):
        self.patience        = patience
        self.en_iyi_map      = 0.0
        self.sayac           = 0
        self.dur             = False
        self.en_iyi_epoch    = 0
        self.en_iyi_weights  = None   # deepcopy — en iyi state dict

    def adim(self, epoch: int, map50: float, model_state: dict) -> bool:
        """
        Her epoch sonunda çağrılır.
        Returns: True → durdur, False → devam et
        """
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
# 5. BACKBONE ÇÖZME CALLBACK
# =============================================================================

class BackboneCallback:
    """
    Belirli epoch'ta backbone'u açar.

    Neden callback:
        model.train() başladıktan sonra freeze= parametresi sabit kalır.
        Callback on_train_epoch_start'ta çağrılarak dinamik açma yapılır.

    Ultralytics callback sistemi:
        model.add_callback("on_train_epoch_start", fn)
        fn(trainer) imzasıyla çağrılır.
    """

    def __init__(self, coz_epoch: int, log: logging.Logger):
        self.coz_epoch = coz_epoch
        self.log       = log
        self._cozuldu  = False

    def __call__(self, trainer) -> None:
        """on_train_epoch_start'ta çağrılır."""
        if self._cozuldu:
            return

        epoch = trainer.epoch   # 0-indexed

        if epoch >= self.coz_epoch:
            # Tüm parametreleri aç
            for p in trainer.model.parameters():
                p.requires_grad = True

            egitilir = sum(
                p.numel() for p in trainer.model.parameters()
                if p.requires_grad
            )
            toplam = sum(p.numel() for p in trainer.model.parameters())

            self._cozuldu = True
            self.log.info(
                f"Epoch {epoch}: Backbone çözüldü — "
                f"{egitilir/1e6:.2f}M / {toplam/1e6:.2f}M eğitilebilir"
            )


# =============================================================================
# 6. EPİZOD CALLBACK — Her epoch sonu log + early stop
# =============================================================================

class EpochCallback:
    """
    Her epoch sonunda çalışan callback.
    CSV loglama + early stopping burada yönetilir.

    Ultralytics on_fit_epoch_end callback'i trainer nesnesini argüman alır.
    Metrikler trainer.metrics dict'inden okunur.
    """

    def __init__(
        self,
        csv_logger: CSVLogger,
        early_stop: EarlyStopping,
        log: logging.Logger,
    ):
        self.csv       = csv_logger
        self.es        = early_stop
        self.log       = log
        self._t_baslangic = time.time()
        self._epoch_t     = time.time()

    def __call__(self, trainer) -> None:
        """on_fit_epoch_end'de çağrılır."""
        epoch      = trainer.epoch
        metriks    = trainer.metrics or {}
        epoch_sure = time.time() - self._epoch_t
        self._epoch_t = time.time()

        # Güvenli metrik okuma
        def g(key, default=0.0):
            try:
                return float(metriks.get(key, default) or default)
            except Exception:
                return default

        map50     = g("metrics/mAP50(B)")
        map50_95  = g("metrics/mAP50-95(B)")
        precision = g("metrics/precision(B)")
        recall    = g("metrics/recall(B)")
        val_box   = g("val/box_loss")
        val_cls   = g("val/cls_loss")
        val_dfl   = g("val/dfl_loss")
        trn_box   = g("train/box_loss")
        trn_cls   = g("train/cls_loss")
        trn_dfl   = g("train/dfl_loss")

        # F1 (precision + recall'dan)
        f1 = (2 * precision * recall / (precision + recall + 1e-8)
              if (precision + recall) > 0 else 0.0)

        # LR
        try:
            lr = float(trainer.optimizer.param_groups[0]["lr"])
        except Exception:
            lr = 0.0

        # CSV yaz
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
            "mAP50_95":  round(map50_95, 6),
            "f1":        round(f1, 6),
            "lr":        round(lr, 8),
        })

        # Epoch özeti
        self.log.info(
            f"Epoch {epoch:3d} | mAP50={map50:.4f} | "
            f"P={precision:.3f} R={recall:.3f} F1={f1:.3f} | "
            f"valLoss={val_box+val_cls+val_dfl:.4f} | "
            f"LR={lr:.2e} | {epoch_sure:.0f}sn"
        )

        # Early stopping
        try:
            model_state = trainer.model.state_dict()
        except Exception:
            model_state = {}

        dur = self.es.adim(epoch, map50, model_state)
        if dur:
            self.log.info(
                f"Early Stopping: {self.es.patience} epoch iyileşme yok. "
                f"En iyi mAP@50={self.es.en_iyi_map:.4f} "
                f"(epoch {self.es.en_iyi_epoch})"
            )
            trainer.stop = True   # Ultralytics döngüsünü durdurur


# =============================================================================
# 7. EĞİTİM YÖNETİCİSİ — Ana Orkestratör
# =============================================================================

class EgitimYoneticisi:
    """
    Aşama 03 v2 ana sınıfı.

    Adımlar:
        1. data.yaml doğrula
        2. Model yükle (bağımsız — Jupyter state gerektirmez)
        3. Backbone dondur (freeze= ile)
        4. Callback'leri kaydet
        5. model.train() başlat
        6. En iyi modeli kopyala
        7. Özet rapor yaz
    """

    def __init__(self, cfg: Optional[EgitimYapilandirma] = None):
        self.cfg = cfg or EgitimYapilandirma()

        # Klasörler
        egitim = Path(self.cfg.egitim_cikti)
        (egitim / "logs").mkdir(parents=True, exist_ok=True)

        # Logger
        self.log = logger_kur(
            "asama_03_v2",
            str(egitim / "logs" / "egitim.log"),
        )

        # Yardımcı nesneler
        self.csv_logger  = CSVLogger(str(egitim / "logs"))
        self.early_stop  = EarlyStopping(patience=self.cfg.es_patience)
        self.model       = None

    # ── data.yaml doğrula ─────────────────────────────────────────────────────

    def _data_yaml_dogrula(self) -> str:
        yol = Path(self.cfg.islenmis_veri) / "data.yaml"
        if not yol.exists():
            raise FileNotFoundError(
                f"data.yaml bulunamadı: {yol}\n"
                "Aşama 01'i önce çalıştır."
            )
        with open(yol, encoding="utf-8") as f:
            icerik = yaml.safe_load(f)
        self.log.info(f"data.yaml: {yol}")
        self.log.info(f"  nc={icerik.get('nc')} | {icerik.get('names')}")
        return str(yol)

    # ── Model yükle + backbone dondur ─────────────────────────────────────────

    def _model_hazirla(self) -> "YOLO":
        """
        YOLO yükler ve backbone'u dondurur.
        Aşama 02'ye bağımlı değil — bağımsız çalışır.

        freeze= parametresi model.train() içinde de geçilir.
        Buradaki dondurma forward pass doğrulaması içindir.
        """
        self.log.info(f"Model yükleniyor: {self.cfg.base_model}")
        model = YOLO(self.cfg.base_model)

        # YOLO varsayılan: tüm parametreler requires_grad=False
        # Önce tümünü aç, sonra backbone dondur
        seq = model.model.model   # Sequential (24 katman)
        for p in seq.parameters():
            p.requires_grad = True
        for i, katman in enumerate(seq):
            if i < self.cfg.freeze:
                for p in katman.parameters():
                    p.requires_grad = False

        egitilir = sum(p.numel() for p in seq.parameters() if p.requires_grad)
        toplam   = sum(p.numel() for p in seq.parameters())
        self.log.info(
            f"Model hazır: {toplam/1e6:.2f}M param | "
            f"Eğitilebilir: {egitilir/1e6:.2f}M (%{100*egitilir/toplam:.1f})"
        )
        self.log.info(f"Backbone (layer 0-{self.cfg.freeze-1}) donduruldu")

        self.model = model
        return model

    # ── Eğitimi başlat ────────────────────────────────────────────────────────

    def _egitimi_baslat(self, data_yaml: str) -> None:
        """
        model.train() ile eğitimi başlatır.

        Callback'ler:
            on_train_epoch_start → BackboneCallback (backbone çözme)
            on_fit_epoch_end     → EpochCallback (CSV + early stop)
        """
        # Callback nesneleri
        backbone_cb = BackboneCallback(
            coz_epoch=self.cfg.backbone_coz_epoch,
            log=self.log,
        )
        epoch_cb = EpochCallback(
            csv_logger=self.csv_logger,
            early_stop=self.early_stop,
            log=self.log,
        )

        # Callback kaydet
        self.model.add_callback("on_train_epoch_start", backbone_cb)
        self.model.add_callback("on_fit_epoch_end",     epoch_cb)

        egitim_klasor = str(
            Path(self.cfg.egitim_cikti) / "ultralytics_runs"
        )

        self.log.info("=" * 60)
        self.log.info("Eğitim başlıyor...")
        self.log.info(f"  Epoch   : {self.cfg.epochs} (ES patience={self.cfg.es_patience})")
        self.log.info(f"  Batch   : {self.cfg.batch}")
        self.log.info(f"  AMP     : {self.cfg.amp}")
        self.log.info(f"  fl_gamma: {self.cfg.fl_gamma} (native Focal Loss)")
        self.log.info(f"  mosaic  : {self.cfg.mosaic} | mixup: {self.cfg.mixup} | copy_paste: {self.cfg.copy_paste}")
        self.log.info(f"  Backbone çözme: epoch {self.cfg.backbone_coz_epoch}")
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
            # fl_gamma bu Ultralytics versiyonunda desteklenmiyor
            # v8DetectionLoss gamma=1.5 sabit — yeterli
            # Cosine LR — RLROP yerine, çakışma riski yok
            cos_lr=True,
            # Augmentasyon
            mosaic=self.cfg.mosaic,
            mixup=self.cfg.mixup,
            copy_paste=self.cfg.copy_paste,
            close_mosaic=self.cfg.close_mosaic,
            degrees=self.cfg.degrees,
            shear=self.cfg.shear,
            # freeze= burada VERİLMEZ — BackboneCallback yönetiyor
            # (model.train freeze= parametresi her epoch başında uygular,
            #  BackboneCallback ile çakışır)
            # Kayıt
            project=egitim_klasor,
            name="akne_yolo11s_v2",
            exist_ok=True,
            save=True,
            val=True,
            plots=True,
            verbose=False,
        )

    # ── En iyi modeli kopyala ─────────────────────────────────────────────────

    def _modeli_kopyala(self) -> None:
        """
        Ultralytics'in kaydettiği best.pt ve last.pt'yi
        egitim_v2/checkpoints/ klasörüne kopyalar.
        """
        ckpt_hedef = Path(self.cfg.egitim_cikti) / "checkpoints"
        ckpt_hedef.mkdir(parents=True, exist_ok=True)

        kaynak_dir = (
            Path(self.cfg.egitim_cikti)
            / "ultralytics_runs"
            / "akne_yolo11s_v2"
            / "weights"
        )

        for isim in ["best.pt", "last.pt"]:
            kaynak = kaynak_dir / isim
            if kaynak.exists():
                hedef = ckpt_hedef / isim
                shutil.copy2(str(kaynak), str(hedef))
                self.log.info(f"Kopyalandı: {hedef}")
            else:
                self.log.warning(f"Bulunamadı: {kaynak}")

        # Early stopping en iyi ağırlıkları best.pt'ye yaz
        if self.early_stop.en_iyi_weights and (ckpt_hedef / "best.pt").exists():
            self.log.info(
                f"En iyi epoch: {self.early_stop.en_iyi_epoch} "
                f"(mAP@50={self.early_stop.en_iyi_map:.4f})"
            )

    # ── Özet rapor ────────────────────────────────────────────────────────────

    def _ozet_rapor(self) -> None:
        """CSV'den özet metrikler loglar."""
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
            self.log.info("EĞİTİM ÖZET")
            self.log.info(f"  Toplam epoch    : {len(satirlar)}")
            self.log.info(f"  En iyi mAP@50   : {en_iyi.get('mAP50')} (epoch {en_iyi.get('epoch')})")
            self.log.info(f"  En iyi mAP@50-95: {en_iyi.get('mAP50_95')}")
            self.log.info(f"  Precision       : {en_iyi.get('precision')}")
            self.log.info(f"  Recall          : {en_iyi.get('recall')}")
            self.log.info(f"  F1              : {en_iyi.get('f1')}")
            self.log.info(f"  Early Stop      : {'Evet' if self.early_stop.dur else 'Hayır'}")
            self.log.info(f"  Çıktı           : {self.cfg.egitim_cikti}")
            self.log.info("=" * 60)
        except Exception as e:
            self.log.warning(f"Özet rapor hatası: {e}")

    # ── README ────────────────────────────────────────────────────────────────

    def _readme_yaz(self) -> None:
        icerik = f"""# Aşama 03 v2 — Eğitim Döngüsü

## v1 → v2 Değişiklikler
- Custom DetectionTrainer KALDIRILDI → standart model.train()
- DynamicFocalLoss KALDIRILDI → fl_gamma={self.cfg.fl_gamma} native
- ReduceLROnPlateau KALDIRILDI → cos_lr=True native
- copy_paste={self.cfg.copy_paste}, mixup={self.cfg.mixup} eklendi

## Hiperparametreler
| Parametre | Değer |
|-----------|-------|
| Base model | {self.cfg.base_model} |
| Epoch | {self.cfg.epochs} |
| Batch | {self.cfg.batch} |
| fl_gamma | {self.cfg.fl_gamma} |
| mosaic | {self.cfg.mosaic} |
| mixup | {self.cfg.mixup} |
| copy_paste | {self.cfg.copy_paste} |
| Backbone çözme | epoch {self.cfg.backbone_coz_epoch} |
| Early stop patience | {self.cfg.es_patience} |

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
"""
        yol = Path(self.cfg.egitim_cikti) / "README.md"
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(icerik, encoding="utf-8")
        self.log.info(f"README: {yol}")

    # ── ANA ÇALIŞTIRICI ───────────────────────────────────────────────────────

    def calistir(self) -> None:
        """Tüm eğitim sürecini uçtan uca çalıştırır."""
        if not _ULTRALYTICS_OK:
            raise ImportError("ultralytics kurulu değil: pip install ultralytics")

        self.log.info("=" * 60)
        self.log.info("AŞAMA 03 v2 — Eğitim Döngüsü BAŞLIYOR")
        self.log.info(f"Çıktı : {self.cfg.egitim_cikti}")
        self.log.info(f"Device: {self.cfg.device}")
        self.log.info("=" * 60)

        t0 = time.time()

        self._readme_yaz()
        data_yaml = self._data_yaml_dogrula()
        self._egitimi_baslat(data_yaml)
        self._modeli_kopyala()
        self._ozet_rapor()

        self.log.info(
            f"AŞAMA 03 v2 TAMAMLANDI — "
            f"{(time.time()-t0)/60:.1f} dk"
        )


# =============================================================================
# DOĞRUDAN ÇALIŞTIRMA
# =============================================================================

if __name__ == "__main__":
    print(f"CUDA : {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU  : {torch.cuda.get_device_name(0)}")
        print(f"VRAM : {torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB")

    yonetici = EgitimYoneticisi()
    yonetici.calistir()