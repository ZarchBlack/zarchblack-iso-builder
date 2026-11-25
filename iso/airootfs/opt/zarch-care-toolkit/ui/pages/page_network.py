"""
ui/pages/page_network.py
========================
Network tools: ping, interfaces, DNS status, recent journal logs.

Fixes applied:
  BUG-C02 — The ping host input is now sanitised before being passed to the
             shell.  Only valid IP addresses (v4/v6) and RFC-1123 hostnames
             are accepted; anything else is rejected with a clear message.
  BUG-C01 — Uses WorkerMixin._spawn_worker() so completed workers are
             automatically removed from self._workers.
"""

import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QLineEdit,
)

from core import troubleshoot
from ui.worker_mixin import WorkerMixin
from core.logger import get_logger

logger = get_logger(__name__)

# ─── validation ───────────────────────────────────────────────────────────────

# Accepts:
#   • IPv4:  digits and dots only, e.g. 192.168.1.1
#   • IPv6:  hex digits and colons, e.g. 2606:4700:4700::1111
#   • Hostnames: letters, digits, hyphens, dots  (RFC-1123)
_SAFE_HOST_RE = re.compile(
    r'^(?:'
    r'(?:[0-9]{1,3}\.){3}[0-9]{1,3}'          # IPv4
    r'|'
    r'[0-9a-fA-F:]{2,39}'                       # IPv6 (simplified)
    r'|'
    r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*'
    r'[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'   # hostname
    r')$'
)

_MAX_HOST_LEN = 253   # RFC 1035 maximum FQDN length


def _validate_host(host: str) -> bool:
    """Return True if *host* is a safe IP address or hostname."""
    if not host or len(host) > _MAX_HOST_LEN:
        return False
    return bool(_SAFE_HOST_RE.match(host))


# ─── page ─────────────────────────────────────────────────────────────────────

class NetworkToolsPage(QWidget, WorkerMixin):
    def __init__(self):
        super().__init__()
        self._workers: list = []   # required by WorkerMixin

        layout = QVBoxLayout(self)

        title = QLabel("Network Tools & Logs")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        row = QHBoxLayout()

        self.host_input = QLineEdit("1.1.1.1")
        self.host_input.setPlaceholderText("IP address or hostname (e.g. 8.8.8.8)")
        self.host_input.setMaxLength(_MAX_HOST_LEN)
        row.addWidget(self.host_input)

        self.btn_ping  = QPushButton("Ping Test")
        self.btn_ping.clicked.connect(self.run_ping)
        row.addWidget(self.btn_ping)

        self.btn_iface = QPushButton("Network Interfaces")
        self.btn_iface.clicked.connect(self.show_interfaces)
        row.addWidget(self.btn_iface)

        self.btn_dns = QPushButton("DNS Status")
        self.btn_dns.clicked.connect(self.show_dns)
        row.addWidget(self.btn_dns)

        self.btn_logs = QPushButton("Recent System Logs")
        self.btn_logs.clicked.connect(self.show_logs)
        row.addWidget(self.btn_logs)

        layout.addLayout(row)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    # ── internal helper ───────────────────────────────────────────────────────

    def _set_buttons_enabled(self, enabled: bool) -> None:
        """Disable/enable all action buttons to prevent concurrent queries."""
        self.btn_ping.setEnabled(enabled)
        self.btn_iface.setEnabled(enabled)
        self.btn_dns.setEnabled(enabled)
        self.btn_logs.setEnabled(enabled)

    def _run_async(self, func, *args) -> None:
        self._set_buttons_enabled(False)
        self.output.setPlainText("Running…")
        worker = self._spawn_worker(func, *args)

        def _done(result: str) -> None:
            self.output.setPlainText(result)
            self._set_buttons_enabled(True)

        def _failed(err: str) -> None:
            self.output.setPlainText(f"Error: {err}")
            self._set_buttons_enabled(True)

        worker.finished_ok.connect(_done)
        worker.failed.connect(_failed)
        worker.start()

    # ── slots ─────────────────────────────────────────────────────────────────

    def run_ping(self) -> None:
        """BUG-C02 fix: validate host before passing to ping."""
        raw_host = self.host_input.text().strip()
        host = raw_host or "1.1.1.1"

        if not _validate_host(host):
            self.output.setPlainText(
                f"❌ Invalid host: '{host}'\n\n"
                "Please enter a valid IP address (e.g. 8.8.8.8) or hostname (e.g. archlinux.org)."
            )
            logger.warning("run_ping: rejected invalid host input: %r", host)
            return

        logger.info("run_ping: pinging %s", host)
        self._run_async(troubleshoot.ping_host, host)

    def show_interfaces(self) -> None:
        self._run_async(troubleshoot.get_network_interfaces)

    def show_dns(self) -> None:
        self._run_async(troubleshoot.check_dns)

    def show_logs(self) -> None:
        self._run_async(troubleshoot.get_recent_logs, 300, "3")
