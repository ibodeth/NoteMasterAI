
# Copied from NoteMasterModelCreate/main_qt.py

YOLO_CLASS_MAPPING = {
    0: {"name": "Empty Area", "color": (200, 200, 200, 80), "type": "Undefined"},
    1: {"name": "Multiple Choice", "color": (0, 255, 0, 80), "type": "Multiple Choice"},
    2: {"name": "True-False", "color": (0, 0, 255, 80), "type": "True-False"},
    3: {"name": "Matching", "color": (128, 0, 128, 80), "type": "Matching"},
    4: {"name": "Classic Question", "color": (255, 0, 0, 80), "type": "Classic Question"},
    5: {"name": "Student Info", "color": (255, 215, 0, 80), "type": "Student Info"},
    6: {"name": "AI Solve", "color": (0, 204, 255, 80), "type": "AI Solve"}
}

DEFAULT_SETTINGS = {
    "mcq_points": 5.0, "mcq_opts": 5, "tf_points": 5.0, 
    "classic_points": 10.0, "match_points": 5.0
}