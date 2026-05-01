"""
=============================================================================
AŞAMA 01 v2 — Veri Ön İşleme ve Artırım (asama_01_veri_v2.py)
=============================================================================
Proje   : YOLOv11 Tabanlı Akne Tespit ve Şiddet Derecelendirme Sistemi
Versiyon: 2.0

v1'den Farklar:
    - Statik mozaik üretimi KALDIRILDI
      Sebep: YOLO eğitimde zaten mosaic=1.0 yapıyor. Statik mozaik +
      dinamik mozaik = görüntüler 1/16 boyutuna iniyor, komedonlar
      piksel gürültüsüne dönüşüyor. Box loss düşemiyordu.
    - Sadece CLAHE + median filter + albumentations augmentasyon korundu.
    - Oversampling mantığı korundu (komedon 7.6x az → daha fazla augment).

Yapılan İşlemler:
    1. Medyan filtresi (gürültü azaltma)
    2. Dinamik CLAHE (koyu cilt: V<0.4 → clip_limit artırılır)
    3. Albumentations augmentasyon (sadece train):
       - Rotasyon ±15°, Shear ±10°
       - HSV Saturation/Value ±%15
       - Blur max 2.5px, Gaussian Noise max %1
       - Horizontal flip p=0.5
    4. Sınıf bazlı oversampling (dengesizlik oranına göre otomatik)
       Formül: max(1, round(sqrt(max_count / class_count)))

Kullanım:
    from asama_01_veri_v2 import VeriOnIsleyici
    isleyici = VeriOnIsleyici()
    isleyici.calistir()
=============================================================================
"""

import os
import cv2
import yaml
import shutil
import logging
import warnings
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import time

warnings.filterwarnings("ignore")

try:
    import albumentations as A
    _ALB_OK = True
except ImportError:
    _ALB_OK = False
    warnings.warn("albumentations yüklü değil. pip install albumentations")


# =============================================================================
# YAPILANDIRMA
# =============================================================================

@dataclass
class VeriYapilandirma:
    """Aşama 01 v2 tüm parametreleri."""

    # ── Yollar ────────────────────────────────────────────────────────────────
    roboflow_root: str = (
        "/mnt/c/Users/Yusuf Soylu/Desktop/Dermatoloji Projesi/Robo Flow V1"
    )
    kaynak_veri:  str = ""
    cikti_klasor: str = ""

    # ── İşlem ─────────────────────────────────────────────────────────────────
    num_workers: int = 0      # 0 → otomatik
    jpg_kalite:  int = 95

    # ── CLAHE ─────────────────────────────────────────────────────────────────
    clahe_clip_normal: float = 2.0
    clahe_clip_koyu:   float = 4.0
    koyu_cilt_esik:    float = 0.40  # HSV V < bu değer → koyu cilt
    clahe_tile:        int   = 8

    # ── Medyan ────────────────────────────────────────────────────────────────
    medyan_kernel: int = 3

    # ── Augmentasyon ─────────────────────────────────────────────────────────
    aug_rotasyon: float = 15.0
    aug_shear:    float = 10.0
    aug_hsv_s:    float = 0.15
    aug_hsv_v:    float = 0.15
    aug_blur:     float = 2.5
    aug_noise:    float = 0.01

    # ── Sınıf bilgisi ─────────────────────────────────────────────────────────
    sinif_isimleri: dict = field(default_factory=lambda: {
        0: "comedone", 1: "nodule", 2: "papule", 3: "pustule"
    })

    def __post_init__(self):
        root = Path(self.roboflow_root)
        if not self.kaynak_veri:
            self.kaynak_veri = str(root / "Acne-Detection-V1-1")
        if not self.cikti_klasor:
            self.cikti_klasor = str(root / "islenmiş_veri")
        if not self.num_workers:
            # Intel Ultra 9: 8P + 16E core → 20 worker optimal
            self.num_workers = min(20, max(4, int(multiprocessing.cpu_count() * 0.8)))


# =============================================================================
# YARDIMCI FONKSİYONLAR
# =============================================================================

def logger_kur(isim: str = "asama_01_v2") -> logging.Logger:
    log = logging.getLogger(isim)
    log.setLevel(logging.INFO)
    if log.handlers:
        log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    return log


