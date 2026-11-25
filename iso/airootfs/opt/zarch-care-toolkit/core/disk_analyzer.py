"""
core/disk_analyzer.py
=====================
Disk space breakdown: mounted filesystems + biggest top-level folders in $HOME.

Fixes applied:
  BUG-H05 — Logging added throughout.
"""

import os
from core.privilege import run_unprivileged
from core.logger import get_logger

logger = get_logger(__name__)


def get_filesystems_summary() -> str:
    code, out = run_unprivileged(["df", "-h", "--total"])
    if code != 0:
        logger.warning("get_filesystems_summary: df failed (exit %d)", code)
        return "Could not read filesystem usage."
    return out


def get_home_breakdown() -> str:
    """
    Size of each top-level folder in the user's home directory.
    Can take a few seconds on large home directories.
    """
    home = os.path.expanduser("~")
    logger.debug("get_home_breakdown: analysing %s", home)
    code, out = run_unprivileged(["du", "-sh", "--max-depth=1", home], timeout=60)
    if code != 0:
        logger.warning("get_home_breakdown: du failed for %s (exit %d)", home, code)
        return (
            f"Could not analyze {home} "
            "(it may be too large, or 'du' is unavailable)."
        )

    lines = out.strip().splitlines()

    def _size_to_bytes(size_str: str) -> float:
        units = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}
        s = size_str.strip()
        if s and s[-1] in units:
            try:
                return float(s[:-1]) * units[s[-1]]
            except ValueError:
                return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0

    parsed: list[tuple[str, str, float]] = []
    for line in lines:
        parts = line.split("\t") if "\t" in line else line.split(None, 1)
        if len(parts) == 2:
            parsed.append((parts[0], parts[1], _size_to_bytes(parts[0])))

    parsed.sort(key=lambda x: x[2], reverse=True)
    return "\n".join(f"{size}\t{path}" for size, path, _ in parsed)


def get_largest_pacman_cache_files(top_n: int = 10) -> str:
    code, out = run_unprivileged(
        [
            "find", "/var/cache/pacman/pkg",
            "-maxdepth", "1", "-type", "f",
            "-printf", "%s\t%p\n",
        ]
    )
    # Distinguish: non-zero exit = command failure; exit 0 + no output = empty cache
    if code != 0:
        logger.warning("get_largest_pacman_cache_files: find failed (exit %d)", code)
        return "Could not read pacman cache directory."
    if not out.strip():
        logger.debug("get_largest_pacman_cache_files: cache directory is empty")
        return "Cache directory is empty."

    entries: list[tuple[int, str]] = []
    for line in out.strip().splitlines():
        try:
            size_str, path = line.split("\t", 1)
            entries.append((int(size_str), path))
        except ValueError:
            continue

    entries.sort(reverse=True)
    lines = [
        f"{size / (1024 ** 2):.1f} MB\t{path}"
        for size, path in entries[:top_n]
    ]
    logger.debug("get_largest_pacman_cache_files: %d entries found", len(entries))
    return "\n".join(lines) if lines else "Cache directory is empty."
