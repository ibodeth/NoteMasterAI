import os
import cv2
import numpy as np
from PIL import Image
from PyQt5.QtGui import QImage, QPixmap
from ultralytics import YOLO

def load_yolo_model(model_path):
    if os.path.exists(model_path):
        try:
            return YOLO(model_path)
        except Exception as e:
            print(f"Error loading YOLO: {e}")
            return None
    return None

def pil_to_qpixmap(pil_image):
    if pil_image.mode == "RGB": 
        r, g, b = pil_image.split()
        pil_image = Image.merge("RGB", (b, g, r))
    elif pil_image.mode == "RGBA": 
        r, g, b, a = pil_image.split()
        pil_image = Image.merge("RGBA", (b, g, r, a))
    elif pil_image.mode == "L": 
        pil_image = pil_image.convert("RGBA")
    
    im2 = pil_image.convert("RGBA")
    data = im2.tobytes("raw", "RGBA")
    qim = QImage(data, im2.size[0], im2.size[1], QImage.Format_ARGB32)
    return QPixmap.fromImage(qim.copy())

def cv2_to_qpixmap(cv_image):
    if cv_image is None:
        return QPixmap()
        
    height, width = cv_image.shape[:2]
    
    if len(cv_image.shape) == 2:
        # Grayscale
        bytes_per_line = width
        q_image = QImage(cv_image.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
    else:
        # RGB/BGR
        bytes_per_line = 3 * width
        q_image = QImage(cv_image.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        
    return QPixmap.fromImage(q_image)

def run_yolo_detection(model, pil_image, conf=0.2):
    """
    Run YOLO detection on a PIL image and return standard zone dictionaries.
    """
    results = model(pil_image, conf=conf)
    zones = []
    import uuid
    from logic.constants import YOLO_CLASS_MAPPING

    for result in results:
        boxes = result.boxes.xyxy.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy()
        
        for box, cls_id in zip(boxes, classes):
            x1, y1, x2, y2 = box
            w = x2 - x1
            h = y2 - y1
            
            cls_id = int(cls_id)
            mapping = YOLO_CLASS_MAPPING.get(cls_id, YOLO_CLASS_MAPPING[0])
            
            zone = {
                "id": str(uuid.uuid4()),
                "zone_name": mapping['name'],
                "zone_type": mapping['type'],
                "zone_points": 5.0, # Default
                "num_options": 5,   # Default
                "left": float(x1), "top": float(y1), 
                "width": float(w), "height": float(h)
            }
            zones.append(zone)
            
    return zones

def preprocess_image_for_ocr(image_cv):
    """
    Applies advanced preprocessing to enhance handwritten text.
    1. Upscale 2x (Critical for small text)
    2. Grayscale
    3. CLAHE (Contrast Enhancement) - Better than simple thresholding for preserving strokes
    4. Mild Denoising
    """
    if image_cv is None: return None
    
    # 1. Upscale (Linear/Cubic)
    # Using Cubic for smoother edges
    upscaled = cv2.resize(image_cv, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    
    # 2. Grayscale
    if len(upscaled.shape) == 3:
        gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
    else:
        gray = upscaled

    # 3. Denoising (Fast NlMeans is too slow, use Gaussian)
    # Just a light blur to remove paper grain without killing text
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # 4. CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(blurred)

    # 5. Binarization (Optional, but sometimes grayscale is better for Gemini Vision)
    # Let's return the Enhanced Grayscale for Vision/Gemini as it handles gradients better.
    # But for Cloud Vision (OCR), pure B&W might be preferred?
    # Actually, recent OCR prefers grayscale over bad B&W. 
    # Let's do a very soft adaptive threshold just to boost signal.
    
    thresh = cv2.adaptiveThreshold(
         enhanced, 255, 
         cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
         cv2.THRESH_BINARY, 21, 10
    )
    
    return thresh

def preprocess_for_gemini(image_cv):
    """
    Super-Enhanced Preprocessing for AI OCR:
    1. Denoise (Remove grain/paper noise)
    2. Upscale (Always 2x or 3x for clarity)
    3. Contrast (CLAHE)
    4. Edge Preservation & Sharpening
    """
    if image_cv is None: return None
    
    # 0. Initial Denoise (Mild) - Helps with paper grain
    # fastNlMeans is a bit slow but worth it for quality
    try:
        denoised = cv2.fastNlMeansDenoisingColored(image_cv, None, 3, 3, 7, 21)
    except:
        denoised = image_cv # Fallback if grayscale input fails Colored func
    
    # Convert to Gray
    if len(denoised.shape) == 3:
        gray = cv2.cvtColor(denoised, cv2.COLOR_BGR2GRAY)
    else:
        gray = denoised
        
    # 1. Aggressive Upscale (Gemini likes pixels for detail)
    # Always upscale to ensure strokes are thick enough
    h, w = gray.shape[:2]
    scale_factor = 2.0
    if h < 400: scale_factor = 3.0 # Boost small text significantly
    
    upscaled = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
        
    # 2. "Whiter Whites, Blacker Blacks" (Contrast Stretching)
    # Normalize first to use full dynamic range 0-255
    normalized = cv2.normalize(upscaled, None, 0, 255, cv2.NORM_MINMAX)
    
    # Apply Linear Contrast Strecthing (Alpha=Contrast, Beta=Brightness)
    # Alpha 1.5 makes blacks darker and whites whiter significantly.
    # Beta -20 shifts everything slightly darker to kill light gray noise.
    high_contrast = cv2.convertScaleAbs(normalized, alpha=1.5, beta=-20)
    
    # 3. Local Contrast Enhancement (CLAHE) - For details in dark areas
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(high_contrast)
    
    # 3. Sharpening (Unsharp Masking with Bilateral protection)
    # Bilateral filter smooths planar regions but keeps edges crisp
    # Formula: Original + (Original - Smoothed) * Amount
    smooth = cv2.bilateralFilter(enhanced, 5, 75, 75)
    sharpened = cv2.addWeighted(enhanced, 2.0, smooth, -1.0, 0)
    
    # Return as RGB
    return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)
