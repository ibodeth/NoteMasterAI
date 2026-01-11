import cv2
import numpy as np

def _get_omr_scores(thresh_image, num_options, layout):
    """(YARDIMCI) Görüntüyü Dikey/Yatay böl ve puanları döndür."""
    h, w = thresh_image.shape
    scores = []

    if layout == "yatay":
        option_width = w // num_options
        for i in range(num_options):
            start_x = i * option_width
            end_x = (i + 1) * option_width if i < num_options - 1 else w 
            split = thresh_image[0:h, start_x:end_x]
            yield split 
    else: # dikey
        option_height = h // num_options
        for i in range(num_options):
            start_y = i * option_height
            end_y = (i + 1) * option_height if i < num_options - 1 else h
            split = thresh_image[start_y:end_y, 0:w]
            yield split 

def process_omr_zone_by_area(image, num_options=5, layout="dikey"):
    """ÇOKTAN SEÇMELİ için: Alan (cv2.contourArea) ile okur."""
    if image is None or image.size == 0: return -1, []

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    try:
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    except cv2.error:
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

    scores = []
    for split in _get_omr_scores(thresh, num_options, layout):
        contours, _ = cv2.findContours(split, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            scores.append(0)
            continue
            
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)
        scores.append(area)
        
    if not scores: return -1, []
        
    selected_index = np.argmax(scores)
    
    h, w = image.shape[:2]
    total_area = h * w
    # Lower threshold to 2% to catch faint pencil marks
    min_area = (total_area / num_options) * 0.02 
    
    # Check if the max score is significant enough
    if scores[selected_index] < min_area:
        return -1, scores 

    return selected_index, scores

def process_omr_zone_by_blackness(image, num_options=2, layout="dikey"):
    """DOĞRU-YANLIŞ için: Siyahlık (cv2.countNonZero) ile okur."""
    if image is None or image.size == 0: return -1, []

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    try:
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    except cv2.error:
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

    scores = []
    for split in _get_omr_scores(thresh, num_options, layout):
        score = cv2.countNonZero(split)
        scores.append(score)
    
    if not scores: return -1, []
        
    selected_index = np.argmax(scores)
    
    h, w = image.shape[:2]
    total_area = h * w
    # Lower threshold to 2%
    min_pixel_count = (total_area / num_options) * 0.02
    
    if scores[selected_index] < min_pixel_count:
        return -1, scores

    return selected_index, scores

def process_visual_comparison(student_img, key_img, num_options=5, layout="dikey"):
    """
    Visual comparison of Student Answer vs Answer Key.
    
    1. Reads the Key Image to find the Correct Answer (Index).
    2. Reads the Student Image to find the Student's Answer (Index).
    3. Compares them.
    4. Returns: (student_index, correct_index, score_bool)
       score_bool: True if match, False otherwise.
    """
    if student_img is None or key_img is None:
        return -1, -1, False
    
    # 1. Determine Correct Answer from Key Image
    # We reuse the existing logic based on layout
    # For True/False (2 options), we use blackness. For Test (5 options), we use contours/area.
    # However, to be robust, let's use the same logic for both or choose based on num_options.
    
    # Heuristic: If num_options == 2, assume True/False (Blackness/Fill).
    # If num_options > 2, assume Test (Bubble/Contour).
    
    func = process_omr_zone_by_area if num_options > 2 else process_omr_zone_by_blackness
    
    # Correct Answer
    correct_idx, _ = func(key_img, num_options, layout)
    
    # Student Answer
    student_idx, _ = func(student_img, num_options, layout)
    
    is_correct = (student_idx == correct_idx) and (correct_idx != -1)
    
    return student_idx, correct_idx, is_correct
