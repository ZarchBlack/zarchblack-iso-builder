"""
tests/test_core.py
==================
Unit tests for all core modules.

Run with:
    cd /mnt/build/zarch-care-toolkit
    python3 -m pytest tests/ -v

IMPORTANT: Use the correct patch target — always patch where the name is
*used*, not where it is *defined*.  For example, to mock run_unprivileged
as called from core.maintenance, patch "core.maintenance.run_unprivileged".
"""

import os
import sys
import unittest
from unittest.mock import patch, mock_open, MagicMock, call

# Make sure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ════════════════════════════════════════════════════════════════════════════
# core/logger.py
# ════════════════════════════════════════════════════════════════════════════

class TestLogger(unittest.TestCase):
    def test_get_logger_returns_namespaced_logger(self):
        from core.logger import get_logger
        logger = get_logger("test_module")
        self.assertIn("zarchcare", logger.name)

    def test_get_logger_already_prefixed(self):
        from core.logger import get_logger
        logger = get_logger("zarchcare.something")
        self.assertEqual(logger.name, "zarchcare.something")


# ════════════════════════════════════════════════════════════════════════════
# core/privilege.py
# ════════════════════════════════════════════════════════════════════════════

class TestRunUnprivileged(unittest.TestCase):
    def test_successful_command(self):
        from core.privilege import run_unprivileged
        code, out = run_unprivileged(["echo", "hello"])
        self.assertEqual(code, 0)
        self.assertIn("hello", out)

    def test_missing_command_returns_127(self):
        from core.privilege import run_unprivileged
        code, out = run_unprivileged(["__nonexistent_cmd_xyz__"])
        self.assertEqual(code, 127)
        self.assertIn("not found", out.lower())

    def test_timeout_returns_124(self):
        from core.privilege import run_unprivileged
        code, out = run_unprivileged(["sleep", "60"], timeout=1)
        self.assertEqual(code, 124)
        self.assertIn("timed out", out.lower())

    def test_has_command_true(self):
        from core.privilege import has_command
        self.assertTrue(has_command("echo"))

    def test_has_command_false(self):
        from core.privilege import has_command
        self.assertFalse(has_command("__nonexistent_cmd_xyz__"))


# ════════════════════════════════════════════════════════════════════════════
# core/dashboard.py  — BUG-H01 regression tests
# Patch target: "core.dashboard.run_unprivileged"  (where it is used)
# ════════════════════════════════════════════════════════════════════════════

class TestGetDisk(unittest.TestCase):
    _NORMAL_DF = (
        "Filesystem  1B-blocks      Used  Available Use% Mounted on\n"
        "/dev/sda1   107374182400 53687091200 53687091200  50% /\n"
    )

    def test_normal_df_output(self):
        with patch("core.dashboard.run_unprivileged", return_value=(0, self._NORMAL_DF)):
            from core.dashboard import _get_disk
            used, total, pct = _get_disk()
            self.assertIn("GB", used)
            self.assertIn("GB", total)
            self.assertAlmostEqual(pct, 50.0, places=0)

    def test_df_failure_returns_question_marks(self):
        with patch("core.dashboard.run_unprivileged", return_value=(1, "error")):
            from core.dashboard import _get_disk
            used, total, pct = _get_disk()
            self.assertEqual(used, "?")
            self.assertEqual(total, "?")
            self.assertEqual(pct, 0.0)

    def test_df_single_line_returns_defaults(self):
        with patch("core.dashboard.run_unprivileged", return_value=(0, "Filesystem\n")):
            from core.dashboard import _get_disk
            used, total, pct = _get_disk()
            self.assertEqual(used, "?")


