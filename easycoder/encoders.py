"""Wykrywanie dostępnych koderów (programowych i sprzętowych).

Koder sprzętowy jest "dostępny" dopiero, gdy krótkie testowe kodowanie
zakończy się sukcesem – sama obecność w `ffmpeg -encoders` nie wystarcza
(np. NVENC bez karty NVIDIA).
"""
from __future__ import annotations

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .platform_utils import hw_encoder_candidates, subprocess_flags

SOFTWARE_ENCODERS = ["libx264", "libx265", "libsvtav1", "libvpx-vp9", "prores_ks", "dnxhd",
                     "aac", "libopus", "libmp3lame", "libvorbis", "flac", "alac"]


def list_encoders(ffmpeg: Path) -> set[str]:
    """Nazwy koderów wkompilowanych w FFmpeg."""
    try:
        res = subprocess.run([str(ffmpeg), "-hide_banner", "-encoders"], capture_output=True,
                             timeout=15, **subprocess_flags())
    except (OSError, subprocess.TimeoutExpired):
        return set()
    names = set()
    for line in res.stdout.decode("utf-8", "replace").splitlines():
        m = re.match(r"^\s*[VAS][\w.]{5}\s+(\S+)", line)
        if m:
            names.add(m.group(1))
    return names


def has_filter(ffmpeg: Path, name: str) -> bool:
    try:
        res = subprocess.run([str(ffmpeg), "-hide_banner", "-filters"], capture_output=True,
                             timeout=15, **subprocess_flags())
    except (OSError, subprocess.TimeoutExpired):
        return False
    return re.search(rf"^\s*\S+\s+{re.escape(name)}\s", res.stdout.decode("utf-8", "replace"),
                     re.M) is not None


def test_encoder(ffmpeg: Path, encoder: str, timeout: float = 15) -> bool:
    """Próbne zakodowanie 5 klatek czarnego obrazu 640×360."""
    pix = "nv12" if ("qsv" in encoder or "videotoolbox" in encoder) else "yuv420p"
    if encoder.startswith("prores"):
        pix = "p210le" if "videotoolbox" in encoder else "yuv422p10le"
    cmd = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin",
           "-f", "lavfi", "-i", "color=c=black:s=640x360:r=30:d=0.2",
           "-frames:v", "5", "-pix_fmt", pix, "-c:v", encoder, "-f", "null", "-"]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=timeout, **subprocess_flags())
        return res.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def detect(ffmpeg: Path) -> dict:
    """Pełne wykrycie: {'encoders': [...], 'hw': [...], 'zscale': bool}."""
    compiled = list_encoders(ffmpeg)
    software = [e for e in SOFTWARE_ENCODERS if e in compiled]
    candidates = [e for e in hw_encoder_candidates() if e in compiled]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda e: (e, test_encoder(ffmpeg, e)), candidates))
    hw = [e for e, ok in results if ok]
    return {"encoders": software + hw, "hw": hw, "zscale": has_filter(ffmpeg, "zscale")}