def sinif_sayilarini_hesapla(label_klasor: Path) -> dict:
    """Label .txt dosyalarından sınıf annotation sayılarını hesaplar."""
    sayilar = {}
    for lbl in label_klasor.glob("*.txt"):
        try:
            with open(lbl) as f:
                for satir in f:
                    s = satir.strip()
                    if s:
                        cls_id = int(s.split()[0])
                        sayilar[cls_id] = sayilar.get(cls_id, 0) + 1
        except Exception:
            pass
    return sayilar


def oversampling_oranlari_hesapla(sinif_sayilari: dict) -> dict:
    """
    Sınıf dengesizliğine göre augmentasyon katı hesaplar.
    Formül: max(1, round(sqrt(max_count / class_count)))
    Karekök → agresif değil, dengeli artış.
    """
    if not sinif_sayilari:
        return {}
    max_c = max(sinif_sayilari.values())
    return {
        cls_id: max(1, round(np.sqrt(max_c / cnt)))
        for cls_id, cnt in sinif_sayilari.items()
    }


def goruntu_sinifini_bul(label_yolu: Path) -> Optional[int]:
    """Label dosyasından baskın sınıf id'sini döndürür."""
    sayac = {}
    try:
        with open(label_yolu) as f:
            for satir in f:
                s = satir.strip()
                if s:
                    cls_id = int(s.split()[0])
                    sayac[cls_id] = sayac.get(cls_id, 0) + 1
        if sayac:
            return max(sayac, key=sayac.get)
    except Exception:
        pass
    return None


# =============================================================================
# ÖN İŞLEME
# =============================================================================

def on_isle(
    goruntu: np.ndarray,
    clip_normal: float = 2.0,
    clip_koyu: float = 4.0,
    koyu_esik: float = 0.40,
    tile: int = 8,
    medyan_k: int = 3,
) -> np.ndarray:
    """
    Medyan filtresi + dinamik CLAHE uygular.

    Neden LAB uzayı:
        CLAHE L (parlaklık) kanalına uygulanır.
        HSV V kanalına uygulamak renk bozukluğuna yol açar.
        LAB daha kararlı sonuç verir.
    """
    # 1. Medyan filtresi — tuz-biber gürültüsü, kamera artefaktları
    goruntu = cv2.medianBlur(goruntu, medyan_k)

    # 2. Koyu cilt tespiti — HSV V kanalı
    hsv = cv2.cvtColor(goruntu, cv2.COLOR_BGR2HSV)
    v_ort = hsv[:, :, 2].mean() / 255.0
    clip = clip_koyu if v_ort < koyu_esik else clip_normal

    # 3. LAB → L kanalına CLAHE
    lab = cv2.cvtColor(goruntu, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tile, tile))
    l = clahe.apply(l)

    # 4. BGR'ye döndür
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


# =============================================================================
# ALBUMENTATIONS PIPELINE
# =============================================================================

def aug_pipeline_olustur(cfg: VeriYapilandirma):
    """
    Train seti augmentasyon pipeline'ı.

    bbox_params kritik:
    - format='yolo' → koordinatlar otomatik dönüşür
    - min_visibility=0.3 → çok küçülen bbox'lar atılır
    - clip=True → sınır dışını kırp
    """
    if not _ALB_OK:
        return None

    return A.Compose(
        [
            A.Rotate(
                limit=cfg.aug_rotasyon,
                border_mode=cv2.BORDER_REFLECT_101,
                p=0.5,
            ),
            A.Affine(shear=(-cfg.aug_shear, cfg.aug_shear), p=0.3),
            A.HueSaturationValue(
                hue_shift_limit=10,
                sat_shift_limit=int(cfg.aug_hsv_s * 100),
                val_shift_limit=int(cfg.aug_hsv_v * 100),
                p=0.5,
            ),
            A.Blur(blur_limit=int(cfg.aug_blur * 2), p=0.2),
            A.GaussNoise(std_range=(0, cfg.aug_noise), p=0.2),
            A.HorizontalFlip(p=0.5),
        ],
        bbox_params=A.BboxParams(
            format="yolo",
            label_fields=["class_labels"],
            min_visibility=0.3,
            clip=True,
        ),
    )


# =============================================================================
# WORKER — modül seviyesinde (multiprocessing pickle uyumu)
# =============================================================================

