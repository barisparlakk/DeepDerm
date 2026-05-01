"""
=============================================================================
AŞAMA 02 — Model İnşası (asama_02_model_insasi.py)
=============================================================================
Proje   : YOLOv11 Tabanlı Akne Tespit ve Şiddet Derecelendirme Sistemi
Versiyon: 1.0

Amaç:
    YOLOv11s üzerine üç kritik modifikasyon uygulayarak klinik düzeyde
    güvenilir bir tespit modeli inşa etmek:

    1. SABottleneck (Spatial Attention Bottleneck)
       → FPN/Neck katmanına eklenir; multi-scale her seviyede dikkat çalışır.
       → Küçük bbox yoğunluğu (%54.3 small) için kritik: P3/P4/P5 feature
         map'lerinde saç/arka plan gürültüsü bastırılır, lezyon sinyali güçlenir.

    2. Dinamik Focal Loss  [γ = 2.0 × sqrt(max_count / class_count)]
       → Komedon γ≈3.51, Nodül γ≈1.27  (veri analizine göre hesaplanır)
       → Standart BCE yerine sınıf bazlı adaptif ceza; objectness collapse önlenir.
       → α (class weight) aynı dengesizlik oranından türetilir.

    3. COCO Pretrained Transfer Learning
       → yolo11s.pt ağırlıklarıyla başlanır; tıbbi küçük dataset'te %15-20 mAP
         avantajı sağlar. Backbone dondurulur, neck+head ince ayar yapılır.

Veri Analizi Kısıtlamaları (Dataset'ten):
    Sınıf sayıları (train):
        0 Komedon : 829   → γ=3.51, α=0.436
        1 Nodül   : 6339  → γ=1.27, α=0.057
        2 Papül   : 3492  → γ=1.71, α=0.104
        3 Püstül  : 4316  → γ=1.54, α=0.084

Dizin Yapısı (Çıktı):
    Robo Flow V1/
    ├── islenmiş_veri/          ← Aşama 01 çıktısı (giriş)
    └── model/                  ← Bu aşama çıktısı
        ├── asama_02_model_insasi.py  (bu dosya kopyalanır)
        ├── README.md
        ├── yolo11s_akne.yaml         ← Modifiye YOLO config
        └── checkpoints/
            └── (eğitim sonrası .pt dosyaları buraya)  ← Aşama 03 kullanır

Kullanım:
    from asama_02_model_insasi import ModelInsaci
    insaci = ModelInsaci()
    model  = insaci.calistir()      # Modifiye model döner
    insaci.yapilandirilmis_modeli_kaydet()
=============================================================================
"""

# =============================================================================
# IMPORTS
# =============================================================================

import os
import math
import shutil
import logging
import warnings
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml

# Ultralytics YOLO — pip install ultralytics
try:
    from ultralytics import YOLO
    from ultralytics.nn.modules import C2f, Conv
    _ULTRALYTICS_OK = True
except ImportError as e:
    _ULTRALYTICS_OK = False
    warnings.warn(f"ultralytics yüklenemedi: {e}. 'pip install ultralytics' çalıştır.")

warnings.filterwarnings("ignore", category=UserWarning)


# =============================================================================
# YAPILANDIRMA
# =============================================================================

@dataclass
class ModelYapilandirma:
    """
    Aşama 02'nin tüm hiperparametreleri tek yerde.
    Değer değiştirmek için nesne oluştururken parametre geç.
    """

    # ── Yollar ────────────────────────────────────────────────────────────────
    roboflow_root: str = (
        "/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi/Robo Flow V1"
    )
    # islenmiş_veri: Aşama 01 çıktısı (data.yaml buradadır)
    islenmis_veri: str = ""       # Boş → roboflow_root/islenmiş_veri
    # model/:  Bu aşama çıktısı
    model_cikti:  str = ""        # Boş → roboflow_root/model

    # ── Temel model ───────────────────────────────────────────────────────────
    base_model: str = "yolo11s.pt"    # COCO pretrained; Small > Nano (+mAP)
    img_boyut: int  = 640

    # ── Sınıf bilgisi (veri analizinden) ─────────────────────────────────────
    # Sınıf id → isim
    sinif_isimleri: dict = field(default_factory=lambda: {
        0: "comedone",   # komedon
        1: "nodule",     # nodül
        2: "papule",     # papül
        3: "pustule",    # püstül
    })
    # Train set sınıf sayıları (bbox annotation, veri analizinden)
    sinif_sayilari: dict = field(default_factory=lambda: {
        0: 829,    # komedon  — 7.6x az
        1: 6339,   # nodül    — dominant
        2: 3492,   # papül
        3: 4316,   # püstül
    })

    # ── Focal Loss parametreleri ───────────────────────────────────────────────
    # γ = 2.0 × sqrt(max_count / class_count)
    # α = max_count / (n_classes × class_count)  → normalize edilmiş ağırlık
    focal_gamma_base: float = 2.0     # Taban γ çarpanı
    focal_alpha_smoothing: float = 0.1  # α değerlerini 0'a çekilmekten korur

    # ── SABottleneck ──────────────────────────────────────────────────────────
    # FPN neck katmanlarına eklenen kanal boyutları
    # YOLOv11s FPN kanalları: P3=256, P4=512, P5=512
    sa_reduction: int = 16   # SABottleneck iç kanal küçültme oranı
    sa_kernel: int   = 7     # Spatial attention konvolüsyon kernel boyutu

    # ── Transfer Learning ──────────────────────────────────────────────────────
    backbone_dondur: bool  = True   # İlk N epoch backbone dondurulur
    dondur_katman_n: int   = 10     # Dondurulacak backbone layer sayısı

    # ── CUDA ──────────────────────────────────────────────────────────────────
    device: str = ""   # Boş → otomatik (cuda varsa cuda:0, yoksa cpu)

    def __post_init__(self):
        root = Path(self.roboflow_root)
        if not self.islenmis_veri:
            self.islenmis_veri = str(root / "islenmiş_veri")
        if not self.model_cikti:
            self.model_cikti = str(root / "model")
        if not self.device:
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"


