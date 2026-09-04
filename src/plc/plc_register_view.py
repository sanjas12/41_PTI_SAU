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
    """Окно диагностики регистров выбранного Modbus-устройства."""

    def __init__(self, plc_interface, device_name: str, parent=None):
        super().__init__(parent)
        self.plc = plc_interface
        self.device_name = device_name
        self.setWindowTitle(f"📊 Регистры: {device_name}")
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
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Группа", "Адрес", "Тип", "Значение (HEX)", "Значение (DEC)"]
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

        self.info_label = QLabel()
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
        self._update_register_info()

    def _update_register_info(self):
        register_map = self.plc.get_register_map()
        descriptions = [
            f"{group['start']}-{group['end']}: {group['description']}"
            for group in register_map.values()
        ]
        self.info_label.setText(
            "📋 Карта регистров " + self.device_name + ":\n" + "\n".join(descriptions)
        )

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
            self.status_label.setText(f"❌ Нет соединения с {self.device_name}")
            self.status_label.setStyleSheet("color: #f44336;")
            return

        try:
            # Читаем все регистры
            register_map = self.plc.get_register_map()

            rows = []
            device_labels = (
                self.plc.get_device_labels()
                if hasattr(self.plc, "get_device_labels")
                else [self.device_name]
            )
            for module_index, device_label in enumerate(device_labels):
                for group_name, group in register_map.items():
                    start_addr = group["start"]
                    count = group["end"] - start_addr + 1
                    if hasattr(self.plc, "get_device_labels"):
                        data = self.plc.read_plc_data(
                            start_addr, count, module_index=module_index
                        )
                    else:
                        data = self.plc.read_plc_data(start_addr, count)
                    if data is None:
                        raise RuntimeError(
                            f"не удалось прочитать {device_label}, группа {group_name}"
                        )
                    value_type = "REAL" if "REAL" in group["description"] else "UINT16"
                    rows.extend(
                        (
                            f"{device_label} / {group_name}",
                            start_addr + index,
                            value_type,
                            value,
                        )
                        for index, value in enumerate(data)
                    )
            self.populate_table(rows)
            self.status_label.setText(f"✅ Обновлено: {len(rows)} регистров")
            self.status_label.setStyleSheet("color: #4CAF50;")

        except Exception as e:
            self.status_label.setText(f"❌ Ошибка: {e}")
            self.status_label.setStyleSheet("color: #f44336;")

    def populate_table(self, rows: List[tuple]):
        """Заполнить таблицу данными"""
        self.table.setRowCount(len(rows))

        for row, (group_name, address, value_type, value) in enumerate(rows):
            group_item = QTableWidgetItem(str(group_name))
            self.table.setItem(row, 0, group_item)

            addr_item = QTableWidgetItem(str(address))
            addr_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, addr_item)

            type_item = QTableWidgetItem(str(value_type))
            type_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, type_item)

            # HEX
            hex_item = QTableWidgetItem(f"0x{value:04X}")
            hex_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, hex_item)

            # DEC
            dec_item = QTableWidgetItem(str(value))
            dec_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, dec_item)

    def on_error(self, error_msg: str):
        """Обработчик ошибок"""
        self.status_label.setText(f"❌ {error_msg}")
        self.status_label.setStyleSheet("color: #f44336;")

    def closeEvent(self, event):  # noqa: N802 - имя метода задаётся Qt
        """Закрытие окна"""
        self.timer.stop()
        event.accept()
