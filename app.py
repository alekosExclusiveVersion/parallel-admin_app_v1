import sys
from PySide6.QtWidgets import QApplication
from gui.application import App

def main():
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()