class TestGetMemory(unittest.TestCase):
    """BUG-H01 regression: /proc/meminfo parsing must never raise ValueError."""

    NORMAL_MEMINFO = (
        "MemTotal:       16000000 kB\n"
        "MemFree:         4000000 kB\n"
        "MemAvailable:    8000000 kB\n"
        "Buffers:          500000 kB\n"
        "Cached:          2000000 kB\n"
    )

    def test_normal_meminfo_parsed(self):
        with patch("builtins.open", mock_open(read_data=self.NORMAL_MEMINFO)):
            from core.dashboard import _get_memory
            used, total, pct = _get_memory()
            self.assertIn("GB", total)
            self.assertGreater(float(total.split()[0]), 0)
            self.assertGreaterEqual(pct, 0.0)
            self.assertLessEqual(pct, 100.0)

    def test_line_without_colon_is_skipped(self):
        """BUG-H01: a line with no ':' must not raise ValueError."""
        weird_meminfo = (
            "MemTotal:       16000000 kB\n"
            "ThisLineHasNoColon\n"
            "MemAvailable:    8000000 kB\n"
        )
        with patch("builtins.open", mock_open(read_data=weird_meminfo)):
            from core.dashboard import _get_memory
            used, total, pct = _get_memory()
            self.assertIn("GB", total)

    def test_empty_meminfo_returns_defaults(self):
        with patch("builtins.open", mock_open(read_data="")):
            from core.dashboard import _get_memory
            used, total, pct = _get_memory()
            self.assertEqual(pct, 0.0)

    def test_proc_meminfo_unreadable_returns_defaults(self):
        with patch("builtins.open", side_effect=OSError("no such file")):
            from core.dashboard import _get_memory
            used, total, pct = _get_memory()
            self.assertEqual(used, "?")
            self.assertEqual(total, "?")
            self.assertEqual(pct, 0.0)

    def test_multiple_colons_in_value_parsed_correctly(self):
        """A value containing ':' (unusual but possible) must not crash."""
        weird = (
            "MemTotal:       16000000 kB\n"
            "SomeKey: weird:value here\n"
            "MemAvailable: 8000000 kB\n"
        )
        with patch("builtins.open", mock_open(read_data=weird)):
            from core.dashboard import _get_memory
            used, total, pct = _get_memory()
            self.assertIn("GB", total)


class TestComputeHealthScore(unittest.TestCase):
    def _issue(self, severity, title="Non-boot issue"):
        from core.troubleshoot import DiagnosticIssue
        return DiagnosticIssue(severity=severity, title=title, detail="d")

    def _boot_issue(self, severity="warning"):
        from core.troubleshoot import DiagnosticIssue
        return DiagnosticIssue(severity=severity, title="Boot log entry", detail="kernel: noise")

    def _boot_info(self):
        from core.troubleshoot import DiagnosticIssue
        return DiagnosticIssue(severity="info", title="Boot log entry", detail="ACPI noise")

    def test_perfect_score(self):
        from core.dashboard import compute_health_score
        self.assertEqual(compute_health_score([], 0, "up to date"), 100)

    def test_errors_deduct_10_each(self):
        from core.dashboard import compute_health_score
        issues = [self._issue("error")] * 5
        self.assertEqual(compute_health_score(issues, 0, "up to date"), 50)

    def test_warnings_deduct_5_each(self):
        from core.dashboard import compute_health_score
        issues = [self._issue("warning")] * 10
        self.assertEqual(compute_health_score(issues, 0, "up to date"), 50)

    def test_info_non_boot_deducts_1_each(self):
        from core.dashboard import compute_health_score
        issues = [self._issue("info")] * 5
        self.assertEqual(compute_health_score(issues, 0, "up to date"), 95)

    def test_boot_log_info_deducts_zero(self):
        """Harmless boot noise (info) must not affect the score at all."""
        from core.dashboard import compute_health_score
        issues = [self._boot_info()] * 20
        self.assertEqual(compute_health_score(issues, 0, "up to date"), 100)

    def test_boot_log_warnings_capped_at_15(self):
        """Even 100 boot log warnings can only deduct 15 points total."""
        from core.dashboard import compute_health_score
        issues = [self._boot_issue("warning")] * 100
        self.assertEqual(compute_health_score(issues, 0, "up to date"), 85)

    def test_two_failed_services_plus_boot_noise(self):
        """
        Simulates the live screenshot scenario:
        2 failed services + 13 ACPI/SGX boot log warnings (capped at 15).
        Expected: 100 - 2*10 (errors) - min(13*3,15) (boot cap) = 100-20-15 = 65.
        Crucially: score must NOT be 0.
        """
        from core.dashboard import compute_health_score
        issues = [self._issue("error")] * 2          # 2 failed services
        issues += [self._boot_issue("warning")] * 13  # boot noise (capped at 15)
        score = compute_health_score(issues, 0, "up to date")
        self.assertEqual(score, 65)
        self.assertGreater(score, 0, "Score must never be 0 just from boot noise")

    def test_orphans_capped_at_10(self):
        from core.dashboard import compute_health_score
        self.assertEqual(compute_health_score([], 100, "up to date"), 90)

    def test_updates_available_deducts_2_flat(self):
        from core.dashboard import compute_health_score
        self.assertEqual(compute_health_score([], 0, "5 available"), 98)

    def test_score_never_below_zero(self):
        from core.dashboard import compute_health_score
        issues = [self._issue("error")] * 50
        score = compute_health_score(issues, 10, "99 available")
        self.assertGreaterEqual(score, 0)

    def test_score_never_above_100(self):
        from core.dashboard import compute_health_score
        self.assertLessEqual(compute_health_score([], 0, "up to date"), 100)


