"""
=============================================================================
AŞAMA 02 v2 — Model İnşası (asama_02_model_insasi_v2.py)
=============================================================================
Proje   : YOLOv11 Tabanlı Akne Tespit ve Şiddet Derecelendirme Sistemi
Versiyon: 2.1 (bugfix)

v2.0'dan Farklar (Bugfix):
    - parametre_sayisi() düzeltildi:
        Eski: self.model.parameters() → requires_grad filtresi yok → 0 rapor
        Yeni: requires_grad=True filtresi → doğru sayı
    - BackboneDondurma.coz() düzeltildi:
        Eski: self.model üzerinde dönüyor (Sequential) → scope doğru ama
              parametre_sayisi ile tutarsız
        Yeni: tek yerden parametre yönetimi
    - _dogrula() düzeltildi:
        Eski: self.model.model.eval() / self.model.model.train()
        Yeni: self.model.model.eval() tutarlı, try/finally korundu
    - Backbone dondurma Aşama 03 ile çakışma riski belgelendi:
        YOLO native freeze= parametresi de var.
        Çözüm: Aşama 03'te freeze= VERİLMEZ, backbone_helper kullanılır.

Bu Aşamanın Görevi:
    1. YOLOv11s COCO pretrained yükle
    2. Backbone dondur (layer 0-9, ~4.45M param)
    3. Eğitilebilir parametre sayısını doğru raporla (~5.01M, %52.9)
    4. Forward pass doğrula
    5. Konfigürasyon kaydet (YAML + README)
    6. Aşama 03'e paket döndür

Katman Yapısı (YOLOv11s, 24 katman):
    Layer  0-9  : Backbone — Conv, C3k2, SPPF, C2PSA (~4.45M param)
    Layer 10-22 : Neck     — FPN, Upsample, Concat, C3k2
    Layer 23    : Head     — Detect

Focal Loss Notu:
    fl_gamma=2.0 → Aşama 03 model.train() parametresiyle verilir.
    Bu dosyada Focal Loss kodu YOK — native YOLO kullanılır.

Kullanım:
    from asama_02_model_insasi_v2 import ModelInsaci
    insaci = ModelInsaci()
    model  = insaci.calistir()
    paket  = insaci.asama03_icin_paketle()
=============================================================================
"""

# =============================================================================
# IMPORTS
# =============================================================================

import shutil
import logging
import warnings
from pathlib import Path
from dataclasses import dataclass, field
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
# YAPILANDIRMA
# =============================================================================

@dataclass
class ModelYapilandirma:
    """Aşama 02 v2 parametreleri."""

    # ── Yollar ────────────────────────────────────────────────────────────────
    roboflow_root: str = (
        "/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi/Robo Flow V1"
    )
    islenmis_veri: str = ""   # Boş → roboflow_root/islenmiş_veri
    model_cikti:   str = ""   # Boş → roboflow_root/model_v2

    # ── Temel model ───────────────────────────────────────────────────────────
    base_model: str = "yolo11s.pt"   # COCO pretrained Small
    img_boyut:  int = 640

    # ── Sınıf bilgisi ─────────────────────────────────────────────────────────
    sinif_isimleri: dict = field(default_factory=lambda: {
        0: "comedone", 1: "nodule", 2: "papule", 3: "pustule"
    })

    # ── Transfer Learning ─────────────────────────────────────────────────────
    backbone_dondur: bool = True
    # Layer 0-9 backbone (Conv, C3k2, SPPF, C2PSA) = ~4.45M param
    # Layer 10+ neck+head = ~5.01M param (eğitilebilir başlangıçta)
    dondur_katman_n: int  = 10

    # ── CUDA ──────────────────────────────────────────────────────────────────
    device: str = ""   # Boş → otomatik

    def __post_init__(self):
        root = Path(self.roboflow_root)
        if not self.islenmis_veri:
            self.islenmis_veri = str(root / "islenmiş_veri")
        if not self.model_cikti:
            self.model_cikti = str(root / "model_v2")
        if not self.device:
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"


# =============================================================================
# YARDIMCI
# =============================================================================

def logger_kur(isim: str = "asama_02_v2") -> logging.Logger:
    log = logging.getLogger(isim)
    log.setLevel(logging.INFO)
    if log.handlers:
        log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    return log


# =============================================================================
# BACKBONE DONDURMA
# =============================================================================

