from PyQt5.QtWidgets import (QWidget, QGroupBox, QGridLayout, QHBoxLayout,
                             QVBoxLayout, QLabel, QLineEdit, QSpinBox,
                             QPushButton, QComboBox, QCheckBox, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class ConnectionPanel(QGroupBox):
    """Панель для подключения к ПЛК через Modbus TCP"""
    
    # Сигналы для внешнего использования
    connected = pyqtSignal(bool)  # True - подключено, False - отключено
    connection_changed = pyqtSignal(dict)  # Параметры подключения
    
    def __init__(self, parent=None):
        super().__init__("🔌 Подключение", parent)
        
        # ИНИЦИАЛИЗИРУЕМ АТРИБУТЫ ДО ВЫЗОВА setup_ui()
        self._is_connected = False
        self._connection_params = {
            'host': '192.168.0.20',
            'port': 502,
            'unit_id': 1
        }
        
        # Список сохраненных подключений (для быстрого выбора)
        self.saved_connections = [
            {'name': 'Simulator', 'host': '127.0.0.1', 'port': 502, 'unit_id': 1},
            {'name': 'PLC-1', 'host': '192.168.0.20', 'port': 502, 'unit_id': 1},
        ]
        
        # ТЕПЕРЬ ВЫЗЫВАЕМ setup_ui()
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Основная сетка параметров
        grid = QGridLayout()
        
        # Быстрый выбор сохраненных подключений
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("-- Выберите сохраненное --")
        for conn in self.saved_connections:
            self.preset_combo.addItem(f"{conn['name']} ({conn['host']}:{conn['port']})")
        grid.addWidget(QLabel("Быстрый выбор:"), 0, 0)
        grid.addWidget(self.preset_combo, 0, 1, 1, 2)
        
        # IP Address
        grid.addWidget(QLabel("IP:"), 1, 0)
        self.ip_edit = QLineEdit("192.168.0.20")
        self.ip_edit.setPlaceholderText("Введите IP адрес")
        self.ip_edit.setMaximumWidth(150)
        grid.addWidget(self.ip_edit, 1, 1)
        
        # Порт
        grid.addWidget(QLabel("Порт:"), 1, 2)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(502)
        self.port_spin.setMaximumWidth(80)
        grid.addWidget(self.port_spin, 1, 3)
        
        # Unit ID
        grid.addWidget(QLabel("Unit ID:"), 2, 0)
        self.unit_spin = QSpinBox()
        self.unit_spin.setRange(0, 255)
        self.unit_spin.setValue(1)
        self.unit_spin.setMaximumWidth(80)
        grid.addWidget(self.unit_spin, 2, 1)
        
        # Кнопки управления
        button_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("🔗 Подключиться")
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
        
        self.disconnect_btn = QPushButton("🔌 Отключиться")
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
        self.save_btn = QPushButton("💾 Сохранить")
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
        self.delete_btn = QPushButton("🗑 Удалить")
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
        grid.addLayout(button_layout, 3, 0, 1, 4)
        
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
        self.connection_time_label.setStyleSheet("color: #666666; font-size: 9px;")
        status_layout.addWidget(self.connection_time_label)
        
        grid.addLayout(status_layout, 4, 0, 1, 4)
        
        layout.addLayout(grid)
        
        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Дополнительная информация
        info_layout = QHBoxLayout()
        
        self.connection_info = QLabel("🔍 Не подключено")
        self.connection_info.setStyleSheet("color: #999999; font-size: 9px;")
        info_layout.addWidget(self.connection_info)
        
        info_layout.addStretch()
        
        self.retry_count_label = QLabel("Попыток: 0")
        self.retry_count_label.setStyleSheet("color: #999999; font-size: 9px;")
        info_layout.addWidget(self.retry_count_label)
        
        layout.addLayout(info_layout)
        
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
        self.setMaximumWidth(400)
        
    def setup_connections(self):
        """Настройка сигналов"""
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        self.disconnect_btn.clicked.connect(self.on_disconnect_clicked)
        self.save_btn.clicked.connect(self.on_save_clicked)
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        self.preset_combo.currentIndexChanged.connect(self.on_preset_selected)
        
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
            self.status_label.setText("❌ Введите IP адрес")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            return
            
        # Сохраняем параметры
        self._connection_params = {
            'host': host,
            'port': port,
            'unit_id': unit_id
        }
        
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
        
        if not host:
            return
            
        # Проверяем, есть ли уже такое подключение
        for conn in self.saved_connections:
            if conn['host'] == host and conn['port'] == port:
                # Обновляем существующее
                conn['unit_id'] = unit_id
                self.update_preset_combo()
                return
                
        # Добавляем новое подключение
        name = f"PLC-{len(self.saved_connections) + 1}"
        self.saved_connections.append({
            'name': name,
            'host': host,
            'port': port,
            'unit_id': unit_id
        })
        self.update_preset_combo()
        
    def on_delete_clicked(self):
        """Удалить выбранное сохраненное подключение"""
        current_index = self.preset_combo.currentIndex()
        if current_index <= 0:  # Пропускаем первый элемент ("-- Выберите сохраненное --")
            return
            
        # Удаляем из списка
        del self.saved_connections[current_index - 1]
        self.update_preset_combo()
        
    def on_preset_selected(self, index):
        """Выбор сохраненного подключения"""
        if index <= 0:
            return
            
        conn = self.saved_connections[index - 1]
        self.ip_edit.setText(conn['host'])
        self.port_spin.setValue(conn['port'])
        self.unit_spin.setValue(conn['unit_id'])
        
    def on_params_changed(self):
        """Параметры подключения изменены"""
        if self._is_connected:
            # Если изменены параметры при подключении, сбрасываем состояние
            self._is_connected = False
            self.update_connection_status()
            
    def update_connection_status(self):
        """Обновить статус подключения"""
        if self._is_connected:
            # Подключено
            self.status_indicator.setStyleSheet("""
                QFrame {
                    background-color: #4CAF50;
                    border-radius: 8px;
                }
            """)
            self.status_label.setText("✅ Подключено")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            
            self.connection_info.setText(
                f"🔗 {self._connection_params['host']}:{self._connection_params['port']} "
                f"(Unit ID: {self._connection_params['unit_id']})"
            )
            self.connection_info.setStyleSheet("color: #4CAF50; font-size: 9px;")
            
            # Время подключения
            import datetime
            now = datetime.datetime.now().strftime("%H:%M:%S")
            self.connection_time_label.setText(f"Подключено в: {now}")
            
        else:
            # Отключено
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
            
            self.connection_info.setText("🔍 Не подключено")
            self.connection_info.setStyleSheet("color: #999999; font-size: 9px;")
            
            self.connection_time_label.setText("Время соединения: --")
            
    def update_preset_combo(self):
        """Обновить выпадающий список сохраненных подключений"""
        self.preset_combo.clear()
        self.preset_combo.addItem("-- Выберите сохраненное --")
        for conn in self.saved_connections:
            self.preset_combo.addItem(f"{conn['name']} ({conn['host']}:{conn['port']})")
            
    def get_connection_params(self):
        """Получить текущие параметры подключения"""
        return {
            'host': self.ip_edit.text().strip(),
            'port': self.port_spin.value(),
            'unit_id': self.unit_spin.value()
        }
        
    def set_connection_status(self, connected: bool):
        """Установить статус подключения извне"""
        self._is_connected = connected
        self.update_connection_status()
        
    def log_connection_event(self, message: str, level: str = "info"):
        """Логировать событие подключения (будет связано с журналом)"""
        # Этот метод будет вызываться из главного окна
        pass