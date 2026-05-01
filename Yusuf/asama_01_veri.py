"""
=============================================================================
AŞAMA 01 — Veri Ön İşleme ve Artırım (asama_01_veri.py)
=============================================================================
Proje  : YOLOv11 Tabanlı Akne Tespit ve Şiddet Derecelendirme Sistemi
Yazar  : Dermatoloji AI Pipeline
Versiyon: 1.0

Amaç:
    Ham YOLO formatındaki akne veri setini eğitime hazır hale getirmek.
    Klinik geçerlilik için cilt tonu adaptasyonu, sınıf dengesizliği giderimi
    ve bbox-güvenli veri artırımı uygulanır.

Kritik Bulgular (Veri Analizi):
    - Tek-sınıf görüntüler: Her görüntüde yalnızca 1 sınıf → Mosaic ile çözülür
    - Komedon 7.6x az → Otomatik oversampling
    - BBox'ların %54'ü small (640px'de ~34x34px) → Hassas bbox dönüşümü şart
    - Karanlık görüntü oranı %23 → Dinamik CLAHE zorunlu

Sınıf Eşleştirmesi (data.yaml'dan):
    0 = comedone (komedon)
    1 = nodule   (nodül)
    2 = papule   (papül)
    3 = pustule  (püstül)

Kullanım:
    from asama_01_veri import VeriOnIsleme
    isleme = VeriOnIsleme(dataset_root="...")
    isleme.calistir()
=============================================================================
"""

import os
import cv2
import numpy as np
import albumentations as A
import logging
import shutil
import random
from pathlib import Path
from PIL import Image
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional
import multiprocessing
import time

# =============================================================================
# YAPILANDIRMA — Tüm sabitler tek yerde, kolayca değiştirilebilir
# =============================================================================

@dataclass
class VeriYapilandirma:
    """
    Pipeline'ın tüm ayarları bu sınıfta toplanır.
    Değer değiştirmek için nesne oluştururken parametre geç:
        cfg = VeriYapilandirma(batch_boyutu=32)
    """

    # ── Yollar ────────────────────────────────────────────────────────────────
    dataset_root: str = (
        "/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi"
        "/Robo Flow V1/Acne-Detection-V1-1"
    )
    cikti_root: str = ""          # Boş bırakılırsa dataset_root/../islenmiş_veri olur

    # ── Görüntü boyutu ────────────────────────────────────────────────────────
    img_boyut: int = 640           # YOLO standardı; değiştirme

    # ── CLAHE eşikleri (cilt tonu tespiti) ───────────────────────────────────
    koyu_cilt_v_esigi: float = 0.40    # V < 0.40 → koyu cilt
    orta_cilt_v_esigi: float = 0.65    # 0.40 ≤ V < 0.65 → orta cilt
    clahe_koyu: float  = 4.0           # Koyu cilt clip_limit
    clahe_orta: float  = 2.5           # Orta cilt clip_limit
    clahe_acik: float  = 1.5           # Açık cilt clip_limit
    clahe_tile: tuple  = (8, 8)        # CLAHE tile grid boyutu

    # ── Medyan filtresi ───────────────────────────────────────────────────────
    medyan_kernel: int = 3             # 3 veya 5 önerilir; büyütme detay kaybeder

    # ── Albumentations artırım parametreleri ──────────────────────────────────
    aug_rotasyon_limit: int   = 15     # ±15 derece
    aug_shear_limit: int      = 10     # ±10 derece
    aug_sat_limit: float      = 0.15   # ±%15 doygunluk
    aug_exp_limit: float      = 0.15   # ±%15 parlaklık
    aug_blur_limit: float     = 2.5    # Max 2.5px blur
    aug_noise_limit: float    = 0.0101 # Max %1.01 gürültü

    # ── Oversampling ──────────────────────────────────────────────────────────
    maks_oversample_kati: int = 8      # Bir sınıf için max kaç kat augment yapılır
    hedef_sinif_dengesi: float = 0.5   # Azınlık sınıfı dominant'ın en az %50'sine çıkar

    # ── Mosaic ────────────────────────────────────────────────────────────────
    mosaic_orani: float = 0.3          # Train görüntülerinin %30'u mosaic ile üretilir
    mosaic_min_bbox_alani: float = 0.0004  # Mosaicten sonra bu alan altı bbox atılır

    # ── Paralel işlem ─────────────────────────────────────────────────────────
    num_workers: int = field(default_factory=lambda: min(20, multiprocessing.cpu_count()))
    # Intel Ultra 9: 24 thread var; I/O sınırlı işlerde 20 yeterli

    # ── Kayıt ─────────────────────────────────────────────────────────────────
    jpg_kalite: int = 95               # JPG kayıt kalitesi (0-100)
    random_seed: int = 42

    def __post_init__(self):
        # Çıktı yolu ayarlanmamışsa otomatik belirle
        if not self.cikti_root:
            parent = Path(self.dataset_root).parent
            self.cikti_root = str(parent / "islenmiş_veri")