# ════════════════════════════════════════════════════════════════════════════
# core/maintenance.py  — BUG-H03, BUG-H04 regression tests
# Patch target: "core.maintenance.run_unprivileged" / "core.maintenance.shutil"
# ════════════════════════════════════════════════════════════════════════════

class TestBuildCacheCleanCommand(unittest.TestCase):
    """BUG-H03: must raise RuntimeError clearly if paccache is missing."""

    def test_raises_when_paccache_missing(self):
        # Patch shutil.which as used inside core.maintenance
        with patch("core.maintenance.shutil.which", return_value=None):
            from core.maintenance import build_cache_clean_command
            with self.assertRaises(RuntimeError) as ctx:
                build_cache_clean_command(1)
            self.assertIn("paccache", str(ctx.exception).lower())

    def test_returns_command_when_paccache_present(self):
        with patch("core.maintenance.shutil.which", return_value="/usr/bin/paccache"):
            from core.maintenance import build_cache_clean_command
            cmd = build_cache_clean_command(1)
            self.assertIn("paccache", cmd)
            self.assertIn("-k", cmd)
            self.assertIn("1", cmd)


class TestBuildTmpCleanupCommand(unittest.TestCase):
    """BUG-H04: must reject paths outside /tmp/ or with '..' traversal."""

    def test_safe_path_accepted(self):
        from core.maintenance import build_tmp_cleanup_command
        cmd = build_tmp_cleanup_command(["/tmp/safe_file.txt"])
        self.assertIn("/tmp/safe_file.txt", cmd)
        self.assertEqual(cmd[0], "rm")

    def test_path_outside_tmp_rejected(self):
        from core.maintenance import build_tmp_cleanup_command
        with self.assertRaises(ValueError):
            build_tmp_cleanup_command(["/home/user/evil_file"])

    def test_dotdot_traversal_rejected(self):
        from core.maintenance import build_tmp_cleanup_command
        with self.assertRaises(ValueError):
            build_tmp_cleanup_command(["/tmp/../../etc/passwd"])

    def test_empty_list_raises(self):
        from core.maintenance import build_tmp_cleanup_command
        with self.assertRaises(ValueError):
            build_tmp_cleanup_command([])

    def test_mixed_list_only_safe_accepted(self):
        from core.maintenance import build_tmp_cleanup_command
        cmd = build_tmp_cleanup_command([
            "/tmp/safe",
            "/home/user/dangerous",
            "/tmp/also_safe",
        ])
        self.assertIn("/tmp/safe", cmd)
        self.assertIn("/tmp/also_safe", cmd)
        self.assertNotIn("/home/user/dangerous", cmd)

    def test_tmp_itself_rejected(self):
        """/tmp itself (not a sub-path) must be rejected."""
        from core.maintenance import build_tmp_cleanup_command
        with self.assertRaises(ValueError):
            build_tmp_cleanup_command(["/tmp"])


