"""
ui/worker_mixin.py
==================
Mixin class that gives any QWidget a managed list of FunctionWorker threads.

Fixes applied:
  BUG-C01 — Memory leak: every completed worker is automatically removed from
             self._workers via the worker's `done` signal.

Usage:
    class MyPage(QWidget, WorkerMixin):
        def __init__(self):
            super().__init__()
            self._workers = []   # required attribute

        def do_something(self):
            worker = self._spawn_worker(some_function, arg1, arg2)
            worker.finished_ok.connect(self._on_done)
            worker.failed.connect(self._on_error)
"""

from ui.workers import FunctionWorker
from core.logger import get_logger

logger = get_logger(__name__)


class WorkerMixin:
    """
    Mixin providing ``_spawn_worker`` which creates, registers and
    auto-cleans a FunctionWorker.

    The host class MUST define ``self._workers: list`` before calling
    ``_spawn_worker``.
    """

    def _spawn_worker(self, func, *args, **kwargs) -> FunctionWorker:
        """
        Create a FunctionWorker, register it in self._workers, and arrange
        for it to be removed automatically when it finishes.

        Returns the worker (not yet started — caller calls worker.start()).
        """
        worker = FunctionWorker(func, *args, **kwargs)

        def _cleanup():
            try:
                self._workers.remove(worker)
            except (ValueError, AttributeError):
                pass
            logger.debug(
                "Worker for %s cleaned up (%d remaining)",
                getattr(func, "__name__", "?"),
                len(getattr(self, "_workers", [])),
            )

        worker.done.connect(_cleanup)
        self._workers.append(worker)
        return worker

    def _cancel_all_workers(self) -> None:
        """
        Request all running workers to stop (non-blocking).
        Workers that are in a blocking system call will finish their current
        call before stopping — this does NOT forcefully kill them.
        """
        workers = list(getattr(self, "_workers", []))
        running = [w for w in workers if w.isRunning()]
        if not running:
            return
        logger.debug("_cancel_all_workers: requesting %d worker(s) to quit", len(running))
        for w in running:
            w.quit()

    def _wait_all_workers(self, timeout_ms: int = 3000) -> None:
        """
        Wait for all running workers to finish.
        Each worker gets at most *timeout_ms* milliseconds.
        """
        workers = list(getattr(self, "_workers", []))
        for w in workers:
            if w.isRunning():
                w.wait(timeout_ms)
