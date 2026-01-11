
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QMessageBox, QGroupBox, QStackedWidget,
                             QListWidget, QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, 
                             QProgressDialog)
from PyQt5.QtCore import Qt
from ui.widgets.canvas import CanvasWidget
from logic.model_manager import ModelManager
from logic.utils import run_yolo_detection, load_yolo_model, pil_to_qpixmap
from logic.pdf_utils import pdf_to_images
from logic.transfer_server import set_reference_image
from logic.constants import YOLO_CLASS_MAPPING, DEFAULT_SETTINGS

class TeachingTab(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = ModelManager()
        self.yolo_model = load_yolo_model("best.pt")
        
        self.current_model_config = None
        self.current_model_images = []
        self.current_zones = {} # {page_idx: [zones]}
        
        self.init_ui()
        
    def init_ui(self):
        self.stack = QStackedWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.stack)
        
        # 1. Home View
        self.home_widget = QWidget()
        self.init_home_ui()
        self.stack.addWidget(self.home_widget)
        
        # 2. Editor View
        self.editor_widget = QWidget()
        self.init_editor_ui()
        self.stack.addWidget(self.editor_widget)
        
        self.refresh_model_list()

    def init_home_ui(self):
        # ... logic from HomeWidget in source ...
        layout = QHBoxLayout(self.home_widget)
        
        # Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(300)
        sidebar.setStyleSheet("background-color: #252526; border-right: 1px solid #3e3e42;")
        sb_layout = QVBoxLayout(sidebar)
        
        sb_layout.addWidget(QLabel("📂 Kayıtlı Modeller", styleSheet="font-size: 16px; font-weight: bold; margin-bottom: 10px;"))
        self.model_list = QListWidget()
        self.model_list.setFrameShape(0)
        self.model_list.itemClicked.connect(self.load_selected_model)
        sb_layout.addWidget(self.model_list)
        
        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.clicked.connect(self.refresh_model_list)
        sb_layout.addWidget(btn_refresh)
        layout.addWidget(sidebar)
        
        # Main Area
        main_area = QWidget()
        m_layout = QVBoxLayout(main_area)
        m_layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel("🏫 NoteMaster Model Yöneticisi")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #007acc;")
        m_layout.addWidget(title)
        
        m_layout.addSpacing(40)
        
        btn_new = QPushButton("➕ Yeni Model Oluştur")
        btn_new.setFixedSize(250, 60)
        btn_new.setStyleSheet("font-size: 18px; background-color: #007acc; color: white; border-radius: 4px;")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.clicked.connect(self.start_creation_wizard)
        m_layout.addWidget(btn_new)
        
        layout.addWidget(main_area)

    def init_editor_ui(self):
        layout = QHBoxLayout(self.editor_widget)
        layout.setContentsMargins(0,0,0,0)
        
        # Canvas
        self.canvas = CanvasWidget()
        self.canvas.zone_selected.connect(self.on_zone_selected)
        self.canvas.zone_added.connect(self.on_zone_added)
        layout.addWidget(self.canvas, stretch=3)
        
        # Controls
        controls = QWidget()
        controls.setFixedWidth(320)
        controls.setStyleSheet("background-color: #252526; border-left: 1px solid #3e3e42;")
        c_layout = QVBoxLayout(controls)
        
        # Nav
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("◀")
        self.btn_next = QPushButton("▶")
        self.lbl_page = QLabel("1 / 1")
        self.lbl_page.setAlignment(Qt.AlignCenter)
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next.clicked.connect(self.next_page)
        
        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedWidth(30)
        btn_zoom_in.clicked.connect(self.canvas.zoom_in)
        
        btn_zoom_out = QPushButton("-")
        btn_zoom_out.setFixedWidth(30)
        btn_zoom_out.clicked.connect(self.canvas.zoom_out)
        
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.lbl_page)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addWidget(btn_zoom_out)
        nav_layout.addWidget(btn_zoom_in)
        
        c_layout.addLayout(nav_layout)
        
        c_layout.addSpacing(15)
        
        # Tools
        self.btn_add_rect = QPushButton("➕ Kutu Çiz")
        self.btn_add_rect.setStyleSheet("background-color: #007acc; color: white; padding: 6px;")
        self.btn_add_rect.clicked.connect(lambda: self.canvas.set_tool("rect"))
        c_layout.addWidget(self.btn_add_rect)
        
        # Properties Group
        self.grp_props = QGroupBox("Özellikler")
        f_layout = QFormLayout(self.grp_props)
        
        self.inp_name = QLineEdit()
        self.inp_name.textChanged.connect(self.update_zone_data)
        
        self.inp_type = QComboBox()
        for v in YOLO_CLASS_MAPPING.values():
            self.inp_type.addItem(v["type"])
        self.inp_type.currentTextChanged.connect(self.on_type_changed)
        
        self.inp_points = QDoubleSpinBox()
        self.inp_points.valueChanged.connect(self.update_zone_data)
        
        self.inp_opts = QSpinBox()
        self.inp_opts.setRange(2, 10)
        self.inp_opts.valueChanged.connect(self.update_zone_data)
        
        f_layout.addRow("Etiket:", self.inp_name)
        f_layout.addRow("Tip:", self.inp_type)
        self.lbl_points = QLabel("Puan:")
        f_layout.addRow(self.lbl_points, self.inp_points)
        self.lbl_opts = QLabel("Şık:") # Keep reference to hide/show
        f_layout.addRow(self.lbl_opts, self.inp_opts)
        
        c_layout.addWidget(self.grp_props)
        
        self.btn_delete = QPushButton("🗑️ Sil")
        self.btn_delete.setStyleSheet("background-color: #d9534f; color: white;")
        self.btn_delete.clicked.connect(self.delete_selected_zone)
        c_layout.addWidget(self.btn_delete)
        
        # New: Question Context
        c_layout.addSpacing(15)
        self.btn_context = QPushButton("📷 Soru Bağlamı Ekle")
        self.btn_context.setStyleSheet("background-color: #6f42c1; color: white; padding: 6px;")
        self.btn_context.clicked.connect(self.enter_context_mode)
        self.btn_context.setEnabled(False) 
        c_layout.addWidget(self.btn_context)
        
        self.btn_delete_context = QPushButton("🗑️ Bağlamı Sil")
        self.btn_delete_context.setStyleSheet("background-color: #d63384; color: white; padding: 6px;")
        self.btn_delete_context.clicked.connect(self.delete_context_data)
        self.btn_delete_context.setVisible(False)
        c_layout.addWidget(self.btn_delete_context)
        
        self.lbl_context_preview = QLabel()
        self.lbl_context_preview.setFixedSize(300, 100) # Preview size
        self.lbl_context_preview.setStyleSheet("border: 1px dashed #555;")
        self.lbl_context_preview.setAlignment(Qt.AlignCenter)
        self.lbl_context_preview.setText("Bağlam Görseli")
        self.lbl_context_preview.setVisible(False)
        c_layout.addWidget(self.lbl_context_preview)
        
        c_layout.addStretch()
        
        # Actions
        btn_save = QPushButton("💾 KAYDET VE ÇIK")
        btn_save.setStyleSheet("background-color: #28a745; color: white; height: 40px;")
        btn_save.clicked.connect(self.save_model_and_exit)
        c_layout.addWidget(btn_save)
        
        btn_cancel = QPushButton("❌ İptal")
        btn_cancel.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        c_layout.addWidget(btn_cancel)
        
        layout.addWidget(controls)
        
        self.grp_props.setEnabled(False)
        self.selected_item = None
        self.current_page_idx = 0

    # --- Logic ---
    
    def refresh_model_list(self):
        self.model_list.clear()
        models = self.manager.list_models()
        for m in models:
            self.model_list.addItem(m)

    def start_creation_wizard(self):
        f_blank, _ = QFileDialog.getOpenFileName(self, "Boş Sınav (PDF)", "", "PDF Files (*.pdf)")
        if not f_blank: return
        
        # Simplified: No Key/Slide PDF needed
        self.raw_key_bytes = None
        self.raw_slides_bytes = None
        
        # Store raw bytes for later saving
        with open(f_blank, "rb") as f: self.raw_blank_bytes = f.read()
            
        # Convert
        dlg = QProgressDialog("PDF Dönüştürülüyor...", None, 0, 0, self)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.show()
        
        try:
            self.current_model_images = pdf_to_images(self.raw_blank_bytes)
            self.current_zones = {}
            
            # AI Check
            if self.yolo_model:
                reply = QMessageBox.question(self, "AI Otomatik Tespit", 
                                             "Soru alanlarını otomatik tespit etmek ister misiniz?",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                       for i, img in enumerate(self.current_model_images):
                           zones = run_yolo_detection(self.yolo_model, img)
                           self.current_zones[i] = zones
            
            self.current_model_config = None # New model
            self.load_editor(0)
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
        finally:
            dlg.close()

    def load_selected_model(self, item):
        name = item.text()
        config, images = self.manager.load_model(name)
        if config and images:
            self.current_model_config = config
            self.current_model_images = images
            
            # Convert zone list to dict
            self.current_zones = {}
            raw_zones = config.get("zones", {})
            # Handle if zones is list or dict based on saving struct (manager uses what we pass)
            # Existing code passes dict {index: [zones]}
            for k, v in raw_zones.items():
                self.current_zones[int(k)] = v
                
            self.raw_blank_bytes = None # Can't resave PDF unless we store it?
            # Actually manager.save_model saves images as PDF if provided, or reconstructs.
            # We don't need re-saving PDF bytes for *editing* existing models (usually)
            # Unless we want to update the PDF too. 
            # For now, editing assumes image editing.
            
            self.load_editor(0)

    def load_editor(self, page_idx):
        if page_idx < 0 or page_idx >= len(self.current_model_images): return
        
        self.current_page_idx = page_idx
        self.lbl_page.setText(f"{page_idx + 1} / {len(self.current_model_images)}")
        
        # Load Image
        img = self.current_model_images[page_idx] # PIL Image
        self.canvas.set_image(img)
        
        # Load Zones
        zones = self.current_zones.get(page_idx, [])
        self.canvas.load_zones(zones)
        
        self.stack.setCurrentIndex(1)

    def prev_page(self):
        self.save_current_view_zones()
        self.load_editor(self.current_page_idx - 1)

    def next_page(self):
        self.save_current_view_zones()
        self.load_editor(self.current_page_idx + 1)

    def save_current_view_zones(self):
        # We need to extract data from canvas items
        zones = []
        for item in self.canvas._scene.items():
            # Use internal _scene or expose a method
            from ui.widgets.canvas import ResizableRectItem
            if isinstance(item, ResizableRectItem):
                item.update_geometry_data() # Ensure sync
                zones.append(item.zone_data)
        self.current_zones[self.current_page_idx] = zones

    def on_zone_selected(self, item):
        self.selected_item = item
        if item:
            self.grp_props.setEnabled(True)
            self.inp_name.blockSignals(True)
            self.inp_type.blockSignals(True)
            self.inp_points.blockSignals(True)
            self.inp_opts.blockSignals(True)
            
            self.inp_name.setText(item.zone_data.get("zone_name", ""))
            self.inp_type.setCurrentText(item.zone_data.get("zone_type", "Tanımsız"))
            self.inp_points.setValue(float(item.zone_data.get("zone_points", 0)))
            self.inp_opts.setValue(int(item.zone_data.get("num_options", 5)))
            
            # Visibility Check (Options)
            is_mcq = item.zone_data.get("zone_type") == "Çoktan Seçmeli"
            self.inp_opts.setVisible(is_mcq)
            self.lbl_opts.setVisible(is_mcq)

            # Visibility Check (Points)
            z_type = item.zone_data.get("zone_type")
            # Hide points for "Tanımsız" (Undefined) and "Öğrenci Bilgisi" (Student Info)
            show_points = z_type not in ["Tanımsız", "Öğrenci Bilgisi"]
            self.inp_points.setVisible(show_points)
            self.lbl_points.setVisible(show_points)
            
            self.inp_name.blockSignals(False)
            self.inp_type.blockSignals(False)
            self.inp_points.blockSignals(False)
            self.inp_opts.blockSignals(False)
            
            self.btn_context.setEnabled(True)
            
            # Context Preview Logic
            ctx = item.zone_data.get("context_rect")
            if ctx:
                self.btn_delete_context.setVisible(True)
                self.lbl_context_preview.setVisible(True)
                
                # Crop and Show
                try:
                    full_img = self.current_model_images[self.current_page_idx]
                    x, y, w, h = ctx["left"], ctx["top"], ctx["width"], ctx["height"]
                    crop = full_img.crop((int(x), int(y), int(x+w), int(y+h)))
                    
                    pix = pil_to_qpixmap(crop)
                    self.lbl_context_preview.setPixmap(pix.scaled(
                        self.lbl_context_preview.size(), 
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    ))
                except Exception as e:
                    print(f"Preview Error: {e}")
                    self.lbl_context_preview.setText("Hata")
            else:
                self.btn_delete_context.setVisible(False)
                self.lbl_context_preview.setVisible(False)
                
        else:
            self.grp_props.setEnabled(False)
            self.btn_context.setEnabled(False)
            self.btn_delete_context.setVisible(False)
            self.lbl_context_preview.setVisible(False)

    def update_zone_data(self):
        if self.selected_item:
            self.selected_item.zone_data["zone_name"] = self.inp_name.text()
            
            if self.inp_points.isVisible():
                self.selected_item.zone_data["zone_points"] = self.inp_points.value()
            else:
                self.selected_item.zone_data.pop("zone_points", None)
                
            if self.inp_opts.isVisible():
                self.selected_item.zone_data["num_options"] = self.inp_opts.value()
            else:
                self.selected_item.zone_data.pop("num_options", None)

    def on_type_changed(self, text):
        if self.selected_item:
            self.selected_item.zone_data["zone_type"] = text
            self.selected_item.update_style()
            
            # Apply defaults
            defs = DEFAULT_SETTINGS
            if text == "Çoktan Seçmeli":
                self.selected_item.zone_data["zone_points"] = defs["mcq_points"]
                self.selected_item.zone_data["num_options"] = defs["mcq_opts"]
            elif text == "Doğru-Yanlış":
                 self.selected_item.zone_data["zone_points"] = defs["tf_points"]
            elif text == "Eşleştirme":
                 self.selected_item.zone_data["zone_points"] = defs["match_points"]
            elif text == "Klasik Soru" or text == "Klasik":
                 self.selected_item.zone_data["zone_points"] = defs["classic_points"]
                 
            elif text == "AI Çözsün":
                 self.selected_item.zone_data["zone_points"] = defs["classic_points"] # Default to classic points
                 
            elif text == "Öğrenci Bilgisi" or text == "Tanımsız":
                 self.selected_item.zone_data.pop("zone_points", None)
                 self.selected_item.zone_data.pop("num_options", None)

            # Clean up options for non-MCQ types generally
            if text != "Çoktan Seçmeli":
                 self.selected_item.zone_data.pop("num_options", None)
            
            # Refresh UI to show new values/visibility
            self.on_zone_selected(self.selected_item)

    def delete_selected_zone(self):
        if self.selected_item:
            self.canvas._scene.removeItem(self.selected_item)
            self.selected_item = None
            self.grp_props.setEnabled(False)

    # --- Context Mode Logic ---
    context_temp_hidden_zones = [] 
    is_context_mode = False
    target_zone_item = None

    def enter_context_mode(self):
        if not self.selected_item: return
        
        self.target_zone_item = self.selected_item
        
        # 1. Hide current zones
        self.context_temp_hidden_zones = []
        for item in self.canvas._scene.items():
            from ui.widgets.canvas import ResizableRectItem
            if isinstance(item, ResizableRectItem):
                if item != self.selected_item: 
                     item.setVisible(False)
                     self.context_temp_hidden_zones.append(item)
                else:
                    item.setVisible(False) 
                    self.context_temp_hidden_zones.append(item)

        # 2. Change Tool
        QMessageBox.information(self, "Mod: Soru Bağlamı", 
            "Lütfen ekrandaki 'Soru Metni' veya 'Görseli'ni içeren alanı çiziniz.\nÇizim bitince otomatik kaydedilecektir.")
            
        self.canvas.set_tool("rect")
        self.is_context_mode = True

    def on_zone_added(self, zone_data):
        if self.is_context_mode:
            # We just drew the context rect. 
            # 1. Capture the geometry
            ctx_rect = {
                "left": zone_data["left"],
                "top": zone_data["top"],
                "width": zone_data["width"],
                "height": zone_data["height"]
            }
            
            # 2. Save to TARGET Zone (stored previously)
            if self.target_zone_item:
                self.target_zone_item.zone_data["context_rect"] = ctx_rect
                print(f"DEBUG: Context rect saved to zone {self.target_zone_item.zone_data.get('zone_name')}")
            
            # 3. Remove the temporary "new zone" that was just created
            target_id = zone_data["id"]
            to_remove = None
            for item in self.canvas._scene.items():
                 from ui.widgets.canvas import ResizableRectItem
                 if isinstance(item, ResizableRectItem) and item.zone_data["id"] == target_id:
                     to_remove = item
                     break
            if to_remove:
                self.canvas._scene.removeItem(to_remove)
                
            # 4. Restore State
            for item in self.context_temp_hidden_zones:
                item.setVisible(True)
            self.context_temp_hidden_zones = []
            
            self.is_context_mode = False
            self.canvas.set_tool("transform")
            
            # Refresh UI to show the new preview
            if self.target_zone_item:
                self.on_zone_selected(self.target_zone_item)
            
            QMessageBox.information(self, "Başarılı", "Soru bağlamı kaydedildi!")

    def sanitize_zone_data(self, zone):
        # Rule 1: num_options only for MCQ
        if zone.get("zone_type") != "Çoktan Seçmeli":
            zone.pop("num_options", None)
            
        # Rule 2: No points for Undefined or Student Info
        if zone.get("zone_type") in ["Tanımsız", "Öğrenci Bilgisi"]:
            zone.pop("zone_points", None)
            
        return zone

    def delete_context_data(self):
        if self.selected_item and "context_rect" in self.selected_item.zone_data:
            self.selected_item.zone_data.pop("context_rect")
            self.on_zone_selected(self.selected_item) # Refresh UI
            QMessageBox.information(self, "Bilgi", "Soru bağlamı silindi.")

    def save_model_and_exit(self):
        self.save_current_view_zones()
        
        # Global Sanitization before Save
        for page_idx, zones in self.current_zones.items():
            for z in zones:
                self.sanitize_zone_data(z)
        
        from PyQt5.QtWidgets import QInputDialog
        default_name = self.current_model_config["model_name"] if self.current_model_config else "Yeni Model"
        name, ok = QInputDialog.getText(self, "Model Kaydet", "Model Adı:", text=default_name)
        
        if ok and name:
            try:
                # Simplified: No Key/Slide PDF
                self.manager.save_model(name, self.current_model_images, self.current_zones, 
                                        None, None)
                                        
                QMessageBox.information(self, "Başarılı", "Model kaydedildi.")
                self.stack.setCurrentIndex(0)
                self.refresh_model_list()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kaydetme hatası: {str(e)}")

