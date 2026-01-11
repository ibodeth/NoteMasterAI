from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QSpinBox, QRadioButton, QButtonGroup, QDialogButtonBox, QLabel, QHBoxLayout

class ZoneDialog(QDialog):
    def __init__(self, parent=None, default_data=None):
        super().__init__(parent)
        self.setWindowTitle("Cevap Alanı Düzenle")
        self.resize(400, 300)
        
        self.data = default_data or {}
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # 1. Zone Name
        self.name_edit = QLineEdit(self.data.get("zone_name", ""))
        self.name_edit.setPlaceholderText("Örn: Soru 1")
        form.addRow("Soru Adı / ID:", self.name_edit)
        
        # 2. Zone Type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Klasik Soru", "Çoktan Seçmeli", "Doğru-Yanlış", 
                                "Boşluk Doldurma", "Eşleştirme", 
                                "Öğrenci Bilgisi", "Tanımsız", "AI Gerekli"])
        current_type = self.data.get("zone_type", "Çoktan Seçmeli")
        index = self.type_combo.findText(current_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        else:
             # Fallback if text differs slightly
             self.type_combo.setCurrentIndex(0)
             
        form.addRow("Soru Tipi:", self.type_combo)
        
        # 3. Dynamic Options (Num Options, Layout)
        self.options_spin = QSpinBox()
        self.options_spin.setRange(2, 10)
        self.options_spin.setValue(self.data.get("num_options", 5))
        form.addRow("Şık Sayısı:", self.options_spin)
        
        # Layout (Dikey/Yatay)
        self.layout_group = QButtonGroup(self)
        self.radio_dikey = QRadioButton("Dikey (Alt Alta)")
        self.radio_yatay = QRadioButton("Yatay (Yan Yana)")
        self.layout_group.addButton(self.radio_dikey)
        self.layout_group.addButton(self.radio_yatay)
        
        layout_hbox = QHBoxLayout()
        layout_hbox.addWidget(self.radio_dikey)
        layout_hbox.addWidget(self.radio_yatay)
        
        if self.data.get("layout", "dikey") == "dikey":
            self.radio_dikey.setChecked(True)
        else:
            self.radio_yatay.setChecked(True)
            
        form.addRow("Düzen:", layout_hbox)
        
        # 4. Teacher Note for AI
        self.ai_note = QLineEdit(self.data.get("ai_note", ""))
        self.ai_note.setPlaceholderText("AI için bu soruya özel not (örn: 'Sadece sayıya bak')")
        form.addRow("AI Notu:", self.ai_note)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Logic to enable/disable fields based on type
        self.type_combo.currentTextChanged.connect(self.update_fields)
        self.update_fields(self.type_combo.currentText())

    def update_fields(self, type_text):
        is_omr = type_text in ["Çoktan Seçmeli", "Doğru-Yanlış"]
        self.options_spin.setEnabled(is_omr)
        self.radio_dikey.setEnabled(is_omr)
        self.radio_yatay.setEnabled(is_omr)
        
        if type_text == "Doğru-Yanlış":
            self.options_spin.setValue(2)
            self.options_spin.setEnabled(False)

    def get_data(self):
        return {
            "zone_name": self.name_edit.text(),
            "zone_type": self.type_combo.currentText(),
            "num_options": self.options_spin.value(),
            "layout": "dikey" if self.radio_dikey.isChecked() else "yatay",
            "ai_note": self.ai_note.text()
        }
