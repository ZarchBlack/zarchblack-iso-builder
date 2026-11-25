"""
ui/pages/page_dashboard.py
==========================
Live system statistics dashboard with health score gauge.

v2.0 changes:
  - Added health score radial gauge
  - Animated progress bars on stat cards
  - System report export button
  - Better visual feedback and hover effects
  - High contrast mode support
"""

import datetime
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QFrame
)
from PySide6.QtCore import Signal, QTimer, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QPen, QColor, QFont

from core import dashboard as dash
from core.settings import settings
from core.operation_log import op_log
from ui.worker_mixin import WorkerMixin
from ui.widgets_common import StatCard
from core.logger import get_logger
from core.hardware import build_full_report
from core.troubleshoot import run_full_diagnosis

logger = get_logger(__name__)

_MIN_REFRESH_INTERVAL = 60   # seconds — don't allow faster than once per minute


class HealthGauge(QFrame):
    """Radial gauge widget for health score display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("healthGauge")
        self.setFixedSize(160, 160)
        self._score = 100
        self._animation = QPropertyAnimation(self, b"score")
        self._animation.setDuration(800)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_score(self, score: int):
        self._animation.stop()
        self._animation.setStartValue(self._score)
        self._animation.setEndValue(score)
        self._animation.start()

    def get_score(self):
        return self._score

    def _set_score(self, value):
        self._score = value
        self.update()
        self._update_property()

    def _update_property(self):
        if self._score >= 90:
            self.setProperty("health", "excellent")
        elif self._score >= 70:
            self.setProperty("health", "good")
        elif self._score >= 50:
            self.setProperty("health", "fair")
        elif self._score >= 30:
            self.setProperty("health", "poor")
        else:
            self.setProperty("health", "critical")
        self.style().unpolish(self)
        self.style().polish(self)

    score = property(get_score, _set_score)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(8, 8, -8, -8)
        center = rect.center()
        radius = min(rect.width(), rect.height()) // 2

        # Background arc
        pen_bg = QPen(QColor("#2a1f4d"), 10)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_bg)
        painter.drawArc(rect, 90 * 16, -360 * 16)

        # Foreground arc based on score
        if self._score >= 90:
            color = QColor("#4dff9e")
        elif self._score >= 70:
            color = QColor("#a6ff9e")
        elif self._score >= 50:
            color = QColor("#ffd24d")
        elif self._score >= 30:
            color = QColor("#ffaa4d")
        else:
            color = QColor("#ff4d6a")

        pen_fg = QPen(color, 10)
        pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_fg)

        span_angle = int(-360 * 16 * (self._score / 100))
        painter.drawArc(rect, 90 * 16, span_angle)

        # Center text
        font = QFont("Noto Sans", 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self._score}")

        # Label below
        label_font = QFont("Noto Sans", 11)
        painter.setFont(label_font)
        painter.setPen(QColor("#b8aee0"))
        label_rect = self.rect().adjusted(0, 80, 0, -10)
        label = "Excellent" if self._score >= 90 else \
                "Good" if self._score >= 70 else \
                "Fair" if self._score >= 50 else \
                "Poor" if self._score >= 30 else "Critical"
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)


class SkeletonCard(QFrame):
    """Skeleton loader for stat cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("skeletonCard")
        self.setFixedHeight(110)
        self.setMinimumWidth(180)