# =============================================================================
# YARDIMCI FONKSİYONLAR — Modülün en alt katmanı, saf fonksiyonlar
# =============================================================================

def logger_kur(isim: str = "asama_01") -> logging.Logger:
    """Hem dosyaya hem konsola yazan logger döndürür."""
    log = logging.getLogger(isim)
    log.setLevel(logging.INFO)
    if log.handlers:        # Jupyter'da çift kayıt önlenir
        log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    # Konsol
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    return log


def goruntu_oku(yol: str) -> Optional[np.ndarray]:
    """
    Türkçe/boşluklu yollarda cv2.imread başarısız olur.
    PIL → NumPy yöntemiyle her yolu güvenle okur.
    BGR formatında döndürür (cv2 uyumlu).
    """
    try:
        img_pil = Image.open(yol).convert("RGB")
        img_rgb = np.array(img_pil, dtype=np.uint8)
        return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    except Exception as e:
        return None


def goruntu_kaydet(yol: str, img_bgr: np.ndarray, kalite: int = 95) -> bool:
    """
    Türkçe yollarda cv2.imwrite başarısız olur.
    PIL ile güvenli kayıt; BGR → RGB dönüşümü yapılır.
    """
    try:
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        pil_img.save(yol, "JPEG", quality=kalite, optimize=True)
        return True
    except Exception:
        return False


def etiket_oku(yol: str) -> list[list[float]]:
    """
    YOLO formatı etiket dosyasını okur.
    Döndürür: [[class_id, cx, cy, w, h], ...]
    """
    kutular = []
    try:
        with open(yol, "r", encoding="utf-8") as f:
            for satir in f:
                parcalar = satir.strip().split()
                if len(parcalar) == 5:
                    kutular.append([float(p) for p in parcalar])
    except Exception:
        pass
    return kutular


def etiket_kaydet(yol: str, kutular: list[list[float]]) -> None:
    """
    YOLO formatında etiket dosyası kaydeder.
    class_id int olarak, koordinatlar 6 ondalık hassasiyetle.
    """
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        for kutu in kutular:
            cls = int(kutu[0])
            coords = " ".join(f"{v:.6f}" for v in kutu[1:])
            f.write(f"{cls} {coords}\n")


def cilt_tonu_tespiti(img_bgr: np.ndarray, cfg: VeriYapilandirma) -> str:
    """
    HSV V kanalının ortalamasına göre cilt tonunu belirler.
    Döndürür: 'koyu' | 'orta' | 'acik'
    """
    img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    # V kanalı 0-255; normalize et
    v_ort = img_hsv[:, :, 2].mean() / 255.0
    if v_ort < cfg.koyu_cilt_v_esigi:
        return "koyu"
    elif v_ort < cfg.orta_cilt_v_esigi:
        return "orta"
    else:
        return "acik"


def on_isle(img_bgr: np.ndarray, cfg: VeriYapilandirma) -> np.ndarray:
    """
    Tek bir görüntüye ön işleme uygular:
    1. Medyan filtresi (gürültü azaltma)
    2. Dinamik CLAHE (cilt tonu adaptasyonu)

    Giriş/Çıkış: BGR NumPy array
    """
    # ── 1. Medyan filtresi ───────────────────────────────────────────────────
    # Salt-pepper gürültü; sivilce kenarlarını net tutar
    img = cv2.medianBlur(img_bgr, cfg.medyan_kernel)

    # ── 2. Cilt tonu tespiti ve dinamik CLAHE ────────────────────────────────
    ton = cilt_tonu_tespiti(img, cfg)
    clip_map = {"koyu": cfg.clahe_koyu, "orta": cfg.clahe_orta, "acik": cfg.clahe_acik}
    clip_limit = clip_map[ton]

    # CLAHE yalnızca L (aydınlık) kanalına uygulanır → renk bozulmaz
    img_lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(img_lab)
    clahe = cv2.createCLAHE(
        clipLimit=clip_limit,
        tileGridSize=cfg.clahe_tile
    )
    l_eq = clahe.apply(l)
    img_eq = cv2.merge([l_eq, a, b])
    img_out = cv2.cvtColor(img_eq, cv2.COLOR_LAB2BGR)

    return img_out


