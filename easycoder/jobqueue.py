"""Kolejka zadań i wykonywanie FFmpeg przez QProcess (bez blokowania GUI).

Każde zadanie to 1..N kroków (np. 2 przebiegi). Postęp czytany jest z
`-progress pipe:1` (out_time_us), błędy ze stderr. Po zakodowaniu w trybie
rozmiaru sprawdzany jest rzeczywisty rozmiar i w razie przekroczenia zadanie
jest ponawiane z niższym bitrate (maks. 2 próby).
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QProcess, Signal

from . import calculator as calc
from .platform_utils import app_data_dir, command_to_string
from .probe import MediaInfo
from .strings import S

MAX_SIZE_RETRIES = 2
LOG_LIMIT = 400_000  # znaków stderr trzymanych w pamięci na zadanie


class Status:
    WAITING = "waiting"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class Job:
    kind: str                           # 'video' | 'audio'
    info: MediaInfo
    out_path: Path
    duration: float
    # (kbps | None) -> lista komend; kbps używany przy ponownej próbie rozmiaru
    make_commands: Callable[[float | None], list[list[str]]]
    target_mb: float | None = None      # cel rozmiaru (tylko tryb rozmiaru)
    video_kbps: float = 0.0
    weights: list[float] = field(default_factory=list)
    status: str = Status.WAITING
    progress: float = 0.0
    message: str = ""
    attempts: int = 0
    log: str = ""
    commands: list[list[str]] = field(default_factory=list)
    row_id: int = 0


ERROR_HINTS = [
    ("No such file or directory", "Nie znaleziono pliku lub folderu."),
    ("Permission denied", "Brak uprawnień do zapisu/odczytu (plik otwarty w innym programie?)."),
    ("No space left", "Brak miejsca na dysku."),
    ("Invalid data found", "Plik źródłowy jest uszkodzony albo to nie jest plik multimedialny."),
    ("Unknown encoder", "Ten FFmpeg nie ma wymaganego kodera."),
    ("Encoder not found", "Ten FFmpeg nie ma wymaganego kodera."),
    ("not divisible by 2", "Wymiary obrazu muszą być parzyste."),
    ("No NVENC capable devices", "Nie znaleziono karty NVIDIA obsługującej NVENC."),
    ("OpenEncodeSessionEx failed", "Karta NVIDIA odrzuciła kodowanie (limit sesji lub sterownik)."),
    ("Error while opening encoder", "Nie udało się uruchomić kodera – sprawdź kodek, format piksela "
                                    "i rozdzielczość."),
    ("Could not write header", "Nie da się zapisać tego połączenia kodeka i kontenera."),
    ("does not contain any stream", "Plik nie zawiera ścieżki, którą da się przetworzyć."),
    ("matches no streams", "Plik nie zawiera ścieżki audio/wideo potrzebnej do konwersji."),
]


def friendly_error(stderr: str, exit_code: int) -> str:
    """Czytelny komunikat po polsku na podstawie logu FFmpeg."""
    for needle, msg in ERROR_HINTS:
        if needle.lower() in stderr.lower():
            return msg
    last = [l for l in stderr.strip().splitlines() if l.strip()]
    tail = last[-1] if last else ""
    return f"FFmpeg zakończył się błędem (kod {exit_code}). {tail}"[:300]


def parse_progress_line(line: str) -> float | None:
    """'out_time_us=1234567' -> 1.234567 s (out_time_ms w FFmpeg to też µs)."""
    if line.startswith(("out_time_us=", "out_time_ms=")):
        try:
            return int(line.split("=", 1)[1]) / 1_000_000
        except ValueError:
            return None
    return None


class _Run:
    """Jedno aktualnie wykonywane zadanie (proces + stan kroków)."""

    def __init__(self, job: Job):
        self.job = job
        self.proc: QProcess | None = None
        self.step = 0
        self.tmp = Path(tempfile.mkdtemp(prefix="easycoder_"))
        self.started = time.monotonic()
        self.buf = b""


class JobRunner(QObject):
    job_started = Signal(object)
    job_progress = Signal(object, float, float)      # job, ułamek, ETA (s)
    job_finished = Signal(object)
    queue_progress = Signal(float, float)            # ułamek, ETA (s)
    queue_finished = Signal(int, int, bool)          # ok, błędy, przerwano
    history_entry = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.jobs: list[Job] = []
        self.running: list[_Run] = []
        self.parallel = 1
        self._stopping = False
        self._queue_started = 0.0
        self._total_weight = 0.0

    @property
    def busy(self) -> bool:
        return bool(self.running)

    # ------------------------------------------------------------------ sterowanie
    def start(self, jobs: list[Job], parallel: int = 1) -> None:
        self.jobs = jobs
        self.parallel = max(1, parallel)
        self._stopping = False
        self._queue_started = time.monotonic()
        self._total_weight = sum(max(j.duration, 1.0) for j in jobs) or 1.0
        self._fill()

    def stop(self) -> None:
        """Przerywa FFmpeg, usuwa niedokończone pliki i logi 2-pass."""
        self._stopping = True
        for run in list(self.running):
            if run.proc:
                run.proc.blockSignals(True)
                run.proc.kill()
                run.proc.waitForFinished(3000)
            run.job.status = Status.STOPPED
            run.job.message = S["status_stopped"]
            self._cleanup(run, remove_output=True)
            self.job_finished.emit(run.job)
            self._history(run.job, False)
        self.running.clear()
        ok = sum(1 for j in self.jobs if j.status == Status.DONE)
        err = sum(1 for j in self.jobs if j.status == Status.ERROR)
        self.queue_finished.emit(ok, err, True)

    # ------------------------------------------------------------------ wewnętrzne
    def _fill(self) -> None:
        if self._stopping:
            return
        while len(self.running) < self.parallel:
            nxt = next((j for j in self.jobs if j.status == Status.WAITING), None)
            if nxt is None:
                break
            self._begin(nxt)
        if not self.running:
            ok = sum(1 for j in self.jobs if j.status == Status.DONE)
            err = sum(1 for j in self.jobs if j.status == Status.ERROR)
            self.queue_finished.emit(ok, err, False)

    def _begin(self, job: Job, kbps: float | None = None) -> None:
        job.status = Status.RUNNING
        job.progress = 0.0
        job.commands = job.make_commands(kbps)
        n = len(job.commands)
        job.weights = [0.35, 0.65] if n == 2 else [1.0 / n] * n
        job.out_path.parent.mkdir(parents=True, exist_ok=True)
        run = _Run(job)
        self.running.append(run)
        self.job_started.emit(job)
        self._launch_step(run)

    def _launch_step(self, run: _Run) -> None:
        argv = run.job.commands[run.step]
        proc = QProcess(self)
        proc.setWorkingDirectory(str(run.tmp))  # logi 2-pass trafiają do folderu tymczasowego
        proc.readyReadStandardOutput.connect(lambda r=run: self._on_stdout(r))
        proc.readyReadStandardError.connect(lambda r=run: self._on_stderr(r))
        proc.finished.connect(lambda code, status, r=run: self._on_finished(r, code, status))
        proc.errorOccurred.connect(lambda err, r=run: self._on_error(r, err))
        run.proc = proc
        run.job.log += f"\n$ {command_to_string(argv)}\n"
        proc.start(argv[0], argv[1:])

    def _on_stdout(self, run: _Run) -> None:
        run.buf += bytes(run.proc.readAllStandardOutput())
        *lines, run.buf = run.buf.split(b"\n")
        t = None
        for raw in lines:
            v = parse_progress_line(raw.decode("ascii", "ignore").strip())
            if v is not None:
                t = v
        if t is None:
            return
        job = run.job
        step_frac = min(1.0, t / job.duration) if job.duration > 0 else 0.0
        frac = sum(job.weights[:run.step]) + job.weights[run.step] * step_frac
        job.progress = frac
        elapsed = time.monotonic() - run.started
        eta = elapsed * (1 - frac) / frac if frac > 0.01 else -1
        self.job_progress.emit(job, frac, eta)
        self._emit_queue_progress()

    def _emit_queue_progress(self) -> None:
        done = sum(max(j.duration, 1.0) * (1.0 if j.status in (Status.DONE, Status.ERROR)
                                         else j.progress if j.status == Status.RUNNING else 0.0)
                   for j in self.jobs)
        frac = min(1.0, done / self._total_weight)
        elapsed = time.monotonic() - self._queue_started
        eta = elapsed * (1 - frac) / frac if frac > 0.01 else -1
        self.queue_progress.emit(frac, eta)

    def _on_stderr(self, run: _Run) -> None:
        txt = bytes(run.proc.readAllStandardError()).decode("utf-8", "replace")
        run.job.log = (run.job.log + txt)[-LOG_LIMIT:]

    def _on_error(self, run: _Run, err) -> None:
        if err == QProcess.ProcessError.FailedToStart:
            self._fail(run, S["err_ffmpeg_start"])

    def _on_finished(self, run: _Run, code: int, status) -> None:
        if run not in self.running:
            return
        self._on_stderr(run)
        if code != 0 or status != QProcess.ExitStatus.NormalExit:
            self._fail(run, friendly_error(run.job.log, code))
            return
        run.step += 1
        if run.step < len(run.job.commands):
            self._launch_step(run)
            return
        self._complete(run)

    def _complete(self, run: _Run) -> None:
        job = run.job
        # Kontrola rozmiaru w trybie "Rozmiar docelowy".
        if job.target_mb and job.out_path.exists():
            actual = job.out_path.stat().st_size / calc.MB
            if actual > job.target_mb and job.attempts < MAX_SIZE_RETRIES:
                job.attempts += 1
                job.video_kbps = calc.retry_bitrate(job.video_kbps, job.target_mb, actual)
                job.log += (f"\n[EASY CODER] Rozmiar {actual:.2f} MB > {job.target_mb:.2f} MB – "
                            f"ponawiam z {job.video_kbps:.0f} kb/s (próba {job.attempts}).\n")
                self._history(job, False, note=S["retry_note"].format(actual))
                self._cleanup(run, remove_output=True)
                self.running.remove(run)
                self._begin(job, job.video_kbps)
                return
        job.status = Status.DONE
        job.progress = 1.0
        size = job.out_path.stat().st_size / calc.MB if job.out_path.exists() else 0
        job.message = S["status_done_size"].format(size)
        self._cleanup(run, remove_output=False)
        self.running.remove(run)
        self.job_finished.emit(job)
        self._history(job, True)
        self._emit_queue_progress()
        self._fill()

    def _fail(self, run: _Run, message: str) -> None:
        if run not in self.running:
            return
        job = run.job
        job.status = Status.ERROR
        job.message = message
        self._cleanup(run, remove_output=True)
        self.running.remove(run)
        self.job_finished.emit(job)
        self._history(job, False)
        self._fill()

    def _cleanup(self, run: _Run, remove_output: bool) -> None:
        if remove_output:
            try:
                run.job.out_path.unlink(missing_ok=True)
            except OSError:
                pass
        shutil.rmtree(run.tmp, ignore_errors=True)

    def _history(self, job: Job, ok: bool, note: str = "") -> None:
        self.history_entry.emit({
            "time": datetime.now().isoformat(timespec="seconds"),
            "kind": job.kind,
            "input": str(job.info.path),
            "output": str(job.out_path),
            "commands": [command_to_string(c) for c in job.commands],
            "ok": ok,
            "message": note or job.message,
            "log": job.log[-20000:],
        })


class HistoryStore:
    """Historia konwersji zapisywana w folderze ustawień (ostatnie 300 wpisów)."""

    LIMIT = 300

    def __init__(self, path: Path | None = None):
        self.path = path or (app_data_dir() / "history.json")
        try:
            self.entries: list[dict] = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.entries = []

    def add(self, entry: dict) -> None:
        self.entries.append(entry)
        self.entries = self.entries[-self.LIMIT:]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.entries, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def clear(self) -> None:
        self.entries = []
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass
