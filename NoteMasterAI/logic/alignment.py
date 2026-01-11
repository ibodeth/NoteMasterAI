import cv2
import numpy as np
import os

# --- AYARLAR ---
# Eşleşme hassasiyeti (Düşük = Daha katı eleme, Yüksek = Daha çok kabul)
# 0.7 - 0.75 arası idealdir.
# Eşleşme hassasiyeti (Düşük = Daha katı eleme, Yüksek = Daha çok kabul)
# 0.7 - 0.75 arası idealdir.
RATIO_TEST_THRESHOLD = 0.80 

# Homography hesaplarken kabul edilebilir piksel hatası
# 4.0 veya 5.0 idealdir. Çok düşük yaparsan (örn: 1.0) hiç eşleşme bulamayabilir.
RANSAC_REPROJ_THRESHOLD = 10.0

# Hizalama yapmak için gereken minimum "kaliteli" nokta sayısı
# Hizalama yapmak için gereken minimum "kaliteli" nokta sayısı
MIN_MATCH_COUNT = 10
# SIFT hesaplaması için maksimum boyut (Hız ve genel yapı doğruluğu için)
MAX_ALIGN_DIM = 2000

def align_image(img_template, img_student, debug_path=None):
    """
    NoteMaster Hizalama Motoru (v5 - Rotation Aware + Multi-Method)
    
    Öğrenci kağıdını hizalar. Önce farklı açıları (0, 90, -90, 180) SIFT ile dener.
    Eğer hepsi başarısız olursa, 0 derecede ORB ve AKAZE alternatiflerini dener.
    
    Args:
        img_template: Referans resim (BGR)
        img_student: Öğrenci resmi (BGR)
        
    Returns:
        aligned_image: Hizalanmış resim veya None
    """
    
    def get_rotated(img, angle):
        if angle == 0: return img
        if angle == 90: return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        if angle == -90: return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        if angle == 180: return cv2.rotate(img, cv2.ROTATE_180)
        return img

    # 1. Rotation Strategy (Try SIFT on all angles first)
    # Orientation is a common failure point for otherwise good images.
    rotations = [0, 90, -90, 180]
    
    for angle in rotations:
        # Log only if retrying
        if angle != 0:
             print(f"[Alignment] Deneniyor: SIFT ile {angle} derece döndürme...")
        else:
             print(f"[Alignment] Deneniyor: SIFT (Standart)...")
             
        rot_img = get_rotated(img_student, angle)
        
        # Use SIFT as primary
        result = _try_align_method("SIFT", img_template, rot_img, debug_path)
        if result is not None:
             print(f"[Alignment] SIFT ({angle}°) ile başarıyla hizalandı.")
             return result

    # 2. Fallback Strategy (Texture/Lighting Issues)
    # If SIFT failed all angles, try robust binary descriptors on original image
    other_methods = ["ORB", "AKAZE"]
    for method in other_methods:
        print(f"[Alignment] Deneniyor: {method} (Fallback)...")
        result = _try_align_method(method, img_template, img_student, debug_path)
        if result is not None:
            print(f"[Alignment] {method} ile başarıyla hizalandı.")
            return result
            
    print("[Alignment] Kritik: Tüm hizalama yöntemleri ve açılar başarısız oldu!")
    return None

