"""
core/privilege.py
=================
Safely execute commands that need root privileges via pkexec (Polkit)
instead of storing a sudo password or running the whole GUI as root
(an unsafe practice that's discouraged on KDE/Wayland).
"""

import shutil
import subprocess

from PySide6.QtCore import QProcess
from core.logger import get_logger

logger = get_logger(__name__)


class PrivilegeError(Exception):
    pass


def has_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def ensure_pkexec() -> None:
    """
    Make sure pkexec is present — the recommended safe way to elevate
    privileges inside a graphical session (instead of interactive sudo in a GUI).
    """
    if not has_command("pkexec"):
        raise PrivilegeError(
            "pkexec is not available on this system. "
            "Install the polkit package:\n  sudo pacman -S polkit"
        )


def run_privileged_stream(command: list[str], parent=None) -> QProcess:
    """
    Run a command that needs root via pkexec, with the output streamed live
    instead of waiting for completion — suitable for showing pacman -Syu
    progress live in the UI.

    Returns a QProcess object so the caller can connect readyReadStandardOutput /
    finished signals to it.
    """
    ensure_pkexec()
    logger.info("run_privileged_stream: pkexec %s", " ".join(command))
    process = QProcess(parent)
    process.setProgram("pkexec")
    process.setArguments(command)
    process.setProcessChannelMode(QProcess.MergedChannels)
    return process


def run_privileged(command: list[str], timeout: int = 30) -> tuple[int, str]:
    """Run a command via pkexec and return (exit_code, output)."""
    try:
        ensure_pkexec()
        logger.info("run_privileged: pkexec %s", " ".join(command))
        result = subprocess.run(
            ["pkexec"] + command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return result.returncode, output
    except FileNotFoundError:
        logger.debug("run_privileged: pkexec not found")
        return 127, "pkexec not found. Install polkit."
    except subprocess.TimeoutExpired:
        logger.warning("run_privileged: timeout after %ds: %s", timeout, " ".join(command))
        return 124, "Command timed out."
    except Exception as exc:
        logger.exception("run_privileged: unexpected error running %s: %s", command[0], exc)
        return 1, f"Unexpected error: {exc}"


def run_unprivileged(command: list[str], timeout: int = 30) -> tuple[int, str]:
    """Run a regular (non-privileged) command and return (exit_code, output)."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return result.returncode, output
    except FileNotFoundError:
        logger.debug("run_unprivileged: command not found: %s", command[0])
        return 127, f"Command not found: {command[0]}"
    except subprocess.TimeoutExpired:
        logger.warning("run_unprivileged: timeout after %ds: %s", timeout, " ".join(command))
        return 124, "Command timed out."
    except Exception as exc:
        logger.exception("run_unprivileged: unexpected error running %s: %s", command[0], exc)
        return 1, f"Unexpected error: {exc}"
