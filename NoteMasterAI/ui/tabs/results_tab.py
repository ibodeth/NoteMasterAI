import os
import sqlite3
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QListWidget, QSplitter, QScrollArea, QFrame, QDoubleSpinBox, 
                             QTextEdit, QFileDialog, QMessageBox, QLineEdit)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from logic import database

class QuestionResultWidget(QFrame):
    score_changed = pyqtSignal(int, float, str) # zone_db_id, new_score, note

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data # zone_result dict from DB
        self.init_ui()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("background-color: #ffffff; border-radius: 5px; margin-bottom: 10px;")

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header: Name | Score/Max
        header_layout = QHBoxLayout()
        lbl_name = QLabel(f"<b>{self.data['question_name']}</b> ({self.data['question_type']})")
        lbl_name.setStyleSheet("font-size: 14px; color: #2c3e50;") 
        
        current_score = self.data['teacher_correction'] if self.data['teacher_correction'] is not None else self.data['score']
        max_score = self.data['max_points']
        
        self.spin_score = QDoubleSpinBox()
        self.spin_score.setRange(0, max_score) 
        self.spin_score.setValue(float(current_score))
        self.spin_score.setSingleStep(0.25)
        self.spin_score.setSuffix(f" / {max_score}")
        self.spin_score.setStyleSheet("color: #000; background: #fff;")
        self.spin_score.valueChanged.connect(self.on_score_changed)
        
        if self.data.get('question_type') == "Öğrenci Bilgisi":
            self.spin_score.setEnabled(False)
            self.spin_score.setSuffix("")
        
        lbl_score_title = QLabel("Puan:")
        lbl_score_title.setStyleSheet("color: #2c3e50; font-weight: bold;")
        
        header_layout.addWidget(lbl_name)
        header_layout.addStretch()
        header_layout.addWidget(lbl_score_title)
        header_layout.addWidget(self.spin_score)
        
        layout.addLayout(header_layout)
        
        # Body: Images & Details
        body_layout = QHBoxLayout()
        
        # Images Column (Student vs Key)
        imgs_col = QVBoxLayout()
        
        # Student Image
        self.lbl_student_img = QLabel("Öğrenci Görseli Yok")
        self.lbl_student_img.setFixedSize(250, 100)
        self.lbl_student_img.setStyleSheet("border: 1px solid #ccc; background: #eaeaea; color: #555;")
        self.lbl_student_img.setAlignment(Qt.AlignCenter)
        imgs_col.addWidget(QLabel("<b>Öğrenci Yanıtı:</b>"))
        imgs_col.addWidget(self.lbl_student_img)
        
        # Key Image
        self.lbl_key_header = QLabel("<b>Cevap Anahtarı:</b>")
        self.lbl_key_img = QLabel("Anahtar Yok")
        self.lbl_key_img.setFixedSize(250, 100)
        self.lbl_key_img.setStyleSheet("border: 1px solid #ccc; background: #eaeaea; color: #555;")
        self.lbl_key_img.setAlignment(Qt.AlignCenter)
        
        imgs_col.addWidget(self.lbl_key_header)
        imgs_col.addWidget(self.lbl_key_img)
        
        body_layout.addLayout(imgs_col)
        
        # Text/Reason (Right)
        text_layout = QVBoxLayout()
        
        lbl_correct_title = QLabel("Doğru Cevap Metni:")
        lbl_correct_title.setStyleSheet("font-weight: bold; color: #27ae60;")
        self.txt_correct = QTextEdit(self.data.get('correct_answer', ''))
        self.txt_correct.setReadOnly(True)
        self.txt_correct.setMaximumHeight(40)
        self.txt_correct.setStyleSheet("background: #eafaf1; color: #333; border: 1px solid #c2e0ce;")
        
        lbl_ocr_title = QLabel("Öğrenci Yazısı (OCR):")
        lbl_ocr_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.txt_ocr = QTextEdit(self.data.get('student_text', ''))
        self.txt_ocr.setReadOnly(True)
        self.txt_ocr.setMaximumHeight(50)
        self.txt_ocr.setStyleSheet("background: #fdfdfd; color: #333; border: 1px solid #ccc;")
        
        lbl_reason_title = QLabel("AI Değerlendirmesi:")
        lbl_reason_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.lbl_reason = QLabel(self.data.get('ai_reason', ''))
        self.lbl_reason.setWordWrap(True)
        self.lbl_reason.setStyleSheet("background: #f0f4f8; padding: 6px; border-radius: 4px; color: #333; border: 1px solid #dceefc;")
        
        text_layout.addWidget(lbl_correct_title)
        text_layout.addWidget(self.txt_correct)
        text_layout.addWidget(lbl_ocr_title)
        text_layout.addWidget(self.txt_ocr)
        text_layout.addWidget(lbl_reason_title)
        text_layout.addWidget(self.lbl_reason)
        
        body_layout.addLayout(text_layout)
        layout.addLayout(body_layout)
        
        # Footer: Teacher Note
        note_layout = QHBoxLayout()
        lbl_note = QLabel("Not:")
        lbl_note.setStyleSheet("color: #2c3e50;")
        
        self.inp_note = QLineEdit(self.data.get('teacher_note', ''))
        self.inp_note.setPlaceholderText("Öğretmen notu...")
        self.inp_note.setStyleSheet("color: #000; background: #fff;")
        
        note_layout.addWidget(lbl_note)
        note_layout.addWidget(self.inp_note)
        layout.addLayout(note_layout)
        
    def set_images(self, student_path, key_path):
        # Student Image
        if student_path and os.path.exists(student_path):
            pix = QPixmap(student_path)
            self.lbl_student_img.setPixmap(pix.scaled(
                self.lbl_student_img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        else:
            self.lbl_student_img.setText("Görsel Bulunamadı")
            
        # Key Image
        if key_path and os.path.exists(key_path):
            pix = QPixmap(key_path)
            self.lbl_key_img.setPixmap(pix.scaled(
                self.lbl_key_img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
            self.lbl_key_img.setVisible(True)
            self.lbl_key_header.setVisible(True)
        else:
            self.lbl_key_img.setVisible(False)
            self.lbl_key_header.setVisible(False)

    def on_score_changed(self, val):
        note = self.inp_note.text()
        z_id = self.data.get('id')
        if z_id:
            self.score_changed.emit(z_id, val, note)

class ResultsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = None
        self.students = []
        self.current_results = []
        self.current_q_index = 0
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.btn_load = QPushButton("📂 Veritabanı Aç (grading_results.db)")
        self.btn_load.clicked.connect(self.load_database)
        toolbar.addWidget(self.btn_load)
        
        self.lbl_db_status = QLabel("Veritabanı seçilmedi")
        toolbar.addWidget(self.lbl_db_status)
        
        toolbar.addStretch()
        
        self.btn_export = QPushButton("📄 PDF Rapor Al")
        self.btn_export.clicked.connect(self.export_pdf) # Connect
        self.btn_export.setEnabled(False)
        toolbar.addWidget(self.btn_export)
        
        main_layout.addLayout(toolbar)
        
        # ... (rest of init_ui logic same)
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Student List
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("<b>Öğrenciler</b>"))
        self.list_students = QListWidget()
        self.list_students.itemClicked.connect(self.on_student_selected)
        left_layout.addWidget(self.list_students)
        splitter.addWidget(left_widget)
        
        # Right: Details
        # Right: Details (Single Question Mode)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Student Header (Name | Class | Number)
        # Student Header (Editable)
        header_form = QWidget()
        form_layout = QHBoxLayout(header_form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Öğrenci Adı")
        self.inp_name.setStyleSheet("font-size: 16px; font-weight: bold; margin: 5px;")
        
        self.inp_class = QLineEdit()
        self.inp_class.setPlaceholderText("Sınıf")
        self.inp_class.setFixedWidth(80)
        
        self.inp_number = QLineEdit()
        self.inp_number.setPlaceholderText("No")
        self.inp_number.setFixedWidth(80)
        
        btn_save_meta = QPushButton("💾")
        btn_save_meta.setToolTip("Bilgileri Kaydet")
        btn_save_meta.clicked.connect(self.save_student_metadata_ui)
        
        form_layout.addWidget(self.inp_name)
        form_layout.addWidget(self.inp_class)
        form_layout.addWidget(self.inp_number)
        form_layout.addWidget(btn_save_meta)
        
        right_layout.addWidget(header_form)
        
        # Header Images (Student Info Crops)
        self.header_images_scroll = QScrollArea()
        self.header_images_scroll.setWidgetResizable(True)
        self.header_images_scroll.setFixedHeight(120) # Limit height
        self.header_images_scroll.setVisible(False) # Hide if empty
        
        self.header_images_widget = QWidget()
        self.header_images_layout = QHBoxLayout(self.header_images_widget)
        self.header_images_scroll.setWidget(self.header_images_widget)
        
        right_layout.addWidget(self.header_images_scroll)
        
        # Container for Current Question Item
        self.question_container = QVBoxLayout()
        right_layout.addLayout(self.question_container)
        
        right_layout.addStretch() # Push Nav to bottom
        
        # Navigation
        nav_layout = QHBoxLayout()
        self.btn_prev_q = QPushButton("← Önceki Soru")
        self.btn_prev_q.clicked.connect(self.prev_question)
        self.btn_next_q = QPushButton("Sonraki Soru →")
        self.btn_next_q.clicked.connect(self.next_question)
        
        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_prev_q)
        nav_layout.addWidget(QLabel(" | "))
        nav_layout.addWidget(self.btn_next_q)
        nav_layout.addStretch()
        
        right_layout.addLayout(nav_layout)

        # Total Score Display
        self.footer_score_layout = QHBoxLayout()
        self.lbl_final_total = QLabel("Toplam Puan: 0")
        self.lbl_final_total.setStyleSheet("font-size: 16px; font-weight: bold; color: blue;")
        self.footer_score_layout.addStretch()
        self.footer_score_layout.addWidget(self.lbl_final_total)
        right_layout.addLayout(self.footer_score_layout)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([250, 750]) # Ratio
        
        main_layout.addWidget(splitter)
        
    def export_pdf(self):
        if not self.students or not self.db_path:
            return
            
        save_path, _ = QFileDialog.getSaveFileName(self, "PDF Kaydet", "Sinif_Listesi.pdf", "PDF Files (*.pdf)")
        if not save_path:
            return
            
        from PyQt5.QtGui import QTextDocument
        from PyQt5.QtPrintSupport import QPrinter
        
        # Generate HTML Table
        html = """
        <h1 style='text-align: center;'>Sınıf Sınav Sonuç Listesi</h1>
        <table border='1' cellspacing='0' cellpadding='5' width='100%'>
            <tr style='background-color: #f2f2f2;'>
                <th>Sınıf</th>
                <th>No</th>
                <th>Öğrenci Adı</th>
                <th>Toplam Puan</th>
                <th>Notlar</th>
            </tr>
        """
        
        # Re-fetch latest data to be sure
        fresh_students = database.get_all_results(self.db_path)
        
        for s in fresh_students:
            cls = s.get('class_name', '') or ''
            num = s.get('student_number', '') or ''
            note = s.get('teacher_note', '') or ''
            
            html += f"""
            <tr>
                <td>{cls}</td>
                <td>{num}</td>
                <td>{s['name']}</td>
                <td style='text-align: center;'><b>{s['total_score']:.2f}</b></td>
                <td>{note}</td>
            </tr>
            """
            
        html += "</table>"
        
        doc = QTextDocument()
        doc.setHtml(html)
        
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(save_path)
        
        doc.print_(printer)
        QMessageBox.information(self, "Başarılı", f"PDF Raporu kaydedildi:\n{save_path}")
        
    def load_database(self):
        path, _ = QFileDialog.getOpenFileName(self, "Veritabanı Seç", "", "SQLite Files (*.db)")
        if not path: return
        
        self.db_path = path
        self.lbl_db_status.setText(os.path.basename(path))
        self.btn_export.setEnabled(True)
        self.refresh_student_list()
        
    def refresh_student_list(self):
        self.list_students.clear()
        self.students = database.get_all_results(self.db_path)
        
        for s in self.students:
            score = s['total_score']
            self.list_students.addItem(f"{s['name']}  ({score:.1f})")
            
    def on_student_selected(self, item):
        idx = self.list_students.row(item)
        if idx < 0: return
        
        student = self.students[idx]
        self.load_student_details(student)
        
    def load_student_details(self, student):
        name = student['name']
        cls = student.get('class_name', '')
        num = student.get('student_number', '')
        self.current_student_id = student['id']
        
        self.inp_name.setText(name)
        self.inp_class.setText(cls)
        self.inp_number.setText(num)
        
        self.inp_class.setText(cls)
        self.inp_number.setText(num)
        
        # Load Questions
        crops_root = os.path.join(os.path.dirname(self.db_path), "crops")
        all_results = student.get('results', [])
        
        # Filter: Separate Info Zones vs Questions
        self.current_results = []
        info_zones = []
        
        for res in all_results:
            if res.get('question_type') == "Öğrenci Bilgisi":
                info_zones.append(res)
            else:
                self.current_results.append(res)
        
        self.current_q_index = 0
        
        # Display Info Images
        # Clear old
        while self.header_images_layout.count():
            child = self.header_images_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        if info_zones:
            self.header_images_scroll.setVisible(True)
            for iz in info_zones:
                 # Create simple label for image
                 lbl = QLabel()
                 lbl.setFixedSize(200, 100)
                 lbl.setStyleSheet("border: 1px solid #ccc; background: #eee;")
                 lbl.setAlignment(Qt.AlignCenter)
                 
                 rel_path = iz.get('crop_path')
                 if rel_path:
                     full_p = os.path.join(crops_root, rel_path)
                     if os.path.exists(full_p):
                         pix = QPixmap(full_p)
                         lbl.setPixmap(pix.scaled(lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                     else:
                         lbl.setText("Görsel Yok")
                 else:
                     lbl.setText("Yol Yok")
                 
                 self.header_images_layout.addWidget(lbl)
            self.header_images_layout.addStretch()
        else:
            self.header_images_scroll.setVisible(False)
        
        self.lbl_final_total.setText(f"Toplam Puan: {student['total_score']:.2f}")
        
        self.show_current_question()
        
    def save_student_metadata_ui(self):
        if not hasattr(self, 'current_student_id') or not self.db_path:
            return
            
        new_name = self.inp_name.text()
        new_class = self.inp_class.text()
        new_num = self.inp_number.text()
        
        database.update_student_metadata(self.db_path, self.current_student_id, new_name, new_num, new_class)
        QMessageBox.information(self, "Bilgi", "Öğrenci bilgileri güncellendi.")
        self.refresh_student_list() # Update name in list
        
    def show_current_question(self):
        # Clear container
        while self.question_container.count():
             child = self.question_container.takeAt(0)
             if child.widget(): child.widget().deleteLater()
             
        if not self.current_results:
            # self.lbl_student_header.setText("Sonuç Bulunamadı") # Removed undefined
            return
            
        # Bounds check
        if self.current_q_index < 0: self.current_q_index = 0
        if self.current_q_index >= len(self.current_results): self.current_q_index = len(self.current_results) - 1
        
        res = self.current_results[self.current_q_index]
        
        # Create Widget
        w = QuestionResultWidget(res)
        w.score_changed.connect(self.handle_score_update)
        
        # Resolve images
        crops_root = os.path.join(os.path.dirname(self.db_path), "crops")
        
        # Student Crop
        s_rel = res.get('crop_path')
        full_s = os.path.join(crops_root, s_rel) if s_rel else None
        
        # Key Crop
        k_rel = res.get('key_crop_path')
        full_k = os.path.join(crops_root, k_rel) if k_rel else None
        
        w.set_images(full_s, full_k)
            
        self.question_container.addWidget(w)
        
        # Update Buttons
        self.btn_prev_q.setEnabled(self.current_q_index > 0)
        self.btn_next_q.setEnabled(self.current_q_index < len(self.current_results) - 1)
        
    def prev_question(self):
        if self.current_q_index > 0:
            self.current_q_index -= 1
            self.show_current_question()
            
    def next_question(self):
        if self.current_q_index < len(self.current_results) - 1:
            self.current_q_index += 1
            self.show_current_question()
        
    def handle_score_update(self, zone_id, new_score, note=""):
        if not self.db_path: return
        
        # 1. Update DB (Zone)
        # Note: We are setting teacher_correction. 
        # But we also passed 'note' from widget.
        database.update_zone_score(self.db_path, zone_id, new_score, note)
        
        # 2. Recalc Total
        # We need student ID. We can get it from the current student object we are viewing.
        # But safer to query DB or use cached list index.
        # Let's rely on database.recalculate_student_total returning the new total.
        
        # Get student_id from zone_id ? OR just use current selected student?
        # Since we are in detail view of a student, we know the student.
        # However, `database.recalculate_student_total` expects student_id.
        
        # Helper to find student_id from zone_id
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT student_id FROM zone_results WHERE id = ?", (zone_id,))
        row = c.fetchone()
        conn.close()
        
        if not row: return
        sid = row[0]
        
        new_total = database.recalculate_student_total(self.db_path, sid)
        
        # 3. GUI Update (Total Label)
        self.lbl_final_total.setText(f"Toplam Puan: {new_total:.2f}")
        
        # 4. Update Local Cache (CRITICAL FIX)
        # We must update self.current_results so next/prev buttons show new score.
        # Find result by ID
        for res in self.current_results:
            if res.get('id') == zone_id:
                res['teacher_correction'] = new_score
                res['teacher_note'] = note
                break
        
        # 5. Update List Item Text
        # Iterate to find item with this student name/id
        # Our list items are simple strings "Name (Score)".
        # We should probably store ID in UserRole to be robust.
        # I'll check if I added the UserRole storage in previous step (I tried but maybe it failed).
        # If not, I'll fallback to matching selected row.
        
        cur_row = self.list_students.currentRow()
        if cur_row >= 0:
            item = self.list_students.item(cur_row)
            # Assuming the selected student IS the one we are editing.
            # Update text
            # Format: "Name  (Score)"
            old_text = item.text()
            name_part = old_text.rsplit("(", 1)[0].strip()
            item.setText(f"{name_part}  ({new_total:.2f})")
