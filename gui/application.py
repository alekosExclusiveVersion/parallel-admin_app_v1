from PySide6.QtWidgets import QMainWindow
from gui.main_window import MainWindow


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parallel Admin v1.0")
        self.setMinimumSize(1200, 700)

        self.ui = MainWindow(self)
        self.setCentralWidget(self.ui)