class TestBuildOrphanRemovalCommand(unittest.TestCase):
    def test_valid_packages(self):
        from core.maintenance import build_orphan_removal_command
        cmd = build_orphan_removal_command(["pkg-a", "pkg-b"])
        self.assertIn("pacman", cmd)
        self.assertIn("-Rns", cmd)
        self.assertIn("pkg-a", cmd)

    def test_empty_list_raises(self):
        from core.maintenance import build_orphan_removal_command
        with self.assertRaises(ValueError):
            build_orphan_removal_command([])


class TestGetOrphanPackages(unittest.TestCase):
    def test_no_orphans_returns_empty(self):
        # patch where run_unprivileged is *used* — inside core.maintenance
        with patch("core.maintenance.run_unprivileged", return_value=(1, "")):
            from core.maintenance import get_orphan_packages
            self.assertEqual(get_orphan_packages(), [])

    def test_orphans_parsed(self):
        with patch("core.maintenance.run_unprivileged", return_value=(0, "lib-a\nlib-b\n")):
            from core.maintenance import get_orphan_packages
            result = get_orphan_packages()
            self.assertEqual(result, ["lib-a", "lib-b"])


class TestGetPacmanCacheSize(unittest.TestCase):
    """
    Real-world bug from live screenshot: du -sh returns '<size>\\t<path>'
    but we must display only the size token (e.g. '5.8G'), not the full path.
    """

    def test_returns_only_size_not_path(self):
        # du -sh output contains both size AND path separated by tab
        mock_out = "5.8G\t/var/cache/pacman/pkg\n"
        with patch("core.maintenance.run_unprivileged", return_value=(0, mock_out)):
            from core.maintenance import get_pacman_cache_size
            result = get_pacman_cache_size()
            self.assertEqual(result, "5.8G")
            self.assertNotIn("/var/cache", result)

    def test_various_size_units_parsed(self):
        for size in ("123M", "1.2G", "45K", "2.0T"):
            mock_out = f"{size}\t/var/cache/pacman/pkg\n"
            with patch("core.maintenance.run_unprivileged", return_value=(0, mock_out)):
                from core.maintenance import get_pacman_cache_size
                result = get_pacman_cache_size()
                self.assertEqual(result, size)

    def test_failure_returns_unknown(self):
        with patch("core.maintenance.run_unprivileged", return_value=(1, "")):
            from core.maintenance import get_pacman_cache_size
            self.assertEqual(get_pacman_cache_size(), "Unknown")

    def test_empty_output_returns_unknown(self):
        with patch("core.maintenance.run_unprivileged", return_value=(0, "")):
            from core.maintenance import get_pacman_cache_size
            self.assertEqual(get_pacman_cache_size(), "Unknown")


# ════════════════════════════════════════════════════════════════════════════
# core/troubleshoot.py  — BUG-Q01 regression + general checks
# Patch target: "core.troubleshoot.run_unprivileged"
# ════════════════════════════════════════════════════════════════════════════

