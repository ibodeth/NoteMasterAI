
import os
import json
import shutil
from PIL import Image

class ModelManager:
    def __init__(self, models_dir="Models"):
        self.models_dir = models_dir
        os.makedirs(self.models_dir, exist_ok=True)

    def list_models(self):
        models = []
        if os.path.exists(self.models_dir):
            for name in os.listdir(self.models_dir):
                p = os.path.join(self.models_dir, name)
                if os.path.isdir(p) and os.path.exists(os.path.join(p, "config.json")):
                    models.append(name)
        return models

    def load_model(self, model_name):
        path = os.path.join(self.models_dir, model_name)
        config_path = os.path.join(path, "config.json")
        
        if not os.path.exists(config_path):
            return None
            
        with open(config_path, "r") as f:
            config = json.load(f)
            
        # Load images
        images = []
        images_dir = os.path.join(path, "images")
        if os.path.exists(images_dir):
            files = sorted(os.listdir(images_dir), key=lambda x: int(x.split('_')[1].split('.')[0]) if '_' in x else 0)
            for f in files:
                img_path = os.path.join(images_dir, f)
                images.append(Image.open(img_path))
                
        return config, images

    def load_key_images(self, model_name):
        path = os.path.join(self.models_dir, model_name)
        key_path = os.path.join(path, "key.pdf")
        
        if not os.path.exists(key_path):
            return []
            
        with open(key_path, "rb") as f:
            bytes_data = f.read()
            
        from logic.pdf_utils import pdf_to_images
        return pdf_to_images(bytes_data)

    def save_model(self, model_name, images, zones, pdf_key_bytes=None, pdf_slides_bytes=None):
        sp = os.path.join(self.models_dir, model_name)
        os.makedirs(os.path.join(sp, "images"), exist_ok=True)
        
        ref_width, ref_height = images[0].size
        
        cfg = {
            "model_name": model_name,
            "ref_width": ref_width,
            "ref_height": ref_height,
            "zones": zones
        }
        
        with open(os.path.join(sp, "config.json"), "w") as f: 
            json.dump(cfg, f, indent=4)
            
        for i, im in enumerate(images): 
            im.save(os.path.join(sp, "images", f"page_{i}.png"))
            
        # Save composite PDF for reference
        images[0].save(
            os.path.join(sp, "blank.pdf"), "PDF", resolution=150.0, save_all=True, append_images=images[1:]
        )
        
        if pdf_key_bytes:
            with open(os.path.join(sp, "key.pdf"), "wb") as f: f.write(pdf_key_bytes)
        if pdf_slides_bytes:
                with open(os.path.join(sp, "slides.pdf"), "wb") as f: f.write(pdf_slides_bytes)
                
        return True
