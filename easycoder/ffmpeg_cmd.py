"""Budowanie komend FFmpeg dla zakładek WIDEO i AUDIO.

Zwraca listy argumentów (bez powłoki) – gotowe dla QProcess. Ścieżki plików
logów 2-pass są względne: proces uruchamiany jest w folderze tymczasowym,
dzięki czemu nie ma problemu z dwukropkiem w "C:\\" w opcjach x265.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import calculator as calc
from .platform_utils import null_output
from .probe import MediaInfo

# --------------------------------------------------------------------------- kodeki wideo

# key: (etykieta, koder, rodzina, sprzętowy, dozwolone kontenery, obsługa trybu rozmiaru)
VIDEO_CODECS: dict[str, dict] = {
    "x264": dict(label="H.264 (libx264) – największa zgodność", encoder="libx264",
                 family="h264", hw=False, containers=["mp4", "mov", "mkv"], sized=True),
    "x265": dict(label="H.265 / HEVC (libx265) – mniejsze pliki", encoder="libx265",
                 family="hevc", hw=False, containers=["mp4", "mov", "mkv"], sized=True),
    "svtav1": dict(label="AV1 (SVT-AV1) – najlepsza kompresja, wolniej", encoder="libsvtav1",
                   family="av1", hw=False, containers=["mp4", "mkv", "webm"], sized=True),
    "vp9": dict(label="VP9 (libvpx) – do WebM", encoder="libvpx-vp9",
                family="vp9", hw=False, containers=["webm", "mkv", "mp4"], sized=True),
    "prores_422": dict(label="ProRes 422 – montaż", encoder="prores_ks", family="prores",
                       hw=False, containers=["mov", "mkv"], sized=False, profile="2"),
    "prores_hq": dict(label="ProRes 422 HQ – montaż", encoder="prores_ks", family="prores",
                      hw=False, containers=["mov", "mkv"], sized=False, profile="3"),
    "prores_4444": dict(label="ProRes 4444 – montaż", encoder="prores_ks", family="prores",
                        hw=False, containers=["mov", "mkv"], sized=False, profile="4"),
    "dnxhr_hq": dict(label="DNxHR HQ – montaż (8-bit)", encoder="dnxhd", family="dnxhr",
                     hw=False, containers=["mov", "mkv", "mxf"], sized=False, profile="dnxhr_hq"),
    "dnxhr_hqx": dict(label="DNxHR HQX – montaż (10-bit)", encoder="dnxhd", family="dnxhr",
                      hw=False, containers=["mov", "mkv", "mxf"], sized=False, profile="dnxhr_hqx"),
    # --- sprzętowe (pokazywane tylko po wykryciu) ---
    "h264_nvenc": dict(label="H.264 – NVIDIA NVENC", encoder="h264_nvenc", family="h264",
                       hw=True, containers=["mp4", "mov", "mkv"], sized=True),
    "hevc_nvenc": dict(label="H.265 – NVIDIA NVENC", encoder="hevc_nvenc", family="hevc",
                       hw=True, containers=["mp4", "mov", "mkv"], sized=True),
    "av1_nvenc": dict(label="AV1 – NVIDIA NVENC", encoder="av1_nvenc", family="av1",
                      hw=True, containers=["mp4", "mkv", "webm"], sized=True),
    "h264_qsv": dict(label="H.264 – Intel Quick Sync", encoder="h264_qsv", family="h264",
                     hw=True, containers=["mp4", "mov", "mkv"], sized=True),
    "hevc_qsv": dict(label="H.265 – Intel Quick Sync", encoder="hevc_qsv", family="hevc",
                     hw=True, containers=["mp4", "mov", "mkv"], sized=True),
    "av1_qsv": dict(label="AV1 – Intel Quick Sync", encoder="av1_qsv", family="av1",
                    hw=True, containers=["mp4", "mkv", "webm"], sized=True),
    "h264_amf": dict(label="H.264 – AMD AMF", encoder="h264_amf", family="h264",
                     hw=True, containers=["mp4", "mov", "mkv"], sized=True),
    "hevc_amf": dict(label="H.265 – AMD AMF", encoder="hevc_amf", family="hevc",
                     hw=True, containers=["mp4", "mov", "mkv"], sized=True),
    "av1_amf": dict(label="AV1 – AMD AMF", encoder="av1_amf", family="av1",
                    hw=True, containers=["mp4", "mkv", "webm"], sized=True),
    "h264_videotoolbox": dict(label="H.264 – Apple VideoToolbox", encoder="h264_videotoolbox",
                              family="h264", hw=True, containers=["mp4", "mov", "mkv"], sized=True),
    "hevc_videotoolbox": dict(label="H.265 – Apple VideoToolbox", encoder="hevc_videotoolbox",
                              family="hevc", hw=True, containers=["mp4", "mov", "mkv"], sized=True),
    "prores_videotoolbox": dict(label="ProRes 422 – Apple VideoToolbox",
                                encoder="prores_videotoolbox", family="prores", hw=True,
                                containers=["mov"], sized=False, profile="2"),
}

CONTAINERS = ["mp4", "mov", "mkv", "webm", "mxf"]
TWO_PASS_ENCODERS = {"libx264", "libx265", "libvpx-vp9"}

# Dźwięk w wideo: key -> (koder, dozwolone kontenery)
VIDEO_AUDIO_CODECS = {
    "aac": dict(encoder="aac", containers=["mp4", "mov", "mkv"]),
    "opus": dict(encoder="libopus", containers=["webm", "mkv", "mp4"]),
    "pcm": dict(encoder="pcm_s24le", containers=["mov", "mkv", "mxf"]),
    "copy": dict(encoder="copy", containers=["mp4", "mov", "mkv", "webm", "mxf"]),
}

SPEEDS = ["fast", "balanced", "best"]


@dataclass
class VideoSettings:
    mode: str = "size"              # 'size' | 'crf'
    target_mb: float = 25.0
    size_scope: str = "per_file"    # 'per_file' | 'total'
    crf: int = 23
    resolution: str = "auto"        # 'auto','orig','2160','1440',...,'custom'
    custom_w: int = 1280
    custom_h: int = 720
    allow_upscale: bool = False
    fps: str = "orig"               # 'orig','max30','60','50','30','25','24'
    codec: str = "x264"
    speed: str = "balanced"
    ten_bit: bool = False
    container: str = "mp4"
    audio_enabled: bool = True
    audio_codec: str = "aac"
    audio_kbps: int = 128
    audio_mono: bool = False
    trim_start: str = ""
    trim_end: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VideoSettings":
        known = {k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class AudioSettings:
    fmt: str = "mp3"                # mp3,wav,aiff,flac,aac,alac,ogg,opus
    mp3_mode: str = "cbr"           # 'cbr' | 'v0'
    bitrate: int = 320
    bit_depth: str = "16"           # '16','24','32f'
    flac_level: int = 5
    sample_rate: str = "orig"       # 'orig','44100','48000','96000'
    channels: str = "stereo"        # 'stereo' | 'mono'
    loudnorm: str = "off"           # 'off','-14','-16','-23'
    keep_metadata: bool = True
    parallel: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AudioSettings":
        known = {k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__}
        return cls(**known)


AUDIO_FORMATS = {
    "mp3": dict(ext="mp3", lossless=False),
    "wav": dict(ext="wav", lossless=True),
    "aiff": dict(ext="aiff", lossless=True),
    "flac": dict(ext="flac", lossless=True),
    "aac": dict(ext="m4a", lossless=False),
    "alac": dict(ext="m4a", lossless=True),
    "ogg": dict(ext="ogg", lossless=False),
    "opus": dict(ext="opus", lossless=False),
}


# --------------------------------------------------------------------------- pomocnicze

def parse_time(text: str) -> float | None:
    """'90', '1:30', '00:01:30.5' -> sekundy. Puste -> None."""
    text = (text or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        parts = [float(p) for p in text.split(":")]
    except ValueError:
        raise ValueError(f"Nieprawidłowy czas: {text}")
    secs = 0.0
    for p in parts:
        secs = secs * 60 + p
    return secs


def effective_duration(info: MediaInfo, s: VideoSettings) -> float:
    start = parse_time(s.trim_start) or 0.0
    end = parse_time(s.trim_end)
    dur = info.duration
    if end is not None and end > start:
        dur = min(dur, end) if dur else end
    return max(0.0, dur - start)


def validate_video(s: VideoSettings, available: set[str] | None = None) -> list[str]:
    """Lista błędów (po polsku) dla niekompatybilnych ustawień."""
    errs: list[str] = []
    codec = VIDEO_CODECS.get(s.codec)
    if not codec:
        return [f"Nieznany kodek: {s.codec}"]
    if available is not None and codec["encoder"] not in available:
        errs.append(f"Koder {codec['encoder']} nie jest dostępny w tym FFmpeg.")
    if s.container not in codec["containers"]:
        errs.append(f"Kodek {codec['label'].split(' –')[0]} nie pasuje do kontenera "
                    f"{s.container.upper()}. Dozwolone: "
                    f"{', '.join(c.upper() for c in codec['containers'])}.")
    if s.audio_enabled:
        ac = VIDEO_AUDIO_CODECS.get(s.audio_codec)
        if ac and s.container not in ac["containers"]:
            errs.append(f"Dźwięk {s.audio_codec.upper()} nie pasuje do kontenera "
                        f"{s.container.upper()}" +
                        (" – dla WebM wybierz Opus." if s.container == "webm" else "."))
    try:
        st, en = parse_time(s.trim_start), parse_time(s.trim_end)
        if st is not None and en is not None and en <= st:
            errs.append("Czas końca musi być większy niż czas początku.")
    except ValueError as e:
        errs.append(str(e))
    if s.ten_bit and s.codec in ("h264_nvenc", "h264_amf", "h264_videotoolbox", "h264_qsv"):
        errs.append("Ten koder sprzętowy H.264 nie obsługuje 10-bit – wybierz H.265/AV1.")
    return errs


def codec_supports_size(codec_key: str) -> bool:
    return VIDEO_CODECS.get(codec_key, {}).get("sized", False)


@dataclass
class VideoPlan:
    """Wyliczone parametry dla jednego pliku (pokazywane w UI i używane w komendzie)."""
    width: int
    height: int
    fps: float
    fps_changed: bool
    video_kbps: float          # 0 w trybie CRF / kodek montażowy
    audio_kbps: float
    duration: float
    quality: str               # excellent/good/medium/poor
    est_mb: float
    upscale: bool = False
    hint_lower: int | None = None
    tonemap: bool = False
    notes: list[str] = field(default_factory=list)


def _target_fps(info: MediaInfo, s: VideoSettings) -> float:
    src = info.fps or 25.0
    if s.fps == "orig":
        return src
    if s.fps == "max30":   # preset "do podglądu": 30 fps lub oryginalne, jeśli niższe
        return min(30.0, src)
    return float(s.fps)


def plan_video(info: MediaInfo, s: VideoSettings, target_mb: float | None = None) -> VideoPlan:
    """Wylicza rozdzielczość, fps, bitrate i jakość dla pliku."""
    codec = VIDEO_CODECS[s.codec]
    family = codec["family"]
    dur = effective_duration(info, s)
    audio_on = s.audio_enabled and info.has_audio
    if not audio_on:
        a_kbps = 0.0
    elif s.audio_codec == "copy":
        a_kbps = info.audio_kbps or 192.0
    elif s.audio_codec == "pcm":
        a_kbps = (info.sample_rate or 48000) * 24 * (1 if s.audio_mono else 2) / 1000
    else:
        a_kbps = float(s.audio_kbps)
    src_w, src_h = info.width or 1920, info.height or 1080
    fps = _target_fps(info, s)
    sized = s.mode == "size" and codec["sized"]
    target_mb = s.target_mb if target_mb is None else target_mb
    v_kbps = calc.video_bitrate_kbps(target_mb, dur, a_kbps) if sized else 0.0

    upscale = False
    hint = None
    if s.resolution == "auto" and sized:
        ch = calc.auto_resolution(src_w, src_h, fps, v_kbps, family)
        w, h, fps = ch.width, ch.height, ch.fps
    elif s.resolution in ("orig", "auto"):
        w, h = src_w - src_w % 2, src_h - src_h % 2
    elif s.resolution == "custom":
        w, h = calc.fit_custom(src_w, src_h, s.custom_w, s.custom_h, s.allow_upscale)
        upscale = w > src_w or h > src_h
    else:
        short = int(s.resolution)
        w, h = calc.fit_resolution(src_w, src_h, short, s.allow_upscale)
        upscale = s.allow_upscale and calc.is_upscale(src_w, src_h, short)

    fps_changed = info.fps > 0 and abs(fps - info.fps) > 0.01
    if sized:
        quality = calc.quality_level(v_kbps, w, h, fps, family)
        est = target_mb
        if quality == "poor" and s.resolution != "auto":
            hint = calc.suggest_lower(src_w, src_h, min(w, h))
    elif codec["sized"]:
        kb = calc.crf_estimate_kbps(s.crf, w, h, fps, family)
        quality = ("excellent" if s.crf <= 20 else "good" if s.crf <= 25
                   else "medium" if s.crf <= 30 else "poor")
        est = calc.estimate_size_mb(kb, a_kbps, dur)
    else:
        kb = calc.intermediate_kbps(s.codec, w, h, fps)
        quality = "excellent"
        est = calc.estimate_size_mb(kb, a_kbps, dur, overhead=0.0)
    tonemap = info.hdr and not (s.ten_bit and family in ("hevc", "av1", "vp9", "prores"))
    return VideoPlan(w, h, fps, fps_changed, v_kbps, a_kbps, dur, quality, est,
                     upscale=upscale, hint_lower=hint, tonemap=tonemap)


def pixel_format(codec_key: str, ten_bit: bool) -> str | None:
    codec = VIDEO_CODECS[codec_key]
    enc, fam = codec["encoder"], codec["family"]
    if fam == "prores":
        if enc == "prores_videotoolbox":
            return None  # VideoToolbox sam dobiera format
        return "yuva444p10le" if codec.get("profile") == "4" else "yuv422p10le"
    if fam == "dnxhr":
        return "yuv422p10le" if codec.get("profile") == "dnxhr_hqx" else "yuv422p"
    if codec["hw"]:
        if ten_bit:
            return "p010le"
        return "nv12" if ("qsv" in enc or "videotoolbox" in enc) else "yuv420p"
    return "yuv420p10le" if ten_bit else "yuv420p"


TONEMAP_FILTER = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
                  "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv")


def video_filters(info: MediaInfo, plan: VideoPlan, has_zscale: bool = True) -> list[str]:
    vf: list[str] = []
    if plan.tonemap and has_zscale:
        vf.append(TONEMAP_FILTER)
    if (plan.width, plan.height) != (info.width, info.height):
        vf.append(f"scale={plan.width}:{plan.height}:flags=lanczos")
    if plan.fps_changed:
        vf.append(f"fps={plan.fps:g}")
    if vf:
        vf.append("setsar=1")
    return vf


def _speed_args(enc: str, speed: str) -> list[str]:
    i = SPEEDS.index(speed) if speed in SPEEDS else 1
    if enc in ("libx264", "libx265"):
        return ["-preset", ["veryfast", "medium", "slow"][i]]
    if enc == "libsvtav1":
        return ["-preset", ["10", "8", "5"][i]]
    if enc == "libvpx-vp9":
        return ["-deadline", "good", "-cpu-used", ["5", "3", "1"][i], "-row-mt", "1"]
    if enc.endswith("_nvenc"):
        return ["-preset", ["p3", "p5", "p7"][i]]
    if enc.endswith("_qsv"):
        return ["-preset", ["veryfast", "medium", "veryslow"][i]]
    if enc.endswith("_amf"):
        return ["-quality", ["speed", "balanced", "quality"][i]]
    if enc.endswith("_videotoolbox") and i == 0:
        return ["-prio_speed", "1"]
    return []


def _rate_args(enc: str, s: VideoSettings, kbps: float, pass_no: int | None) -> list[str]:
    """Kontrola bitrate'u: 2-pass (programowe), VBR+maxrate (sprzętowe) lub CRF."""
    if s.mode == "size":
        b = f"{int(kbps)}k"
        if enc in TWO_PASS_ENCODERS and pass_no:
            args = ["-b:v", b]
            if enc == "libx265":
                args += ["-x265-params", f"pass={pass_no}:stats=ec2pass.log"]
            else:
                args += ["-pass", str(pass_no), "-passlogfile", "ec2pass"]
            return args
        if enc == "libsvtav1":
            return ["-b:v", b]
        maxrate = f"{int(kbps * 1.5)}k"
        bufsize = f"{int(kbps * 2)}k"
        if enc.endswith("_nvenc"):
            return ["-rc", "vbr", "-multipass", "fullres", "-b:v", b,
                    "-maxrate", maxrate, "-bufsize", bufsize]
        if enc.endswith("_amf"):
            return ["-rc", "vbr_peak", "-b:v", b, "-maxrate", maxrate, "-bufsize", bufsize]
        return ["-b:v", b, "-maxrate", maxrate, "-bufsize", bufsize]
    crf = int(s.crf)
    if enc in ("libx264", "libx265"):
        return ["-crf", str(crf)]
    if enc == "libsvtav1":
        return ["-crf", str(min(63, crf + 8))]  # skala SVT-AV1 jest przesunięta
    if enc == "libvpx-vp9":
        return ["-crf", str(min(63, crf + 8)), "-b:v", "0"]
    if enc.endswith("_nvenc"):
        return ["-rc", "vbr", "-cq", str(crf), "-b:v", "0"]
    if enc.endswith("_qsv"):
        return ["-global_quality", str(crf)]
    if enc.endswith("_amf"):
        return ["-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf), "-qp_b", str(crf)]
    if enc.endswith("_videotoolbox"):
        return ["-q:v", str(max(1, min(100, int(100 - crf * 1.6))))]
    return []


def _audio_args_video(info: MediaInfo, s: VideoSettings) -> list[str]:
    if not s.audio_enabled or not info.has_audio:
        return ["-an"]
    if s.audio_codec == "copy":
        return ["-c:a", "copy"]
    enc = VIDEO_AUDIO_CODECS[s.audio_codec]["encoder"]
    args = ["-c:a", enc]
    if s.audio_codec != "pcm":
        args += ["-b:a", f"{int(s.audio_kbps)}k"]
    if s.audio_mono:
        args += ["-ac", "1"]
    elif info.channels > 2 and s.audio_codec != "pcm":
        args += ["-ac", "2"]
    return args


def _input_args(ffmpeg: str, src: Path, s: VideoSettings) -> list[str]:
    args = [ffmpeg, "-hide_banner", "-nostdin", "-y"]
    start = parse_time(s.trim_start)
    end = parse_time(s.trim_end)
    if start:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", str(src)]
    if end is not None:
        args += ["-t", f"{end - (start or 0):.3f}"]
    return args


def build_video_commands(ffmpeg: str, info: MediaInfo, s: VideoSettings, plan: VideoPlan,
                         out: Path, video_kbps: float | None = None,
                         has_zscale: bool = True) -> list[list[str]]:
    """Lista komend (1 lub 2 przebiegi) dla jednego pliku wideo."""
    codec = VIDEO_CODECS[s.codec]
    enc = codec["encoder"]
    kbps = video_kbps if video_kbps is not None else plan.video_kbps
    sized = s.mode == "size" and codec["sized"]

    common_v = ["-map", "0:v:0", "-c:v", enc]
    if "profile" in codec:
        common_v += ["-profile:v", codec["profile"]]
    pf = pixel_format(s.codec, s.ten_bit)
    vf = video_filters(info, plan, has_zscale)
    if vf:
        common_v += ["-vf", ",".join(vf)]
    if pf:
        common_v += ["-pix_fmt", pf]
    if codec["family"] not in ("prores", "dnxhr"):
        common_v += _speed_args(enc, s.speed)
    if codec["family"] == "hevc" and s.container in ("mp4", "mov"):
        common_v += ["-tag:v", "hvc1"]  # wymagane przez QuickTime / iOS
    if enc == "prores_ks":
        common_v += ["-vendor", "apl0"]
    if plan.tonemap and has_zscale:
        common_v += ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]

    tail = ["-map_metadata", "0", "-map_chapters", "-1"]
    if s.container in ("mp4", "mov"):
        tail += ["-movflags", "+faststart"]
    tail += ["-progress", "pipe:1", "-nostats", str(out)]

    audio_map = ["-map", "0:a:0?"] if (s.audio_enabled and info.has_audio) else []
    base = _input_args(ffmpeg, info.path, s)

    if sized and enc in TWO_PASS_ENCODERS:
        p1 = (base + common_v + _rate_args(enc, s, kbps, 1) + ["-an", "-f", "null"]
              + ["-progress", "pipe:1", "-nostats", null_output()])
        p2 = (base + common_v + _rate_args(enc, s, kbps, 2) + audio_map
              + _audio_args_video(info, s) + tail)
        return [p1, p2]
    rate = _rate_args(enc, s, kbps, None) if codec["family"] not in ("prores", "dnxhr") else []
    return [base + common_v + rate + audio_map + _audio_args_video(info, s) + tail]


# --------------------------------------------------------------------------- audio

def audio_output_ext(s: AudioSettings) -> str:
    return AUDIO_FORMATS[s.fmt]["ext"]


def audio_bits(s: AudioSettings) -> int:
    return {"16": 16, "24": 24, "32f": 32}.get(s.bit_depth, 16)


def audio_out_rate(info: MediaInfo, s: AudioSettings) -> int:
    if s.sample_rate != "orig":
        return int(s.sample_rate)
    return info.sample_rate or 48000


def audio_estimate(info: MediaInfo, s: AudioSettings) -> float:
    ch = 1 if s.channels == "mono" else 2
    rate = audio_out_rate(info, s)
    bits = audio_bits(s)
    if s.fmt == "aiff" and bits == 32:
        bits = 24
    kbps = s.bitrate
    if s.fmt == "mp3" and s.mp3_mode == "v0":
        kbps = 245
    if s.fmt == "opus":
        kbps = min(s.bitrate, 256)
    return calc.audio_estimate_mb(s.fmt, info.duration, rate, ch, bits, kbps)


def build_audio_command(ffmpeg: str, info: MediaInfo, s: AudioSettings, out: Path) -> list[str]:
    """Komenda konwersji audio (także wyciąganie dźwięku z wideo)."""
    args = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", str(info.path), "-map", "0:a:0"]
    cover = (s.keep_metadata and info.has_cover
             and s.fmt in ("mp3", "flac", "aac", "alac"))
    if cover:
        args += ["-map", "0:v:0?", "-c:v", "copy", "-disposition:v:0", "attached_pic"]
    else:
        args += ["-vn"]
    bits = audio_bits(s)
    fmt = s.fmt
    if fmt == "mp3":
        args += ["-c:a", "libmp3lame"]
        args += ["-q:a", "0"] if s.mp3_mode == "v0" else ["-b:a", f"{s.bitrate}k"]
        args += ["-id3v2_version", "3"]
    elif fmt == "wav":
        args += ["-c:a", {16: "pcm_s16le", 24: "pcm_s24le", 32: "pcm_f32le"}[bits]]
    elif fmt == "aiff":
        args += ["-c:a", "pcm_s24be" if bits >= 24 else "pcm_s16be"]
    elif fmt == "flac":
        args += ["-c:a", "flac", "-compression_level", str(int(s.flac_level))]
        args += ["-sample_fmt", "s32", "-bits_per_raw_sample", "24"] if bits >= 24 \
            else ["-sample_fmt", "s16"]
    elif fmt == "aac":
        args += ["-c:a", "aac", "-b:a", f"{s.bitrate}k"]
    elif fmt == "alac":
        args += ["-c:a", "alac", "-sample_fmt", "s32p" if bits >= 24 else "s16p"]
    elif fmt == "ogg":
        args += ["-c:a", "libvorbis", "-b:a", f"{s.bitrate}k"]
    elif fmt == "opus":
        args += ["-c:a", "libopus", "-b:a", f"{min(s.bitrate, 256)}k"]

    af: list[str] = []
    if s.loudnorm != "off":
        af.append(f"loudnorm=I={s.loudnorm}:TP=-1.5:LRA=11")
    if af:
        args += ["-af", ",".join(af)]
    # loudnorm wewnętrznie pracuje w 192 kHz – zawsze ustawiamy częstotliwość jawnie.
    if s.sample_rate != "orig" or s.loudnorm != "off":
        rate = audio_out_rate(info, s)
        if fmt == "opus":
            rate = 48000
        args += ["-ar", str(rate)]
    args += ["-ac", "1" if s.channels == "mono" else "2"]
    if s.keep_metadata:
        args += ["-map_metadata", "0"]
    else:
        args += ["-map_metadata", "-1"]
    if fmt in ("aac", "alac"):
        args += ["-movflags", "+faststart"]
    args += ["-progress", "pipe:1", "-nostats", str(out)]
    return args


def extract_audio_settings_from_video(s: VideoSettings) -> AudioSettings:
    """'Tylko wyciągnij audio z wideo' – sensowne ustawienia startowe zakładki AUDIO."""
    if s.audio_codec == "pcm":
        return AudioSettings(fmt="wav", bit_depth="24")
    return AudioSettings(fmt="aac", bitrate=max(128, s.audio_kbps))
