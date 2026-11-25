"""
ui/icons.py
===========
Loads the ZarchBlack logo (provided as resources/icons/zarchcare.svg, with
pre-rendered PNGs at several sizes) as a QIcon / QPixmap, resolved relative
to this file so it works whether the app is run from source or installed.

Fixes applied:
  BUG-Q06 — logo_pixmap() now uses Qt.SmoothTransformation when scaling so
             the sidebar logo is sharp instead of pixelated (FastTransformation
             was the implicit default before).
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

_ICONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resources", "icons",
)

_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)


def _png_path(size: int) -> str:
    return os.path.join(_ICONS_DIR, f"zarchcare-{size}.png")


def app_icon() -> QIcon:
    """
    Multi-resolution QIcon for the window/taskbar, built from all available
    pre-rendered sizes so Qt can pick the sharpest one.
    Falls back to the SVG if no PNGs are present.
    """
    icon = QIcon()
    for size in _SIZES:
        path = _png_path(size)
        if os.path.exists(path):
            icon.addFile(path)
    if icon.isNull():
        svg_path = os.path.join(_ICONS_DIR, "zarchcare.svg")
        if os.path.exists(svg_path):
            icon = QIcon(svg_path)
    return icon


def logo_pixmap(size: int = 48) -> QPixmap:
    """
    A single-size pixmap for embedding the logo directly in the UI
    (e.g. the sidebar header).

    BUG-Q06 fix: uses Qt.SmoothTransformation for crisp scaling instead of
    the default FastTransformation which produces blocky/pixelated results.
    """
    closest = min(_SIZES, key=lambda s: abs(s - size))
    path = _png_path(closest)
    if not os.path.exists(path):
        return QPixmap()
    pix = QPixmap(path)
    if pix.width() != size:
        pix = pix.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,   # BUG-Q06 fix
        )
    return pix
