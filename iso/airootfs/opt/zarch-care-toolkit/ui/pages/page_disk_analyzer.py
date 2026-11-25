"""
ui/pages/page_disk_analyzer.py
==============================
Disk space breakdown: mounted filesystems + biggest top-level folders in $HOME.

Fixes applied:
  BUG-P03 — Lazy initialization: filesystem scan now runs only when the page
             is first shown (showEvent), not at __init__ time while every other
             page is still being constructed.
  BUG-C01 — Uses WorkerMixin._spawn_worker() for automatic worker cleanup.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel,
)

from core import disk_analyzer
from ui.worker_mixin import WorkerMixin
from core.logger import get_logger

logger = get_logger(__name__)


class DiskAnalyzerPage(QWidget, WorkerMixin):
    def __init__(self):
        super().__init__()
        self._workers: list = []
        self._initialized = False   # BUG-P03: lazy init flag

        layout = QVBoxLayout(self)

        title = QLabel("Disk Analyzer")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        row = QHBoxLayout()
        self.btn_fs = QPushButton("Filesystem Usage")
        self.btn_fs.clicked.connect(self.show_filesystems)
        row.addWidget(self.btn_fs)

        self.btn_home = QPushButton("Analyze Home Folder (may take a moment)")
        self.btn_home.clicked.connect(self.show_home_breakdown)
        row.addWidget(self.btn_home)

        self.btn_cache = QPushButton("Largest Pacman Cache Files")
        self.btn_cache.clicked.connect(self.show_cache_files)
        row.addWidget(self.btn_cache)
        layout.addLayout(row)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    # BUG-P03 fix: run first scan on first show, not at construction time
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._initialized:
            self._initialized = True
            self.show_filesystems()

    def _run_async(self, func, *args) -> None:
        self.output.setPlainText("Running…")
        worker = self._spawn_worker(func, *args)   # BUG-C01 fix
        worker.finished_ok.connect(self.output.setPlainText)
        worker.failed.connect(lambda e: self.output.setPlainText(f"Error: {e}"))
        worker.start()

    def show_filesystems(self) -> None:
        self._run_async(disk_analyzer.get_filesystems_summary)

    def show_home_breakdown(self) -> None:
        self._run_async(disk_analyzer.get_home_breakdown)

    def show_cache_files(self) -> None:
        self._run_async(disk_analyzer.get_largest_pacman_cache_files, 15)