class TestCheckDiskSpace(unittest.TestCase):
    def test_high_usage_warning(self):
        mock_df = (
            "target pcent source\n"
            "/      95%   /dev/sda1\n"
            "/boot  40%   /dev/sda2\n"
        )
        with patch("core.troubleshoot.run_unprivileged", return_value=(0, mock_df)):
            from core.troubleshoot import check_disk_space
            issues = check_disk_space(threshold_percent=90)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].severity, "warning")
            self.assertIn("/", issues[0].title)

    def test_normal_usage_no_issues(self):
        mock_df = "target pcent source\n/      50%   /dev/sda1\n"
        with patch("core.troubleshoot.run_unprivileged", return_value=(0, mock_df)):
            from core.troubleshoot import check_disk_space
            issues = check_disk_space(threshold_percent=90)
            self.assertEqual(len(issues), 0)

    def test_non_device_mounts_ignored(self):
        mock_df = "target pcent source\n/run   99%   tmpfs\n/sys   10%   sysfs\n"
        with patch("core.troubleshoot.run_unprivileged", return_value=(0, mock_df)):
            from core.troubleshoot import check_disk_space
            issues = check_disk_space(threshold_percent=90)
            self.assertEqual(len(issues), 0)

    def test_malformed_pcent_skipped(self):
        mock_df = "target pcent source\n/      -%    /dev/sda1\n"
        with patch("core.troubleshoot.run_unprivileged", return_value=(0, mock_df)):
            from core.troubleshoot import check_disk_space
            issues = check_disk_space()
            self.assertEqual(len(issues), 0)


class TestCheckFailedPacmanLocks(unittest.TestCase):
    """BUG-Q01 regression: 'import os' must work at module level."""

    def test_no_lock_file(self):
        with patch("core.troubleshoot.os.path.exists", return_value=False):
            from core.troubleshoot import check_failed_pacman_locks
            issues = check_failed_pacman_locks()
            self.assertEqual(len(issues), 0)

    def test_lock_file_present(self):
        with patch("core.troubleshoot.os.path.exists", return_value=True):
            from core.troubleshoot import check_failed_pacman_locks
            issues = check_failed_pacman_locks()
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].severity, "warning")
            self.assertIn("lock", issues[0].title.lower())


class TestGetFailedServices(unittest.TestCase):
    def test_no_failed_services(self):
        with patch("core.troubleshoot.run_unprivileged", return_value=(0, "")):
            from core.troubleshoot import get_failed_services
            self.assertEqual(get_failed_services(), [])

    def test_failed_service_detected(self):
        with patch("core.troubleshoot.run_unprivileged",
                   return_value=(0, "NetworkManager.service loaded failed failed")):
            from core.troubleshoot import get_failed_services
            issues = get_failed_services()
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].severity, "error")
            self.assertIn("NetworkManager", issues[0].title)


# ════════════════════════════════════════════════════════════════════════════
# core/hardware.py  — BUG-H06 regression tests
# Patch target: "core.hardware.run_unprivileged"
# ════════════════════════════════════════════════════════════════════════════

