"""Wspólna część zakładek WIDEO i AUDIO: kolejka plików, foldery,
nazewnictwo, przyciski START/Stop i paski postępu."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QFileDialog, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog,
                               QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
                               QRadioButton, QScrollArea, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .. import naming
from ..jobqueue import Job, JobRunner, Status
from ..probe import AUDIO_EXTS, VIDEO_EXTS, MediaInfo, collect_media_files, probe
from ..settings import Settings
from ..strings import S, format_duration, format_size
from . import theme

COLS = ["col_name", "col_format", "col_duration", "col_res", "col_size", "col_est",
        "col_output", "col_status", "col_progress"]
C_NAME, C_FMT, C_DUR, C_RES, C_SIZE, C_EST, C_OUT, C_STATUS, C_PROG = range(len(COLS))


@dataclass
class QueueItem:
    path: Path
    info: MediaInfo | None = None
    custom_name: str | None = None
    out_path: Path | None = None
    est_mb: float = 0.0
    status: str = ""
    job: Job | None = None


# ----------------------------------------------------------------- analiza w tle

class _ProbeSignals(QObject):
    done = Signal(object, object)   # QueueItem, MediaInfo


class _ProbeTask(QRunnable):
    def __init__(self, item: QueueItem, ffprobe: Path, signals: _ProbeSignals):
        super().__init__()
        self.item, self.ffprobe, self.signals = item, ffprobe, signals

    def run(self):
        self.signals.done.emit(self.item, probe(self.item.path, self.ffprobe))


# ----------------------------------------------------------------- tabela z drag & drop

class FileTable(QTableWidget):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(0, len(COLS), parent)
        self.setHorizontalHeaderLabels([S[c] for c in COLS])
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(30)
        self.setShowGrid(False)
        self.setWordWrap(False)
        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setSectionResizeMode(C_NAME, QHeaderView.Stretch)
        h.setSectionResizeMode(C_OUT, QHeaderView.Stretch)
        h.setMinimumSectionSize(40)
        for col, w in [(C_FMT, 58), (C_DUR, 62), (C_RES, 125), (C_SIZE, 72), (C_EST, 92),
                       (C_STATUS, 140), (C_PROG, 90)]:
            self.setColumnWidth(col, w)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            paths = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
            self.files_dropped.emit(paths)
            e.acceptProposedAction()
        else:
            super().dropEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.rowCount() == 0:
            p = QPainter(self.viewport())
            p.setPen(Qt.gray)
            f = self.font()
            f.setPointSizeF(max(f.pointSizeF(), 10.0) + 3)
            p.setFont(f)
            p.drawText(self.viewport().rect(), Qt.AlignCenter, "⬇  " + S["drop_hint"])
            p.end()


def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color: {theme.BORDER};")
    return f


def fmt_eta(seconds: float) -> str:
    return S["eta"].format(format_duration(seconds)) if seconds and seconds >= 0 else S["eta_unknown"]


# ----------------------------------------------------------------- zakładka bazowa

class BaseTab(QWidget):
    """Szablon zakładki. Podklasy implementują panel ustawień i budowę zadań."""

    kind = "video"                       # klucz w ustawieniach
    file_kinds = {"video"}               # jakie pliki przyjmować z folderów
    queue_done = Signal(int, int, bool, list)   # ok, błędy, przerwano, zadania z błędem
    history_entry = Signal(dict)
    busy_changed = Signal(bool)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.ffmpeg: Path | None = None
        self.ffprobe: Path | None = None
        self.items: list[QueueItem] = []
        self.runner = JobRunner(self)
        self.pool = QThreadPool.globalInstance()
        self._probe_signals = _ProbeSignals()
        self._probe_signals.done.connect(self._on_probed)
        self._refresh_timer = QTimer(self, singleShot=True, interval=120)
        self._refresh_timer.timeout.connect(self.refresh)
        self._build_ui()
        self._connect_runner()

    # ================================================================= UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        split = QSplitter(Qt.Horizontal)
        root.addWidget(split, 1)

        # ---- lewa strona: kolejka, foldery, nazewnictwo
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 6, 0)
        btns = QHBoxLayout()
        self.btn_add = QPushButton("＋ " + S["add_files"])
        self.btn_add_dir = QPushButton("📁 " + S["add_folder"])
        self.btn_remove = QPushButton(S["remove"])
        self.btn_clear = QPushButton(S["clear"])
        for b in (self.btn_add, self.btn_add_dir):
            btns.addWidget(b)
        btns.addStretch(1)
        btns.addWidget(self.btn_remove)
        btns.addWidget(self.btn_clear)
        lv.addLayout(btns)
        self.table = FileTable()
        lv.addWidget(self.table, 1)
        self.btn_add.clicked.connect(self.add_files_dialog)
        self.btn_add_dir.clicked.connect(self.add_folder_dialog)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear.clicked.connect(self.clear_queue)
        self.table.files_dropped.connect(self.add_paths)
        self.table.cellDoubleClicked.connect(self._rename_row)
        self.table.itemSelectionChanged.connect(self.schedule_refresh)

        folders = QGridLayout()
        self.src_edit = QLineEdit(self.settings.get_path(f"{self.kind}_source"))
        self.dst_edit = QLineEdit(self.settings.get_path(f"{self.kind}_target"))
        b_src, b_dst = QPushButton(S["browse"]), QPushButton(S["browse"])
        b_src.clicked.connect(lambda: self._browse(self.src_edit))
        b_dst.clicked.connect(lambda: self._browse(self.dst_edit))
        self.chk_next = QCheckBox(S["next_to_source"])
        self.chk_next.setChecked(self.settings.data["general"]["next_to_source"].get(self.kind, False))
        folders.addWidget(QLabel(S["source_folder"]), 0, 0)
        folders.addWidget(self.src_edit, 0, 1)
        folders.addWidget(b_src, 0, 2)
        folders.addWidget(QLabel(S["target_folder"]), 1, 0)
        folders.addWidget(self.dst_edit, 1, 1)
        folders.addWidget(b_dst, 1, 2)
        folders.addWidget(self.chk_next, 2, 1)
        lv.addLayout(folders)
        self.dst_edit.textChanged.connect(self.schedule_refresh)
        self.chk_next.toggled.connect(self._on_next_toggled)
        self.dst_edit.setEnabled(not self.chk_next.isChecked())

        lv.addWidget(self._build_naming())
        split.addWidget(left)

        # ---- prawa strona: ustawienia podklasy
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel = self.build_settings_panel()
        scroll.setWidget(panel)
        scroll.setMinimumWidth(460)
        split.addWidget(scroll)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)

        # ---- dół: postęp i przyciski
        bottom = QHBoxLayout()
        prog = QGridLayout()
        self.lbl_cur = QLabel(S["current_file"])
        self.lbl_cur.setObjectName("muted")
        self.pb_cur = QProgressBar()
        self.pb_all = QProgressBar()
        self.lbl_eta_cur = QLabel("")
        self.lbl_eta_all = QLabel("")
        for lbl in (self.lbl_eta_cur, self.lbl_eta_all):
            lbl.setMinimumWidth(130)
            lbl.setObjectName("muted")
        all_lbl = QLabel(S["whole_queue"])
        all_lbl.setObjectName("muted")
        prog.addWidget(self.lbl_cur, 0, 0)
        prog.addWidget(self.pb_cur, 0, 1)
        prog.addWidget(self.lbl_eta_cur, 0, 2)
        prog.addWidget(all_lbl, 1, 0)
        prog.addWidget(self.pb_all, 1, 1)
        prog.addWidget(self.lbl_eta_all, 1, 2)
        prog.setColumnStretch(1, 1)
        bottom.addLayout(prog, 1)
        self.btn_start = QPushButton("▶  " + S["start"])
        self.btn_start.setObjectName("start")
        self.btn_stop = QPushButton("■  " + S["stop"])
        self.btn_stop.setObjectName("stop")
        self.btn_stop.setEnabled(False)
        self.btn_open = QPushButton(S["open_target"])
        self.btn_open.setObjectName("stop")
        bottom.addWidget(self.btn_open)
        bottom.addWidget(self.btn_stop)
        bottom.addWidget(self.btn_start)
        root.addWidget(_hline())
        root.addLayout(bottom)
        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_open.clicked.connect(self.open_target)

    def _build_naming(self) -> QGroupBox:
        cfg = self.settings.data["naming"][self.kind]
        box = QGroupBox(S["naming"])
        g = QGridLayout(box)
        self.rb_suffix = QRadioButton(S["naming_suffix"])
        self.rb_pattern = QRadioButton(S["naming_pattern"])
        grp = QButtonGroup(box)
        grp.addButton(self.rb_suffix)
        grp.addButton(self.rb_pattern)
        (self.rb_pattern if cfg.get("mode") == "pattern" else self.rb_suffix).setChecked(True)
        self.ed_suffix = QLineEdit(cfg.get("suffix", "_ec"))
        self.ed_suffix.setMaximumWidth(120)
        self.ed_pattern = QLineEdit(cfg.get("pattern", ""))
        vars_lbl = QLabel(S["naming_vars"])
        vars_lbl.setObjectName("muted")
        vars_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_preview = QLabel("")
        self.lbl_preview.setObjectName("bignum")
        hint = QLabel(S["naming_rename_hint"])
        hint.setObjectName("muted")
        g.addWidget(self.rb_suffix, 0, 0)
        g.addWidget(self.ed_suffix, 0, 1, Qt.AlignLeft)
        g.addWidget(self.rb_pattern, 1, 0)
        g.addWidget(self.ed_pattern, 1, 1)
        g.addWidget(vars_lbl, 2, 0, 1, 2)
        g.addWidget(self.lbl_preview, 3, 0, 1, 2)
        g.addWidget(hint, 4, 0, 1, 2)
        g.setColumnStretch(1, 1)
        for w in (self.rb_suffix, self.rb_pattern):
            w.toggled.connect(self.schedule_refresh)
        for w in (self.ed_suffix, self.ed_pattern):
            w.textChanged.connect(self.schedule_refresh)
        return box

    # ================================================================= do nadpisania
    def build_settings_panel(self) -> QWidget:
        raise NotImplementedError

    def output_ext(self) -> str:
        raise NotImplementedError

    def naming_values(self, item: QueueItem, index: int) -> dict:
        return {"nr": f"{index + 1:02d}"}

    def update_estimates(self) -> None:
        """Uzupełnia item.est_mb i panel informacji."""

    def validate(self) -> list[str]:
        return []

    def make_jobs(self, items: list[QueueItem]) -> list[Job]:
        raise NotImplementedError

    def parallel_jobs(self) -> int:
        return 1

    def save_state(self) -> None:
        """Zapisuje ustawienia podklasy do self.settings (bez zapisu pliku)."""

    def set_encoders(self, available: set[str], hw: list[str], zscale: bool) -> None:
        """Wywoływane po wykryciu koderów."""

    # ================================================================= kolejka
    def set_ffmpeg(self, ffmpeg: Path, ffprobe: Path) -> None:
        self.ffmpeg, self.ffprobe = ffmpeg, ffprobe

    def _filter_text(self) -> str:
        exts = VIDEO_EXTS if self.file_kinds == {"video"} else VIDEO_EXTS | AUDIO_EXTS
        pattern = " ".join(f"*{e}" for e in sorted(exts))
        key = "media_filter_video" if self.file_kinds == {"video"} else "media_filter_audio"
        return f"{S[key].format(pattern)};;{S['all_files']}"

    def add_files_dialog(self):
        start = self.src_edit.text() or str(Path.home())
        files, _ = QFileDialog.getOpenFileNames(self, S["choose_files"], start, self._filter_text())
        if files:
            self.src_edit.setText(str(Path(files[0]).parent))
            self.add_paths([Path(f) for f in files])

    def add_folder_dialog(self):
        start = self.src_edit.text() or str(Path.home())
        d = QFileDialog.getExistingDirectory(self, S["choose_folder"], start)
        if d:
            self.src_edit.setText(d)
            self.add_paths([Path(d)])

    def add_paths(self, paths: list[Path]):
        if self.runner.busy:
            return
        files = collect_media_files(paths, self.file_kinds)
        known = {str(i.path).lower() for i in self.items}
        for f in files:
            if str(f).lower() in known:
                continue
            known.add(str(f).lower())
            item = QueueItem(path=f, status=S["status_probing"])
            self.items.append(item)
            self._append_row(item)
            if self.ffprobe:
                self.pool.start(_ProbeTask(item, self.ffprobe, self._probe_signals))
        if files and not self.src_edit.text():
            self.src_edit.setText(str(files[0].parent))
        self.schedule_refresh()

    def _append_row(self, item: QueueItem):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(len(COLS)):
            if c == C_PROG:
                pb = QProgressBar()
                pb.setRange(0, 1000)
                pb.setValue(0)
                pb.setTextVisible(False)
                self.table.setCellWidget(r, c, pb)
            else:
                it = QTableWidgetItem("")
                if c in (C_DUR, C_SIZE, C_EST):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, it)
        self._fill_row(r, item)

    def _fill_row(self, r: int, item: QueueItem):
        info = item.info
        self.table.item(r, C_NAME).setText(item.path.name)
        self.table.item(r, C_NAME).setToolTip(str(item.path))
        if info:
            self.table.item(r, C_FMT).setText((item.path.suffix[1:] or info.format_name).upper())
            self.table.item(r, C_DUR).setText(format_duration(info.duration))
            self.table.item(r, C_RES).setText(self.describe_source(info))
            self.table.item(r, C_SIZE).setText(format_size(info.size_mb))
        self.table.item(r, C_STATUS).setText(item.status)
        self.table.item(r, C_STATUS).setToolTip(item.status)

    def describe_source(self, info: MediaInfo) -> str:
        if info.has_video:
            hdr = " HDR" if info.hdr else ""
            return f"{info.width}×{info.height} {info.fps:.3g}p{hdr}"
        if info.has_audio:
            return f"{info.sample_rate / 1000:g} kHz"
        return "—"

    def _row_of(self, item: QueueItem) -> int:
        for i, it in enumerate(self.items):
            if it is item:
                return i
        return -1

    def _on_probed(self, item: QueueItem, info: MediaInfo):
        r = self._row_of(item)
        if r < 0:
            return
        item.info = info
        if info.error or info.duration <= 0 or not (info.has_video or info.has_audio):
            item.status = S["status_probe_error"]
            self.table.item(r, C_STATUS).setForeground(Qt.red)
        else:
            item.status = S["status_ready"]
        self._fill_row(r, item)
        if info.error:
            self.table.item(r, C_STATUS).setToolTip(info.error)
        self.schedule_refresh()

    def remove_selected(self):
        if self.runner.busy:
            return
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
            del self.items[r]
        self.schedule_refresh()

    def clear_queue(self):
        if self.runner.busy:
            return
        self.table.setRowCount(0)
        self.items.clear()
        self.schedule_refresh()

    def _rename_row(self, row: int, col: int):
        if self.runner.busy or not (0 <= row < len(self.items)):
            return
        item = self.items[row]
        current = item.custom_name or (item.out_path.stem if item.out_path else item.path.stem)
        text, ok = QInputDialog.getText(self, S["rename_title"], S["rename_prompt"], text=current)
        if ok:
            item.custom_name = naming.sanitize(text.strip()) if text.strip() else None
            self.schedule_refresh()

    def selected_item(self) -> QueueItem | None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        cands = [self.items[r] for r in rows if self.items[r].info and not self.items[r].info.error]
        if cands:
            return cands[0]
        return next((i for i in self.items if i.info and not i.info.error and i.info.duration > 0), None)

    def ready_items(self) -> list[QueueItem]:
        return [i for i in self.items
                if i.info and not i.info.error and i.info.duration > 0
                and (i.info.has_video or i.info.has_audio)]

    # ================================================================= nazwy i odświeżanie
    def schedule_refresh(self, *_):
        self._refresh_timer.start()

    def target_dir_for(self, item: QueueItem) -> Path | None:
        if self.chk_next.isChecked():
            return item.path.parent
        t = self.dst_edit.text().strip()
        return Path(t) if t else None

    def naming_mode(self) -> str:
        return "pattern" if self.rb_pattern.isChecked() else "suffix"

    def compute_outputs(self, overwrite: bool = False) -> None:
        reserved: set[str] = set()
        ext = self.output_ext()
        for idx, item in enumerate(self.items):
            d = self.target_dir_for(item)
            if not item.info or d is None:
                item.out_path = None
                continue
            stem = naming.output_stem(item.path, self.naming_mode(), self.ed_suffix.text(),
                                      self.ed_pattern.text(), self.naming_values(item, idx),
                                      item.custom_name)
            out = naming.build_output_path(item.path, d, stem, ext, overwrite, reserved)
            reserved.add(str(out).lower())
            item.out_path = out

    def refresh(self):
        self.update_estimates()
        self.compute_outputs()
        for r, item in enumerate(self.items):
            self.table.item(r, C_EST).setText(format_size(item.est_mb) if item.info else "")
            out = item.out_path
            self.table.item(r, C_OUT).setText(out.name if out else "—")
            self.table.item(r, C_OUT).setToolTip(str(out) if out else S["no_target"])
        first = next((i for i in self.items if i.out_path), None)
        if first:
            self.lbl_preview.setText(S["naming_preview"].format(first.out_path.name))
        else:
            ex = naming.output_stem(Path("film.mov"), self.naming_mode(), self.ed_suffix.text(),
                                    self.ed_pattern.text(), {"nr": "01"})
            self.lbl_preview.setText(S["naming_preview"].format(f"{ex}.{self.output_ext()}"))

    def _browse(self, edit: QLineEdit):
        d = QFileDialog.getExistingDirectory(self, S["choose_folder"], edit.text() or str(Path.home()))
        if d:
            edit.setText(d)

    def _on_next_toggled(self, on: bool):
        self.dst_edit.setEnabled(not on)
        self.schedule_refresh()

    def open_target(self):
        item = self.selected_item()
        d = self.target_dir_for(item) if item else (Path(self.dst_edit.text())
                                                    if self.dst_edit.text() else None)
        if d and d.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    # ================================================================= uruchamianie
    def _connect_runner(self):
        r = self.runner
        r.job_started.connect(self._on_job_started)
        r.job_progress.connect(self._on_job_progress)
        r.job_finished.connect(self._on_job_finished)
        r.queue_progress.connect(self._on_queue_progress)
        r.queue_finished.connect(self._on_queue_finished)
        r.history_entry.connect(self.history_entry)

    def start(self):
        if self.runner.busy or not self.ffmpeg:
            return
        items = self.ready_items()
        if not items:
            QMessageBox.information(self, "EASY CODER", S["queue_empty"])
            return
        if not self.chk_next.isChecked() and not self.dst_edit.text().strip():
            QMessageBox.warning(self, "EASY CODER", S["no_target"])
            return
        errs = self.validate()
        if errs:
            QMessageBox.warning(self, "EASY CODER", S["invalid_settings"] + "\n\n• " + "\n• ".join(errs))
            return
        overwrite = False
        if self.settings.data["general"].get("overwrite") == "ask":
            self.compute_outputs(overwrite=True)
            existing = [i for i in items if i.out_path and i.out_path.exists()]
            if existing:
                ans = QMessageBox.question(
                    self, S["overwrite_title"], S["overwrite_ask"].format(len(existing)),
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.No)
                if ans == QMessageBox.Cancel:
                    return
                overwrite = ans == QMessageBox.Yes
        self.update_estimates()
        self.compute_outputs(overwrite=overwrite)
        items = [i for i in items if i.out_path]
        jobs = self.make_jobs(items)
        for item, job in zip(items, jobs):
            item.job = job
            item.status = S["status_ready"]
        for r, item in enumerate(self.items):
            pb = self.table.cellWidget(r, C_PROG)
            pb.setValue(0)
            self.table.item(r, C_STATUS).setText(item.status)
            self.table.item(r, C_STATUS).setForeground(self.palette().text())
        self.pb_cur.setValue(0)
        self.pb_all.setRange(0, 1000)
        self.pb_all.setValue(0)
        self._set_busy(True)
        self.runner.start(jobs, self.parallel_jobs())

    def stop(self):
        if self.runner.busy:
            self.runner.stop()

    def _set_busy(self, busy: bool):
        self.btn_start.setEnabled(not busy)
        self.btn_stop.setEnabled(busy)
        for w in (self.btn_add, self.btn_add_dir, self.btn_remove, self.btn_clear):
            w.setEnabled(not busy)
        self.busy_changed.emit(busy)

    def _item_for_job(self, job: Job) -> tuple[int, QueueItem | None]:
        for r, it in enumerate(self.items):
            if it.job is job:
                return r, it
        return -1, None

    def _on_job_started(self, job: Job):
        r, item = self._item_for_job(job)
        if item:
            item.status = S["status_running"]
            self.table.item(r, C_STATUS).setText(item.status)
            self.table.scrollToItem(self.table.item(r, C_NAME))
            self.lbl_cur.setText(job.info.path.name[:40])
            self.lbl_cur.setToolTip(str(job.info.path))

    def _on_job_progress(self, job: Job, frac: float, eta: float):
        r, item = self._item_for_job(job)
        if item:
            self.table.cellWidget(r, C_PROG).setValue(int(frac * 1000))
            self.table.item(r, C_STATUS).setText(f"{S['status_running']} {frac * 100:.0f}%")
        self.pb_cur.setRange(0, 1000)
        self.pb_cur.setValue(int(frac * 1000))
        self.lbl_eta_cur.setText(fmt_eta(eta))

    def _on_job_finished(self, job: Job):
        r, item = self._item_for_job(job)
        if not item:
            return
        item.status = job.message
        st = self.table.item(r, C_STATUS)
        st.setText(job.message)
        st.setToolTip(job.message)
        if job.status == Status.DONE:
            self.table.cellWidget(r, C_PROG).setValue(1000)
            st.setForeground(Qt.green)
        elif job.status == Status.ERROR:
            st.setForeground(Qt.red)
        else:
            self.table.cellWidget(r, C_PROG).setValue(0)

    def _on_queue_progress(self, frac: float, eta: float):
        self.pb_all.setValue(int(frac * 1000))
        self.lbl_eta_all.setText(fmt_eta(eta))

    def _on_queue_finished(self, ok: int, err: int, stopped: bool):
        self._set_busy(False)
        self.lbl_cur.setText(S["current_file"])
        self.lbl_eta_cur.setText("")
        self.lbl_eta_all.setText("")
        if not stopped:
            self.pb_all.setValue(1000)
        failed = [j for j in self.runner.jobs if j.status == Status.ERROR]
        # zadania przerwane wracają do stanu "oczekuje"
        for it in self.items:
            if it.job and it.job.status == Status.WAITING:
                it.status = S["status_ready"]
        self.schedule_refresh()
        self.queue_done.emit(ok, err, stopped, failed)

    # ================================================================= stan
    def save_common_state(self):
        st = self.settings
        st.set_path(f"{self.kind}_source", self.src_edit.text())
        st.set_path(f"{self.kind}_target", self.dst_edit.text())
        st.data["general"]["next_to_source"][self.kind] = self.chk_next.isChecked()
        st.data["naming"][self.kind] = {"mode": self.naming_mode(),
                                        "suffix": self.ed_suffix.text(),
                                        "pattern": self.ed_pattern.text()}

    def load_common_state(self):
        """Po imporcie ustawień – odśwież pola wspólne."""
        st = self.settings
        self.src_edit.setText(st.get_path(f"{self.kind}_source"))
        self.dst_edit.setText(st.get_path(f"{self.kind}_target"))
        self.chk_next.setChecked(st.data["general"]["next_to_source"].get(self.kind, False))
        cfg = st.data["naming"][self.kind]
        (self.rb_pattern if cfg.get("mode") == "pattern" else self.rb_suffix).setChecked(True)
        self.ed_suffix.setText(cfg.get("suffix", "_ec"))
        self.ed_pattern.setText(cfg.get("pattern", ""))
