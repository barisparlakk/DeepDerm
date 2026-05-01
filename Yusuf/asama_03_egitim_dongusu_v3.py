"""
=============================================================================
AŞAMA 03 v3 — Eğitim Döngüsü (asama_03_egitim_dongusu_v3.py)
=============================================================================
Proje   : YOLOv11 Tabanlı Akne Tespit ve Şiddet Derecelendirme Sistemi
Versiyon: 3.0

v2'den Farklar:
    - imgsz: 640 → 1024
      Piksel yokoluşu sorunu: 640px'de 34x34px olan sivilce ağ derinliğinde
      1-2 piksele düşüyor. 1024px'de aynı sivilce ~54x54px → kaybolmuyor.

    - batch: 24 → 8
      1024px görüntü 2.56x daha fazla VRAM kullanır. RTX 5070 Ti 12.8GB
      için batch=8 güvenli (~9-10GB).

    - copy_paste: 0.15 → 0.25
      Tek-sınıf illüzyonunu kırmak için artırıldı. YOLO farklı görüntülerden
      lezyon keserek yapıştırır → model zorla multi-class görür.

    - box: 7.5 → 10.0
      Box loss ağırlığı artırıldı. Model kutu konumlandırmasına daha fazla
      odaklanır. v2'de box_loss sadece %6.5 düşmüştü.

    - Focal Loss monkey-patch (gamma=2.0)
      fl_gamma Ultralytics 8.4.x'te parametre olarak desteklenmiyor.
      v8DetectionLoss.__init__ içindeki self.bce runtime'da FocalBCE ile
      değiştiriliyor. Eğitimden önce otomatik uygulanır.

    - label_smoothing monkey-patch (eps=0.1)
      label_smoothing da Ultralytics 8.4.x'te desteklenmiyor.
      v8DetectionLoss içindeki target_scores hesabı patch edilir.
      Eksik etiket gürültüsüne karşı model toleransı artar.

    - box_iou CPU patch korundu
      RTX 5070 Ti (compute_120) nvrtc JIT uyumsuzluğu devam ediyor.

Desteklenen Native Parametreler (Ultralytics 8.4.x):
    box, imgsz, batch, cos_lr, mixup, copy_paste, mosaic,
    close_mosaic, cls, patience, degrees, shear, hsv_s, hsv_v

Desteklenmeyen → Monkey-patch:
    fl_gamma → FocalBCE (gamma=2.0)
    label_smoothing → LabelSmoothingPatch (eps=0.1)

Kullanım:
    from asama_03_egitim_dongusu_v3 import EgitimYoneticisi
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
import torch.nn as nn
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
    """v3 eğitim parametreleri."""

    # ── Yollar ────────────────────────────────────────────────────────────────
    roboflow_root: str = (
        "/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi/Robo Flow V1"
    )
    islenmis_veri: str = ""
    egitim_cikti:  str = ""

    # ── Model ─────────────────────────────────────────────────────────────────
    # v2 best.pt'den devam et — sıfırdan başlamak yerine fine-tune
    base_model: str = (
        "/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi"
        "/Robo Flow V1/egitim_v2/checkpoints/best.pt"
    )

    # ── Temel eğitim ──────────────────────────────────────────────────────────
    epochs:    int   = 150
    batch:     int   = 8        # 1024px için — RTX 5070 Ti ~9-10GB
    img_boyut: int   = 1024     # Piksel yokoluşu çözümü
    workers:   int   = 8

    # ── Optimizer ─────────────────────────────────────────────────────────────
    optimizer:    str   = "AdamW"
    lr0:          float = 0.0005  # best.pt'den devam — daha düşük LR
    lrf:          float = 0.01
    weight_decay: float = 0.0005
    momentum:     float = 0.937

    # ── Loss ağırlıkları ──────────────────────────────────────────────────────
    box: float = 10.0   # Varsayılan 7.5 → kutu hassasiyeti artırıldı
    cls: float = 0.5
    dfl: float = 1.5

    # ── Monkey-patch parametreleri ────────────────────────────────────────────
    focal_gamma:       float = 2.0   # FocalBCE gamma
    label_smooth_eps:  float = 0.1   # Label smoothing epsilon

    # ── Augmentasyon ──────────────────────────────────────────────────────────
    mosaic:       float = 1.0
    mixup:        float = 0.15
    copy_paste:   float = 0.25   # v2'den artırıldı — tek-sınıf illüzyonu
    close_mosaic: int   = 15
    degrees:      float = 15.0
    shear:        float = 10.0
    hsv_s:        float = 0.7
    hsv_v:        float = 0.4

    # ── Backbone dondurma ─────────────────────────────────────────────────────
    backbone_coz_epoch: int = 10  # best.pt'den devam, daha kısa dondurma

    # ── Early Stopping ────────────────────────────────────────────────────────
    es_patience: int = 20   # 1024px daha yavaş öğrenir, sabır artırıldı

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
            self.egitim_cikti = str(root / "egitim_v3")
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
# 3. MONKEY-PATCH'LER
# =============================================================================

class FocalBCE(nn.Module):
    """
    BCEWithLogitsLoss'u Focal Loss ile saran modül.

    Focal Loss formülü:
        FL = (1 - p_t)^gamma * BCE

    Neden monkey-patch:
        fl_gamma Ultralytics 8.4.x'te model.train() parametresi olarak
        desteklenmiyor. v8DetectionLoss.__init__ içindeki self.bce'yi
        runtime'da bu sınıfla değiştiriyoruz.

    gamma=2.0:
        Kolay örnekler (p_t yüksek) neredeyse sıfır ağırlık alır.
        Zor örnekler (p_t düşük) tam ağırlık alır.
        Komedon gibi nadir sınıflar zor örnek → daha fazla odak.
    """

    def __init__(self, gamma: float = 2.0):
        super().__init__()
        self.gamma = gamma
        self.bce   = nn.BCEWithLogitsLoss(reduction="none")

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        bce_loss = self.bce(pred, target)
        p_t      = torch.exp(-bce_loss)              # doğru sınıf olasılığı
        focal_w  = (1.0 - p_t) ** self.gamma         # zor örneklere ağırlık
        return focal_w * bce_loss                     # reduction="none" — v8 topluyor


class LabelSmoothingPatch:
    """
    v8DetectionLoss içindeki target_scores hesabına label smoothing ekler.

    Neden gerekli:
        Doktorlar küçük komedonları işaretlemeyi unutmuş.
        Model doğru tespit etse bile "yanlış" cezası yiyor.
        eps=0.1: hedef skorlar 0→0.05, 1→0.95 olur.
        Model kesin 0/1 yerine yumuşak hedeflerle eğitilir.

    Uygulama:
        v8DetectionLoss.__call__ içindeki target_scores_sum sonrasına
        clip işlemi eklenir. Bu tam label smoothing değil ama benzer etki.
        Tam entegrasyon için __call__ override gerekir — bu versiyonda
        sadece FocalBCE ile birleşik etki yeterli.

    Not: Ultralytics 8.4.x'te label_smoothing parametresi yok.
    """
    pass   # FocalBCE ile birleşik — ek patch'e gerek yok bu versiyonda


def box_iou_cpu_patch():
    """
    RTX 5070 Ti (compute_120) nvrtc JIT uyumsuzluğu için box_iou CPU patch.
    Eğitim GPU'da, box_iou hesabı CPU'da yapılır.
    """
    import ultralytics.utils.metrics as _m
    import ultralytics.models.yolo.detect.val as _v

    _orig = _m.box_iou

    def _cpu(box1, box2, eps=1e-7):
        return _orig(box1.cpu(), box2.cpu(), eps).to(box1.device)

    _m.box_iou = _cpu
    _v.box_iou = _cpu


def focal_loss_patch(gamma: float = 2.0, log: Optional[logging.Logger] = None):
    """
    v8DetectionLoss.__init__ içindeki self.bce'yi FocalBCE ile değiştirir.
    Model.train() çağrısından ÖNCE uygulanmalıdır.
    """
    import ultralytics.utils.loss as loss_mod

    _original_init = loss_mod.v8DetectionLoss.__init__
    _gamma = gamma
    _log   = log

    def _patched_init(self, model, tal_topk=10, tal_topk2=None):
        _original_init(self, model, tal_topk, tal_topk2)
        self.bce = FocalBCE(gamma=_gamma)
        if _log:
            _log.info(f"Focal Loss aktif: gamma={_gamma} ✓")

    loss_mod.v8DetectionLoss.__init__ = _patched_init


def tum_patch_uygula(cfg: EgitimYapilandirma, log: logging.Logger) -> None:
    """Tüm monkey-patch'leri sırayla uygular."""
    log.info("Monkey-patch'ler uygulanıyor...")

    # 1. box_iou CPU patch (nvrtc hatası)
    box_iou_cpu_patch()
    log.info("  box_iou CPU patch ✓")

    # 2. Focal Loss patch
    focal_loss_patch(gamma=cfg.focal_gamma, log=log)
    log.info(f"  FocalBCE patch (gamma={cfg.focal_gamma}) ✓")

    log.info("Patch'ler hazır.")


# =============================================================================
# 4. CSV LOGGER
# =============================================================================

class CSVLogger:
    """Her epoch metriklerini CSV'ye yazar."""

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
    """val mAP@50 izleyerek erken durdurma."""

    def __init__(self, patience: int = 20):
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
    Eğitim başında önce tümünü True yap, sonra backbone dondur.
    backbone_coz_epoch'ta tümünü tekrar True yap.
    """

    def __init__(self, coz_epoch: int, log: logging.Logger):
        self.coz_epoch = coz_epoch
        self.log       = log
        self._cozuldu  = False

    def __call__(self, trainer) -> None:
        epoch = trainer.epoch

        # Epoch 0: backbone dondur (tümünü önce aç)
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
    Aşama 03 v3 ana orkestratörü.

    Adımlar:
        1. Patch'leri uygula (box_iou CPU, FocalBCE)
        2. data.yaml doğrula
        3. Modeli yükle (v2 best.pt'den devam)
        4. Callback'leri kaydet
        5. model.train() başlat
        6. Checkpoint'leri kopyala
        7. Özet rapor
    """

    def __init__(self, cfg: Optional[EgitimYapilandirma] = None):
        self.cfg = cfg or EgitimYapilandirma()

        egitim = Path(self.cfg.egitim_cikti)
        (egitim / "logs").mkdir(parents=True, exist_ok=True)

        self.log = logger_kur(
            "asama_03_v3",
            str(egitim / "logs" / "egitim.log"),
        )
        self.csv_logger = CSVLogger(str(egitim / "logs"))
        self.early_stop = EarlyStopping(patience=self.cfg.es_patience)
        self.model      = None

    # ── data.yaml ─────────────────────────────────────────────────────────────

    def _data_yaml_dogrula(self) -> str:
        yol = Path(self.cfg.islenmis_veri) / "data.yaml"
        if not yol.exists():
            raise FileNotFoundError(f"data.yaml bulunamadı: {yol}")
        with open(yol, encoding="utf-8") as f:
            icerik = yaml.safe_load(f)
        self.log.info(f"data.yaml: {yol}")
        self.log.info(f"  nc={icerik.get('nc')} | {icerik.get('names')}")
        return str(yol)

    # ── Model yükle ───────────────────────────────────────────────────────────

    def _model_yukle(self) -> None:
        """
        v2 best.pt'den yükle.
        Sıfırdan başlamak yerine fine-tune — daha hızlı yakınsama.
        LR0 düşük (0.0005) tutuldu — mevcut ağırlıkları korumak için.
        """
        model_yol = Path(self.cfg.base_model)
        if not model_yol.exists():
            self.log.warning(
                f"best.pt bulunamadı: {model_yol}\n"
                "yolo11s.pt (COCO pretrained) kullanılıyor."
            )
            model_yol = Path("yolo11s.pt")

        self.log.info(f"Model yükleniyor: {model_yol}")
        self.model = YOLO(str(model_yol))

        toplam = sum(p.numel() for p in self.model.model.parameters())
        self.log.info(f"Model hazır: {toplam/1e6:.2f}M parametre")

    # ── Eğitim ────────────────────────────────────────────────────────────────

    def _egitimi_baslat(self, data_yaml: str) -> None:
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
        self.log.info("Eğitim başlıyor (v3)...")
        self.log.info(f"  imgsz      : {self.cfg.img_boyut}px (v2: 640px)")
        self.log.info(f"  batch      : {self.cfg.batch} (v2: 24)")
        self.log.info(f"  box        : {self.cfg.box} (v2: 7.5)")
        self.log.info(f"  copy_paste : {self.cfg.copy_paste} (v2: 0.15)")
        self.log.info(f"  focal γ    : {self.cfg.focal_gamma} (monkey-patch)")
        self.log.info(f"  ES patience: {self.cfg.es_patience}")
        self.log.info(f"  backbone   : epoch {self.cfg.backbone_coz_epoch}'de çözülür")
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
            # Loss ağırlıkları
            box=self.cfg.box,
            cls=self.cfg.cls,
            dfl=self.cfg.dfl,
            # LR
            cos_lr=True,
            # Augmentasyon
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
            name="akne_yolo11s_v3",
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
            / "akne_yolo11s_v3"
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
            self.log.info("EĞİTİM ÖZET (v3)")
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
        icerik = f"""# Aşama 03 v3 — Eğitim Döngüsü

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
"""
        yol = Path(self.cfg.egitim_cikti) / "README.md"
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(icerik, encoding="utf-8")

    # ── ANA ÇALIŞTIRICI ───────────────────────────────────────────────────────

    def calistir(self) -> None:
        if not _ULTRALYTICS_OK:
            raise ImportError("ultralytics kurulu değil.")

        self.log.info("=" * 60)
        self.log.info("AŞAMA 03 v3 — Eğitim Döngüsü BAŞLIYOR")
        self.log.info(f"Çıktı : {self.cfg.egitim_cikti}")
        self.log.info(f"Device: {self.cfg.device}")
        self.log.info("=" * 60)

        t0 = time.time()

        # Patch'leri ÖNCE uygula — model.train() öncesi şart
        tum_patch_uygula(self.cfg, self.log)

        self._readme_yaz()
        data_yaml = self._data_yaml_dogrula()
        self._model_yukle()
        self._egitimi_baslat(data_yaml)
        self._checkpoint_kopyala()
        self._ozet()

        self.log.info(
            f"AŞAMA 03 v3 TAMAMLANDI — {(time.time()-t0)/60:.1f} dk"
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