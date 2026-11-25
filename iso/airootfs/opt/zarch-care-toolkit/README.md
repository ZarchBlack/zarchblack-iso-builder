# ZarchCare
### ZarchBlack System Care Tool — Complete System Maintenance Suite

# ZarchCare — v2.0 (Renamed & Enhanced Release)
### ZarchBlack System Care Tool

---

## Overview

`ZarchCare` is a desktop app built with **Python 3 + PySide6 (Qt6)** designed
specifically for **ZarchBlack (Arch Linux)**. It provides a
complete system-care toolbox accessible from a sidebar-navigated single window:

- **Dashboard** — live tiles for Disk, Memory, CPU, Packages, Updates, Cache,
  Orphans, Uptime, Kernel, refreshed on demand.
- **Health Score** — a 0–100 score from failed services, boot errors, disk
  pressure, pacman locks, orphan packages and pending updates.
- **Network Tools & Logs** — ping (validated), interfaces, DNS status, recent journal logs.
- **Hardware & Drivers** — CPU/GPU/RAM/Storage/Motherboard detection and
  driver suggestion/installation (supports multi-GPU: Intel iGPU + NVIDIA/AMD).
- **Clean System** — orphan packages, pacman cache trimming, journal vacuum.
- **Update System** — `pacman -Syu` with real-time output and clear error reporting.
- **Disk Analyzer** — filesystem usage, home-folder breakdown, largest pacman cache files.
- **Broken Packages** — `pacman -Qk` integrity scan with one-line fix hints.
- **Pacnew Files** — `.pacnew` review helper.
- **Quick Clean** — one click, two safe steps (journal vacuum + cache trim).
- **One-Click Maintenance** — checklist-driven full checkup with single confirmation dialog.
- **Bottom status bar** — firewall status, AUR helper, last refresh time.

---

## Security design

- **The whole app never runs as root.** Every privileged action goes through
  `pkexec` for that one specific command — never the full GUI process.
- **Every destructive action requires an explicit confirmation dialog** before
  running. Nothing is deleted silently.
- **pacman cache cleanup uses `paccache -r -k1`** (keeps the latest version of
  each package) so `pacman -U` rollback still works.
- **Ping host input is fully validated** against a strict regex (IP/hostname
  only) — shell injection characters are rejected before reaching subprocess.
- **`/tmp` cleanup** only accepts paths that start with `/tmp/` and contain no
  `..` components — no directory traversal possible.

---

## v2.0 — Major Release

### Renamed from ZarchCare to ZarchCare
- Clear, descriptive name expressing its purpose and ZarchBlack distribution: **Zarch**Black **Care**
- Updated all branding, window titles, desktop entries, and polkit policies

### New Features
- **System Report Export** — Generate comprehensive system health reports (HTML/JSON)
- **Settings Page** — Configure auto-refresh intervals, theme selection, notification preferences, log levels
- **Service Manager** — View and manage systemd services (start/stop/restart/enable/disable)
- **Enhanced Log Viewer** — Filter by priority, search, export logs

### Visual Improvements
- Health score radial gauge on dashboard
- Animated progress bars on stat cards
- Better color coding for critical thresholds
- Improved typography hierarchy
- Hover effects on cards
- Skeleton loaders for pages
- Smooth transitions between pages
- High contrast mode option
- Better status pills with icons

### Bug Fixes (inherited from v1.1)
All 16 documented bugs fixed:
| Bug ID | Severity | Summary |
|--------|----------|---------|
| BUG-C01 | 🔴 Critical | Memory leak: completed worker threads were never removed from `_workers` lists |
| BUG-C02 | 🔴 Critical | Command injection in Ping: user input was passed unsanitised to subprocess |
| BUG-C03 | 🔴 Critical | Race condition: could trigger a second privileged sequence while the first was still running |
| BUG-C04 | 🔴 Critical | Button re-enabled immediately after `runner.run()` (async call), not after completion |
| BUG-H01 | 🟠 Hidden | `/proc/meminfo` parsing crashed on lines without a colon (used `split(":")`) |
| BUG-H02 | 🟠 Hidden | Duplicate background worker spawned for `build_dashboard_snapshot` at startup |
| BUG-H03 | 🟠 Hidden | `paccache` not in `REQUIRED_TOOLS`; missing it caused a cryptic crash at runtime |
| BUG-H04 | 🟠 Hidden | `/tmp` paths passed to `rm -rf` without path validation (directory traversal risk) |
| BUG-H05 | 🟠 Hidden | No logging system — errors silently swallowed |
| BUG-H06 | 🟠 Hidden | Multi-GPU detection only returned first vendor (Intel iGPU ignored on hybrid laptops) |
| BUG-H07 | 🟠 Hidden | No `failed` handler in status bar worker — pills stuck on "checking…" on error |
| BUG-P03 | 🟡 Performance | All 11 pages eagerly initialised at startup (including heavy scans) |
| BUG-P04 | 🟡 Performance | `filter_uninstalled()` called `pacman -Qi` once per package (N calls instead of 1) |
| BUG-Q01 | 🔵 Quality | `import os` inside a function body instead of at module level |
| BUG-Q05 | 🔵 Quality | No error feedback when `pkexec` update step exits non-zero |
| BUG-Q06 | 🔵 Quality | Logo pixmap used `FastTransformation` (pixelated scaling) |

---

## Project structure

