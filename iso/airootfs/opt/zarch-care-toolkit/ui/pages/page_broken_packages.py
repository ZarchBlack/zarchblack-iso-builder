"""
ui/pages/page_broken_packages.py
=================================
pacman -Qk integrity scan for packages with missing or altered owned files.

Fixes applied:
  BUG-C01 — Uses WorkerMixin._spawn_worker() for automatic worker cleanup.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel,
)

from core import broken_packages
from ui.worker_mixin import WorkerMixin
from core.logger import get_logger

logger = get_logger(__name__)


class BrokenPackagesPage(QWidget, WorkerMixin):
    def __init__(self):
        super().__init__()
        self._workers: list = []

        layout = QVBoxLayout(self)

        title = QLabel("Broken Packages")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Checks whether every file owned by an installed package "
            "still exists on disk (pacman -Qk). Can take up to a minute."
        )
        subtitle.setStyleSheet("color: #9d94c2;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.btn_scan = QPushButton("Scan for Broken Packages")
        self.btn_scan.clicked.connect(self.run_scan)
        layout.addWidget(self.btn_scan)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def run_scan(self) -> None:
        self.btn_scan.setEnabled(False)
        self.output.setPlainText("Scanning installed packages, this may take a minute…")

        worker = self._spawn_worker(broken_packages.scan_broken_packages)   # BUG-C01 fix

        def done(problems: list[str]) -> None:
            self.btn_scan.setEnabled(True)
            if not problems:
                self.output.setPlainText("✅ No broken packages found.")
            else:
                self.output.setPlainText(
                    f"⚠️  {len(problems)} package(s) reported issues:\n\n"
                    + "\n".join(problems)
                    + "\n\nTip: reinstalling a package (pacman -S <name>) restores its files."
                )
            logger.info("BrokenPackagesPage: scan done — %d issue(s)", len(problems))

        def failed(err: str) -> None:
            self.btn_scan.setEnabled(True)
            self.output.setPlainText(f"Error: {err}")
            logger.warning("BrokenPackagesPage: scan failed: %s", err)

        worker.finished_ok.connect(done)
        worker.failed.connect(failed)
        worker.start()
