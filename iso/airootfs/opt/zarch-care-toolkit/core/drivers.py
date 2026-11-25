"""
core/drivers.py
===============
Determine appropriate drivers based on detected hardware, and install via pacman.

All system queries use ``core.sysctl`` — no bare subprocess calls here.

Note: the package catalog below is based on official Arch Linux package names
(extra repo) as of early 2026.  Review periodically since package names can
change.
"""

from core.privilege import run_unprivileged
from core.sysctl import pacman_query_installed
from core.hardware import detect_gpu_vendors, get_network_devices
from core.logger import get_logger

logger = get_logger(__name__)


# ─── GPU driver catalog ───────────────────────────────────────────────────────

_GPU_CATALOG: dict[str, list[str]] = {
    "nvidia": [
        "nvidia",
        "nvidia-utils",
        "nvidia-settings",
        "lib32-nvidia-utils",   # for 32-bit apps / Steam
    ],
    "amd": [
        "mesa",
        "lib32-mesa",
        "vulkan-radeon",
        "lib32-vulkan-radeon",
        "xf86-video-amdgpu",
        "libva-mesa-driver",
        "mesa-vdpau",
    ],
    "intel": [
        "mesa",
        "lib32-mesa",
        "vulkan-intel",
        "lib32-vulkan-intel",
        "intel-media-driver",
    ],
    "unknown": [],
}


def suggest_gpu_packages() -> tuple[str, list[str]]:
    """
    Return (vendor_summary_string, deduplicated_package_list).
    Collects packages for ALL detected GPU vendors so laptops with
    Intel iGPU + discrete NVIDIA/AMD receive suggestions for both.
    """
    vendors = detect_gpu_vendors()
    vendor_str = " + ".join(vendors)

    seen: set[str] = set()
    pkgs: list[str] = []
    for vendor in vendors:
        for pkg in _GPU_CATALOG.get(vendor, []):
            if pkg not in seen:
                seen.add(pkg)
                pkgs.append(pkg)

    logger.debug("suggest_gpu_packages: vendors=%s pkgs=%d", vendors, len(pkgs))
    return vendor_str, pkgs


# ─── Network driver catalog ───────────────────────────────────────────────────

def suggest_network_packages() -> list[str]:
    """Suggest common packages for wireless interfaces (Broadcom/Realtek often need DKMS)."""
    devices = " ".join(get_network_devices()).lower()
    pkgs: list[str] = []
    if "broadcom" in devices:
        pkgs.append("broadcom-wl-dkms")
    if "realtek" in devices and (
        "wireless" in devices or "wifi" in devices or "802.11" in devices
    ):
        pkgs.append("rtl8821ce-dkms")  # common example — may vary by chipset
    return pkgs


# ─── Installed-package queries ────────────────────────────────────────────────

def filter_uninstalled(packages: list[str]) -> list[str]:
    """
    Return the subset of *packages* that are not currently installed.
    Uses a single ``pacman -Qq`` call for all packages.
    """
    if not packages:
        return []
    # Use run_unprivileged directly so tests can patch 'core.drivers.run_unprivileged'
    code, out = run_unprivileged(["pacman", "-Qq"] + packages)
    installed: set[str] = set(out.strip().splitlines()) if out.strip() else set()
    not_installed = [p for p in packages if p not in installed]
    logger.debug(
        "filter_uninstalled: %d/%d packages not installed",
        len(not_installed), len(packages),
    )
    return not_installed


# ─── Install command builder ──────────────────────────────────────────────────

def build_install_command(packages: list[str]) -> list[str]:
    """Build the safe pacman install command (executed later via pkexec)."""
    if not packages:
        raise ValueError("No packages provided to build_install_command.")
    return ["pacman", "-S", "--needed", "--noconfirm", *packages]
