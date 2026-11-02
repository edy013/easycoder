"""Ciemny motyw – identyczny na Windows i macOS (styl Fusion + arkusz QSS)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath,
                           QPalette, QPixmap)
from PySide6.QtWidgets import QApplication

from ..platform_utils import project_root

ACCENT = "#ff7a1a"
ACCENT_DARK = "#d9600a"
BG = "#17181c"
PANEL = "#202228"
PANEL_2 = "#2a2d35"
BORDER = "#363a44"
TEXT = "#e8e9ec"
MUTED = "#9aa0ab"

QUALITY_COLORS = {"excellent": "#3ddc84", "good": "#9bd65a", "medium": "#f5b83d", "poor": "#ff5c5c"}

QSS = f"""
QWidget {{ color: {TEXT}; font-size: 13px; }}
QMainWindow, QDialog {{ background: {BG}; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; background: {PANEL}; top: -1px; }}
QTabBar::tab {{ background: {PANEL_2}; color: {MUTED}; padding: 10px 34px; margin-right: 4px;
               border-top-left-radius: 8px; border-top-right-radius: 8px; font-weight: 600;
               font-size: 14px; letter-spacing: 1px; }}
QTabBar::tab:selected {{ background: {ACCENT}; color: #111; }}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 8px; margin-top: 14px; padding: 10px 8px 8px 8px;
            background: {PANEL}; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {ACCENT}; }}
QPushButton {{ background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 6px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: #5d626c; border-color: #2c2f36; }}
QPushButton:checked {{ background: {ACCENT}; color: #111; border-color: {ACCENT}; }}
QPushButton#start {{ background: {ACCENT}; color: #111; font-size: 16px; font-weight: 800;
                    padding: 12px 40px; border: none; }}
QPushButton#start:hover {{ background: #ff9442; }}
QPushButton#start:disabled {{ background: #5a3a22; color: #999; }}
QPushButton#stop {{ font-size: 14px; padding: 12px 22px; }}
QPushButton#chip {{ padding: 5px 10px; border-radius: 12px; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {BG}; border: 1px solid {BORDER};
    border-radius: 5px; padding: 5px 7px; selection-background-color: {ACCENT}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: {PANEL_2}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT}; selection-color: #111; }}
QDoubleSpinBox#bigsize {{ font-size: 22px; font-weight: 700; padding: 4px 8px; }}
QTableWidget {{ background: {BG}; alternate-background-color: #1c1e23; border: 1px solid {BORDER};
    border-radius: 6px; gridline-color: transparent; selection-background-color: #4a3424; }}
QTableWidget::item:selected {{ background: #4a3424; color: {TEXT}; }}
QHeaderView::section {{ background: {PANEL_2}; color: {MUTED}; border: none; padding: 6px;
    border-right: 1px solid {BORDER}; font-weight: 600; }}
QProgressBar {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 5px; text-align: center;
    height: 16px; color: {TEXT}; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QSlider::groove:horizontal {{ height: 8px; background: {BG}; border: 1px solid {BORDER}; border-radius: 4px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 4px; }}
QSlider::handle:horizontal {{ background: #fff; width: 22px; height: 22px; margin: -8px 0;
    border-radius: 11px; border: 2px solid {ACCENT}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QCheckBox, QRadioButton {{ spacing: 7px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#warn {{ color: #ffb347; }}
QLabel#error {{ color: #ff6b6b; }}
QLabel#title {{ font-size: 26px; font-weight: 900; letter-spacing: 3px; color: {TEXT}; }}
QLabel#subtitle {{ color: {MUTED}; font-size: 13px; }}
QLabel#bignum {{ font-size: 15px; font-weight: 700; }}
QMenuBar {{ background: {BG}; }}
QMenuBar::item:selected {{ background: {PANEL_2}; }}
QMenu {{ background: {PANEL_2}; border: 1px solid {BORDER}; }}
QMenu::item:selected {{ background: {ACCENT}; color: #111; }}
QToolTip {{ background: {PANEL_2}; color: {TEXT}; border: 1px solid {BORDER}; }}
QStatusBar {{ color: {MUTED}; }}
QTextEdit, QPlainTextEdit, QListWidget {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; }}
QSplitter::handle {{ background: transparent; }}
"""


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in [
        (QPalette.Window, BG), (QPalette.WindowText, TEXT), (QPalette.Base, BG),
        (QPalette.AlternateBase, PANEL), (QPalette.ToolTipBase, PANEL_2),
        (QPalette.ToolTipText, TEXT), (QPalette.Text, TEXT), (QPalette.Button, PANEL_2),
        (QPalette.ButtonText, TEXT), (QPalette.Highlight, ACCENT),
        (QPalette.HighlightedText, "#111111"), (QPalette.Link, ACCENT),
        (QPalette.PlaceholderText, "#6b707a"),
    ]:
        pal.setColor(role, QColor(color))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor("#5d626c"))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#5d626c"))
    app.setPalette(pal)
    app.setStyleSheet(QSS)


def paint_icon(size: int) -> QPixmap:
    """Ikona aplikacji rysowana kodem (używana też do wygenerowania .ico/.icns)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r = QRectF(size * 0.04, size * 0.04, size * 0.92, size * 0.92)
    grad = QLinearGradient(r.topLeft(), r.bottomRight())
    grad.setColorAt(0, QColor("#ff9a3d"))
    grad.setColorAt(1, QColor("#e2550b"))
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(r, size * 0.22, size * 0.22)
    # Symbol "kompresji": dwa trójkąty zbiegające się do środka.
    p.setBrush(QColor("#17181c"))
    c, w = size / 2, size * 0.26
    for sign in (-1, 1):
        path = QPainterPath()
        x0 = c + sign * size * 0.36
        path.moveTo(QPointF(x0, c - w))
        path.lineTo(QPointF(c + sign * size * 0.07, c))
        path.lineTo(QPointF(x0, c + w))
        path.closeSubpath()
        p.drawPath(path)
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(QRectF(c - size * 0.035, c - w, size * 0.07, 2 * w), size * 0.03, size * 0.03)
    p.end()
    return pm


def app_icon() -> QIcon:
    png = project_root() / "assets" / "icon.png"
    if png.exists():
        return QIcon(str(png))
    icon = QIcon()
    for s in (16, 32, 64, 128, 256, 512):
        icon.addPixmap(paint_icon(s))
    return icon


def title_font() -> QFont:
    f = QFont()
    f.setPointSize(20)
    f.setBold(True)
    return f
