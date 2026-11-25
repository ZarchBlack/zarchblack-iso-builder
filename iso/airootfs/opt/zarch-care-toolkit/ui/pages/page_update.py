"""
ui/pages/page_update.py
=======================
System update page — runs pacman -Syu via pkexec.

Fixes applied:
  BUG-Q05 — Added a failed-exit handler that shows a clear error message in
             the output area when the pkexec step returns a non-zero exit code
             (e.g. user cancelled authentication or pacman error).
  BUG-C04 — "Update Now" button is only re-enabled after the sequence
             completes (on_all_done callback) instead of staying active during
             the privileged operation.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QMessageBox,
)

from core import maintenance
from ui.privileged_sequence import PrivilegedSequenceRunner
from core.logger import get_logger

logger = get_logger(__name__)


class UpdateSystemPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Update System")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("Runs a full system update via pacman -Syu.")
        subtitle.setStyleSheet("color: #9d94c2;")
        layout.addWidget(subtitle)

        self.btn_update = QPushButton("⬆  Update Now")
        self.btn_update.clicked.connect(self.run_update)
        layout.addWidget(self.btn_update)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        # BUG-Q05 fix: pass on_all_done so we know when the step finishes
        self.runner = PrivilegedSequenceRunner(
            self.output,
            on_all_done=self._on_done,
        )

    # ── callbacks ─────────────────────────────────────────────────────────────

    def _on_done(self) -> None:
        """Called by PrivilegedSequenceRunner after the update step finishes."""
        self.btn_update.setEnabled(True)
        # BUG-Q05 fix: check exit code hint in the output text
        text = self.output.toPlainText()
        if "exit code: 0" not in text and "exit code" in text:
            self.output.insertPlainText(
                "\n⚠️  The update command returned a non-zero exit code.\n"
                "Check the output above for details, or run:\n"
                "  journalctl -p 3 -b -n 30\n"
            )
            logger.warning("UpdateSystemPage: update finished with non-zero exit code")
        else:
            logger.info("UpdateSystemPage: update completed successfully")

    # ── main action ───────────────────────────────────────────────────────────

    def run_update(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Confirm Update",
            "This will run: pacman -Syu\n"
            "This updates all system packages. Continue?",
        )
        if confirm != QMessageBox.Yes:
            return

        self.btn_update.setEnabled(False)   # BUG-C04 fix: disable until done
        self.runner.run([
            ("System update (pacman -Syu)", maintenance.build_update_command()),
        ])
