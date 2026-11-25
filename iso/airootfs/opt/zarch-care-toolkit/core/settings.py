"""
core/settings.py
================
Persistent application settings backed by QSettings (uses the system's
native settings storage — ~/.config/ZarchCare/ZarchCare.conf on Linux).

Usage:
    from core.settings import settings
    interval = settings.auto_refresh_interval
    settings.auto_refresh_interval = 300
"""

from __future__ import annotations
from PySide6.QtCore import QSettings
from core.logger import get_logger

logger = get_logger(__name__)

# Application identity must match what QApplication uses
_ORG  = "ZarchCare"
_APP  = "ZarchCare"


class AppSettings:
    """
    Thin wrapper around QSettings providing typed property accessors.
    All properties have safe defaults if the key has never been saved.
    """

    def __init__(self) -> None:
        self._qs = QSettings(_ORG, _APP)
        logger.debug("AppSettings loaded from: %s", self._qs.fileName())

    # ── auto-refresh ──────────────────────────────────────────────────────────

    @property
    def auto_refresh_interval(self) -> int:
        """
        Dashboard auto-refresh interval in seconds.
        0 = disabled (default).  Minimum meaningful value: 60.
        """
        return int(self._qs.value("dashboard/auto_refresh_interval", 0))

    @auto_refresh_interval.setter
    def auto_refresh_interval(self, value: int) -> None:
        self._qs.setValue("dashboard/auto_refresh_interval", max(0, int(value)))
        self._qs.sync()

    # ── window geometry ───────────────────────────────────────────────────────

    @property
    def window_geometry(self) -> bytes | None:
        raw = self._qs.value("window/geometry")
        return bytes(raw) if raw else None

    @window_geometry.setter
    def window_geometry(self, data: bytes) -> None:
        self._qs.setValue("window/geometry", data)
        self._qs.sync()

    # ── last page visited ─────────────────────────────────────────────────────

    @property
    def last_page_index(self) -> int:
        return int(self._qs.value("window/last_page_index", 0))

    @last_page_index.setter
    def last_page_index(self, index: int) -> None:
        self._qs.setValue("window/last_page_index", max(0, int(index)))
        self._qs.sync()

    # ── notifications ─────────────────────────────────────────────────────────

    @property
    def show_notifications(self) -> bool:
        """Whether to show toast-style status-bar notifications."""
        return self._qs.value("ui/show_notifications", True, type=bool)

    @show_notifications.setter
    def show_notifications(self, value: bool) -> None:
        self._qs.setValue("ui/show_notifications", bool(value))
        self._qs.sync()

    # ── v2.0 new settings ──────────────────────────────────────────────────────

    @property
    def high_contrast(self) -> bool:
        """High contrast mode for accessibility."""
        return self._qs.value("ui/high_contrast", False, type=bool)

    @high_contrast.setter
    def high_contrast(self, value: bool) -> None:
        self._qs.setValue("ui/high_contrast", bool(value))
        self._qs.sync()

    @property
    def animations_enabled(self) -> bool:
        """Enable smooth UI transitions."""
        return self._qs.value("ui/animations_enabled", True, type=bool)

    @animations_enabled.setter
    def animations_enabled(self, value: bool) -> None:
        self._qs.setValue("ui/animations_enabled", bool(value))
        self._qs.sync()

    @property
    def notifications_enabled(self) -> bool:
        """Enable desktop notifications."""
        return self._qs.value("ui/notifications_enabled", True, type=bool)

    @notifications_enabled.setter
    def notifications_enabled(self, value: bool) -> None:
        self._qs.setValue("ui/notifications_enabled", bool(value))
        self._qs.sync()

    @property
    def minimize_to_tray(self) -> bool:
        """Minimize to system tray instead of taskbar."""
        return self._qs.value("ui/minimize_to_tray", False, type=bool)

    @minimize_to_tray.setter
    def minimize_to_tray(self, value: bool) -> None:
        self._qs.setValue("ui/minimize_to_tray", bool(value))
        self._qs.sync()

    @property
    def start_minimized(self) -> bool:
        """Start application minimized to tray."""
        return self._qs.value("ui/start_minimized", False, type=bool)

    @start_minimized.setter
    def start_minimized(self, value: bool) -> None:
        self._qs.setValue("ui/start_minimized", bool(value))
        self._qs.sync()

    @property
    def log_level(self) -> str:
        """Logging level (DEBUG, INFO, WARNING, ERROR)."""
        return self._qs.value("logging/level", "INFO", type=str)

    @log_level.setter
    def log_level(self, value: str) -> None:
        self._qs.setValue("logging/level", value.upper())
        self._qs.sync()

    @property
    def telemetry_enabled(self) -> bool:
        """Allow anonymous usage statistics."""
        return self._qs.value("privacy/telemetry_enabled", False, type=bool)

    @telemetry_enabled.setter
    def telemetry_enabled(self, value: bool) -> None:
        self._qs.setValue("privacy/telemetry_enabled", bool(value))
        self._qs.sync()

    # ── health scan on startup ────────────────────────────────────────────────

    @property
    def scan_on_health_open(self) -> bool:
        """Whether to auto-scan when Health Score page is opened."""
        return self._qs.value("health/scan_on_open", True, type=bool)

    @scan_on_health_open.setter
    def scan_on_health_open(self, value: bool) -> None:
        self._qs.setValue("health/scan_on_open", bool(value))
        self._qs.sync()

    # ── reset ──────────────────────────────────────────────────────────────────

    def reset_all(self) -> None:
        """Clear all stored settings (useful for testing)."""
        self._qs.clear()
        self._qs.sync()
        logger.info("AppSettings: all settings reset to defaults")


# Module-level singleton — import and use directly
settings = AppSettings()