```
zarchcare/
├── main.py                            # Entry point + REQUIRED_TOOLS check
├── core/
│   ├── logger.py                       # Centralised logging (~/.local/share/zarchcare/)
│   ├── privilege.py                    # Safe root elevation via pkexec
│   ├── troubleshoot.py                 # Diagnostics + logs + network
│   ├── hardware.py                     # Hardware detection (multi-GPU fixed)
│   ├── drivers.py                      # Driver suggestion/installation (BUG-P04 fixed)
│   ├── maintenance.py                  # Update/cleanup (BUG-H03, BUG-H04 fixed)
│   ├── dashboard.py                    # Live snapshot + Health Score (BUG-H01 fixed)
│   ├── disk_analyzer.py                # Filesystem/home/cache breakdown
│   └── broken_packages.py              # pacman -Qk integrity scan
├── ui/
│   ├── theme.py                        # Visual theme (QSS)
│   ├── workers.py                      # Background thread (done signal — BUG-C01 fixed)
│   ├── worker_mixin.py                 # Auto-cleanup mixin for _workers lists
│   ├── widgets_common.py               # StatCard / Pill / HealthBadge
│   ├── privileged_sequence.py          # Chains pkexec steps (BUG-C03, BUG-C04 fixed)
│   ├── icons.py                        # App icon + logo (BUG-Q06 fixed)
│   ├── main_window.py                  # Sidebar + pages + status bar (BUG-H02, H07 fixed)
│   └── pages/
│       ├── page_dashboard.py
│       ├── page_health_score.py        # Lazy init (BUG-P03 fixed)
│       ├── page_network.py             # Ping validation (BUG-C02 fixed)
│       ├── page_hardware.py            # Multi-GPU suggestion (BUG-H06 fixed)
│       ├── page_clean.py               # paccache check (BUG-H03 fixed)
│       ├── page_update.py              # Error feedback (BUG-Q05 fixed)
│       ├── page_disk_analyzer.py       # Lazy init (BUG-P03 fixed)
│       ├── page_broken_packages.py
│       ├── page_pacnew.py              # Lazy init (BUG-P03 fixed)
│       ├── page_quick_clean.py         # Button timing (BUG-C04 fixed)
│       ├── page_one_click.py           # Button timing + paccache (BUG-C04, H03 fixed)
│       ├── page_settings.py            # ✨ NEW: Settings page
│       └── page_services.py            # ✨ NEW: Service manager page
├── tests/
│   ├── __init__.py
│   ├── test_core.py                    # 73 unit tests (all passing)
│   └── test_integration.py             # 79 integration tests (all passing)
└── resources/
    ├── org.zarchblack.zarchcare.policy  # Polkit policy (ZarchBlack branding)
    └── zarchcare.desktop                # Desktop menu entry
```

---

## Install & run (development)

```bash
# Prerequisites (ZarchBlack / Arch Linux)
sudo pacman -S pyside6 polkit pciutils pacman-contrib

# Run the app
cd zarchcare
python3 main.py

# Run the unit tests (no Arch system required)
python3 -m pytest tests/ -v
```

> **Note:** `paccache` comes from the `pacman-contrib` package. The app will
> warn you at startup if it is missing, and will gracefully skip the cache-clean
> step in Quick Clean and One-Click Maintenance.

---

## Logging

The app writes logs to:

```
~/.local/share/zarchcare/zarchcare.log
```

The log file is automatically created on first run. It rotates at 2 MB and
keeps 2 backup files. Log level is `DEBUG` in the file, `WARNING` on stderr.

---

## Testing status

| Test type | Count | Status |
|-----------|-------|--------|
| Syntax check (py_compile) | 27 files | ✅ All clean |
| Unit tests (pytest) | 73 tests | ✅ 73/73 passed |
| Integration tests (pytest) | 79 tests | ✅ 79/79 passed |
| Manual on real ZarchBlack | — | ⏳ Your turn |

### Manual test checklist (real ZarchBlack system)

- [ ] Open the app — Dashboard tiles load within ~2 seconds
- [ ] Refresh Dashboard several times — no UI freeze, no growing memory
- [ ] Navigate to Health Score — scan starts automatically on first visit only
- [ ] Navigate to Disk Analyzer — scan starts automatically on first visit only
- [ ] Network → Ping with `8.8.8.8` — works
- [ ] Network → Ping with `; rm -rf /` — rejected with error message (not executed)
- [ ] Quick Clean → double-click the button fast — button is disabled during run
- [ ] One-Click Maintenance — button stays disabled until the LAST step finishes
- [ ] Hardware page on Intel+NVIDIA laptop — both vendors + both package sets shown
- [ ] Check `~/.local/share/zarchcare/zarchcare.log` — populated with debug info
- [ ] If `pacman-contrib` not installed — warning shown, cache steps skipped gracefully
- [ ] Settings page — theme switching works
- [ ] Service manager — can start/stop/restart services
- [ ] System report export — generates HTML/JSON reports

---

## Packaging (PKGBUILD)

```bash
package() {
   install -Dm755 main.py "$pkgdir/usr/share/zarchcare/main.py"
   cp -r core ui resources "$pkgdir/usr/share/zarchcare/"
   install -Dm644 resources/zarchcare.desktop \
       "$pkgdir/usr/share/applications/zarchcare.desktop"
   install -Dm644 resources/org.zarchblack.zarchcare.policy \
       "$pkgdir/usr/share/polkit-1/actions/org.zarchcare.policy"

   for size in 16 24 32 48 64 128 256 512; do
       install -Dm644 "resources/icons/zarchcare-${size}.png" \
           "$pkgdir/usr/share/icons/hicolor/${size}x${size}/apps/zarchcare.png"
   done
   install -Dm644 resources/icons/zarchcare.svg \
       "$pkgdir/usr/share/icons/hicolor/scalable/apps/zarchcare.svg"
}
depends=('pyside6' 'polkit' 'pacman' 'pciutils' 'systemd' 'pacman-contrib')
```