def _worker(args: tuple) -> tuple[bool, str]:
    """
    Tek görüntüyü işleyen worker.
    Modül seviyesinde tanımlı olmalı — ProcessPoolExecutor pickle eder.
    """
    (
        img_yolu_str, label_yolu_str,
        cikti_img_str, cikti_lbl_str,
        aug_sayisi,
        clip_normal, clip_koyu, koyu_esik, tile, medyan_k,
        jpg_kalite,
        aug_rotasyon, aug_shear, aug_hsv_s, aug_hsv_v, aug_blur, aug_noise,
    ) = args

    try:
        img_yolu    = Path(img_yolu_str)
        label_yolu  = Path(label_yolu_str)
        cikti_img   = Path(cikti_img_str)
        cikti_lbl   = Path(cikti_lbl_str)

        # Görüntü oku
        goruntu = cv2.imread(str(img_yolu))
        if goruntu is None:
            return False, f"Okunamadı: {img_yolu}"

        # Label oku
        with open(label_yolu) as f:
            label_satirlar = f.readlines()

        # Ön işleme
        islenmis = on_isle(goruntu, clip_normal, clip_koyu, koyu_esik, tile, medyan_k)

        # Orijinal kaydet
        isim = img_yolu.stem
        cv2.imwrite(
            str(cikti_img / f"{isim}.jpg"),
            islenmis,
            [cv2.IMWRITE_JPEG_QUALITY, jpg_kalite],
        )
        shutil.copy2(str(label_yolu), str(cikti_lbl / f"{isim}.txt"))

        # Augmentasyon
        if aug_sayisi > 0 and _ALB_OK:
            bboxes = []
            class_labels = []
            for satir in label_satirlar:
                prc = satir.strip().split()
                if len(prc) == 5:
                    cls_id = int(prc[0])
                    cx, cy, w, h = map(float, prc[1:])
                    if 0 < w <= 1 and 0 < h <= 1:
                        bboxes.append([cx, cy, w, h])
                        class_labels.append(cls_id)

            if bboxes:
                # Worker içinde minimal cfg nesnesi
                class _Cfg:
                    pass
                cfg = _Cfg()
                cfg.aug_rotasyon = aug_rotasyon
                cfg.aug_shear    = aug_shear
                cfg.aug_hsv_s    = aug_hsv_s
                cfg.aug_hsv_v    = aug_hsv_v
                cfg.aug_blur     = aug_blur
                cfg.aug_noise    = aug_noise

                pipeline = aug_pipeline_olustur(cfg)

                for idx in range(aug_sayisi):
                    try:
                        sonuc = pipeline(
                            image=islenmis,
                            bboxes=bboxes,
                            class_labels=class_labels,
                        )
                        aug_img    = sonuc["image"]
                        aug_bboxes = sonuc["bboxes"]
                        aug_lbls   = sonuc["class_labels"]

                        if not aug_bboxes:
                            continue

                        aug_isim = f"{isim}_aug{idx}"
                        cv2.imwrite(
                            str(cikti_img / f"{aug_isim}.jpg"),
                            aug_img,
                            [cv2.IMWRITE_JPEG_QUALITY, jpg_kalite],
                        )
                        with open(cikti_lbl / f"{aug_isim}.txt", "w") as f:
                            for (cx, cy, w, h), cls_id in zip(aug_bboxes, aug_lbls):
                                f.write(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

                    except Exception:
                        continue

        return True, ""

    except Exception as e:
        return False, str(e)


# =============================================================================
# ANA SINIF
# =============================================================================

class VeriOnIsleyici:
    """
    Aşama 01 v2 — Veri ön işleme orkestratörü.

    Adımlar:
        1. Kaynak doğrulama
        2. Çıktı klasörü sıfırla (eski islenmiş_veri silinir)
        3. Valid + test: sadece ön işleme
        4. Train: ön işleme + sınıf bazlı augmentasyon
        5. data.yaml yaz
        6. Doğrulama
    """

    def __init__(self, cfg: Optional[VeriYapilandirma] = None):
        self.cfg = cfg or VeriYapilandirma()
        self.log = logger_kur("asama_01_v2")

    def _dogrula_kaynak(self) -> None:
        if not Path(self.cfg.kaynak_veri).exists():
            raise FileNotFoundError(f"Kaynak bulunamadı: {self.cfg.kaynak_veri}")
        self.log.info(f"Dataset doğrulandı: {self.cfg.kaynak_veri}")

    def _hazirla_cikti(self) -> None:
        cikti = Path(self.cfg.cikti_klasor)
        if cikti.exists():
            self.log.info(f"Eski çıktı siliniyor: {cikti}")
            shutil.rmtree(str(cikti))
        for split in ["train", "valid", "test"]:
            (cikti / split / "images").mkdir(parents=True, exist_ok=True)
            (cikti / split / "labels").mkdir(parents=True, exist_ok=True)
        self.log.info(f"Çıktı hazırlandı: {cikti}")

    def _oversampling_hesapla(self) -> dict:
        lbl_dir = Path(self.cfg.kaynak_veri) / "train" / "labels"
        sayilar  = sinif_sayilarini_hesapla(lbl_dir)
        oranlar  = oversampling_oranlari_hesapla(sayilar)

        self.log.info("Sınıf sayıları ve augmentasyon oranları:")
        for cls_id in sorted(oranlar):
            isim = self.cfg.sinif_isimleri.get(cls_id, str(cls_id))
            self.log.info(
                f"  [{cls_id}] {isim:10s}: "
                f"{sayilar.get(cls_id, 0):5d} annotation → "
                f"{oranlar[cls_id]}x augment"
            )
        return oranlar

    def _split_isle(
        self,
        split: str,
        oversampling: dict,
        augment: bool,
    ) -> tuple[int, int]:
        """Bir split'i parallel işler. (üretilen, atlanan) döndürür."""
        kaynak = Path(self.cfg.kaynak_veri) / split
        cikti  = Path(self.cfg.cikti_klasor) / split

        img_dir = kaynak / "images"
        lbl_dir = kaynak / "labels"

        gorseller = (
            list(img_dir.glob("*.jpg")) +
            list(img_dir.glob("*.jpeg")) +
            list(img_dir.glob("*.png"))
        ) if img_dir.exists() else []

        if not gorseller:
            self.log.warning(f"{split}: görüntü bulunamadı")
            return 0, 0

        self.log.info(f"\n{'='*60}")
        self.log.info(f"Split: {split.upper()} — {len(gorseller)} görüntü")
        self.log.info("=" * 60)

        # Worker argümanlarını hazırla
        args_listesi = []
        for img_yolu in gorseller:
            lbl_yolu = lbl_dir / (img_yolu.stem + ".txt")
            if not lbl_yolu.exists():
                continue

            if augment:
                cls_id    = goruntu_sinifini_bul(lbl_yolu)
                aug_sayisi = max(0, oversampling.get(cls_id, 1) - 1)
            else:
                aug_sayisi = 0

            args_listesi.append((
                str(img_yolu), str(lbl_yolu),
                str(cikti / "images"), str(cikti / "labels"),
                aug_sayisi,
                self.cfg.clahe_clip_normal,
                self.cfg.clahe_clip_koyu,
                self.cfg.koyu_cilt_esik,
                self.cfg.clahe_tile,
                self.cfg.medyan_kernel,
                self.cfg.jpg_kalite,
                self.cfg.aug_rotasyon,
                self.cfg.aug_shear,
                self.cfg.aug_hsv_s,
                self.cfg.aug_hsv_v,
                self.cfg.aug_blur,
                self.cfg.aug_noise,
            ))

        # Parallel işleme
        uretilen = atlanan = 0
        baslangic = time.time()
        son_rapor = 0

        self.log.info(
            f"İşlem başlıyor: {self.cfg.num_workers} worker, "
            f"{len(args_listesi)} görüntü"
        )

        with ProcessPoolExecutor(max_workers=self.cfg.num_workers) as ex:
            futures = {ex.submit(_worker, a): i for i, a in enumerate(args_listesi)}
            tamam = 0
            toplam = len(futures)

            for fut in as_completed(futures):
                ok, _ = fut.result()
                tamam += 1
                if ok:
                    uretilen += 1
                else:
                    atlanan += 1

                yuzde = int(tamam / toplam * 100)
                if yuzde >= son_rapor + 10 or tamam == toplam:
                    gecen = time.time() - baslangic
                    hiz = tamam / gecen if gecen > 0 else 0
                    self.log.info(
                        f"  {tamam}/{toplam} (%{yuzde}) — {hiz:.1f} görüntü/sn"
                    )
                    son_rapor = yuzde

        sure = time.time() - baslangic
        self.log.info(
            f"\n{split.upper()} tamamlandı: "
            f"{uretilen} üretildi, {atlanan} atlandı — {sure:.1f} sn"
        )
        return uretilen, atlanan

    def _data_yaml_yaz(self) -> None:
        cikti = Path(self.cfg.cikti_klasor)
        icerik = {
            "path":  str(cikti),
            "train": "train/images",
            "val":   "valid/images",
            "test":  "test/images",
            "nc":    len(self.cfg.sinif_isimleri),
            "names": list(self.cfg.sinif_isimleri.values()),
        }
        yol = cikti / "data.yaml"
        with open(yol, "w", encoding="utf-8") as f:
            yaml.dump(icerik, f, allow_unicode=True, default_flow_style=False)
        self.log.info(f"data.yaml yazıldı: {yol}")

    def _readme_yaz(self, stats: dict) -> None:
        icerik = f"""# Aşama 01 v2 — İşlenmiş Veri

## v1 → v2 Değişiklik
- Statik mozaik KALDIRILDI (YOLO eğitimde mosaic=1.0 yapacak)
- CLAHE + median filter + albumentasyon augmentasyon korundu

## Üretilen
| Split | Kaynak | Üretilen |
|-------|--------|----------|
| Train | {stats.get('train_k', 0)} | {stats.get('train_u', 0)} |
| Valid | {stats.get('valid_k', 0)} | {stats.get('valid_u', 0)} |
| Test  | {stats.get('test_k',  0)} | {stats.get('test_u',  0)} |

## Sonraki
asama_03_egitim_dongusu_v2.py
"""
        with open(Path(self.cfg.cikti_klasor) / "README.md", "w", encoding="utf-8") as f:
            f.write(icerik)

    def _dogrula_cikti(self) -> None:
        cikti = Path(self.cfg.cikti_klasor)
        for split in ["train", "valid", "test"]:
            img_dir = cikti / split / "images"
            lbl_dir = cikti / split / "labels"
            if not img_dir.exists():
                continue
            n_img = len(list(img_dir.glob("*.jpg")))
            n_lbl = len(list(lbl_dir.glob("*.txt")))
            if n_img == n_lbl:
                self.log.info(f"✓ {split}: {n_img} görüntü, 0 sorun")
            else:
                self.log.warning(f"⚠ {split}: {n_img} görüntü ≠ {n_lbl} label")

    def calistir(self) -> None:
        self.log.info("=" * 60)
        self.log.info("AŞAMA 01 v2 — Veri Ön İşleme BAŞLIYOR")
        self.log.info(f"Kaynak  : {self.cfg.kaynak_veri}")
        self.log.info(f"Çıktı   : {self.cfg.cikti_klasor}")
        self.log.info(f"Worker  : {self.cfg.num_workers}")
        self.log.info(f"Mozaik  : KAPALI (YOLO eğitimde yapacak)")
        self.log.info("=" * 60)

        t0 = time.time()

        self._dogrula_kaynak()
        self._hazirla_cikti()
        oversampling = self._oversampling_hesapla()

        stats = {}

        # Valid + Test: sadece ön işleme
        for split in ["valid", "test"]:
            u, _ = self._split_isle(split, oversampling, augment=False)
            k_dir = Path(self.cfg.kaynak_veri) / split / "images"
            k = len(list(k_dir.glob("*.jpg")) + list(k_dir.glob("*.png"))) if k_dir.exists() else 0
            stats[f"{split}_k"] = k
            stats[f"{split}_u"] = u

        # Train: ön işleme + augmentasyon
        u, _ = self._split_isle("train", oversampling, augment=True)
        k_dir = Path(self.cfg.kaynak_veri) / "train" / "images"
        k = len(list(k_dir.glob("*.jpg")) + list(k_dir.glob("*.png"))) if k_dir.exists() else 0
        stats["train_k"] = k
        stats["train_u"] = u

        self._data_yaml_yaz()
        self._readme_yaz(stats)
        self._dogrula_cikti()

        sure = time.time() - t0
        self.log.info("\n" + "=" * 60)
        self.log.info("AŞAMA 01 v2 TAMAMLANDI")
        self.log.info(f"Toplam süre: {sure:.1f} sn ({sure/60:.1f} dk)")
        self.log.info(f"  valid: {stats['valid_k']} → {stats['valid_u']}")
        self.log.info(f"  test : {stats['test_k']}  → {stats['test_u']}")
        self.log.info(f"  train: {stats['train_k']} → {stats['train_u']}")
        self.log.info(f"Çıktı: {self.cfg.cikti_klasor}")
        self.log.info("=" * 60)


# =============================================================================
# DOĞRUDAN ÇALIŞTIRMA
# =============================================================================

if __name__ == "__main__":
    isleyici = VeriOnIsleyici()
    isleyici.calistir()