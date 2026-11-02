"""Okno "Historia": komenda FFmpeg i wynik każdej konwersji."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QPlainTextEdit,
                               QPushButton, QSplitter, QVBoxLayout)

from ..jobqueue import HistoryStore
from ..strings import S


class HistoryDialog(QDialog):
    def __init__(self, store: HistoryStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle(S["history_title"])
        self.resize(1000, 600)
        lay = QVBoxLayout(self)
        split = QSplitter(Qt.Horizontal)
        self.list = QListWidget()
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.NoWrap)
        split.addWidget(self.list)
        split.addWidget(self.text)
        split.setStretchFactor(1, 2)
        lay.addWidget(split, 1)
        row = QHBoxLayout()
        b_copy = QPushButton(S["history_copy"])
        b_clear = QPushButton(S["history_clear"])
        b_close = QPushButton(S["history_close"])
        row.addWidget(b_copy)
        row.addWidget(b_clear)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        b_copy.clicked.connect(self._copy)
        b_clear.clicked.connect(self._clear)
        b_close.clicked.connect(self.accept)
        self.list.currentRowChanged.connect(self._show)
        self.reload()

    def reload(self):
        self.list.clear()
        for e in reversed(self.store.entries):
            mark = "✔" if e.get("ok") else "✖"
            name = e.get("input", "").replace("\\", "/").split("/")[-1]
            it = QListWidgetItem(f"{mark}  {e.get('time', '')[5:16].replace('T', ' ')}  {name}")
            it.setForeground(Qt.green if e.get("ok") else Qt.red)
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.text.clear()

    def _entry(self, row: int) -> dict | None:
        if row < 0:
            return None
        return list(reversed(self.store.entries))[row]

    def _show(self, row: int):
        e = self._entry(row)
        if not e:
            return
        status = S["history_ok"] if e.get("ok") else S["history_fail"]
        parts = [f"[{status}] {e.get('message', '')}", "",
                 f"Wejście:  {e.get('input')}", f"Wyjście:  {e.get('output')}", "",
                 "Komenda FFmpeg:"] + e.get("commands", []) + ["", "Log FFmpeg:", e.get("log", "")]
        self.text.setPlainText("\n".join(parts))

    def _copy(self):
        e = self._entry(self.list.currentRow())
        if e:
            QGuiApplication.clipboard().setText("\n".join(e.get("commands", [])))

    def _clear(self):
        self.store.clear()
        self.reload()
