
# Copied from NoteMasterModelCreate/main_qt.py

YOLO_CLASS_MAPPING = {
    0: {"name": "Boş Alan", "color": (200, 200, 200, 80), "type": "Tanımsız"},
    1: {"name": "Çoktan Seçmeli", "color": (0, 255, 0, 80), "type": "Çoktan Seçmeli"},
    2: {"name": "Doğru-Yanlış", "color": (0, 0, 255, 80), "type": "Doğru-Yanlış"},
    3: {"name": "Eşleştirme", "color": (128, 0, 128, 80), "type": "Eşleştirme"},
    4: {"name": "Klasik Soru", "color": (255, 0, 0, 80), "type": "Klasik Soru"},
    5: {"name": "Öğrenci Bilgisi", "color": (255, 215, 0, 80), "type": "Öğrenci Bilgisi"},
    6: {"name": "AI Çözsün", "color": (0, 204, 255, 80), "type": "AI Çözsün"}
}

DEFAULT_SETTINGS = {
    "mcq_points": 5.0, "mcq_opts": 5, "tf_points": 5.0, 
    "classic_points": 10.0, "match_points": 5.0
}
