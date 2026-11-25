"""
ui/pages/page_pacnew.py
=======================
.pacnew files review helper.

Fixes applied:
  BUG-P03 — Lazy initialization: scan runs on first showEvent, not __init__.
  BUG-C01 — Uses WorkerMixin._spawn_worker() for automatic worker cleanup.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel,
)

from core import maintenance
from ui.worker_mixin import WorkerMixin
from core.logger import get_logger

logger = get_logger(__name__)


class PacnewPage(QWidget, WorkerMixin):
    def __init__(self):
        super().__init__()
        self._workers: list = []
        self._initialized = False   # BUG-P03: lazy init flag

        layout = QVBoxLayout(self)

        title = QLabel(".pacnew Files")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "New config files pacman kept alongside your edited ones "
            "instead of overwriting them. Review and merge manually."
        )
        subtitle.setStyleSheet("color: #9d94c2;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.btn_scan = QPushButton("Find .pacnew Files")
        self.btn_scan.clicked.connect(self.run_scan)
        layout.addWidget(self.btn_scan)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    # BUG-P03 fix: run first scan on first show
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._initialized:
            self._initialized = True
            self.run_scan()

    def run_scan(self) -> None:
        self.btn_scan.setEnabled(False)
        self.output.setPlainText("Searching /etc …")

        worker = self._spawn_worker(maintenance.find_pacnew_files)   # BUG-C01 fix

        def done(files: list[str]) -> None:
            self.btn_scan.setEnabled(True)
            if not files:
                self.output.setPlainText("✅ No .pacnew files awaiting review.")
            else:
                self.output.setPlainText(
                    f"{len(files)} file(s) need manual review:\n\n"
                    + "\n".join(files)
                    + "\n\nTip: use a tool like pacdiff to compare and merge them."
                )

        def failed(err: str) -> None:
            self.btn_scan.setEnabled(True)
            self.output.setPlainText(f"Error: {err}")
            logger.warning("PacnewPage scan failed: %s", err)

        worker.finished_ok.connect(done)
        worker.failed.connect(failed)
        worker.start()
