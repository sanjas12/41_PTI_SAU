from typing import List

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class PLCRegisterView(QMainWindow):
    """Окно диагностики оперативных регистров МУ210-501."""

    def __init__(self, plc_interface, parent=None):
        super().__init__(parent)
        self.plc = plc_interface
        self.setWindowTitle("📊 Регистры МУ210-501")
        self.setGeometry(200, 200, 800, 600)

        self.setup_ui()
        self.setup_connections()

        # Таймер для автоматического обновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(500)  # 500ms

    def setup_ui(self):
        """Настройка интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Панель управления
        control_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.refresh_data)
        control_layout.addWidget(self.refresh_btn)

        self.auto_refresh_cb = QComboBox()
        self.auto_refresh_cb.addItems(
            ["Автообновление: Выкл", "500ms", "1s", "2s", "5s"]
        )
        self.auto_refresh_cb.currentIndexChanged.connect(self.on_auto_refresh_changed)
        control_layout.addWidget(self.auto_refresh_cb)

        control_layout.addStretch()

        self.status_label = QLabel("Статус: Обновлено")
        control_layout.addWidget(self.status_label)

        layout.addLayout(control_layout)

        # Таблица регистров
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Адрес", "Тип", "Значение (HEX)", "Значение (DEC)"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setFont(QFont("Consolas", 9))

        # Настройка стилей таблицы
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f5f5f5;
                gridline-color: #d0d0d0;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                padding: 4px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
        """)

        layout.addWidget(self.table)

        # Информация о регистрах
        info_layout = QHBoxLayout()

        self.info_label = QLabel("""
        📋 Карта оперативного обмена МУ210-501:
        3000-3007: значения AO1-AO8 (UINT16, 0...1000 ‰)
        3128-3135: состояние выходов
        3160-3167: режимы выходов
        """)
        self.info_label.setStyleSheet("color: #666666; font-size: 9px;")
        info_layout.addWidget(self.info_label)

        layout.addLayout(info_layout)

        # Стиль окна
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QComboBox {
                padding: 4px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)

    def setup_connections(self):
        """Настройка сигналов"""
        self.plc.error_occurred.connect(self.on_error)

    def on_auto_refresh_changed(self, index):
        """Изменен режим автообновления"""
        self.timer.stop()

        if index == 0:
            # Выключено
            return
        elif index == 1:
            interval = 500
        elif index == 2:
            interval = 1000
        elif index == 3:
            interval = 2000
        elif index == 4:
            interval = 5000
        else:
            return

        self.timer.start(interval)

    def refresh_data(self):
        """Обновить данные в таблице"""
        if not self.plc.modbus.is_connected():
            self.status_label.setText("❌ Нет соединения с МУ210")
            self.status_label.setStyleSheet("color: #f44336;")
            return

        try:
            # Читаем все регистры
            register_map = self.plc.get_register_map()

            # Получаем данные для аналоговых сигналов
            start_addr = register_map["analog_outputs"]["start"]
            end_addr = register_map["analog_outputs"]["end"]
            count = end_addr - start_addr + 1

            data = self.plc.read_plc_data(start_addr, count)

            if data:
                self.populate_table(data, start_addr)
                self.status_label.setText(f"✅ Обновлено: {len(data)} регистров")
                self.status_label.setStyleSheet("color: #4CAF50;")
            else:
                self.status_label.setText("❌ Ошибка чтения данных")
                self.status_label.setStyleSheet("color: #f44336;")

        except Exception as e:
            self.status_label.setText(f"❌ Ошибка: {e}")
            self.status_label.setStyleSheet("color: #f44336;")

    def populate_table(self, data: List[int], start_addr: int):
        """Заполнить таблицу данными"""
        self.table.setRowCount(len(data))

        for i, value in enumerate(data):
            address = start_addr + i

            # Адрес
            addr_item = QTableWidgetItem(str(address))
            addr_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, addr_item)

            type_item = QTableWidgetItem("UINT16")
            type_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 1, type_item)

            # HEX
            hex_item = QTableWidgetItem(f"0x{value:04X}")
            hex_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 2, hex_item)

            # DEC
            dec_item = QTableWidgetItem(str(value))
            dec_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 3, dec_item)

    def on_error(self, error_msg: str):
        """Обработчик ошибок"""
        self.status_label.setText(f"❌ {error_msg}")
        self.status_label.setStyleSheet("color: #f44336;")

    def closeEvent(self, event):  # noqa: N802 - имя метода задаётся Qt
        """Закрытие окна"""
        self.timer.stop()
        event.accept()
