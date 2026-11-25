"""
ui/pages/page_services.py
=========================
Systemd Service Manager page for ZarchCare.

v2.0 features:
  - List systemd services with status
  - Start/Stop/Restart/Enable/Disable services
  - Filter by state (active, inactive, failed, all)
  - Search services by name
  - View service logs
  - User services support (--user)
"""

import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu, QMessageBox, QDialog, QDialogButtonBox,
    QTextEdit, QFrame, QScrollArea, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QCursor

from core.privilege import run_privileged
from core.sysctl import run_unprivileged
from core.logger import get_logger
from core.operation_log import op_log
from ui.worker_mixin import WorkerMixin
from ui.widgets_common import StatCard

logger = get_logger(__name__)


class ServiceLogDialog(QDialog):
    """Dialog to display service logs."""

    def __init__(self, service_name: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Logs: {service_name}")
        self.resize(800, 500)
        self._service_name = service_name
        self._is_user = is_user

        layout = QVBoxLayout(self)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFontFamily("JetBrains Mono")
        self.log_text.setFontPointSize(11)
        layout.addWidget(self.log_text)

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄  Refresh")
        self.btn_refresh.clicked.connect(self._load_logs)
        btn_layout.addWidget(self.btn_refresh)

        self.btn_follow = QPushButton("👁  Follow (tail -f)")
        self.btn_follow.setCheckable(True)
        self.btn_follow.toggled.connect(self._toggle_follow)
        btn_layout.addWidget(self.btn_follow)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self._follow_timer = QTimer(self)
        self._follow_timer.timeout.connect(self._load_logs)
        self._load_logs()

    def _load_logs(self) -> None:
        user_flag = "--user" if self._is_user else ""
        code, out = run_unprivileged(
            ["journalctl", user_flag, "-u", self._service_name, "-n", "200", "--no-pager"]
        )
        if out:
            self.log_text.setPlainText(out)
            # Scroll to bottom
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)

    def _toggle_follow(self, checked: bool) -> None:
        if checked:
            self._follow_timer.start(2000)
            self.btn_follow.setText("⏹  Stop Following")
        else:
            self._follow_timer.stop()
            self.btn_follow.setText("👁  Follow (tail -f)")

    def closeEvent(self, event):
        self._follow_timer.stop()
        super().closeEvent(event)


class ServiceCard(QFrame):
    """Individual service card for the service list."""

    action_requested = Signal(str, str, bool)  # service_name, action, is_user

    def __init__(self, name: str, description: str, state: str, substate: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("serviceCard")
        self.setProperty("state", state)
        self._name = name
        self._is_user = is_user

        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 10, 12, 10)

        # Status indicator
        self.status_label = QLabel()
        self.status_label.setFixedWidth(12)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Service info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_layout = QHBoxLayout()
        name_layout.setSpacing(8)

        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #ffffff;")
        name_layout.addWidget(self.name_label)

        if is_user:
            user_badge = QLabel("USER")
            user_badge.setStyleSheet("""
                background: #3a2a5e;
                color: #a685ff;
                padding: 1px 6px;
                border-radius: 3px;
                font-size: 9px;
                font-weight: 600;
            """)
            user_badge.setFixedWidth(40)
            name_layout.addWidget(user_badge)

        name_layout.addStretch()
        info_layout.addLayout(name_layout)

        self.desc_label = QLabel(description[:80] + ("…" if len(description) > 80 else ""))
        self.desc_label.setStyleSheet("color: #9d94c2; font-size: 11px;")
        info_layout.addWidget(self.desc_label)

        self.state_label = QLabel(f"{state} ({substate})")
        self.state_label.setStyleSheet("color: #b8aee0; font-size: 11px;")
        info_layout.addWidget(self.state_label)

        layout.addLayout(info_layout, 1)

        # Action buttons
        self.btn_start = QPushButton("Start")
        self.btn_start.setFixedWidth(70)
        self.btn_start.clicked.connect(lambda: self._request("start"))
        layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFixedWidth(70)
        self.btn_stop.clicked.connect(lambda: self._request("stop"))
        layout.addWidget(self.btn_stop)

        self.btn_restart = QPushButton("Restart")
        self.btn_restart.setFixedWidth(75)
        self.btn_restart.clicked.connect(lambda: self._request("restart"))
        layout.addWidget(self.btn_restart)

        self.btn_enable = QPushButton("Enable")
        self.btn_enable.setFixedWidth(70)
        self.btn_enable.clicked.connect(lambda: self._request("enable"))
        layout.addWidget(self.btn_enable)

        self.btn_disable = QPushButton("Disable")
        self.btn_disable.setFixedWidth(70)
        self.btn_disable.clicked.connect(lambda: self._request("disable"))
        layout.addWidget(self.btn_disable)

        self.btn_logs = QPushButton("Logs")
        self.btn_logs.setFixedWidth(60)
        self.btn_logs.clicked.connect(self._show_logs)
        layout.addWidget(self.btn_logs)

        self._update_ui(state, substate)

    def _update_ui(self, state: str, substate: str) -> None:
        """Update UI based on service state."""
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)

        # Status dot color
        colors = {
            "active": "#4dff9e",
            "inactive": "#ff4d6a",
            "failed": "#ffaa4d",
            "activating": "#ffd24d",
            "deactivating": "#ffd24d",
            "reloading": "#ffd24d",
        }
        color = colors.get(state, "#9d94c2")
        self.status_label.setStyleSheet(f"""
            background: {color};
            border-radius: 6px;
            min-width: 12px;
            max-width: 12px;
            min-height: 12px;
            max-height: 12px;
        """)

        # Update button states
        is_active = state == "active"
        is_failed = state == "failed"

        self.btn_start.setEnabled(not is_active)
        self.btn_stop.setEnabled(is_active)
        self.btn_restart.setEnabled(is_active)
        self.btn_enable.setEnabled(True)
        self.btn_disable.setEnabled(True)

    def _request(self, action: str) -> None:
        self.action_requested.emit(self._name, action, self._is_user)

    def _show_logs(self) -> None:
        dialog = ServiceLogDialog(self._name, self._is_user, self.window())
        dialog.exec()


class ServicesPage(QWidget, WorkerMixin):
    """Systemd Service Manager page."""

    def __init__(self):
        super().__init__()
        self._workers: list = []
        self._services: list = []
        self._filter_state = "all"
        self._search_text = ""
        self._show_user = False

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── header ────────────────────────────────────────────────────────────
        header = QVBoxLayout()
        title = QLabel("Service Manager")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        subtitle = QLabel("Manage systemd services (system & user)")
        subtitle.setStyleSheet("color: #9d94c2;")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # ── toolbar ───────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Search services…")
        self.search_box.setFixedWidth(300)
        self.search_box.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_box)

        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["All", "Active", "Inactive", "Failed"])
        self.combo_filter.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.combo_filter)

        self.check_user = QCheckBox("Show user services (--user)")
        self.check_user.setChecked(False)
        self.check_user.toggled.connect(self._on_user_toggled)
        toolbar.addWidget(self.check_user)

        toolbar.addStretch()

        self.btn_refresh = QPushButton("⟳  Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        toolbar.addWidget(self.btn_refresh)

        self.btn_reload_daemon = QPushButton("🔄  Reload Daemon")
        self.btn_reload_daemon.setObjectName("exportButton")
        self.btn_reload_daemon.clicked.connect(self._reload_daemon)
        toolbar.addWidget(self.btn_reload_daemon)

        layout.addLayout(toolbar)

        # ── stats row ─────────────────────────────────────────────────────────
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.stat_active = StatCard("✅", "Active", "#4dff9e")
        self.stat_inactive = StatCard("⏸", "Inactive", "#9d94c2")
        self.stat_failed = StatCard("❌", "Failed", "#ff4d6a")
        self.stat_total = StatCard("📋", "Total", "#7c4dff")

        for card in [self.stat_active, self.stat_inactive, self.stat_failed, self.stat_total]:
            card.setObjectName("statCard")
            stats_layout.addWidget(card)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # ── service list area ─────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.services_container = QWidget()
        self.services_layout = QVBoxLayout(self.services_container)
        self.services_layout.setSpacing(8)
        self.services_layout.setContentsMargins(0, 0, 0, 0)
        self.services_layout.addStretch()

        scroll.setWidget(self.services_container)
        layout.addWidget(scroll, 1)

        # Initial load
        self.refresh()

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.lower()
        self._render_services()

    def _on_filter_changed(self, text: str) -> None:
        self._filter_state = text.lower()
        self._render_services()

    def _on_user_toggled(self, checked: bool) -> None:
        self._show_user = checked
        self.refresh()

    def refresh(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⟳  Loading…")

        worker = self._spawn_worker(self._fetch_services)

        def done(services):
            self._services = services
            self._update_stats()
            self._render_services()
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("⟳  Refresh")
            op_log.record("Services refreshed", success=True, detail=f"{len(services)} services")

        def failed(err: str):
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("⟳  Refresh")
            op_log.record("Services refresh", success=False, detail=err)
            logger.warning("Services refresh failed: %s", err)

        worker.finished_ok.connect(done)
        worker.failed.connect(failed)
        worker.start()

    def _fetch_services(self) -> list:
        """Fetch systemd services."""
        services = []

        # System services
        code, out = run_unprivileged([
            "systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"
        ])
        if out:
            for line in out.strip().split('\n'):
                parts = line.split(None, 4)
                if len(parts) >= 4:
                    name = parts[0]
                    load_state = parts[1]
                    active_state = parts[2]
                    sub_state = parts[3]
                    description = parts[4] if len(parts) > 4 else ""
                    services.append({
                        "name": name,
                        "description": description,
                        "state": active_state,
                        "substate": sub_state,
                        "is_user": False,
                    })

        # User services if requested
        if self._show_user:
            code, out = run_unprivileged([
                "systemctl", "--user", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"
            ])
            if out:
                for line in out.strip().split('\n'):
                    parts = line.split(None, 4)
                    if len(parts) >= 4:
                        name = parts[0]
                        load_state = parts[1]
                        active_state = parts[2]
                        sub_state = parts[3]
                        description = parts[4] if len(parts) > 4 else ""
                        services.append({
                            "name": name,
                            "description": description,
                            "state": active_state,
                            "substate": sub_state,
                            "is_user": True,
                        })

        return services

    def _update_stats(self) -> None:
        active = sum(1 for s in self._services if s["state"] == "active")
        inactive = sum(1 for s in self._services if s["state"] == "inactive")
        failed = sum(1 for s in self._services if s["state"] == "failed")
        total = len(self._services)

        self.stat_active.set_value(str(active))
        self.stat_inactive.set_value(str(inactive))
        self.stat_failed.set_value(str(failed))
        self.stat_total.set_value(str(total))

    def _render_services(self) -> None:
        # Clear existing cards
        while self.services_layout.count() > 1:  # Keep the stretch at the end
            item = self.services_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Filter services
        filtered = []
        for svc in self._services:
            # Search filter
            if self._search_text:
                if self._search_text not in svc["name"].lower() and \
                   self._search_text not in svc["description"].lower():
                    continue

            # State filter
            if self._filter_state != "all":
                if self._filter_state == "active" and svc["state"] != "active":
                    continue
                if self._filter_state == "inactive" and svc["state"] not in ("inactive", "deactivating"):
                    continue
                if self._filter_state == "failed" and svc["state"] != "failed":
                    continue

            filtered.append(svc)

        # Sort: active first, then by name
        filtered.sort(key=lambda s: (s["state"] != "active", s["name"]))

        # Add cards
        for svc in filtered:
            card = ServiceCard(
                svc["name"],
                svc["description"],
                svc["state"],
                svc["substate"],
                svc["is_user"],
            )
            card.action_requested.connect(self._on_service_action)
            self.services_layout.insertWidget(self.services_layout.count() - 1, card)

    def _on_service_action(self, service_name: str, action: str, is_user: bool) -> None:
        """Handle service action request."""
        user_flag = "--user" if is_user else ""

        # Determine if action needs privilege
        needs_privilege = action in ("start", "stop", "restart", "enable", "disable") and not is_user

        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText(f"⟳  {action.capitalize()}…")

        if needs_privilege:
            # Use pkexec for privileged operations
            worker = self._spawn_worker(
                lambda: self._run_privileged_action(service_name, action, user_flag)
            )
        else:
            worker = self._spawn_worker(
                lambda: self._run_unprivileged_action(service_name, action, user_flag)
            )

        def done(result):
            if result[0] == 0:
                QMessageBox.information(self, "Success",
                    f"Service '{service_name}' {action} completed successfully.")
                op_log.record(f"Service {action}", success=True, detail=service_name)
            else:
                QMessageBox.critical(self, "Failed",
                    f"Failed to {action} service '{service_name}':\n{result[1]}")
                op_log.record(f"Service {action}", success=False, detail=f"{service_name}: {result[1]}")

            # Refresh after a short delay
            QTimer.singleShot(500, self.refresh)

        def failed(err: str):
            QMessageBox.critical(self, "Error", f"Error executing {action}:\n{err}")
            op_log.record(f"Service {action}", success=False, detail=err)
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("⟳  Refresh")

        worker.finished_ok.connect(done)
        worker.failed.connect(failed)
        worker.start()

    def _run_privileged_action(self, service: str, action: str, user_flag: str) -> tuple:
        """Run systemctl action with pkexec."""
        from core.privilege import run_privileged
        return run_privileged(["systemctl", user_flag, action, service])

    def _run_unprivileged_action(self, service: str, action: str, user_flag: str) -> tuple:
        """Run systemctl action without privilege (user services)."""
        return run_unprivileged(["systemctl", user_flag, action, service])

    def _reload_daemon(self) -> None:
        """Reload systemd daemon."""
        self.btn_reload_daemon.setEnabled(False)
        self.btn_reload_daemon.setText("🔄  Reloading…")

        worker = self._spawn_worker(
            lambda: run_privileged(["systemctl", "daemon-reload"])
        )

        def done(result):
            if result[0] == 0:
                QMessageBox.information(self, "Success", "Systemd daemon reloaded successfully.")
                op_log.record("Daemon reload", success=True)
            else:
                QMessageBox.critical(self, "Failed", f"Failed to reload daemon:\n{result[1]}")
                op_log.record("Daemon reload", success=False, detail=result[1])
            self.btn_reload_daemon.setEnabled(True)
            self.btn_reload_daemon.setText("🔄  Reload Daemon")

        def failed(err: str):
            QMessageBox.critical(self, "Error", f"Error reloading daemon:\n{err}")
            op_log.record("Daemon reload", success=False, detail=err)
            self.btn_reload_daemon.setEnabled(True)
            self.btn_reload_daemon.setText("🔄  Reload Daemon")

        worker.finished_ok.connect(done)
        worker.failed.connect(failed)
        worker.start()