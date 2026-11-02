#!/usr/bin/env bash
# Budowa EASY CODER dla macOS.
#   ./scripts/build_macos.sh [arm64|x86_64|universal2]
# Wynik: dist/EasyCoder.app i dist/EasyCoder-macOS-<arch>.dmg
#
# universal2 wymaga Pythona universal2 (instalator z python.org) – wtedy PySide6
# i PyInstaller budują jedną paczkę dla M1–M4 i Intela. Na GitHub Actions
# budujemy osobno arm64 (macos-14) i x86_64 (macos-15-intel).
#
# Podpis i notaryzacja (opcjonalnie, z kontem Apple Developer):
#   EC_CODESIGN_IDENTITY="Developer ID Application: Imię Nazwisko (TEAMID)"
#   EC_NOTARY_PROFILE="easycoder"   (xcrun notarytool store-credentials easycoder ...)
set -euo pipefail
cd "$(dirname "$0")/.."

ARCH="${1:-$(uname -m)}"
PY="${PYTHON:-python3}"
VERSION=$($PY -c "import easycoder; print(easycoder.__version__)")
echo "== EASY CODER $VERSION (macOS $ARCH) =="

# 1. FFmpeg dla właściwej architektury
rm -f bin/ffmpeg bin/ffprobe
$PY scripts/fetch_ffmpeg.py --arch "$ARCH"
file bin/ffmpeg

# 2. Ikony
[ -f assets/icon.icns ] || $PY scripts/make_icons.py

# 3. Testy
QT_QPA_PLATFORM=offscreen $PY -m pytest -q

# 4. PyInstaller -> dist/EasyCoder.app
export EC_TARGET_ARCH="$ARCH"
$PY -m PyInstaller EasyCoder.spec --noconfirm --clean
APP="dist/EasyCoder.app"
chmod +x "$APP/Contents/Resources/bin/ffmpeg" "$APP/Contents/Resources/bin/ffprobe"

# 5. Podpis: Developer ID (z hardened runtime) albo ad-hoc
if [ -n "${EC_CODESIGN_IDENTITY:-}" ]; then
  codesign --force --options runtime --timestamp -s "$EC_CODESIGN_IDENTITY" \
    "$APP/Contents/Resources/bin/ffmpeg" "$APP/Contents/Resources/bin/ffprobe"
  codesign --force --deep --options runtime --timestamp -s "$EC_CODESIGN_IDENTITY" "$APP"
else
  codesign --force --deep -s - "$APP"
fi

# 6. DMG z linkiem do /Applications
DMG="dist/EasyCoder-macOS-$ARCH.dmg"
STAGE="dist/dmg"
rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "EASY CODER" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"

# 7. Notaryzacja (opcjonalnie)
if [ -n "${EC_CODESIGN_IDENTITY:-}" ] && [ -n "${EC_NOTARY_PROFILE:-}" ]; then
  codesign -s "$EC_CODESIGN_IDENTITY" --timestamp "$DMG"
  xcrun notarytool submit "$DMG" --keychain-profile "$EC_NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
fi
echo "Gotowe: $DMG"
