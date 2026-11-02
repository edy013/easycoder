"""Generator nazw plików."""
from pathlib import Path

from easycoder import naming


def test_sanitize_windows_forbidden():
    assert naming.sanitize('a\\b/c:d*e?f"g<h>i|j') == "a_b_c_d_e_f_g_h_i_j"


def test_sanitize_trailing_dots_and_reserved():
    assert naming.sanitize("film. ") == "film"
    assert naming.sanitize("CON") == "_CON"
    assert naming.sanitize("") == "plik"


def test_suffix_mode():
    assert naming.output_stem(Path("film.mov"), "suffix", "_ec", "", {}) == "film_ec"


def test_pattern_mode():
    stem = naming.output_stem(Path("/x/film.mov"), "pattern", "_ec",
                              "{nazwa}_{rozdzielczosc}_{rozmiarMB}MB",
                              {"rozdzielczosc": "720p", "rozmiarMB": "25"})
    assert stem == "film_720p_25MB"


def test_pattern_unknown_vars_kept_and_sanitized():
    stem = naming.output_stem(Path("a.mp4"), "pattern", "", "{nazwa}:{xyz}", {})
    assert stem == "a_{xyz}"


def test_pattern_date_and_number():
    stem = naming.output_stem(Path("a.mp4"), "pattern", "", "{nr}-{data}", {"nr": "03"})
    assert stem.startswith("03-20")


def test_custom_name_wins():
    assert naming.output_stem(Path("a.mp4"), "pattern", "_x", "{nazwa}", {}, "Klient v2") == "Klient v2"
    assert naming.output_stem(Path("a.mp4"), "suffix", "_x", "", {}, "dla:klienta.mp4") == "dla_klienta"


def test_unique_numbering(tmp_path):
    (tmp_path / "film_ec.mp4").write_bytes(b"x")
    (tmp_path / "film_ec (1).mp4").write_bytes(b"x")
    p = naming.build_output_path(tmp_path / "film.mov", tmp_path, "film_ec", "mp4")
    assert p.name == "film_ec (2).mp4"


def test_reserved_in_queue(tmp_path):
    reserved = {str(tmp_path / "a_ec.mp4").lower()}
    p = naming.build_output_path(tmp_path / "a.mov", tmp_path, "a_ec", "mp4", reserved=reserved)
    assert p.name == "a_ec (1).mp4"


def test_never_overwrites_source(tmp_path):
    src = tmp_path / "film.mp4"
    src.write_bytes(b"x")
    # pusty dopisek + ten sam kontener + ten sam folder = nazwa źródła
    p = naming.build_output_path(src, tmp_path, "film", "mp4", overwrite=True)
    assert p != src and p.name == "film (1).mp4"


def test_overwrite_existing_output(tmp_path):
    (tmp_path / "b_ec.mp4").write_bytes(b"x")
    p = naming.build_output_path(tmp_path / "b.mov", tmp_path, "b_ec", "mp4", overwrite=True)
    assert p.name == "b_ec.mp4"
