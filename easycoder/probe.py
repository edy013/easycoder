"""Odczyt parametrów pliku przez ffprobe."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .platform_utils import subprocess_flags

HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".mxf", ".webm", ".m4v", ".mts", ".m2ts",
              ".ts", ".mpg", ".mpeg", ".wmv", ".flv", ".3gp", ".dv", ".lrf", ".insv"}
AUDIO_EXTS = {".wav", ".aif", ".aiff", ".flac", ".mp3", ".aac", ".m4a", ".ogg", ".oga",
              ".opus", ".wma", ".alac", ".caf", ".ac3", ".wv", ".ape", ".mka"}


@dataclass
class MediaInfo:
    path: Path
    size_bytes: int = 0
    duration: float = 0.0
    format_name: str = ""
    # wideo
    has_video: bool = False
    width: int = 0
    height: int = 0
    fps: float = 0.0
    vcodec: str = ""
    pix_fmt: str = ""
    bit_depth: int = 8
    hdr: bool = False
    # audio
    has_audio: bool = False
    acodec: str = ""
    sample_rate: int = 0
    channels: int = 0
    audio_kbps: float = 0.0
    has_cover: bool = False
    tags: dict = field(default_factory=dict)
    error: str = ""

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)

    @property
    def is_vertical(self) -> bool:
        return self.height > self.width > 0


def _fps(rate: str) -> float:
    try:
        num, _, den = rate.partition("/")
        n, d = float(num), float(den or 1)
        return n / d if d else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def _rotation(stream: dict) -> int:
    rot = stream.get("tags", {}).get("rotate")
    if rot is not None:
        try:
            return int(float(rot))
        except ValueError:
            pass
    for sd in stream.get("side_data_list", []) or []:
        if "rotation" in sd:
            try:
                return int(float(sd["rotation"]))
            except (TypeError, ValueError):
                pass
    return 0


def _bit_depth(stream: dict) -> int:
    raw = stream.get("bits_per_raw_sample")
    if raw and str(raw).isdigit():
        return int(raw)
    pf = stream.get("pix_fmt", "")
    for depth in (16, 12, 10):
        if f"{depth}le" in pf or f"{depth}be" in pf:
            return depth
    return 8


def parse_probe_json(data: dict, path: Path) -> MediaInfo:
    """Zamienia JSON z ffprobe na MediaInfo (osobno, żeby dało się testować)."""
    info = MediaInfo(path=Path(path))
    fmt = data.get("format", {}) or {}
    info.format_name = (fmt.get("format_name") or "").split(",")[0]
    try:
        info.size_bytes = int(fmt.get("size") or 0)
    except ValueError:
        info.size_bytes = 0
    try:
        info.duration = float(fmt.get("duration") or 0)
    except ValueError:
        info.duration = 0.0
    info.tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}

    for s in data.get("streams", []) or []:
        ctype = s.get("codec_type")
        disp = s.get("disposition", {}) or {}
        if ctype == "video" and disp.get("attached_pic"):
            info.has_cover = True
            continue
        if ctype == "video" and not info.has_video:
            info.has_video = True
            w, h = int(s.get("width") or 0), int(s.get("height") or 0)
            if abs(_rotation(s)) % 180 == 90:
                w, h = h, w
            info.width, info.height = w, h
            info.fps = _fps(s.get("avg_frame_rate") or "") or _fps(s.get("r_frame_rate") or "")
            info.vcodec = s.get("codec_name", "")
            info.pix_fmt = s.get("pix_fmt", "")
            info.bit_depth = _bit_depth(s)
            info.hdr = (s.get("color_transfer") or "") in HDR_TRANSFERS
            if not info.duration:
                try:
                    info.duration = float(s.get("duration") or 0)
                except ValueError:
                    pass
        elif ctype == "audio" and not info.has_audio:
            info.has_audio = True
            info.acodec = s.get("codec_name", "")
            info.sample_rate = int(s.get("sample_rate") or 0)
            info.channels = int(s.get("channels") or 0)
            try:
                info.audio_kbps = int(s.get("bit_rate") or 0) / 1000
            except ValueError:
                info.audio_kbps = 0
            if not info.duration:
                try:
                    info.duration = float(s.get("duration") or 0)
                except ValueError:
                    pass
    if not info.size_bytes and info.path.exists():
        info.size_bytes = info.path.stat().st_size
    return info


def probe(path: Path, ffprobe: Path, timeout: float = 30) -> MediaInfo:
    """Uruchamia ffprobe i zwraca MediaInfo (pole `error` przy problemie)."""
    cmd = [str(ffprobe), "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", str(path)]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=timeout, **subprocess_flags())
    except (OSError, subprocess.TimeoutExpired) as e:
        return MediaInfo(path=Path(path), error=str(e))
    if res.returncode != 0:
        err = res.stderr.decode("utf-8", "replace").strip()
        info = MediaInfo(path=Path(path), error=err or "ffprobe zakończył się błędem")
        if Path(path).exists():
            info.size_bytes = Path(path).stat().st_size
        return info
    data = json.loads(res.stdout.decode("utf-8", "replace") or "{}")
    return parse_probe_json(data, Path(path))


def collect_media_files(paths: list[Path], kinds: set[str]) -> list[Path]:
    """Rozwija foldery (rekurencyjnie) i filtruje po rozszerzeniach.

    `kinds` – {"video"} lub {"video", "audio"}.
    """
    exts: set[str] = set()
    if "video" in kinds:
        exts |= VIDEO_EXTS
    if "audio" in kinds:
        exts |= AUDIO_EXTS
    out: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            out += sorted(f for f in p.rglob("*")
                          if f.is_file() and f.suffix.lower() in exts and not f.name.startswith("."))
        elif p.is_file():
            out.append(p)
    return out
