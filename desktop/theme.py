"""Warm paper and walnut visual system from the selected desktop mockup."""

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase


COLORS = {
    "background": "#B79B82",
    "walnut": "#895D45",
    "walnut_dark": "#65412F",
    "walnut_light": "#A87559",
    "paper": "#F2E7DB",
    "paper_light": "#FBF7F2",
    "line": "#D8BFA9",
    "ink": "#50362A",
    "muted": "#8A6C5B",
    "warning": "#F4D9A9",
}


def application_font() -> QFont:
    available = set(QFontDatabase.families())
    for family in ("Avenir Next", "Segoe UI", "Noto Sans", "Arial"):
        if family in available:
            return QFont(family, 11)
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    font.setPointSize(11)
    return font


STYLESHEET = """
QMainWindow, QWidget#root { background: #AD9077; color: #50362A; }
QWidget#settingsPanel { background: #AD9077; color: #50362A; }
QScrollArea#settingsScroll, QWidget#settingsScrollViewport,
QWidget#settingsScrollContent { background: #AD9077; border: 0; }
QFrame#settingsSurface { background: #F1E5D9; border: 1px solid #DDC9B7; border-radius: 19px; }
QFrame#settingsCard { background: transparent; border: 0; }
QFrame#settingsDivider { background: #DDC9B7; border: 0; }
QRadioButton#settingsModeRadio { color: #65412F; font-size: 19px; font-weight: 700; spacing: 10px; }
QFrame#settingsPrivacy { background: #F4D9A9; border-radius: 11px; }
QLabel#settingsTitle { color: #FFF8F1; font-size: 25px; font-weight: 700; }
QLabel#settingsCardTitle { color: #65412F; font-size: 19px; font-weight: 700; }
QLabel#settingsDescription { color: #826452; font-size: 12px; }
QLabel#settingsFieldLabel { color: #65412F; font-size: 12px; font-weight: 600; }
QLabel#settingsStatus { color: #866B5B; font-size: 11px; }
QLabel#settingsFooterNote { color: #FFF4E9; font-size: 11px; }
QLabel#settingsPrivacyText { color: #65412F; font-size: 13px; font-weight: 600; }
QWidget#settingsPanel > QLabel#settingsDescription { color: #FFF4E9; }
QWidget#settingsPanel QComboBox, QWidget#settingsPanel QLineEdit {
    background: #FBF7F2; color: #50362A; border: 1px solid #CFAF98;
    border-radius: 10px; padding: 8px 10px; min-height: 25px; font-size: 12px;
}
QWidget#settingsPanel QComboBox:disabled { background: #E9DDD2; color: #A48B7D; }
QWidget#settingsPanel QLineEdit:focus, QWidget#settingsPanel QComboBox:focus { border: 2px solid #A87559; }
QWidget#settingsPanel QComboBox::drop-down {
    subcontrol-origin: padding; subcontrol-position: top right;
    width: 30px; background: #FBF7F2; border: 0; border-left: 1px solid #DFC7B4;
    border-top-right-radius: 9px; border-bottom-right-radius: 9px;
}
QWidget#settingsPanel QComboBox:disabled::drop-down { background: #E9DDD2; }
QWidget#settingsPanel QComboBox QAbstractItemView {
    background: #FBF7F2; color: #50362A; border: 1px solid #CFAF98;
    selection-background-color: #E8D2C0; selection-color: #50362A;
}
QFrame#sidebar { background: #906149; border-radius: 20px; }
QFrame#topBar, QFrame#previewPanel, QFrame#reviewPanel {
    background: #F1E5D9; border: 1px solid #DDC9B7; border-radius: 19px;
}
QFrame#paperCard { background: #F5EDE5; border: 1px solid #D8BFA9; border-radius: 10px; }
QFrame#readerCard { background: #F8F1EA; border: 1px solid #D6BCA9; border-radius: 10px; }
QFrame#candidateRow { background: transparent; border-bottom: 1px solid #DDC9B7; }
QFrame#warningCard { background: #F4D9A9; border-radius: 12px; }
QFrame#warningCard QLabel { color: #65412F; }
QLabel#aiWarning { color: #65412F; background: #F4D9A9; border-radius: 10px;
    padding: 9px; font-size: 11px; }
QLabel#sidebarTitle { color: #FFF5E9; font-size: 15px; font-weight: 500; letter-spacing: 4px; }
QLabel#sectionTitle { color: #65412F; font-size: 15px; font-weight: 500; letter-spacing: 3px; }
QLabel#smallLabel { color: #8A6C5B; font-size: 11px; }
QLabel#sidebarLabel { color: #FFF5E9; font-size: 13px; }
QLabel#documentTitle { color: #65412F; font-size: 15px; font-weight: 600; }
QLabel#statusLabel { color: #65412F; font-size: 13px; }
QLabel#emptyText { color: #8A6C5B; font-size: 15px; }
QFrame#previewEmptyCard { background: #F8F1EA; border: 1px dashed #CDAE98; border-radius: 16px; }
QLabel#previewEmptyTitle { color: #65412F; font-size: 18px; font-weight: 600; }
QLabel#previewEmptyDescription { color: #8A6C5B; font-size: 13px; }
QLabel#candidateName { color: #895D45; background: #EBDCCD; font-size: 11px; min-width: 68px; padding: 6px; }
QLabel#candidateText { color: #50362A; font-size: 12px; }
QPushButton { border: 1px solid #D8BFA9; background: #F7EDE3; color: #65412F;
    padding: 9px 15px; border-radius: 10px; font-size: 12px; }
QPushButton:hover { background: #FFF7EF; border-color: #A87559; }
QPushButton:pressed { background: #E7D2BE; }
QPushButton:disabled { color: #A48B7D; background: #E9DDD2; border-color: #DFCDBF; }
QPushButton#primaryButton { background: #895D45; color: #FFF8F1; border-color: #895D45; font-weight: 600; }
QPushButton#primaryButton:hover { background: #76503C; }
QPushButton#primaryButton:disabled { background: #C9AE9D; border-color: #C9AE9D; color: #F4E9E1; }
QPushButton#sidebarButton { background: #F2E7DB; color: #65412F; border: 0; text-align: left; }
QPushButton#sidebarButton:hover { background: #FFF8F0; }
QPushButton#sidebarButton:disabled { background: #CBAF9D; color: #805E4C; }
QPushButton#iconButton { min-width: 34px; max-width: 34px; padding: 7px; }
QFrame#reviewPanel QPushButton { padding: 7px 5px; font-size: 11px; }
QPushButton#modeButton:checked { background: #895D45; border-color: #895D45;
    color: #FFF8F1; font-weight: 600; }
QPlainTextEdit#overviewText { font-size: 13px; line-height: 1.4; }
QListWidget { background: transparent; border: 0; outline: none; color: #FFF5E9; }
QListWidget::item { border-radius: 12px; padding: 5px; margin: 3px 0; }
QListWidget::item:hover { background: #9D7059; }
QListWidget::item:selected { background: #EEDBCB; color: #65412F; }
QListWidget#documentList::item { color: #FFF5E9; padding: 7px 4px; }
QListWidget#documentList::item:selected { background: #A67258; color: #FFF5E9; }
QListWidget#pageList::item { border-radius: 12px; padding: 8px; margin: 3px 0; }
QListWidget#reviewList { color: #65412F; }
QListWidget#reviewList::item:hover { background: #EBD9C8; }
QListWidget#reviewList::item:selected { background: #D5B69E; color: #50362A; }
QPlainTextEdit { background: #FBF7F2; color: #50362A; border: 1px solid #CFAF98;
    border-radius: 10px; padding: 10px; font-size: 14px; selection-background-color: #C99E81; }
QPlainTextEdit:focus { border: 2px solid #A87559; }
QScrollArea { border: 0; background: transparent; }
QProgressBar { border: 0; border-radius: 5px; background: #DDCBBB; height: 9px; text-align: center; }
QProgressBar::chunk { border-radius: 5px; background: #895D45; }
QToolTip { background: #FFF7EF; color: #50362A; border: 1px solid #D8BFA9; }
"""

CHEVRON_PATH = (Path(__file__).resolve().parent / "assets" / "chevron-down.svg").as_posix()
STYLESHEET += f"\nQWidget#settingsPanel QComboBox::down-arrow {{ image: url({CHEVRON_PATH}); width: 14px; height: 9px; }}\n"
