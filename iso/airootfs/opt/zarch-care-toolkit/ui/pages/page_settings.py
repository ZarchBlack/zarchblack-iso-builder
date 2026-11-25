"""
ui/pages/page_settings.py
=========================
Settings page for ZarchCare application.

v2.0 features:
  - Auto-refresh interval configuration
  - Theme selection (Dark / High Contrast)
  - Notification preferences
  - Log level configuration
  - Window geometry persistence
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QGroupBox, QFormLayout,
    QFrame, QScrollArea, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from core.settings import settings
from core.logger import get_logger
from ui.theme import ZARCH_STYLESHEET
from ui.worker_mixin import WorkerMixin

logger = get_logger(__name__)


class SettingsPage(QWidget, WorkerMixin):
    """Settings configuration page."""

    settings_changed = Signal()

    def __init__(self):
        super().__init__()
        self._workers: list = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── header ────────────────────────────────────────────────────────────
        header = QVBoxLayout()
        title = QLabel("Settings")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        subtitle = QLabel("Configure ZarchCare behavior and appearance")
        subtitle.setStyleSheet("color: #9d94c2;")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # ── Appearance Section ───────────────────────────────────────────────
        appearance_group = self._create_section("🎨  Appearance")
        appearance_form = QFormLayout()
        appearance_form.setSpacing(12)
        appearance_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Dark (Default)", "High Contrast"])
        self.combo_theme.setCurrentIndex(0 if not settings.high_contrast else 1)
        self.combo_theme.currentIndexChanged.connect(self._on_theme_changed)
        appearance_form.addRow("Theme:", self.combo_theme)

        self.check_animations = QCheckBox("Enable smooth transitions")
        self.check_animations.setChecked(settings.animations_enabled)
        self.check_animations.toggled.connect(self._on_animations_changed)
        appearance_form.addRow("", self.check_animations)

        appearance_group.setLayout(appearance_form)
        layout.addWidget(appearance_group)

        # ── Behavior Section ─────────────────────────────────────────────────
        behavior_group = self._create_section("⚙️  Behavior")
        behavior_form = QFormLayout()
        behavior_form.setSpacing(12)
        behavior_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.spin_refresh = QSpinBox()
        self.spin_refresh.setRange(60, 3600)
        self.spin_refresh.setSuffix(" seconds")
        self.spin_refresh.setValue(settings.auto_refresh_interval)
        self.spin_refresh.valueChanged.connect(self._on_refresh_changed)
        behavior_form.addRow("Auto-refresh interval:", self.spin_refresh)

        self.check_notifications = QCheckBox("Show desktop notifications")
        self.check_notifications.setChecked(settings.notifications_enabled)
        self.check_notifications.toggled.connect(self._on_notifications_changed)
        behavior_form.addRow("", self.check_notifications)

        self.check_minimize_tray = QCheckBox("Minimize to system tray")
        self.check_minimize_tray.setChecked(settings.minimize_to_tray)
        self.check_minimize_tray.toggled.connect(self._on_minimize_tray_changed)
        behavior_form.addRow("", self.check_minimize_tray)

        self.check_start_minimized = QCheckBox("Start minimized to tray")
        self.check_start_minimized.setChecked(settings.start_minimized)
        self.check_start_minimized.toggled.connect(self._on_start_minimized_changed)
        behavior_form.addRow("", self.check_start_minimized)

        behavior_group.setLayout(behavior_form)
        layout.addWidget(behavior_group)

        # ── Logging Section ──────────────────────────────────────────────────
        logging_group = self._create_section("📝  Logging")
        logging_form = QFormLayout()
        logging_form.setSpacing(12)
        logging_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.combo_log_level.setCurrentText(settings.log_level)
        self.combo_log_level.currentTextChanged.connect(self._on_log_level_changed)
        logging_form.addRow("Log level:", self.combo_log_level)

        self.btn_view_logs = QPushButton("📂  Open Log Folder")
        self.btn_view_logs.clicked.connect(self._open_log_folder)
        logging_form.addRow("", self.btn_view_logs)

        self.btn_clear_logs = QPushButton("🗑  Clear Logs")
        self.btn_clear_logs.setObjectName("dangerButton")
        self.btn_clear_logs.clicked.connect(self._clear_logs)
        logging_form.addRow("", self.btn_clear_logs)

        logging_group.setLayout(logging_form)
        layout.addWidget(logging_group)

        # ── Data Section ─────────────────────────────────────────────────────
        data_group = self._create_section("💾  Data & Privacy")
        data_form = QFormLayout()
        data_form.setSpacing(12)
        data_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.check_telemetry = QCheckBox("Allow anonymous usage statistics")
        self.check_telemetry.setChecked(settings.telemetry_enabled)
        self.check_telemetry.toggled.connect(self._on_telemetry_changed)
        data_form.addRow("", self.check_telemetry)

        self.btn_export_settings = QPushButton("📤  Export Settings")
        self.btn_export_settings.clicked.connect(self._export_settings)
        data_form.addRow("", self.btn_export_settings)

        self.btn_import_settings = QPushButton("📥  Import Settings")
        self.btn_import_settings.clicked.connect(self._import_settings)
        data_form.addRow("", self.btn_import_settings)

        self.btn_reset_settings = QPushButton("🔄  Reset to Defaults")
        self.btn_reset_settings.setObjectName("dangerButton")
        self.btn_reset_settings.clicked.connect(self._reset_settings)
        data_form.addRow("", self.btn_reset_settings)

        data_group.setLayout(data_form)
        layout.addWidget(data_group)

        # ── About Section ────────────────────────────────────────────────────
        about_group = self._create_section("ℹ️  About")
        about_layout = QVBoxLayout()
        about_layout.setSpacing(8)

        about_text = QLabel(
            "<b>ZarchCare v2.0</b> — ZarchBlack System Care<br>"
            "A comprehensive system maintenance and monitoring tool for ZarchBlack.<br><br>"
            "Built with Python 3 + PySide6 (Qt6)<br>"
            "License: MIT<br>"
            "Repository: <a href='https://github.com/zarchblack/zarchcare' style='color: #7c4dff;'>github.com/zarchblack/zarchcare</a>"
        )
        about_text.setWordWrap(True)
        about_text.setOpenExternalLinks(True)
        about_text.setStyleSheet("color: #b8aee0;")
        about_layout.addWidget(about_text)

        about_group.setLayout(about_layout)
        layout.addWidget(about_group)

        layout.addStretch()
        scroll.setWidget(content)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        # Load window geometry if saved
        if settings.window_geometry:
            try:
                self.window().restoreGeometry(settings.window_geometry)
            except Exception:
                pass

    def _create_section(self, title: str) -> QGroupBox:
        """Create a styled section group box."""
        group = QGroupBox(title)
        group.setObjectName("settingsSection")
        return group

    # ── Settings handlers ────────────────────────────────────────────────────

    def _on_theme_changed(self, index: int) -> None:
        settings.high_contrast = (index == 1)
        # Apply to entire application
        app = self.window()
        app.setProperty("highContrast", settings.high_contrast)
        app.style().unpolish(app)
        app.style().polish(app)
        # Recursively update all children
        self._update_all_widgets(app)
        logger.info("Theme changed: high_contrast=%s", settings.high_contrast)
        self.settings_changed.emit()

    def _update_all_widgets(self, widget):
        """Recursively update widget styles."""
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        for child in widget.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)

    def _on_animations_changed(self, enabled: bool) -> None:
        settings.animations_enabled = enabled
        logger.info("Animations: %s", "enabled" if enabled else "disabled")
        self.settings_changed.emit()

    def _on_refresh_changed(self, value: int) -> None:
        settings.auto_refresh_interval = value
        logger.info("Auto-refresh interval: %ds", value)
        self.settings_changed.emit()

    def _on_notifications_changed(self, enabled: bool) -> None:
        settings.notifications_enabled = enabled
        logger.info("Notifications: %s", "enabled" if enabled else "disabled")
        self.settings_changed.emit()

    def _on_minimize_tray_changed(self, enabled: bool) -> None:
        settings.minimize_to_tray = enabled
        logger.info("Minimize to tray: %s", "enabled" if enabled else "disabled")
        self.settings_changed.emit()

    def _on_start_minimized_changed(self, enabled: bool) -> None:
        settings.start_minimized = enabled
        logger.info("Start minimized: %s", "enabled" if enabled else "disabled")
        self.settings_changed.emit()

    def _on_log_level_changed(self, level: str) -> None:
        settings.log_level = level
        # Update logger level
        import logging
        root_logger = logging.getLogger("zarchcare")
        root_logger.setLevel(getattr(logging, level))
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(getattr(logging, level))
        logger.info("Log level changed to: %s", level)
        self.settings_changed.emit()

    def _on_telemetry_changed(self, enabled: bool) -> None:
        settings.telemetry_enabled = enabled
        logger.info("Telemetry: %s", "enabled" if enabled else "disabled")
        self.settings_changed.emit()

    # ── Actions ──────────────────────────────────────────────────────────────

    def _open_log_folder(self) -> None:
        import os
        log_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "zarchcare")
        if os.path.exists(log_dir):
            import subprocess
            subprocess.Popen(["xdg-open", log_dir])
        else:
            QMessageBox.information(self, "Log Folder", f"Log folder does not exist yet:\n{log_dir}")

    def _clear_logs(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear Logs",
            "Are you sure you want to delete all log files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            import os
            log_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "zarchcare")
            try:
                for f in os.listdir(log_dir):
                    if f.endswith(".log") or f.endswith(".log.1") or f.endswith(".log.2"):
                        os.remove(os.path.join(log_dir, f))
                QMessageBox.information(self, "Logs Cleared", "All log files have been deleted.")
                logger.info("Log files cleared by user")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear logs:\n{e}")
                logger.error("Failed to clear logs: %s", e)

    def _export_settings(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Settings",
            "zarchcare-settings.json",
            "JSON Files (*.json)"
        )
        if file_path:
            try:
                import json
                data = {
                    "high_contrast": settings.high_contrast,
                    "animations_enabled": settings.animations_enabled,
                    "auto_refresh_interval": settings.auto_refresh_interval,
                    "notifications_enabled": settings.notifications_enabled,
                    "minimize_to_tray": settings.minimize_to_tray,
                    "start_minimized": settings.start_minimized,
                    "log_level": settings.log_level,
                    "telemetry_enabled": settings.telemetry_enabled,
                    "last_page_index": settings.last_page_index,
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                QMessageBox.information(self, "Export Complete", f"Settings exported to:\n{file_path}")
                logger.info("Settings exported to: %s", file_path)
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export settings:\n{e}")
                logger.error("Settings export failed: %s", e)

    def _import_settings(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Settings",
            "",
            "JSON Files (*.json)"
        )
        if file_path:
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                settings.high_contrast = data.get("high_contrast", False)
                settings.animations_enabled = data.get("animations_enabled", True)
                settings.auto_refresh_interval = data.get("auto_refresh_interval", 120)
                settings.notifications_enabled = data.get("notifications_enabled", True)
                settings.minimize_to_tray = data.get("minimize_to_tray", False)
                settings.start_minimized = data.get("start_minimized", False)
                settings.log_level = data.get("log_level", "INFO")
                settings.telemetry_enabled = data.get("telemetry_enabled", False)

                # Update UI
                self.combo_theme.setCurrentIndex(1 if settings.high_contrast else 0)
                self.check_animations.setChecked(settings.animations_enabled)
                self.spin_refresh.setValue(settings.auto_refresh_interval)
                self.check_notifications.setChecked(settings.notifications_enabled)
                self.check_minimize_tray.setChecked(settings.minimize_to_tray)
                self.check_start_minimized.setChecked(settings.start_minimized)
                self.combo_log_level.setCurrentText(settings.log_level)
                self.check_telemetry.setChecked(settings.telemetry_enabled)

                # Apply theme
                self._on_theme_changed(self.combo_theme.currentIndex())

                QMessageBox.information(self, "Import Complete", "Settings imported successfully.")
                logger.info("Settings imported from: %s", file_path)
                self.settings_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Import Failed", f"Failed to import settings:\n{e}")
                logger.error("Settings import failed: %s", e)

    def _reset_settings(self) -> None:
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            settings.reset_to_defaults()

            # Update UI
            self.combo_theme.setCurrentIndex(0)
            self.check_animations.setChecked(True)
            self.spin_refresh.setValue(120)
            self.check_notifications.setChecked(True)
            self.check_minimize_tray.setChecked(False)
            self.check_start_minimized.setChecked(False)
            self.combo_log_level.setCurrentText("INFO")
            self.check_telemetry.setChecked(False)

            # Apply theme
            self._on_theme_changed(0)

            QMessageBox.information(self, "Settings Reset", "All settings have been reset to defaults.")
            logger.info("Settings reset to defaults")
            self.settings_changed.emit()