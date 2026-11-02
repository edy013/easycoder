"""Generator nazw plików wyjściowych."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

# Znaki niedozwolone na Windows (oraz ':' problematyczny w Finderze).
_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}

PATTERN_VARS = ["{nazwa}", "{kodek}", "{rozdzielczosc}", "{rozmiarMB}",
                "{bitrate}", "{data}", "{nr}"]


def sanitize(name: str, replacement: str = "_") -> str:
    """Usuwa znaki niedozwolone w nazwach plików na Windows, żeby pliki
    przenoszone z Maca na PC zawsze działały."""
    cleaned = _FORBIDDEN.sub(replacement, name)
    cleaned = cleaned.rstrip(" .")  # Windows nie lubi kropek/spacji na końcu
    if not cleaned:
        cleaned = "plik"
    if cleaned.split(".")[0].upper() in _RESERVED:
        cleaned = "_" + cleaned
    return cleaned[:200]


def render_pattern(pattern: str, values: dict) -> str:
    """Podstawia zmienne {nazwa}, {kodek}... Nieznane zmienne zostają bez zmian."""
    def repl(m: re.Match) -> str:
        key = m.group(1)
        return str(values[key]) if key in values else m.group(0)
    return re.sub(r"\{(\w+)\}", repl, pattern)


def output_stem(src: Path, mode: str, suffix: str, pattern: str, values: dict,
                custom_name: str | None = None) -> str:
    """Nazwa wyjściowa bez rozszerzenia.

    mode: 'suffix' (oryginał + dopisek) lub 'pattern' (własny wzorzec).
    custom_name: nazwa nadana ręcznie (dwuklik na liście) – ma pierwszeństwo.
    """
    if custom_name:
        stem = Path(custom_name).stem if Path(custom_name).suffix else custom_name
        return sanitize(stem)
    if mode == "pattern" and pattern.strip():
        vals = {"nazwa": src.stem, "data": datetime.now().strftime("%Y-%m-%d")}
        vals.update(values)
        return sanitize(render_pattern(pattern, vals))
    return sanitize(src.stem + suffix)


def unique_path(path: Path, reserved: set | None = None, source: Path | None = None) -> Path:
    """Dopisuje (1), (2)... jeśli plik istnieje, jest zarezerwowany w kolejce
    albo jest plikiem źródłowym (źródła nigdy nie nadpisujemy)."""
    reserved = reserved or set()

    def taken(p: Path) -> bool:
        key = str(p).lower()
        if source is not None and _same(p, source):
            return True
        return p.exists() or key in reserved

    if not taken(path):
        return path
    i = 1
    while True:
        cand = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not taken(cand):
            return cand
        i += 1


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve() or str(a).lower() == str(b).lower()
    except OSError:
        return str(a).lower() == str(b).lower()


def build_output_path(src: Path, out_dir: Path, stem: str, ext: str,
                      overwrite: bool = False, reserved: set | None = None) -> Path:
    """Pełna ścieżka wyjściowa z ochroną przed nadpisaniem.

    overwrite=True pozwala nadpisać istniejący plik wynikowy, ale nigdy źródło.
    """
    path = Path(out_dir) / f"{stem}.{ext.lstrip('.')}"
    if overwrite and not _same(path, src) and str(path).lower() not in (reserved or set()):
        return path
    return unique_path(path, reserved, source=src)
