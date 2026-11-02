# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller – jeden plik spec dla Windows i macOS.

Windows: dist/EasyCoder/EasyCoder.exe (jeden plik .exe) + dist/EasyCoder/bin/ffmpeg.exe, ffprobe.exe
         FFmpeg leży obok .exe, a nie w środku – inaczej każde uruchomienie
         rozpakowywałoby ~200 MB do folderu tymczasowego.
macOS:   dist/EasyCoder.app z FFmpeg w Contents/Resources/bin

Uruchomienie:  pyinstaller EasyCoder.spec --noconfirm
Architektura macOS: zmienna EC_TARGET_ARCH = arm64 | x86_64 | universal2 (domyślnie bieżąca).
"""
import os
import sys
from pathlib import Path

from easycoder import __version__

ROOT = Path(SPECPATH)
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
BIN = ROOT / "bin"

datas = [(str(ROOT / "assets" / "icon.png"), "assets")]
if IS_MAC:
    # W .app FFmpeg ląduje w Contents/Resources/bin
    for tool in ("ffmpeg", "ffprobe"):
        if (BIN / tool).exists():
            datas.append((str(BIN / tool), "bin"))

excludes = ["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
            "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts",
            "PySide6.QtPdf", "PySide6.QtDataVisualization", "tkinter", "unittest"]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    datas=datas,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

if IS_WIN:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="EasyCoder",
        icon=str(ROOT / "assets" / "icon.ico"),
        console=False,
        upx=False,
        version=None,
    )
else:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="EasyCoder",
        console=False,
        upx=False,
        target_arch=os.environ.get("EC_TARGET_ARCH") or None,
        codesign_identity=os.environ.get("EC_CODESIGN_IDENTITY") or None,
        entitlements_file=None,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="EasyCoder", upx=False)
    app = BUNDLE(
        coll,
        name="EasyCoder.app",
        icon=str(ROOT / "assets" / "icon.icns"),
        bundle_identifier="pl.easycoder.app",
        version=__version__,
        info_plist={
            "CFBundleName": "EasyCoder",
            "CFBundleDisplayName": "EASY CODER",
            "CFBundleShortVersionString": __version__,
            "NSHighResolutionCapable": True,          # Retina
            "LSMinimumSystemVersion": "12.0",
            "NSRequiresAquaSystemAppearance": False,
            # Przeciąganie plików na ikonę w Docku / "Otwórz za pomocą"
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Media",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": ["public.movie", "public.audio", "public.audiovisual-content"],
            }],
        },
    )
