import sys

from PySide6.QtWidgets import QApplication, QStyle
from PySide6.QtGui import QColor, QPalette

from gui.application import App
from gui.login_dialog import LoginDialog


def light_palette() -> QPalette:
    """Светлая палитра, чтобы тёмная тема macOS не скрывала текст."""

    p = QPalette()

    for group in (
        QPalette.Active,
        QPalette.Inactive,
    ):
        p.setColor(group, QPalette.Window, QColor("#f3f5f7"))
        p.setColor(group, QPalette.WindowText, QColor("#2d3436"))
        p.setColor(group, QPalette.Base, QColor("#ffffff"))
        p.setColor(group, QPalette.AlternateBase, QColor("#f8f9fa"))
        p.setColor(group, QPalette.Text, QColor("#2d3436"))
        p.setColor(group, QPalette.PlaceholderText, QColor("#7f8c8d"))
        p.setColor(group, QPalette.Button, QColor("#ffffff"))
        p.setColor(group, QPalette.ButtonText, QColor("#2d3436"))
        p.setColor(group, QPalette.Highlight, QColor("#1976d2"))
        p.setColor(group, QPalette.HighlightedText, QColor("#ffffff"))
        p.setColor(group, QPalette.Link, QColor("#1976d2"))
        p.setColor(group, QPalette.BrightText, QColor("#ffffff"))
        p.setColor(group, QPalette.ToolTipBase, QColor("#ffffff"))
        p.setColor(group, QPalette.ToolTipText, QColor("#2d3436"))

    p.setColor(QPalette.Disabled, QPalette.Text, QColor("#9aa4af"))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#9aa4af"))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#9aa4af"))
    p.setColor(QPalette.Disabled, QPalette.Highlight, QColor("#c4cdd5"))
    p.setColor(
        QPalette.Disabled,
        QPalette.HighlightedText,
        QColor("#ffffff"),
    )

    return p


def main():

    qt_app = QApplication(sys.argv)

    qt_app.setPalette(light_palette())

    qt_app.setWindowIcon(
        qt_app.style().standardIcon(
            QStyle.SP_ComputerIcon
        )
    )

    login = LoginDialog()

    if login.exec() != LoginDialog.Accepted:
        sys.exit(0)

    window = App()

    window.show()

    sys.exit(
        qt_app.exec()
    )


if __name__ == "__main__":
    main()