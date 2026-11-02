"""Punkt startowy aplikacji."""
from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from . import APP_NAME, APP_TITLE, __version__
from .platform_utils import IS_WINDOWS


class EasyCoderApp(QApplication):
    """QApplication z obsługą QFileOpenEvent – na macOS pliki upuszczone
    na ikonę w Docku / "Otwórz za pomocą" trafiają do kolejki."""

    def __init__(self, argv):
        super().__init__(argv)
        self.window = None
        self.pending: list = []

    def event(self, e):
        if e.type() == QEvent.FileOpen:
            from pathlib import Path
            p = Path(e.file())
            if self.window is not None and self.window.ffprobe:
                self.window.tabs.currentWidget().add_paths([p])
            else:
                self.pending.append(p)
            return True
        return super().event(e)


def main() -> int:
    # HiDPI / Retina: Qt6 skaluje automatycznie; ułamkowe skale bez zaokrąglania.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    if IS_WINDOWS:
        # Własna ikona na pasku zadań zamiast ikony pythona.
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EasyCoder.App")
        except Exception:
            pass
    app = EasyCoderApp(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)

    from .gui import theme
    from .gui.main_window import MainWindow
    theme.apply_dark_theme(app)
    app.setWindowIcon(theme.app_icon())

    win = MainWindow()
    app.window = win
    win.show()
    if not win.init_ffmpeg():
        return 1
    # Pliki podane w linii poleceń / upuszczone na ikonę aplikacji.
    from pathlib import Path
    args = [Path(a) for a in sys.argv[1:] if Path(a).exists()] + app.pending
    if args:
        win.tabs.currentWidget().add_paths(args)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
