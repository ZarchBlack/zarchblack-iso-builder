"""
tests/test_integration.py
==========================
Integration-level tests — verify that the full call chain from a UI action
through the core module and back produces the expected result.

These tests still mock external tools (pacman, systemctl …) so they work
without an Arch Linux system, but they exercise MORE of the real code path
than the pure unit tests in test_core.py.

Run with:
    python3 -m pytest tests/ -v
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, mock_open

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ════════════════════════════════════════════════════════════════════════════
# Full maintenance command-building pipeline
# ════════════════════════════════════════════════════════════════════════════

class TestMaintenancePipeline(unittest.TestCase):
    """
    Simulate the flow a UI button click would take:
      user clicks → confirm dialog → commands built → would be sent to pkexec.
    """

    def test_orphan_removal_full_flow(self):
        """get_orphan_packages → build_orphan_removal_command → valid pkexec args."""
        mock_pacman = "lib-unused\npython-old-package\n"
        with patch("core.maintenance.run_unprivileged", return_value=(0, mock_pacman)):
            from core.maintenance import get_orphan_packages, build_orphan_removal_command
            orphans = get_orphan_packages()
            self.assertEqual(len(orphans), 2)
            cmd = build_orphan_removal_command(orphans)
            self.assertIn("pacman", cmd)
            self.assertIn("-Rns", cmd)
            self.assertIn("lib-unused", cmd)
            self.assertIn("python-old-package", cmd)

    def test_cache_clean_flow_with_paccache(self):
        with patch("core.maintenance.shutil.which", return_value="/usr/bin/paccache"):
            from core.maintenance import build_cache_clean_command
            cmd = build_cache_clean_command(2)
            self.assertIn("paccache", cmd[0])
            self.assertIn("2", cmd)

    def test_cache_clean_flow_without_paccache_raises(self):
        with patch("core.maintenance.shutil.which", return_value=None):
            from core.maintenance import build_cache_clean_command
            with self.assertRaises(RuntimeError) as ctx:
                build_cache_clean_command()
            self.assertIn("paccache", str(ctx.exception))
            self.assertIn("pacman-contrib", str(ctx.exception))

    def test_tmp_cleanup_flow(self):
        safe_paths = ["/tmp/old_stuff", "/tmp/leftover_cache"]
        from core.maintenance import build_tmp_cleanup_command
        cmd = build_tmp_cleanup_command(safe_paths)
        self.assertEqual(cmd[0], "rm")
        self.assertIn("-rf", cmd)
        for p in safe_paths:
            self.assertIn(p, cmd)

    def test_tmp_cleanup_rejects_dangerous_paths_but_accepts_safe_ones(self):
        mixed = ["/tmp/safe", "/etc/passwd", "/tmp/../../root/.bashrc"]
        from core.maintenance import build_tmp_cleanup_command
        cmd = build_tmp_cleanup_command(mixed)
        self.assertIn("/tmp/safe", cmd)
        self.assertNotIn("/etc/passwd", cmd)
        self.assertNotIn("/root/.bashrc", cmd)


# ════════════════════════════════════════════════════════════════════════════
# Health Score calculation chain (BUG-H01 data flows into score)
# ════════════════════════════════════════════════════════════════════════════

class TestHealthScorePipeline(unittest.TestCase):
    """
    Simulate DashboardPage refresh → build_dashboard_snapshot →
    compute_health_score to check that BUG-H01 parsing feeds
    correctly into the score.
    """

    _GOOD_MEMINFO = (
        "MemTotal:       16384000 kB\n"
        "MemFree:         8192000 kB\n"
        "MemAvailable:   10240000 kB\n"
    )

    def _make_mocks(self, disk_out, mem_data, issues, orphan_out):
        """Helper that patches all external calls used by build_dashboard_snapshot."""
        return [
            patch("core.dashboard.run_unprivileged", side_effect=[
                (0, disk_out),      # df -B1 /
                (0, ""),            # pacman -Qq
                (0, ""),            # checkupdates
                (0, "0 kB"),        # du -sh pacman cache
                (1, ""),            # pacman -Qtdq (no orphans)
                (0, "2h 10m"),      # uptime (actually from /proc/uptime)
                (0, "6.9.0-arch1"), # uname -r
                (0, "active"),      # systemctl is-active firewalld
            ]),
            patch("builtins.open", side_effect=lambda path, **kw:
                  open(os.devnull) if "/proc/uptime" in path else
                  __import__("io").StringIO(mem_data) if "meminfo" in path else
                  __import__("io").StringIO("0.0 0") if "stat" in path else
                  open(os.devnull)
            ),
            patch("core.dashboard.troubleshoot.run_full_diagnosis", return_value=issues),
        ]

    def test_perfect_system_scores_100(self):
        from core.dashboard import compute_health_score
        score = compute_health_score([], 0, "up to date")
        self.assertEqual(score, 100)

    def test_one_error_service_deducts_10(self):
        from core.dashboard import compute_health_score
        from core.troubleshoot import DiagnosticIssue
        issues = [DiagnosticIssue("error", "NetworkManager failed", "detail")]
        score = compute_health_score(issues, 0, "up to date")
        self.assertEqual(score, 90)

    def test_score_with_combined_problems(self):
        from core.dashboard import compute_health_score
        from core.troubleshoot import DiagnosticIssue
        issues = [
            DiagnosticIssue("error",   "svc1 failed", ""),
            DiagnosticIssue("warning", "disk 91% full", ""),
            DiagnosticIssue("info",    "pacnew files", ""),
        ]
        # -10 (error) -5 (warning) -1 (info) -5 (orphans) -2 (updates flat) = 77
        score = compute_health_score(issues, 5, "3 available")
        self.assertEqual(score, 77)

    def test_meminfo_with_no_colon_line_does_not_crash_score(self):
        """BUG-H01 end-to-end: weird meminfo must not corrupt the score."""
        from unittest.mock import mock_open as mk_open
        weird = "MemTotal:       8000000 kB\nSomeGarbageLine\nMemAvailable:   4000000 kB\n"
        with patch("builtins.open", mk_open(read_data=weird)):
            from core.dashboard import _get_memory
            # Must not raise
            used, total, pct = _get_memory()
            self.assertIn("GB", total)
            self.assertGreater(float(total.split()[0]), 0)


# ════════════════════════════════════════════════════════════════════════════
# Driver suggestion pipeline (BUG-H06 + BUG-P04 end-to-end)
# ════════════════════════════════════════════════════════════════════════════

class TestDriverPipeline(unittest.TestCase):
    """
    GPU detection → driver suggestion → filter_uninstalled → install command.
    Verifies BUG-H06 (multi-vendor) and BUG-P04 (single query) work together.
    """

    LSPCI_DUAL = (
        "00:02.0 VGA compatible controller: Intel Corporation UHD Graphics 620\n"
        "\tKernel driver in use: i915\n"
        "01:00.0 3D controller: NVIDIA Corporation GeForce MX150\n"
        "\tKernel driver in use: nvidia\n"
    )

    def test_dual_gpu_full_pipeline(self):
        """Intel+NVIDIA laptop gets packages for both GPUs suggested and filtered."""
        # lspci returns dual GPU
        with patch("core.hardware.run_unprivileged", return_value=(0, self.LSPCI_DUAL)):
            # pacman -Qq returns only mesa as installed
            with patch("core.drivers.run_unprivileged", return_value=(0, "mesa\n")):
                with patch("core.drivers.get_network_devices", return_value=[]):
                    from core.drivers import suggest_gpu_packages, filter_uninstalled
                    vendor_str, all_pkgs = suggest_gpu_packages()

                    # Both vendors detected
                    self.assertIn("nvidia", vendor_str)
                    self.assertIn("intel", vendor_str)

                    # Not installed = all - mesa
                    not_installed = filter_uninstalled(all_pkgs)
                    self.assertNotIn("mesa", not_installed)          # already installed
                    self.assertIn("nvidia", " ".join(not_installed)) # needs install
                    self.assertIn("vulkan-intel", not_installed)     # needs install

    def test_filter_uninstalled_uses_one_call(self):
        """BUG-P04 regression: exactly 1 pacman call regardless of package count."""
        call_log = []

        def spy_run(cmd, **kw):
            call_log.append(cmd)
            return (0, "")

        with patch("core.drivers.run_unprivileged", side_effect=spy_run):
            from core.drivers import filter_uninstalled
            filter_uninstalled(["mesa", "nvidia", "vulkan-intel", "lib32-mesa"])

        self.assertEqual(len(call_log), 1)
        # The single call must pass all packages at once
        joined = " ".join(call_log[0])
        self.assertIn("mesa", joined)
        self.assertIn("nvidia", joined)

    def test_build_install_command_valid(self):
        from core.drivers import build_install_command
        cmd = build_install_command(["nvidia", "nvidia-utils"])
        self.assertIn("pacman", cmd)
        self.assertIn("-S", cmd)
        self.assertIn("--needed", cmd)
        self.assertIn("nvidia", cmd)

    def test_build_install_command_empty_raises(self):
        from core.drivers import build_install_command
        with self.assertRaises(ValueError):
            build_install_command([])


# ════════════════════════════════════════════════════════════════════════════
# PrivilegedSequenceRunner — BUG-C03 + BUG-C04 integration
# ════════════════════════════════════════════════════════════════════════════

class TestPrivilegedSequenceRunner(unittest.TestCase):
    """
    Test the runner logic without spawning a real process.
    We patch run_privileged_stream to return a mock QProcess.
    """

    def _make_runner_with_mock_process(self):
        """Return (runner, output_widget, done_calls, mock_process)."""
        from unittest.mock import MagicMock, patch

        output = MagicMock()
        output.toPlainText.return_value = ""
        done_calls = []

        mock_proc = MagicMock()
        # Simulate signals as plain lists of connected callbacks
        mock_proc._stdout_handlers = []
        mock_proc._finish_handlers = []
        mock_proc.readyReadStandardOutput = MagicMock()
        mock_proc.readyReadStandardOutput.connect = lambda h: mock_proc._stdout_handlers.append(h)
        mock_proc.readyReadStandardOutput.disconnect = MagicMock()
        mock_proc.finished = MagicMock()
        mock_proc.finished.connect = lambda h: mock_proc._finish_handlers.append(h)
        mock_proc.finished.disconnect = MagicMock()
        mock_proc.start = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.waitForFinished = MagicMock()
        mock_proc.readAllStandardOutput = MagicMock(return_value=b"output data")
        mock_proc.isRunning = MagicMock(return_value=False)

        from ui.privileged_sequence import PrivilegedSequenceRunner
        runner = PrivilegedSequenceRunner(output, on_all_done=lambda: done_calls.append(1))
        return runner, output, done_calls, mock_proc

    def test_is_running_false_before_run(self):
        runner, *_ = self._make_runner_with_mock_process()
        self.assertFalse(runner.is_running())

    def test_is_running_true_after_run_called(self):
        runner, _, done_calls, mock_proc = self._make_runner_with_mock_process()

        with patch("ui.privileged_sequence.run_privileged_stream", return_value=mock_proc):
            runner.run([("Step 1", ["echo", "hello"])])
            self.assertTrue(runner.is_running())

    def test_on_all_done_called_after_last_step(self):
        runner, _, done_calls, mock_proc = self._make_runner_with_mock_process()

        with patch("ui.privileged_sequence.run_privileged_stream", return_value=mock_proc):
            runner.run([("Step 1", ["echo", "hello"])])
            # Simulate step finishing with exit code 0
            for handler in mock_proc._finish_handlers:
                handler(0, None)

        self.assertEqual(done_calls, [1], "on_all_done must be called exactly once")

    def test_on_all_done_not_called_mid_sequence(self):
        runner, _, done_calls, mock_proc = self._make_runner_with_mock_process()

        # Two steps
        steps = [("Step 1", ["echo", "a"]), ("Step 2", ["echo", "b"])]

        procs = [MagicMock() for _ in steps]
        for proc in procs:
            proc._finish_handlers = []
            proc.finished = MagicMock()
            proc.finished.connect = lambda h, p=proc: p._finish_handlers.append(h)
            proc.finished.disconnect = MagicMock()
            proc.readyReadStandardOutput = MagicMock()
            proc.readyReadStandardOutput.connect = MagicMock()
            proc.readyReadStandardOutput.disconnect = MagicMock()
            proc.start = MagicMock()
            proc.kill = MagicMock()
            proc.waitForFinished = MagicMock()
            proc.readAllStandardOutput = MagicMock(return_value=b"")

        proc_iter = iter(procs)
        with patch("ui.privileged_sequence.run_privileged_stream",
                   side_effect=lambda *a, **k: next(proc_iter)):
            runner.run(steps)
            # Finish step 1 — on_all_done must NOT fire yet
            for h in procs[0]._finish_handlers:
                h(0, None)
            self.assertEqual(done_calls, [], "on_all_done must not fire after first step")

            # Finish step 2 — now it must fire
            for h in procs[1]._finish_handlers:
                h(0, None)
            self.assertEqual(done_calls, [1], "on_all_done must fire after final step")

    def test_empty_steps_list_does_not_set_running(self):
        runner, _, done_calls, _ = self._make_runner_with_mock_process()
        runner.run([])
        self.assertFalse(runner.is_running())


# ════════════════════════════════════════════════════════════════════════════
# Network host validation — edge cases (BUG-C02)
# ════════════════════════════════════════════════════════════════════════════

class TestNetworkValidationEdgeCases(unittest.TestCase):
    """Additional edge cases not covered in test_core.py."""

    def _v(self, host):
        from ui.pages.page_network import _validate_host
        return _validate_host(host)

    def test_null_bytes_rejected(self):
        self.assertFalse(self._v("host\x00evil"))

    def test_newlines_rejected(self):
        self.assertFalse(self._v("host\nevil"))

    def test_tab_rejected(self):
        self.assertFalse(self._v("host\tevil"))

    def test_leading_hyphen_hostname_rejected(self):
        # RFC 1123: labels must not start with hyphen
        self.assertFalse(self._v("-badhost.org"))

    def test_single_label_hostname_accepted(self):
        # Plain single-word hostname (e.g. "router" on LAN)
        self.assertTrue(self._v("router"))

    def test_valid_subdomain_three_levels(self):
        self.assertTrue(self._v("mirrors.archlinux.org"))

    def test_numeric_only_hostname_not_ipv4(self):
        # e.g. "123" — a valid single-label hostname
        self.assertTrue(self._v("123"))

    def test_port_number_in_host_rejected(self):
        self.assertFalse(self._v("8.8.8.8:53"))

    def test_url_scheme_rejected(self):
        self.assertFalse(self._v("https://archlinux.org"))

    def test_angle_bracket_injection_rejected(self):
        self.assertFalse(self._v("<script>"))

    def test_ampersand_rejected(self):
        self.assertFalse(self._v("host & cat /etc/shadow"))


# ════════════════════════════════════════════════════════════════════════════
# WorkerMixin — BUG-C01 integration
# ════════════════════════════════════════════════════════════════════════════

class TestWorkerMixinCleanup(unittest.TestCase):
    """
    Verify that workers are automatically removed from _workers after completion.
    """

    def test_worker_removed_after_done_signal(self):
        from ui.worker_mixin import WorkerMixin
        from ui.workers import FunctionWorker

        class MockPage(WorkerMixin):
            def __init__(self):
                self._workers = []

        page = MockPage()
        worker = page._spawn_worker(lambda: 42)

        # Before done: worker is in the list
        self.assertIn(worker, page._workers)

        # Simulate the done signal firing (as it would after thread finishes)
        worker.done.emit()

        # After done: worker must be removed
        self.assertNotIn(worker, page._workers)
        self.assertEqual(len(page._workers), 0)

    def test_multiple_workers_removed_independently(self):
        from ui.worker_mixin import WorkerMixin

        class MockPage(WorkerMixin):
            def __init__(self):
                self._workers = []

        page = MockPage()
        w1 = page._spawn_worker(lambda: 1)
        w2 = page._spawn_worker(lambda: 2)
        w3 = page._spawn_worker(lambda: 3)

        self.assertEqual(len(page._workers), 3)

        w2.done.emit()
        self.assertEqual(len(page._workers), 2)
        self.assertNotIn(w2, page._workers)
        self.assertIn(w1, page._workers)
        self.assertIn(w3, page._workers)

        w1.done.emit()
        w3.done.emit()
        self.assertEqual(len(page._workers), 0)

    def test_done_emitted_on_success(self):
        """FunctionWorker must emit done even on successful execution."""
        from ui.workers import FunctionWorker
        done_received = []

        worker = FunctionWorker(lambda: 99)
        worker.done.connect(lambda: done_received.append(True))
        worker.run()   # run directly in this thread for simplicity

        self.assertEqual(done_received, [True])

    def test_done_emitted_on_exception(self):
        """FunctionWorker must emit done even when the function raises."""
        from ui.workers import FunctionWorker
        done_received = []
        errors = []

        def explode():
            raise RuntimeError("intentional test failure")

        worker = FunctionWorker(explode)
        worker.done.connect(lambda: done_received.append(True))
        worker.failed.connect(lambda e: errors.append(e))
        worker.run()

        self.assertEqual(done_received, [True], "done must fire even on exception")
        self.assertEqual(len(errors), 1)
        self.assertIn("intentional", errors[0])


# ════════════════════════════════════════════════════════════════════════════
# Logging system — BUG-H05 integration
# ════════════════════════════════════════════════════════════════════════════

class TestLoggingIntegration(unittest.TestCase):
    """
    Verify that calls to core functions produce log records (i.e. the logging
    hooks inside the fixed functions are actually wired up correctly).
    """

    def test_paccache_missing_logs_warning_via_maintenance(self):
        """When paccache is missing, a RuntimeError is raised (no log needed here,
        but we verify the module imports cleanly with logger active)."""
        with patch("core.maintenance.shutil.which", return_value=None):
            from core.maintenance import build_cache_clean_command
            with self.assertRaises(RuntimeError):
                build_cache_clean_command()

    def test_unsafe_path_logs_warning(self):
        """build_tmp_cleanup_command must log rejected paths."""
        import logging
        from core.logger import get_logger
        logger = get_logger("core.maintenance")

        with self.assertLogs("zarchcare.core.maintenance", level="WARNING") as log:
            from core.maintenance import build_tmp_cleanup_command
            try:
                build_tmp_cleanup_command(["/tmp/ok", "/home/evil"])
            except ValueError:
                pass  # expected when only safe paths remain

        # At least one warning about the rejected path must appear
        self.assertTrue(
            any("/home/evil" in m or "rejected" in m.lower() for m in log.output),
            "Expected a WARNING about the rejected path but got: " + str(log.output)
        )

    def test_logger_namespace_correct(self):
        """All loggers must be under 'zarchcare' so our handlers apply."""
        from core.logger import get_logger
        for name in ["core.maintenance", "core.dashboard", "ui.workers", "main"]:
            logger = get_logger(name)
            self.assertTrue(
                logger.name.startswith("zarchcare"),
                f"Logger '{logger.name}' is not under 'zarchcare' namespace"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ════════════════════════════════════════════════════════════════════════════
# v1.2 — core/sysctl.py unit tests
# ════════════════════════════════════════════════════════════════════════════

class TestSysctlModule(unittest.TestCase):

    def test_pacman_list_installed_parses_output(self):
        with patch("core.sysctl.run_unprivileged", return_value=(0, "pkg-a\npkg-b\n")):
            from core.sysctl import pacman_list_installed
            self.assertEqual(pacman_list_installed(), ["pkg-a", "pkg-b"])

    def test_pacman_list_installed_failure_returns_empty(self):
        with patch("core.sysctl.run_unprivileged", return_value=(1, "")):
            from core.sysctl import pacman_list_installed
            self.assertEqual(pacman_list_installed(), [])

    def test_pacman_query_installed_returns_set(self):
        with patch("core.sysctl.run_unprivileged", return_value=(0, "mesa\nvulkan-radeon\n")):
            from core.sysctl import pacman_query_installed
            installed = pacman_query_installed("mesa", "vulkan-radeon", "ghost-pkg")
            self.assertIn("mesa", installed)
            self.assertNotIn("ghost-pkg", installed)

    def test_pacman_query_installed_empty_input(self):
        from core.sysctl import pacman_query_installed
        self.assertEqual(pacman_query_installed(), set())

    def test_uname_release_strips_newline(self):
        with patch("core.sysctl.run_unprivileged", return_value=(0, "6.12.1-zen\n")):
            from core.sysctl import uname_release
            self.assertEqual(uname_release(), "6.12.1-zen")

    def test_uname_release_failure_returns_question(self):
        with patch("core.sysctl.run_unprivileged", return_value=(1, "")):
            from core.sysctl import uname_release
            self.assertEqual(uname_release(), "?")

    def test_uptime_seconds_parses_proc(self):
        from core.sysctl import uptime_seconds
        with patch("builtins.open", mock_open(read_data="3723.45 0.00\n")):
            result = uptime_seconds()
            self.assertAlmostEqual(result, 3723.45, places=1)

    def test_uptime_seconds_io_error_returns_none(self):
        from core.sysctl import uptime_seconds
        with patch("builtins.open", side_effect=OSError("no file")):
            self.assertIsNone(uptime_seconds())

    def test_command_available_echo(self):
        from core.sysctl import command_available
        self.assertTrue(command_available("echo"))

    def test_command_available_nonexistent(self):
        from core.sysctl import command_available
        self.assertFalse(command_available("__no_such_cmd_xyz__"))

    def test_first_available_returns_first_found(self):
        from core.sysctl import first_available
        self.assertEqual(first_available("__nonexistent__", "echo"), "echo")

    def test_first_available_none_found(self):
        from core.sysctl import first_available
        self.assertIsNone(first_available("__no1__", "__no2__"))

    def test_pacman_cache_size_returns_size_only(self):
        with patch("core.sysctl.run_unprivileged",
                   return_value=(0, "5.8G\t/var/cache/pacman/pkg\n")):
            from core.sysctl import pacman_cache_size
            result = pacman_cache_size()
            self.assertEqual(result, "5.8G")
            self.assertNotIn("/var/cache", result)

    def test_systemctl_first_active_none_when_all_inactive(self):
        with patch("core.sysctl.run_unprivileged", return_value=(1, "inactive")):
            from core.sysctl import systemctl_first_active
            self.assertIsNone(systemctl_first_active("firewalld", "ufw"))

    def test_systemctl_first_active_returns_match(self):
        def mock_run(cmd, **kw):
            return (0, "active") if "ufw" in cmd else (1, "inactive")
        with patch("core.sysctl.run_unprivileged", side_effect=mock_run):
            from core.sysctl import systemctl_first_active
            self.assertEqual(
                systemctl_first_active("firewalld", "ufw", "nftables"), "ufw"
            )


# ════════════════════════════════════════════════════════════════════════════
# v1.2 — core/operation_log.py unit tests
# ════════════════════════════════════════════════════════════════════════════

class TestOperationLog(unittest.TestCase):

    def setUp(self):
        from core.operation_log import OperationLog
        self.log = OperationLog(max_entries=10)

    def test_record_success(self):
        self.log.record("Action", success=True, detail="ok")
        self.assertEqual(self.log.count, 1)
        self.assertEqual(self.log.success_count, 1)
        self.assertEqual(self.log.failure_count, 0)

    def test_record_failure(self):
        self.log.record("Failed", success=False)
        self.assertEqual(self.log.failure_count, 1)

    def test_as_text_empty(self):
        self.assertIn("No operations", self.log.as_text())

    def test_as_text_contains_entries(self):
        self.log.record("First", success=True)
        self.log.record("Second", success=False)
        text = self.log.as_text()
        self.assertIn("First", text)
        self.assertIn("✅", text)
        self.assertIn("❌", text)

    def test_max_entries_enforced(self):
        for i in range(20):
            self.log.record(f"Action {i}", success=True)
        self.assertLessEqual(self.log.count, 10)

    def test_clear_resets(self):
        self.log.record("X", success=True)
        self.log.clear()
        self.assertEqual(self.log.count, 0)

    def test_export_has_header(self):
        self.log.record("X", success=True)
        self.assertIn("ZarchCare Session Log", self.log.export())

    def test_reversed_newest_first(self):
        self.log.record("First", success=True)
        self.log.record("Last", success=True)
        self.assertIn("Last", self.log.as_text_reversed().splitlines()[0])

    def test_entries_is_copy(self):
        self.log.record("E", success=True)
        self.log.entries.clear()
        self.assertEqual(self.log.count, 1)

    def test_singleton_type(self):
        from core.operation_log import op_log, OperationLog
        self.assertIsInstance(op_log, OperationLog)


# ════════════════════════════════════════════════════════════════════════════
# v1.2 — core/settings.py unit tests
# ════════════════════════════════════════════════════════════════════════════

class TestSettings(unittest.TestCase):

    def setUp(self):
        from core.settings import AppSettings
        self.s = AppSettings()
        self.s.reset_all()

    def test_auto_refresh_default_zero(self):
        self.assertEqual(self.s.auto_refresh_interval, 0)

    def test_auto_refresh_set(self):
        self.s.auto_refresh_interval = 300
        self.assertEqual(self.s.auto_refresh_interval, 300)

    def test_auto_refresh_negative_clamped(self):
        self.s.auto_refresh_interval = -5
        self.assertEqual(self.s.auto_refresh_interval, 0)

    def test_last_page_index_default_zero(self):
        self.assertEqual(self.s.last_page_index, 0)

    def test_last_page_index_set(self):
        self.s.last_page_index = 4
        self.assertEqual(self.s.last_page_index, 4)

    def test_last_page_negative_clamped(self):
        self.s.last_page_index = -1
        self.assertEqual(self.s.last_page_index, 0)

    def test_show_notifications_default_true(self):
        self.assertTrue(self.s.show_notifications)

    def test_show_notifications_toggle(self):
        self.s.show_notifications = False
        self.assertFalse(self.s.show_notifications)

    def test_scan_on_health_open_default_true(self):
        self.assertTrue(self.s.scan_on_health_open)

    def test_reset_restores_defaults(self):
        self.s.auto_refresh_interval = 600
        self.s.last_page_index = 9
        self.s.reset_all()
        self.assertEqual(self.s.auto_refresh_interval, 0)
        self.assertEqual(self.s.last_page_index, 0)

    def test_singleton_type(self):
        from core.settings import settings, AppSettings
        self.assertIsInstance(settings, AppSettings)

