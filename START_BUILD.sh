#!/bin/bash
# افتح هذا الملف في terminal وشغّله بـ sudo
cd /mnt/build/project-zarch-iso/zarchblack_iso
sudo bash scripts/build-iso.sh 2>&1 | tee /tmp/zarchblack-build.log
echo "=== اكتمل البناء — السجل في /tmp/zarchblack-build.log ==="
