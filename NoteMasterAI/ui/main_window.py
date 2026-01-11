from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel
from PyQt5.QtGui import QIcon
from ui.styles import DARK_THEME

from ui.tabs.teaching_tab import TeachingTab
from ui.tabs.verification_tab import VerificationTab
from ui.tabs.grading_tab import GradingTab
from ui.tabs.results_tab import ResultsTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("NoteMasterAI - Desktop Edition")
        self.resize(1200, 800)
        self.setStyleSheet(DARK_THEME)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Header
        header = QLabel("NoteMasterAI")
        header.setObjectName("Header")
        main_layout.addWidget(header)
        
        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Add Tabs
        self.teaching_tab = TeachingTab()
        self.verification_tab = VerificationTab()
        self.tab_grading = GradingTab()
        self.tab_results = ResultsTab()
        
        self.tabs.addTab(self.teaching_tab, "1. Şablon Oluşturma")
        self.tabs.addTab(self.verification_tab, "2. Kontrol ve Onay")
        self.tabs.addTab(self.tab_grading, "3. Notlandırma")
        self.tabs.addTab(self.tab_results, "4. Sonuçlar (İnceleme)")
