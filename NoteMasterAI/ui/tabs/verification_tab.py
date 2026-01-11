
import numpy as np
import cv2
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QSplitter, QFrame, QGroupBox, 
                             QFormLayout, QLineEdit, QGraphicsPathItem)
from PyQt5.QtGui import QPen, QPainterPath
from PyQt5.QtCore import Qt
from PIL import Image
from ui.widgets.canvas import CanvasWidget
from logic.model_manager import ModelManager
from logic.pdf_utils import PDF_DPI
from data.state import GlobalState

class VerificationTab(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = ModelManager()
        self.current_model_config = None
        self.blank_images = []
        self.key_images = []
        self.current_zones = {}
        self.current_page_idx = 0
        
        self.init_ui()
        
    # --- Logic ---
    current_drawings = {} # {page_idx: [QPainterPath]}
    
    def save_current_drawings_to_memory(self):
        # Extract paths from current scene
        paths = []
        for item in self.canvas._scene.items():
            if isinstance(item, QGraphicsPathItem):
                paths.append(item.path())
        self.current_drawings[self.current_page_idx] = paths
        
    def restore_drawings_from_memory(self, idx):
        paths = self.current_drawings.get(idx, [])
        for p in paths:
             item = QGraphicsPathItem(p)
             pen = QPen(Qt.red, 3)
             pen.setCapStyle(Qt.RoundCap)
             pen.setJoinStyle(Qt.RoundJoin)
             item.setPen(pen)
             self.canvas._scene.addItem(item)

    def load_page(self, idx):
        # Save previous page drawings first if switching
        if self.current_page_idx != idx and self.blank_images: 
             # Only if we are successfully loaded (checked by valid blank_images)
             # But self.current_page_idx is initialized to 0.
             # We should ensure we don't save empty state over valid state if init
             # Simple approach: Always save current state before clearing.
             self.save_current_drawings_to_memory()

        if not self.blank_images: return
        if idx < 0 or idx >= len(self.blank_images): return
        
        self.current_page_idx = idx
        self.lbl_page.setText(f"{idx + 1} / {len(self.blank_images)}")
        
        # Decide background: Use Key Image if available (Visual History), else Blank
        bg_img = self.blank_images[idx]
        if idx < len(self.key_images):
             # Ensure key image is valid
             if self.key_images[idx]:
                 bg_img = self.key_images[idx]
        
        self.canvas.set_image(bg_img)
        zones = self.current_zones.get(idx, [])
        self.canvas.load_zones(zones)
        
        # Restore vector drawings for this session
        self.restore_drawings_from_memory(idx)
        
        # Lock items but allow selection
        for item in self.canvas._scene.items():
            if hasattr(item, "set_locked"):
                item.set_locked(True)
                
        self.grp_answer.setVisible(False)
        self.selected_item = None
        self.set_tool("transform") # Reset to select mode on page change

    def set_tool(self, tool):
        self.canvas.set_tool(tool) # "transform" (select) or "pen"
        if tool == "pen":
             # Deselect zones to avoid visual clutter
             self.canvas._scene.clearSelection()
             self.grp_answer.setVisible(False)

    def prev_page(self):
        self.save_current_drawings_to_memory()
        self.load_page(self.current_page_idx - 1)

    def next_page(self):
        self.save_current_drawings_to_memory()
        self.load_page(self.current_page_idx + 1)
        
    # --- UI & Save ---

    def init_ui(self):
        layout = QHBoxLayout(self)
        
        # Left: Canvas
        left_area = QWidget()
        l_layout = QVBoxLayout(left_area)
        
        # Nav
        nav_bar = QHBoxLayout()
        self.cmb_models = QComboBox()
        self.cmb_models.setMinimumWidth(200)
        self.cmb_models.currentIndexChanged.connect(self.on_model_changed)
        nav_bar.addWidget(QLabel("Model:"))
        nav_bar.addWidget(self.cmb_models)
        
        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(30)
        btn_refresh.clicked.connect(self.refresh_list)
        nav_bar.addWidget(btn_refresh)
        
        nav_bar.addStretch()
        
        # Tools
        btn_select = QPushButton("👆")
        btn_select.setToolTip("Seçim Modu")
        btn_select.setFixedWidth(40)
        btn_select.clicked.connect(lambda: self.set_tool("transform"))
        nav_bar.addWidget(btn_select)
        
        btn_pen = QPushButton("✏️")
        btn_pen.setToolTip("Kalem Modu")
        btn_pen.setFixedWidth(40)
        btn_pen.clicked.connect(lambda: self.set_tool("pen"))
        nav_bar.addWidget(btn_pen)
        
        btn_eraser = QPushButton("🧹")
        btn_eraser.setToolTip("Silgi Modu")
        btn_eraser.setFixedWidth(40)
        btn_eraser.clicked.connect(lambda: self.set_tool("eraser"))
        nav_bar.addWidget(btn_eraser)
        
        nav_bar.addSpacing(20)
        
        btn_prev = QPushButton("◀")
        btn_next = QPushButton("▶")
        self.lbl_page = QLabel("0 / 0")
        
        btn_prev.clicked.connect(self.prev_page)
        btn_next.clicked.connect(self.next_page)
        
        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedWidth(30)
        btn_zoom_in.clicked.connect(lambda: self.canvas.zoom_in())
        
        btn_zoom_out = QPushButton("-")
        btn_zoom_out.setFixedWidth(30)
        btn_zoom_out.clicked.connect(lambda: self.canvas.zoom_out())
        
        nav_bar.addWidget(btn_prev)
        nav_bar.addWidget(self.lbl_page)
        nav_bar.addWidget(btn_next)
        nav_bar.addWidget(btn_zoom_out)
        nav_bar.addWidget(btn_zoom_in)
        
        l_layout.addLayout(nav_bar)
        
        self.canvas = CanvasWidget()
        self.canvas.item_selected.connect(self.on_zone_selected)
        l_layout.addWidget(self.canvas)
        layout.addWidget(left_area, stretch=3)
        
        # Right: Sidebar
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(280)
        self.sidebar.setStyleSheet("background-color: #252526; border-left: 1px solid #3e3e42;")
        r_layout = QVBoxLayout(self.sidebar)
        
        r_layout.addWidget(QLabel("📝 Cevap Anahtarı", styleSheet="font-size: 16px; font-weight: bold; margin-bottom: 10px;"))
        
        self.grp_info = QGroupBox("Seçili Soru")
        form = QFormLayout(self.grp_info)
        self.lbl_zone_name = QLabel("-")
        self.lbl_zone_type = QLabel("-")
        form.addRow("Etiket:", self.lbl_zone_name)
        form.addRow("Tip:", self.lbl_zone_type)
        r_layout.addWidget(self.grp_info)
        
        r_layout.addSpacing(20)
        
        self.grp_answer = QGroupBox("Doğru Cevap")
        ans_layout = QVBoxLayout(self.grp_answer)
        
        self.inp_mcq = QComboBox()
        self.inp_mcq.addItems(["", "A", "B", "C", "D", "E"])
        self.inp_mcq.currentTextChanged.connect(self.on_answer_changed)
        ans_layout.addWidget(self.inp_mcq)
        
        self.inp_tf = QComboBox()
        self.inp_tf.addItems(["", "Doğru", "Yanlış"])
        self.inp_tf.currentTextChanged.connect(self.on_answer_changed)
        ans_layout.addWidget(self.inp_tf)
        
        self.inp_text = QLineEdit()
        self.inp_text.setPlaceholderText("Cevabı yazın...")
        self.inp_text.textChanged.connect(self.on_answer_changed)
        ans_layout.addWidget(self.inp_text)
        
        r_layout.addWidget(self.grp_answer)
        
        # New: AI Note Box
        self.grp_ai = QGroupBox("AI için Özel Not")
        ai_layout = QVBoxLayout(self.grp_ai)
        self.inp_ai_note = QLineEdit()
        self.inp_ai_note.setPlaceholderText("Örn: 'Sadece sayıya bak'")
        self.inp_ai_note.textChanged.connect(self.on_ai_note_changed)
        ai_layout.addWidget(self.inp_ai_note)
        r_layout.addWidget(self.grp_ai)
        
        r_layout.addStretch()
        
        btn_reset = QPushButton("🗑️ CEVAP ANAHTARINI SİL")
        btn_reset.setStyleSheet("background-color: #d9534f; color: white; height: 40px; font-weight: bold; margin-bottom: 10px;")
        btn_reset.clicked.connect(self.delete_answer_key)
        r_layout.addWidget(btn_reset)
        
        btn_save = QPushButton("💾 KAYDET (Tüm Değişiklikler)")
        btn_save.setStyleSheet("background-color: #28a745; color: white; height: 50px; font-weight: bold;")
        btn_save.clicked.connect(self.save_model_data)
        r_layout.addWidget(btn_save)
        
        layout.addWidget(self.sidebar)
        
        self.refresh_list()
        self.grp_answer.setVisible(False)
        self.grp_ai.setVisible(False)
        self.selected_item = None

    def delete_answer_key(self):
        # 1. Confirm
        from PyQt5.QtWidgets import QMessageBox
        res = QMessageBox.question(self, "Onay", 
            "Mevcut cevap anahtarını (görsel çizimler ve oluşturulan PDF) silmek istediğinize emin misiniz?\n\nNot: Bu işlem dijital cevapları (A, B vb.) silmez, sadece çizimleri siler.",
            QMessageBox.Yes | QMessageBox.No)
            
        if res != QMessageBox.Yes: return
        
        # 2. Delete key.pdf
        import os
        name = self.cmb_models.currentText()
        if not name or name == "Seçiniz...": return
        
        model_dir = os.path.join(self.manager.models_dir, name)
        key_pdf = os.path.join(model_dir, "key.pdf")
        
        if os.path.exists(key_pdf):
            try:
                os.remove(key_pdf)
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Dosya silinemedi: {e}")
                return
        
        # 3. Clear memory
        self.key_images = [] # No more key images
        self.current_drawings = {} # Clear current session drawings
        self.canvas._scene.clear() # Clear scene to be safe
        
        # 4. Reload
        self.load_page(self.current_page_idx)
        QMessageBox.information(self, "Başarılı", "Cevap anahtarı silindi. Yeni bir tane oluşturabilirsiniz.")

    def save_model_data(self):
        self.save_current_drawings_to_memory() # Persist current view
        
        from PyQt5.QtWidgets import QMessageBox, QProgressDialog
        import os
        import json
        
        name = self.cmb_models.currentText()
        if not name or name == "Seçiniz...": return

        # 1. Generate Key PDF (Visual)
        # We need to iterate ALL pages, render them, and save
        
        progress = QProgressDialog("Cevap Anahtarı Oluşturuluyor (PDF)...", None, 0, len(self.blank_images), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        rendered_key_images = []
        
        try:
            for i in range(len(self.blank_images)):
                progress.setValue(i)
                # Load context into canvas to render
                # Note: This is an expensive operation as it updates the UI
                # We can optimize by creating a headless scene, but reuse is safer for correctness
                
                # Determine BG
                bg = self.blank_images[i]
                if i < len(self.key_images) and self.key_images[i]:
                    bg = self.key_images[i]
                    
                self.canvas.set_image(bg)
                
                # Add stored paths
                self.restore_drawings_from_memory(i)
                
                # Don't add zones (we want clean key) or add them hidden?
                # canvas.render_canvas handles hiding ResizableRectItems logic!
                # But we need to make sure they exist in the scene to be hidden?
                # Actually render_canvas hides them if they exist.
                # But we haven't added them to scene in this loop.
                # IF we want simple key (just bg + marks), we don't need zones in scene.
                # Canvas.render_canvas hides zones assuming they are there. If not there, result is same.
                
                img = self.canvas.render_canvas()
                rendered_key_images.append(img)
                
            # Restore view to current page
            self.load_page(self.current_page_idx)
            
            # Save PDF
            model_dir = os.path.join(self.manager.models_dir, name)
            key_pdf_path = os.path.join(model_dir, "key.pdf")
            if rendered_key_images:
                # Calculate DPI based on image size and standard A4 width (8.27 inches)
                # This ensures the output PDF has the same 'physical' dimensions as the input
                img_w, img_h = rendered_key_images[0].size
                calc_dpi = int(img_w / 8.27)
                if calc_dpi < 72: calc_dpi = 72 # Minimum safety
                
                print(f"DEBUG: Saving Key PDF with Calculated DPI: {calc_dpi} (Size: {img_w}x{img_h})")
                
                rendered_key_images[0].save(
                    key_pdf_path, 
                    "PDF", 
                    resolution=float(calc_dpi), 
                    save_all=True, 
                    append_images=rendered_key_images[1:]
                )
            
            # 2. Save Metadata (Zones/Answers)
            self.current_model_config["zones"] = self.current_zones
            cfg_path = os.path.join(model_dir, "config.json")
            with open(cfg_path, "w") as f:
                json.dump(self.current_model_config, f, indent=4)
                
            QMessageBox.information(self, "Başarılı", "Cevap anahtarı ve model kaydedildi.")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
        finally:
            progress.close()

    def refresh_list(self):
        current = self.cmb_models.currentText()
        self.cmb_models.blockSignals(True)
        self.cmb_models.clear()
        self.cmb_models.addItem("Seçiniz...", None)
        
        models = self.manager.list_models()
        self.cmb_models.addItems(models)
            
        self.cmb_models.setCurrentText(current)
        self.cmb_models.blockSignals(False)

    def on_model_changed(self):
        name = self.cmb_models.currentText()
        if name == "Seçiniz...": return
        
        config, images = self.manager.load_model(name)
        if not config: return
        
        self.current_model_config = config
        self.blank_images = images
        
        # Populate GlobalState for Grading
        GlobalState().template_images = self.blank_images
        
        # Load Key
        key_imgs = self.manager.load_key_images(name)
        
        # Safety: Resize key images if they don't match blank images
        # This fixes "corrupted" look if DPI mismatch occurred
        self.key_images = []
        for i, k_img in enumerate(key_imgs):
            if i < len(self.blank_images):
                target_size = self.blank_images[i].size # (w, h)
                if k_img.size != target_size:
                    print(f"Uyarı: Key image boyutu uyumsuz ({k_img.size} vs {target_size}). Yeniden boyutlandırılıyor.")
                    k_img = k_img.resize(target_size, Image.Resampling.LANCZOS)
            self.key_images.append(k_img)
        
        self.current_zones = {}
        raw_zones = config.get("zones", {})
        for k, v in raw_zones.items():
            self.current_zones[int(k)] = v
            
        self.load_page(0)

    def on_zone_selected(self, item):
        self.selected_item = item
        if not item or not hasattr(item, "zone_data"):
            self.grp_answer.setVisible(False)
            self.grp_ai.setVisible(False)
            return
            
        z = item.zone_data
        self.lbl_zone_name.setText(z.get("zone_name", "-"))
        self.lbl_zone_type.setText(z.get("zone_type", "-"))
        
        self.grp_answer.setVisible(True)
        self.grp_ai.setVisible(True) # Show Note
        
        # Setup Input based on type
        self.inp_mcq.setVisible(False)
        self.inp_tf.setVisible(False)
        self.inp_text.setVisible(False)
        
        # Load Answer
        curr_ans = z.get("answer", "")
        # Load Note
        curr_note = z.get("ai_note", "")
        
        self.inp_ai_note.blockSignals(True)
        self.inp_ai_note.setText(curr_note)
        self.inp_ai_note.blockSignals(False)
        
        t = z.get("zone_type")
        if t == "Çoktan Seçmeli":
            self.inp_mcq.setVisible(True)
            self.inp_mcq.blockSignals(True)
            self.inp_mcq.setCurrentText(curr_ans)
            self.inp_mcq.blockSignals(False)
        elif t == "Doğru-Yanlış":
            self.inp_tf.setVisible(True)
            self.inp_tf.blockSignals(True)
            self.inp_tf.setCurrentText(curr_ans)
            self.inp_tf.blockSignals(False)
        else:
            self.inp_text.setVisible(True)
            self.inp_text.blockSignals(True)
            self.inp_text.setText(str(curr_ans))
            self.inp_text.blockSignals(False)

    def on_answer_changed(self, val):
        if self.selected_item:
            self.selected_item.zone_data["answer"] = val
            self.selected_item.update() # Trigger repaint to show text

    def on_ai_note_changed(self, val):
        if self.selected_item:
            self.selected_item.zone_data["ai_note"] = val