class DashboardPage(QWidget, WorkerMixin):
    snapshot_ready = Signal(object)

    def __init__(self):
        super().__init__()
        self._workers: list = []
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── header ────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(16)

        title_box = QVBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("sectionTitle")
        title_box.addWidget(title)
        self._subtitle = QLabel("Live system statistics")
        self._subtitle.setStyleSheet("color: #9d94c2;")
        title_box.addWidget(self._subtitle)
        header.addLayout(title_box)
        header.addStretch()

        # Health gauge in header
        self.health_gauge = HealthGauge()
        header.addWidget(self.health_gauge)

        self.btn_refresh = QPushButton("⟳  Refresh")
        self.btn_refresh.setFixedHeight(40)
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)

        self.btn_export = QPushButton("📄  Export Report")
        self.btn_export.setObjectName("exportButton")
        self.btn_export.setFixedHeight(40)
        self.btn_export.clicked.connect(self.export_report)
        header.addWidget(self.btn_export)

        layout.addLayout(header)

        # ── metric cards grid ─────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(14)
        layout.addLayout(grid)

        self.card_disk = StatCard("💾", "Disk", "#ff4d8d")
        self.card_mem = StatCard("🧠", "Memory", "#4dc9ff")
        self.card_cpu = StatCard("⚡", "CPU", "#a685ff")
        self.card_pkgs = StatCard("📦", "Packages", "#4dff9e")
        self.card_updates = StatCard("🔄", "Updates", "#ffd24d")
        self.card_cache = StatCard("🗑", "Cache", "#ff9d4d")
        self.card_orphans = StatCard("👻", "Orphans", "#ff4d6a")
        self.card_uptime = StatCard("⏱", "Uptime", "#4dc9ff")
        self.card_kernel = StatCard("🐧", "Kernel", "#a685ff")

        cards = [
            self.card_disk, self.card_mem, self.card_cpu,
            self.card_pkgs, self.card_updates, self.card_cache,
            self.card_orphans, self.card_uptime, self.card_kernel,
        ]
        for i, card in enumerate(cards):
            card.setObjectName("statCard")
            grid.addWidget(card, i // 3, i % 3)

        # System info cards row
        info_grid = QGridLayout()
        info_grid.setSpacing(12)
        layout.addLayout(info_grid)

        self.info_cards = []
        info_items = [
            ("🖥", "CPU Model", "cpu_model", "#7c4dff"),
            ("🎮", "GPU(s)", "gpu", "#a685ff"),
            ("💾", "Total RAM", "ram", "#4dc9ff"),
            ("💿", "Storage", "storage", "#ff9d4d"),
            ("🔧", "Motherboard", "motherboard", "#4dff9e"),
            ("🌐", "Network", "network", "#ff4d8d"),
        ]

        for i, (icon, title, key, color) in enumerate(info_items):
            card = self._create_info_card(icon, title, key, color)
            self.info_cards.append((key, card))
            info_grid.addWidget(card, 0, i)

        layout.addStretch()

        # Apply saved auto-refresh setting
        self._apply_auto_refresh()
        self.refresh()

    def _create_info_card(self, icon: str, title: str, key: str, color: str) -> QFrame:
        card = QFrame()
        card.setObjectName("infoCard")
        card.setMinimumWidth(160)
        card.setMaximumHeight(110)

        layout = QVBoxLayout(card)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 12, 12, 12)

        icon_lbl = QLabel(icon)
        icon_lbl.setObjectName("infoCardIcon")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("infoCardTitle")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        value_lbl = QLabel("Loading…")
        value_lbl.setObjectName("infoCardValue")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_lbl.setWordWrap(True)
        layout.addWidget(value_lbl)

        card._value_label = value_lbl
        card._key = key
        return card

    def _apply_auto_refresh(self) -> None:
        interval = settings.auto_refresh_interval
        if interval >= _MIN_REFRESH_INTERVAL:
            self._refresh_timer.start(interval * 1000)
            logger.debug("DashboardPage: auto-refresh every %ds", interval)
        else:
            self._refresh_timer.stop()

    def set_auto_refresh(self, interval_seconds: int) -> None:
        """Change auto-refresh interval at runtime and persist the setting."""
        settings.auto_refresh_interval = interval_seconds
        self._apply_auto_refresh()

    def refresh(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⟳  Refreshing…")
        self._subtitle.setText("Live system statistics — refreshing…")
        start = datetime.datetime.now()

        worker = self._spawn_worker(dash.build_dashboard_snapshot)

        def done(snap):
            elapsed = (datetime.datetime.now() - start).total_seconds()
            self._render(snap)
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("⟳  Refresh")
            self._subtitle.setText(
                f"Live system statistics — updated {datetime.datetime.now().strftime('%H:%M:%S')}"
                f"  ({elapsed:.1f}s)"
            )
            self.snapshot_ready.emit(snap)
            op_log.record(
                "Dashboard refreshed",
                success=True,
                detail=f"score={snap.health_score} issues={snap.issue_count} t={elapsed:.1f}s",
            )

        def failed(err: str):
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("⟳  Refresh")
            self._subtitle.setText("Live system statistics — refresh failed")
            op_log.record("Dashboard refresh", success=False, detail=err)
            logger.warning("DashboardPage refresh failed: %s", err)

        worker.finished_ok.connect(done)
        worker.failed.connect(failed)
        worker.start()

    def _render(self, snap) -> None:
        # Update stat cards with animated progress
        self.card_disk.set_value(f"{snap.disk_used} / {snap.disk_total}")
        self.card_disk.set_progress(snap.disk_percent)

        self.card_mem.set_value(f"{snap.mem_used} / {snap.mem_total}")
        self.card_mem.set_progress(snap.mem_percent)

        self.card_cpu.set_value(f"{snap.cpu_percent}%")
        self.card_cpu.set_progress(snap.cpu_percent)

        self.card_pkgs.set_value(str(snap.package_count))
        self.card_updates.set_value(snap.updates_available)
        self.card_cache.set_value(snap.cache_size)
        self.card_orphans.set_value(str(snap.orphan_count))
        self.card_uptime.set_value(snap.uptime)
        self.card_kernel.set_value(snap.kernel)

        # Update health gauge
        self.health_gauge.set_score(snap.health_score)

        # Update info cards in background
        self._refresh_hardware_info()

    def _refresh_hardware_info(self) -> None:
        """Fetch hardware info asynchronously and update info cards."""
        worker = self._spawn_worker(build_full_report)

        def done(report):
            self._update_info_cards(report)

        def failed(err: str):
            logger.warning("Hardware info fetch failed: %s", err)
            for _, card in self.info_cards:
                card._value_label.setText("Unavailable")

        worker.finished_ok.connect(done)
        worker.failed.connect(failed)
        worker.start()

    def _update_info_cards(self, report) -> None:
        # CPU
        cpu_text = report.cpu.split('\n')[0] if report.cpu else "Unknown"
        if "Model name" in cpu_text:
            cpu_text = cpu_text.split(":", 1)[1].strip()
        self._set_info_card("cpu_model", cpu_text[:40])

        # GPU
        gpu_text = ", ".join([g.split('\n')[0].split(":", 1)[-1].strip() if ":" in g else g
                               for g in report.gpu[:2]]) if report.gpu else "None"
        self._set_info_card("gpu", gpu_text[:40])

        # RAM
        ram_text = report.ram.split('\n')[0] if report.ram else "Unknown"
        if "Mem:" in ram_text:
            parts = ram_text.split()
            if len(parts) >= 2:
                ram_text = f"{parts[1]} total"
        self._set_info_card("ram", ram_text)

        # Storage
        storage_text = report.storage.split('\n')[0] if report.storage else "Unknown"
        self._set_info_card("storage", storage_text[:40])

        # Motherboard
        mb_text = report.motherboard if report.motherboard else "Unknown"
        self._set_info_card("motherboard", mb_text[:40])

        # Network
        net_text = ", ".join([n.split(":", 1)[-1].strip() for n in report.network[:2]]) if report.network else "None"
        self._set_info_card("network", net_text[:40])

    def _set_info_card(self, key: str, value: str) -> None:
        for k, card in self.info_cards:
            if k == key:
                card._value_label.setText(value)
                break

    def export_report(self) -> None:
        """Export comprehensive system report as JSON or HTML."""
        self.btn_export.setEnabled(False)
        self.btn_export.setText("📄  Generating…")

        worker = self._spawn_worker(self._generate_report)

        def done(report_data):
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export System Report",
                f"zarchcare-report-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "HTML Report (*.html);;JSON Report (*.json)"
            )

            if file_path:
                try:
                    if file_path.endswith('.html'):
                        self._write_html_report(report_data, file_path)
                    else:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(report_data, f, indent=2, ensure_ascii=False)
                    QMessageBox.information(self, "Export Complete",
                        f"System report saved to:\n{file_path}")
                    op_log.record("Report exported", success=True, detail=file_path)
                except Exception as e:
                    QMessageBox.critical(self, "Export Failed", f"Failed to save report:\n{e}")
                    op_log.record("Report export", success=False, detail=str(e))
            else:
                op_log.record("Report export cancelled", success=True, detail="User cancelled")

            self.btn_export.setEnabled(True)
            self.btn_export.setText("📄  Export Report")

        def failed(err: str):
            QMessageBox.critical(self, "Export Failed", f"Failed to generate report:\n{err}")
            op_log.record("Report generation", success=False, detail=err)
            self.btn_export.setEnabled(True)
            self.btn_export.setText("📄  Export Report")
            logger.warning("Report generation failed: %s", err)

        worker.finished_ok.connect(done)
        worker.failed.connect(failed)
        worker.start()

    def _generate_report(self) -> dict:
        """Generate comprehensive system report data."""
        # Get dashboard snapshot
        snap = dash.build_dashboard_snapshot()

        # Get hardware report
        hw = build_full_report()

        # Get diagnostic issues
        issues = run_full_diagnosis()

        # Get network info
        from core.troubleshoot import get_network_interfaces, check_dns
        interfaces = get_network_interfaces()
        dns = check_dns()

        return {
            "metadata": {
                "app": "ZarchCare",
                "version": "2.0",
                "generated": datetime.datetime.now().isoformat(),
                "hostname": __import__('socket').gethostname(),
            },
            "health_score": snap.health_score,
            "issues": [
                {
                    "severity": i.severity,
                    "title": i.title,
                    "detail": i.detail,
                    "suggestion": i.suggestion
                }
                for i in issues
            ],
            "system": {
                "disk": {
                    "used": snap.disk_used,
                    "total": snap.disk_total,
                    "percent": snap.disk_percent
                },
                "memory": {
                    "used": snap.mem_used,
                    "total": snap.mem_total,
                    "percent": snap.mem_percent
                },
                "cpu_percent": snap.cpu_percent,
                "uptime": snap.uptime,
                "kernel": snap.kernel,
                "package_count": snap.package_count,
                "updates_available": snap.updates_available,
                "cache_size": snap.cache_size,
                "orphan_count": snap.orphan_count,
                "firewall_status": snap.firewall_status,
                "aur_helper": snap.aur_helper,
            },
            "hardware": {
                "cpu": hw.cpu,
                "gpu": hw.gpu,
                "ram": hw.ram,
                "storage": hw.storage,
                "motherboard": hw.motherboard,
                "network": hw.network,
            },
            "network": {
                "interfaces": interfaces,
                "dns": dns,
            }
        }

    def _write_html_report(self, data: dict, file_path: str) -> None:
        """Write HTML formatted report."""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZarchCare System Report - {data['metadata']['generated']}</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #14101f; color: #e6e0ff; margin: 0; padding: 20px; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        h1 {{ color: #7c4dff; border-bottom: 2px solid #2a1f4d; padding-bottom: 10px; }}
        h2 {{ color: #a685ff; border-left: 4px solid #7c4dff; padding-left: 12px; margin-top: 30px; }}
        h3 {{ color: #b8aee0; }}
        .card {{ background: #1b1530; border: 1px solid #2a1f4d; border-radius: 10px; padding: 20px; margin: 16px 0; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }}
        .stat {{ background: #1e1836; border-radius: 8px; padding: 16px; }}
        .stat-label {{ color: #9d94c2; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #fff; margin-top: 4px; }}
        .health-score {{ text-align: center; padding: 30px; }}
        .health-score .value {{ font-size: 64px; font-weight: bold; }}
        .health-score .label {{ color: #b8aee0; margin-top: 8px; }}
        .issue {{ padding: 12px; margin: 8px 0; border-radius: 6px; border-left: 4px solid; }}
        .issue.error {{ background: #2a1828; border-color: #ff4d6a; }}
        .issue.warning {{ background: #2a2518; border-color: #ffd24d; }}
        .issue.info {{ background: #18252a; border-color: #7c4dff; }}
        .issue-title {{ font-weight: bold; margin-bottom: 4px; }}
        .issue-detail {{ color: #b8aee0; font-size: 13px; }}
        .issue-suggestion {{ color: #a685ff; font-size: 12px; margin-top: 8px; font-style: italic; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #2a1f4d; }}
        th {{ color: #7c4dff; font-weight: 600; }}
        .meta {{ color: #9d94c2; font-size: 13px; }}
        pre {{ background: #0e0b1a; border: 1px solid #3a2a5e; border-radius: 6px; padding: 12px; overflow-x: auto; color: #cfe8ff; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 ZarchCare System Report</h1>
        <p class="meta">Generated: {data['metadata']['generated']} | Host: {data['metadata']['hostname']} | App: {data['metadata']['app']} v{data['metadata']['version']}</p>

        <div class="card health-score">
            <div class="value" style="color: {self._get_health_color(data['health_score'])};">{data['health_score']}</div>
            <div class="label">Health Score: {self._get_health_label(data['health_score'])}</div>
        </div>

        <h2>System Overview</h2>
        <div class="grid">
            <div class="stat"><div class="stat-label">Disk Usage</div><div class="stat-value">{data['system']['disk']['used']} / {data['system']['disk']['total']} ({data['system']['disk']['percent']}%)</div></div>
            <div class="stat"><div class="stat-label">Memory</div><div class="stat-value">{data['system']['memory']['used']} / {data['system']['memory']['total']} ({data['system']['memory']['percent']}%)</div></div>
            <div class="stat"><div class="stat-label">CPU</div><div class="stat-value">{data['system']['cpu_percent']}%</div></div>
            <div class="stat"><div class="stat-label">Uptime</div><div class="stat-value">{data['system']['uptime']}</div></div>
            <div class="stat"><div class="stat-label">Kernel</div><div class="stat-value">{data['system']['kernel']}</div></div>
            <div class="stat"><div class="stat-label">Packages</div><div class="stat-value">{data['system']['package_count']}</div></div>
            <div class="stat"><div class="stat-label">Updates</div><div class="stat-value">{data['system']['updates_available']}</div></div>
            <div class="stat"><div class="stat-label">Cache</div><div class="stat-value">{data['system']['cache_size']}</div></div>
            <div class="stat"><div class="stat-label">Orphans</div><div class="stat-value">{data['system']['orphan_count']}</div></div>
            <div class="stat"><div class="stat-label">Firewall</div><div class="stat-value">{data['system']['firewall_status']}</div></div>
            <div class="stat"><div class="stat-label">AUR Helper</div><div class="stat-value">{data['system']['aur_helper']}</div></div>
        </div>

        <h2>Hardware</h2>
        <div class="card">
            <h3>CPU</h3>
            <pre>{data['hardware']['cpu']}</pre>
        </div>
        <div class="card">
            <h3>GPU(s)</h3>
            <pre>{chr(10).join(data['hardware']['gpu'])}</pre>
        </div>
        <div class="card">
            <h3>Memory</h3>
            <pre>{data['hardware']['ram']}</pre>
        </div>
        <div class="card">
            <h3>Storage</h3>
            <pre>{data['hardware']['storage']}</pre>
        </div>
        <div class="card">
            <h3>Motherboard</h3>
            <pre>{data['hardware']['motherboard']}</pre>
        </div>
        <div class="card">
            <h3>Network Devices</h3>
            <pre>{chr(10).join(data['hardware']['network'])}</pre>
        </div>

        <h2>Network</h2>
        <div class="card">
            <h3>Interfaces</h3>
            <pre>{data['network']['interfaces']}</pre>
        </div>
        <div class="card">
            <h3>DNS</h3>
            <pre>{data['network']['dns']}</pre>
        </div>

        <h2>Diagnostic Issues ({len(data['issues'])})</h2>
        {self._format_issues_html(data['issues'])}
    </div>
</body>
</html>"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)

    def _get_health_color(self, score: int) -> str:
        if score >= 90: return "#4dff9e"
        elif score >= 70: return "#a6ff9e"
        elif score >= 50: return "#ffd24d"
        elif score >= 30: return "#ffaa4d"
        return "#ff4d6a"

    def _get_health_label(self, score: int) -> str:
        if score >= 90: return "Excellent"
        elif score >= 70: return "Good"
        elif score >= 50: return "Fair"
        elif score >= 30: return "Poor"
        return "Critical"

    def _format_issues_html(self, issues: list) -> str:
        if not issues:
            return '<div class="card"><p style="color: #4dff9e;">✓ No issues detected</p></div>'

        html = ""
        for issue in issues:
            html += f'''
            <div class="issue {issue['severity']}">
                <div class="issue-title">[{issue['severity'].upper()}] {issue['title']}</div>
                <div class="issue-detail">{issue['detail']}</div>
                {f"<div class=\"issue-suggestion\">{issue['suggestion']}</div>" if issue['suggestion'] else ""}
            </div>
            '''
        return html