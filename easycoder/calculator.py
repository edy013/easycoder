"""Kalkulator rozmiaru, bitrate'u, rozdzielczości i przewidywanej jakości.

Czysta logika bez zależności od Qt/FFmpeg – w całości pokryta testami.
"""
from __future__ import annotations

from dataclasses import dataclass

MB = 1024 * 1024
# Narzut kontenera (nagłówki, indeksy, przeplot) – odejmowany od budżetu.
CONTAINER_OVERHEAD = 0.04
# Minimalny sensowny bitrate wideo (kb/s), poniżej którego koder i tak się dławi.
MIN_VIDEO_KBPS = 40

# Drabinka rozdzielczości: klucz -> "krótszy bok" (dla 16:9 to wysokość).
RESOLUTION_LADDER = [2160, 1440, 1080, 720, 540, 480, 360]

# Względna efektywność kodeków (ile bitów potrzeba wobec H.264 dla tej samej jakości).
CODEC_EFFICIENCY = {
    "h264": 1.0,
    "hevc": 0.65,
    "av1": 0.5,
    "vp9": 0.6,
    "prores": 1.0,
    "dnxhr": 1.0,
}

# Progi jakości w bitach na piksel (dla H.264; dla innych kodeków skalowane efektywnością).
QUALITY_THRESHOLDS = [
    (0.10, "excellent"),
    (0.06, "good"),
    (0.035, "medium"),
]
QUALITY_ORDER = ["poor", "medium", "good", "excellent"]


# --------------------------------------------------------------------------- bitrate

def total_bitrate_kbps(size_mb: float, duration_s: float) -> float:
    """Całkowity bitrate (kb/s), który mieści się w `size_mb` przy danym czasie."""
    if duration_s <= 0:
        return 0.0
    return size_mb * 8 * MB / duration_s / 1000.0


def video_bitrate_kbps(size_mb: float, duration_s: float, audio_kbps: float = 0.0,
                       overhead: float = CONTAINER_OVERHEAD) -> float:
    """Bitrate wideo po odjęciu audio i marginesu na narzut kontenera."""
    total = total_bitrate_kbps(size_mb, duration_s) * (1.0 - overhead)
    return max(MIN_VIDEO_KBPS, total - audio_kbps)


def estimate_size_mb(video_kbps: float, audio_kbps: float, duration_s: float,
                     overhead: float = CONTAINER_OVERHEAD) -> float:
    """Szacowany rozmiar pliku (MB) dla zadanych bitrate'ów."""
    if duration_s <= 0:
        return 0.0
    bits = (video_kbps + audio_kbps) * 1000.0 * duration_s
    return bits / 8 / MB / (1.0 - overhead)


def retry_bitrate(current_kbps: float, target_mb: float, actual_mb: float) -> float:
    """Nowy bitrate po przekroczeniu rozmiaru – proporcjonalnie niższy z zapasem 3%."""
    if actual_mb <= 0:
        return current_kbps * 0.9
    return max(MIN_VIDEO_KBPS, current_kbps * (target_mb / actual_mb) * 0.97)


def split_budget(total_mb: float, durations: list[float]) -> list[float]:
    """Rozkład łącznego budżetu na pliki proporcjonalnie do czasu trwania."""
    total_dur = sum(d for d in durations if d > 0)
    if total_dur <= 0:
        n = max(1, len(durations))
        return [total_mb / n] * len(durations)
    return [total_mb * max(d, 0) / total_dur for d in durations]


# --------------------------------------------------------------------------- rozdzielczość

def _even(x: float) -> int:
    """Zaokrąglenie do najbliższej liczby parzystej (min. 2) – wymóg koderów 4:2:0."""
    return max(2, int(round(x / 2.0)) * 2)


def fit_resolution(src_w: int, src_h: int, short_side: int,
                   allow_upscale: bool = False) -> tuple[int, int]:
    """Dopasowuje obraz do ramki "Np" z zachowaniem proporcji.

    Ramka dla 720p to 1280×720 dla materiału poziomego i 720×1280 dla pionowego
    (wtedy "720p" oznacza 720 px szerokości). Materiał o nietypowych proporcjach
    (np. 2.39:1) mieści się w ramce, więc 4K scope → 1080p daje 1920×804.
    """
    if src_w <= 0 or src_h <= 0:
        return (_even(short_side * 16 / 9), _even(short_side))
    long_side = short_side * 16 / 9
    if src_w >= src_h:
        box_w, box_h = long_side, short_side
    else:
        box_w, box_h = short_side, long_side
    scale = min(box_w / src_w, box_h / src_h)
    if scale >= 1.0 and not allow_upscale:
        return (_even(src_w), _even(src_h))
    return (_even(src_w * scale), _even(src_h * scale))


def fit_custom(src_w: int, src_h: int, max_w: int, max_h: int,
               allow_upscale: bool = False) -> tuple[int, int]:
    """Własna rozdzielczość: dopasowanie w ramce W×H z zachowaniem proporcji.

    Jeśli jeden z wymiarów = 0, liczony jest z proporcji.
    """
    if src_w <= 0 or src_h <= 0:
        return (_even(max_w or 2), _even(max_h or 2))
    scales = []
    if max_w > 0:
        scales.append(max_w / src_w)
    if max_h > 0:
        scales.append(max_h / src_h)
    scale = min(scales) if scales else 1.0
    if scale >= 1.0 and not allow_upscale:
        return (_even(src_w), _even(src_h))
    return (_even(src_w * scale), _even(src_h * scale))


