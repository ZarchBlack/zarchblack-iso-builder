"""
ui/workers.py
=============
Run any slow function (diagnostics, hardware scan …) in a separate QThread
so the GUI never freezes.

Fixes applied:
  BUG-C01 — Memory leak: workers were appended to _workers lists but never
             removed.  The worker now emits a `done` signal (fired regardless
             of success or failure) so callers can purge it from their list.
"""

from PySide6.QtCore import QThread, Signal
from core.logger import get_logger

logger = get_logger(__name__)


class FunctionWorker(QThread):
    """
    Runs ``func(*args, **kwargs)`` in a background thread.

    Signals
    -------
    finished_ok(object)   — emitted with the return value on success
    failed(str)           — emitted with the error message on exception
    done()                — emitted in BOTH cases (use to clean up references)
    """

    finished_ok = Signal(object)
    failed = Signal(str)
    done = Signal()          # BUG-C01 fix: always fires so callers can remove this worker

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished_ok.emit(result)
        except Exception as exc:
            logger.exception("FunctionWorker error in %s: %s", getattr(self.func, "__name__", "?"), exc)
            self.failed.emit(str(exc))
        finally:
            self.done.emit()     # always notify — BUG-C01 fix
