import os
import io
import cv2
import numpy as np
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QProgressBar, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QInputDialog, QLineEdit, QComboBox, 
                             QFrame, QTextEdit, QSplitter, QScrollArea)
from PyQt5.QtGui import QImage, QPixmap
from PIL import Image
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings, QFileSystemWatcher

from logic import alignment, omr, grading
from logic.pdf_utils import pdf_to_images, get_text_from_pdf
from logic.model_manager import ModelManager
from logic.utils import preprocess_image_for_ocr
from logic import database
import logic.transfer_server as transfer_server
from logic.transfer_server import set_reference_image
from data.state import GlobalState

class GradingWorker(QThread):
    # Signals
    student_progress = pyqtSignal(str, str, int)  # Name, Status, percent
    live_update = pyqtSignal(dict)                # Visual feed
    result_ready = pyqtSignal(dict)               # Final stats per student
    error_occurred = pyqtSignal(str)
    finished_all = pyqtSignal()
    log_signal = pyqtSignal(str)

    def __init__(self, file_paths, api_key, service_account_path, teacher_prompt=""):
        super().__init__()
        self.file_paths = file_paths
        self.api_key = api_key
        self.service_account_path = service_account_path
        self.teacher_prompt = teacher_prompt
        self.state = GlobalState()
        self.is_running = True

    def run(self):
        import concurrent.futures
        import functools
        import threading
        
        # 1. Setup APIs
        vision_client, gemini_model = grading.setup_apis()
        if not vision_client or not gemini_model:
            self.error_occurred.emit("API Kurulumu Başarısız! Lütfen service-account.json ve API Key kontrol edin.")
            return

        # 2. Parse Context & Answer Key
        context_text = ""
        if self.state.pdf_ders_notlari:
            context_text = get_text_from_pdf(self.state.pdf_ders_notlari)
        
        ideal_texts = {} 
        if self.state.zones:
            for p_idx, page_zones in self.state.zones.items():
                for z in page_zones:
                    z_id = z.get('id', 'Unknown')
                    ideal_texts[z_id] = z.get("answer", "")

        answer_key_images = []
        if self.state.pdf_cevap_anahtari:
            try:
                answer_key_images = pdf_to_images(self.state.pdf_cevap_anahtari)
            except Exception as e:
                print(f"ERROR: Failed to parse Answer Key images: {e}")

        # Database Setup
        if len(self.file_paths) > 0:
            first_path = self.file_paths[0].rstrip(os.sep) 
            base_dir = os.path.dirname(first_path)
            if os.path.isfile(self.file_paths[0]): 
                 base_dir = os.path.dirname(self.file_paths[0])
        else:
             base_dir = os.getcwd()
             
        self.db_path = os.path.join(base_dir, "grading_results.db")
        self.crops_dir = os.path.join(base_dir, "crops")
        os.makedirs(self.crops_dir, exist_ok=True)
        debug_dir = os.path.join(os.getcwd(), "debug_output")
        os.makedirs(debug_dir, exist_ok=True)
        
        database.init_db(self.db_path)

        # Thread Pool (Max 5 workers for AI)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=5) 
        
        # Semaphore for memory heavy ops (Loading/Aligning)
        # Allow 2 students to align in parallel (CPU bound but memory heavy)
        align_sem = threading.Semaphore(2) 

        # Progress Tracker: {unit_name: {'total': N, 'done': 0, 'buffer': [], 'details': {}}}
        prog_tracker = {}
        tracker_lock = threading.Lock()

        # --- CALLBACK HELPER ---
        def task_done_callback(fut, meta, u_name, db_pth, s_db_id):
            try:
                result_wrapper = fut.result()
                res_type = result_wrapper.get("type")
                res_data = result_wrapper.get("data")
                
                with tracker_lock:
                    if u_name not in prog_tracker: return
                    st = prog_tracker[u_name]
                    st['done'] += 1
                    done_count = st['done']
                    total_count = st['total']
                    pct = int((done_count / total_count) * 100) if total_count > 0 else 100
                    
                    # Log Status
                    self.student_progress.emit(u_name, f"AI Değerlendiriyor ({done_count}/{total_count})", pct)

                details_dict = st['details']
                
                if res_type == "info":
                    info = res_data
                    new_part = info.get("name", "").strip()
                    s_num = info.get("number", "")
                    s_cls = info.get("class_name", "")
                    if s_num: details_dict["number"] = s_num
                    if s_cls: details_dict["class"] = s_cls
                    
                    final_name = u_name
                    if new_part and new_part not in final_name:
                         final_name += f" {new_part}"
                    
                    database.update_student_metadata(db_pth, s_db_id, final_name, 
                                                     details_dict["number"], details_dict["class"])
                    return

                elif res_type in ["comparison", "grading"]:
                    max_pts = meta.get("max_points", 0.0)
                    score = 0.0
                    is_correct = False
                    reason = ""
                    val_s = ""
                    val_c = ""
                    
                    if res_type == "comparison":
                        is_correct = res_data.get("match", False)
                        val_s = res_data.get("student_val", "?")
                        val_c = res_data.get("key_val", "?")
                        reason = res_data.get("reason", "")
                        score = max_pts if is_correct else 0.0
                    else:
                        score_coeff = float(res_data.get("puan", 0.0))
                        score = score_coeff * max_pts
                        reason = res_data.get("gerekce", "")
                        val_s = res_data.get("okunan_cevap", "")
                        z_struct = meta.get("z", {})
                        z_id = z_struct.get("id", "Unknown")
                        val_c = ideal_texts.get(z_id, "")
                    
                    final_res = {
                        "sys_meta": meta,
                        "p_idx": meta["p_idx"],
                        "top": meta["top"],
                        "name": meta["z_name"],
                        "type": meta["z_type"],
                        "score": score,
                        "max_points": max_pts,
                        "student_text": val_s,
                        "correct_answer": val_c,
                        "reason": reason,
                        "crop_path": meta["crop_path"],
                        "key_crop_path": meta["key_crop_path"]
                    }
                    
                    with tracker_lock:
                         st['buffer'].append(final_res)

                    # Live Feed
                    live_data = {
                        "question": meta["z_name"],
                        "type": meta["z_type"],
                        "student_crop": meta["crop"], 
                        "key_crop": meta.get("key_crop"),
                        "student_text": str(val_s),
                        "correct_answer": str(val_c),
                        "score": score,
                        "reason": reason
                    }
                    self.live_update.emit(live_data)
                
                # Check Completion
                is_finished = False
                with tracker_lock:
                    if st['done'] >= st['total']:
                        is_finished = True
                
                if is_finished:
                    finalize_student(u_name, st['buffer'], details_dict, s_db_id)

            except Exception as e:
                print(f"Callback Error: {e}")

        def finalize_student(u_name, buffer, details_dict, s_db_id):
            # Sort
            buffer.sort(key=lambda x: (x["p_idx"], x["top"]))
            
            report_lines = []
            total_file_score = 0.0
            file_result = {"filename": u_name, "zones": []}
            
            for res in buffer:
                db_entry = {
                    "name": res["name"],
                    "type": res["type"],
                    "score": res["score"],
                    "max_points": res["max_points"],
                    "student_text": res["student_text"],
                    "correct_answer": res["correct_answer"],
                    "reason": res["reason"],
                    "crop_path": res["crop_path"],
                    "key_crop_path": res["key_crop_path"]
                }
                database.save_zone_result(self.db_path, s_db_id, db_entry)
                total_file_score += res["score"]
                detail = f"{res['student_text']} | Puan: {res['score']}"
                report_lines.append(f"{res['name']}: {detail} ({res['reason']})")
                file_result["zones"].append({"name": res["name"], "score": res["score"], "details": detail})

            database.update_student_score(self.db_path, s_db_id, total_file_score)
            file_result["total_score"] = total_file_score
            
            # Save Text Report logic (same as before, Simplified)
            # ...
            
            self.student_progress.emit(u_name, "Tamamlandı", 100)
            self.result_ready.emit(file_result)
            
            with tracker_lock:
                if u_name in prog_tracker:
                    del prog_tracker[u_name] # Cleanup

        # --- MAIN LOOP ---
        for idx, unit_path in enumerate(self.file_paths):
            if not self.is_running: break
            
            unit_name = os.path.basename(unit_path)
            
            # Initial UI Update
            self.student_progress.emit(unit_name, "Hazırlanıyor...", 0)
            
            align_sem.acquire() # Block if too many active loading
            
            try:
                self.student_progress.emit(unit_name, "Görüntüler İşleniyor...", 5)
                
                # Load Images
                student_images = []
                if os.path.isdir(unit_path):
                    valid_exts = ('.jpg', '.jpeg', '.png', '.bmp')
                    img_files = [f for f in os.listdir(unit_path) if f.lower().endswith(valid_exts)]
                    def sort_key(s):
                        import re
                        parts = re.split(r'(\d+)', s)
                        return [int(p) if p.isdigit() else p.lower() for p in parts]
                    img_files.sort(key=sort_key)
                    for img_f in img_files:
                        try:
                            im = Image.open(os.path.join(unit_path, img_f)).convert("RGB")
                            student_images.append(im)
                        except: pass
                else:
                    with open(unit_path, "rb") as f:
                        student_images = pdf_to_images(f.read())
                        
                if not student_images:
                    self.error_occurred.emit(f"{unit_name}: Görüntü yüklenemedi")
                    continue

                student_db_id = database.save_student_header(self.db_path, unit_name, unit_path)
                
                # Calculate Total Tasks (Zones)
                total_tasks = 0
                for p_idx in range(len(student_images)):
                     total_tasks += len([z for z in self.state.zones.get(p_idx, []) if z.get("zone_type") != "Tanımsız"])
                
                if total_tasks == 0:
                     self.student_progress.emit(unit_name, "Soru Bulunamadı", 100)
                     continue

                # Initialize Tracker
                with tracker_lock:
                    prog_tracker[unit_name] = {
                        'total': total_tasks,
                        'done': 0,
                        'buffer': [],
                        'details': {"name": "", "number": "", "class": ""}
                    }

                # --- WAIT FOR TASKS ---
                # REMOVED blocking 'wait' to allow parallel students.
                # Completion is handled via callbacks and prog_tracker.
                # --- PROCESS PAGES ---
                for p_idx, p_img in enumerate(student_images):
                    if not self.is_running: break
                    
                    self.student_progress.emit(unit_name, f"Sayfa {p_idx+1} Hizalanıyor...", 10)
                    
                    if p_img.mode != 'RGB': p_img = p_img.convert('RGB')
                    stud_cv = cv2.cvtColor(np.array(p_img), cv2.COLOR_RGB2BGR)
                    
                    # Alignment
                    # Alignment
                    tmpl_pil = self.state.pdf_images[p_idx] if p_idx < len(self.state.pdf_images) else None
                    if tmpl_pil:
                        tmpl_cv = cv2.cvtColor(np.array(tmpl_pil.convert('RGB')), cv2.COLOR_RGB2BGR)
                        matches_vis_path = os.path.join(debug_dir, f"debug_matches_{unit_name}_{p_idx}.jpg")
                        aligned_stud = alignment.align_image(tmpl_cv, stud_cv, debug_path=matches_vis_path)
                        if aligned_stud is None: 
                            # Fallback: Assume it IS aligned (from Server) but needs resizing to match Template
                            print(f"[Grading] Alignment failed for {unit_name}, assuming pre-aligned. Resizing to template.")
                            h_t, w_t = tmpl_cv.shape[:2]
                            aligned_stud = cv2.resize(stud_cv, (w_t, h_t))
                    else:
                        aligned_stud = stud_cv
                        tmpl_cv = None 
                    
                    # Submit Tasks
                    page_zones = self.state.zones.get(p_idx, [])
                    page_zones = sorted(page_zones, key=lambda z: z.get('top', 0))
                    
                    for z in page_zones:
                        z_name = z.get("zone_name", "Unknown")
                        z_type = z.get("zone_type", "Klasik")
                        if z_type == "Tanımsız": continue
                        
                        x, y, w, h = int(z['left']), int(z['top']), int(z['width']), int(z['height'])
                        
                        # Crop
                        h_img, w_img = aligned_stud.shape[:2]
                        x = max(0, min(x, w_img-1))
                        y = max(0, min(y, h_img-1))
                        w = max(1, min(w, w_img-x))
                        h = max(1, min(h, h_img-y))
                        crop = aligned_stud[y:y+h, x:x+w]
                        
                        from logic import utils
                        proc_crop_cv = utils.preprocess_for_gemini(crop)
                        
                        safe_zid = str(z.get("id", "no_id"))[:6]
                        crop_filename = f"{unit_name}_{z_name}_{safe_zid}_{p_idx}.jpg".replace(" ", "_").replace("/", "-")
                        cv2.imwrite(os.path.join(self.crops_dir, crop_filename), proc_crop_cv)
                        pil_crop_input = Image.fromarray(cv2.cvtColor(proc_crop_cv, cv2.COLOR_BGR2RGB))
                        
                        task_meta = {
                            "p_idx": p_idx,
                            "top": y,
                            "z_name": z_name,
                            "z_type": z_type,
                            "z": z, 
                            "crop": proc_crop_cv,
                            "crop_path": crop_filename,
                            "key_crop_path": ""
                        }
                        
                        # Student Info
                        if z_type == "Öğrenci Bilgisi":
                              def parse_info_task(model, img):
                                  try:
                                      return {"type": "info", "data": grading.parse_student_info(model, img)}
                                  except Exception as e:
                                      return {"type": "error", "msg": str(e)}

                              fut = executor.submit(parse_info_task, gemini_model, pil_crop_input)
                              cb = functools.partial(task_done_callback, meta=task_meta, u_name=unit_name, 
                                                     db_pth=self.db_path, s_db_id=student_db_id)
                              fut.add_done_callback(cb)
                              continue

                        # Safe Max Points Parsing
                        try:
                            raw_pts = str(z.get('zone_points', 0))
                            raw_pts = raw_pts.replace(',', '.')
                            max_pts_val = float(raw_pts)
                        except:
                            max_pts_val = 0.0
                        
                        if max_pts_val <= 0 and z_type == "AI Çözsün": max_pts_val = 10.0
                            
                        # Key Crop Logic (same as before)
                        key_crop_cv = None
                        key_crop_pil = None
                        if z_type in ["Çoktan Seçmeli", "Doğru-Yanlış"]:
                            if p_idx < len(answer_key_images):
                                try:
                                    k_page = np.array(answer_key_images[p_idx].convert('RGB'))
                                    k_page = cv2.cvtColor(k_page, cv2.COLOR_RGB2BGR)
                                    h_k, w_k = k_page.shape[:2]
                                    kx = max(0, min(x, w_k-1))
                                    ky = max(0, min(y, h_k-1))
                                    kw = max(1, min(w, w_k-kx))
                                    kh = max(1, min(h, h_k-ky))
                                    key_crop_cv = k_page[ky:ky+kh, kx:kx+kw]
                                    key_proc_cv = utils.preprocess_for_gemini(key_crop_cv)
                                    
                                    safe_zid = str(z.get("id", "no_id"))[:6]
                                    k_crop_name = f"{unit_name}_{z_name}_{safe_zid}_{p_idx}_KEY.jpg".replace(" ", "_").replace("/", "-")
                                    cv2.imwrite(os.path.join(self.crops_dir, k_crop_name), key_proc_cv)
                                    
                                    task_meta["key_crop_path"] = k_crop_name
                                    task_meta["key_crop"] = key_proc_cv
                                    key_crop_pil = Image.fromarray(cv2.cvtColor(key_proc_cv, cv2.COLOR_BGR2RGB))
                                except: pass
                        
                        # Context (same as before)
                        context_img_pil = None
                        if "context_rect" in z and tmpl_cv is not None:
                             # ... (Simple Copy) ...
                            cr = z["context_rect"]
                            cx, cy, cw, ch = int(cr["left"]), int(cr["top"]), int(cr["width"]), int(cr["height"])
                            h_t, w_t = tmpl_cv.shape[:2]
                            cx = max(0, min(cx, w_t-1))
                            cy = max(0, min(cy, h_t-1))
                            cw = max(1, min(cw, w_t-cx))
                            ch = max(1, min(ch, h_t-cy))
                            if cw>0 and ch>0:
                                ctx_crop = tmpl_cv[cy:cy+ch, cx:cx+cw]
                                context_img_pil = Image.fromarray(cv2.cvtColor(ctx_crop, cv2.COLOR_BGR2RGB))
                        
                        if context_img_pil is None and tmpl_cv is not None:
                            tmpl_zone = tmpl_cv[y:y+h, x:x+w]
                            context_img_pil = Image.fromarray(cv2.cvtColor(tmpl_zone, cv2.COLOR_BGR2RGB))

                        # Define Task Function
                        def grade_task(model, s_crop, k_crop, c_crop, z_type_str, ideal, ctx_txt, t_prompt, q_note):
                            if z_type_str in ["Çoktan Seçmeli", "Doğru-Yanlış"]:
                                return {"type": "comparison", "data": grading.get_ai_comparison_result(model, s_crop, k_crop, z_type_str, preprocess=False)}
                            else:
                                txt = "" 
                                return {"type": "grading", "data": grading.get_gemini_score(model, txt, ideal, ctx_txt, z_type_str, 
                                                                                            sorunun_gorseli=c_crop, ogrenci_gorseli=s_crop, 
                                                                                            teacher_prompt=t_prompt, question_prompt=q_note, preprocess=False)}

                        # Submit
                        z_id = z.get("id", "")
                        ideal_text = ideal_texts.get(z_id, "")
                        q_note = z.get('ai_note', '')
                        task_meta["max_points"] = max_pts_val
                        
                        fut = executor.submit(grade_task, gemini_model, pil_crop_input, key_crop_pil, context_img_pil, 
                                                 str(z_type), ideal_text, context_text, self.teacher_prompt, q_note)
                        
                        cb = functools.partial(task_done_callback, meta=task_meta, u_name=unit_name, 
                                               db_pth=self.db_path, s_db_id=student_db_id)
                        fut.add_done_callback(cb)

                # After submitting all tasks for this student, we can notify "Queued" 
                # and release semaphore to allow next student to load.
                self.student_progress.emit(unit_name, "AI Bekleniyor...", 15)
                
            finally:
                align_sem.release()

        # Shutdown waiter? No, run() ends but threads continue.
        # We need to wait until all trackers are empty?
        # Actually, executor.shutdown(wait=True) will wait for all tasks.
        executor.shutdown(wait=True)
        self.finished_all.emit()

    def stop(self):
        self.is_running = False

