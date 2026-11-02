"""Główne okno: nagłówek EASY CODER, zakładki, menu, wykrywanie FFmpeg i koderów."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
                               QMessageBox, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget)

from .. import APP_TITLE, __version__, encoders
from .. import platform_utils as pu
from ..ffmpeg_cmd import AudioSettings
from ..jobqueue import HistoryStore
from ..settings import Settings
from ..strings import S
from . import theme
from .audio_tab import AudioTab
from .history_dialog import HistoryDialog
from .video_tab import VideoTab


class _DetectSignals(QObject):
    done = Signal(dict)


class _DetectTask(QRunnable):
    def __init__(self, ffmpeg: Path, signals: _DetectSignals):
        super().__init__()
        self.ffmpeg, self.signals = ffmpeg, signals

    def run(self):
        self.signals.done.emit(encoders.detect(self.ffmpeg))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.history = HistoryStore()
        self.ffmpeg: Path | None = None
        self.ffprobe: Path | None = None
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(theme.app_icon())
        self.setAcceptDrops(True)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(14, 10, 14, 8)
        head = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(theme.app_icon().pixmap(44, 44))
        title = QLabel(APP_TITLE)
        title.setObjectName("title")
        sub = QLabel(S["app_subtitle"])
        sub.setObjectName("subtitle")
        head.addWidget(icon)
        head.addWidget(title)
        head.addSpacing(12)
        head.addWidget(sub, 0, Qt.AlignBottom)
        head.addStretch(1)
        lay.addLayout(head)

        self.tabs = QTabWidget()
        self.video = VideoTab(self.settings)
        self.audio = AudioTab(self.settings)
        self.tabs.addTab(self.video, "🎬  " + S["tab_video"])
        self.tabs.addTab(self.audio, "🎵  " + S["tab_audio"])
        lay.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        for tab in (self.video, self.audio):
            tab.history_entry.connect(self.history.add)
            tab.queue_done.connect(self._on_queue_done)
        self.video.extract_audio_requested.connect(self._extract_audio)
        self.tabs.setCurrentIndex(int(self.settings.data["window"].get("tab", 0)))

        self.tray = QSystemTrayIcon(theme.app_icon(), self)
        self.tray.setToolTip(APP_TITLE)
        self._build_menu()
        self._restore_geometry()
        self.statusBar().showMessage(S["hw_detecting"])

    # ================================================================= menu
    def _build_menu(self):
        mb = self.menuBar()
        m_file = mb.addMenu(S["menu_file"])
        a_add = QAction(S["add_files"] + "…", self, shortcut=QKeySequence.Open)
        a_add.triggered.connect(lambda: self.tabs.currentWidget().add_files_dialog())
        m_file.addAction(a_add)
        m_file.addSeparator()
        a_exp = QAction(S["act_export"], self, triggered=self._export)
        a_imp = QAction(S["act_import"], self, triggered=self._import)
        m_file.addAction(a_exp)
        m_file.addAction(a_imp)
        m_file.addSeparator()
        a_quit = QAction(S["act_quit"], self, shortcut=QKeySequence.Quit, triggered=self.close)
        a_quit.setMenuRole(QAction.QuitRole)   # macOS: menu aplikacji "Zakończ"
        m_file.addAction(a_quit)

        m_set = mb.addMenu(S["menu_settings"])
        self.m_presets = m_set.addMenu(S["user_presets"])
        self._rebuild_user_presets()
        a_save_p = QAction(S["act_save_preset"], self, triggered=self._save_preset)
        a_del_p = QAction(S["act_delete_preset"], self, triggered=self._delete_preset)
        m_set.addAction(a_save_p)
        m_set.addAction(a_del_p)
        m_set.addSeparator()
        g = self.settings.data["general"]
        a_sound = QAction(S["act_sound"], self, checkable=True, checked=g.get("done_sound", True))
        a_sound.toggled.connect(lambda v: g.__setitem__("done_sound", v))
        a_notify = QAction(S["act_notify"], self, checkable=True, checked=g.get("notify", True))
        a_notify.toggled.connect(lambda v: g.__setitem__("notify", v))
        m_set.addAction(a_sound)
        m_set.addAction(a_notify)
        m_ow = m_set.addMenu(S["act_overwrite"])
        grp = QActionGroup(self)
        for key, label in (("number", "act_ow_number"), ("ask", "act_ow_ask")):
            a = QAction(S[label], self, checkable=True, checked=g.get("overwrite") == key)
            a.toggled.connect(lambda on, k=key: on and g.__setitem__("overwrite", k))
            grp.addAction(a)
            m_ow.addAction(a)
        m_set.addSeparator()
        a_ff = QAction(S["act_ffmpeg"], self, triggered=self._choose_ffmpeg)
        a_ff.setMenuRole(QAction.NoRole)
        a_det = QAction(S["act_redetect"], self, triggered=lambda: self._detect(force=True))
        m_set.addAction(a_ff)
        m_set.addAction(a_det)

        m_view = mb.addMenu(S["menu_view"])
        a_hist = QAction(S["act_history"], self, shortcut=QKeySequence("Ctrl+H"),
                         triggered=self._show_history)
        m_view.addAction(a_hist)
        a_tab_v = QAction(S["tab_video"], self, shortcut=QKeySequence("Ctrl+1"),
                          triggered=lambda: self.tabs.setCurrentIndex(0))
        a_tab_a = QAction(S["tab_audio"], self, shortcut=QKeySequence("Ctrl+2"),
                          triggered=lambda: self.tabs.setCurrentIndex(1))
        m_view.addAction(a_tab_v)
        m_view.addAction(a_tab_a)

        m_help = mb.addMenu(S["menu_help"])
        a_about = QAction(S["act_about"], self, triggered=self._about)
        a_about.setMenuRole(QAction.AboutRole)  # macOS: "O programie" w menu aplikacji
        m_help.addAction(a_about)

    # ================================================================= FFmpeg i kodery
    def init_ffmpeg(self) -> bool:
        """Szuka FFmpeg; gdy brak – pyta o folder. Zwraca False, jeśli użytkownik zrezygnował."""
        custom = self.settings.get_path("ffmpeg_dir") or None
        found = pu.find_ffmpeg(custom)
        while not found:
            box = QMessageBox(QMessageBox.Warning, S["ffmpeg_missing_title"], S["ffmpeg_missing"],
                              QMessageBox.Cancel, self)
            choose = box.addButton(S["ffmpeg_choose"], QMessageBox.AcceptRole)
            box.exec()
            if box.clickedButton() is not choose:
                return False
            d = QFileDialog.getExistingDirectory(self, S["ffmpeg_choose"])
            if d:
                found = pu.find_ffmpeg(d)
                if found:
                    self.settings.set_path("ffmpeg_dir", d)
                else:
                    QMessageBox.warning(self, APP_TITLE, S["ffmpeg_invalid"])
        self._set_ffmpeg(*found)
        return True

    def _set_ffmpeg(self, ffmpeg: Path, ffprobe: Path):
        self.ffmpeg, self.ffprobe = ffmpeg, ffprobe
        for tab in (self.video, self.audio):
            tab.set_ffmpeg(ffmpeg, ffprobe)
        self._detect()

    def _choose_ffmpeg(self):
        d = QFileDialog.getExistingDirectory(self, S["ffmpeg_choose"],
                                             str(self.ffmpeg.parent) if self.ffmpeg else "")
        if not d:
            return
        found = pu.find_ffmpeg(d)
        if found and found[0].parent == Path(d):
            self.settings.set_path("ffmpeg_dir", d)
            self._set_ffmpeg(*found)
        else:
            QMessageBox.warning(self, APP_TITLE, S["ffmpeg_invalid"])

    def _detect(self, force: bool = False):
        """Wykrywanie koderów w tle; wynik buforowany per system i binarkę FFmpeg."""
        if not self.ffmpeg:
            return
        cache = self.settings.data.setdefault("encoder_cache", {}).get(self.settings.os, {})
        try:
            mtime = os.path.getmtime(self.ffmpeg)
        except OSError:
            mtime = 0
        if (not force and cache.get("ffmpeg") == str(self.ffmpeg)
                and cache.get("mtime") == mtime and cache.get("result")):
            self._on_detected(cache["result"], store=False)
            return
        self.statusBar().showMessage(S["hw_detecting"])
        self._det_signals = _DetectSignals()
        self._det_signals.done.connect(self._on_detected)
        self._det_mtime = mtime
        QThreadPool.globalInstance().start(_DetectTask(self.ffmpeg, self._det_signals))

    def _on_detected(self, result: dict, store: bool = True):
        if store:
            self.settings.data.setdefault("encoder_cache", {})[self.settings.os] = {
                "ffmpeg": str(self.ffmpeg), "mtime": self._det_mtime, "result": result}
        av = set(result.get("encoders", []))
        self.video.set_encoders(av, result.get("hw", []), result.get("zscale", False))
        hw = ", ".join(result.get("hw", [])) or S["encoders_none"]
        self.statusBar().showMessage(f"FFmpeg: {self.ffmpeg}   ·   {S['encoders_found'].format(hw)}")

    # ================================================================= akcje
    def _extract_audio(self, paths: list):
        if not paths:
            return
        self.audio.apply_settings(AudioSettings.from_dict(
            {**self.audio.current_settings().to_dict(),
             **({"fmt": "wav", "bit_depth": "24"} if self.video.current_settings().audio_codec == "pcm"
                else {"fmt": "aac", "bitrate": max(192, self.video.current_settings().audio_kbps)})}))
        self.audio.add_paths(paths)
        self.tabs.setCurrentWidget(self.audio)

    def _on_queue_done(self, ok: int, err: int, stopped: bool, failed: list):
        g = self.settings.data["general"]
        msg = S["stopped_msg"] if stopped else S["done_msg"].format(ok, err)
        if not stopped:
            if g.get("notify", True) and QSystemTrayIcon.isSystemTrayAvailable():
                self.tray.show()
                self.tray.showMessage(S["done_title"], msg, theme.app_icon(), 6000)
            if g.get("done_sound", True):
                pu.play_done_sound()
        self.statusBar().showMessage(msg, 15000)
        if failed:
            box = QMessageBox(QMessageBox.Warning, S["errors_title"],
                              S["errors_msg"].format(len(failed)), QMessageBox.Ok, self)
            box.setInformativeText("\n".join(f"• {j.info.path.name}: {j.message}" for j in failed))
            # Rozwijany pełny log FFmpeg ("Pokaż szczegóły…").
            box.setDetailedText("\n\n".join(f"===== {j.info.path.name} =====\n{j.log[-30000:]}"
                                            for j in failed))
            box.exec()
        self.save_settings()

    def _show_history(self):
        HistoryDialog(self.history, self).exec()

    def _about(self):
        QMessageBox.about(self, S["act_about"],
                          S["about"].format(__version__, self.ffmpeg or "—", self.settings.path))

    def _export(self):
        self.save_settings()
        path, _ = QFileDialog.getSaveFileName(self, S["act_export"],
                                              str(Path.home() / "EasyCoder-ustawienia.json"),
                                              "JSON (*.json)")
        if path:
            self.settings.export_to(Path(path))
            QMessageBox.information(self, APP_TITLE, S["export_done"].format(path))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, S["act_import"], str(Path.home()), "JSON (*.json)")
        if not path:
            return
        try:
            self.settings.import_from(Path(path))
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, APP_TITLE, S["import_error"].format(e))
            return
        from ..ffmpeg_cmd import VideoSettings
        self.video.apply_settings(VideoSettings.from_dict(self.settings.data.get("video", {})))
        self.audio.apply_settings(AudioSettings.from_dict(self.settings.data.get("audio", {})))
        for tab in (self.video, self.audio):
            tab.load_common_state()
        self._rebuild_user_presets()
        self.settings.save()
        QMessageBox.information(self, APP_TITLE, S["import_done"])

    # ---- presety użytkownika (zapisywane w ustawieniach, eksportowane razem z nimi)
    def _current_tab_kind(self) -> str:
        return "video" if self.tabs.currentWidget() is self.video else "audio"

    def _save_preset(self):
        kind = self._current_tab_kind()
        name, ok = QInputDialog.getText(self, S["act_save_preset"], S["preset_name_prompt"])
        if ok and name.strip():
            tab = self.video if kind == "video" else self.audio
            self.settings.data["presets"].setdefault(kind, {})[name.strip()] = \
                tab.current_settings().to_dict()
            self._rebuild_user_presets()
            self.save_settings()

    def _delete_preset(self):
        kind = self._current_tab_kind()
        names = list(self.settings.data["presets"].get(kind, {}))
        if not names:
            return
        name, ok = QInputDialog.getItem(self, S["act_delete_preset"], S["preset_name_prompt"],
                                        names, 0, False)
        if ok:
            self.settings.data["presets"][kind].pop(name, None)
            self._rebuild_user_presets()
            self.save_settings()

    def _rebuild_user_presets(self):
        self.m_presets.clear()
        for kind, tab, label in (("video", self.video, S["tab_video"]),
                                 ("audio", self.audio, S["tab_audio"])):
            for name, data in self.settings.data["presets"].get(kind, {}).items():
                a = QAction(f"{label}: {name}", self)
                a.triggered.connect(lambda _=False, t=tab, d=data: (t.apply_user_preset(d),
                                                                    self.tabs.setCurrentWidget(t)))
                self.m_presets.addAction(a)
        self.m_presets.setEnabled(bool(self.m_presets.actions()))

    # ================================================================= okno i zapis
    def _restore_geometry(self):
        w = self.settings.data.get("window", {})
        self.resize(int(w.get("w", 1380)), int(w.get("h", 860)))
        if w.get("max"):
            self.showMaximized()

    def save_settings(self):
        self.video.save_state()
        self.audio.save_state()
        self.settings.data["window"] = {"w": self.width(), "h": self.height(),
                                        "max": self.isMaximized(), "tab": self.tabs.currentIndex()}
        try:
            self.settings.save()
        except OSError:
            pass

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
        self.tabs.currentWidget().add_paths(paths)

    def closeEvent(self, e):
        busy = self.video.runner.busy or self.audio.runner.busy
        if busy:
            if QMessageBox.question(self, APP_TITLE, S["busy_close"]) != QMessageBox.Yes:
                e.ignore()
                return
            self.video.stop()
            self.audio.stop()
        self.save_settings()
        self.tray.hide()
        e.accept()