class BackboneDondurma:
    """
    Transfer learning için backbone katmanlarını dondurur/çözer.

    Neden donduruyoruz:
        COCO pretrained backbone güçlü genel feature'lar öğrenmiştir.
        Epoch 0-14: sadece neck+head eğitilir (backbone korunur).
        Epoch 15+:  backbone açılır, tüm ağ ince ayar yapar.

    Önemli — Aşama 03 çakışma riski:
        YOLO model.train() içinde freeze= parametresi de var.
        Aşama 03'te freeze= VERİLMEMELİ — bu sınıf yönetiyor.
        İkisi aynı anda kullanılırsa parametreler iki kez dondurulur.

    Katman yapısı (YOLOv11s, 24 katman):
        Layer  0-9  : Backbone → dondurulur (4.45M param)
        Layer 10-23 : Neck+Head → eğitilebilir (5.01M param)
    """

    def __init__(
        self,
        sequential: torch.nn.Sequential,  # model.model.model (Sequential)
        katman_n: int = 10,
        log: Optional[logging.Logger] = None,
    ):
        # sequential: model.model.model → 24 katmanlı Sequential
        self.sequential  = sequential
        self.n           = katman_n
        self.log         = log or logging.getLogger("backbone")
        self._donduruldu = False

    # ── Dondur ────────────────────────────────────────────────────────────────

    def dondur(self) -> None:
        """Layer 0'dan n-1'e kadar tüm parametreleri dondurur.

        Kritik: YOLO yüklenince tüm parametreler requires_grad=False gelir.
        Önce tümünü True yap, sonra backbone'u False yap.
        """
        if self._donduruldu:
            self.log.warning("Backbone zaten dondurulmuş, tekrar atlandı.")
            return

        # YOLO varsayılan: tüm parametreler requires_grad=False
        # Önce tümünü eğitilebilir yap
        for p in self.sequential.parameters():
            p.requires_grad = True

        donduruldu_katman = 0
        donduruldu_param  = 0

        for i, katman in enumerate(self.sequential):
            if i < self.n:
                for p in katman.parameters():
                    p.requires_grad = False
                    donduruldu_param += p.numel()
                donduruldu_katman += 1

        self._donduruldu = True
        self.log.info(
            f"Backbone donduruldu: {donduruldu_katman} katman "
            f"(0-{self.n-1}), {donduruldu_param/1e6:.2f}M param donduruldu"
        )
        self._parametre_raporu()

    # ── Çöz ───────────────────────────────────────────────────────────────────

    def coz(self) -> None:
        """Tüm katmanları eğitilebilir yapar (backbone dahil)."""
        for katman in self.sequential:
            for p in katman.parameters():
                p.requires_grad = True

        self._donduruldu = False
        self.log.info(
            f"Backbone çözüldü — tüm {len(self.sequential)} katman eğitilebilir"
        )
        self._parametre_raporu()

    # ── Rapor ─────────────────────────────────────────────────────────────────

    def _parametre_raporu(self) -> None:
        """requires_grad durumuna göre parametre sayısını loglar."""
        egitilir, toplam = self.parametre_sayisi()
        self.log.info(
            f"Parametre: {egitilir/1e6:.2f}M eğitilebilir / "
            f"{toplam/1e6:.2f}M toplam "
            f"(%{100*egitilir/toplam:.1f})"
        )

    def parametre_sayisi(self) -> tuple[int, int]:
        """
        (eğitilebilir_param, toplam_param) döndürür.

        BUG FIX v2.0:
            Eski: self.model.parameters() → requires_grad filtresi YOK
                  Sonuç: egitilir=0 (yanlış)
            Yeni: requires_grad=True filtresi var → doğru sayım
        """
        toplam   = sum(p.numel() for p in self.sequential.parameters())
        egitilir = sum(
            p.numel()
            for p in self.sequential.parameters()
            if p.requires_grad   # ← DÜZELTME: filtre eklendi
        )
        return egitilir, toplam


# =============================================================================
# MODEL İNŞACI
# =============================================================================

