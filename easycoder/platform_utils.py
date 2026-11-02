"""Wszystkie różnice między Windows a macOS w jednym miejscu.

Ścieżki ustawień, nazwy binarek, dołączony FFmpeg, kandydaci na kodery
sprzętowe, otwieranie folderów, dźwięk i flagi procesów.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import APP_NAME

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"


def os_key(platform: str | None = None) -> str:
    """Klucz systemu używany w pliku ustawień ('windows' / 'macos' / 'linux')."""
    p = platform or sys.platform
    if p.startswith("win"):
        return "windows"
    if p == "darwin":
        return "macos"
    return "linux"


def app_data_dir(platform: str | None = None, home: Path | None = None,
                 env: dict | None = None) -> Path:
    """Folder ustawień aplikacji.

    Windows: %APPDATA%\\EasyCoder
    macOS:   ~/Library/Application Support/EasyCoder
    Linux:   ~/.config/EasyCoder
    """
    key = os_key(platform)
    home = home or Path.home()
    env = os.environ if env is None else env
    if key == "windows":
        base = Path(env["APPDATA"]) if env.get("APPDATA") else home / "AppData" / "Roaming"
    elif key == "macos":
        base = home / "Library" / "Application Support"
    else:
        base = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else home / ".config"
    return base / APP_NAME


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def exe_name(name: str, platform: str | None = None) -> str:
    """'ffmpeg' -> 'ffmpeg.exe' na Windows."""
    return f"{name}.exe" if os_key(platform) == "windows" else name


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def bundled_bin_dirs() -> list[Path]:
    """Miejsca, w których może leżeć dołączony FFmpeg.

    - PyInstaller (Windows, onefile/onedir): sys._MEIPASS/bin lub obok .exe
    - macOS .app: Contents/Resources/bin (oraz Contents/Frameworks/bin)
    - tryb deweloperski: <projekt>/bin
    """
    dirs: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(Path(meipass) / "bin")
        exe_dir = Path(sys.executable).resolve().parent
        dirs += [exe_dir / "bin", exe_dir.parent / "Resources" / "bin",
                 exe_dir.parent / "Frameworks" / "bin"]
    dirs.append(project_root() / "bin")
    return dirs


def find_ffmpeg(custom_dir: str | None = None) -> tuple[Path, Path] | None:
    """Szuka pary ffmpeg/ffprobe: ścieżka użytkownika -> dołączony -> PATH."""
    ff, fp = exe_name("ffmpeg"), exe_name("ffprobe")
    candidates: list[Path] = []
    if custom_dir:
        c = Path(custom_dir)
        candidates.append(c.parent if c.is_file() else c)
    candidates += bundled_bin_dirs()
    for d in candidates:
        if (d / ff).is_file() and (d / fp).is_file():
            return d / ff, d / fp
    w_ff, w_fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if w_ff and w_fp:
        return Path(w_ff), Path(w_fp)
    # Homebrew na Macu nie zawsze jest w PATH aplikacji uruchomionej z Findera.
    if IS_MAC:
        for d in (Path("/opt/homebrew/bin"), Path("/usr/local/bin")):
            if (d / ff).is_file() and (d / fp).is_file():
                return d / ff, d / fp
    return None


def hw_encoder_candidates(platform: str | None = None) -> list[str]:
    """Kodery sprzętowe sprawdzane na danym systemie."""
    key = os_key(platform)
    if key == "macos":
        return ["h264_videotoolbox", "hevc_videotoolbox", "prores_videotoolbox"]
    if key == "windows":
        return ["h264_nvenc", "hevc_nvenc", "av1_nvenc",
                "h264_qsv", "hevc_qsv", "av1_qsv",
                "h264_amf", "hevc_amf", "av1_amf"]
    return ["h264_nvenc", "hevc_nvenc", "av1_nvenc", "h264_vaapi", "hevc_vaapi"]


def null_output() -> str:
    """Wyjście "do nikąd" dla 1. przebiegu 2-pass."""
    return "NUL" if IS_WINDOWS else "/dev/null"


def subprocess_flags() -> dict:
    """Ukrywa okno konsoli przy wywołaniach subprocess na Windows."""
    if IS_WINDOWS:
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def command_to_string(argv: list[str]) -> str:
    """Komenda w formie do skopiowania do terminala danego systemu."""
    if IS_WINDOWS:
        return subprocess.list2cmdline([str(a) for a in argv])
    import shlex
    return shlex.join(str(a) for a in argv)


def reveal_in_file_manager(path: Path) -> None:
    """Pokazuje plik w Eksploratorze / Finderze (z zaznaczeniem)."""
    try:
        if IS_WINDOWS:
            subprocess.Popen(["explorer", "/select,", str(path)], **subprocess_flags())
        elif IS_MAC:
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        pass


def play_done_sound() -> None:
    """Krótki systemowy dźwięk po zakończeniu kolejki."""
    try:
        if IS_WINDOWS:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        elif IS_MAC:
            subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
        else:
            print("\a", end="", flush=True)
    except Exception:
        pass


def file_manager_name() -> str:
    return "Finder" if IS_MAC else ("Eksplorator" if IS_WINDOWS else "menedżer plików")
