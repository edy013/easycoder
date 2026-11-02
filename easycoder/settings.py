"""Ustawienia aplikacji w JSON – ten sam format na Windows i macOS.

Ścieżki folderów zapisywane są osobno dla każdego systemu (klucz "paths" ->
"windows"/"macos"), więc import pliku z drugiego komputera ich nie psuje.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .platform_utils import os_key, settings_path

SETTINGS_VERSION = 1

DEFAULTS: dict = {
    "version": SETTINGS_VERSION,
    "video": {},          # VideoSettings.to_dict()
    "audio": {},          # AudioSettings.to_dict()
    "naming": {
        "video": {"mode": "suffix", "suffix": "_ec", "pattern": "{nazwa}_{rozdzielczosc}_{rozmiarMB}MB"},
        "audio": {"mode": "suffix", "suffix": "_ec", "pattern": "{nazwa}_{kodek}"},
    },
    "general": {
        "overwrite": "number",        # 'number' (dopisz (1)) | 'ask'
        "done_sound": True,
        "notify": True,
        "next_to_source": {"video": False, "audio": False},
    },
    "paths": {},          # {"windows": {...}, "macos": {...}}
    "presets": {"video": {}, "audio": {}},   # presety użytkownika
    "encoder_cache": {},  # per system: {ffmpeg, mtime, result}
    "window": {},
}


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Settings:
    """Prosty magazyn ustawień z zapisem do pliku."""

    def __init__(self, path: Path | None = None, platform: str | None = None):
        self.path = Path(path) if path else settings_path()
        self.os = os_key(platform)
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    # ---- plik
    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.data = _merge(DEFAULTS, raw)
        except (OSError, ValueError):
            self.data = copy.deepcopy(DEFAULTS)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ---- ścieżki zależne od systemu
    def get_path(self, key: str, default: str = "") -> str:
        return self.data.get("paths", {}).get(self.os, {}).get(key, default)

    def set_path(self, key: str, value: str) -> None:
        self.data.setdefault("paths", {}).setdefault(self.os, {})[key] = str(value)

    # ---- sekcje
    def section(self, name: str) -> dict:
        return self.data.setdefault(name, {})

    # ---- eksport / import
    def export_to(self, path: Path) -> None:
        data = copy.deepcopy(self.data)
        data.pop("encoder_cache", None)   # zależne od sprzętu
        data.pop("window", None)
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def import_from(self, path: Path) -> None:
        """Importuje ustawienia i presety. Ścieżki bieżącego systemu zostają,
        jeśli importowany plik ich nie zawiera; ścieżki innych systemów są
        dołączane bez wpływu na ten komputer."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("To nie jest plik ustawień EASY CODER.")
        mine_paths = copy.deepcopy(self.data.get("paths", {}).get(self.os, {}))
        cache = self.data.get("encoder_cache", {})
        window = self.data.get("window", {})
        raw.pop("encoder_cache", None)
        raw.pop("window", None)
        self.data = _merge(DEFAULTS, _merge(self.data, raw))
        imported_mine = raw.get("paths", {}).get(self.os, {})
        merged = _merge(mine_paths, imported_mine)
        # Ścieżki, które nie istnieją na tym komputerze, nie nadpisują lokalnych.
        for k, v in imported_mine.items():
            if k in mine_paths and v and not Path(v).exists():
                merged[k] = mine_paths[k]
        self.data.setdefault("paths", {})[self.os] = merged
        self.data["encoder_cache"] = cache
        self.data["window"] = window
