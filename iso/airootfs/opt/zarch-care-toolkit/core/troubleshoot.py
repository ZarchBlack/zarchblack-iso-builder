"""
core/troubleshoot.py
====================
Automatic diagnosis of common issues + log viewing + network tools.
All commands here are read-only and don't require root.

All system queries use ``core.sysctl`` — no bare subprocess calls here.

v1.2 changes:
  - Uses sysctl helpers throughout.
  - Removed unused quick_hardware_health() (dead code).
  - Boot log entries capped at 15 unique lines.
  - Known-harmless messages downgraded to "info" (zero health score penalty).
  - Tailored suggestions for common failed services.
"""

import os
import re
from dataclasses import dataclass

from core.privilege import run_unprivileged
from core.sysctl import (
    systemctl_failed_units,
    journalctl_boot_errors,
    journalctl_recent,
    df_human_output_fields,
    find_files,
    ip_brief_addr,
    command_available,
)
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DiagnosticIssue:
    severity:   str   # "error" | "warning" | "info"
    title:      str
    detail:     str
    suggestion: str = ""


# ─── known-harmless boot message patterns ─────────────────────────────────────
# These appear on virtually every modern PC and indicate missing optional
# hardware features — NOT actionable system problems.

_HARMLESS_BOOT_PATTERNS: list[re.Pattern] = [
    re.compile(r"ACPI.*(AE_NOT_FOUND|AE_ALREADY_EXISTS|dspkginit)", re.I),
    re.compile(r"x86/cpu.*SGX", re.I),
    re.compile(r"virt/tdx.*not supported", re.I),
    re.compile(r"iTCO_wdt.*failed", re.I),
    re.compile(r"pstore.*failed", re.I),
    re.compile(r"RAS:.*correctable", re.I),
    re.compile(r"ERST.*failed", re.I),
    re.compile(r"tpm.*failed", re.I),
    re.compile(r"Bluetooth.*failed", re.I),
    re.compile(r"mei_hdcp.*failed", re.I),
    re.compile(r"DMAR.*ACPI", re.I),
    re.compile(r"_OSC.*failed", re.I),
]

# Tailored suggestions for specific well-known service failures.
_SERVICE_SUGGESTIONS: dict[str, str] = {
    "grub-btrfsd": (
        "grub-btrfsd regenerates grub-btrfs.cfg for Btrfs snapshots. "
        "If you don't use Btrfs snapshots, disable it:\n"
        "  sudo systemctl disable --now grub-btrfsd\n"
        "If you do use snapshots: journalctl -u grub-btrfsd -xe"
    ),
    "shadow": (
        "shadow.service checks /etc/shadow and /etc/passwd integrity. "
        "Common fix: sudo pwck -r && sudo grpck -r\n"
        "Or view the full error: journalctl -u shadow.service -xe"
    ),
    "systemd-modules": (
        "A kernel module failed to load at boot. Usually harmless if the "
        "related hardware isn't present. Check: journalctl -u systemd-modules-load -xe"
    ),
    "ufw": (
        "UFW firewall failed to start. Check: sudo ufw status verbose"
    ),
    "NetworkManager": (
        "NetworkManager failed. Try: sudo systemctl restart NetworkManager"
    ),
}


def _service_suggestion(unit: str) -> str:
    unit_lower = unit.lower()
    for key, suggestion in _SERVICE_SUGGESTIONS.items():
        if key in unit_lower:
            return suggestion
    return f"Check the full log: journalctl -u {unit} -xe"


def _is_harmless_boot_message(line: str) -> bool:
    return any(p.search(line) for p in _HARMLESS_BOOT_PATTERNS)


# ─── individual checks ────────────────────────────────────────────────────────

def get_failed_services() -> list[DiagnosticIssue]:
    """Find failed systemd services."""
    issues: list[DiagnosticIssue] = []
    # Use run_unprivileged directly so tests can patch 'core.troubleshoot.run_unprivileged'
    code, out = run_unprivileged(
        ["systemctl", "--failed", "--no-legend", "--plain"]
    )
    raw = out.strip() if code == 0 else ""
    if raw:
        for line in raw.splitlines():
            unit = line.split()[0] if line.split() else line.strip()
            issues.append(DiagnosticIssue(
                severity="error",
                title=f"Failed service: {unit}",
                detail=line.strip(),
                suggestion=_service_suggestion(unit),
            ))
    logger.debug("get_failed_services: %d issue(s)", len(issues))
    return issues


