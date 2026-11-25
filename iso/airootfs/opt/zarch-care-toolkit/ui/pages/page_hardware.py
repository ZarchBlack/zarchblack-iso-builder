"""
ui/pages/page_hardware.py
=========================
Hardware detection & driver suggestion/installation.

Fixes applied:
  BUG-C01  — Uses WorkerMixin._spawn_worker() for automatic worker cleanup.
  BUG-H06  — suggest_drivers() now shows all detected vendors (Intel + NVIDIA,
              etc.) thanks to the updated drivers.suggest_gpu_packages().
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QMessageBox,
)
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import QProcess

from core import hardware, drivers
from core.privilege import run_privileged_stream, PrivilegeError
from core.operation_log import op_log
from ui.worker_mixin import WorkerMixin
from core.logger import get_logger

logger = get_logger(__name__)


class HardwareDriversPage(QWidget, WorkerMixin):
    def __init__(self):
        super().__init__()
        self._workers: list = []
        self._proc: QProcess | None = None
        self._pending_packages: list[str] = []

        layout = QVBoxLayout(self)

        title = QLabel("Hardware Detection & Drivers")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        btn_row = QHBoxLayout()

        self.btn_scan = QPushButton("Scan Hardware Components")
        self.btn_scan.clicked.connect(self.scan_hardware)
        btn_row.addWidget(self.btn_scan)

        self.btn_suggest = QPushButton("Suggest Appropriate Drivers")
        self.btn_suggest.clicked.connect(self.suggest_drivers)
        btn_row.addWidget(self.btn_suggest)

        self.btn_install = QPushButton("Install Suggested Drivers")
        self.btn_install.setObjectName("dangerButton")
        self.btn_install.clicked.connect(self.install_drivers)
        self.btn_install.setEnabled(False)
        btn_row.addWidget(self.btn_install)
        layout.addLayout(btn_row)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _set_scan_buttons_enabled(self, enabled: bool) -> None:
        self.btn_scan.setEnabled(enabled)
        self.btn_suggest.setEnabled(enabled)

    # ── scan ──────────────────────────────────────────────────────────────────

    def scan_hardware(self) -> None:
        self._set_scan_buttons_enabled(False)
        self.output.setPlainText("Scanning hardware…")

        worker = self._spawn_worker(hardware.build_full_report)   # BUG-C01 fix

        def done(report) -> None:
            text = (
                f"=== CPU ===\n{report.cpu}\n\n"
                "=== GPU ===\n" + "\n\n".join(report.gpu) + "\n\n"
                f"=== RAM ===\n{report.ram}\n\n"
                f"=== Storage ===\n{report.storage}\n\n"
                f"=== Motherboard ===\n{report.motherboard}\n\n"
                "=== Network Devices ===\n" + "\n".join(report.network)
            )
            self.output.setPlainText(text)
            self._set_scan_buttons_enabled(True)

        def failed(err: str) -> None:
            self.output.setPlainText(f"Error while scanning: {err}")
            self._set_scan_buttons_enabled(True)
            logger.warning("HardwareDriversPage scan failed: %s", err)

        worker.finished_ok.connect(done)
        worker.failed.connect(failed)
        worker.start()

    # ── driver suggestion ─────────────────────────────────────────────────────

    def suggest_drivers(self) -> None:
        """Run driver suggestion in background — does NOT block UI."""
        self._set_scan_buttons_enabled(False)
        self.output.setPlainText("Scanning GPU and network hardware…")

        def _collect():
            vendor_str, gpu_pkgs = drivers.suggest_gpu_packages()
            net_pkgs = drivers.suggest_network_packages()
            all_pkgs = gpu_pkgs + [p for p in net_pkgs if p not in gpu_pkgs]
            not_installed = drivers.filter_uninstalled(all_pkgs)
            return vendor_str, gpu_pkgs, net_pkgs, all_pkgs, not_installed

        worker = self._spawn_worker(_collect)

        def _done(result) -> None:
            vendor_str, gpu_pkgs, net_pkgs, all_pkgs, not_installed = result
            self._pending_packages = not_installed

            if not all_pkgs:
                self.output.setPlainText(
                    f"Detected GPU vendor(s): {vendor_str}\n"
                    "No additional packages suggested — hardware is already supported "
                    "by the default kernel/mesa drivers."
                )
                self.btn_install.setEnabled(False)
            else:
                lines = [f"Detected GPU vendor(s): {vendor_str}", ""]
                if gpu_pkgs:
                    lines.append("GPU packages:")
                    for p in gpu_pkgs:
                        status = "✅ already installed" if p not in not_installed else "⬜ not installed"
                        lines.append(f"  - {p}  [{status}]")
                if net_pkgs:
                    lines.append("\nNetwork packages:")
                    for p in net_pkgs:
                        status = "✅ already installed" if p not in not_installed else "⬜ not installed"
                        lines.append(f"  - {p}  [{status}]")
                self.output.setPlainText("\n".join(lines))
                self.btn_install.setEnabled(bool(not_installed))

            op_log.record(
                "Driver suggestion scan",
                success=True,
                detail=f"{vendor_str}, {len(not_installed)} package(s) needed",
            )
            self._set_scan_buttons_enabled(True)

        def _failed(err: str) -> None:
            self.output.setPlainText(f"Error scanning drivers: {err}")
            op_log.record("Driver suggestion scan", success=False, detail=err)
            self._set_scan_buttons_enabled(True)

        worker.finished_ok.connect(_done)
        worker.failed.connect(_failed)
        worker.start()

    # ── driver installation ───────────────────────────────────────────────────

    def install_drivers(self) -> None:
        if not self._pending_packages:
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Installation",
            "The following packages will be installed via pacman with root "
            "privileges:\n\n"
            + "\n".join(f"  • {p}" for p in self._pending_packages)
            + "\n\nDo you want to continue?",
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            cmd = drivers.build_install_command(self._pending_packages)
            self._proc = run_privileged_stream(cmd, self)
        except (PrivilegeError, ValueError) as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.output.clear()
        self.btn_install.setEnabled(False)
        self._proc.readyReadStandardOutput.connect(self._on_output)
        self._proc.finished.connect(self._on_finished)
        self._proc.start()
        logger.info("HardwareDriversPage: installing %d package(s)", len(self._pending_packages))

    def _on_output(self) -> None:
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode(errors="replace")
        self.output.moveCursor(QTextCursor.End)
        self.output.insertPlainText(data)

    def _on_finished(self, code: int, status) -> None:
        self.output.insertPlainText(
            f"\n\n--- Process finished with exit code: {code} ---\n"
        )
        if code != 0:
            self.output.insertPlainText(
                "⚠️  Installation returned a non-zero exit code. "
                "Check the output above for details.\n"
            )
            logger.warning("HardwareDriversPage: install finished with code %d", code)
        else:
            logger.info("HardwareDriversPage: install completed successfully")
        self.btn_install.setEnabled(True)
        self._pending_packages = []
