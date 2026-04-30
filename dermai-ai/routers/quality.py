from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, Response
import cv2
import numpy as np
import mediapipe as mp
import logging

router = APIRouter(prefix="/quality")
logger = logging.getLogger("dermai-ai.quality")

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=True,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5
)

# Eye landmarks indices in MediaPipe Face Mesh
LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]

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
            
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(img_rgb)
        
        if not results.multi_face_landmarks:
            return JSONResponse({
                "valid": False, 
                "detected_angle": "unknown", 
                "message": "Yüz algılanamadı. Lütfen daha aydınlık ve net bir fotoğraf çekin."
            })
            
        landmarks = results.multi_face_landmarks[0].landmark
        
        # Landmark 1: Nose tip
        # Landmark 234: Right tragion (person's right ear, left side of image)
        # Landmark 454: Left tragion (person's left ear, right side of image)
        nose = landmarks[1]
        right_ear = landmarks[234] 
        left_ear = landmarks[454]
        
        # Calculate horizontal distances
        dist_left_side = nose.x - right_ear.x  # Distance from right ear to nose (left side of image)
        dist_right_side = left_ear.x - nose.x  # Distance from nose to left ear (right side of image)
        
        # Simple ratio to determine angle
        # If ratio is close to 1, it's front.
        # If dist_left_side is much smaller, nose is pointing left -> person is showing RIGHT cheek.
        # If dist_right_side is much smaller, nose is pointing right -> person is showing LEFT cheek.
        
        ratio = dist_left_side / (dist_right_side + 1e-6)
        
        detected_angle = "front"
        if ratio < 0.6:
            detected_angle = "right"  # Right cheek visible
        elif ratio > 1.6:
            detected_angle = "left"   # Left cheek visible
            
        valid = (detected_angle == target_angle)
        
        return JSONResponse({
            "valid": valid,
            "detected_angle": detected_angle,
            "message": valid and "Açı uygun." or f"Beklenen: {target_angle}, Algılanan: {detected_angle}"
        })
        
    except Exception as e:
        logger.error(f"Angle check failed: {e}")
        # In case of error (e.g. no face detected), we could fail open or closed. Fail open for robustness.
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
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")
            
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(img_rgb)
        
        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            h, w, _ = img.shape
            
            for eye_indices in [LEFT_EYE, RIGHT_EYE]:
                # Get bounding box for the eye
                xs = [int(landmarks[idx].x * w) for idx in eye_indices]
                ys = [int(landmarks[idx].y * h) for idx in eye_indices]
                
                min_x, max_x = max(0, min(xs) - 10), min(w, max(xs) + 10)
                min_y, max_y = max(0, min(ys) - 10), min(h, max(ys) + 10)
                
                # Draw black rectangle
                cv2.rectangle(img, (min_x, min_y), (max_x, max_y), (0, 0, 0), -1)
                
        # Encode back to JPEG
        _, encoded_img = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return Response(content=encoded_img.tobytes(), media_type="image/jpeg")
        
    except Exception as e:
        logger.error(f"Eye masking failed: {e}")
        # If it fails, just return original image to not block the upload process
        return Response(content=contents, media_type=file.content_type)
