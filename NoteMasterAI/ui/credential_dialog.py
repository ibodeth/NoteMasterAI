
import os
import json
import shutil
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QFileDialog, QMessageBox, QFormLayout, QHBoxLayout, QFrame)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QFont

SECRETS_FILE = "secrets.json"

class CredentialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NoteMaster - Kurulum Sihirbazı")
        self.setFixedSize(500, 350)
        self.setModal(True)
        self.setup_ui()
        self.load_existing()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header
        lbl_title = QLabel("Hoş Geldiniz! 🚀")
        lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #007acc;")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_desc = QLabel("NoteMaster'ı kullanabilmek için lütfen aşağıdaki Google API bilgilerini giriniz.\nBu işlem sadece bir kez yapılacaktır.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #cccccc;")
        lbl_desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_desc)

        layout.addSpacing(10)

        # Form
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # 1. Gemini API Key
        self.inp_api_key = QLineEdit()
        self.inp_api_key.setPlaceholderText("AI-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        self.inp_api_key.setEchoMode(QLineEdit.Password)
        self.inp_api_key.setStyleSheet("padding: 8px;")
        
        lbl_key = QLabel("Gemini API Anahtarı:")
        lbl_key.setStyleSheet("font-weight: bold;")
        form_layout.addRow(lbl_key, self.inp_api_key)

        # 2. Service Account
        self.inp_sa_path = QLineEdit()
        self.inp_sa_path.setPlaceholderText("service-account.json dosya yolu...")
        self.inp_sa_path.setReadOnly(True)
        self.inp_sa_path.setStyleSheet("padding: 8px; background-color: #2d2d30;")

        btn_browse = QPushButton("📁")
        btn_browse.setFixedSize(40, 35)
        btn_browse.clicked.connect(self.browse_sa_file)

        sa_layout = QHBoxLayout()
        sa_layout.addWidget(self.inp_sa_path)
        sa_layout.addWidget(btn_browse)

        lbl_sa = QLabel("Google Vision Dosyası:")
        lbl_sa.setStyleSheet("font-weight: bold;")
        form_layout.addRow(lbl_sa, sa_layout)

        layout.addLayout(form_layout)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_save = QPushButton("✅ Kaydet ve Başla")
        self.btn_save.setFixedHeight(45)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #28a745; 
                color: white; 
                font-size: 14px; 
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #218838; }
        """)
        self.btn_save.clicked.connect(self.validate_and_save)

        btn_exit = QPushButton("Çıkış")
        btn_exit.setFixedHeight(45)
        btn_exit.setStyleSheet("background-color: #d9534f; color: white; border-radius: 5px;")
        btn_exit.clicked.connect(self.reject)

        btn_layout.addWidget(btn_exit)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)

    def browse_sa_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Service Account JSON Seç", "", "JSON Files (*.json)")
        if f:
            self.inp_sa_path.setText(f)

    def load_existing(self):
        if os.path.exists(SECRETS_FILE):
            try:
                with open(SECRETS_FILE, "r") as f:
                    data = json.load(f)
                    self.inp_api_key.setText(data.get("gemini_api_key", ""))
                    
                    # Check saved path
                    saved_sa = data.get("service_account_path", "")
                    if saved_sa and os.path.exists(saved_sa):
                        self.inp_sa_path.setText(saved_sa)
                    elif os.path.exists("service-account.json"):
                         self.inp_sa_path.setText(os.path.abspath("service-account.json"))
            except:
                pass

    def validate_and_save(self):
        key = self.inp_api_key.text().strip()
        sa_path = self.inp_sa_path.text().strip()

        if not key:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen Gemini API Anahtarını giriniz.")
            return
        
        if not sa_path or not os.path.exists(sa_path):
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen geçerli bir Service Account JSON dosyası seçiniz.")
            return

        # Prepare for save
        # We can copy the service account to app dir for convenience, OR just save the path.
        # Implementation Plan said "save them". User asked "service account konumunu da sorsun".
        # Let's save the path to secrets.json.
        
        try:
            data = {
                "gemini_api_key": key,
                "service_account_path": sa_path
            }
            
            with open(SECRETS_FILE, "w") as f:
                json.dump(data, f, indent=4)
                
            QMessageBox.information(self, "Başarılı", "Kurulum tamamlandı! Uygulama başlatılıyor...")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Ayarlar kaydedilemedi:\n{e}")

def check_credentials_at_startup():
    """
    Checks if secrets.json exists and is valid.
    If not, enters loop showing CredentialDialog.
    Returns True if valid, False if user cancelled.
    """
    
    # 1. Check if valid already
    if is_config_valid():
        return True
        
    # 2. Show Dialog
    dlg = CredentialDialog()
    if dlg.exec_() == QDialog.Accepted:
        return is_config_valid() # Re-check
        
    return False

def is_config_valid():
    if not os.path.exists(SECRETS_FILE): return False
    try:
        with open(SECRETS_FILE, "r") as f:
            data = json.load(f)
            key = data.get("gemini_api_key")
            path = data.get("service_account_path")
            
            if not key: return False
            if not path or not os.path.exists(path): return False
            
            # Allow environment setting
            os.environ["GEMINI_API_KEY"] = key
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path # Grading uses this or passed arg
            return True
    except:
        return False
