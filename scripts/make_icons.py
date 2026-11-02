"""Generuje assets/icon.png, icon.ico (Windows) i icon.icns (macOS) z ikony rysowanej w Qt.

    python scripts/make_icons.py      (wymaga: pip install pillow)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from easycoder.gui.theme import paint_icon  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)  # noqa: F841 – potrzebne do QPixmap
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    big = assets / "icon_1024.png"
    paint_icon(1024).save(str(big))
    img = Image.open(big).convert("RGBA")
    img.resize((512, 512), Image.LANCZOS).save(assets / "icon.png")
    img.save(assets / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                         (128, 128), (256, 256)])
    img.save(assets / "icon.icns")
    big.unlink()
    print("Zapisano ikony w", assets)


if __name__ == "__main__":
    main()
