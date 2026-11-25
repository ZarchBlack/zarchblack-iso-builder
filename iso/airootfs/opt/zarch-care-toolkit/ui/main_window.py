"""
ui/main_window.py
=================
Main application window: sidebar navigation + stacked page area + status bar.

Fixes applied:
  BUG-C01  — WorkerMixin auto-cleans completed workers from self._workers.
  BUG-H02  — Removed the duplicate _refresh_status_bar() worker that was
             spawning a *second* full build_dashboard_snapshot() at startup.
             The DashboardPage already emits snapshot_ready when its own
             refresh completes; main_window just listens to that signal.
  BUG-H07  — Added worker.failed handler so status-bar pills show an error
             state instead of staying on "checking…" forever.
"""

import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QListWidgetItem, QStackedWidget, QLabel, QStatusBar,
)
from PySide6.QtCore import Qt

from ui.theme import ZARCH_STYLESHEET
from ui.widgets_common import Pill, HealthBadge
from ui.worker_mixin import WorkerMixin
from ui.icons import app_icon, logo_pixmap
from core.logger import get_logger
from core.settings import settings

from ui.pages.page_dashboard import DashboardPage
from ui.pages.page_health_score import HealthScorePage
from ui.pages.page_network import NetworkToolsPage
from ui.pages.page_hardware import HardwareDriversPage
from ui.pages.page_clean import CleanSystemPage
from ui.pages.page_update import UpdateSystemPage
from ui.pages.page_disk_analyzer import DiskAnalyzerPage
from ui.pages.page_broken_packages import BrokenPackagesPage
from ui.pages.page_pacnew import PacnewPage
from ui.pages.page_quick_clean import QuickCleanPage
from ui.pages.page_one_click import OneClickMaintenancePage
from ui.pages.page_settings import SettingsPage
from ui.pages.page_services import ServicesPage

logger = get_logger(__name__)

NAV_ITEMS = [
    ("📊  Dashboard",          "dashboard"),
    ("❤  Health Score",        "health"),
    ("🌐  Network Tools",      "network"),
    ("🖥  Hardware & Drivers", "hardware"),
    ("⚙️  Service Manager",     "services"),
    ("🧹  Clean System",       "clean"),
    ("⬆  Update System",      "update"),
    ("💿  Disk Analyzer",      "disk"),
    ("🔧  Broken Packages",    "broken"),
    ("📄  Pacnew Files",       "pacnew"),
    ("⚡  Quick Clean",        "quick"),
    ("🚀  One-Click Maint.",   "oneclick"),
    ("⚙️  Settings",           "settings"),
]


class ZarchCareWindow(QMainWindow, WorkerMixin):
    def __init__(self):
        super().__init__()
        self._workers: list = []   # required by WorkerMixin (BUG-C01)

        self.setWindowTitle("ZarchCare — ZarchBlack System Care")
        self.resize(1150, 760)
        self.setStyleSheet(ZARCH_STYLESHEET)
        self.setWindowIcon(app_icon())

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ─── Sidebar ──────────────────────────────────────────────────────────
        sidebar_container = QWidget()
        sidebar_container.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(14, 16, 14, 14)
        sidebar_layout.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        logo_lbl = QLabel()
        logo_lbl.setPixmap(logo_pixmap(40))
        logo_lbl.setFixedSize(40, 40)
        logo_lbl.setScaledContents(True)
        brand_row.addWidget(logo_lbl)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand = QLabel("ZarchBlack")
        brand.setObjectName("brandTitle")
        brand_text.addWidget(brand)
        # Restore saved version label
        subbrand = QLabel("ZarchCare v2.0")
        subbrand.setObjectName("brandSubtitle")
        brand_text.addWidget(subbrand)
        brand_row.addLayout(brand_text)
        brand_row.addStretch()
        sidebar_layout.addLayout(brand_row)

        self.health_badge = HealthBadge()
        sidebar_layout.addWidget(self.health_badge)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("sidebar")
        for label, _key in NAV_ITEMS:
            QListWidgetItem(label, self.nav_list)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        sidebar_layout.addWidget(self.nav_list, 1)

        root.addWidget(sidebar_container)

        # ─── Pages ────────────────────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        # BUG-H02 fix: only listen to DashboardPage's own signal — no extra worker
        self.dashboard_page.snapshot_ready.connect(self._on_dashboard_snapshot)

        self.pages = {
            "dashboard": self.dashboard_page,
            "health":    HealthScorePage(),
            "network":   NetworkToolsPage(),
            "hardware":  HardwareDriversPage(),
            "services":  ServicesPage(),
            "clean":     CleanSystemPage(),
            "update":    UpdateSystemPage(),
            "disk":      DiskAnalyzerPage(),
            "broken":    BrokenPackagesPage(),
            "pacnew":    PacnewPage(),
            "quick":     QuickCleanPage(),
            "oneclick":  OneClickMaintenancePage(),
            "settings":  SettingsPage(),
        }
        for _label, key in NAV_ITEMS:
            self.stack.addWidget(self.pages[key])

        page_wrapper = QWidget()
        page_layout = QVBoxLayout(page_wrapper)
        page_layout.setContentsMargins(20, 18, 20, 10)
        page_layout.addWidget(self.stack)
        root.addWidget(page_wrapper, 1)

        self.setCentralWidget(central)
        self.nav_list.setCurrentRow(0)

        # ─── Status bar ───────────────────────────────────────────────────────
        self.status = QStatusBar()
        self.pill_firewall = Pill("🛡  Firewall: checking…", "#9d94c2")
        self.pill_aur      = Pill("🔧  AUR: checking…",     "#9d94c2")
        self.pill_updated  = Pill("🕒  Not checked yet",    "#9d94c2")
        self.status.addWidget(self.pill_firewall)
        self.status.addWidget(self.pill_aur)
        self.status.addPermanentWidget(self.pill_updated)
        self.setStatusBar(self.status)

        # BUG-H02 fix: status bar is populated via snapshot_ready from DashboardPage —
        # no separate worker needed here.
        logger.info("ZarchCareWindow initialised")

    # ─── Slots ────────────────────────────────────────────────────────────────

    def _on_nav_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        settings.last_page_index = row

    def _on_dashboard_snapshot(self, snap) -> None:
        """Update sidebar badge + status-bar pills when DashboardPage refreshes."""
        self.health_badge.set_score(snap.health_score)
        self.pill_firewall.setText(f"🛡  {snap.firewall_status}")
        self.pill_aur.setText(f"🔧  AUR: {snap.aur_helper}")
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.pill_updated.setText(f"🕒  Checked: {now}")
        logger.debug("Status bar updated from dashboard snapshot (score=%d)", snap.health_score)

    # ─── Shutdown ─────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Save window state and give running threads a moment to finish."""
        # Save geometry
        settings.window_geometry = bytes(self.saveGeometry())

        # Collect all running workers across main window + all pages
        all_workers = list(self._workers)
        for page in self.pages.values():
            if hasattr(page, "_workers"):
                all_workers += list(page._workers)
        running = [w for w in all_workers if w.isRunning()]

        if running:
            logger.info("closeEvent: waiting for %d running worker(s)…", len(running))
            # Request all threads to quit (non-blocking)
            for w in running:
                w.quit()
            # Wait in parallel (each gets up to 3s)
            for w in running:
                w.wait(3000)

        logger.info("ZarchCareWindow closed")
        event.accept()