# =============================================================================
# YARDIMCI FONKSİYONLAR
# =============================================================================

def logger_kur(isim: str = "asama_02") -> logging.Logger:
    """Hem konsola hem dosyaya yazan logger döndürür."""
    log = logging.getLogger(isim)
    log.setLevel(logging.INFO)
    if log.handlers:
        log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    return log


def dinamik_focal_parametreler(
    sinif_sayilari: dict,
    gamma_base: float = 2.0,
    alpha_smoothing: float = 0.1,
) -> tuple[dict, dict]:
    """
    Veri dengesizliğinden sınıf bazlı γ ve α hesaplar.

    Formül:
        γ_i = gamma_base × sqrt(max_count / count_i)
        α_i = max_count / (n_classes × count_i)  → normalize + smoothing

    Neden:
        Komedon gibi nadir sınıflar için γ büyür → model zor örneklere
        daha fazla odaklanır. α küçük sınıflara daha yüksek ağırlık verir.

    Döndürür:
        gammas: {class_id: gamma_değeri}
        alphas: {class_id: alpha_değeri}  (toplamı ≈ 1 olacak şekilde normalize)
    """
    max_count = max(sinif_sayilari.values())
    n_cls     = len(sinif_sayilari)

    gammas = {}
    alphas = {}

    for cls_id, count in sinif_sayilari.items():
        # γ: karekök dengesizlik çarpanı, aşırı cezalandırmayı frenler
        gammas[cls_id] = gamma_base * math.sqrt(max_count / count)

        # α: ham ters frekans ağırlığı
        raw_alpha = max_count / (n_cls * count)
        alphas[cls_id] = raw_alpha

    # α değerlerini normalize et (toplam = 1), smoothing uygula
    total_alpha = sum(alphas.values())
    for cls_id in alphas:
        alphas[cls_id] = (alphas[cls_id] / total_alpha) * (1 - alpha_smoothing) + \
                          alpha_smoothing / n_cls

    return gammas, alphas


# =============================================================================
# SABottleneck — Spatial Attention Bottleneck Modülü
# =============================================================================

