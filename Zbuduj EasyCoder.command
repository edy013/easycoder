#!/usr/bin/env bash
# EASY CODER – budowa i instalacja na Macu jednym dwuklikiem.
# Wymaga Pythona 3.11+ z python.org (systemowy python3 z macOS jest za stary).
# Wynik: /Applications/EasyCoder.app oraz dist/EasyCoder-macOS-<arch>.dmg
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for c in python3.13 python3.12 python3.11 \
         /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
         /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
         /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1 && \
     "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done

if [ -z "$PY" ]; then
  osascript -e 'display dialog "EASY CODER potrzebuje Pythona 3.11 lub nowszego.\n\nZainstaluj go ze strony python.org (otworzy się za chwilę), a potem uruchom ten plik ponownie." buttons {"OK"} default button 1 with title "EASY CODER"' || true
  open "https://www.python.org/downloads/macos/"
  exit 1
fi
echo "Python: $PY ($("$PY" --version))"

# Środowisko z bibliotekami (PySide6, PyInstaller) – tylko przy pierwszym razie.
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -r requirements.txt -r requirements-build.txt certifi -q
# Python z python.org nie ma certyfikatów SSL, dopóki nie uruchomi się „Install Certificates”.
export SSL_CERT_FILE="$(.venv/bin/python -m certifi)"

ARCH="$(uname -m)"
PYTHON=.venv/bin/python bash scripts/build_macos.sh "$ARCH"

# Instalacja w Programach (bez kwarantanny – aplikacja zbudowana lokalnie).
rm -rf /Applications/EasyCoder.app
ditto dist/EasyCoder.app /Applications/EasyCoder.app
xattr -dr com.apple.quarantine /Applications/EasyCoder.app 2>/dev/null || true
echo
echo "Gotowe: EASY CODER jest w Programach. Paczka do przekazania dalej: dist/EasyCoder-macOS-$ARCH.dmg"
open /Applications/EasyCoder.app
