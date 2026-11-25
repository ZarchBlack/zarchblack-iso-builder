#!/usr/bin/env python3
"""
ZarchCare — Arch Linux System Care Tool
======================================
Diagnostics, hardware/driver detection, system cleanup and updates —
all in one application.

Requirements: PySide6, polkit (pkexec), pacman, systemd, pciutils
Run: python3 main.py
"""

import sys
import shutil

from PySide6.QtWidgets import QApplication, QMessageBox

from ui.main_window import ZarchCareWindow
from ui.icons import app_icon

APP_VERSION = "2.0"

# Core tools that must exist for full functionality
REQUIRED_TOOLS = [
    "pacman",
    "systemctl",
    "journalctl",
    "lspci",
    "ip",
    "pkexec",
]

# Tools that are optional but enhance functionality
OPTIONAL_TOOLS = [
    ("checkupdates", "pacman-contrib",  "faster update checking without syncing DB"),
    ("paccache",     "pacman-contrib",  "safe package cache trimming (keeps last N versions)"),
    ("sensors",      "lm_sensors",      "CPU/GPU temperature monitoring"),
    ("smartctl",     "smartmontools",   "disk health SMART data"),
    ("dmidecode",    "dmidecode",       "motherboard information (also needs root)"),
]


def check_environment() -> tuple[list[str], list[tuple[str, str, str]]]:
    """
    Returns (missing_required, missing_optional) lists.
    missing_optional items are (tool, package, reason) tuples.
    """
    missing_req = [t for t in REQUIRED_TOOLS if shutil.which(t) is None]
    missing_opt = [
        (tool, pkg, reason)
        for tool, pkg, reason in OPTIONAL_TOOLS
        if shutil.which(tool) is None
    ]
    return missing_req, missing_opt


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("ZarchCare")
    app.setOrganizationName("ZarchCare")
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(app_icon())

    missing_req, missing_opt = check_environment()

    if missing_req:
        lines = "\n".join(f"  • {t}" for t in missing_req)
        QMessageBox.warning(
            None,
            "Missing Required Tools",
            "The following required tools are missing — some features will not work:\n\n"
            + lines
            + "\n\nThis application is designed specifically for Arch Linux.\n"
            "Install missing packages with pacman before using all features.",
        )

    if missing_opt:
        lines = "\n".join(
            f"  • {tool}  (pkg: {pkg}) — needed for: {reason}"
            for tool, pkg, reason in missing_opt
        )
        from core.logger import get_logger
        logger = get_logger("main")
        logger.info("Optional tools not installed:\n%s", lines)

    window = ZarchCareWindow()

    # Restore saved window geometry if available
    from core.settings import settings
    geo = settings.window_geometry
    if geo:
        window.restoreGeometry(geo)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
