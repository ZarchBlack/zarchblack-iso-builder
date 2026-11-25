"""
ui/pages/page_health_score.py
=============================
Full automatic diagnosis page with health score display.

v1.2 changes:
  - Score breakdown table shows per-category point deductions.
  - "What does this mean?" explanation label.
  - Operation log integration.
  - Buttons properly disabled/re-enabled during scan.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QFrame,
)

from core import troubleshoot
from core.dashboard import compute_health_score
from core.maintenance import get_orphan_packages
from core.operation_log import op_log
from ui.worker_mixin import WorkerMixin
from ui.widgets_common import HealthBadge
from core.logger import get_logger

logger = get_logger(__name__)


def _build_score_breakdown(issues: list, orphan_count: int, updates_text: str) -> str:
    """
    Return a human-readable breakdown of how the health score was computed.
    """
    lines = ["Score Breakdown:"]
    lines.append("─" * 40)

    total_deduction = 0
    error_count = warning_count = info_count = boot_count = 0
    boot_deduction = 0

    for issue in issues:
        if issue.title.startswith("Boot log") or issue.title.startswith("…"):
            if issue.severity == "warning":
                boot_count += 1
                boot_deduction += 3
        else:
            if issue.severity == "error":
                error_count += 1
            elif issue.severity == "warning":
                warning_count += 1
            elif issue.severity == "info":
                info_count += 1

    if error_count:
        d = error_count * 10
        lines.append(f"  🔴 Failed services:   {error_count} × -10 = -{d}")
        total_deduction += d
    if warning_count:
        d = warning_count * 5
        lines.append(f"  🟡 Warnings:          {warning_count} × -5  = -{d}")
        total_deduction += d
    if info_count:
        d = info_count * 1
        lines.append(f"  🔵 Info items:        {info_count} × -1  = -{d}")
        total_deduction += d
    if boot_count:
        actual = min(boot_deduction, 15)
        lines.append(f"  📋 Boot log entries:  {boot_count} entries = -{actual} (capped at 15)")
        total_deduction += actual
    if orphan_count:
        d = min(orphan_count, 10)
        lines.append(f"  👻 Orphan packages:   {orphan_count} × -1  = -{d} (max 10)")
        total_deduction += d
    if "available" in updates_text and not updates_text.startswith("0"):
        try:
            n = int(updates_text.split()[0])
            if n > 0:
                lines.append(f"  🔄 Pending updates:   {n} updates = -2 (flat)")
                total_deduction += 2
        except (ValueError, IndexError):
            pass

    if total_deduction == 0:
        lines.append("  ✅ No deductions — system is healthy!")
    else:
        lines.append("─" * 40)
        lines.append(f"  Total deduction:  -{total_deduction}")
        lines.append(f"  Final score:       100 - {total_deduction} = {max(0, 100-total_deduction)}/100")

    return "\n".join(lines)


class HealthScorePage(QWidget, WorkerMixin):
    def __init__(self):
        super().__init__()
        self._workers: list = []
        self._initialized = False
        self._last_issues = []
        self._last_orphans = 0

        layout = QVBoxLayout(self)

        # ── header ────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Health Score")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()
        self.badge = HealthBadge()
        header.addWidget(self.badge)
        layout.addLayout(header)

        subtitle = QLabel(
            "Full automatic diagnosis: failed services, boot errors, "
            "disk space, pacman locks, unresolved .pacnew files."
        )
        subtitle.setStyleSheet("color: #9d94c2;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ── actions ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.btn_scan = QPushButton("🔍  Run Full Scan")
        self.btn_scan.clicked.connect(self.run_scan)
        btn_row.addWidget(self.btn_scan)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── breakdown panel ───────────────────────────────────────────────────
        self.breakdown_label = QLabel("")
        self.breakdown_label.setStyleSheet(
            "color: #c0b8e0; font-family: monospace; font-size: 12px;"
            "background: #1a1628; border-radius: 6px; padding: 8px;"
        )
        self.breakdown_label.setWordWrap(True)
        self.breakdown_label.hide()
        layout.addWidget(self.breakdown_label)

        # ── separator ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #3a3050;")
        layout.addWidget(sep)

        # ── issues output ─────────────────────────────────────────────────────
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._initialized:
            self._initialized = True
            self.run_scan()

    def run_scan(self) -> None:
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("🔍  Scanning…")
        self.output.setPlainText("Scanning system…")
        self.breakdown_label.hide()

        worker = self._spawn_worker(self._collect)
        worker.finished_ok.connect(self._render)
        worker.failed.connect(self._on_failed)
        worker.start()

    def _on_failed(self, err: str) -> None:
        self.output.setPlainText(f"❌ Scan failed: {err}")
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("🔍  Run Full Scan")
        op_log.record("Health scan", success=False, detail=err)

    @staticmethod
    def _collect():
        issues  = troubleshoot.run_full_diagnosis()
        orphans = len(get_orphan_packages())
        score   = compute_health_score(issues, orphans, "")
        return issues, orphans, score

    def _render(self, result) -> None:
        issues, orphan_count, score = result
        self._last_issues  = issues
        self._last_orphans = orphan_count

        self.badge.set_score(score)
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("🔍  Run Full Scan")

        # Show breakdown
        breakdown = _build_score_breakdown(issues, orphan_count, "")
        self.breakdown_label.setText(breakdown)
        self.breakdown_label.show()

        op_log.record(
            "Health scan completed",
            success=True,
            detail=f"score={score} issues={len(issues)} orphans={orphan_count}",
        )
        logger.debug("HealthScorePage: score=%d issues=%d", score, len(issues))

        if not issues:
            self.output.setPlainText("✅ No apparent issues found. Your system looks healthy.")
            return

        icon_map = {"error": "🔴", "warning": "🟡", "info": "🔵"}
        lines: list[str] = []
        for issue in issues:
            lines.append(f"{icon_map.get(issue.severity, '•')} {issue.title}")
            lines.append(f"    Detail: {issue.detail}")
            if issue.suggestion:
                lines.append(f"    Suggestion: {issue.suggestion}")
            lines.append("")
        self.output.setPlainText("\n".join(lines))
