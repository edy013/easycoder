"""Pobiera statyczny FFmpeg + ffprobe do folderu bin/ (dla budowy paczki).

Windows: gyan.dev "release essentials" (NVENC, QSV, AMF, x264/x265, SVT-AV1, VP9,
         LAME, Opus, Vorbis, zimg).
macOS:   ffmpeg.martin-riedl.de – osobne buildy arm64 i x86_64 (amd64).

Użycie:
    python scripts/fetch_ffmpeg.py                # system i architektura bieżącej maszyny
    python scripts/fetch_ffmpeg.py --arch arm64   # macOS: arm64 | x86_64 | universal2
Adresy można nadpisać zmiennymi FFMPEG_URL / FFPROBE_URL (zip).
"""
from __future__ import annotations

import argparse
import io
import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"

WIN_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
MAC_URL = "https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/release/{tool}.zip"


def download(url: str) -> bytes:
    print(f"Pobieranie {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "EasyCoder-build"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


def extract(data: bytes, names: list[str], dest: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for member in z.namelist():
            base = member.rsplit("/", 1)[-1]
            if base in names:
                target = dest / base
                with z.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                print(f"  -> {target}")


def fetch_windows() -> None:
    url = os.environ.get("FFMPEG_URL", WIN_URL)
    extract(download(url), ["ffmpeg.exe", "ffprobe.exe"], BIN)


def fetch_mac_arch(arch: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    mac_arch = "amd64" if arch == "x86_64" else "arm64"
    for tool in ("ffmpeg", "ffprobe"):
        env = os.environ.get(f"{tool.upper()}_URL")
        extract(download(env or MAC_URL.format(arch=mac_arch, tool=tool)), [tool], dest)


def fetch_mac(arch: str) -> None:
    if arch == "universal2":
        tmp = BIN / "_tmp"
        fetch_mac_arch("arm64", tmp / "arm64")
        fetch_mac_arch("x86_64", tmp / "x86_64")
        for tool in ("ffmpeg", "ffprobe"):
            subprocess.run(["lipo", "-create", str(tmp / "arm64" / tool),
                            str(tmp / "x86_64" / tool), "-output", str(BIN / tool)], check=True)
        shutil.rmtree(tmp)
    else:
        fetch_mac_arch(arch, BIN)
    # Apple Silicon uruchamia tylko podpisane binarki – podpis ad-hoc wystarczy.
    for tool in ("ffmpeg", "ffprobe"):
        subprocess.run(["xattr", "-c", str(BIN / tool)], check=False)
        subprocess.run(["codesign", "--force", "--sign", "-", str(BIN / tool)], check=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", default=platform.machine(),
                    help="macOS: arm64 | x86_64 | universal2")
    args = ap.parse_args()
    BIN.mkdir(exist_ok=True)
    if sys.platform.startswith("win"):
        fetch_windows()
    elif sys.platform == "darwin":
        fetch_mac(args.arch)
    else:
        print("Na Linuksie użyj ffmpeg z menedżera pakietów (apt install ffmpeg).")
        return 1
    exe = BIN / ("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg")
    subprocess.run([str(exe), "-hide_banner", "-version"], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
