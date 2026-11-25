#!/usr/bin/env bash
set -e

# 1. Locales
locale-gen

# 2. Keyring
pacman-key --init
pacman-key --populate archlinux chaotic cachyos blackarch zarchblack

# 3. Create autologin group and liveuser
groupadd -f autologin
if ! id "liveuser" &>/dev/null; then
    useradd -m -g users -G wheel,video,audio,storage,autologin -s /bin/zsh liveuser
fi
passwd -d liveuser

# 4. Copy skel to liveuser
cp -rT /etc/skel /home/liveuser/

# 5. Standard Directories
mkdir -p /home/liveuser/{Desktop,Documents,Downloads,Music,Pictures,Videos}

# 6. Fix permissions
chown -R liveuser:users /home/liveuser/

# 7. sudoers for liveuser (livecd only - no password)
echo "liveuser ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/liveuser
chmod 440 /etc/sudoers.d/liveuser

# 8. Fix GRUB menuentry name — show ZarchBlack only
sed -i \
  -e 's/OS="${GRUB_DISTRIBUTOR} Linux"/OS="${GRUB_DISTRIBUTOR}"/' \
  -e 's|title="$(gettext_printf "%s, with Linux %s (booster initramfs)" "${os}" "${version}")"|title="$(gettext_printf "%s" "${os}")"|' \
  -e 's|title="$(gettext_printf "%s, with Linux %s (fallback initramfs)" "${os}" "${version}")"|title="$(gettext_printf "%s (fallback)" "${os}")"|' \
  -e 's|title="$(gettext_printf "%s, with Linux %s (recovery mode)" "${os}" "${version}")"|title="$(gettext_printf "%s (recovery)" "${os}")"|' \
  -e 's|title="$(gettext_printf "%s, with Linux %s" "${os}" "${version}")"|title="$(gettext_printf "%s" "${os}")"|' \
  /etc/grub.d/10_linux

# 9. Override Calamares Desktop Shortcut
cp /etc/calamares/calamares.desktop /usr/share/applications/calamares.desktop

# 10. Disable conflicting network services
systemctl disable systemd-networkd.service systemd-networkd-wait-online.service || true

# 11. Enable System Services Natively
systemctl enable NetworkManager.service
systemctl enable systemd-resolved.service
systemctl enable sddm.service
systemctl enable bluetooth.service
systemctl enable avahi-daemon.service
systemctl enable systemd-timesyncd.service
systemctl enable fstrim.timer
systemctl enable libvirtd.service || true

# Set default target to GUI
systemctl set-default graphical.target

# 12. Flatpak: Add Flathub remote
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

# 13. Enable Firewalld and fix KDE Connect
systemctl enable firewalld.service || true
firewall-offline-cmd --zone=public --add-service=kdeconnect || true

# 14. Install ZarchCare (System Health Toolkit)
ZARCHCARE_SRC="/opt/zarch-care-toolkit"
ZARCHCARE_DST="/usr/share/zarchcare"

if [ -d "$ZARCHCARE_SRC" ]; then
    install -dm755 "$ZARCHCARE_DST"
    cp -r "$ZARCHCARE_SRC/core" "$ZARCHCARE_DST/"
    cp -r "$ZARCHCARE_SRC/ui" "$ZARCHCARE_DST/"
    cp -r "$ZARCHCARE_SRC/resources" "$ZARCHCARE_DST/"
    install -Dm755 "$ZARCHCARE_SRC/main.py" "$ZARCHCARE_DST/main.py"

    # Executable
    cat > /usr/bin/zarchcare << 'WRAPPER'
#!/bin/bash
cd /usr/share/zarchcare && exec python3 main.py "$@"
WRAPPER
    chmod 755 /usr/bin/zarchcare

    # Desktop entry & icons
    install -Dm644 "$ZARCHCARE_SRC/resources/zarchcare.desktop" \
        /usr/share/applications/zarchcare.desktop
    install -Dm644 "$ZARCHCARE_SRC/resources/org.zarchblack.zarchcare.policy" \
        /usr/share/polkit-1/actions/org.zarchblack.zarchcare.policy
    for size in 16 24 32 48 64 128 256 512; do
        install -Dm644 "$ZARCHCARE_SRC/resources/icons/zarchcare-${size}.png" \
            "/usr/share/icons/hicolor/${size}x${size}/apps/zarchcare.png"
    done
    install -Dm644 "$ZARCHCARE_SRC/resources/icons/zarchcare.svg" \
        /usr/share/icons/hicolor/scalable/apps/zarchcare.svg

    # Clean pyc
    find "$ZARCHCARE_DST" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo "ZarchCare installed successfully."
else
    echo "Warning: ZarchCare source not found at $ZARCHCARE_SRC — skipping."
fi
