"""Ścieżki na obu systemach oraz przenośność pliku ustawień."""
import json
from pathlib import Path, PurePosixPath, PureWindowsPath

from easycoder import platform_utils as pu
from easycoder.settings import Settings


def test_os_key():
    assert pu.os_key("win32") == "windows"
    assert pu.os_key("darwin") == "macos"
    assert pu.os_key("linux") == "linux"


def test_app_data_windows():
    p = pu.app_data_dir("win32", home=Path("C:/Users/x"), env={"APPDATA": "C:/Users/x/AppData/Roaming"})
    assert PureWindowsPath(p).parts[-2:] == ("Roaming", "EasyCoder")


def test_app_data_windows_without_env():
    p = pu.app_data_dir("win32", home=Path("C:/Users/x"), env={})
    assert p.parts[-3:] == ("AppData", "Roaming", "EasyCoder")


def test_app_data_macos():
    p = pu.app_data_dir("darwin", home=Path("/Users/x"), env={})
    assert PurePosixPath(p.as_posix()).parts[-3:] == ("Library", "Application Support", "EasyCoder")


def test_exe_names():
    assert pu.exe_name("ffmpeg", "win32") == "ffmpeg.exe"
    assert pu.exe_name("ffmpeg", "darwin") == "ffmpeg"


def test_hw_candidates_per_os():
    assert all("videotoolbox" in e for e in pu.hw_encoder_candidates("darwin"))
    win = pu.hw_encoder_candidates("win32")
    assert "h264_nvenc" in win and "h264_qsv" in win and "h264_amf" in win
    assert not any("videotoolbox" in e for e in win)


def test_paths_stored_per_os(tmp_path):
    f = tmp_path / "s.json"
    win = Settings(f, platform="win32")
    win.set_path("video_target", "D:/Wideo")
    win.save()
    mac = Settings(f, platform="darwin")
    assert mac.get_path("video_target") == ""          # ścieżka z Windows nie psuje Maca
    mac.set_path("video_target", "/Users/x/Movies")
    mac.save()
    again = Settings(f, platform="win32")
    assert again.get_path("video_target") == "D:/Wideo"


def test_export_import_keeps_local_paths(tmp_path):
    a = Settings(tmp_path / "a.json", platform="darwin")
    a.set_path("video_target", "/Users/x/Movies")
    a.data["presets"]["video"]["Klient"] = {"codec": "x264", "target_mb": 20}
    a.data["encoder_cache"]["macos"] = {"result": {"hw": ["h264_videotoolbox"]}}
    a.export_to(tmp_path / "export.json")
    exported = json.loads((tmp_path / "export.json").read_text(encoding="utf-8"))
    assert "encoder_cache" not in exported

    b = Settings(tmp_path / "b.json", platform="win32")
    b.set_path("video_target", "D:/Wideo")
    b.import_from(tmp_path / "export.json")
    assert b.get_path("video_target") == "D:/Wideo"
    assert b.data["presets"]["video"]["Klient"]["target_mb"] == 20
    assert b.data["paths"]["macos"]["video_target"] == "/Users/x/Movies"


def test_corrupt_settings_fall_back_to_defaults(tmp_path):
    f = tmp_path / "s.json"
    f.write_text("{nie json", encoding="utf-8")
    s = Settings(f)
    assert s.data["naming"]["video"]["suffix"] == "_ec"
