#!/bin/bash
# ============================================================================
# ZarchCare Installation Script
# ============================================================================
# هذا السكربت يقوم بحذف ZarchGuard وتثبيت ZarchCare بشكل صحيح
# يجب تشغيله بصلاحيات جذر (sudo)
# ============================================================================

set -e  # إيقاف السكربت عند أي خطأ

# ألوان للرسائل
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  ZarchCare Installation Script"
echo "=========================================="
echo ""

# المصادر
PROJECT_DIR="/mnt/build/zarch-care-toolkit"
INSTALL_DIR="/usr/share/zarchcare"
DESKTOP_DIR="/usr/share/applications"
POLICY_DIR="/usr/share/polkit-1/actions"
ICON_BASE="/usr/share/icons/hicolor"
DESKTOP_FILE="zarchcare.desktop"
POLICY_FILE="org.zarchcare.policy"

# ─── 1. حذف ZarchGuard ──────────────────────────────────────────────────────
echo -e "${YELLOW}Step 1: Removing ZarchGuard...${NC}"

remove_if_exists() {
    local file="$1"
    if [ -f "$file" ]; then
        sudo rm -f "$file"
        echo "  ✓ Removed: $file"
    else
        echo "  - Not found: $file (ok)"
    fi
}

remove_if_exists /usr/bin/zarchguard
remove_if_exists "$DESKTOP_DIR/zarchguard.desktop"
remove_if_exists "$POLICY_DIR/org.zarchblack.zarchguard.policy"

echo ""

# ─── 2. إنشاء هيكل التثبيت ─────────────────────────────────────────────────
echo -e "${YELLOW}Step 2: Creating installation directories...${NC}"

sudo mkdir -p "$INSTALL_DIR"
sudo mkdir -p "$DESKTOP_DIR"
sudo mkdir -p "$POLICY_DIR"
sudo mkdir -p "$ICON_BASE/scalable/apps"

for size in 16 24 32 48 64 128 256 512; do
    sudo mkdir -p "$ICON_BASE/${size}x${size}/apps"
done

echo "  ✓ Directories created"

# ─── 3. نسخ الملفات الأساسية ────────────────────────────────────────────────
echo -e "${YELLOW}Step 3: Installing application files...${NC}"

# نسخ main.py
sudo install -Dm755 "$PROJECT_DIR/main.py" "$INSTALL_DIR/main.py"
echo "  ✓ Installed main.py"

# نسخ الوحدات
sudo cp -r "$PROJECT_DIR/core" "$INSTALL_DIR/"
echo "  ✓ Installed core module"

sudo cp -r "$PROJECT_DIR/ui" "$INSTALL_DIR/"
echo "  ✓ Installed ui module"

sudo mkdir -p "$INSTALL_DIR/resources"
sudo cp -r "$PROJECT_DIR/resources/icons" "$INSTALL_DIR/resources/"
echo "  ✓ Installed icons"

# ─── 4. إنشاء ثنائي التنفيذ ─────────────────────────────────────────────────
echo -e "${YELLOW}Step 4: Creating executable wrapper...${NC}"

cat | sudo tee /usr/bin/zarchcare > /dev/null << 'WRAPPER'
#!/bin/bash
# ZarchCare - System Health Guardian
# ZarchCare v2.0
# ZarchBlack System Care

APP_DIR="/usr/share/zarchcare"
cd "$APP_DIR" || exit 1
exec python3 "$APP_DIR/main.py" "$@"
WRAPPER

sudo chmod +x /usr/bin/zarchcare
echo "  ✓ Created /usr/bin/zarchcare"

# ─── 5. نسخ الوثائق والوثائق ───────────────────────────────────────────────────
echo -e "${YELLOW}Step 5: Installing desktop and policy files...${NC}"

sudo install -Dm644 "$PROJECT_DIR/resources/$DESKTOP_FILE" "$DESKTOP_DIR/$DESKTOP_FILE"
echo "  ✓ Installed desktop entry"

sudo install -Dm644 "$PROJECT_DIR/resources/org.zarchblack.zarchcare.policy" "$POLICY_DIR/$POLICY_FILE"
echo "  ✓ Installed polkit policy"

# ─── 6. نسخ الأيقونات ───────────────────────────────────────────────────────────
echo -e "${YELLOW}Step 6: Installing application icons...${NC}"

for size in 16 24 32 48 64 128 256 512; do
    src="$PROJECT_DIR/resources/icons/zarchcare-${size}.png"
    dst="$ICON_BASE/${size}x${size}/apps/zarchcare.png"
    if [ -f "$src" ]; then
        sudo cp "$src" "$dst"
        echo "  ✓ Installed ${size}x${size} icon"
    fi
done

sudo cp "$PROJECT_DIR/resources/icons/zarchcare.svg" "$ICON_BASE/scalable/apps/zarchcare.svg"
echo "  ✓ Installed SVG icon"

# ─── 7. تحديث كاش الأيقونات ─────────────────────────────────────────────────────
echo -e "${YELLOW}Step 7: Updating icon cache...${NC}"

if command -v gtk-update-icon-cache &> /dev/null; then
    sudo gtk-update-icon-cache "$ICON_BASE" 2>/dev/null || echo "  - Icon cache update skipped (non-critical)"
else
    echo "  - gtk-update-icon-cache not found (ok)"
fi

# ─── 8. تنظيف الملفات القديمة ───────────────────────────────────────────────────
echo -e "${YELLOW}Step 8: Cleaning up temporary files...${NC}"

sudo rm -rf /usr/share/zarchcare/__pycache__ 2>/dev/null || true
echo "  ✓ Cleanup complete"

# ─── الخلاصة ─────────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo -e "${GREEN}  Installation Complete!${NC}"
echo "=========================================="
echo ""
echo "You can now:"
echo "  • Launch ZarchCare from the application menu"
echo "  • Or run: zarchcare"
echo ""
echo "Log file location: ~/.local/share/zarchcare/zarchcare.log"
echo ""