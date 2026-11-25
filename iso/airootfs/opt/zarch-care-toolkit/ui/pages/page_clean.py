"""
ui/pages/page_clean.py
======================
System cleanup: orphan packages, pacman cache trimming, journal vacuum.

Fixes applied:
  BUG-C01  — Uses WorkerMixin._spawn_worker() for automatic worker cleanup.
  BUG-C03  — PrivilegedSequenceRunner (fixed separately) handles re-runs.
  BUG-C04  — Buttons are re-enabled via on_all_done callback from the runner.
  BUG-H03  — Cache clean button catches RuntimeError from build_cache_clean_command
              when paccache is missing, showing a clear message instead of crash.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QMessageBox,
)

from core import maintenance
from core.operation_log import op_log
from ui.worker_mixin import WorkerMixin
from ui.privileged_sequence import PrivilegedSequenceRunner
from core.logger import get_logger

logger = get_logger(__name__)


class CleanSystemPage(QWidget, WorkerMixin):
    def __init__(self):
        super().__init__()
        self._workers: list = []
        self._orphans: list[str] = []

        layout = QVBoxLayout(self)

        title = QLabel("Clean System")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        row1 = QHBoxLayout()
        self.btn_find_orphans = QPushButton("Find Orphan Packages")
        self.btn_find_orphans.clicked.connect(self.find_orphans)
        row1.addWidget(self.btn_find_orphans)

        self.btn_remove_orphans = QPushButton("Remove Orphan Packages")
        self.btn_remove_orphans.setObjectName("dangerButton")
        self.btn_remove_orphans.setEnabled(False)
        self.btn_remove_orphans.clicked.connect(self.remove_orphans)
        row1.addWidget(self.btn_remove_orphans)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_cache_size = QPushButton("Show Cache Size")
        self.btn_cache_size.clicked.connect(self.show_cache_size)
        row2.addWidget(self.btn_cache_size)

        self.btn_clean_cache = QPushButton("Clean Cache (keep latest version)")
        self.btn_clean_cache.clicked.connect(self.clean_cache)
        row2.addWidget(self.btn_clean_cache)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.btn_journal_size = QPushButton("Show Log Size")
        self.btn_journal_size.clicked.connect(self.show_journal_size)
        row3.addWidget(self.btn_journal_size)

        self.btn_vacuum = QPushButton("Vacuum Logs Older Than 2 Weeks")
        self.btn_vacuum.clicked.connect(self.vacuum_journal)
        row3.addWidget(self.btn_vacuum)
        layout.addLayout(row3)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        self.runner = PrivilegedSequenceRunner(self.output)

    # ── internal helper ───────────────────────────────────────────────────────

    def _run_async(self, func, on_done, *args) -> None:
        """
        Run *func* in a background worker and call *on_done(result)* on success.
        Note: on_done is connected as a signal callback, NOT passed to the function.
        """
        self.output.setPlainText("Running…")
        worker = self._spawn_worker(func, *args)
        worker.finished_ok.connect(on_done)
        worker.failed.connect(lambda e: self.output.setPlainText(f"Error: {e}"))
        worker.start()

    # ── orphan packages ───────────────────────────────────────────────────────

    def find_orphans(self) -> None:
        def done(orphans: list[str]) -> None:
            self._orphans = orphans
            if not orphans:
                self.output.setPlainText("✅ No orphan packages found.")
                self.btn_remove_orphans.setEnabled(False)
            else:
                self.output.setPlainText(
                    "Orphan packages found:\n" + "\n".join(orphans)
                )
                self.btn_remove_orphans.setEnabled(True)

        self._run_async(maintenance.get_orphan_packages, done)

    def remove_orphans(self) -> None:
        if not self._orphans:
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Removal",
            "The following packages will be permanently removed:\n\n"
            + "\n".join(self._orphans)
            + "\n\nAre you sure?",
        )
        if confirm != QMessageBox.Yes:
            return
        cmd = maintenance.build_orphan_removal_command(self._orphans)
        self.runner.run([("Removing orphan packages", cmd)])
        self._orphans = []
        self.btn_remove_orphans.setEnabled(False)

    # ── cache ─────────────────────────────────────────────────────────────────

    def show_cache_size(self) -> None:
        self._run_async(
            maintenance.get_pacman_cache_size,
            lambda s: self.output.setPlainText(f"Current pacman cache size:\n{s}"),
        )

    def clean_cache(self) -> None:
        # BUG-H03 fix: check paccache availability before showing confirm dialog
        try:
            cmd = maintenance.build_cache_clean_command(1)
        except RuntimeError as exc:
            QMessageBox.warning(self, "paccache Not Found", str(exc))
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Cleanup",
            "This removes old package versions from the cache and keeps only the "
            "latest version of each package. Continue?",
        )
        if confirm != QMessageBox.Yes:
            return
        self.runner.run([("Cleaning pacman cache", cmd)])

    # ── journal ───────────────────────────────────────────────────────────────

    def show_journal_size(self) -> None:
        self._run_async(
            maintenance.get_journal_size,
            lambda s: self.output.setPlainText(f"Current log size:\n{s}"),
        )

    def vacuum_journal(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Confirm",
            "This deletes journal logs older than 2 weeks. Continue?",
        )
        if confirm != QMessageBox.Yes:
            return
        self.runner.run([(
            "Vacuuming journal logs",
            maintenance.build_journal_vacuum_command("2weeks"),
        )])