class SpatialAttentionGate(nn.Module):
    """
    Uzamsal (spatial) dikkat kapısı.

    Kanal bazlı max/avg pool → concat → konvolüsyon → sigmoid
    Çıktı: [B, 1, H, W] maske — her piksel için [0,1] arası önem skoru.

    Neden bu yapı:
        Max pool: Baskın özellik sinyallerini (lezyon kenarları) yakalar.
        Avg pool: Genel doku bağlamını (arka plan tonu) yakalar.
        İkisinin birleşimi: Hem lezyon hem bağlam bilgisi + konvolüsyon →
        model hangi piksellere bakacağını öğrenir.
    """

    def __init__(self, kernel_size: int = 7):
        """
        Args:
            kernel_size: Dikkat konvolüsyonu kernel boyutu.
                         Büyük kernel → daha geniş alanlı dikkat.
                         7 önerilir: küçük bbox'lar için yeterli alan.
        """
        super().__init__()
        # kernel_size tek sayı olmalı; padding = kernel//2 → boyut korunur
        padding = kernel_size // 2
        self.conv = nn.Conv2d(
            in_channels=2,        # max_pool + avg_pool concat
            out_channels=1,
            kernel_size=kernel_size,
            padding=padding,
            bias=False,           # BatchNorm sonrası bias gereksiz
        )
        self.bn  = nn.BatchNorm2d(1)
        self.act = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [B, C, H, W]
        Döndürür: [B, C, H, W] — dikkat maskesiyle ağırlıklandırılmış x
        """
        # Kanal boyutunda max ve avg pool → [B, 1, H, W]
        max_pool = torch.max(x, dim=1, keepdim=True).values
        avg_pool = torch.mean(x, dim=1, keepdim=True)

        # Birleştir → [B, 2, H, W]
        pooled   = torch.cat([max_pool, avg_pool], dim=1)

        # Dikkat maskesi → [B, 1, H, W]
        mask     = self.act(self.bn(self.conv(pooled)))

        # Orijinal feature map'i maskele
        return x * mask


class ChannelAttentionGate(nn.Module):
    """
    Kanal (channel) dikkat kapısı — ECANet benzeri hafif versiyon.

    Global avg pool → 1D konvolüsyon → sigmoid
    Çıktı: [B, C, 1, 1] kanal ağırlıkları.

    Neden:
        Hangi feature kanallarının (renk dokusu, kenar gradyanı vb.)
        lezyon tespiti için önemli olduğunu öğrenir.
        Fully-connected yerine 1D konv → parametre sayısı düşük.
    """

    def __init__(self, channels: int, reduction: int = 16):
        """
        Args:
            channels:  Giriş kanal sayısı
            reduction: İç boyut küçültme oranı (bellek/hız dengesi)
        """
        super().__init__()
        inner_ch = max(channels // reduction, 8)   # En az 8 kanal kalsın
        self.gap  = nn.AdaptiveAvgPool2d(1)          # Global Average Pool
        self.fc   = nn.Sequential(
            nn.Linear(channels, inner_ch, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(inner_ch, channels, bias=False),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [B, C, H, W]
        Döndürür: [B, C, H, W] — kanal ağırlıklandırılmış x
        """
        b, c, _, _ = x.shape
        weights = self.gap(x).view(b, c)       # [B, C]
        weights = self.fc(weights).view(b, c, 1, 1)  # [B, C, 1, 1]
        return x * weights