class ModelInsaci:
    """
    Aşama 02 v2 ana sınıfı.

    Adımlar:
        1. YOLOv11s COCO pretrained yükle
        2. Backbone dondur (layer 0-9)
        3. Eğitilebilir param doğrula (~5.01M, %52.9)
        4. Forward pass doğrula
        5. Konfigürasyon kaydet
        6. Aşama 03 paketi hazırla
    """

    def __init__(self, cfg: Optional[ModelYapilandirma] = None):
        self.cfg             = cfg or ModelYapilandirma()
        self.log             = logger_kur("asama_02_v2")
        self.model           = None
        self.backbone_helper = None

        # Çıktı klasörleri
        Path(self.cfg.model_cikti).mkdir(parents=True, exist_ok=True)
        Path(self.cfg.model_cikti, "checkpoints").mkdir(parents=True, exist_ok=True)

    # ── 1. Model yükleme ──────────────────────────────────────────────────────

    def _model_yukle(self) -> None:
        """
        YOLOv11s COCO pretrained yükler.

        Neden yolo11s.pt:
            - C2PSA (Spatial Attention) layer 10'da built-in
            - 9.46M param, RTX 5070 Ti batch=24 ile rahat
            - Nano'dan %15-20 daha iyi mAP
        """
        if not _ULTRALYTICS_OK:
            raise ImportError("ultralytics kurulu değil: pip install ultralytics")

        self.log.info(f"YOLOv11s yükleniyor: {self.cfg.base_model}")
        self.log.info(f"Device: {self.cfg.device}")

        self.model = YOLO(self.cfg.base_model)
        self.model.to(self.cfg.device)

        toplam = sum(p.numel() for p in self.model.model.parameters())
        self.log.info(f"Model yüklendi: {toplam/1e6:.2f}M parametre")
        self.log.info("C2PSA (Spatial Attention) built-in — Layer 10 ✓")

    # ── 2. Backbone dondurma ──────────────────────────────────────────────────

    def _backbone_dondur(self) -> None:
        """
        BackboneDondurma'ya model.model.model (Sequential) geçer.

        BUG FIX v2.0:
            Eski: self.model.model → DetectionModel geçiyordu
            Yeni: self.model.model.model → Sequential (24 katman) geçiyor
                  BackboneDondurma enumerate(self.sequential) yapabiliyor
        """
        # model         → YOLO wrapper
        # model.model   → DetectionModel
        # model.model.model → Sequential (24 katman) ← bunu geçiyoruz
        sequential = self.model.model.model

        self.backbone_helper = BackboneDondurma(
            sequential=sequential,
            katman_n=self.cfg.dondur_katman_n,
            log=self.log,
        )

        if self.cfg.backbone_dondur:
            self.backbone_helper.dondur()
        else:
            self.log.info("Backbone dondurma devre dışı — tüm katmanlar eğitilebilir")

    # ── 3. Forward pass doğrulama ─────────────────────────────────────────────

    def _dogrula(self) -> None:
        """
        Dummy tensor ile forward pass — model bütünlüğü testi.
        Standart YOLO mimarisi, custom patch yok → serializasyon sorunu yok.
        """
        self.log.info("Forward pass doğrulaması...")

        # eval moduna al (batch norm, dropout etkisiz)
        self.model.model.eval()

        try:
            with torch.no_grad():
                dummy = torch.zeros(
                    1, 3, self.cfg.img_boyut, self.cfg.img_boyut,
                    device=self.cfg.device,
                )
                cikti = self.model.model(dummy)

            # Çıktı shape'leri logla
            if isinstance(cikti, (list, tuple)):
                for i, c in enumerate(cikti):
                    if hasattr(c, "shape"):
                        self.log.info(f"  Çıktı [{i}]: {tuple(c.shape)}")
                    elif isinstance(c, (list, tuple)):
                        for j, cc in enumerate(c):
                            if hasattr(cc, "shape"):
                                self.log.info(f"  Çıktı [{i}][{j}]: {tuple(cc.shape)}")
            else:
                self.log.info(f"  Çıktı: {tuple(cikti.shape)}")

            self.log.info("Forward pass başarılı ✓")

        except Exception as e:
            self.log.error(f"Forward pass başarısız: {e}")
            raise

        finally:
            # Her durumda train moduna geri al
            self.model.model.train()

    # ── 4. Kaydetme ───────────────────────────────────────────────────────────

    def _kaydet(self) -> None:
        """YAML konfigürasyonu ve README kaydeder. Kaynak kodu kopyalar."""

        # Kaynak kodu kopyala
        try:
            kaynak = Path(__file__)
            if kaynak.exists():
                hedef = Path(self.cfg.model_cikti) / kaynak.name
                shutil.copy2(str(kaynak), str(hedef))
                self.log.info(f"Kaynak kod kopyalandı: {hedef}")
        except NameError:
            self.log.info("Kaynak kod kopyası atlandı (Jupyter ortamı)")

        # YAML — Aşama 03 referansı
        egitilir, toplam = self.backbone_helper.parametre_sayisi()
        yaml_icerik = {
            "model":     "YOLOv11s — C2PSA built-in + Native Focal Loss",
            "versiyon":  "2.1",
            "base_model": self.cfg.base_model,
            "img_size":  self.cfg.img_boyut,
            "nc":        len(self.cfg.sinif_isimleri),
            "names":     self.cfg.sinif_isimleri,
            "attention": "C2PSA built-in (Layer 10)",
            "focal_loss": {
                "not":    "fl_gamma=2.0 Aşama 03 train() ile verilir",
                "gamma":  2.0,
                "yontem": "YOLO native v8DetectionLoss",
            },
            "transfer_learning": {
                "pretrained":      self.cfg.base_model,
                "freeze_layers":   self.cfg.dondur_katman_n,
                "frozen_params_M": round(
                    (toplam - egitilir) / 1e6, 2
                ),
                "trainable_params_M": round(egitilir / 1e6, 2),
                "trainable_pct": round(100 * egitilir / toplam, 1),
                "unfreeze_epoch": "Aşama 03'te backbone_coz_epoch ile",
                "asama03_uyari":  (
                    "freeze= parametresi VERİLMEMELİ — "
                    "backbone_helper.coz() yönetiyor"
                ),
            },
        }

        yaml_yolu = Path(self.cfg.model_cikti) / "yolo11s_akne_v2.yaml"
        with open(yaml_yolu, "w", encoding="utf-8") as f:
            yaml.dump(
                yaml_icerik, f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
        self.log.info(f"Model YAML kaydedildi: {yaml_yolu}")

        # README
        readme = f"""# Aşama 02 v2.1 — Model İnşası

## Değişiklikler (v2.0 → v2.1 bugfix)
- `parametre_sayisi()` düzeltildi: `requires_grad=True` filtresi eklendi
- `BackboneDondurma` artık doğru scope'ta çalışıyor (Sequential)
- `_dogrula()` eval/train geçişi tutarlı hale getirildi

## Model
| Bileşen | Detay |
|---------|-------|
| Base | {self.cfg.base_model} (COCO pretrained) |
| Attention | C2PSA built-in (Layer 10) |
| Toplam param | {toplam/1e6:.2f}M |
| Eğitilebilir | {egitilir/1e6:.2f}M (%{100*egitilir/toplam:.1f}) |
| Dondurulmuş | {(toplam-egitilir)/1e6:.2f}M (Layer 0-{self.cfg.dondur_katman_n-1}) |

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
"""
        readme_yolu = Path(self.cfg.model_cikti) / "README.md"
        with open(readme_yolu, "w", encoding="utf-8") as f:
            f.write(readme)
        self.log.info(f"README kaydedildi: {readme_yolu}")

    # ── Ana çalıştırıcı ───────────────────────────────────────────────────────

    def calistir(self) -> "YOLO":
        """
        Tüm model inşa sürecini çalıştırır.
        Returns: Backbone dondurulmuş, eğitime hazır YOLO nesnesi.
        """
        self.log.info("=" * 60)
        self.log.info("AŞAMA 02 v2.1 — Model İnşası BAŞLIYOR")
        self.log.info(f"Base model : {self.cfg.base_model}")
        self.log.info(f"Device     : {self.cfg.device}")
        self.log.info(f"Çıktı      : {self.cfg.model_cikti}")
        self.log.info("=" * 60)

        self._model_yukle()      # 1. COCO pretrained
        self._backbone_dondur()  # 2. Transfer learning
        self._dogrula()          # 3. Forward pass
        self._kaydet()           # 4. Konfigürasyon

        self.log.info("=" * 60)
        self.log.info("AŞAMA 02 v2.1 TAMAMLANDI")
        self.log.info("Sonraki: asama_03_egitim_dongusu_v2.py")
        self.log.info("=" * 60)

        return self.model

    def asama03_icin_paketle(self) -> dict:
        """
        Aşama 03'ün ihtiyaç duyduğu nesneleri döndürür.

        Returns:
            model           : ultralytics.YOLO (backbone dondurulmuş)
            backbone_helper : BackboneDondurma (coz() çağrısı için)
            cfg             : ModelYapilandirma
            data_yaml       : str — islenmiş_veri/data.yaml yolu
        """
        if self.model is None:
            raise RuntimeError("Önce calistir() çağrılmalı.")

        return {
            "model":           self.model,
            "backbone_helper": self.backbone_helper,
            "cfg":             self.cfg,
            "data_yaml":       str(
                Path(self.cfg.islenmis_veri) / "data.yaml"
            ),
        }


# =============================================================================
# DOĞRUDAN ÇALIŞTIRMA
# =============================================================================

if __name__ == "__main__":
    import torch
    print(f"CUDA : {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU  : {torch.cuda.get_device_name(0)}")
        print(f"VRAM : {torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB")

    insaci = ModelInsaci()
    model  = insaci.calistir()
    paket  = insaci.asama03_icin_paketle()

    print(f"\nAşama 03 paketi hazır:")
    print(f"  data.yaml : {paket['data_yaml']}")
    print(f"  model     : {type(paket['model']).__name__}")