import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QGridLayout,
                             QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox,
                             QCheckBox, QSlider, QFrame, QSplitter, QTabWidget,
                             QScrollArea, QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QThreadPool
from PyQt5.QtGui import QFont, QColor, QPalette

from core.signal_generator import SignalGenerator
from core.channel import AnalogChannel
from core.signal_types import SignalType
from ui.plot_widget import PlotWindow
from ui.logger_window import LoggerWindow
from ui.connection_panel import ConnectionPanel
from ui.interval_control import IntervalControl
from modbus.modbus_client import ModbusClientWrapper
from modbus.worker import Runnable
from plc.plc_interface import PLCInterface
from plc.plc_register_view import PLCRegisterView
from _version import __full_version__


class ChannelWidget(QFrame):
    """Виджет для отображения и управления одним каналом"""
    
    channel_selected = pyqtSignal(int)
    channel_type_changed = pyqtSignal(int, str)  # channel_id, signal_type
    
    def __init__(self, channel: AnalogChannel, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.setup_ui()
        self.update_display()
        
    def setup_ui(self):
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 5px;
            }
            QFrame:hover {
                background-color: #f0f8ff;
                border: 2px solid #4CAF50;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Имя канала (кликабельно для выбора графика)
        self.name_label = QLabel(f"Ch{self.channel.id+1}: {self.channel.name}")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFont(QFont("Arial", 8, QFont.Bold))
        self.name_label.setStyleSheet("color: #0066CC; cursor: pointer;")
        self.name_label.mousePressEvent = self.on_name_click
        layout.addWidget(self.name_label)
        
        # Значение
        self.value_label = QLabel("0.00")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.value_label.setStyleSheet("color: #0066CC;")
        layout.addWidget(self.value_label)
        
        # Мини-индикатор (полоска)
        self.bar = QFrame()
        self.bar.setFixedHeight(4)
        self.bar.setStyleSheet("background-color: #4CAF50; border-radius: 2px;")
        layout.addWidget(self.bar)
        
        # НОВЫЙ ВЫПАДАЮЩИЙ СПИСОК ДЛЯ ВЫБОРА ТИПА СИГНАЛА
        self.type_combo = QComboBox()
        self.type_combo.addItems([st.name.capitalize() for st in SignalType])
        current_type = self.channel.signal_type.name.capitalize()
        index = self.type_combo.findText(current_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        self.type_combo.setStyleSheet("""
            QComboBox {
                font-size: 7px;
                padding: 1px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
            }
        """)
        layout.addWidget(self.type_combo)
        
        # Включен/Выключен
        self.enabled_check = QCheckBox("Вкл")
        self.enabled_check.setChecked(self.channel.enabled)
        self.enabled_check.stateChanged.connect(self.on_enabled_changed)
        self.enabled_check.setStyleSheet("font-size: 8px;")
        layout.addWidget(self.enabled_check, alignment=Qt.AlignCenter)
        
        self.setLayout(layout)
        self.setMinimumSize(100, 140)  # Увеличил высоту для combo
        self.setMaximumSize(120, 160)
        
    def on_name_click(self, event):
        self.channel_selected.emit(self.channel.id)
        
    def on_type_changed(self, text: str):
        """Изменен тип сигнала"""
        try:
            # Находим соответствующий SignalType
            signal_type = SignalType[text.upper()]
            self.channel.signal_type = signal_type
            # Обновляем отображение типа
            self.type_label.setText(str(signal_type))
            # Отправляем сигнал об изменении
            self.channel_type_changed.emit(self.channel.id, text)
        except KeyError:
            pass
        
    def on_enabled_changed(self, state):
        self.channel.enabled = bool(state)
        if not state:
            self.value_label.setStyleSheet("color: #999999;")
            self.bar.setStyleSheet("background-color: #cccccc; border-radius: 2px;")
            self.type_combo.setEnabled(False)
        else:
            self.value_label.setStyleSheet("color: #0066CC;")
            self.bar.setStyleSheet("background-color: #4CAF50; border-radius: 2px;")
            self.type_combo.setEnabled(True)
            
    def update_display(self):
        """Обновить отображение значения"""
        if self.channel.enabled:
            value = self.channel.current_value
            self.value_label.setText(f"{value:.1f}")
            # Обновляем полоску
            percent = (value - self.channel.min_value) / (self.channel.max_value - self.channel.min_value)
            bar_width = max(0, min(100, percent * 100))
            self.bar.setStyleSheet(f"""
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:{bar_width/100} #4CAF50,
                    stop:{bar_width/100} #e0e0e0, stop:1 #e0e0e0);
                border-radius: 2px;
            """)
        else:
            self.value_label.setText("Off")
            self.bar.setStyleSheet("background-color: #cccccc; border-radius: 2px;")
            
    def update_channel(self, channel: AnalogChannel):
        """Обновить данные канала"""
        self.channel = channel
        self.name_label.setText(f"Ch{channel.id+1}: {channel.name}")
        
        # Обновляем выпадающий список
        current_type = channel.signal_type.name.capitalize()
        index = self.type_combo.findText(current_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
            
        self.enabled_check.setChecked(channel.enabled)
        self.update_display()


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analog Signal Simulator v1.0")
        self.setGeometry(100, 100, 1200, 800)
        
        # Создаем генератор с 20 каналами
        self.generator = SignalGenerator()
        self._setup_channels()
        
        # Создаем Modbus клиент
        self.modbus = ModbusClientWrapper()
        
        # Создаем интерфейс для PLC
        self.plc_interface = PLCInterface(
            self.generator,
            self,
            debug=True
        )
        self.plc_interface.connection_status.connect(self.on_plc_connection_status)
        self.plc_interface.error_occurred.connect(lambda e: self.log(f"PLC Error: {e}", "error"))
        self.plc_interface.debug_data.connect(self.on_plc_debug_data)
        
        # Настраиваем UI
        self.setup_ui()
        
        # Таймер для обновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_signals)
        self.timer.start(10)  # 100 Гц
        
        # Счетчик
        self.frame_count = 0
        self.is_running = True
        self.plot_window = None
        self.logger_window = None
        self.plc_view = None
        
        # Потоковый пул для Modbus операций
        self.thread_pool = QThreadPool.globalInstance()
        
    def _setup_channels(self):
        """Создать 20 каналов с разными типами сигналов"""
        signal_types = [SignalType.SINE, SignalType.SQUARE, 
                       SignalType.SAWTOOTH, SignalType.TRIANGLE,
                       SignalType.RANDOM]
        
        for i in range(20):
            stype = signal_types[i % len(signal_types)]
            channel = AnalogChannel(
                id=i,
                name=f"Ch_{i+1:02d}",
                signal_type=stype,
                frequency=0.5 + (i % 10) * 0.3,
                amplitude=30 + (i % 7) * 10,
                offset=10 + (i % 9) * 5,
                min_value=0,
                max_value=100,
                enabled=True
            )
            self.generator.add_channel(channel)
            
    def setup_ui(self):
        """Настройка UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Левая панель - подключение и каналы
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        # Панель подключения к ПЛК
        self.connection_panel = ConnectionPanel()
        self.connection_panel.connection_changed.connect(self.on_connection_changed)
        self.connection_panel.connected.connect(self.on_connection_status_changed)
        left_layout.addWidget(self.connection_panel)
        
        # Панель управления
        control_panel = self._create_control_panel()
        left_layout.addWidget(control_panel)
        
        # Интервал обновления
        self.interval_control = IntervalControl()
        self.interval_control.interval_changed.connect(self.on_interval_changed)
        left_layout.addWidget(self.interval_control)
        
        # Сетка каналов
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #f5f5f5; }")
        
        grid_widget = QWidget()
        grid_layout = QGridLayout()
        grid_layout.setSpacing(3)
        grid_widget.setLayout(grid_layout)
        
        self.channel_widgets = []
        cols = 4
        for i, channel in enumerate(self.generator.channels):
            widget = ChannelWidget(channel)
            widget.channel_selected.connect(self.on_channel_selected)
            widget.channel_type_changed.connect(self.on_channel_type_changed)  # ← НОВЫЙ СИГНАЛ
            row = i // cols
            col = i % cols
            grid_layout.addWidget(widget, row, col)
            self.channel_widgets.append(widget)
            
        scroll.setWidget(grid_widget)
        left_layout.addWidget(scroll)
        
        main_layout.addWidget(left_panel)
        
        # Правая панель - информационная
        right_panel = self._create_info_panel()
        main_layout.addWidget(right_panel)
        
        # Устанавливаем пропорции
        main_layout.setStretchFactor(left_panel, 2)
        main_layout.setStretchFactor(right_panel, 1)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QLabel { color: #333333; }
        """)
        
    def _create_control_panel(self):
        """Создать панель управления"""
        panel = QGroupBox("Управление")
        layout = QHBoxLayout()
        panel.setLayout(layout)
        
        self.start_btn = QPushButton("⏸ Стоп")
        self.start_btn.clicked.connect(self.toggle_generation)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        layout.addWidget(self.start_btn)
        
        self.reset_btn = QPushButton("↺ Сброс")
        self.reset_btn.clicked.connect(self.reset_signals)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        layout.addWidget(self.reset_btn)
        
        self.plot_btn = QPushButton("📊 Графики")
        self.plot_btn.clicked.connect(self.open_plot_window)
        self.plot_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        layout.addWidget(self.plot_btn)
        
        self.logger_btn = QPushButton("📋 Журнал")
        self.logger_btn.clicked.connect(self.open_logger_window)
        self.logger_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7B1FA2; }
        """)
        layout.addWidget(self.logger_btn)
        
        self.plc_btn = QPushButton("📋 PLC Регистры")
        self.plc_btn.clicked.connect(self.open_plc_view)
        self.plc_btn.setStyleSheet("""
            QPushButton {
                background-color: #795548;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5D4037; }
        """)
        layout.addWidget(self.plc_btn)
        
        layout.addStretch()
        
        self.fps_label = QLabel("FPS: 0")
        self.fps_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.fps_label)
        
        return panel
        
    def _create_info_panel(self):
        """Создать информационную панель"""
        panel = QGroupBox("Информация")
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # Статус
        self.status_label = QLabel("● Работает")
        self.status_label.setStyleSheet("color: #00CC00; font-weight: bold; font-size: 12px;")
        layout.addWidget(self.status_label)
        
        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # Выбранный канал
        layout.addWidget(QLabel("Выбранный канал:"))
        self.selected_channel_label = QLabel("Канал 1")
        self.selected_channel_label.setStyleSheet("color: #0066CC; font-weight: bold;")
        layout.addWidget(self.selected_channel_label)
        
        # Тип сигнала выбранного канала
        layout.addWidget(QLabel("Тип сигнала:"))
        self.selected_type_label = QLabel("Sine")
        self.selected_type_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.selected_type_label)
        
        layout.addSpacing(10)
        
        # Статистика
        layout.addWidget(QLabel("Статистика:"))
        self.stats_label = QLabel("Каналов: 20\nАктивных: 20")
        self.stats_label.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(self.stats_label)
        
        layout.addStretch()
        
        # Версия
        version_label = QLabel("Версия: 1.3.0")
        version_label.setStyleSheet("color: #999999; font-size: 9px;")
        layout.addWidget(version_label)
        
        return panel
        
    def on_channel_type_changed(self, channel_id: int, type_name: str):
        """Изменен тип сигнала канала"""
        channel = self.generator.get_channel(channel_id)
        if channel:
            # Логируем изменение
            self.log(f"Канал {channel_id+1}: тип сигнала изменен на {type_name}", "info")
            
            # Если канал выбран для отображения, обновляем информацию
            if self.selected_channel_label.text().startswith(f"Канал {channel_id+1}"):
                self.selected_type_label.setText(type_name)
                
    def on_interval_changed(self, interval: float):
        """Изменен интервал обновления сигналов"""
        self.generator.set_update_interval(interval)
        freq = 1.0 / interval if interval > 0 else 0
        self.log(f"Интервал обновления изменен: {interval:.3f} с ({freq:.1f} Гц)", "info")
        
        # Обновляем статус
        self.status_label.setText(f"⏱ Интервал: {interval:.3f} с")
        self.status_label.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 12px;")
        
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.status_label.setText("● Работает"))
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #00CC00; font-weight: bold; font-size: 12px;"))
        
    def on_connection_changed(self, params):
        """Изменены параметры подключения"""
        host = params['host']
        port = params['port']
        unit_id = params['unit_id']
        
        try:
            self.modbus.configure(host, port, unit_id)
            self.log(f"Настроено подключение к {host}:{port} (Unit ID: {unit_id})", "info")
            self.plc_interface.configure(host, port, unit_id)
        except Exception as e:
            self.log(f"Ошибка настройки подключения: {e}", "error")
            
    def on_connection_status_changed(self, connected):
        """Изменен статус подключения"""
        if connected:
            def after_connect(ok):
                if ok:
                    self.log("Подключение установлено", "success")
                    self.connection_panel.set_connection_status(True)
                    self.plc_interface.connect()
                else:
                    self.log("Не удалось подключиться", "error")
                    self.connection_panel.set_connection_status(False)
                    
            self._submit(self.modbus.open, after_connect)
        else:
            self.modbus.close()
            self.plc_interface.disconnect()
            self.log("Соединение закрыто", "info")
            
    def _submit(self, fn, on_result, *args, **kwargs):
        """Выполнить асинхронную операцию"""
        job = Runnable(fn, *args, **kwargs)
        job.signals.result.connect(on_result)
        job.signals.error.connect(lambda e: self.log(f"Ошибка: {e}", "error"))
        self.thread_pool.start(job)
        
    def log(self, message: str, level: str = "info"):
        """Добавить сообщение в журнал"""
        if self.logger_window and self.logger_window.isVisible():
            self.logger_window.log(message, level)
        else:
            print(f"[{level.upper()}] {message}")
            
    def on_channel_selected(self, channel_id):
        channel = self.generator.get_channel(channel_id)
        if channel:
            self.selected_channel_label.setText(f"Канал {channel_id+1}: {channel.name}")
            self.selected_type_label.setText(str(channel.signal_type))
            self.status_label.setText(f"📊 Канал {channel_id+1}: {channel.name}")
            self.status_label.setStyleSheet("color: #0066CC; font-weight: bold; font-size: 12px;")
            
    def open_plot_window(self):
        if self.plot_window is None or not self.plot_window.isVisible():
            self.plot_window = PlotWindow(self.generator, self)
            self.plot_window.show()
        else:
            self.plot_window.raise_()
            self.plot_window.activateWindow()
            
    def open_logger_window(self):
        if self.logger_window is None or not self.logger_window.isVisible():
            self.logger_window = LoggerWindow(self)
            self.logger_window.show()
        else:
            self.logger_window.raise_()
            self.logger_window.activateWindow()
            
    def open_plc_view(self):
        if self.plc_view is None or not self.plc_view.isVisible():
            self.plc_view = PLCRegisterView(self.plc_interface, self)
            self.plc_view.show()
        else:
            self.plc_view.raise_()
            self.plc_view.activateWindow()
            
    def on_plc_connection_status(self, connected):
        if connected:
            self.log("PLC интерфейс активен", "success")
        else:
            self.log("PLC интерфейс отключен", "warning")
            
    def on_plc_debug_data(self, debug_info: dict):
        print(f"\n[PLC_DEBUG] Запись #{debug_info['write_count']} - "
              f"{len(debug_info.get('registers', []))} регистров записано")
        
        if self.logger_window and self.logger_window.isVisible():
            if hasattr(self.logger_window, 'log_debug_data'):
                self.logger_window.log_debug_data(debug_info)
        
    def toggle_generation(self):
        if self.is_running:
            self.timer.stop()
            self.start_btn.setText("▶ Старт")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #da190b; }
            """)
            self.status_label.setText("● Остановлен")
            self.status_label.setStyleSheet("color: #FF4444; font-weight: bold; font-size: 12px;")
            self.is_running = False
        else:
            self.timer.start(10)
            self.start_btn.setText("⏸ Стоп")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #45a049; }
            """)
            self.status_label.setText("● Работает")
            self.status_label.setStyleSheet("color: #00CC00; font-weight: bold; font-size: 12px;")
            self.is_running = True
            
    def reset_signals(self):
        for channel in self.generator.channels:
            channel.time = 0
            channel.current_value = 0
        self.update_signals()
            
    def update_signals(self):
        if not self.is_running:
            return
            
        self.generator.update(dt=0.01)
        
        active_count = 0
        for i, widget in enumerate(self.channel_widgets):
            if i < len(self.generator.channels):
                widget.update_display()
                if self.generator.channels[i].enabled:
                    active_count += 1
                    
        self.stats_label.setText(f"Каналов: 20\nАктивных: {active_count}")
        
        self.frame_count += 1
        if self.frame_count >= 50:
            self.fps_label.setText(f"FPS: {self.frame_count * 2}")
            self.frame_count = 0
            
    def closeEvent(self, event):
        if self.plot_window:
            self.plot_window.close()
        if self.logger_window:
            self.logger_window.close()
        if self.plc_view:
            self.plc_view.close()
        self.plc_interface.disconnect()
        self.modbus.close()
        event.accept()