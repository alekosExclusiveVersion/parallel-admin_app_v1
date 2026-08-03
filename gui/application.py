from PySide6.QtWidgets import QMainWindow
from gui.main_window import MainWindow
from common.version import APP_VERSION


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Parallel Admin v{APP_VERSION}")
        self.setMinimumSize(1200, 700)

        self.ui = MainWindow(self)
        self.setCentralWidget(self.ui)