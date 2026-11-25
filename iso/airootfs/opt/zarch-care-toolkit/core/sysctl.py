"""
core/sysctl.py
==============
Centralized system command abstraction layer for ZarchCare.

ALL modules must use the typed helpers defined here instead of calling
``run_unprivileged`` directly with raw command lists.  This provides:

  • A single place to adjust command flags, timeouts, and fallbacks.
  • Named functions that are easy to mock in unit tests.
  • Consistent error handling and logging across the whole application.
  • Zero subprocess calls scattered across feature modules.

Privileged commands (pacman -Syu, paccache, rm …) are NOT included here
because they must go through pkexec via ``run_privileged_stream()``.
Only *read-only / unprivileged* system queries belong in this module.
"""

from __future__ import annotations

import shutil
from core.privilege import run_unprivileged, has_command
from core.logger import get_logger

logger = get_logger(__name__)

# ─── pacman ───────────────────────────────────────────────────────────────────

def pacman_list_installed() -> list[str]:
    """Return a list of all installed package names."""
    code, out = run_unprivileged(["pacman", "-Qq"])
    if code != 0:
        logger.warning("pacman_list_installed: exit %d", code)
        return []
    return [ln.strip() for ln in out.strip().splitlines() if ln.strip()]


def pacman_query_installed(*packages: str) -> set[str]:
    """
    Return the subset of *packages* that are currently installed.
    Uses a single ``pacman -Qq`` call regardless of how many packages are passed.
    """
    if not packages:
        return set()
    code, out = run_unprivileged(["pacman", "-Qq", *packages])
    return set(out.strip().splitlines()) if out.strip() else set()


def pacman_check_updates(timeout: int = 25) -> str:
    """
    Return raw output from ``checkupdates`` (from pacman-contrib).
    Returns an empty string when the system is up to date.
    Returns ``None`` if checkupdates is not available.
    """
    if not has_command("checkupdates"):
        return None  # type: ignore[return-value]
    code, out = run_unprivileged(["checkupdates"], timeout=timeout)
    if code == 0:
        return out.strip()
    # exit 1 with empty stdout = no updates (checkupdates convention)
    if code == 1 and not out.strip():
        return ""
    return None  # type: ignore[return-value]  # db not synced or error


def pacman_query_orphans() -> list[str]:
    """Return a list of orphan package names (installed as deps, no longer needed)."""
    code, out = run_unprivileged(["pacman", "-Qtdq"])
    if code != 0 or not out.strip():
        return []
    return [ln.strip() for ln in out.strip().splitlines() if ln.strip()]


def pacman_cache_size() -> str:
    """Return the human-readable size of /var/cache/pacman/pkg (e.g. '5.8G')."""
    code, out = run_unprivileged(["du", "-sh", "/var/cache/pacman/pkg"])
    if code != 0 or not out.strip():
        return "Unknown"
    parts = out.strip().split()
    return parts[0] if parts else "Unknown"


# ─── systemctl ────────────────────────────────────────────────────────────────

def systemctl_is_active(service: str) -> bool:
    """Return True if *service* is currently active."""
    if not has_command("systemctl"):
        return False
    code, out = run_unprivileged(["systemctl", "is-active", service])
    return code == 0 and out.strip() == "active"


def systemctl_first_active(*services: str) -> str | None:
    """
    Return the name of the first service in *services* that is active,
    or ``None`` if none are active.

    More efficient than calling ``systemctl_is_active`` in a loop because
    it exits on the first match.
    """
    for svc in services:
        if systemctl_is_active(svc):
            return svc
    return None


def systemctl_failed_units() -> str:
    """Return raw output of ``systemctl --failed``."""
    code, out = run_unprivileged(
        ["systemctl", "--failed", "--no-legend", "--plain"]
    )
    return out.strip() if code == 0 else ""


# ─── journalctl ───────────────────────────────────────────────────────────────

def journalctl_boot_errors(max_lines: int = 100) -> str:
    """Return up to *max_lines* boot-time journal entries at priority err (3)."""
    code, out = run_unprivileged(
        ["journalctl", "-p", "3", "-b", "--no-pager", "-n", str(max_lines)],
        timeout=15,
    )
    return out.strip() if code == 0 else ""


def journalctl_disk_usage() -> str:
    """Return journal disk usage string."""
    code, out = run_unprivileged(["journalctl", "--disk-usage"])
    return out.strip() if code == 0 else "Unknown"


def journalctl_recent(lines: int = 200, priority: str | None = None) -> str:
    """Return recent journal entries, optionally filtered by priority."""
    cmd = ["journalctl", "--no-pager", "-n", str(lines)]
    if priority:
        cmd += ["-p", priority]
    code, out = run_unprivileged(cmd, timeout=15)
    return out if code == 0 else f"Could not read logs (exit {code})."