class TestDetectGpuVendors(unittest.TestCase):
    """BUG-H06: all GPU vendors must be detected, not just the first."""

    # Note: tabs for indented lspci lines
    LSPCI_DUAL = (
        "00:02.0 VGA compatible controller [0300]: Intel Corporation UHD Graphics 620\n"
        "\tSubsystem: laptop\n"
        "\tKernel driver in use: i915\n"
        "01:00.0 3D controller [0302]: NVIDIA Corporation GP108M [GeForce MX150]\n"
        "\tSubsystem: other\n"
        "\tKernel driver in use: nvidia\n"
    )

    LSPCI_AMD_ONLY = (
        "00:01.0 VGA compatible controller [0300]: Advanced Micro Devices [AMD/ATI] "
        "Radeon RX 580\n"
        "\tKernel driver in use: amdgpu\n"
    )

    LSPCI_NO_GPU = (
        "00:00.0 Host bridge [0600]: Intel Corporation Device [8086:9b54]\n"
        "\tKernel driver in use: skl_uncore\n"
    )

    def test_dual_gpu_returns_both_vendors(self):
        with patch("core.hardware.run_unprivileged", return_value=(0, self.LSPCI_DUAL)):
            from core.hardware import detect_gpu_vendors
            vendors = detect_gpu_vendors()
            self.assertIn("nvidia", vendors)
            self.assertIn("intel", vendors)

    def test_single_amd_returns_amd_only(self):
        with patch("core.hardware.run_unprivileged", return_value=(0, self.LSPCI_AMD_ONLY)):
            from core.hardware import detect_gpu_vendors
            vendors = detect_gpu_vendors()
            self.assertIn("amd", vendors)
            self.assertNotIn("nvidia", vendors)
            self.assertNotIn("intel", vendors)

    def test_no_gpu_returns_unknown(self):
        with patch("core.hardware.run_unprivileged", return_value=(0, self.LSPCI_NO_GPU)):
            from core.hardware import detect_gpu_vendors
            vendors = detect_gpu_vendors()
            self.assertEqual(vendors, ["unknown"])

    def test_backward_compat_single_vendor_helper(self):
        """detect_gpu_vendor() (singular) must still return a string."""
        with patch("core.hardware.run_unprivileged", return_value=(0, self.LSPCI_AMD_ONLY)):
            from core.hardware import detect_gpu_vendor
            vendor = detect_gpu_vendor()
            self.assertIsInstance(vendor, str)
            self.assertEqual(vendor, "amd")

    def test_no_duplicates_per_vendor(self):
        """If two VGA lines both say Intel, 'intel' should only appear once."""
        lspci_two_intel = (
            "00:02.0 VGA compatible controller: Intel Corporation HD Graphics 630\n"
            "\tKernel driver: i915\n"
            "00:04.0 Display controller: Intel Corporation Iris Plus Graphics\n"
            "\tKernel driver: i915\n"
        )
        with patch("core.hardware.run_unprivileged", return_value=(0, lspci_two_intel)):
            from core.hardware import detect_gpu_vendors
            vendors = detect_gpu_vendors()
            self.assertEqual(vendors.count("intel"), 1)


# ════════════════════════════════════════════════════════════════════════════
# core/drivers.py  — BUG-P04 + BUG-H06 regression tests
# Patch target: "core.drivers.run_unprivileged" / "core.drivers.get_network_devices"
# ════════════════════════════════════════════════════════════════════════════

class TestFilterUninstalled(unittest.TestCase):
    """BUG-P04: must use a single pacman query, not one per package."""

    def test_all_installed(self):
        # pacman -Qq returns the names of installed packages
        with patch("core.drivers.run_unprivileged",
                   return_value=(0, "mesa\nvulkan-radeon\n")):
            from core.drivers import filter_uninstalled
            result = filter_uninstalled(["mesa", "vulkan-radeon"])
            self.assertEqual(result, [])

    def test_none_installed(self):
        # pacman -Qq returns empty when none found
        with patch("core.drivers.run_unprivileged", return_value=(0, "")):
            from core.drivers import filter_uninstalled
            result = filter_uninstalled(["mesa", "nvidia"])
            self.assertIn("mesa", result)
            self.assertIn("nvidia", result)

    def test_partial_install(self):
        with patch("core.drivers.run_unprivileged",
                   return_value=(0, "mesa\n")):
            from core.drivers import filter_uninstalled
            result = filter_uninstalled(["mesa", "vulkan-radeon"])
            self.assertNotIn("mesa", result)
            self.assertIn("vulkan-radeon", result)

    def test_empty_input_returns_empty(self):
        from core.drivers import filter_uninstalled
        self.assertEqual(filter_uninstalled([]), [])

    def test_single_pacman_call_for_multiple_packages(self):
        """BUG-P04 regression: verify only ONE run_unprivileged call is made."""
        call_count = [0]

        def counting_run(cmd, **kw):
            call_count[0] += 1
            # Return empty (none installed) to avoid side effects
            return (0, "")

        with patch("core.drivers.run_unprivileged", side_effect=counting_run):
            from core.drivers import filter_uninstalled
            filter_uninstalled(["mesa", "vulkan-radeon", "lib32-mesa"])

        self.assertEqual(
            call_count[0], 1,
            "filter_uninstalled must use exactly 1 pacman call (BUG-P04 regression)"
        )


