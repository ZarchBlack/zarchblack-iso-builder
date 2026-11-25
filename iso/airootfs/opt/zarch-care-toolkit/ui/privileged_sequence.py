"""
ui/privileged_sequence.py
=========================
Run a sequence of privileged commands one after another, streaming combined
output into a QTextEdit. Used by Clean System, Quick Clean and One-Click
Maintenance, which all chain multiple pacman/journalctl steps.

Fixes applied:
  BUG-C03 — Race condition: calling run() while a previous sequence is still
             running now kills the old process cleanly before starting fresh.
  BUG-C04 — on_all_done callback is invoked by the runner itself (not the
             caller) so the caller's button is only re-enabled when the *last*
             step actually finishes.
"""

from PySide6.QtCore import QProcess
from PySide6.QtGui import QTextCursor
from core.privilege import run_privileged_stream, PrivilegeError
from core.operation_log import op_log
from core.logger import get_logger

logger = get_logger(__name__)


class PrivilegedSequenceRunner:
    def __init__(self, output_widget, on_all_done=None):
        self.output = output_widget
        self.on_all_done = on_all_done   # callable() invoked after last step
        self.steps: list[tuple[str, list[str]]] = []
        self.index: int = 0
        self.proc: QProcess | None = None
        self._running: bool = False

    # ------------------------------------------------------------------ public

    def is_running(self) -> bool:
        return self._running

    def run(self, steps: list[tuple[str, list[str]]]) -> None:
        """
        Start a new sequence.  If a sequence is already running the old
        process is killed first (BUG-C03 fix).

        steps: list of (label, command) tuples executed in order.
        """
        # ── BUG-C03 fix: tear down any in-progress sequence ────────────────
        if self._running and self.proc is not None:
            logger.warning("PrivilegedSequenceRunner.run() called while already running — killing previous process")
            # Disconnect old signals to avoid stale callbacks firing after kill
            try:
                self.proc.readyReadStandardOutput.disconnect()
                self.proc.finished.disconnect()
            except RuntimeError:
                pass   # signals already disconnected
            self.proc.kill()
            self.proc.waitForFinished(2000)
            self.proc = None

        self._running = False
        self.steps = list(steps)
        self.index = 0
        self.output.clear()

        if not self.steps:
            self.output.insertPlainText("No steps to run.\n")
            return

        self._running = True
        self._run_next()

    # ----------------------------------------------------------------- private

    def _run_next(self) -> None:
        if self.index >= len(self.steps):
            self._running = False
            self.output.moveCursor(QTextCursor.End)
            self.output.insertPlainText("\n✅ All steps completed.\n")
            logger.info("PrivilegedSequenceRunner: all %d step(s) completed", len(self.steps))
            # ── BUG-C04 fix: notify caller *here*, not immediately after run() ──
            if self.on_all_done:
                self.on_all_done()
            return

        label, cmd = self.steps[self.index]
        self.output.insertPlainText(f"\n=== {label} ===\n")
        logger.info("PrivilegedSequenceRunner: starting step %d/%d — %s", self.index + 1, len(self.steps), label)

        try:
            self.proc = run_privileged_stream(cmd, self.output)
        except PrivilegeError as exc:
            self._running = False
            msg = f"Privilege error: {exc}\n"
            self.output.insertPlainText(msg)
            logger.error("PrivilegedSequenceRunner privilege error: %s", exc)
            return

        self.proc.readyReadStandardOutput.connect(self._on_output)
        self.proc.finished.connect(self._on_step_finished)
        self.proc.start()

    def _on_output(self) -> None:
        if self.proc is None:
            return
        data = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        self.output.moveCursor(QTextCursor.End)
        self.output.insertPlainText(data)

    def _on_step_finished(self, code: int, status) -> None:
        # C-04 fix: use index 0 (label), not index 1 (command list)
        label = self.steps[self.index][0] if self.index < len(self.steps) else "?"
        self.output.insertPlainText(f"--- exit code: {code} ---\n")
        if code != 0:
            logger.warning("Step '%s' finished with non-zero exit code %d", label, code)
            op_log.record(label, success=False, detail=f"exit code {code}")
        else:
            logger.info("Step '%s' finished successfully", label)
            op_log.record(label, success=True)
        self.index += 1
        self._run_next()