# ─── filesystem ───────────────────────────────────────────────────────────────

def df_root() -> str:
    """Return raw ``df -B1 /`` output."""
    code, out = run_unprivileged(["df", "-B1", "/"])
    return out if code == 0 else ""


def df_human(extra_flags: list[str] | None = None) -> str:
    """Return ``df -h`` output with optional extra flags."""
    cmd = ["df", "-h"] + (extra_flags or [])
    code, out = run_unprivileged(cmd)
    return out if code == 0 else "Could not read disk space."


def df_human_output_fields(fields: str = "target,pcent,source") -> str:
    """Return ``df -h --output=<fields>`` output."""
    code, out = run_unprivileged(["df", "-h", f"--output={fields}"])
    return out if code == 0 else ""


def du_path(path: str) -> str:
    """Return the human-readable size of *path* (first token of du -sh output)."""
    code, out = run_unprivileged(["du", "-sh", path])
    if code != 0 or not out.strip():
        return "Unknown"
    parts = out.strip().split()
    return parts[0] if parts else "Unknown"


def find_files(
    directory: str,
    name_pattern: str | None = None,
    atime_days: int | None = None,
    mtime_days: int | None = None,
    maxdepth: int | None = None,
) -> list[str]:
    """
    Wrapper around ``find`` with common options.  Returns a list of paths.
    Ignores errors silently (returns empty list on failure).
    """
    cmd = ["find", directory, "-mindepth", "1"]
    if maxdepth is not None:
        cmd += ["-maxdepth", str(maxdepth)]
    if name_pattern:
        cmd += ["-name", name_pattern]
    if atime_days is not None:
        cmd += ["-atime", f"+{atime_days}"]
    if mtime_days is not None:
        cmd += ["-mtime", f"+{mtime_days}"]
    code, out = run_unprivileged(cmd, timeout=30)
    if code != 0 or not out.strip():
        return []
    return [ln.strip() for ln in out.strip().splitlines() if ln.strip()]


# ─── kernel / system info ─────────────────────────────────────────────────────

def uname_release() -> str:
    """Return the kernel release string (``uname -r``)."""
    code, out = run_unprivileged(["uname", "-r"])
    return out.strip() if code == 0 else "?"


def uptime_seconds() -> float | None:
    """Return system uptime in seconds from /proc/uptime, or None on error."""
    try:
        with open("/proc/uptime", encoding="utf-8") as fh:
            return float(fh.readline().split()[0])
    except Exception as exc:
        logger.warning("uptime_seconds: %s", exc)
        return None


# ─── hardware info ────────────────────────────────────────────────────────────

def lspci_verbose() -> str:
    """Return verbose ``lspci -nnk`` output."""
    code, out = run_unprivileged(["lspci", "-nnk"])
    if code != 0:
        logger.warning("lspci_verbose: exit %d", code)
        return ""
    return out


def lscpu() -> str:
    """Return full ``lscpu`` output."""
    code, out = run_unprivileged(["lscpu"])
    if code != 0:
        logger.warning("lscpu: exit %d", code)
        return ""
    return out


def free_human() -> str:
    """Return ``free -h`` output."""
    code, out = run_unprivileged(["free", "-h"])
    if code != 0:
        logger.warning("free_human: exit %d", code)
        return ""
    return out


def lsblk_info(columns: str = "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL") -> str:
    """Return ``lsblk`` output with the given columns."""
    code, out = run_unprivileged(["lsblk", "-o", columns])
    if code != 0:
        logger.warning("lsblk_info: exit %d", code)
        return ""
    return out


def dmidecode_baseboard() -> str:
    """Return DMI baseboard info (usually requires root; graceful fallback)."""
    if not has_command("dmidecode"):
        return "dmidecode not installed (install: pacman -S dmidecode)."
    code, out = run_unprivileged(["dmidecode", "-t", "baseboard"])
    if code == 0 and out.strip():
        return out
    return "Reading motherboard data requires root privileges."


def ip_brief_addr() -> str:
    """Return ``ip -brief addr show`` output."""
    code, out = run_unprivileged(["ip", "-brief", "addr", "show"])
    return out if code == 0 else "Could not read network interfaces."


# ─── availability helpers ─────────────────────────────────────────────────────

def command_available(name: str) -> bool:
    """Return True if *name* is available on PATH."""
    return shutil.which(name) is not None


def first_available(*commands: str) -> str | None:
    """Return the first command in *commands* found on PATH, or None."""
    for cmd in commands:
        if shutil.which(cmd):
            return cmd
    return None