class TestSuggestGpuPackages(unittest.TestCase):
    """BUG-H06: packages for ALL detected GPU vendors must be included."""

    LSPCI_DUAL = (
        "00:02.0 VGA compatible controller [0300]: Intel Corporation UHD Graphics\n"
        "\tKernel driver in use: i915\n"
        "01:00.0 3D controller [0302]: NVIDIA Corporation GeForce MX150\n"
        "\tKernel driver in use: nvidia\n"
    )

    LSPCI_AMD_INTEL = (
        "00:02.0 VGA compatible controller: Intel Corporation HD Graphics 630\n"
        "\tKernel driver: i915\n"
        "01:00.0 Display controller: Advanced Micro Devices [AMD/ATI] Radeon\n"
        "\tKernel driver: amdgpu\n"
    )

    def test_dual_intel_nvidia_suggests_both_package_sets(self):
        with patch("core.hardware.run_unprivileged", return_value=(0, self.LSPCI_DUAL)):
            with patch("core.drivers.get_network_devices", return_value=[]):
                from core.drivers import suggest_gpu_packages
                vendor_str, pkgs = suggest_gpu_packages()
                self.assertIn("nvidia", vendor_str)
                self.assertIn("intel", vendor_str)
                pkg_str = " ".join(pkgs)
                self.assertIn("nvidia", pkg_str)
                self.assertIn("mesa", pkg_str)
                self.assertIn("vulkan-intel", pkg_str)

    def test_no_duplicates_in_package_list(self):
        """'mesa' must appear only once even if both intel and amd need it."""
        with patch("core.hardware.run_unprivileged", return_value=(0, self.LSPCI_AMD_INTEL)):
            with patch("core.drivers.get_network_devices", return_value=[]):
                from core.drivers import suggest_gpu_packages
                _, pkgs = suggest_gpu_packages()
                self.assertEqual(
                    len(pkgs), len(set(pkgs)),
                    "Package list must not contain duplicates"
                )


# ════════════════════════════════════════════════════════════════════════════
# core/broken_packages.py
# Patch target: "core.broken_packages.run_unprivileged"
# ════════════════════════════════════════════════════════════════════════════

class TestScanBrokenPackages(unittest.TestCase):
    def test_healthy_system_returns_empty(self):
        # All packages show "0 missing files" — exit 0
        mock_out = "package1: 0 missing files\npackage2: 0 missing files\n"
        with patch("core.broken_packages.run_unprivileged", return_value=(0, mock_out)):
            from core.broken_packages import scan_broken_packages
            self.assertEqual(scan_broken_packages(), [])

    def test_broken_package_detected(self):
        # exit 1 when some packages have issues (pacman -Qk convention)
        mock_out = "package1: 0 missing files\nbadpkg: 3 missing files\n"
        with patch("core.broken_packages.run_unprivileged", return_value=(1, mock_out)):
            from core.broken_packages import scan_broken_packages
            result = scan_broken_packages()
            self.assertTrue(any("badpkg" in r for r in result))
            # Healthy lines must be filtered out
            self.assertFalse(any("package1" in r for r in result))

    def test_pacman_crash_returns_error_message(self):
        # Exit code 2 means pacman itself crashed
        with patch("core.broken_packages.run_unprivileged", return_value=(2, "fatal error")):
            from core.broken_packages import scan_broken_packages
            result = scan_broken_packages()
            self.assertEqual(len(result), 1)
            self.assertIn("Could not run", result[0])

    def test_build_reinstall_command_valid(self):
        from core.broken_packages import build_reinstall_command
        cmd = build_reinstall_command("mesa")
        self.assertIn("pacman", cmd)
        self.assertIn("mesa", cmd)

    def test_build_reinstall_empty_raises(self):
        from core.broken_packages import build_reinstall_command
        with self.assertRaises(ValueError):
            build_reinstall_command("  ")