class GradingTab(QWidget):
    def __init__(self):
        super().__init__()
        self.state = GlobalState()
        self.manager = ModelManager()
        self.worker = None 
        self.transfer_server = None # Init server placeholder
        self.init_ui()
        self.populate_models()
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.on_directory_changed)
        self.current_watched_folder = None
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Top: Controls
        hbox_ctrl = QHBoxLayout()
        
        # Model Selection
        self.cmb_models = QComboBox() 
        self.cmb_models.setMinimumWidth(200)
        self.cmb_models.currentIndexChanged.connect(self.on_model_selected)
        hbox_ctrl.addWidget(QLabel("Model:"))
        hbox_ctrl.addWidget(self.cmb_models)
        
        # Refresh Button
        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(30)
        btn_refresh.clicked.connect(self.populate_models)
        hbox_ctrl.addWidget(btn_refresh)
        
        hbox_ctrl.addSpacing(20)
        
        self.btn_load_folder = QPushButton("📂 Öğrenci Klasörü Seç")
        self.btn_load_folder.clicked.connect(self.load_student_folder)
        hbox_ctrl.addWidget(self.btn_load_folder)
        
        # Server Status Label
        self.lbl_server_status = QLabel("Mobil Sunucu: 🔴 Kapalı")
        self.lbl_server_status.setStyleSheet("color: #FF5555; font-weight: bold; margin-left: 20px;")
        hbox_ctrl.addWidget(self.lbl_server_status)
        
        self.lbl_folder = QLabel("Seçilen: Yok")
        # --- Teacher Prompt (New) ---
        prompt_layout = QVBoxLayout()
        prompt_layout.addWidget(QLabel("📝 Öğretmen Talimatları (AI için Ekstra Yönergeler):"))
        self.txt_teacher_prompt = QTextEdit()
        self.txt_teacher_prompt.setPlaceholderText("Örn: 'Bu bir 5.sınıf sınavıdır. Yazım hatalarını görmezden gel. Cevaplar İngilizce olmalı. Tam cümlelere artı puan ver.'")
        self.txt_teacher_prompt.setMaximumHeight(80)
        prompt_layout.addWidget(self.txt_teacher_prompt)
        
        layout.addLayout(prompt_layout)
        # ----------------------------
        
        self.btn_start = QPushButton("▶ Puanlamayı Başlat")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.start_grading)
        
        hbox_ctrl.addWidget(self.btn_load_folder)
        hbox_ctrl.addWidget(self.lbl_folder)
        hbox_ctrl.addStretch()
        hbox_ctrl.addWidget(self.btn_start)
        layout.addLayout(hbox_ctrl)
        
        # MAIN SPLITTER
        self.splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(self.splitter)
        
        # LEFT: Progress & Table
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0,0,0,0)
        
        self.progress_bar = QProgressBar()
        left_layout.addWidget(self.progress_bar)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Öğrenci", "Puan", "Durum", "İlerleme"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 120)
        left_layout.addWidget(self.table)
        
        self.splitter.addWidget(left_widget)
        
        # RIGHT: Live Log / Visual Feed
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0,0,0,0)
        
        right_layout.addWidget(QLabel("CANLI İZLEME EKRANI", styleSheet="font-weight:bold; color:#007acc;"))
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.log_container = QWidget()
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.addStretch()
        self.scroll_area.setWidget(self.log_container)
        
        right_layout.addWidget(self.scroll_area)
        self.splitter.addWidget(right_widget)
        self.splitter.setSizes([400, 600]) # Give more space to log
        
        self.student_files = []

    def populate_models(self):
        current = self.cmb_models.currentText()
        self.cmb_models.blockSignals(True)
        self.cmb_models.clear()
        self.cmb_models.addItem("Model Seçiniz...", None)
        
        models = self.manager.list_models()
        self.cmb_models.addItems(models)
        
        if current in models:
            self.cmb_models.setCurrentText(current)
            
        self.cmb_models.blockSignals(False)

    def on_model_selected(self):
        name = self.cmb_models.currentText()
        if not name or name == "Model Seçiniz...":
            self.state.reset() # clear state
            return
            
        # Load Model to State
        config, images = self.manager.load_model(name)
        if config and images:
            self.state.pdf_images = images # Template Images
            
            # Set Server Reference & Auto-Start
            set_reference_image(images[0])
            # Set Server Reference & Auto-Start
            set_reference_image(images[0])
            self.toggle_transfer_server(force_start=True)
            
            # Load Zones
            raw_zones = config.get("zones", {})
            self.state.zones = {int(k): v for k, v in raw_zones.items()}
            
            # Load Key Images (Visual Answer Key) if exists
            # Actually for Grading we need the TEXT or PDF Answer Key if provided separately?
            # In Phase 2 default, we might not have 'pdf_cevap_anahtari' (images) unless user saves it.
            # But we generated 'key.pdf' in save_model which is the visual key.
            # However, for OMR/Grading we need reference.
            
            # Use 'key.pdf' as answer key pdf if exists
            model_dir = os.path.join(self.manager.models_dir, name)
            key_path = os.path.join(model_dir, "key.pdf")
            if os.path.exists(key_path):
                with open(key_path, "rb") as f:
                    self.state.pdf_cevap_anahtari = f.read()
            else:
                self.state.pdf_cevap_anahtari = None # Fallback?
                
            print(f"DEBUG: Model '{name}' loaded. {len(images)} pages, {len(self.state.zones)} zone pages.")

    def load_student_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Öğrenci Klasörü (Root) Seç")
        if folder:
             self.process_loaded_folder(folder)

    def process_loaded_folder(self, folder):
        self.student_files = [] 
        
        items = os.listdir(folder)
        for item in items:
            full_path = os.path.join(folder, item)
            
            if os.path.isfile(full_path) and item.lower().endswith(".pdf"):
                self.student_files.append(full_path)
            elif os.path.isdir(full_path):
                imgs = [f for f in os.listdir(full_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                if imgs:
                    self.student_files.append(full_path)

        self.lbl_folder.setText(f"{len(self.student_files)} öğrenci (dosya/klasör) bulundu.")
        if self.student_files:
            self.btn_start.setEnabled(True)
            
        # Save Preference & Update Server
        settings = QSettings("NoteMaster", "Scanner")
        settings.setValue("LastStudentFolder", folder)
        
        # Update Server Path
        import logic.transfer_server as srv
        srv.UPLOAD_DIR = folder
        print(f"Sunucu Kayıt Klasörü Güncellendi: {folder}")
        
        # Setup Watcher
        if self.current_watched_folder:
            if self.current_watched_folder in self.watcher.directories():
                self.watcher.removePath(self.current_watched_folder)
        
        self.current_watched_folder = folder
        self.watcher.addPath(folder)

    def on_directory_changed(self, path):
        if path == self.current_watched_folder:
            # Refresh list without resetting server path or heavy logic
            self.student_files = [] 
            items = os.listdir(path)
            for item in items:
                full_path = os.path.join(path, item)
                if os.path.isfile(full_path) and item.lower().endswith(".pdf"):
                    self.student_files.append(full_path)
                elif os.path.isdir(full_path):
                    imgs = [f for f in os.listdir(full_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                    if imgs:
                        self.student_files.append(full_path)
            
            self.lbl_folder.setText(f"{len(self.student_files)} öğrenci (dosya/klasör) bulundu.")
            if self.student_files:
                self.btn_start.setEnabled(True)

    def check_api_key(self):
        # 1. Check Env
        if os.environ.get("GEMINI_API_KEY"):
            return True
        
        # 2. Check File
        secrets_path = "secrets.json"
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, "r") as f:
                    data = json.load(f)
                    key = data.get("gemini_api_key")
                    if key:
                        os.environ["GEMINI_API_KEY"] = key
                        return True
            except:
                pass

        # 3. Ask User
        key, ok = QInputDialog.getText(
            self, "API Anahtarı Eksik", 
            "Lütfen Google Gemini API Anahtarınızı giriniz:\n(Bu anahtar secrets.json dosyasına kaydedilecektir.)",
            QLineEdit.Password
        )
        if ok and key:
            os.environ["GEMINI_API_KEY"] = key.strip()
            # Save
            try:
                with open(secrets_path, "w") as f:
                    json.dump({"gemini_api_key": key.strip()}, f)
            except Exception as e:
                QMessageBox.warning(self, "Uyarı", f"Anahtar kaydedilemedi: {e}")
            return True
            
        return False

    def start_grading(self):
        if not self.check_api_key():
            QMessageBox.critical(self, "Hata", "Puanlama için API anahtarı gereklidir.")
            return

        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.btn_start.setEnabled(False)
        # Clear previous logs
        while self.log_layout.count() > 1: # Keep stretch
             item = self.log_layout.takeAt(0)
             if item.widget(): item.widget().deleteLater()
        # Start Worker
        teacher_notes = self.txt_teacher_prompt.toPlainText()
        # Assuming 'files', 'self.current_api_key', 'self.service_account_path' are defined elsewhere or will be defined by the user.
        # For now, using self.student_files for 'files' and placeholder for other new args.
        # The instruction snippet is slightly malformed, correcting 'update_progress)' to 'self.worker.progress.connect(self.update_progress)'
        # Start Worker
        teacher_notes = self.txt_teacher_prompt.toPlainText()
        
        # Explicitly get credentials
        if not self.check_api_key(): return
        
        api_key = os.environ.get("GEMINI_API_KEY", "")
        service_account_path = "service_account.json" 
        
        self.worker = GradingWorker(self.student_files, api_key, service_account_path, teacher_notes)
        self.worker.log_signal.connect(self.log) 
        self.worker.student_progress.connect(self.update_student_progress)
        self.worker.result_ready.connect(self.add_result_row)
        self.worker.live_update.connect(self.on_live_update) 
        self.worker.error_occurred.connect(lambda e: QMessageBox.critical(self, "Hata", e))
        self.worker.finished_all.connect(self.on_finished)
        self.worker.start()

    def update_student_progress(self, name, status, percent):
        # Find row
        row_idx = -1
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).text() == name:
                row_idx = r
                break
        
        if row_idx == -1:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(name))
            self.table.setItem(row_idx, 1, QTableWidgetItem("-")) # Score placeholder
            self.table.setItem(row_idx, 2, QTableWidgetItem(status))
            
            p_bar = QProgressBar()
            p_bar.setStyleSheet("QProgressBar { border: 1px solid grey; border-radius: 4px; text-align: center; } QProgressBar::chunk { background-color: #007acc; }")
            p_bar.setValue(percent)
            self.table.setCellWidget(row_idx, 3, p_bar)
        else:
            self.table.setItem(row_idx, 2, QTableWidgetItem(status))
            # Update Bar
            pb = self.table.cellWidget(row_idx, 3)
            if pb: pb.setValue(percent)

    def log(self, msg):
        # Placeholder if log method missing, or assume it exists
        # self.log_layout...
        lbl = QLabel(msg)
        self.log_layout.insertWidget(self.log_layout.count()-1, lbl)

    def on_live_update(self, data):
        # Create a card for this update
        card = QWidget()
        card_layout = QHBoxLayout(card)
        card.setStyleSheet("background-color: #333; border-radius: 8px; margin-bottom: 10px;")
        
        # --- IMAGES SECTION ---
        # We put images in a sub-layout
        imgs_widget = QWidget()
        imgs_layout = QHBoxLayout(imgs_widget)
        imgs_layout.setContentsMargins(0,0,0,0)
        
        # Helper to create Pixmap from CV2
        def cv2_to_pixmap(cv_img):
            import cv2
            from PyQt5.QtGui import QImage, QPixmap
            if cv_img is None: return None
            rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            # Scale if too big for card
            if w > 200: pix = pix.scaledToWidth(200)
            return pix

        # 1. Student Image
        if "student_crop" in data and data["student_crop"] is not None:
            lbl_s = QLabel()
            pix_s = cv2_to_pixmap(data["student_crop"])
            if pix_s: 
                lbl_s.setPixmap(pix_s)
                lbl_s.setToolTip("Öğrenci Cevabı")
                imgs_layout.addWidget(lbl_s)
                
        # 2. Key Image
        if "key_crop" in data and data["key_crop"] is not None:
            lbl_k = QLabel()
            pix_k = cv2_to_pixmap(data["key_crop"])
            if pix_k:
                lbl_k.setPixmap(pix_k)
                lbl_k.setToolTip("Cevap Anahtarı")
                # Add a separator or label?
                imgs_layout.addWidget(QLabel(" VS ", styleSheet="color:#888; font-weight:bold;"))
                imgs_layout.addWidget(lbl_k)
        
        card_layout.addWidget(imgs_widget)
        
        # --- TEXT INFO ---
        info_widget = QWidget()
        info_l = QVBoxLayout(info_widget)
        
        q_name = QLabel(f"<b>Soru:</b> {data['question']}")
        q_name.setStyleSheet("color: white; font-size: 14px;")
        info_l.addWidget(q_name)
        
        # Student Text
        s_txt = data.get('student_text', '?')
        s_ans = QLabel(f"<b>Öğrenci:</b> {s_txt}")
        s_ans.setStyleSheet("color: #ffa500;") # Orange
        info_l.addWidget(s_ans)
        
        # Correct Answer
        c_txt = data.get('correct_answer', '?')
        c_ans = QLabel(f"<b>Doğru:</b> {c_txt}")
        c_ans.setStyleSheet("color: #4caf50;") # Green
        info_l.addWidget(c_ans)
        
        reason = QLabel(f"<i>{data['reason']}</i>")
        reason.setStyleSheet("color: #ccc;")
        reason.setWordWrap(True)
        info_l.addWidget(reason)
        
        score_lbl = QLabel(f"<b>Puan: {data['score']}</b>")
        score_lbl.setStyleSheet("color: #0f0; font-size: 16px;")
        info_l.addWidget(score_lbl)
        
        card_layout.addWidget(info_widget)
        
        # Add to top of log
        self.log_layout.insertWidget(0, card)

    def add_result_row(self, res):
        name = res["filename"]
        row_idx = -1
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).text() == name:
                row_idx = r
                break
        
        if row_idx == -1:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(name))
            self.table.setItem(row_idx, 1, QTableWidgetItem("-")) 
            self.table.setItem(row_idx, 2, QTableWidgetItem(""))
            
            pb = QProgressBar()
            pb.setStyleSheet("QProgressBar { border: 1px solid grey; border-radius: 4px; text-align: center; } QProgressBar::chunk { background-color: #007acc; }")
            self.table.setCellWidget(row_idx, 3, pb)
            
        score_item = QTableWidgetItem(f"{res.get('total_score', 0):.2f}")
        score_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row_idx, 1, score_item)
        
        details = res.get("error", "Tamamlandı")
        if "zones" in res and not res.get("error"):
             details = "Tamamlandı" # Don't clutter UI with all zones, user can click for details if implemented later

        self.table.setItem(row_idx, 2, QTableWidgetItem(details))
        
        # Ensure bar is 100%
        pb = self.table.cellWidget(row_idx, 3)
        if pb: pb.setValue(100)

    def on_finished(self):
        self.btn_start.setEnabled(True)
        self.progress_bar.setFormat("Tamamlandı.")
        QMessageBox.information(self, "Tamamlandı", "Tüm dosyalar işlendi.")

    def log(self, message):
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("border-bottom: 1px solid #444; padding: 4px;")
        self.log_layout.insertWidget(0, lbl) # Add to top
    def log_server_msg(self, msg):
        self.log(f"[Server] {msg}")
        if "Sunucu Başlatıldı" in msg:
             try:
                 parts = msg.split(": ")
                 if len(parts) >= 2:
                     addr = parts[-1]
                     self.lbl_server_status.setText(f"Mobil Sunucu: 🟢 {addr}")
                     self.lbl_server_status.setStyleSheet("color: #55FF55; font-weight: bold; margin-left: 20px;")
             except: pass

    def toggle_transfer_server(self, force_start=True):
        if not self.transfer_server:
            self.transfer_server = transfer_server.TransferServer()
            self.transfer_server.signals.log.connect(self.log_server_msg)
            self.transfer_server.signals.status_update.connect(self.log)
            self.transfer_server.signals.image_received.connect(self.on_image_received)
        
        if force_start and not self.transfer_server.running:
            self.transfer_server.start()
        elif not force_start and self.transfer_server.running:
            self.transfer_server.stop()
            if hasattr(self, 'lbl_server_status'):
                self.lbl_server_status.setText("Mobil Sunucu: 🔴 Kapalı")
                self.lbl_server_status.setStyleSheet("color: #FF5555; font-weight: bold; margin-left: 20px;")

    def on_image_received(self, img, status):
        try:
            # Create Preview Card
            card = QWidget()
            card.setStyleSheet("background-color: #222; border: 1px solid #444; border-radius: 8px; margin: 5px;")
            l = QVBoxLayout(card)
            
            # Header
            color = "#4CAF50" if status == "aligned" else "#F44336"
            lbl_st = QLabel(f"Gelen Görüntü: {status.upper()}")
            lbl_st.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px;")
            l.addWidget(lbl_st)
            
            # Image
            if img is not None:
                # Resize for UI (Height 300)
                h, w = img.shape[:2]
                scale = 300 / h
                dim = (int(w * scale), 300)
                resized = cv2.resize(img, dim, interpolation=cv2.INTER_AREA)
                
                # CV2 to QPixmap
                rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pix = QPixmap.fromImage(qimg)
                
                lbl_img = QLabel()
                lbl_img.setPixmap(pix)
                lbl_img.setAlignment(Qt.AlignCenter)
                l.addWidget(lbl_img)
                
            self.log_layout.insertWidget(0, card)
        except Exception as e:
            print(f"Preview Error: {e}")

    def on_transfer_finished(self, path):
        self.selected_folder = path
        self.folder_label.setText(f"Seçilen: {path}")
        self.log(f"Otomatik olarak klasör seçildi: {path}")
        # Refresh file list if needed? For now just setting it is enough for 'Start Grading'
        QMessageBox.information(self, "Aktarım Tamamlandı", f"Dosyalar başarıyla alındı!\nKonum: {path}")
