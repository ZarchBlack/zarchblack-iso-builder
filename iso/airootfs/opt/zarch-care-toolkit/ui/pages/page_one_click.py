"""
ui/pages/page_one_click.py
==========================
A guided full checkup: update, remove orphans, trim cache, vacuum logs —
each step optional and shown clearly before anything runs.

Fixes applied:
  BUG-C04 — "Run" button is now re-enabled via the runner's on_all_done
             callback (i.e. AFTER the last step finishes), not immediately
             after calling runner.run() which starts the sequence
             asynchronously.
  BUG-C03 — PrivilegedSequenceRunner (fixed separately) guards against a
             second call while the first is running, but we also disable the
             button here for belt-and-suspenders safety.
  BUG-C01 — Uses WorkerMixin._spawn_worker() so the orphan-fetch worker is
             automatically removed from self._workers when done.
  BUG-H03 — Cache-clean step is skipped gracefully if paccache is missing,
             with a clear message in the output area.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QCheckBox, QMessageBox,
)

from core import maintenance
from ui.worker_mixin import WorkerMixin
from ui.privileged_sequence import PrivilegedSequenceRunner
from core.logger import get_logger

logger = get_logger(__name__)


class OneClickMaintenancePage(QWidget, WorkerMixin):
    def __init__(self):
        super().__init__()
        self._workers: list = []   # required by WorkerMixin
        layout = QVBoxLayout(self)

        title = QLabel("One-Click Maintenance")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Runs a complete maintenance checkup. Uncheck any step you'd "
            "rather skip — everything still needs one confirmation before it runs."
        )
        subtitle.setStyleSheet("color: #9d94c2;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.chk_update  = QCheckBox("Update system (pacman -Syu)")
        self.chk_update.setChecked(True)
        layout.addWidget(self.chk_update)

        self.chk_orphans = QCheckBox("Remove orphan packages")
        self.chk_orphans.setChecked(True)
        layout.addWidget(self.chk_orphans)

        self.chk_cache   = QCheckBox("Trim pacman cache (keep latest version)")
        self.chk_cache.setChecked(True)
        layout.addWidget(self.chk_cache)

        self.chk_journal = QCheckBox("Vacuum logs older than 2 weeks")
        self.chk_journal.setChecked(True)
        layout.addWidget(self.chk_journal)

        self.btn_run = QPushButton("🚀  Run Full Maintenance")
        self.btn_run.clicked.connect(self.run_maintenance)
        layout.addWidget(self.btn_run)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        # BUG-C04 fix: pass on_all_done so the runner re-enables the button
        self.runner = PrivilegedSequenceRunner(
            self.output,
            on_all_done=self._on_sequence_done,
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _on_sequence_done(self) -> None:
        """Called by PrivilegedSequenceRunner after the LAST step finishes."""
        self.btn_run.setEnabled(True)
        logger.info("OneClickMaintenancePage: maintenance sequence completed")

    # ── main action ───────────────────────────────────────────────────────────

    def run_maintenance(self) -> None:
        steps: list[tuple[str, list[str]]] = []
        summary: list[str] = []

        if self.chk_update.isChecked():
            steps.append(("System update", maintenance.build_update_command()))
            summary.append("Full system update (pacman -Syu)")

        if self.chk_orphans.isChecked():
            summary.append("Remove orphan packages (fetched live before running)")

        if self.chk_cache.isChecked():
            try:
                cmd = maintenance.build_cache_clean_command(1)
                steps.append(("Trimming pacman cache", cmd))
                summary.append("Trim pacman cache (keep latest version)")
            except RuntimeError as exc:
                # BUG-H03 fix: paccache missing — warn and skip this step
                self.output.setPlainText(
                    f"⚠️ Cache-clean step skipped:\n{exc}\n\n"
                    "Uncheck 'Trim pacman cache' or install pacman-contrib to use this step."
                )
                self.chk_cache.setChecked(False)
                return

        if self.chk_journal.isChecked():
            steps.append((
                "Vacuuming journal logs",
                maintenance.build_journal_vacuum_command("2weeks"),
            ))
            summary.append("Vacuum logs older than 2 weeks")

        if not summary:
            self.output.setPlainText("No steps selected.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Full Maintenance",
            "The following steps will run in order:\n\n  • "
            + "\n  • ".join(summary)
            + "\n\nContinue?",
        )
        if confirm != QMessageBox.Yes:
            return

        # BUG-C04 fix: disable button here; it will be re-enabled by _on_sequence_done
        self.btn_run.setEnabled(False)

        if self.chk_orphans.isChecked():
            # Fetch orphan list live right before running
            worker = self._spawn_worker(maintenance.get_orphan_packages)   # BUG-C01

            def got_orphans(orphans: list[str]) -> None:
                if orphans:
                    insert_at = 1 if steps else 0
                    steps.insert(
                        insert_at,
                        ("Removing orphan packages",
                         maintenance.build_orphan_removal_command(orphans)),
                    )
                logger.info("OneClickMaintenancePage: starting %d step(s)", len(steps))
                self.runner.run(steps)

            def fetch_failed(err: str) -> None:
                logger.warning("OneClickMaintenancePage: orphan fetch failed: %s", err)
                # Still run the other steps even if orphan fetch failed
                self.runner.run(steps)

            worker.finished_ok.connect(got_orphans)
            worker.failed.connect(fetch_failed)
            worker.start()
        else:
            logger.info("OneClickMaintenancePage: starting %d step(s)", len(steps))
            self.runner.run(steps)
