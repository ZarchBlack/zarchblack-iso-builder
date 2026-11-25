"""
core/hardware.py
================
Hardware component detection: CPU, GPU, RAM, Storage, Motherboard, Network.

All system queries use ``core.sysctl`` — no bare subprocess calls here.
"""

from dataclasses import dataclass, field
from core.privilege import run_unprivileged
from core.sysctl import (
    lspci_verbose,
    lscpu,
    free_human,
    lsblk_info,
    dmidecode_baseboard,
)
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HardwareReport:
    cpu:         str        = ""
    gpu:         list[str]  = field(default_factory=list)
    ram:         str        = ""
    storage:     str        = ""
    motherboard: str        = ""
    network:     list[str]  = field(default_factory=list)


# ─── CPU ──────────────────────────────────────────────────────────────────────

_LSCPU_FIELDS = (
    "Model name", "Architecture", "CPU(s)", "Thread(s) per core",
    "Core(s) per socket", "CPU max MHz", "Vendor ID",
)


def get_cpu_info() -> str:
    out = lscpu()
    if not out:
        return "Could not read CPU information."
    lines = [ln.strip() for ln in out.splitlines() if ln.strip().startswith(_LSCPU_FIELDS)]
    return "\n".join(lines) if lines else out[:800]


# ─── GPU ──────────────────────────────────────────────────────────────────────

def get_gpu_info() -> list[str]:
    # Use run_unprivileged directly so tests can patch 'core.hardware.run_unprivileged'
    code, out = run_unprivileged(["lspci", "-nnk"])
    if code != 0:
        logger.warning("get_gpu_info: lspci failed (exit %d)", code)
        return ["Could not run lspci — make sure the pciutils package is installed."]

    gpus: list[str] = []
    lines = out.splitlines()
    current: list[str] = []

    def _is_gpu_block(block: list[str]) -> bool:
        return any(
            "VGA" in ln or "3D controller" in ln or "Display controller" in ln
            for ln in block
        )

    for line in lines:
        if line and not line.startswith(("\t", " ")):
            if current and _is_gpu_block(current):
                gpus.append("\n".join(current))
            current = [line]
        else:
            current.append(line)

    if current and _is_gpu_block(current):
        gpus.append("\n".join(current))

    logger.debug("get_gpu_info: %d GPU block(s) found", len(gpus))
    return gpus if gpus else ["No GPU detected via lspci."]


def detect_gpu_vendors() -> list[str]:
    """
    Return a list of ALL detected GPU vendors.
    Possible values: "nvidia", "amd", "intel", "unknown".
    """
    gpus = get_gpu_info()
    vendors: list[str] = []

    for block in gpus:
        text = block.lower()
        if "nvidia" in text and "nvidia" not in vendors:
            vendors.append("nvidia")
        if ("amd" in text or "advanced micro devices" in text or "radeon" in text) \
                and "amd" not in vendors:
            vendors.append("amd")
        if "intel" in text and "intel" not in vendors:
            vendors.append("intel")

    if not vendors:
        vendors.append("unknown")

    logger.debug("detect_gpu_vendors: %s", vendors)
    return vendors


def detect_gpu_vendor() -> str:
    """Return the primary GPU vendor string (first in detect_gpu_vendors())."""
    return detect_gpu_vendors()[0]


# ─── RAM ──────────────────────────────────────────────────────────────────────

def get_ram_info() -> str:
    out = free_human()
    return out if out else "Could not read memory information."


# ─── Storage ──────────────────────────────────────────────────────────────────

def get_storage_info() -> str:
    out = lsblk_info()
    return out if out else "Could not read storage information."


# ─── Motherboard ──────────────────────────────────────────────────────────────

def get_motherboard_info() -> str:
    return dmidecode_baseboard()


# ─── Network devices ──────────────────────────────────────────────────────────

def get_network_devices() -> list[str]:
    out = lspci_verbose()
    if not out:
        return ["Could not run lspci."]
    devices = [
        line.strip()
        for line in out.splitlines()
        if "Network controller" in line or "Ethernet controller" in line
    ]
    return devices if devices else ["No additional network devices detected via PCI."]


# ─── Full report ──────────────────────────────────────────────────────────────

def build_full_report() -> HardwareReport:
    return HardwareReport(
        cpu=get_cpu_info(),
        gpu=get_gpu_info(),
        ram=get_ram_info(),
        storage=get_storage_info(),
        motherboard=get_motherboard_info(),
        network=get_network_devices(),
    )