# ════════════════════════════════════════════════════════════════════════════
# core/disk_analyzer.py
# Patch target: "core.disk_analyzer.run_unprivileged"
# ════════════════════════════════════════════════════════════════════════════

class TestDiskAnalyzer(unittest.TestCase):
    def test_get_filesystems_summary_success(self):
        with patch("core.disk_analyzer.run_unprivileged", return_value=(0, "df output")):
            from core.disk_analyzer import get_filesystems_summary
            result = get_filesystems_summary()
            self.assertEqual(result, "df output")

    def test_get_filesystems_summary_failure(self):
        with patch("core.disk_analyzer.run_unprivileged", return_value=(1, "")):
            from core.disk_analyzer import get_filesystems_summary
            result = get_filesystems_summary()
            self.assertIn("Could not", result)

    def test_get_largest_pacman_cache_files_empty_cache(self):
        # find returns 0 lines → "Cache directory is empty."
        with patch("core.disk_analyzer.run_unprivileged", return_value=(0, "")):
            from core.disk_analyzer import get_largest_pacman_cache_files
            result = get_largest_pacman_cache_files()
            self.assertIn("empty", result.lower())

    def test_get_largest_pacman_cache_files_find_failure(self):
        with patch("core.disk_analyzer.run_unprivileged", return_value=(1, "")):
            from core.disk_analyzer import get_largest_pacman_cache_files
            result = get_largest_pacman_cache_files()
            self.assertIn("Could not", result)

    def test_get_largest_pacman_cache_files_sorted(self):
        mock_out = (
            "1000\t/var/cache/pacman/pkg/small.pkg\n"
            "100000000\t/var/cache/pacman/pkg/large.pkg\n"
        )
        with patch("core.disk_analyzer.run_unprivileged", return_value=(0, mock_out)):
            from core.disk_analyzer import get_largest_pacman_cache_files
            result = get_largest_pacman_cache_files(2)
            lines = result.strip().splitlines()
            # Largest must come first
            self.assertIn("large.pkg", lines[0])
            self.assertIn("small.pkg", lines[1])


# ════════════════════════════════════════════════════════════════════════════
# Network input validation  — BUG-C02 regression tests
# ════════════════════════════════════════════════════════════════════════════

class TestNetworkHostValidation(unittest.TestCase):
    """BUG-C02: ping host must be validated before being passed to subprocess."""

    def _validate(self, host: str) -> bool:
        from ui.pages.page_network import _validate_host
        return _validate_host(host)

    def test_valid_ipv4(self):
        self.assertTrue(self._validate("8.8.8.8"))
        self.assertTrue(self._validate("1.1.1.1"))
        self.assertTrue(self._validate("192.168.1.1"))

    def test_valid_hostname(self):
        self.assertTrue(self._validate("archlinux.org"))
        self.assertTrue(self._validate("mirrors.kernel.org"))
        self.assertTrue(self._validate("localhost"))

    def test_shell_injection_rejected(self):
        self.assertFalse(self._validate("; rm -rf /"))
        self.assertFalse(self._validate("1.1.1.1; whoami"))
        self.assertFalse(self._validate("$(evil)"))
        self.assertFalse(self._validate("`rm -rf ~`"))
        self.assertFalse(self._validate("host | cat /etc/passwd"))

    def test_empty_string_rejected(self):
        self.assertFalse(self._validate(""))

    def test_too_long_rejected(self):
        self.assertFalse(self._validate("a" * 300))

    def test_path_traversal_rejected(self):
        self.assertFalse(self._validate("../../etc/passwd"))

    def test_spaces_rejected(self):
        self.assertFalse(self._validate("valid host"))

    def test_ipv6_accepted(self):
        self.assertTrue(self._validate("2606:4700:4700::1111"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
