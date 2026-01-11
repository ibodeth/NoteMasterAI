
DARK_THEME = """
QMainWindow {
    background-color: #1e1e1e;
    color: #ffffff;
}

QWidget {
    background-color: #1e1e1e;
    color: #ffffff;
    font-family: "Segoe UI", sans-serif;
    font-size: 14px;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #333333;
    background: #1e1e1e;
}
QTabBar::tab {
    background: #2d2d2d;
    border: 1px solid #333333;
    padding: 10px 20px;
    color: #aaaaaa;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #3d3d3d;
    color: #ffffff;
    border-bottom: 2px solid #007acc;
}
QTabBar::tab:hover {
    background: #333333;
}

/* Push Button */
QPushButton {
    background-color: #007acc;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    min-height: 20px;
}
QPushButton:hover {
    background-color: #0098ff;
}
QPushButton:pressed {
    background-color: #005c99;
}
QPushButton:disabled {
    background-color: #333333;
    color: #666666;
}

/* Secondary Button */
QPushButton#SecondaryButton {
    background-color: #3d3d3d;
    border: 1px solid #555555;
}
QPushButton#SecondaryButton:hover {
    background-color: #4d4d4d;
}

/* Inputs */
QLineEdit, QComboBox, QSpinBox {
    background-color: #2d2d2d;
    border: 1px solid #333333;
    padding: 6px;
    color: white;
    border-radius: 4px;
    selection-background-color: #007acc;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #007acc;
}

/* Labels */
QLabel {
    color: #dddddd;
}
QLabel#Header {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
    margin-bottom: 10px;
}
QLabel#SubHeader {
    font-size: 16px;
    font-weight: bold;
    color: #0098ff;
    margin-top: 10px;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #1e1e1e;
    width: 10px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background: #444444;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* GroupBox */
QGroupBox {
    border: 1px solid #333333;
    border-radius: 6px;
    margin-top: 20px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 10px;
    background-color: #1e1e1e;
    color: #0098ff;
}
"""