def validate_homography(H, h_stud, w_stud, h_tmpl, w_tmpl):
    """
    Checks if the Homography H (Student -> Template) is geometrically valid.
    """
    # 1. Determinant Check (Scale/Flip)
    det = np.linalg.det(H[:2, :2])
    
    # Calculate Expected Scaling
    # H maps Student -> Template. Det is area scaling factor.
    area_tmpl = h_tmpl * w_tmpl
    area_stud = h_stud * w_stud
    expected_scale = area_tmpl / area_stud if area_stud > 0 else 1.0
    
    # Relaxed Relative Limits (0.2x - 5x of expected)
    # This handles high-res PDF vs low-res Photo scenarios
    if det < (0.2 * expected_scale) or det > (5.0 * expected_scale):
        # Fallback absolute check just in case expected is weird (e.g. crop)
        if det < 0.1 or det > 30.0: 
            print(f"[Alignment] Rejection: Bad Determinant ({det:.2f}) vs Expected ({expected_scale:.2f})")
            return False
            
    print(f"[Alignment] Determinant OK ({det:.2f} ~ Exp {expected_scale:.2f})")
        
    # 2. Corner Check (Template corners mapped back to Student Image)
    # H maps Student -> Template.
    # Inv(H) maps Template -> Student.
    try:
        H_inv = np.linalg.inv(H)
    except:
        return False
        
    # Template Corners
    pts_tmpl = np.float32([ [0,0], [w_tmpl,0], [w_tmpl,h_tmpl], [0,h_tmpl] ]).reshape(-1,1,2)
    
    # Map to Student Coordinates
    pts_stud_proj = cv2.perspectiveTransform(pts_tmpl, H_inv)
    
    # 3. Check Convexity (Is it a valid quad?)
    if not cv2.isContourConvex(np.int32(pts_stud_proj)):
        print(f"[Alignment] Rejection: Non-convex shape (Twisted)")
        return False
        
    # 4. Check if projected corners are somewhat within reasonable bounds?
    # (Optional: If projected corners are HUGE or TINY, reject)
    # Area check
    area = cv2.contourArea(np.int32(pts_stud_proj))
    stud_area = h_stud * w_stud
    
    if area < stud_area * 0.2: # Projected area too small
         print(f"[Alignment] Rejection: Projected area too small ({area})")
         return False
    
    if area > stud_area * 4.0: # Projected area too huge
         print(f"[Alignment] Rejection: Projected area too big ({area})")
         return False

    return True

def _try_align_method(method_name, img_template, img_student, debug_path):
    """Tekil hizalama denemesi"""
    
    def resize_for_compute(img, max_dim=MAX_ALIGN_DIM):
        h, w = img.shape[:2]
        if max(h, w) <= max_dim: return img, 1.0
        scale = max_dim / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA), scale

    # 1. Resize & Preprocess
    templ_small, templ_scale = resize_for_compute(img_template)
    stud_small, stud_scale = resize_for_compute(img_student)

    gray_template = cv2.cvtColor(templ_small, cv2.COLOR_BGR2GRAY)
    gray_student = cv2.cvtColor(stud_small, cv2.COLOR_BGR2GRAY)
    
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray_template = clahe.apply(gray_template)
    gray_student = clahe.apply(gray_student)

    # 2. Detect Features
    detector = None
    if method_name == "SIFT":
        detector = cv2.SIFT_create(nfeatures=5000)
    elif method_name == "ORB":
        detector = cv2.ORB_create(nfeatures=5000)
    elif method_name == "AKAZE":
        detector = cv2.AKAZE_create()
        
    if detector is None: return None
        
    kp_template, des_template = detector.detectAndCompute(gray_template, None)
    kp_student, des_student = detector.detectAndCompute(gray_student, None)

    if des_template is None or des_student is None: return None
    if len(kp_template) < MIN_MATCH_COUNT or len(kp_student) < MIN_MATCH_COUNT: return None

    # 3. Match
    matches = []
    
    if method_name in ["ORB", "AKAZE"]:
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False) 
        matches = bf.knnMatch(des_template, des_student, k=2)
    else:
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        try:
             matches = flann.knnMatch(des_template, des_student, k=2)
        except: return None

    # 4. Ratio Test
    good_matches = []
    ratio = RATIO_TEST_THRESHOLD
    if method_name == "ORB": ratio = 0.8
    
    for m_n in matches:
        if len(m_n) != 2: continue
        m, n = m_n
        if m.distance < ratio * n.distance:
            good_matches.append(m)

    if len(good_matches) < MIN_MATCH_COUNT: return None

    # 5. Homography
    src_pts = np.float32([kp_template[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp_student[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    
    src_pts /= templ_scale
    dst_pts /= stud_scale

    algo = cv2.RANSAC
    if hasattr(cv2, 'USAC_MAGSAC'): algo = cv2.USAC_MAGSAC
    
    thresh = RANSAC_REPROJ_THRESHOLD 
    H, mask = cv2.findHomography(dst_pts, src_pts, algo, thresh)
    
    if H is None: return None

    # --- SAFETY CHECK (Rigorous) ---
    h_orig, w_orig = img_template.shape[:2]
    h_stud_orig, w_stud_orig = img_student.shape[:2]
    
    if not validate_homography(H, h_stud_orig, w_stud_orig, h_orig, w_orig):
        return None
    # -------------------------------

    # 6. Warming
    aligned_image = cv2.warpPerspective(img_student, H, (w_orig, h_orig))
    
    if debug_path and method_name == "SIFT": 
         pass
         
    return aligned_image

