import sys

from PySide6.QtWidgets import QApplication

from gui.application import App
from gui.login_dialog import LoginDialog


def main():

    qt_app = QApplication(sys.argv)

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