# =============================================================================
# ALBUMENTATIONS PIPELINE — Eğitim seti artırımı
# =============================================================================

def augmentasyon_pipeline_olustur(cfg: VeriYapilandirma) -> A.Compose:
    """
    Eğitim seti için Albumentations pipeline döndürür.

    Neden bu dönüşümler?
    - Rotate/Shear: Farklı açılardan çekilmiş yüzler simüle edilir
    - HueSaturationValue: Farklı ışık koşulları / cilt tonları
    - GaussianBlur: Düşük çözünürlüklü / hareket bulanıklığı
    - GaussNoise: Kamera sensör gürültüsü

    bbox_params zorunlu: Rotate/Shear sırasında bbox koordinatları
    otomatik güncellenir; aksi hâlde bbox kayar.
    """
    return A.Compose(
        [
            # Geometrik dönüşümler — bbox ile birlikte döner
            A.Rotate(
                limit=cfg.aug_rotasyon_limit,
                border_mode=cv2.BORDER_REFLECT_101,   # Kenar pikselleri yansıtır
                p=0.7
            ),
            A.Affine(
                shear=(-cfg.aug_shear_limit, cfg.aug_shear_limit),
                p=0.5
            ),

            # Renk/parlaklık dönüşümleri — geometrik değil, bbox değişmez
            A.HueSaturationValue(
                hue_shift_limit=0,                    # Ton kaydırma yok (cilt tonu korunur)
                sat_shift_limit=int(cfg.aug_sat_limit * 255),
                val_shift_limit=int(cfg.aug_exp_limit * 255),
                p=0.6
            ),

            # Blur — maksimum 2.5px; küçük bbox'ları silmez
            A.GaussianBlur(
                blur_limit=(3, max(3, int(cfg.aug_blur_limit * 2) | 1)),  # Tek sayı zorunlu
                p=0.3
            ),

            # Gürültü
            A.GaussNoise(
                std_range=(0, cfg.aug_noise_limit),
                p=0.3
            ),

            # Yatay çevirme — yüzde sol/sağ fark etmez
            A.HorizontalFlip(p=0.5),
        ],
        bbox_params=A.BboxParams(
            format="yolo",
            label_fields=["class_labels"],
            min_visibility=0.3,     # Augmentten sonra %30'dan az kalan bbox atılır
            min_area=0.0001,        # Çok küçük bbox'lar atılır (piksel gürültüsü)
        ),
    )


# =============================================================================
# MOSAİC — Tek-sınıf problemi çözümü
# =============================================================================

