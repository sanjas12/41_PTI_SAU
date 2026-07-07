import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QGridLayout,
                             QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox,
                             QCheckBox, QSlider, QFrame, QSplitter, QTabWidget,
                             QScrollArea, QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette

# Простые импорты (без src)
from core.signal_generator import SignalGenerator
from core.channel import AnalogChannel
from core.signal_types import SignalType
from ui.plot_widget import PlotWindow


class ChannelWidget(QFrame):
    """Виджет для отображения одного канала"""
    
    channel_selected = pyqtSignal(int)
    
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
        
        # Информация о типе сигнала
        self.type_label = QLabel(str(self.channel.signal_type))
        self.type_label.setAlignment(Qt.AlignCenter)
        self.type_label.setStyleSheet("color: #999999; font-size: 7px;")
        layout.addWidget(self.type_label)
        
        # Включен/Выключен
        self.enabled_check = QCheckBox("Вкл")
        self.enabled_check.setChecked(self.channel.enabled)
        self.enabled_check.stateChanged.connect(self.on_enabled_changed)
        self.enabled_check.setStyleSheet("font-size: 8px;")
        layout.addWidget(self.enabled_check, alignment=Qt.AlignCenter)
        
        self.setLayout(layout)
        self.setMinimumSize(100, 110)
        self.setMaximumSize(120, 130)
        
    def on_name_click(self, event):
        """Клик по имени канала - выбираем для графика"""
        self.channel_selected.emit(self.channel.id)
        
    def on_enabled_changed(self, state):
        self.channel.enabled = bool(state)
        if not state:
            self.value_label.setStyleSheet("color: #999999;")
            self.bar.setStyleSheet("background-color: #cccccc; border-radius: 2px;")
        else:
            self.value_label.setStyleSheet("color: #0066CC;")
            self.bar.setStyleSheet("background-color: #4CAF50; border-radius: 2px;")
            
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
        self.type_label.setText(str(channel.signal_type))
        self.enabled_check.setChecked(channel.enabled)
        self.update_display()


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analog Signal Simulator v1.0")
        self.setGeometry(100, 100, 900, 700)
        
        # Создаем генератор с 20 каналами
        self.generator = SignalGenerator()
        self._setup_channels()
        
        # Настраиваем UI
        self.setup_ui()
        
        # Таймер для обновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_signals)
        self.timer.start(10)  # 100 Гц
        
        # Счетчик для статистики
        self.frame_count = 0
        self.is_running = True
        self.plot_window = None  # Окно с графиками
        
    def _setup_channels(self):
        """Создать 20 каналов с разными сигналами"""
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
        """Настройка пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Верхняя панель управления
        control_layout = self._create_control_panel()
        main_layout.addLayout(control_layout)
        
        # Сетка каналов с прокруткой
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #f5f5f5; }")
        
        grid_widget = QWidget()
        grid_layout = QGridLayout()
        grid_layout.setSpacing(3)
        grid_widget.setLayout(grid_layout)
        
        # Добавляем виджеты каналов
        self.channel_widgets = []
        cols = 5
        for i, channel in enumerate(self.generator.channels):
            widget = ChannelWidget(channel)
            widget.channel_selected.connect(self.on_channel_selected)
            row = i // cols
            col = i % cols
            grid_layout.addWidget(widget, row, col)
            self.channel_widgets.append(widget)
            
        scroll.setWidget(grid_widget)
        main_layout.addWidget(scroll)
        
        # Нижняя информационная панель
        info_layout = self._create_info_panel()
        main_layout.addLayout(info_layout)
        
        # Применяем общий стиль
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333333;
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
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        
    def _create_control_panel(self):
        """Создать панель управления"""
        layout = QHBoxLayout()
        
        # Кнопки управления
        self.start_btn = QPushButton("⏸ Стоп")
        self.start_btn.clicked.connect(self.toggle_generation)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        layout.addWidget(self.start_btn)
        
        self.reset_btn = QPushButton("↺ Сброс")
        self.reset_btn.clicked.connect(self.reset_signals)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        layout.addWidget(self.reset_btn)
        
        # Кнопка открытия графиков
        self.plot_btn = QPushButton("📊 Графики")
        self.plot_btn.clicked.connect(self.open_plot_window)
        self.plot_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        layout.addWidget(self.plot_btn)
        
        # Статус
        self.status_label = QLabel("● Работает")
        self.status_label.setStyleSheet("color: #00CC00; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Информация
        self.fps_label = QLabel("FPS: 0")
        self.fps_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.fps_label)
        
        self.channels_count_label = QLabel("Каналы: 20")
        self.channels_count_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.channels_count_label)
        
        return layout
        
    def _create_info_panel(self):
        """Создать нижнюю информационную панель"""
        layout = QHBoxLayout()
        
        modbus_info = QLabel("🔌 Modbus TCP: 127.0.0.1:502 | Holding Registers: 40001-40040")
        modbus_info.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(modbus_info)
        
        layout.addStretch()
        
        # Информация о выбранном канале для графика
        self.selected_channel_label = QLabel("Выбран: Канал 1")
        self.selected_channel_label.setStyleSheet("color: #0066CC; font-size: 10px; font-weight: bold;")
        layout.addWidget(self.selected_channel_label)
        
        layout.addStretch()
        
        version_label = QLabel("Версия: 1.1.0")
        version_label.setStyleSheet("color: #999999; font-size: 9px;")
        layout.addWidget(version_label)
        
        return layout
        
    def on_channel_selected(self, channel_id):
        """Обработчик выбора канала для графика"""
        channel = self.generator.get_channel(channel_id)
        if channel:
            self.selected_channel_label.setText(f"Выбран: Канал {channel_id+1} - {channel.name}")
            self.status_label.setText(f"📊 Канал {channel_id+1}: {channel.name}")
            self.status_label.setStyleSheet("color: #0066CC; font-weight: bold;")
            
            # Если окно графиков открыто, обновляем его
            if self.plot_window and self.plot_window.isVisible():
                # Добавляем выбранный канал в список выбора в окне графиков
                # Находим элемент в списке
                for i in range(self.plot_window.channels_list.count()):
                    item = self.plot_window.channels_list.item(i)
                    if item.data(Qt.UserRole) == channel_id:
                        self.plot_window.channels_list.setCurrentItem(item)
                        break
        
    def open_plot_window(self):
        """Открыть окно с графиками"""
        if self.plot_window is None or not self.plot_window.isVisible():
            self.plot_window = PlotWindow(self.generator, self)
            self.plot_window.show()
        else:
            self.plot_window.raise_()
            self.plot_window.activateWindow()
        
    def toggle_generation(self):
        """Включить/выключить генерацию"""
        if self.is_running:
            self.timer.stop()
            self.start_btn.setText("▶ Старт")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
            """)
            self.status_label.setText("● Остановлен")
            self.status_label.setStyleSheet("color: #FF4444; font-weight: bold;")
            self.is_running = False
        else:
            self.timer.start(10)
            self.start_btn.setText("⏸ Стоп")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.status_label.setText("● Работает")
            self.status_label.setStyleSheet("color: #00CC00; font-weight: bold;")
            self.is_running = True
            
    def reset_signals(self):
        """Сбросить все сигналы"""
        for channel in self.generator.channels:
            channel.time = 0
            channel.current_value = 0
        self.update_signals()
            
    def update_signals(self):
        """Обновить сигналы и UI"""
        if not self.is_running:
            return
            
        # Обновляем значения
        self.generator.update(dt=0.01)
        
        # Обновляем виджеты каналов
        for i, widget in enumerate(self.channel_widgets):
            if i < len(self.generator.channels):
                widget.update_display()
                
        # Счетчик FPS
        self.frame_count += 1
        if self.frame_count >= 50:
            self.fps_label.setText(f"FPS: {self.frame_count * 2}")
            self.frame_count = 0
            
    def closeEvent(self, event):
        """Закрытие главного окна"""
        if self.plot_window:
            self.plot_window.close()
        event.accept()