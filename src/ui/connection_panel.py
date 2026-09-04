import json
import os
import sys
from typing import Any, Dict

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .collapsible_groupbox import CollapsibleGroupBox


class ConnectionPanel(CollapsibleGroupBox):
    """Панель выбора устройства и подключения по Modbus TCP."""

    DEVICE_LABELS = {
        "plc": "PLC Modicon Premium",
        "simulator": "Simulator",
        "owen": "ОВЕН МУ210-501",
    }

    # Сигналы для внешнего использования
    connected = pyqtSignal(bool)  # True - подключено, False - отключено
    connection_changed = pyqtSignal(dict)  # Параметры подключения

    # Имя файла для сохранения настроек
    CONFIG_FILE = "connections.json"

    def __init__(self, parent=None):
        super().__init__("Подключение", parent)

        # Путь к файлу конфигурации в папке пользователя
        self.config_path = self._get_config_path()

        # ИНИЦИАЛИЗИРУЕМ АТРИБУТЫ
        self._is_connected = False
        self._connection_params = {
            "device_type": "owen",
            "host": "192.168.1.99",
            "port": 502,
            "unit_id": 1,
        }

        # Список сохраненных подключений (загружаем из файла)
        self.saved_connections = []
        self._load_connections()

        # Если нет сохраненных, добавляем стандартные
        if not self.saved_connections:
            self.saved_connections = [
                {
                    "name": "PLC",
                    "device_type": "plc",
                    "host": "192.168.0.1",
                    "port": 502,
                    "unit_id": 1,
                },
                {
                    "name": "Simulator",
                    "device_type": "simulator",
                    "host": "127.0.0.1",
                    "port": 502,
                    "unit_id": 1,
                },
                {
                    "name": "МУ210-501",
                    "device_type": "owen",
                    "host": "192.168.1.99",
                    "port": 502,
                    "unit_id": 1,
                },
            ]
            self._save_connections()

        # Загружаем последнее использованное подключение
        self._load_last_connection()

        # ТЕПЕРЬ ВЫЗЫВАЕМ setup_ui
        self.setup_ui()
        self.setup_connections()

        # Применяем загруженные параметры
        self._apply_last_connection()

        # Сохраняем виджеты содержимого для сворачивания
        self._content_widgets = self.findChildren(QWidget)

    def _get_config_path(self):
        """Получить путь к файлу конфигурации"""
        home_dir = os.path.expanduser("~")
        config_dir = os.path.join(home_dir, ".pti_sau")

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        return os.path.join(config_dir, self.CONFIG_FILE)

    def _load_connections(self):
        """Загрузить сохраненные подключения из файла"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self.saved_connections = data.get("connections", [])
                    self._last_connection = data.get("last_connection", None)
                    return True
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")
        return False

    def _save_connections(self):
        """Сохранить подключения в файл"""
        try:
            data = {
                "connections": self.saved_connections,
                "last_connection": self._last_connection
                if hasattr(self, "_last_connection")
                else None,
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
            return False

    def _load_last_connection(self):
        """Загрузить последнее использованное подключение"""
        self._last_connection = None
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self._last_connection = data.get("last_connection")
        except Exception:
            pass

    def _apply_last_connection(self):
        """Применить последнее использованное подключение"""
        if self._last_connection:
            device_type = self._last_connection.get("device_type", "plc")
            index = self.device_combo.findData(device_type)
            self.device_combo.setCurrentIndex(max(0, index))
            self.ip_edit.setText(self._last_connection.get("host", "192.168.1.99"))
            self.port_spin.setValue(self._last_connection.get("port", 502))
            self.unit_spin.setValue(self._last_connection.get("unit_id", 1))

    def setup_ui(self):
        """Настройка интерфейса"""
        # Основной контейнер для содержимого
        content_widget = QWidget()
        layout = QVBoxLayout()
        content_widget.setLayout(layout)

        # Основная сетка параметров
        grid = QGridLayout()

        self.device_combo = QComboBox()
        for device_type, label in self.DEVICE_LABELS.items():
            self.device_combo.addItem(label, device_type)
        self.device_combo.setCurrentIndex(self.device_combo.findData("owen"))
        grid.addWidget(QLabel("Устройство:"), 0, 0)
        grid.addWidget(self.device_combo, 0, 1, 1, 2)

        # Быстрый выбор сохраненных подключений
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("-- Выберите сохраненное --")
        for conn in self.saved_connections:
            self.preset_combo.addItem(f"{conn['name']} ({conn['host']}:{conn['port']})")
        grid.addWidget(QLabel("Быстрый выбор:"), 1, 0)
        grid.addWidget(self.preset_combo, 1, 1, 1, 2)

        # IP Address
        self.ip_label = QLabel("IP-адреса:")
        grid.addWidget(self.ip_label, 2, 0)
        self.ip_edit = QLineEdit("192.168.1.99")
        self.ip_edit.setPlaceholderText("192.168.1.99, 192.168.1.100")
        self.ip_edit.setMaximumWidth(320)
        grid.addWidget(self.ip_edit, 2, 1)

        # Порт
        grid.addWidget(QLabel("Порт:"), 2, 2)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(502)
        self.port_spin.setMaximumWidth(80)
        grid.addWidget(self.port_spin, 2, 3)

        # Unit ID
        grid.addWidget(QLabel("Unit ID:"), 3, 0)
        self.unit_spin = QSpinBox()
        self.unit_spin.setRange(0, 255)
        self.unit_spin.setValue(1)
        self.unit_spin.setMaximumWidth(80)
        grid.addWidget(self.unit_spin, 3, 1)

        # Кнопки управления
        button_layout = QHBoxLayout()

        self.connect_btn = QPushButton("Подключиться")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        button_layout.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("Отключиться")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c62828;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        button_layout.addWidget(self.disconnect_btn)

        # Кнопка сохранить настройки
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.setMaximumWidth(100)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        button_layout.addWidget(self.save_btn)

        # Кнопка удалить настройки
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.setMaximumWidth(100)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff5722;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e64a19;
            }
        """)
        button_layout.addWidget(self.delete_btn)

        # Добавляем кнопки в сетку
        grid.addLayout(button_layout, 4, 0, 1, 4)

        # Статус подключения
        status_layout = QHBoxLayout()

        self.status_indicator = QFrame()
        self.status_indicator.setFixedSize(16, 16)
        self.status_indicator.setStyleSheet("""
            QFrame {
                background-color: #f44336;
                border-radius: 8px;
            }
        """)
        status_layout.addWidget(self.status_indicator)

        self.status_label = QLabel("Отключено")
        self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        # Время соединения
        self.connection_time_label = QLabel("Время соединения: --")
        self.connection_time_label.setStyleSheet("color: #666666;")
        status_layout.addWidget(self.connection_time_label)

        grid.addLayout(status_layout, 5, 0, 1, 4)

        layout.addLayout(grid)

        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Дополнительная информация
        info_layout = QHBoxLayout()

        self.connection_info = QLabel("Не подключено")
        self.connection_info.setStyleSheet("color: #999999;")
        info_layout.addWidget(self.connection_info)

        info_layout.addStretch()

        self.retry_count_label = QLabel("Попыток: 0")
        self.retry_count_label.setStyleSheet("color: #999999;")
        info_layout.addWidget(self.retry_count_label)

        # Информация о файле настроек
        config_info = QLabel(f"📁 {os.path.basename(self.config_path)}")
        config_info.setStyleSheet("color: #999999;")
        info_layout.addWidget(config_info)

        layout.addLayout(info_layout)

        # Добавляем контент в GroupBox
        self.setLayout(layout)

        self._content_widgets = []
        for child in self.findChildren(QWidget):
            if child != self:  # Не добавляем сам GroupBox
                self._content_widgets.append(child)

        # Стили группы
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #d0d0d0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: #fafafa;
            }
            QGroupBox::indicator {
                width: 18px;
                height: 18px;
            }
            QGroupBox::indicator:checked {
                image: none;
            }
            QGroupBox::indicator:unchecked {
                image: none;
            }
            QLabel {
                color: #333333;
            }
            QLineEdit, QSpinBox, QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 2px solid #4CAF50;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 16px;
            }
        """)

        # Размеры
        self.setMaximumWidth(500)

    def setup_connections(self):
        """Настройка сигналов"""
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        self.disconnect_btn.clicked.connect(self.on_disconnect_clicked)
        self.save_btn.clicked.connect(self.on_save_clicked)
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        self.preset_combo.currentIndexChanged.connect(self.on_preset_selected)
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)

        # Автоматическое обновление при изменении параметров
        self.ip_edit.textChanged.connect(self.on_params_changed)
        self.port_spin.valueChanged.connect(self.on_params_changed)
        self.unit_spin.valueChanged.connect(self.on_params_changed)

    def on_connect_clicked(self):
        """Обработчик нажатия кнопки подключения"""
        host = self.ip_edit.text().strip()
        port = self.port_spin.value()
        unit_id = self.unit_spin.value()

        if not host:
            self.status_label.setText("Введите IP адрес")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            return

        # Сохраняем параметры
        self._connection_params = {
            "device_type": self.device_combo.currentData(),
            "host": host,
            "port": port,
            "unit_id": unit_id,
        }

        # Сохраняем последнее подключение
        self._last_connection = self._connection_params.copy()
        self._save_connections()

        # Эмитируем сигнал подключения
        self.connection_changed.emit(self._connection_params)
        self.connected.emit(True)

        # Обновляем состояние
        self._is_connected = True
        self.update_connection_status()

    def on_disconnect_clicked(self):
        """Обработчик нажатия кнопки отключения"""
        self._is_connected = False
        self.connected.emit(False)
        self.update_connection_status()

    def on_save_clicked(self):
        """Сохранить текущие настройки"""
        host = self.ip_edit.text().strip()
        port = self.port_spin.value()
        unit_id = self.unit_spin.value()
        device_type = self.device_combo.currentData()

        if not host:
            QMessageBox.warning(self, "Предупреждение", "Введите IP адрес")
            return

        # Проверяем, есть ли уже такое подключение
        for conn in self.saved_connections:
            if (
                conn["host"] == host
                and conn["port"] == port
                and conn.get("device_type", "plc") == device_type
            ):
                # Обновляем существующее
                conn["unit_id"] = unit_id
                self._save_connections()
                self.update_preset_combo()
                QMessageBox.information(
                    self, "Успех", f"Подключение '{conn['name']}' обновлено"
                )
                return

        # Добавляем новое подключение
        name = f"{self.DEVICE_LABELS[device_type]}-{len(self.saved_connections) + 1}"
        self.saved_connections.append(
            {
                "name": name,
                "device_type": device_type,
                "host": host,
                "port": port,
                "unit_id": unit_id,
            }
        )
        self._save_connections()
        self.update_preset_combo()

        QMessageBox.information(self, "Успех", f"Подключение '{name}' сохранено")

    def on_delete_clicked(self):
        """Удалить выбранное сохраненное подключение"""
        current_index = self.preset_combo.currentIndex()
        if current_index <= 0:
            QMessageBox.warning(
                self, "Предупреждение", "Выберите подключение для удаления"
            )
            return

        conn_name = self.saved_connections[current_index - 1]["name"]
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить подключение '{conn_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            del self.saved_connections[current_index - 1]
            self._save_connections()
            self.update_preset_combo()
            QMessageBox.information(self, "Успех", f"Подключение '{conn_name}' удалено")

    def on_preset_selected(self, index):
        """Выбор сохраненного подключения"""
        if index <= 0:
            return

        conn = self.saved_connections[index - 1]
        device_type = conn.get("device_type", "plc")
        device_index = self.device_combo.findData(device_type)
        self.device_combo.setCurrentIndex(max(0, device_index))
        self.ip_edit.setText(conn["host"])
        self.port_spin.setValue(conn["port"])
        self.unit_spin.setValue(conn["unit_id"])

        self._last_connection = conn.copy()
        self._save_connections()

    def on_params_changed(self):
        """Параметры подключения изменены"""
        if self._is_connected:
            self._is_connected = False
            self.connected.emit(False)
            self.update_connection_status()

    def on_device_changed(self):
        """Подставить типовой адрес и отключить прежнее устройство."""
        device_type = self.device_combo.currentData()
        default_hosts = {
            "plc": "192.168.0.1",
            "simulator": "127.0.0.1",
            "owen": "192.168.1.99",
        }
        if device_type == "owen":
            self.ip_label.setText("IP-адреса:")
            self.ip_edit.setPlaceholderText("192.168.1.99, 192.168.1.100")
        else:
            self.ip_label.setText("IP:")
            self.ip_edit.setPlaceholderText("Введите IP адрес")
        self.ip_edit.setText(default_hosts[device_type])
        self.on_params_changed()

    def update_connection_status(self):
        """Обновить статус подключения"""
        if self._is_connected:
            self.status_indicator.setStyleSheet("""
                QFrame {
                    background-color: #4CAF50;
                    border-radius: 8px;
                }
            """)
            self.status_label.setText("Подключено")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)

            self.connection_info.setText(
                f"🔗 {self.DEVICE_LABELS[self._connection_params['device_type']]} · "
                f"{self._connection_params['host']}:{self._connection_params['port']} "
                f"(Unit ID: {self._connection_params['unit_id']})"
            )
            self.connection_info.setStyleSheet("color: #4CAF50;")

            import datetime

            now = datetime.datetime.now().strftime("%H:%M:%S")
            self.connection_time_label.setText(f"Подключено в: {now}")

        else:
            self.status_indicator.setStyleSheet("""
                QFrame {
                    background-color: #f44336;
                    border-radius: 8px;
                }
            """)
            self.status_label.setText("❌ Отключено")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")

            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)

            self.connection_info.setText("Не подключено")
            self.connection_info.setStyleSheet("color: #999999;")

            self.connection_time_label.setText("Время соединения: --")

    def update_preset_combo(self):
        """Обновить выпадающий список сохраненных подключений"""
        self.preset_combo.clear()
        self.preset_combo.addItem("-- Выберите сохраненное --")
        for conn in self.saved_connections:
            self.preset_combo.addItem(f"{conn['name']} ({conn['host']}:{conn['port']})")

    def get_connection_params(self) -> Dict[str, Any]:
        """Получить текущие параметры подключения"""
        return {
            "device_type": self.device_combo.currentData(),
            "host": self.ip_edit.text().strip(),
            "port": self.port_spin.value(),
            "unit_id": self.unit_spin.value(),
        }

    def set_connection_status(self, connected: bool):
        """Установить статус подключения извне"""
        self._is_connected = connected
        self.update_connection_status()

    def log_connection_event(self, message: str, level: str = "info"):
        """Логировать событие подключения (будет связано с журналом)"""
        # Этот метод будет вызываться из главного окна
        pass


def test_connection_panel():
    """Тестовая функция для проверки работы ConnectionPanel"""

    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ConnectionPanel")
    print("=" * 60)
    print(f"Файл настроек: {ConnectionPanel.CONFIG_FILE}")
    print("=" * 60)

    # Создаем приложение
    app = QApplication(sys.argv)

    # Создаем главное окно
    window = QWidget()
    window.setWindowTitle("Тест ConnectionPanel")
    window.setGeometry(200, 200, 450, 400)

    layout = QVBoxLayout()
    window.setLayout(layout)

    # Создаем панель
    panel = ConnectionPanel()
    layout.addWidget(panel)

    # Добавляем информационную метку
    info_label = QLabel("Нажмите 'Подключиться' для теста")
    info_label.setAlignment(Qt.AlignCenter)
    info_label.setStyleSheet("color: #666666; padding: 10px;")
    layout.addWidget(info_label)

    # Счетчик событий
    event_counter = QLabel("Событий: 0")
    event_counter.setAlignment(Qt.AlignCenter)
    event_counter.setStyleSheet("color: #999999;")
    layout.addWidget(event_counter)

    # Переменная для подсчета событий
    event_count = 0

    # Подключаем сигналы для теста
    def on_connected(status):
        nonlocal event_count
        event_count += 1
        event_counter.setText(f"Событий: {event_count}")
        print(f"[СИГНАЛ] connected({status})")
        if status:
            print("Подключение установлено")
        else:
            print("Подключение отключено")

    def on_connection_changed(params):
        nonlocal event_count
        event_count += 1
        event_counter.setText(f"Событий: {event_count}")
        print(f"[СИГНАЛ] connection_changed({params})")
        print(f"  📡 Хост: {params['host']}")
        print(f"  🔌 Порт: {params['port']}")
        print(f"  🆔 Unit ID: {params['unit_id']}")

    panel.connected.connect(on_connected)
    panel.connection_changed.connect(on_connection_changed)

    # Добавляем кнопку для ручного теста
    def manual_test():
        print("\n" + "=" * 60)
        print("РУЧНОЙ ТЕСТ")
        print("=" * 60)
        params = panel.get_connection_params()
        print(f"Текущие параметры: {params}")
        print(f"Сохраненных подключений: {len(panel.saved_connections)}")
        for i, conn in enumerate(panel.saved_connections):
            print(
                f"  {i + 1}. {conn['name']}: {conn['host']}:{conn['port']} (Unit: {conn['unit_id']})"
            )
        print(f"\nФайл настроек: {panel.config_path}")

    test_btn = QPushButton("🧪 Показать параметры")
    test_btn.clicked.connect(manual_test)
    layout.addWidget(test_btn)

    # Показываем окно
    window.show()

    print("\n✅ Тестовое окно открыто")
    print("📋 Инструкция:")
    print("  1. Нажмите 'Подключиться' - увидите сигналы")
    print("  2. Нажмите 'Отключиться' - статус изменится")
    print("  3. Выберите сохраненное подключение")
    print("  4. Нажмите 'Сохранить' - добавится новое")
    print("  5. Нажмите '🧪 Показать параметры' - увидите данные")
    print(f"\n📁 Настройки сохраняются в: {panel.config_path}")
    print("\nЗакройте окно для завершения теста")

    # Запускаем цикл обработки событий
    sys.exit(app.exec_())


if __name__ == "__main__":
    # Запускаем тест
    test_connection_panel()
