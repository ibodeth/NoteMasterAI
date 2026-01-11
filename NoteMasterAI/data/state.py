import json
import os

class GlobalState:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalState, cls).__new__(cls)
            cls._instance.reset()
        return cls._instance
    
    def reset(self):
        # Phase 1 Data
        self.pdf_images = []     # Template blank PDF images (PIL or OpenCV)
        self.current_page = 0
        self.zones = {}          # Dictionary: { page_index: [zone_dict, ...] }
        self.template_json_path = "sablon.json"
        self.template_images_dir = "template_images"
        
        # Phase 2 Context Data
        self.pdf_ders_notlari = None       # bytes or None
        self.pdf_cevap_anahtari = None     # bytes or None
        self.context_text = ""            # Parsed text from ders notlari
        self.answer_key_images = []       # Images from answer key PDF
        self.template_images = []         # For context cropping (Phase 3)
        self.template_images = []         # For context cropping (Phase 3)
        
        # API Clients
        self.vision_client = None
        self.gemini_model = None

    def load_zones_from_file(self):
        if os.path.exists(self.template_json_path):
            try:
                with open(self.template_json_path, 'r', encoding='utf-8') as f:
                    # JSON keys are strings in file, but we use ints for page index in memory usually.
                    # Let's standardize on string keys for zones dictionary to match JSON.
                    self.zones = json.load(f)
                    # Convert keys to int if needed by UI, or keep as str. 
                    # app.py used int indices in loop: for i in range(len(pdf_images)).
                    # But JSON stores keys as strings "0", "1".
                    # Let's convert keys to ints for internal Python usage.
                    self.zones = {int(k): v for k, v in self.zones.items()}
                return True
            except Exception as e:
                print(f"Error loading zones: {e}")
                return False
        return False

    def save_zones_to_file(self):
        try:
            with open(self.template_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.zones, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving zones: {e}")
            return False
