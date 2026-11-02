"""Wszystkie teksty interfejsu w jednym miejscu.

Aby dodać język angielski: skopiuj słownik PL jako EN, przetłumacz wartości
i ustaw `S = _Strings(EN)` (lub wybór w ustawieniach).
"""
from __future__ import annotations


class _Strings(dict):
    """Słownik, który przy brakującym kluczu zwraca sam klucz (zamiast wyjątku)."""

    def __missing__(self, key):
        return key


PL = {
    # --- ogólne
    "app_subtitle": "kompresja i konwersja wideo oraz audio",
    "tab_video": "WIDEO",
    "tab_audio": "AUDIO",
    "add_files": "Dodaj pliki",
    "add_folder": "Dodaj folder",
    "remove": "Usuń",
    "clear": "Wyczyść",
    "drop_hint": "Przeciągnij tutaj pliki lub foldery",
    "source_folder": "Folder źródłowy:",
    "target_folder": "Folder docelowy:",
    "browse": "Przeglądaj…",
    "next_to_source": "Zapisuj obok pliku źródłowego",
    "start": "START",
    "stop": "Stop",
    "open_target": "Otwórz folder docelowy",
    "current_file": "Bieżący plik",
    "whole_queue": "Cała kolejka",
    "eta": "pozostało {}",
    "eta_unknown": "pozostało —",
    "idle": "Gotowy",
    "choose_files": "Wybierz pliki",
    "choose_folder": "Wybierz folder",
    "media_filter_video": "Pliki wideo ({})",
    "media_filter_audio": "Pliki audio i wideo ({})",
    "all_files": "Wszystkie pliki (*)",

    # --- kolumny
    "col_name": "Nazwa",
    "col_format": "Format",
    "col_duration": "Czas",
    "col_res": "Rozdzielczość",
    "col_rate": "Częstotl.",
    "col_size": "Rozmiar",
    "col_est": "Szac. rozmiar",
    "col_output": "Plik wyjściowy",
    "col_status": "Status",
    "col_progress": "Postęp",

    # --- statusy
    "status_probing": "Analiza…",
    "status_ready": "Oczekuje",
    "status_running": "Kodowanie…",
    "status_done_size": "Gotowe ({:.2f} MB)",
    "status_error": "Błąd",
    "status_stopped": "Przerwano",
    "status_probe_error": "Nieczytelny plik",
    "retry_note": "Plik miał {:.2f} MB – ponawiam z niższym bitrate",

    # --- nazewnictwo
    "naming": "Nazwa pliku wyjściowego",
    "naming_suffix": "Oryginalna nazwa + dopisek",
    "naming_pattern": "Własny wzorzec",
    "naming_vars": "Zmienne: {nazwa} {kodek} {rozdzielczosc} {rozmiarMB} {bitrate} {data} {nr}",
    "naming_preview": "Podgląd: {}",
    "naming_rename_hint": "Dwuklik na pliku na liście = własna nazwa",
    "rename_title": "Nazwa pliku wyjściowego",
    "rename_prompt": "Nowa nazwa (bez rozszerzenia, puste = automatyczna):",

    # --- wideo
    "presets": "Presety",
    "preset_preview720": "Do podglądu / dla klienta (720p)",
    "preset_preview1080": "Do podglądu 1080p",
    "preset_archive": "Archiwum (oryginał, wysoka jakość)",
    "mode": "Tryb kompresji",
    "mode_size": "Rozmiar docelowy (MB)",
    "mode_crf": "Stała jakość (CRF)",
    "target_size": "Docelowy rozmiar pliku",
    "size_custom": "Własny",
    "size_scope_per_file": "na każdy plik",
    "size_scope_total": "łącznie dla wszystkich",
    "info_bitrate": "Bitrate wideo: {}",
    "info_resolution": "Rozdzielczość wyjściowa: {}",
    "info_quality": "Przewidywana jakość: {}",
    "info_estimate": "Szacowany rozmiar: {}",
    "info_no_file": "Dodaj plik, aby zobaczyć wyliczenia.",
    "info_for_file": "Dla pliku: {}",
    "hint_lower": "Zalecane zmniejszenie do {}p",
    "hint_upscale": "Uwaga: powiększanie obrazu nie poprawia jakości, tylko zwiększa plik.",
    "hint_tonemap": "Materiał HDR – zostanie zmapowany do SDR (tone mapping).",
    "hint_no_size": "Kodek montażowy – rozmiar wynika z jakości, suwak MB nie działa.",
    "hint_auto_crf": "„Auto” działa tylko w trybie rozmiaru – w CRF zostaje oryginał.",
    "quality_excellent": "Świetna",
    "quality_good": "Dobra",
    "quality_medium": "Średnia",
    "quality_poor": "Słaba",
    "crf_hint": "18 = prawie bezstratnie · 23 = standard · 28 = mały plik",
    "resolution": "Rozdzielczość",
    "res_auto": "Auto (najlepsza dla rozmiaru)",
    "res_orig": "Bez zmian (oryginał)",
    "res_custom": "Własna",
    "allow_upscale": "Pozwól powiększać ponad oryginał (niezalecane)",
    "fps": "Liczba klatek",
    "fps_orig": "Bez zmian",
    "fps_max30": "Maks. 30",
    "codec": "Kodek wideo",
    "speed": "Szybkość kodowania",
    "speed_fast": "Szybko",
    "speed_balanced": "Zrównoważone",
    "speed_best": "Najlepsza jakość",
    "ten_bit": "10-bit",
    "container": "Kontener",
    "video_audio": "Dźwięk",
    "include_audio": "Dołącz dźwięk",
    "audio_codec": "Kodek",
    "audio_bitrate": "Bitrate",
    "mono": "Mono",
    "acodec_aac": "AAC",
    "acodec_opus": "Opus",
    "acodec_pcm": "PCM 24-bit (montaż)",
    "acodec_copy": "Kopiuj bez zmian",
    "trim": "Przycinanie",
    "trim_start": "Początek",
    "trim_end": "Koniec",
    "trim_placeholder": "np. 0:12 lub 1:02:03.5",
    "extract_audio": "Tylko wyciągnij audio z wideo →",
    "hw_detecting": "Wykrywanie koderów sprzętowych…",
    "encoders_found": "Kodery sprzętowe: {}",
    "encoders_none": "brak (tylko programowe)",

    # --- audio
    "out_format": "Format wyjściowy",
    "preset_mp3_128": "MP3 128 (mały)",
    "preset_mp3_320": "MP3 320 (max)",
    "preset_wav_cd": "WAV 16-bit 44.1 kHz (CD)",
    "preset_wav_studio": "WAV 24-bit 48 kHz (wideo/studio)",
    "preset_flac": "FLAC bezstratny",
    "mp3_vbr": "VBR V0 (~245 kb/s)",
    "bit_depth": "Głębia bitowa",
    "bit_32f": "32-bit float",
    "flac_level": "Poziom kompresji FLAC",
    "sample_rate": "Częstotliwość",
    "rate_orig": "Bez zmian",
    "channels": "Kanały",
    "stereo": "Stereo",
    "loudnorm": "Normalizacja głośności",
    "loud_off": "Wyłączona",
    "loud_14": "-14 LUFS (streaming)",
    "loud_16": "-16 LUFS (podcast)",
    "loud_23": "-23 LUFS (broadcast)",
    "keep_meta": "Zachowaj metadane (tytuł, wykonawca, okładka)",
    "parallel": "Przetwarzaj 2 pliki równolegle",
    "lossy_note": "Uwaga: dekodowanie pliku stratnego (MP3/AAC…) do formatu bezstratnego "
                  "nie przywraca utraconej jakości – plik będzie tylko większy.",
    "fmt_mp3": "MP3",
    "fmt_wav": "WAV (PCM)",
    "fmt_aiff": "AIFF",
    "fmt_flac": "FLAC",
    "fmt_aac": "AAC / M4A",
    "fmt_alac": "ALAC (bezstratny Apple)",
    "fmt_ogg": "OGG Vorbis",
    "fmt_opus": "Opus",

    # --- menu
    "menu_file": "Plik",
    "menu_settings": "Ustawienia",
    "menu_view": "Widok",
    "menu_help": "Pomoc",
    "act_export": "Eksportuj ustawienia i presety…",
    "act_import": "Importuj ustawienia i presety…",
    "act_ffmpeg": "Wskaż FFmpeg…",
    "act_redetect": "Wykryj kodery ponownie",
    "act_quit": "Zakończ",
    "act_history": "Historia konwersji",
    "act_about": "O programie EASY CODER",
    "act_sound": "Dźwięk po zakończeniu kolejki",
    "act_notify": "Powiadomienie systemowe",
    "act_overwrite": "Gdy plik wyjściowy istnieje",
    "act_ow_number": "Dopisz (1), (2)…",
    "act_ow_ask": "Zapytaj",
    "act_save_preset": "Zapisz bieżące ustawienia jako preset…",
    "act_delete_preset": "Usuń preset użytkownika…",
    "user_presets": "Moje presety",
    "preset_name_prompt": "Nazwa presetu:",

    # --- komunikaty
    "ffmpeg_missing_title": "Nie znaleziono FFmpeg",
    "ffmpeg_missing": "EASY CODER potrzebuje programów ffmpeg i ffprobe.\n\n"
                      "Nie ma ich w folderze aplikacji ani w PATH. Wskaż folder, "
                      "w którym leżą ffmpeg i ffprobe.",
    "ffmpeg_choose": "Wskaż ffmpeg",
    "ffmpeg_invalid": "W tym folderze nie ma pary ffmpeg + ffprobe.",
    "err_ffmpeg_start": "Nie udało się uruchomić FFmpeg.",
    "queue_empty": "Kolejka jest pusta – dodaj pliki.",
    "no_target": "Wybierz folder docelowy albo zaznacz „Zapisuj obok pliku źródłowego”.",
    "invalid_settings": "Nie można zacząć – popraw ustawienia:",
    "overwrite_title": "Pliki już istnieją",
    "overwrite_ask": "{} plik(ów) wyjściowych już istnieje.\n\nNadpisać je? "
                     "(„Nie” = dopisz (1), (2)… do nazwy)",
    "done_title": "EASY CODER – gotowe",
    "done_msg": "Zakończono: {} OK, {} błędów.",
    "stopped_msg": "Kolejka przerwana.",
    "errors_title": "Błędy podczas konwersji",
    "errors_msg": "Nie udało się przetworzyć {} plik(ów):",
    "export_done": "Zapisano ustawienia do:\n{}",
    "import_done": "Zaimportowano ustawienia i presety.",
    "import_error": "Nie udało się wczytać pliku ustawień:\n{}",
    "busy_close": "Trwa kodowanie. Przerwać i zamknąć?",
    "about": "<h2>EASY CODER {}</h2><p>Prosty konwerter i kompresor wideo oraz audio "
             "dla montażystów i muzyków.</p><p>Silnik: FFmpeg ({})</p>"
             "<p>Ustawienia: {}</p>",

    # --- historia
    "history_title": "Historia konwersji",
    "history_copy": "Kopiuj komendę",
    "history_clear": "Wyczyść historię",
    "history_close": "Zamknij",
    "history_ok": "OK",
    "history_fail": "BŁĄD",
}

S = _Strings(PL)


def quality_text(level: str) -> str:
    return S[f"quality_{level}"]


def format_duration(seconds: float) -> str:
    if seconds is None or seconds < 0:
        return "—"
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_size(mb: float) -> str:
    if mb <= 0:
        return "—"
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    if mb >= 10:
        return f"{mb:.0f} MB"
    return f"{mb:.1f} MB"


def format_kbps(kbps: float) -> str:
    if kbps >= 10000:
        return f"{kbps / 1000:.1f} Mb/s"
    return f"{kbps:,.0f} kb/s".replace(",", " ")
