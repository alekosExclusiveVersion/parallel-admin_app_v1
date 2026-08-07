from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_ICONS = {
    "done_all": (
        "M18,7l-1.41,-1.41 -6.34,6.34 1.41,1.41L18,7z"
        "M22.24,5.59L11.66,16.17 7.48,12l-1.41,1.41L11.66,19l12,-12 -1.42,-1.41z"
        "M0.41,13.41L6,19l1.41,-1.41L1.83,12 0.41,13.41z"
    ),
    "close": (
        "M19,6.41L17.59,5 12,10.59 6.41,5 5,6.41 10.59,12 "
        "5,17.59 6.41,19 12,13.41 17.59,19 19,17.59 13.41,12z"
    ),
    "swap_horiz": (
        "M6.99,11L3,15l3.99,4v-3H14v-2H6.99v-3z"
        "M21,9l-3.99,-4v3H10v2h7.01v3L21,9z"
    ),
    "delete_outline": (
        "M6,19c0,1.1 0.9,2 2,2h8c1.1,0 2,-0.9 2,-2V7H6v12z"
        "M19,4h-3.5l-1,-1h-5l-1,1H5v2h14V4z"
    ),
    "content_copy": (
        "M16,1H4C2.9,1 2,1.9 2,3v14h2V3h12V1z"
        "M19,5H8c-1.1,0 -2,0.9 -2,2v14c0,1.1 0.9,2 2,2h11c1.1,0 2,-0.9 2,-2V7c0,-1.1 -0.9,-2 -2,-2z"
        "M19,21H8V7h11v14z"
    ),
    "download": (
        "M19,9h-4V3H9v6H5l7,7 7,-7z"
        "M5,18v2h14v-2H5z"
    ),
    "refresh": (
        "M17.65,6.35C16.2,4.9 14.21,4 12,4c-4.42,0 -7.99,3.58 -7.99,8s3.57,8 7.99,8"
        "c3.73,0 6.84,-2.55 7.73,-6h-2.08c-0.82,2.33 -3.04,4 -5.65,4 -3.31,0 -6,-2.69 "
        "-6,-6s2.69,-6 6,-6c1.66,0 3.14,0.69 4.22,1.78L13,11h7V4l-2.35,2.35z"
    ),
    "play_arrow": (
        "M8,5v14l11,-7z"
    ),
    "edit": (
        "M3,17.25V21h3.75L17.81,9.94l-3.75,-3.75L3,17.25z "
        "M20.71,7.04c0.39,-0.39 0.39,-1.02 0,-1.41l-2.34,-2.34"
        "c-0.39,-0.39 -1.02,-0.39 -1.41,0l-1.83,1.83 3.75,3.75 1.83,-1.83z"
    ),
    "check_circle": (
        "M12,2C6.48,2 2,6.48 2,12s4.48,10 10,10 10,-4.48 10,-10S17.52,2 12,2z "
        "M10,17l-5,-5 1.41,-1.41L10,14.17l7.59,-7.59L19,8l-9,9z"
    ),
    "stop": (
        "M6,6h12v12H6z"
    ),
    "dns": (
        "M4,13h16c1.1,0 2,0.9 2,2v5c0,1.1 -0.9,2 -2,2H4c-1.1,0 -2,-0.9 -2,-2v-5"
        "c0,-1.1 0.9,-2 2,-2z M6.5,17.5c-1.1,0 -2,0.9 -2,2s0.9,2 2,2 2,-0.9 2,-2"
        " -0.9,-2 -2,-2z M4,2h16c1.1,0 2,0.9 2,2v5c0,1.1 -0.9,2 -2,2H4c-1.1,0 "
        "-2,-0.9 -2,-2V4c0,-1.1 0.9,-2 2,-2z M6.5,6.5c-1.1,0 -2,0.9 -2,2"
        "s0.9,2 2,2 2,-0.9 2,-2 -0.9,-2 -2,-2z"
    ),
    "storage": (
        "M20,4H4C2.9,4 2.01,4.9 2.01,6L2,18c0,1.1 0.9,2 2,2h16c1.1,0 "
        "2,-0.9 2,-2V6c0,-1.1 -0.9,-2 -2,-2z M4,9h16v2H4V9z M4,13h16v2H4V13z"
    ),
    "grid_on": (
        "M4,8h4V4H4V8z M10,8h4V4h-4V8z M16,8h4V4h-4V8z M4,14h4v-4H4V14z "
        "M10,14h4v-4h-4V14z M16,14h4v-4h-4V14z M4,20h4v-4H4V20z "
        "M10,20h4v-4h-4V20z M16,20h4v-4h-4V20z"
    ),
    "app_icon": (
        "M3,5C3,3.9 3.9,3 5,3h14c1.1,0 2,0.9 2,2v14c0,1.1 -0.9,2 -2,2"
        "H5c-1.1,0 -2,-0.9 -2,-2V5z M5,5v3h14V5H5z M5,10v3h14v-3H5z"
        "M5,15v4h14v-4H5z M12,12l3,3 -1.5,0.5 0.5,1.5 -3,-3 1,-2z"
    ),
    "add": (
        "M19,13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"
    ),
}


def icon(name: str, size: int = 16, color: str = "#475569") -> QIcon:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" '
        'viewBox="0 0 24 24">'
        '<path fill="{c}" d="{d}"/></svg>'
    ).format(s=size, c=color, d=_ICONS[name])

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def app_icon() -> QIcon:
    """Иконка приложения для окна, Dock и переключателя macOS.

    Приоритет у ParallelsSQLAdmin.icns — той же иконки, что лежит в бандле
    и видна в Finder. На macOS QApplication.setWindowIcon() переопределяет
    иконку в Dock и переключателе, поэтому она должна совпадать с
    бандл-иконкой, иначе в Dock будет другой рисунок, чем в Finder.
    """
    icns_path = _ASSETS_DIR / "ParallelsSQLAdmin.icns"
    if icns_path.exists():
        icon = QIcon(str(icns_path))
        if not icon.isNull():
            return icon

    svg_path = _ASSETS_DIR / "app_icon.svg"
    png_path = _ASSETS_DIR / "app_icon.png"

    if svg_path.exists():
        renderer = QSvgRenderer(str(svg_path))
        pixmap = QPixmap(256, 256)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    if png_path.exists():
        return QIcon(str(png_path))

    # Фallback: монохромная встроенная иконка
    return icon("app_icon", size=64, color="#2563eb")
