"""
ui/widgets_common.py
Reusable small widgets: stat cards for the dashboard, and status-bar pills.
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt


class StatCard(QFrame):
    """A single dashboard tile: icon + label + big value + optional progress bar."""

    def __init__(self, icon: str, label: str, accent: str = "#7c4dff"):
        super().__init__()
        self.setObjectName("statCard")
        self.accent = accent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        header = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 18px;")
        header.addWidget(icon_lbl)
        header.addStretch()
        layout.addLayout(header)

        self.label_lbl = QLabel(label)
        self.label_lbl.setStyleSheet("color: #9d94c2; font-size: 12px;")
        layout.addWidget(self.label_lbl)

        self.value_lbl = QLabel("—")
        self.value_lbl.setStyleSheet(f"color: {accent}; font-size: 22px; font-weight: 700;")
        layout.addWidget(self.value_lbl)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {accent}; }}"
        )
        self.progress.hide()
        layout.addWidget(self.progress)
        layout.addStretch()

    def set_value(self, text: str):
        self.value_lbl.setText(text)

    def set_progress(self, percent: float):
        self.progress.show()
        self.progress.setValue(int(max(0, min(100, percent))))


class Pill(QLabel):
    """Small rounded status indicator for the bottom status bar."""

    def __init__(self, text: str, color: str = "#4dff9e"):
        super().__init__(text)
        self.setStyleSheet(
            f"background-color: #1e1836; color: {color}; border: 1px solid {color};"
            "border-radius: 10px; padding: 3px 12px; font-size: 11px; font-weight: 600;"
        )


class HealthBadge(QFrame):
    """Health score badge shown at the top of the sidebar."""

    def __init__(self):
        super().__init__()
        self.setObjectName("healthBadge")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.icon_lbl = QLabel("♥")
        self.icon_lbl.setStyleSheet("color: #ff4d8d; font-size: 14px;")
        layout.addWidget(self.icon_lbl)
        self.text_lbl = QLabel("Health")
        self.text_lbl.setStyleSheet("color: #b8aee0; font-size: 12px;")
        layout.addWidget(self.text_lbl)
        layout.addStretch()
        self.score_lbl = QLabel("—/100")
        self.score_lbl.setStyleSheet("color: #4dff9e; font-size: 13px; font-weight: 700;")
        layout.addWidget(self.score_lbl)

    def set_score(self, score: int):
        self.score_lbl.setText(f"{score}/100")
        if score >= 80:
            color = "#4dff9e"
        elif score >= 50:
            color = "#ffd24d"
        else:
            color = "#ff4d6a"
        self.score_lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 700;")
