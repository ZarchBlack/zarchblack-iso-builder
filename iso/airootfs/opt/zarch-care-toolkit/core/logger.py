"""
core/logger.py
==============
Centralized logging configuration for ZarchCare.

All core modules import their logger from here, so the entire app logs to
a single file at ~/.local/share/zarchcare/zarchcare.log with consistent formatting.

Usage in any module:
    from core.logger import get_logger
    logger = get_logger(__name__)
    logger.warning("something went wrong: %s", detail)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_LOG_FILE = os.path.join(os.path.expanduser("~"), ".local", "share", "zarchcare", "zarchcare.log")
_LOG_DIR = os.path.dirname(_LOG_FILE)

_FORMATTER = logging.Formatter(
    fmt="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ─── root logger (configures once) ───────────────────────────────────────────

def _setup_root_logger() -> None:
    root = logging.getLogger("zarchcare")
    if root.handlers:          # already configured (e.g. during tests)
        return
    root.setLevel(logging.DEBUG)

    # File handler — rotates at 2 MB, keeps 2 backups
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        fh = RotatingFileHandler(_LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(_FORMATTER)
        root.addHandler(fh)
    except OSError as exc:
        # If we can't write the log file (e.g. no home dir), fall back to stderr
        print(f"[ZarchCare] Warning: cannot open log file {_LOG_FILE}: {exc}", file=sys.stderr)

    # Stderr handler — only WARNING and above so the terminal isn't noisy
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sh.setFormatter(_FORMATTER)
    root.addHandler(sh)


_setup_root_logger()


def get_logger(name: str) -> logging.Logger:
    """Return a logger namespaced under 'zarchcare.<name>'."""
    # Ensure the name is rooted under our namespace so level/handlers apply
    if not name.startswith("zarchcare"):
        name = f"zarchcare.{name}"
    return logging.getLogger(name)
