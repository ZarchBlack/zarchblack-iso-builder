# ArchCare — Renaming & Enhancement Plan

## New Name: **ArchCare** (Arch Linux System Care Tool)

**Rationale:**
- "Arch" clearly identifies the target distribution (Arch Linux / ZarchBlack)
- "Care" expresses the purpose: system care, maintenance, health monitoring
- Short, memorable, professional
- Replaces "ZarchCare" which was ambiguous (ZarchBlack + Care)

---

## Files to Update for Renaming

### Core Identity Files
- [ ] `main.py` - App name, version, window title, QApplication name
- [ ] `README.md` - All references, title, documentation
- [ ] `ui/main_window.py` - Window title, sidebar branding, version label
- [ ] `ui/icons.py` - Icon naming if needed
- [ ] `resources/zarchcare.desktop` - Desktop entry name, exec command
- [ ] `resources/org.zarchblack.zarchcare.policy` - Polkit policy name
- [ ] `requirements.txt` - No change needed (dependencies same)

### Core Modules (logging namespace)
- [ ] `core/logger.py` - Logger namespace from "zarchcare" to "archcare"
- [ ] All core modules using `get_logger(__name__)` - auto-updated via namespace change

### UI Modules
- [ ] `ui/theme.py` - No code changes, just verify theme works
- [ ] `ui/widgets_common.py` - No changes needed
- [ ] All page modules - Update any hardcoded "ZarchCare" strings

### Resources
- [ ] Icon files - rename from `zarchcare-*` to `archcare-*` (optional, can keep for compatibility)
- [ ] Desktop file - rename to `archcare.desktop`
- [ ] Policy file - rename to `org.archlinux.archcare.policy`

### Tests
- [ ] Update any test references to old name

---

## Visual Improvements

### 1. Enhanced Dashboard
- [ ] Add animated progress bars on stat cards
- [ ] Improved color coding for critical thresholds
- [ ] Better typography hierarchy
- [ ] Hover effects on cards

### 2. Better Loading States
- [ ] Skeleton loaders for pages
- [ ] Smooth transitions between pages
- [ ] Progress indicators for long operations

### 3. Theme Refinements
- [ ] Consistent accent colors
- [ ] Better focus/selection states
- [ ] Improved scrollbar styling
- [ ] High contrast mode option

### 4. New Visual Components
- [ ] Health score radial gauge
- [ ] System info cards with icons
- [ ] Better status pills with icons

---

## New Features

### 1. System Report Export
- [ ] Generate comprehensive system health report (HTML/PDF/JSON)
- [ ] Include all dashboard metrics, health score, hardware info, issues
- [ ] One-click export button on dashboard

### 2. Settings Page
- [ ] Auto-refresh interval configuration
- [ ] Theme selection (dark/light/high-contrast)
- [ ] Notification preferences
- [ ] Log level configuration

### 3. Service Manager (systemd)
- [ ] View failed/enabled/disabled services
- [ ] Start/stop/restart services (via pkexec)
- [ ] Enable/disable services

### 4. Enhanced Log Viewer
- [ ] Filter by priority
- [ ] Search/filter logs
- [ ] Export logs

### 5. Package Manager Frontend Improvements
- [ ] Show package descriptions
- [ ] Categorize orphans by type
- [ ] Better update details

---

## Implementation Order

1. **Rename** - All references from "ZarchCare" to "ArchCare"
2. **Visual Polish** - Theme improvements, better components
3. **New Features** - System report, settings, service manager
4. **Testing** - Verify all tests still pass
5. **Documentation** - Update README, add user guide

---

## Backward Compatibility

- Keep `zarchcare` as internal logger namespace alias for log continuity
- Desktop file can have both names during transition
- Config/settings stored under new name but can migrate old settings