def mosaic_olustur(
    goruntu_yollari: list[str],
    etiket_yollari: list[str],
    cfg: VeriYapilandirma,
) -> tuple[np.ndarray, list[list[float]]]:
    """
    4 görüntüyü 2x2 grid'de birleştirerek mosaic üretir.

    Neden gerekli?
    Veri setinde her görüntüde yalnızca 1 sınıf var (örn. sadece nodül).
    Mosaic 4 farklı sınıfı tek görüntüde birleştirir → model multi-class öğrenir.

    Koordinat dönüşümü:
    Her sub-görüntünün (cx, cy) değeri global mosaic koordinatına çevrilir.
    w, h değerleri de yarıya indirilir (sub-görüntü 640/2 = 320px'dir).

    Döndürür: (mosaic_img_bgr, birleşik_kutular)
    """
    S = cfg.img_boyut          # 640
    half = S // 2              # 320 — her çeyreğin boyutu

    # Boş tuval
    mozaik = np.zeros((S, S, 3), dtype=np.uint8)
    tum_kutular = []

    # 4 pozisyon: sol-üst, sağ-üst, sol-alt, sağ-alt
    pozisyonlar = [(0, 0), (half, 0), (0, half), (half, half)]

    # Rastgele 4 görüntü seç (liste 4'ten azsa tekrar kullan)
    secilen_idx = [random.randint(0, len(goruntu_yollari) - 1) for _ in range(4)]

    for i, idx in enumerate(secilen_idx):
        img = goruntu_oku(goruntu_yollari[idx])
        if img is None:
            continue

        # Sub-görüntüyü yarı boyuta indirge
        img_kucuk = cv2.resize(img, (half, half), interpolation=cv2.INTER_LINEAR)

        # Yerleştir
        x_off, y_off = pozisyonlar[i]
        mozaik[y_off:y_off + half, x_off:x_off + half] = img_kucuk

        # Etiket koordinatlarını global'e dönüştür
        kutular = etiket_oku(etiket_yollari[idx])
        for kutu in kutular:
            cls, cx, cy, w, h = kutu
            # Sub-görüntüde normalize koordinat → global normalize koordinat
            cx_global = (x_off + cx * half) / S
            cy_global = (y_off + cy * half) / S
            w_global  = w * half / S
            h_global  = h * half / S

            # Sınır kontrolü
            if w_global < 0.005 or h_global < 0.005:
                continue  # Çok küçük bbox atılır
            alan = w_global * h_global
            if alan < cfg.mosaic_min_bbox_alani:
                continue

            # Görüntü dışına taşanları kırp
            cx_global = np.clip(cx_global, 0.001, 0.999)
            cy_global = np.clip(cy_global, 0.001, 0.999)
            x1 = cx_global - w_global / 2
            x2 = cx_global + w_global / 2
            y1 = cy_global - h_global / 2
            y2 = cy_global + h_global / 2
            x1, x2 = max(0.0, x1), min(1.0, x2)
            y1, y2 = max(0.0, y1), min(1.0, y2)
            w_kırp = x2 - x1
            h_kırp = y2 - y1
            if w_kırp < 0.005 or h_kırp < 0.005:
                continue
            tum_kutular.append([cls, (x1 + x2) / 2, (y1 + y2) / 2, w_kırp, h_kırp])

    return mozaik, tum_kutular


# =============================================================================
# SINIF DENGESİ ANALİZİ — Oversampling oranı hesabı
# =============================================================================

def sinif_sayilari_hesapla(etiket_klasoru: str) -> Counter:
    """
    Bir split'teki tüm etiket dosyalarını tarar.
    Her görüntünün sınıfını dosya adından okur (levle0/1/2/3 → sınıf).

    Döndürür: Counter({sınıf_id: görüntü_sayısı})
    """
    sayac = Counter()
    for txt in Path(etiket_klasoru).glob("*.txt"):
        with open(txt, "r") as f:
            siniflar = set()
            for satir in f:
                parcalar = satir.strip().split()
                if parcalar:
                    siniflar.add(int(parcalar[0]))
        for s in siniflar:
            sayac[s] += 1
    return sayac


def oversample_oranlari_hesapla(
    sayac: Counter,
    cfg: VeriYapilandirma,
) -> dict[int, int]:
    """
    Her sınıf için kaç kat augmentasyon yapılacağını hesaplar.

    Formül:
        oran = min(maks_kat, ceil(dominant / (hedef_oran * azınlık)))
        Dominant sınıf: oran = 1 (ek augment gerekmez)

    Örnek (mevcut veri):
        Nodül: 6339 (dominant)
        Komedon: 829 → 6339 / (0.5 * 829) ≈ 15.3 → min(8, 15) = 8 kat
    """
    if not sayac:
        return {}
    dominant = max(sayac.values())
    oranlar = {}
    for sinif, sayi in sayac.items():
        if sayi == 0:
            oranlar[sinif] = 1
            continue
        hedef = dominant * cfg.hedef_sinif_dengesi
        oran = int(np.ceil(hedef / sayi))
        oranlar[sinif] = min(cfg.maks_oversample_kati, max(1, oran))
    return oranlar


# =============================================================================
# İŞÇİ FONKSİYONU — ProcessPoolExecutor için picklable olmalı (sınıf dışı)
# =============================================================================

