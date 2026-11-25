"""
core/maintenance.py
===================
System update + finding leftover files + safe removal (always confirmed before
deletion).

All system queries use ``core.sysctl`` — no bare subprocess calls here.
"""

import os
import shutil

from core.privilege import run_unprivileged
from core.sysctl import (
    pacman_query_orphans,
    pacman_cache_size,
    journalctl_disk_usage,
    find_files,
    du_path,
)
from core.logger import get_logger

logger = get_logger(__name__)


# ─── system update ────────────────────────────────────────────────────────────

def build_update_command() -> list[str]:
    """Return the pacman system update command (executed via pkexec)."""
    return ["pacman", "-Syu", "--noconfirm"]


# ─── orphan packages ──────────────────────────────────────────────────────────

def get_orphan_packages() -> list[str]:
    """Packages installed as dependencies no longer required by anything."""
    code, out = run_unprivileged(["pacman", "-Qtdq"])
    if code != 0 or not out.strip():
        return []
    return [ln.strip() for ln in out.strip().splitlines() if ln.strip()]


def build_orphan_removal_command(packages: list[str]) -> list[str]:
    if not packages:
        raise ValueError("No packages provided for orphan removal.")
    return ["pacman", "-Rns", "--noconfirm", *packages]


# ─── pacman cache ─────────────────────────────────────────────────────────────

def get_pacman_cache_size() -> str:
    """Return human-readable size of the pacman package cache (e.g. '5.8G').

    'du -sh' output format is: '<size>\t<path>\n'
    We extract only the size token (first field).
    """
    code, out = run_unprivileged(["du", "-sh", "/var/cache/pacman/pkg"])
    if code != 0 or not out.strip():
        return "Unknown"
    parts = out.strip().split()
    return parts[0] if parts else "Unknown"


def build_cache_clean_command(keep_versions: int = 1) -> list[str]:
    """
    paccache keeps the last N versions of each package and removes the rest —
    safer than wiping the whole cache.

    Raises RuntimeError if paccache is not installed so callers can show a
    clear message before attempting pkexec.
    """
    if not shutil.which("paccache"):
        raise RuntimeError(
            "paccache is not installed on this system.\n"
            "Install it with: sudo pacman -S pacman-contrib"
        )
    return ["paccache", "-r", "-k", str(keep_versions)]


# ─── .pacnew files ────────────────────────────────────────────────────────────

def find_pacnew_files() -> list[str]:
    """Return a list of .pacnew file paths found under /etc."""
    return find_files("/etc", name_pattern="*.pacnew")


# ─── journal logs ─────────────────────────────────────────────────────────────

def get_journal_size() -> str:
    """Return the journal disk usage string."""
    return journalctl_disk_usage()


def build_journal_vacuum_command(keep_time: str = "2weeks") -> list[str]:
    """Return the journalctl vacuum command (executed via pkexec)."""
    return ["journalctl", f"--vacuum-time={keep_time}"]


# ─── /tmp files ───────────────────────────────────────────────────────────────

def find_old_tmp_files(days: int = 7) -> list[str]:
    """
    Look in /tmp for files older than *days* days.
    Checks both atime and mtime to handle filesystems with noatime/relatime.
    Never deletes automatically — caller must confirm and use build_tmp_cleanup_command.
    """
    by_atime = set(find_files(
        "/tmp",
        atime_days=days,
        maxdepth=2,
    ))
    by_mtime = set(find_files(
        "/tmp",
        mtime_days=days,
        maxdepth=2,
    ))
    combined = sorted(by_atime | by_mtime)
    logger.debug("find_old_tmp_files: %d file(s) older than %d days", len(combined), days)
    return combined


def build_tmp_cleanup_command(paths: list[str]) -> list[str]:
    """
    Build a safe rm command for paths explicitly chosen by the user.

    Every path is validated:
      1. Must start with "/tmp/" (no /tmp itself)
      2. Must contain no ".." traversal components
    Raises ValueError if no safe paths remain after filtering.
    """
    safe: list[str] = []
    for p in paths:
        norm = os.path.normpath(p)
        if not norm.startswith("/tmp/"):
            logger.warning("build_tmp_cleanup_command: rejected unsafe path: %r", p)
            continue
        if ".." in norm.split(os.sep):
            logger.warning("build_tmp_cleanup_command: rejected path with '..': %r", p)
            continue
        safe.append(norm)

    if not safe:
        raise ValueError(
            "No safe paths to delete after validation. "
            "Only paths under /tmp/ without '..' are allowed."
        )

    logger.info("build_tmp_cleanup_command: %d safe path(s) accepted", len(safe))
    return ["rm", "-rf", *safe]


# ─── disk summary ─────────────────────────────────────────────────────────────

def get_disk_free_summary() -> str:
    """Return a human-readable disk usage table."""
    from core.sysctl import df_human
    return df_human(["--total"])


def build_orphan_count() -> int:
    """Return the number of orphan packages (convenience wrapper)."""
    return len(get_orphan_packages())
