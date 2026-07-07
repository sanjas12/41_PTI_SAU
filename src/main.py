import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# Добавляем путь к src если нужно
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Устанавливаем стиль
    app.setStyle('Fusion')
    
    # Устанавливаем тему (темную или светлую)
    # app.setStyleSheet("""
    #     QMainWindow { background-color: #2b2b2b; }
    #     QLabel { color: #ffffff; }
    # """)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
    