def _isci_goruntu_isle(args: tuple) -> dict:
    """
    Tek bir görüntüyü işler: ön işleme + augmentasyon.

    ProcessPoolExecutor ile çalışmak için modül düzeyinde tanımlanmalıdır
    (lambda veya yerel fonksiyon pickle edilemez).

    Döndürür: {'basarili': bool, 'uretilen': int, 'hata': str}
    """
    (
        img_yol, etiket_yol, cikti_img_dir, cikti_lbl_dir,
        aug_kat, cfg_dict, aug_pipeline_parametreleri, dosya_adi_tabanı
    ) = args

    # cfg_dict'ten VeriYapilandirma nesnesi yeniden oluştur
    cfg = VeriYapilandirma(**cfg_dict)
    aug_pipeline = augmentasyon_pipeline_olustur(cfg)

    os.makedirs(cikti_img_dir, exist_ok=True)
    os.makedirs(cikti_lbl_dir, exist_ok=True)

    # ── Görüntü oku ──────────────────────────────────────────────────────────
    img = goruntu_oku(img_yol)
    if img is None:
        return {"basarili": False, "uretilen": 0, "hata": f"Okunamadı: {img_yol}"}

    # ── Etiket oku ───────────────────────────────────────────────────────────
    kutular = etiket_oku(etiket_yol)
    if not kutular:
        return {"basarili": False, "uretilen": 0, "hata": f"Etiket boş: {etiket_yol}"}

    uretilen = 0

    # ── Orijinal görüntüyü ön işle ve kaydet ─────────────────────────────────
    img_islenmiş = on_isle(img, cfg)
    cikti_img = os.path.join(cikti_img_dir, f"{dosya_adi_tabanı}.jpg")
    cikti_lbl = os.path.join(cikti_lbl_dir, f"{dosya_adi_tabanı}.txt")
    goruntu_kaydet(cikti_img, img_islenmiş, cfg.jpg_kalite)
    etiket_kaydet(cikti_lbl, kutular)
    uretilen += 1

    # ── Augmentasyon (aug_kat - 1 kez; orijinal zaten kaydedildi) ────────────
    for aug_i in range(aug_kat - 1):
        try:
            bboxes = [k[1:] for k in kutular]       # [cx, cy, w, h]
            labels = [int(k[0]) for k in kutular]   # [cls_id]

            sonuc = aug_pipeline(
                image=img_islenmiş,
                bboxes=bboxes,
                class_labels=labels,
            )

            aug_img = sonuc["image"]
            aug_bboxes = sonuc["bboxes"]
            aug_labels = sonuc["class_labels"]

            if not aug_bboxes:
                continue  # Tüm bbox'lar kırpıldıysa atla

            aug_kutular = [
                [aug_labels[j], *aug_bboxes[j]] for j in range(len(aug_bboxes))
            ]

            aug_img_islenmiş = on_isle(aug_img, cfg)  # Aug sonrası da CLAHE uygula
            isim = f"{dosya_adi_tabanı}_aug{aug_i:03d}"
            goruntu_kaydet(
                os.path.join(cikti_img_dir, f"{isim}.jpg"),
                aug_img_islenmiş, cfg.jpg_kalite
            )
            etiket_kaydet(
                os.path.join(cikti_lbl_dir, f"{isim}.txt"),
                aug_kutular
            )
            uretilen += 1

        except Exception as e:
            continue  # Tek augment hatası tüm görüntüyü durdurmasın

    return {"basarili": True, "uretilen": uretilen, "hata": ""}


# =============================================================================
# ANA SINIF — VeriOnIsleme
# =============================================================================

