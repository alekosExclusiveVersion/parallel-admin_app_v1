import sys

from PySide6.QtWidgets import QApplication, QStyle

from gui.application import App
from gui.login_dialog import LoginDialog


def main():

    qt_app = QApplication(sys.argv)

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