def get_boot_errors(max_lines: int = 100) -> list[DiagnosticIssue]:
    """
    Read recent boot errors from journalctl (priority err and above).

    Known-harmless messages (ACPI, SGX, TDX …) are downgraded to "info"
    (zero health score penalty).  Remaining entries get "warning" severity.
    Capped at 15 unique entries.
    """
    issues: list[DiagnosticIssue] = []
    out = journalctl_boot_errors(max_lines)
    if not out:
        return issues

    lines = [
        ln for ln in out.splitlines()
        if ln.strip() and "-- No entries --" not in ln
    ]

    # Deduplicate by first 80 chars
    seen: set[str] = set()
    unique: list[str] = []
    for line in lines:
        key = line.strip()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(line.strip())

    cap = 15
    for line in unique[:cap]:
        sev = "info" if _is_harmless_boot_message(line) else "warning"
        issues.append(DiagnosticIssue(
            severity=sev,
            title="Boot log entry",
            detail=line,
            suggestion=(
                "Known-harmless kernel message for your hardware (no action needed)."
                if sev == "info" else
                "Run: journalctl -p 3 -b --no-pager  for the full list."
            ),
        ))

    if len(unique) > cap:
        issues.append(DiagnosticIssue(
            severity="info",
            title=f"… and {len(unique) - cap} more boot log entries (not shown)",
            detail="Showing only the first 15 unique entries.",
            suggestion="Run: journalctl -p 3 -b --no-pager | less",
        ))

    logger.debug(
        "get_boot_errors: %d unique issue(s) from %d raw lines",
        len(unique), len(lines),
    )
    return issues


def check_disk_space(threshold_percent: int = 90) -> list[DiagnosticIssue]:
    """Check for disks over a given usage threshold."""
    issues: list[DiagnosticIssue] = []
    # Use run_unprivileged directly so tests can patch 'core.troubleshoot.run_unprivileged'
    code, out = run_unprivileged(
        ["df", "-h", "--output=target,pcent,source"]
    )
    if code != 0 or not out:
        return issues
    for line in out.strip().splitlines()[1:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        target, pcent, source = parts[0], parts[1], parts[2]
        if not source.startswith("/dev/"):
            continue
        try:
            pct = int(pcent.strip("%"))
        except ValueError:
            continue
        if pct >= threshold_percent:
            issues.append(DiagnosticIssue(
                severity="warning",
                title=f"Disk almost full: {target}",
                detail=f"{source} is {pct}% used",
                suggestion="Clean unneeded files from the 'Clean System' tab.",
            ))
    logger.debug("check_disk_space: %d issue(s)", len(issues))
    return issues


def check_failed_pacman_locks() -> list[DiagnosticIssue]:
    """Detect a leftover pacman lock file."""
    lock_path = "/var/lib/pacman/db.lck"
    if os.path.exists(lock_path):
        logger.warning("pacman lock file detected at %s", lock_path)
        return [DiagnosticIssue(
            severity="warning",
            title="pacman lock file present",
            detail=lock_path,
            suggestion=(
                "Make sure no other pacman process is running, "
                "then remove: sudo rm /var/lib/pacman/db.lck"
            ),
        )]
    return []


def check_orphaned_config_conflicts() -> list[DiagnosticIssue]:
    """Look for .pacnew files which may cause silent config conflicts."""
    paths = find_files("/etc", name_pattern="*.pacnew")
    if paths:
        return [DiagnosticIssue(
            severity="info",
            title=f"{len(paths)} .pacnew file(s) awaiting review",
            detail="New config files that haven't been merged with your current configs.",
            suggestion="Review manually or use: sudo pacdiff",
        )]
    return []


def run_full_diagnosis() -> list[DiagnosticIssue]:
    """Run all automatic checks at once."""
    logger.debug("run_full_diagnosis: starting")
    issues: list[DiagnosticIssue] = (
        get_failed_services()
        + get_boot_errors()
        + check_disk_space()
        + check_failed_pacman_locks()
        + check_orphaned_config_conflicts()
    )
    logger.info("run_full_diagnosis: %d issue(s) found", len(issues))
    return issues


# ─── network tools ────────────────────────────────────────────────────────────

def ping_host(host: str = "1.1.1.1", count: int = 4) -> str:
    code, out = run_unprivileged(
        ["ping", "-c", str(count), "-W", "2", host],
        timeout=count * 3 + 5,
    )
    return out


def get_network_interfaces() -> str:
    return ip_brief_addr()


def check_dns() -> str:
    if command_available("resolvectl"):
        code, out = run_unprivileged(["resolvectl", "status"])
        return out
    code, out = run_unprivileged(["cat", "/etc/resolv.conf"])
    return out


def get_recent_logs(lines: int = 200, priority: str | None = None) -> str:
    return journalctl_recent(lines, priority)