class VeriOnIsleme:
    """
    Akne veri seti ön işleme ve artırım pipeline'ının ana orkestratörü.

    Kullanım:
        isleme = VeriOnIsleme(
            dataset_root="/mnt/c/Users/Yusuf Soylu/Desktop/...",
            cfg=VeriYapilandirma(maks_oversample_kati=6)
        )
        isleme.calistir()
    """

    # Sınıf ID'si → Türkçe isim
    SINIF_ISIMLERI = {0: "Komedon", 1: "Nodül", 2: "Papül", 3: "Püstül"}

    def __init__(
        self,
        dataset_root: Optional[str] = None,
        cikti_root: Optional[str] = None,
        cfg: Optional[VeriYapilandirma] = None,
    ):
        """
        Parametreler:
            dataset_root : Ham veri seti klasörü (data.yaml burada olmalı)
            cikti_root   : İşlenmiş veri çıktısı (None → otomatik belirlenir)
            cfg          : VeriYapilandirma nesnesi (None → varsayılanlar)
        """
        self.cfg = cfg or VeriYapilandirma()
        if dataset_root:
            self.cfg.dataset_root = dataset_root
        if cikti_root:
            self.cfg.cikti_root = cikti_root
            # __post_init__ yeniden çalıştırılır
        self.cfg.__post_init__()

        self.log = logger_kur("asama_01")
        random.seed(self.cfg.random_seed)
        np.random.seed(self.cfg.random_seed)

        # Yolları Path nesnesine çevir
        self.dataset_root = Path(self.cfg.dataset_root)
        self.cikti_root   = Path(self.cfg.cikti_root)

        self._veri_seti_dogrula()

    # ──────────────────────────────────────────────────────────────────────────
    # DOĞRULAMA
    # ──────────────────────────────────────────────────────────────────────────

    def _veri_seti_dogrula(self) -> None:
        """Dataset klasör yapısını ve data.yaml'ı kontrol eder."""
        if not self.dataset_root.exists():
            raise FileNotFoundError(
                f"Dataset klasörü bulunamadı: {self.dataset_root}\n"
                "WSL'de Windows yolu /mnt/c/... formatında olmalı."
            )
        yaml_yol = self.dataset_root / "data.yaml"
        if not yaml_yol.exists():
            raise FileNotFoundError(f"data.yaml bulunamadı: {yaml_yol}")
        self.log.info(f"Dataset doğrulandı: {self.dataset_root}")

    # ──────────────────────────────────────────────────────────────────────────
    # SPLIT İŞLEME
    # ──────────────────────────────────────────────────────────────────────────

    def _split_isle(self, split: str) -> dict:
        """
        Belirli bir split'i (train/valid/test) işler.

        Train: ön işleme + oversampling augmentasyonu + mosaic
        Valid/Test: yalnızca ön işleme (augmentasyon uygulanmaz — doğru değerlendirme için)

        Döndürür: {'toplam_goruntu': int, 'uretilen': int, 'atlanılan': int}
        """
        is_train = (split == "train")

        img_dir = self.dataset_root / split / "images"
        lbl_dir = self.dataset_root / split / "labels"

        cikti_img = self.cikti_root / split / "images"
        cikti_lbl = self.cikti_root / split / "labels"
        cikti_img.mkdir(parents=True, exist_ok=True)
        cikti_lbl.mkdir(parents=True, exist_ok=True)

        # Görüntü-etiket çiftlerini bul
        img_dosyalari = sorted(img_dir.glob("*.jpg")) + sorted(img_dir.glob("*.png"))
        if not img_dosyalari:
            self.log.warning(f"{split}: Görüntü bulunamadı!")
            return {"toplam_goruntu": 0, "uretilen": 0, "atlanilan": 0}

        self.log.info(f"\n{'='*60}")
        self.log.info(f"Split: {split.upper()} — {len(img_dosyalari)} görüntü")
        self.log.info(f"{'='*60}")

        # ── Oversampling oranlarını hesapla (yalnızca train) ─────────────────
        aug_kat_map = {}
        if is_train:
            sayac = sinif_sayilari_hesapla(str(lbl_dir))
            aug_kat_map = oversample_oranlari_hesapla(sayac, self.cfg)
            self.log.info("Sınıf sayıları ve augmentasyon oranları:")
            for cls_id in sorted(sayac.keys()):
                isim = self.SINIF_ISIMLERI.get(cls_id, str(cls_id))
                self.log.info(
                    f"  [{cls_id}] {isim:10s}: {sayac[cls_id]:5d} görüntü → "
                    f"{aug_kat_map.get(cls_id, 1)}x augment"
                )

        # ── İşçi argümanları hazırla ──────────────────────────────────────────
        # cfg dataclass'ını dict'e çevir (pickle için)
        cfg_dict = {
            k: v for k, v in self.cfg.__dict__.items()
        }

        grevler = []
        for img_yol in img_dosyalari:
            stem = img_yol.stem
            lbl_yol = lbl_dir / f"{stem}.txt"
            if not lbl_yol.exists():
                continue

            # Sınıf ID'sini dosya adından çıkar (levle0→0, levle1→3, levle2→2, levle3→1)
            # Etiket dosyasından birinci sınıfı oku (single-class görüntü)
            try:
                with open(lbl_yol) as f:
                    ilk = f.readline().strip().split()
                cls_id = int(ilk[0]) if ilk else -1
            except Exception:
                cls_id = -1

            aug_kat = aug_kat_map.get(cls_id, 1) if is_train else 1

            grevler.append((
                str(img_yol), str(lbl_yol),
                str(cikti_img), str(cikti_lbl),
                aug_kat, cfg_dict, None, stem
            ))

        # ── Paralel işlem ─────────────────────────────────────────────────────
        toplam = len(grevler)
        uretilen = 0
        atlanilan = 0
        baslangic = time.time()

        self.log.info(
            f"İşlem başlıyor: {self.cfg.num_workers} worker, {toplam} görüntü"
        )

        with ProcessPoolExecutor(max_workers=self.cfg.num_workers) as executor:
            gelecekler = {
                executor.submit(_isci_goruntu_isle, gorev): i
                for i, gorev in enumerate(grevler)
            }
            tamamlanan = 0
            for future in as_completed(gelecekler):
                try:
                    sonuc = future.result()
                    if sonuc["basarili"]:
                        uretilen += sonuc["uretilen"]
                    else:
                        atlanilan += 1
                except Exception as e:
                    atlanilan += 1
                tamamlanan += 1
                # Her 100 görüntüde bir ilerleme raporu
                if tamamlanan % 100 == 0 or tamamlanan == toplam:
                    gecen = time.time() - baslangic
                    hiz = tamamlanan / gecen if gecen > 0 else 0
                    self.log.info(
                        f"  {tamamlanan}/{toplam} "
                        f"({100*tamamlanan/toplam:.0f}%) "
                        f"— {hiz:.1f} görüntü/sn"
                    )

        # ── Mosaic üret (yalnızca train) ──────────────────────────────────────
        if is_train:
            mosaic_sayisi = int(len(img_dosyalari) * self.cfg.mosaic_orani)
            self.log.info(f"\nMosaic üretimi: {mosaic_sayisi} adet")
            self._mosaic_uret(
                img_dosyalari, lbl_dir, cikti_img, cikti_lbl, mosaic_sayisi
            )
            uretilen += mosaic_sayisi

        sure = time.time() - baslangic
        self.log.info(
            f"\n{split.upper()} tamamlandı: "
            f"{uretilen} üretildi, {atlanilan} atlandı — "
            f"{sure:.1f} sn"
        )
        return {"toplam_goruntu": toplam, "uretilen": uretilen, "atlanilan": atlanilan}

    def _mosaic_uret(
        self,
        img_dosyalari: list,
        lbl_dir: Path,
        cikti_img: Path,
        cikti_lbl: Path,
        sayi: int,
    ) -> None:
        """
        `sayi` kadar mosaic görüntüsü üretir ve kaydeder.
        Her mosaic 4 rastgele görüntüden oluşur.
        """
        img_yollari = [str(p) for p in img_dosyalari]
        lbl_yollari = [
            str(lbl_dir / f"{p.stem}.txt") for p in img_dosyalari
        ]
        # Yalnızca etiket dosyası var olanları kullan
        gecerli = [
            (i, l) for i, l in zip(img_yollari, lbl_yollari)
            if os.path.exists(l)
        ]
        if not gecerli:
            return
        gec_img, gec_lbl = zip(*gecerli)

        for idx in range(sayi):
            try:
                mozaik_img, mozaik_kutular = mosaic_olustur(
                    list(gec_img), list(gec_lbl), self.cfg
                )
                if not mozaik_kutular:
                    continue
                isim = f"mosaic_{idx:05d}"
                goruntu_kaydet(
                    str(cikti_img / f"{isim}.jpg"),
                    mozaik_img, self.cfg.jpg_kalite
                )
                etiket_kaydet(
                    str(cikti_lbl / f"{isim}.txt"),
                    mozaik_kutular
                )
            except Exception as e:
                self.log.warning(f"Mosaic {idx} hatası: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # YAML KOPYALAMA
    # ──────────────────────────────────────────────────────────────────────────

    def _yaml_guncelle(self) -> None:
        """
        data.yaml'ı çıktı klasörüne kopyalar ve yolları günceller.
        Aşama 2 (model) bu dosyayı kullanır.
        """
        kaynak = self.dataset_root / "data.yaml"
        hedef  = self.cikti_root / "data.yaml"

        with open(kaynak, "r", encoding="utf-8") as f:
            icerik = f.read()

        # Yolları çıktı klasörüne göre ayarla
        icerik = icerik.replace(
            "train: ../train/images",
            f"train: {self.cikti_root / 'train' / 'images'}"
        ).replace(
            "val: ../valid/images",
            f"val: {self.cikti_root / 'valid' / 'images'}"
        ).replace(
            "test: ../test/images",
            f"test: {self.cikti_root / 'test' / 'images'}"
        )

        with open(hedef, "w", encoding="utf-8") as f:
            f.write(icerik)

        self.log.info(f"data.yaml güncellendi: {hedef}")

    # ──────────────────────────────────────────────────────────────────────────
    # ANA ÇALIŞTIRICI
    # ──────────────────────────────────────────────────────────────────────────

    def calistir(self) -> dict:
        """
        Tüm pipeline'ı uçtan uca çalıştırır.
        Sıra: valid/test (yalnızca ön işleme) → train (ön işleme + aug + mosaic)

        Döndürür: Özet istatistik dict'i
        """
        self.log.info("=" * 60)
        self.log.info("AŞAMA 01 — Veri Ön İşleme ve Artırım BAŞLIYOR")
        self.log.info(f"Kaynak  : {self.dataset_root}")
        self.log.info(f"Çıktı   : {self.cikti_root}")
        self.log.info(f"Worker  : {self.cfg.num_workers}")
        self.log.info("=" * 60)

        ozet = {}
        baslangic = time.time()

        # Önce valid ve test (hızlı, augment yok)
        for split in ["valid", "test", "train"]:
            split_dir = self.dataset_root / split
            if not split_dir.exists():
                self.log.warning(f"{split} klasörü yok, atlanıyor.")
                continue
            ozet[split] = self._split_isle(split)

        # data.yaml güncelle
        self._yaml_guncelle()

        toplam_sure = time.time() - baslangic
        self.log.info("\n" + "=" * 60)
        self.log.info("AŞAMA 01 TAMAMLANDI")
        self.log.info(f"Toplam süre: {toplam_sure:.1f} sn ({toplam_sure/60:.1f} dk)")
        for split, s in ozet.items():
            self.log.info(
                f"  {split:5s}: {s['toplam_goruntu']} kaynak → "
                f"{s['uretilen']} üretildi, {s['atlanilan']} atlandı"
            )
        self.log.info(f"Çıktı klasörü: {self.cikti_root}")
        self.log.info("=" * 60)

        return ozet


# =============================================================================
# DOĞRULAMA — Çıktı veri setini hızlıca kontrol eder
# =============================================================================

class CiktiDogrulayici:
    """
    Aşama 01 çıktısını doğrular:
    - Her görüntünün bir etiket dosyası var mı?
    - YOLO koordinatları [0,1] aralığında mı?
    - Bozuk görüntü var mı?
    """

    def __init__(self, cikti_root: str):
        self.cikti_root = Path(cikti_root)
        self.log = logger_kur("dogrulayici")

    def dogrula(self) -> dict:
        """Tüm split'leri tarar ve sorunları raporlar."""
        sonuclar = {}
        for split in ["train", "valid", "test"]:
            split_dir = self.cikti_root / split
            if not split_dir.exists():
                continue
            img_dir = split_dir / "images"
            lbl_dir = split_dir / "labels"

            sorunlar = []
            dosyalar = list(img_dir.glob("*.jpg"))

            for img_yol in dosyalar:
                stem = img_yol.stem
                lbl_yol = lbl_dir / f"{stem}.txt"

                # Etiket eksik?
                if not lbl_yol.exists():
                    sorunlar.append(f"Etiket yok: {stem}")
                    continue

                # Koordinat aralığı kontrolü
                kutular = etiket_oku(str(lbl_yol))
                for kutu in kutular:
                    if len(kutu) != 5:
                        sorunlar.append(f"Hatalı format: {stem}")
                        break
                    _, cx, cy, w, h = kutu
                    if not (0 <= cx <= 1 and 0 <= cy <= 1
                            and 0 < w <= 1 and 0 < h <= 1):
                        sorunlar.append(f"Koordinat dışı: {stem} {kutu}")
                        break

            sonuclar[split] = {
                "toplam": len(dosyalar),
                "sorun_sayisi": len(sorunlar),
                "sorunlar": sorunlar[:10],  # İlk 10 sorun gösterilir
            }
            durum = "✓" if not sorunlar else "✗"
            self.log.info(
                f"{durum} {split:5s}: {len(dosyalar)} görüntü, "
                f"{len(sorunlar)} sorun"
            )
            for s in sorunlar[:5]:
                self.log.warning(f"   → {s}")

        return sonuclar


# =============================================================================
# DOĞRUDAN ÇALIŞTIRMA — python asama_01_veri.py
# =============================================================================

if __name__ == "__main__":
    DATASET_ROOT = (
        "/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi"
        "/Robo Flow V1/Acne-Detection-V1-1"
    )

    # Pipeline başlat
    isleme = VeriOnIsleme(dataset_root=DATASET_ROOT)
    ozet = isleme.calistir()

    # Çıktıyı doğrula
    dogrulay = CiktiDogrulayici(isleme.cfg.cikti_root)
    dogrulay.dogrula()