def is_upscale(src_w: int, src_h: int, short_side: int) -> bool:
    return min(src_w, src_h) < short_side if src_w > 0 and src_h > 0 else False


def resolution_label(w: int, h: int) -> str:
    """Etykieta "1080p" z rzeczywistych wymiarów (krótszy bok)."""
    return f"{min(w, h)}p" if w and h else "?"


# --------------------------------------------------------------------------- jakość

def bits_per_pixel(video_kbps: float, w: int, h: int, fps: float) -> float:
    if w <= 0 or h <= 0 or fps <= 0:
        return 0.0
    return video_kbps * 1000.0 / (w * h * fps)


def quality_level(video_kbps: float, w: int, h: int, fps: float, family: str = "h264") -> str:
    """Zwraca 'excellent' / 'good' / 'medium' / 'poor'."""
    eff = CODEC_EFFICIENCY.get(family, 1.0)
    bpp = bits_per_pixel(video_kbps, w, h, fps) / eff
    for threshold, label in QUALITY_THRESHOLDS:
        if bpp >= threshold:
            return label
    return "poor"


def quality_at_least(level: str, minimum: str) -> bool:
    return QUALITY_ORDER.index(level) >= QUALITY_ORDER.index(minimum)


@dataclass
class AutoChoice:
    width: int
    height: int
    fps: float
    quality: str
    short_side: int


def auto_resolution(src_w: int, src_h: int, src_fps: float, video_kbps: float,
                    family: str = "h264", min_quality: str = "good") -> AutoChoice:
    """Tryb "Auto": najwyższa rozdzielczość (i ew. 30 fps zamiast 60),
    przy której jakość jest co najmniej `min_quality`.

    Kolejność prób na każdym szczeblu: oryginalne fps, potem 30 fps (gdy > 30).
    Jeśli nic nie spełnia progu – najniższy szczebel drabinki.
    """
    src_short = min(src_w, src_h) if src_w and src_h else 1080
    rungs = [r for r in RESOLUTION_LADDER if r <= src_short]
    if not rungs or rungs[0] < src_short:
        # Oryginał spoza drabinki (np. 1200p) – też jest kandydatem.
        rungs = [src_short] + rungs
    fps_options = [src_fps] if src_fps <= 30.5 else [src_fps, 30.0]
    last = None
    for rung in rungs:
        w, h = fit_resolution(src_w, src_h, rung)
        for fps in fps_options:
            q = quality_level(video_kbps, w, h, fps, family)
            last = AutoChoice(w, h, fps, q, rung)
            if quality_at_least(q, min_quality):
                return last
    return last  # najniższa rozdzielczość / fps


def suggest_lower(src_w: int, src_h: int, current_short: int) -> int | None:
    """Szczebel niżej w drabince – do podpowiedzi "Zalecane zmniejszenie do 540p"."""
    for rung in RESOLUTION_LADDER:
        if rung < current_short:
            return rung
    return None


# --------------------------------------------------------------------------- szacunki CRF / audio

def crf_estimate_kbps(crf: int, w: int, h: int, fps: float, family: str = "h264") -> float:
    """Bardzo przybliżony bitrate dla CRF (heurystyka: CRF 23 ≈ 0.08 bpp dla H.264,
    każde +6 CRF ≈ połowa bitrate'u)."""
    eff = CODEC_EFFICIENCY.get(family, 1.0)
    bpp = 0.08 * (2 ** ((23 - crf) / 6.0)) * eff
    return bpp * w * h * max(fps, 1) / 1000.0


# Przybliżone bitrate'y kodeków montażowych (kb/s dla 1080p25) – skalowane pikselami.
_INTERMEDIATE_1080P25 = {"prores_422": 117_000, "prores_hq": 176_000,
                         "prores_4444": 264_000, "dnxhr_hq": 176_000, "dnxhr_hqx": 176_000}


def intermediate_kbps(codec_key: str, w: int, h: int, fps: float) -> float:
    base = _INTERMEDIATE_1080P25.get(codec_key, 150_000)
    return base * (w * h) / (1920 * 1080) * (fps / 25.0)


def pcm_size_mb(duration_s: float, sample_rate: int, bits: int, channels: int) -> float:
    return duration_s * sample_rate * bits * channels / 8 / MB


def audio_estimate_mb(fmt: str, duration_s: float, sample_rate: int, channels: int,
                      bits: int = 16, kbps: float = 0) -> float:
    """Szacowany rozmiar pliku audio dla zakładki AUDIO."""
    if duration_s <= 0:
        return 0.0
    if fmt in ("wav", "aiff"):
        return pcm_size_mb(duration_s, sample_rate, bits, channels)
    if fmt in ("flac", "alac"):
        return pcm_size_mb(duration_s, sample_rate, bits, channels) * 0.6
    return kbps * 1000 * duration_s / 8 / MB
