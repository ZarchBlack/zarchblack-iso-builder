"""
ui/pages/page_quick_clean.py
============================
One button, two very safe steps: journal vacuum + pacman cache trim.
Nothing here can break the system or remove anything you might still need.

Fixes applied:
  BUG-C04  — "Run Quick Clean" button is re-enabled via on_all_done callback
              (after the last step finishes), not immediately on runner.run().
  BUG-H03  — Cache-clean step gracefully skipped with a clear message if
              paccache is not installed.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QMessageBox,
)

from core import maintenance
from ui.privileged_sequence import PrivilegedSequenceRunner
from core.logger import get_logger

logger = get_logger(__name__)


class QuickCleanPage(QWidget):
    """One button, two always-safe cleanup steps."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Quick Clean")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "A fast, always-safe cleanup in one click:\n"
            "  1. Trim journal logs to the last 2 weeks\n"
            "  2. Keep only the latest version of each package in the pacman cache\n"
            "No packages are removed, nothing is deleted permanently beyond old logs/cache."
        )
        subtitle.setStyleSheet("color: #9d94c2;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.btn_run = QPushButton("⚡  Run Quick Clean")
        self.btn_run.clicked.connect(self.run_quick_clean)
        layout.addWidget(self.btn_run)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        # BUG-C04 fix: button re-enabled by on_all_done, not immediately
        self.runner = PrivilegedSequenceRunner(
            self.output,
            on_all_done=lambda: self.btn_run.setEnabled(True),
        )

    def run_quick_clean(self) -> None:
        # BUG-H03 fix: check paccache before showing confirmation dialog
        try:
            cache_cmd = maintenance.build_cache_clean_command(1)
        except RuntimeError as exc:
            QMessageBox.warning(
                self,
                "paccache Not Found",
                str(exc) + "\n\nOnly the journal vacuum step will run.",
            )
            cache_cmd = None

        confirm = QMessageBox.question(
            self,
            "Confirm Quick Clean",
            "This will vacuum old journal logs"
            + (" and trim the pacman cache" if cache_cmd else "")
            + ". Continue?",
        )
        if confirm != QMessageBox.Yes:
            return

        steps: list[tuple[str, list[str]]] = [
            ("Vacuuming journal logs (older than 2 weeks)",
             maintenance.build_journal_vacuum_command("2weeks")),
        ]
        if cache_cmd:
            steps.append(("Trimming pacman cache (keep latest version)", cache_cmd))

        self.btn_run.setEnabled(False)   # BUG-C04 fix: disable until done
        logger.info("QuickCleanPage: running %d step(s)", len(steps))
        self.runner.run(steps)
