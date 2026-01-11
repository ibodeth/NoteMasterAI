import sys
import os
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    # High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    
    # Modern font
    # font = app.font()
    # font.setFamily("Segoe UI")
    # app.setFont(font)
    
    # Credential Check
    from ui.credential_dialog import check_credentials_at_startup
    if not check_credentials_at_startup():
        print("Kurulum tamamlanmadı veya iptal edildi.")
        sys.exit(0)

    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
