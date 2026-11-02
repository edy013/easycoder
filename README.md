# EASY CODER

Desktopowy kompresor/konwerter wideo i audio (FFmpeg + PySide6) dla Windows i macOS – jeden wspólny kod.

- **WIDEO** – suwak „docelowy rozmiar w MB” (2-pass, kontrola rozmiaru z maks. 2 ponowieniami), tryb CRF,
  rozdzielczość ręczna lub Auto (4K → … → 360p, ew. 60→30 fps), presety *Mail 20/25 MB, Discord 10, WhatsApp 64, 100 MB*,
  *Do podglądu 720p/1080p*, *Archiwum*, H.264/H.265/AV1/VP9/ProRes/DNxHR + kodery sprzętowe (NVENC/QSV/AMF/VideoToolbox – tylko wykryte),
  HDR→SDR (tone mapping), przycinanie, dźwięk wł./wył. (wyłączenie oddaje budżet obrazowi).
- **AUDIO** – MP3 (CBR/V0), WAV 16/24/32f, AIFF, FLAC 0–8, AAC/M4A, ALAC, OGG, Opus; częstotliwość, mono/stereo,
  loudnorm −14/−16/−23 LUFS, metadane z okładką, opcjonalnie 2 pliki równolegle.
- Kolejka z drag & drop, szacowany rozmiar przed startem, ETA, Stop (usuwa niedokończony plik i logi 2-pass),
  nazewnictwo (dopisek / wzorzec ze zmiennymi / dwuklik), historia z komendami FFmpeg, powiadomienie systemowe.

## Architektura

```
main.py                     start (python main.py)
easycoder/
  platform_utils.py         WSZYSTKIE różnice Windows/macOS: ścieżki, binarki, kodery HW, Finder/Eksplorator, dźwięk
  probe.py                  ffprobe -> MediaInfo (obrót, HDR, 10-bit, okładka)
  calculator.py             bitrate z rozmiaru, rozdzielczość (pion/nietypowe proporcje), jakość bpp, Auto
  ffmpeg_cmd.py             ustawienia (dataclass) -> komendy FFmpeg (2-pass / VBR HW / CRF / audio), walidacja
  naming.py                 nazwy plików: dopisek, wzorzec, czyszczenie znaków Windows, (1)(2), ochrona źródła
  encoders.py               wykrywanie koderów (testowe kodowanie)
  jobqueue.py               kolejka QProcess, postęp z -progress pipe:1, ponawianie rozmiaru, historia
  settings.py               settings.json (ścieżki osobno per system), eksport/import
  strings.py                wszystkie teksty UI (PL) – tu dodaje się angielski
  gui/                      main_window, base_tab (kolejka/foldery/nazwy/postęp), video_tab, audio_tab, history, theme
tests/                      pytest: kalkulator, rozdzielczości (w tym pion), nazwy, ścieżki i ustawienia, komendy
scripts/                    fetch_ffmpeg.py, make_icons.py, build_windows.ps1, build_macos.sh
EasyCoder.spec              PyInstaller (Windows + macOS)
installer/EasyCoder.iss     instalator Inno Setup
.github/workflows/build.yml GitHub Actions: testy + Windows + macOS arm64/x86_64 + Release
```

Ustawienia: Windows `%APPDATA%\EasyCoder\settings.json`, macOS `~/Library/Application Support/EasyCoder/settings.json`.
Menu **Plik → Eksportuj/Importuj ustawienia i presety** przenosi je między komputerami; foldery są zapisywane
osobno dla `windows` i `macos`, więc import ich nie psuje.

FFmpeg szukany jest kolejno: folder wskazany w menu → dołączony `bin/` → PATH (na Macu też Homebrew) → okno wyboru.

## Uruchomienie ze źródeł

```bash
python -m venv .venv
```
Windows: `.venv\Scripts\activate`, macOS: `source .venv/bin/activate`, potem:
```bash
pip install -r requirements.txt -r requirements-build.txt
```
```bash
python main.py
```
```bash
python -m pytest -q
```

## Budowa – Windows

```bash
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```
Pobiera FFmpeg (gyan.dev release essentials) do `bin\` (albo `-FfmpegDir C:\ścieżka` z własnym), uruchamia testy i PyInstaller.
Wynik: `dist\EasyCoder-win\EasyCoder.exe` + `dist\EasyCoder-win\bin\ffmpeg.exe, ffprobe.exe`, zip, a jeśli jest
[Inno Setup 6](https://jrsoftware.org/isinfo.php) – `dist\EasyCoder-Setup.exe` (skrót w menu Start, opcjonalnie na pulpicie).
FFmpeg leży obok .exe, a nie w środku – inaczej każde uruchomienie rozpakowywałoby setki MB do folderu tymczasowego.

## Budowa – macOS

```bash
./scripts/build_macos.sh arm64
```
`arm64` (M1–M4), `x86_64` (Intel) albo `universal2` (wymaga Pythona universal2 z python.org; FFmpeg jest wtedy sklejany `lipo`).
FFmpeg (ffmpeg.martin-riedl.de) trafia do `EasyCoder.app/Contents/Resources/bin`. Wynik: `dist/EasyCoder-macOS-<arch>.dmg`.

**Bez konta Apple Developer** aplikacja jest podpisana ad-hoc. Przy pierwszym uruchomieniu Gatekeeper ją zablokuje:
kliknij `EasyCoder.app` w Programach **prawym przyciskiem → Otwórz → Otwórz** (jednorazowo). Na macOS 15+ zamiast tego:
Ustawienia systemowe → Prywatność i ochrona → „Otwórz mimo to”. Alternatywnie w Terminalu:
```bash
xattr -dr com.apple.quarantine /Applications/EasyCoder.app
```

**Z kontem Apple Developer** (podpis + notaryzacja):
```bash
xcrun notarytool store-credentials easycoder --apple-id TWOJ@EMAIL --team-id TEAMID --password HASLO-APLIKACJI
```
```bash
EC_CODESIGN_IDENTITY="Developer ID Application: Imię Nazwisko (TEAMID)" EC_NOTARY_PROFILE=easycoder ./scripts/build_macos.sh arm64
```

## GitHub Actions

`.github/workflows/build.yml` – po wypchnięciu tagu `v1.0.0` (lub ręcznie z zakładki Actions) buduje:
Windows (zip + instalator), macOS arm64 (`macos-14`) i Intel (`macos-15-intel`) i dołącza je do Release.
Podpis Maca jest opcjonalny – sekrety: `MACOS_CERT_P12` (base64), `MACOS_CERT_PASSWORD`, `MACOS_CODESIGN_IDENTITY`,
`APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD`.

## Uwagi

- Kodery montażowe (ProRes, DNxHR) nie mają trybu rozmiaru – suwak MB jest wtedy nieaktywny.
- SVT-AV1 i kodery sprzętowe są jednoprzebiegowe (VBR + maxrate/bufsize); przekroczenie rozmiaru koryguje ponowienie.
- Tone mapping HDR→SDR wymaga filtra `zscale` (jest w zalecanych buildach FFmpeg); 10-bit HEVC/AV1 zachowuje HDR.
