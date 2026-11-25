"""
Unified visual theme for the ZarchCare app — matching the ZarchBlack identity
(dark neon purple/blue, KDE Plasma compatible).
"""

ZARCH_STYLESHEET = """
QWidget {
    background-color: #14101f;
    color: #e6e0ff;
    font-family: "Noto Sans", "Segoe UI", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #14101f;
}

QTabWidget::pane {
    border: 1px solid #3a2a5e;
    border-radius: 8px;
    background-color: #1b1530;
    top: -1px;
}

QTabBar::tab {
    background-color: #1e1836;
    color: #b8aee0;
    padding: 10px 20px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border: 1px solid #3a2a5e;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #2a1f4d;
    color: #ffffff;
    border-bottom: 2px solid #7c4dff;
}

QTabBar::tab:hover {
    background-color: #251c42;
}

QPushButton {
    background-color: #2a1f4d;
    color: #ffffff;
    border: 1px solid #7c4dff;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #3a2a6e;
    border: 1px solid #a685ff;
}

QPushButton:pressed {
    background-color: #1e1638;
}

QPushButton:disabled {
    background-color: #221c38;
    color: #6a6080;
    border: 1px solid #3a2a5e;
}

QPushButton#dangerButton {
    border: 1px solid #ff4d8d;
}
QPushButton#dangerButton:hover {
    background-color: #4d1f38;
}

QTextEdit, QPlainTextEdit, QListWidget, QTreeWidget {
    background-color: #0e0b1a;
    color: #cfe8ff;
    border: 1px solid #3a2a5e;
    border-radius: 6px;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 12px;
}

QLabel#sectionTitle {
    color: #7c4dff;
    font-size: 15px;
    font-weight: 700;
    padding: 4px 0;
}

QLabel#statusOk {
    color: #4dff9e;
    font-weight: 600;
}
QLabel#statusWarn {
    color: #ffd24d;
    font-weight: 600;
}
QLabel#statusError {
    color: #ff4d6a;
    font-weight: 600;
}

QProgressBar {
    border: 1px solid #3a2a5e;
    border-radius: 6px;
    text-align: center;
    background-color: #0e0b1a;
    color: #ffffff;
}
QProgressBar::chunk {
    background-color: #7c4dff;
    border-radius: 5px;
}

QCheckBox {
    spacing: 8px;
}

QScrollBar:vertical {
    background: #14101f;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #3a2a5e;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #7c4dff;
}

/* --- Sidebar navigation --- */
QListWidget#sidebar {
    background-color: #17122a;
    border: none;
    border-right: 1px solid #2a1f4d;
    outline: none;
    padding: 6px;
}
QListWidget#sidebar::item {
    color: #b8aee0;
    padding: 10px 12px;
    border-radius: 8px;
    margin: 2px 4px;
}
QListWidget#sidebar::item:selected {
    background-color: #2a1f4d;
    color: #ffffff;
    border: 1px solid #7c4dff;
}
QListWidget#sidebar::item:hover:!selected {
    background-color: #1e1836;
}

/* --- Dashboard stat cards --- */
QFrame#statCard {
    background-color: #1b1530;
    border: 1px solid #2a1f4d;
    border-radius: 10px;
}
QFrame#statCard:hover {
    border: 1px solid #7c4dff;
}

QFrame#healthBadge {
    background-color: #1b1530;
    border: 1px solid #2a1f4d;
    border-radius: 10px;
}

QLabel#brandTitle {
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
}
QLabel#brandSubtitle {
    color: #8f84b8;
    font-size: 11px;
}

/* --- Health Score Radial Gauge --- */
QFrame#healthGauge {
    background-color: #1b1530;
    border: 2px solid #2a1f4d;
    border-radius: 80px;
}
QFrame#healthGauge[health="excellent"] {
    border-color: #4dff9e;
}
QFrame#healthGauge[health="good"] {
    border-color: #a6ff9e;
}
QFrame#healthGauge[health="fair"] {
    border-color: #ffd24d;
}
QFrame#healthGauge[health="poor"] {
    border-color: #ffaa4d;
}
QFrame#healthGauge[health="critical"] {
    border-color: #ff4d6a;
}

QLabel#gaugeValue {
    color: #ffffff;
    font-size: 28px;
    font-weight: 700;
}
QLabel#gaugeLabel {
    color: #b8aee0;
    font-size: 12px;
}

/* --- Skeleton Loaders --- */
QFrame#skeleton {
    background-color: #1e1836;
    border-radius: 6px;
}
QFrame#skeletonCard {
    background-color: #1b1530;
    border: 1px solid #2a1f4d;
    border-radius: 10px;
}

/* --- Enhanced Focus States --- */
QWidget:focus {
    outline: 2px solid #7c4dff;
    outline-offset: 2px;
}

QPushButton:focus, QCheckBox:focus, QComboBox:focus, QSpinBox:focus {
    border: 2px solid #a685ff;
}

QListWidget#sidebar::item:focus {
    border: 2px solid #a685ff;
    background-color: #2a1f4d;
}

/* --- Status Bar Pills --- */
QWidget#statusPill {
    background-color: #1e1836;
    border-radius: 12px;
    padding: 4px 12px;
}
QWidget#statusPill[status="ok"] {
    border: 1px solid #4dff9e;
}
QWidget#statusPill[status="warn"] {
    border: 1px solid #ffd24d;
}
QWidget#statusPill[status="error"] {
    border: 1px solid #ff4d6a;
}
QWidget#statusPill[status="checking"] {
    border: 1px solid #7c4dff;
}

/* --- High Contrast Mode --- */
QWidget[highContrast="true"] {
    background-color: #000000;
    color: #ffffff;
}
QWidget[highContrast="true"] QFrame#statCard {
    background-color: #1a1a1a;
    border: 2px solid #ffffff;
}
QWidget[highContrast="true"] QFrame#statCard:hover {
    border-color: #00ffff;
}
QWidget[highContrast="true"] QPushButton {
    background-color: #000000;
    border: 2px solid #ffffff;
    color: #ffffff;
}
QWidget[highContrast="true"] QPushButton:hover {
    background-color: #333333;
    border-color: #00ffff;
}
QWidget[highContrast="true"] QListWidget#sidebar {
    background-color: #0a0a0a;
    border-right: 2px solid #ffffff;
}
QWidget[highContrast="true"] QListWidget#sidebar::item:selected {
    background-color: #ffffff;
    color: #000000;
    border: 2px solid #00ffff;
}
QWidget[highContrast="true"] QTextEdit,
QWidget[highContrast="true"] QPlainTextEdit,
QWidget[highContrast="true"] QListWidget,
QWidget[highContrast="true"] QTreeWidget {
    background-color: #0a0a0a;
    border: 2px solid #ffffff;
    color: #ffffff;
}
QWidget[highContrast="true"] QProgressBar {
    background-color: #0a0a0a;
    border: 2px solid #ffffff;
}
QWidget[highContrast="true"] QProgressBar::chunk {
    background-color: #00ffff;
}
QWidget[highContrast="true"] QScrollBar:vertical {
    background: #000000;
}
QWidget[highContrast="true"] QScrollBar::handle:vertical {
    background: #ffffff;
    border: 1px solid #ffffff;
}

/* --- Smooth Transitions --- */
QWidget {
    transition: background-color 150ms ease, border-color 150ms ease, color 150ms ease;
}
QFrame#statCard {
    transition: border-color 200ms ease, background-color 200ms ease;
}
QListWidget#sidebar::item {
    transition: background-color 150ms ease, border-color 150ms ease, color 150ms ease;
}
QPushButton {
    transition: background-color 150ms ease, border-color 150ms ease;
}

/* --- Page Transition Container --- */
QStackedWidget#pageStack {
    background-color: transparent;
}

/* --- System Info Cards --- */
QFrame#infoCard {
    background-color: #1b1530;
    border: 1px solid #2a1f4d;
    border-radius: 8px;
    padding: 12px;
}
QFrame#infoCard:hover {
    border-color: #7c4dff;
}
QLabel#infoCardIcon {
    font-size: 24px;
    color: #7c4dff;
}
QLabel#infoCardTitle {
    color: #b8aee0;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel#infoCardValue {
    color: #ffffff;
    font-size: 16px;
    font-weight: 600;
}

/* --- Settings Page --- */
QFrame#settingsSection {
    background-color: #1b1530;
    border: 1px solid #2a1f4d;
    border-radius: 10px;
    padding: 16px;
}
QLabel#settingsSectionTitle {
    color: #7c4dff;
    font-size: 14px;
    font-weight: 700;
    padding-bottom: 8px;
    border-bottom: 1px solid #2a1f4d;
    margin-bottom: 12px;
}

/* --- Service Manager --- */
QFrame#serviceCard {
    background-color: #1b1530;
    border: 1px solid #2a1f4d;
    border-radius: 8px;
    padding: 10px 12px;
}
QFrame#serviceCard[state="active"] {
    border-left: 3px solid #4dff9e;
}
QFrame#serviceCard[state="inactive"] {
    border-left: 3px solid #ff4d6a;
}
QFrame#serviceCard[state="failed"] {
    border-left: 3px solid #ffaa4d;
    background-color: #2a1828;
}
QFrame#serviceCard:hover {
    border-color: #7c4dff;
}

/* --- Report Export Button --- */
QPushButton#exportButton {
    background-color: #1e1638;
    border: 1px solid #7c4dff;
    padding: 10px 20px;
    font-size: 13px;
}
QPushButton#exportButton:hover {
    background-color: #2a1f4d;
    border-color: #a685ff;
}

/* --- Log Viewer --- */
QWidget#logViewer {
    background-color: #0e0b1a;
    border: 1px solid #3a2a5e;
    border-radius: 6px;
}
QComboBox#logFilter {
    background-color: #1b1530;
    border: 1px solid #3a2a5e;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e6e0ff;
}
QLineEdit#logSearch {
    background-color: #1b1530;
    border: 1px solid #3a2a5e;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e6e0ff;
}
QLineEdit#logSearch:focus {
    border-color: #7c4dff;
}

"""
