from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse, Response
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from pathlib import Path
import logging

router = APIRouter(prefix="/quality")
logger = logging.getLogger("dermai-ai.quality")

# ── MediaPipe Face Landmarker (Tasks API — mediapipe 0.10+) ───────────────────
_MODEL_PATH = Path(__file__).parent.parent / "face_landmarker.task"

base_options = mp_python.BaseOptions(model_asset_path=str(_MODEL_PATH))
_landmarker_options = mp_vision.FaceLandmarkerOptions(
    base_options=base_options,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=True,
    num_faces=1,
    min_face_detection_confidence=0.5,
    min_face_presence_confidence=0.5,
)
face_landmarker = mp_vision.FaceLandmarker.create_from_options(_landmarker_options)

# Eye landmark indices (same as before — 478-point mesh)
LEFT_EYE  = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]


def _detect(img_bgr: np.ndarray):
    """Run face landmarker and return result."""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    return face_landmarker.detect(mp_image)


@router.post("/check-angle")
async def check_angle(file: UploadFile = File(...), target_angle: str = Form(...)):
    """
    Checks if the uploaded face image matches the target_angle ('front', 'right', 'left').
    Returns { "valid": bool, "detected_angle": str, "message": str }
    """
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")

        result = _detect(img)

        if not result.face_landmarks:
            return JSONResponse({
                "valid": False,
                "detected_angle": "unknown",
                "message": "Yüz algılanamadı. Lütfen daha aydınlık ve net bir fotoğraf çekin."
            })

        landmarks = result.face_landmarks[0]

        # Nose tip = landmark 1, right tragion = 234, left tragion = 454
        nose      = landmarks[1]
        right_ear = landmarks[234]
        left_ear  = landmarks[454]

        dist_left_side  = nose.x - right_ear.x
        dist_right_side = left_ear.x - nose.x

        ratio = dist_left_side / (dist_right_side + 1e-6)

        if ratio < 0.6:
            detected_angle = "right"
        elif ratio > 1.6:
            detected_angle = "left"
        else:
            detected_angle = "front"

        valid = (detected_angle == target_angle)
        return JSONResponse({
            "valid": valid,
            "detected_angle": detected_angle,
            "message": "Açı uygun." if valid else f"Beklenen: {target_angle}, Algılanan: {detected_angle}"
        })

    except Exception as e:
        logger.error(f"Angle check failed: {e}")
        return JSONResponse({
            "valid": False,
            "detected_angle": "error",
            "message": "Fotoğraf analiz edilemedi."
        })


@router.post("/mask-eyes")
async def mask_eyes(file: UploadFile = File(...)):
    """
    Detects eyes and draws black rectangles over them for privacy.
    Returns the processed image bytes.
    """
    contents = await file.read()
    try:
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")

        result = _detect(img)

        if result.face_landmarks:
            landmarks = result.face_landmarks[0]
            h, w, _ = img.shape

            for eye_indices in [LEFT_EYE, RIGHT_EYE]:
                xs = [int(landmarks[idx].x * w) for idx in eye_indices]
                ys = [int(landmarks[idx].y * h) for idx in eye_indices]
                min_x = max(0, min(xs) - 10)
                max_x = min(w, max(xs) + 10)
                min_y = max(0, min(ys) - 10)
                max_y = min(h, max(ys) + 10)
                cv2.rectangle(img, (min_x, min_y), (max_x, max_y), (0, 0, 0), -1)

        _, encoded_img = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return Response(content=encoded_img.tobytes(), media_type="image/jpeg")

    except Exception as e:
        logger.error(f"Eye masking failed: {e}")
        return Response(content=contents, media_type=file.content_type)
