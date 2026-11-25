"""
core/broken_packages.py
=======================
Detect packages with missing or altered owned files (pacman -Qk).

Fixes applied:
  BUG-H05 — Logging added so scan results and errors are recorded to the
             ZarchCare log file.
"""

from core.privilege import run_unprivileged
from core.logger import get_logger

logger = get_logger(__name__)


def scan_broken_packages() -> list[str]:
    """
    Runs `pacman -Qk`, which checks that every file owned by every installed
    package still exists on disk.

    Returns only the lines that report actual problems (pacman prints one
    summary line per package; healthy ones say '0 missing files').
    """
    logger.debug("scan_broken_packages: starting (may take ~60 s)")
    code, out = run_unprivileged(["pacman", "-Qk"], timeout=120)

    # pacman -Qk exits 0 if all files OK, 1 if any issues found
    if code not in (0, 1):
        msg = f"Could not run the scan: {out.strip()}"
        logger.error("scan_broken_packages: pacman -Qk exit code %d — %s", code, out.strip())
        return [msg]

    problems: list[str] = []
    for line in out.strip().splitlines():
        if not line.strip():
            continue
        if line.startswith("0 missing files") or ": 0 missing files" in line:
            continue
        problems.append(line.strip())

    logger.info(
        "scan_broken_packages: done — %d problem line(s) found (exit code %d)",
        len(problems), code,
    )
    return problems


def build_reinstall_command(package_name: str) -> list[str]:
    """Reinstalling a package restores any missing/altered files it owns."""
    if not package_name.strip():
        raise ValueError("package_name must not be empty.")
    return ["pacman", "-S", "--noconfirm", package_name.strip()]