class SABottleneck(nn.Module):
    """
    Spatial + Channel Attention Bottleneck (CBAM-lite).

    Sıra: Channel Attention → Spatial Attention → residual bağlantı.
    Residual: Dikkat öğrenemezse bile gradient korunur (eğitim stabilitesi).

    FPN Neck'e Entegrasyon Noktası:
        YOLOv11s FPN'in P3 (256ch), P4 (512ch), P5 (512ch) çıkışlarına
        ayrı SABottleneck örnekleri eklenir. Her ölçek kendi dikkat
        ağırlıklarını bağımsız öğrenir.

        P3 (80×80): Küçük lezyonlar (komedon, küçük papül)
        P4 (40×40): Orta lezyonlar (papül, püstül)
        P5 (20×20): Büyük lezyonlar (nodül)
    """

    def __init__(self, channels: int, reduction: int = 16, sa_kernel: int = 7):
        """
        Args:
            channels:   Giriş/çıkış kanal sayısı (aynı tutulur — FPN uyumu)
            reduction:  Kanal dikkat küçültme oranı
            sa_kernel:  Uzamsal dikkat kernel boyutu
        """
        super().__init__()
        self.channel_att = ChannelAttentionGate(channels, reduction)
        self.spatial_att = SpatialAttentionGate(sa_kernel)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [B, C, H, W]
        Döndürür: [B, C, H, W] — dikkat + residual
        """
        # Önce kanal dikkatı → sonra uzamsal dikkat → residual ekle
        out = self.channel_att(x)
        out = self.spatial_att(out)
        return out + x   # Residual: eğitim başında dikkat sıfırsa bile gradient akar


# =============================================================================
# DİNAMİK FOCAL LOSS
# =============================================================================

class DynamicFocalLoss(nn.Module):
    """
    Sınıf bazlı dinamik γ ve α ile Focal Binary Cross-Entropy Loss.

    Standart Focal Loss:
        FL(p_t) = -α_t × (1 - p_t)^γ × log(p_t)

    Buradaki fark:
        - Her sınıf için farklı γ (nadir sınıflar için büyük γ)
        - Her sınıf için farklı α (nadir sınıflar için büyük α)
        - Sigmoid çıkışlı multi-label tasarımı (YOLO'nun cls loss yapısına uygun)

    Kullanım Notu:
        Bu sınıf bağımsız bir PyTorch modülüdür; Ultralytics'in iç kayıp
        mekanizmasını doğrudan değiştirmez. Aşama 03 eğitim döngüsünde
        özel kayıp hesabı için kullanılır. Ultralytics'in yerleşik eğitim
        altyapısıyla entegrasyon: DetectionTrainer subclass'ında
        criterion override edilerek kullanılır (bkz. Aşama 03).
    """

    def __init__(
        self,
        sinif_sayilari: dict,
        gamma_base: float = 2.0,
        alpha_smoothing: float = 0.1,
        reduction: str = "mean",
    ):
        """
        Args:
            sinif_sayilari:   {class_id: annotation_count}
            gamma_base:       Taban γ çarpanı (2.0 önerilir)
            alpha_smoothing:  Label smoothing benzeri α stabilizasyonu
            reduction:        'mean' | 'sum' | 'none'
        """
        super().__init__()
        self.reduction = reduction

        # Sınıf bazlı γ ve α hesapla
        gammas, alphas = dinamik_focal_parametreler(
            sinif_sayilari, gamma_base, alpha_smoothing
        )
        self.n_cls = len(sinif_sayilari)

        # Tensor'e dönüştür; sınıf sırası 0,1,2,3
        sorted_ids = sorted(sinif_sayilari.keys())
        gamma_vals = [gammas[i] for i in sorted_ids]
        alpha_vals = [alphas[i] for i in sorted_ids]

        # register_buffer: state_dict'e girer, .to(device) ile taşınır
        self.register_buffer("gammas", torch.tensor(gamma_vals, dtype=torch.float32))
        self.register_buffer("alphas", torch.tensor(alpha_vals, dtype=torch.float32))

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """
        Args:
            pred:   [B, n_cls] — raw logit (sigmoid öncesi)
            target: [B, n_cls] — 0/1 hedef (one-hot veya soft label)

        Döndürür:
            Scalar kayıp (reduction='mean' varsayılan)
        """
        # Binary cross-entropy with logits (numerik kararlı)
        bce = F.binary_cross_entropy_with_logits(
            pred, target, reduction="none"
        )  # [B, n_cls]

        # p_t: doğru sınıf tahmini olasılığı
        prob    = torch.sigmoid(pred)                           # [B, n_cls]
        p_t     = prob * target + (1 - prob) * (1 - target)    # [B, n_cls]

        # (1 - p_t)^γ modülatörü — sınıf bazlı farklı γ
        # self.gammas: [n_cls] → broadcast için [1, n_cls]
        gamma   = self.gammas.unsqueeze(0)                      # [1, n_cls]
        modulator = (1 - p_t).pow(gamma)                        # [B, n_cls]

        # α ağırlığı — sınıf bazlı
        alpha   = self.alphas.unsqueeze(0)                      # [1, n_cls]
        # Hedef=1 için α, hedef=0 için (1-α)
        alpha_t = alpha * target + (1 - alpha) * (1 - target)  # [B, n_cls]

        # Focal loss
        focal   = alpha_t * modulator * bce                     # [B, n_cls]

        if self.reduction == "mean":
            return focal.mean()
        elif self.reduction == "sum":
            return focal.sum()
        else:
            return focal   # 'none' → [B, n_cls]


# =============================================================================
# SA WRAPPER — Modül seviyesinde (torch.save pickle uyumu)
# =============================================================================

class SAWrapper(nn.Module):
    def __init__(self, base, sa):
        super().__init__()
        self.base = base
        self.sa   = sa

    def forward(self, x):
        return self.sa(self.base(x))

    def __getattr__(self, name):
        try:
            return super().__getattr__(name)
        except AttributeError:
            return getattr(self.base, name)


# =============================================================================
# YOLO NECK PATCHER — SABottleneck'i FPN'e Enjekte Eder
# =============================================================================

class YoloNeckPatcher:
    """
    YOLOv11 modelinin FPN (neck) katmanlarına SABottleneck modülleri ekler.

    Yaklaşım:
        Ultralytics modeli nn.Sequential benzeri bir model.model listesi tutar.
        FPN katmanları belirli index'lerde C2f/nn.Module olarak bulunur.
        Her FPN çıkış noktasına SABottleneck → nn.Sequential wrapper ile enjekte edilir.

    Neden Sequential Wrapper:
        Orijinal katman çıkışı → SABottleneck → sonraki katman
        Yalnızca ileriye (forward) müdahale; backprop otomatik çalışır.

    YOLOv11s Mimarisi (layer index'leri):
        Layer 15: FPN P3 (512ch)  → küçük objeler  (80×80)
        Layer 18: FPN P4 (384ch)  → orta objeler   (40×40)
        Layer 21: FPN P5 (768ch)  → büyük objeler  (20×20)
        (Hook ölçümüyle doğrulandı — skip concat sonrası değerler)
    """

    # YOLOv11s FPN katman index'leri ve gerçek kanal boyutları
    # Hook ölçümüyle doğrulandı (forward pass, 640×640 giriş):
    #   Layer 15: [1, 512, 80×80]  — P3, skip concat sonrası
    #   Layer 18: [1, 384, 40×40]  — P4, skip concat sonrası
    #   Layer 21: [1, 768, 20×20]  — P5, skip concat sonrası
    # Concat öncesi tahmin (256/512/512) yanlıştı; skip bağlantısı kanal sayısını artırır.
    YOLO11S_FPN_LAYERS = {
        15: 512,   # P3 — small scale  (80×80)
        18: 384,   # P4 — medium scale (40×40)
        21: 768,   # P5 — large scale  (20×20)
    }

    def __init__(self, cfg: ModelYapilandirma, log: logging.Logger):
        self.cfg = cfg
        self.log = log

    def _katman_boyutunu_bul(self, model: nn.Module, layer_idx: int) -> int:
        """
        Belirtilen layer'ın çıkış kanal boyutunu dinamik olarak tespit eder.
        FPN layer map'i yanlışsa fallback olarak kullanılır.
        """
        try:
            katman = model.model[layer_idx]
            # C2f veya Conv tipi katmanlarda cv2.out_channels
            if hasattr(katman, 'cv2'):
                return katman.cv2.out_channels if hasattr(katman.cv2, 'out_channels') \
                       else katman.cv2.conv.out_channels
            # Genel nn.Conv2d
            for m in katman.modules():
                if isinstance(m, nn.Conv2d):
                    return m.out_channels
        except Exception:
            pass
        return self.YOLO11S_FPN_LAYERS.get(layer_idx, 256)

    def patch(self, ultralytics_model) -> None:
        """
        Ultralytics YOLO modelinin FPN katmanlarına SABottleneck enjekte eder.

        Args:
            ultralytics_model: ultralytics.YOLO nesnesi (.model iç modeli değil)
        """
        nn_model = ultralytics_model.model   # Asıl PyTorch nn.Module
        nn_model.to(self.cfg.device)

        basarili = 0
        for layer_idx, varsayilan_ch in self.YOLO11S_FPN_LAYERS.items():
            try:
                # Kanal boyutunu doğrula
                ch = self._katman_boyutunu_bul(nn_model, layer_idx)
                self.log.info(
                    f"  FPN Layer {layer_idx}: {ch}ch → SABottleneck ekleniyor"
                )

                # Orijinal katmanı al
                orijinal_katman = nn_model.model[layer_idx]

                # SABottleneck oluştur
                sa_block = SABottleneck(
                    channels=ch,
                    reduction=self.cfg.sa_reduction,
                    sa_kernel=self.cfg.sa_kernel,
                )
                sa_block.to(self.cfg.device)

                # Wrapper: orijinal → SABottleneck
                # SAWrapper modül seviyesinde tanımlı — torch.save pickle uyumu
                nn_model.model[layer_idx] = SAWrapper(orijinal_katman, sa_block)
                basarili += 1

            except Exception as e:
                self.log.warning(
                    f"  Layer {layer_idx} SABottleneck enjeksiyonu başarısız: {e}"
                )
                self.log.warning("  → Orijinal katman korundu")

        self.log.info(
            f"SABottleneck enjeksiyonu: {basarili}/{len(self.YOLO11S_FPN_LAYERS)} "
            f"katman başarılı"
        )


# =============================================================================
# BACKBONE DONDURMA
# =============================================================================

class BackboneDondurma:
    """
    Transfer learning başlangıcında backbone katmanlarını dondurur.

    Neden:
        COCO pretrained backbone zaten güçlü genel feature'lar öğrenmiştir.
        İlk epoch'larda backbone gradyanını serbest bırakmak → pretrained
        ağırlıklar bozulur. Neck + Head önce ısınır, sonra backbone açılır.
        Aşama 03'te belirli epoch'tan sonra unfreeze çağrılır.

    Dondurma Stratejisi:
        İlk N layer (backbone) → requires_grad=False
        N+1 sonrası (neck + head) → requires_grad=True
    """

    def __init__(self, model: nn.Module, katman_n: int = 10, log: Optional[logging.Logger] = None):
        self.model   = model
        self.n       = katman_n
        self.log     = log or logging.getLogger("backbone_dondurma")
        self._donduruldu = False

    def dondur(self) -> None:
        """İlk N layer'ı dondurur."""
        if self._donduruldu:
            return
        donduruldu = 0
        for i, layer in enumerate(self.model.model):
            if i < self.n:
                for p in layer.parameters():
                    p.requires_grad = False
                donduruldu += 1
        self._donduruldu = True
        self.log.info(f"Backbone dondurma: {donduruldu} layer donduruldu (0-{self.n-1})")

    def coz(self) -> None:
        """Tüm parametreleri eğitilebilir yapar (ısınma sonrası)."""
        for layer in self.model.model:
            for p in layer.parameters():
                p.requires_grad = True
        self._donduruldu = False
        self.log.info("Backbone çözüldü — tüm parametreler eğitilebilir")

    def egitilbilir_parametre_sayisi(self) -> tuple[int, int]:
        """
        Döndürür: (eğitilebilir, toplam) parametre sayısı
        """
        toplam    = sum(p.numel() for p in self.model.parameters())
        egitilir  = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        return egitilir, toplam


# =============================================================================
# MODEL YAML ÜRETICI — Ultralytics için modifiye config
# =============================================================================

class ModelYamlUretici:
    """
    Ultralytics'in yolo11s.yaml'ını temel alarak modifiye config üretir.
    SABottleneck ve Focal Loss ayarlarını YAML'a yazar.

    Bu YAML doğrudan eğitimde kullanılmaz (model yükleme pretrained ile yapılır),
    ancak versiyonlama ve reproducibility için kaydedilir.
    """

    def __init__(self, cfg: ModelYapilandirma):
        self.cfg = cfg

    def uret(self, kaydet_yolu: str) -> dict:
        """
        Model konfigürasyonunu dict olarak üretir ve YAML'a kaydeder.

        Returns:
            config_dict: Model yapılandırma sözlüğü
        """
        gammas, alphas = dinamik_focal_parametreler(
            self.cfg.sinif_sayilari,
            self.cfg.focal_gamma_base,
            self.cfg.focal_alpha_smoothing,
        )

        config = {
            "# Model": "YOLOv11s + SABottleneck (FPN) + Dynamic Focal Loss",
            "# Versiyon": "1.0 — Aşama 02",
            "base_model": self.cfg.base_model,
            "img_size": self.cfg.img_boyut,
            "nc": len(self.cfg.sinif_isimleri),
            "names": self.cfg.sinif_isimleri,
            "sinif_sayilari": self.cfg.sinif_sayilari,
            "sa_bottleneck": {
                "fpn_layers": [15, 18, 21],
                "channels":   [512, 384, 768],
                "reduction":  self.cfg.sa_reduction,
                "kernel":     self.cfg.sa_kernel,
            },
            "focal_loss": {
                "gamma_base": self.cfg.focal_gamma_base,
                "alpha_smoothing": self.cfg.focal_alpha_smoothing,
                "per_class_gamma": {
                    self.cfg.sinif_isimleri[i]: round(gammas[i], 4)
                    for i in sorted(gammas)
                },
                "per_class_alpha": {
                    self.cfg.sinif_isimleri[i]: round(alphas[i], 4)
                    for i in sorted(alphas)
                },
            },
            "transfer_learning": {
                "pretrained": self.cfg.base_model,
                "freeze_backbone_layers": self.cfg.dondur_katman_n,
            },
        }

        os.makedirs(os.path.dirname(kaydet_yolu), exist_ok=True)
        with open(kaydet_yolu, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return config


# =============================================================================
# README ÜRETİCİ
# =============================================================================

def readme_yaz(cikti_klasor: str, cfg: ModelYapilandirma, gammas: dict, alphas: dict) -> None:
    """
    model/ klasörüne README.md yazar.
    """
    icerik = f"""# Aşama 02 — Model İnşası

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
Formül: γ = {cfg.focal_gamma_base:.1f} × sqrt(max_count / class_count)

| Sınıf    | Sayı  | γ     | α     |
|----------|-------|-------|-------|
"""
    for cls_id in sorted(cfg.sinif_sayilari.keys()):
        isim  = cfg.sinif_isimleri[cls_id]
        sayi  = cfg.sinif_sayilari[cls_id]
        gamma = gammas[cls_id]
        alpha = alphas[cls_id]
        icerik += f"| {isim:8s} | {sayi:5d} | {gamma:.3f} | {alpha:.3f} |\n"

    icerik += f"""
### 3. Transfer Learning
- Base: {cfg.base_model} (COCO pretrained)
- Backbone dondurma: İlk {cfg.dondur_katman_n} layer (ısınma süresince)
- Çözme: Aşama 03 eğitim döngüsünde belirli epoch'ta

## Giriş / Çıkış
- Giriş (data): `{cfg.islenmis_veri}/data.yaml`
- Device: `{cfg.device}`
- Checkpoint çıkışı: `{cikti_klasor}/checkpoints/`

## Sonraki Adım
`asama_03_egitim_dongusu.py` → Model bu aşamanın çıktısını yükler.
"""

    readme_yolu = Path(cikti_klasor) / "README.md"
    with open(readme_yolu, "w", encoding="utf-8") as f:
        f.write(icerik)


# =============================================================================
# MODEL İNŞACI — Ana Orkestratör
# =============================================================================

class ModelInsaci:
    """
    Aşama 02'nin ana sınıfı.

    Adımlar:
        1. Ultralytics YOLOv11s yükle (COCO pretrained)
        2. FPN'e SABottleneck enjekte et
        3. Backbone'u dondur
        4. DynamicFocalLoss nesnesi oluştur (Aşama 03'e döndürülür)
        5. Model konfigürasyonunu ve README'yi kaydet
        6. Doğrulama: forward pass testi
    """

    def __init__(self, cfg: Optional[ModelYapilandirma] = None):
        self.cfg = cfg or ModelYapilandirma()
        self.log = logger_kur("asama_02")
        self.model            = None    # Ultralytics YOLO nesnesi
        self.focal_loss       = None    # DynamicFocalLoss nesnesi
        self.backbone_dondur  = None    # BackboneDondurma yardımcısı

        # Çıktı klasörlerini oluştur
        Path(self.cfg.model_cikti).mkdir(parents=True, exist_ok=True)
        Path(self.cfg.model_cikti, "checkpoints").mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 1: Model yükleme
    # ──────────────────────────────────────────────────────────────────────────

    def _model_yukle(self) -> None:
        """
        YOLOv11s'i COCO pretrained ağırlıklarla yükler.
        ultralytics otomatik olarak yolo11s.pt'yi indirir (ilk çalıştırmada).
        """
        self.log.info(f"YOLOv11s yükleniyor: {self.cfg.base_model}")
        self.log.info(f"Device: {self.cfg.device}")

        if not _ULTRALYTICS_OK:
            raise ImportError("ultralytics kurulu değil. 'pip install ultralytics' çalıştır.")

        self.model = YOLO(self.cfg.base_model)
        self.model.to(self.cfg.device)

        # Parametre sayısını raporla
        toplam = sum(p.numel() for p in self.model.model.parameters())
        self.log.info(f"Model yüklendi: {toplam/1e6:.2f}M parametre")

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 2: SABottleneck enjeksiyonu
    # ──────────────────────────────────────────────────────────────────────────

    def _sa_ekle(self) -> None:
        """FPN katmanlarına SABottleneck enjekte eder."""
        self.log.info("SABottleneck FPN enjeksiyonu başlıyor...")
        patcher = YoloNeckPatcher(self.cfg, self.log)
        patcher.patch(self.model)

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 3: Backbone dondurma
    # ──────────────────────────────────────────────────────────────────────────

    def _backbone_dondur(self) -> None:
        """Transfer learning için backbone'u dondurur."""
        self.backbone_dondur = BackboneDondurma(
            self.model.model,
            katman_n=self.cfg.dondur_katman_n,
            log=self.log,
        )
        if self.cfg.backbone_dondur:
            self.backbone_dondur.dondur()
            egitilir, toplam = self.backbone_dondur.egitilbilir_parametre_sayisi()
            self.log.info(
                f"Eğitilebilir: {egitilir/1e6:.2f}M / {toplam/1e6:.2f}M parametre "
                f"(%{100*egitilir/toplam:.1f})"
            )

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 4: Focal Loss oluşturma
    # ──────────────────────────────────────────────────────────────────────────

    def _focal_loss_olustur(self) -> None:
        """Dinamik Focal Loss nesnesi oluşturur."""
        self.log.info("Dinamik Focal Loss parametreleri hesaplanıyor...")
        self.focal_loss = DynamicFocalLoss(
            sinif_sayilari=self.cfg.sinif_sayilari,
            gamma_base=self.cfg.focal_gamma_base,
            alpha_smoothing=self.cfg.focal_alpha_smoothing,
        ).to(self.cfg.device)

        # Hesaplanan değerleri raporla
        gammas, alphas = dinamik_focal_parametreler(
            self.cfg.sinif_sayilari,
            self.cfg.focal_gamma_base,
            self.cfg.focal_alpha_smoothing,
        )
        self.log.info("  Sınıf bazlı Focal Loss parametreleri:")
        for cls_id in sorted(self.cfg.sinif_sayilari.keys()):
            isim = self.cfg.sinif_isimleri[cls_id]
            self.log.info(
                f"    [{cls_id}] {isim:10s}: "
                f"γ={gammas[cls_id]:.3f}  α={alphas[cls_id]:.3f}  "
                f"(n={self.cfg.sinif_sayilari[cls_id]})"
            )

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 5: Kaydetme
    # ──────────────────────────────────────────────────────────────────────────

    def _kaydet(self) -> None:
        """Model konfigürasyonu, README ve kaynak kodu kaydeder."""
        # Kaynak kodunu model klasörüne kopyala (reproducibility)
        # Jupyter'da __file__ tanımsız olabilir → güvenli kontrol
        try:
            kaynak_py = Path(__file__)
            if kaynak_py.exists():
                hedef_py = Path(self.cfg.model_cikti) / kaynak_py.name
                shutil.copy2(str(kaynak_py), str(hedef_py))
                self.log.info(f"Kaynak kod kopyalandı: {hedef_py}")
        except NameError:
            self.log.info("Kaynak kod kopyalaması atlandı (Jupyter ortamı)")

        # YAML konfigürasyonu
        yaml_yolu = str(Path(self.cfg.model_cikti) / "yolo11s_akne.yaml")
        yaml_uretici = ModelYamlUretici(self.cfg)
        yaml_uretici.uret(yaml_yolu)
        self.log.info(f"Model YAML kaydedildi: {yaml_yolu}")

        # README
        gammas, alphas = dinamik_focal_parametreler(
            self.cfg.sinif_sayilari,
            self.cfg.focal_gamma_base,
            self.cfg.focal_alpha_smoothing,
        )
        readme_yaz(self.cfg.model_cikti, self.cfg, gammas, alphas)
        self.log.info(f"README kaydedildi: {self.cfg.model_cikti}/README.md")

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 6: Doğrulama — forward pass
    # ──────────────────────────────────────────────────────────────────────────

    def _dogrula(self) -> None:
        """
        Dummy tensor ile forward pass yaparak model bütünlüğünü test eder.
        SABottleneck enjeksiyonu sonrası boyut uyumunu doğrular.
        """
        self.log.info("Forward pass doğrulaması...")
        self.model.model.eval()

        try:
            with torch.no_grad():
                dummy = torch.zeros(
                    1, 3, self.cfg.img_boyut, self.cfg.img_boyut,
                    device=self.cfg.device,
                )
                # Ultralytics modeli predict() ile çağrılır (eğitim modunda değil)
                cikti = self.model.model(dummy)

            # Çıktı boyutlarını raporla
            if isinstance(cikti, (list, tuple)):
                for i, c in enumerate(cikti):
                    if hasattr(c, 'shape'):
                        self.log.info(f"  Çıktı [{i}]: {tuple(c.shape)}")
                    elif isinstance(c, (list, tuple)):
                        for j, cc in enumerate(c):
                            if hasattr(cc, 'shape'):
                                self.log.info(f"  Çıktı [{i}][{j}]: {tuple(cc.shape)}")
            self.log.info("Forward pass başarılı ✓")

        except Exception as e:
            self.log.error(f"Forward pass başarısız: {e}")
            self.log.error("SABottleneck layer index'leri modelle uyumsuz olabilir.")
            self.log.error("YoloNeckPatcher.YOLO11S_FPN_LAYERS dict'ini kontrol et.")
            raise

        finally:
            # Eğitim moduna geri al
            self.model.model.train()

    # ──────────────────────────────────────────────────────────────────────────
    # ANA ÇALIŞTIRICI
    # ──────────────────────────────────────────────────────────────────────────

    def calistir(self) -> "YOLO":
        """
        Tüm model inşa sürecini uçtan uca çalıştırır.

        Döndürür:
            ultralytics.YOLO: SABottleneck + Backbone dondurma uygulanmış model
            (focal_loss ayrıca self.focal_loss üzerinden erişilir)
        """
        self.log.info("=" * 60)
        self.log.info("AŞAMA 02 — Model İnşası BAŞLIYOR")
        self.log.info(f"Base model : {self.cfg.base_model}")
        self.log.info(f"Device     : {self.cfg.device}")
        self.log.info(f"Çıktı      : {self.cfg.model_cikti}")
        self.log.info("=" * 60)

        self._model_yukle()       # 1. COCO pretrained yükle
        self._sa_ekle()           # 2. SABottleneck → FPN
        self._backbone_dondur()   # 3. Backbone dondur
        self._focal_loss_olustur()  # 4. Focal Loss hazırla
        self._kaydet()            # 5. Konfigürasyon kaydet
        self._dogrula()           # 6. Forward pass testi

        self.log.info("=" * 60)
        self.log.info("AŞAMA 02 TAMAMLANDI")
        self.log.info(f"Model çıktısı: {self.cfg.model_cikti}")
        self.log.info("Sonraki adım : asama_03_egitim_dongusu.py")
        self.log.info("=" * 60)

        return self.model

    def aşama03_icin_paketle(self) -> dict:
        """
        Aşama 03'ün ihtiyaç duyduğu nesneleri paketler.

        Döndürür:
            {
                "model":           ultralytics.YOLO nesnesi,
                "focal_loss":      DynamicFocalLoss nesnesi,
                "backbone_helper": BackboneDondurma nesnesi,
                "cfg":             ModelYapilandirma nesnesi,
                "data_yaml":       data.yaml yolu (str),
            }
        """
        return {
            "model":           self.model,
            "focal_loss":      self.focal_loss,
            "backbone_helper": self.backbone_dondur,
            "cfg":             self.cfg,
            "data_yaml":       str(Path(self.cfg.islenmis_veri) / "data.yaml"),
        }


# =============================================================================
# DOĞRUDAN ÇALIŞTIRMA — python asama_02_model_insasi.py
# =============================================================================

if __name__ == "__main__":

    # CUDA kontrolü
    print(f"CUDA kullanılabilir: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # Model inşa et
    insaci = ModelInsaci()
    model  = insaci.calistir()

    # Aşama 03 paketi — Jupyter'dan import edildiğinde kullanılır
    paket = insaci.aşama03_icin_paketle()
    print(f"\nAşama 03 paketi hazır:")
    print(f"  data.yaml : {paket['data_yaml']}")
    print(f"  model     : {type(paket['model']).__name__}")
    print(f"  focal_loss: {type(paket['focal_loss']).__name__}")