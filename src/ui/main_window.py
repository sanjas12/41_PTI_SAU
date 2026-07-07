import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QGridLayout,
                             QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox,
                             QCheckBox, QSlider, QFrame)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette

# Используем абсолютные импорты
from src.core.signal_generator import SignalGenerator
from src.core.channel import AnalogChannel
from src.core.signal_types import SignalType


class ChannelWidget(QFrame):
    """Виджет для отображения одного канала"""
    
    def __init__(self, channel: AnalogChannel, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.setup_ui()
        self.update_display()
        
    def setup_ui(self):
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        
        layout = QVBoxLayout()
        layout.setSpacing(2)
        
        # Имя канала
        self.name_label = QLabel(f"Ch{self.channel.id+1}: {self.channel.name}")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFont(QFont("Arial", 8, QFont.Bold))
        layout.addWidget(self.name_label)
        
        # Значение
        self.value_label = QLabel("0.00")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.value_label.setStyleSheet("color: #0066CC;")
        layout.addWidget(self.value_label)
        
        # Индикатор активности (простая цветная точка)
        self.active_indicator = QLabel("●")
        self.active_indicator.setAlignment(Qt.AlignCenter)
        self.active_indicator.setStyleSheet("color: #00CC00; font-size: 14px;")
        layout.addWidget(self.active_indicator)
        
        # Включен/Выключен
        self.enabled_check = QCheckBox("Вкл")
        self.enabled_check.setChecked(self.channel.enabled)
        self.enabled_check.stateChanged.connect(self.on_enabled_changed)
        layout.addWidget(self.enabled_check, alignment=Qt.AlignCenter)
        
        self.setLayout(layout)
        self.setMinimumSize(100, 100)
        self.setMaximumSize(120, 120)
        
    def on_enabled_changed(self, state):
        self.channel.enabled = bool(state)
        if not state:
            self.value_label.setStyleSheet("color: #999999;")
            self.active_indicator.setStyleSheet("color: #999999; font-size: 14px;")
        else:
            self.value_label.setStyleSheet("color: #0066CC;")
            self.active_indicator.setStyleSheet("color: #00CC00; font-size: 14px;")
            
    def update_display(self):
        """Обновить отображение значения"""
        if self.channel.enabled:
            self.value_label.setText(f"{self.channel.current_value:.2f}")
            # Мигание индикатора при изменении
            if hasattr(self, '_last_value'):
                if abs(self.channel.current_value - self._last_value) > 0.1:
                    self.active_indicator.setStyleSheet("color: #FF6600; font-size: 14px;")
                    # Возвращаем цвет через 100ms
                    QTimer.singleShot(100, lambda: self.active_indicator.setStyleSheet("color: #00CC00; font-size: 14px;"))
            self._last_value = self.channel.current_value
        else:
            self.value_label.setText("Off")
            
    def update_channel(self, channel: AnalogChannel):
        """Обновить данные канала"""
        self.channel = channel
        self.name_label.setText(f"Ch{channel.id+1}: {channel.name}")
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
        
    def _setup_channels(self):
        """Создать 20 каналов"""
        signal_types = [SignalType.SINE, SignalType.SQUARE, 
                       SignalType.SAWTOOTH, SignalType.TRIANGLE]
        
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
        control_layout = QHBoxLayout()
        
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
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        control_layout.addWidget(self.start_btn)
        
        self.reset_btn = QPushButton("↺ Сброс")
        self.reset_btn.clicked.connect(self.reset_signals)
        control_layout.addWidget(self.reset_btn)
        
        # Статус
        self.status_label = QLabel("● Работает")
        self.status_label.setStyleSheet("color: #00CC00; font-weight: bold;")
        control_layout.addWidget(self.status_label)
        
        control_layout.addStretch()
        
        # Информация
        self.fps_label = QLabel("FPS: 0")
        self.fps_label.setStyleSheet("color: #666666;")
        control_layout.addWidget(self.fps_label)
        
        self.channels_count_label = QLabel("Каналы: 20")
        self.channels_count_label.setStyleSheet("color: #666666;")
        control_layout.addWidget(self.channels_count_label)
        
        main_layout.addLayout(control_layout)
        
        # Сетка каналов (скролл)
        from PyQt5.QtWidgets import QScrollArea
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        grid_widget = QWidget()
        grid_layout = QGridLayout()
        grid_widget.setLayout(grid_layout)
        
        # Добавляем виджеты каналов
        self.channel_widgets = []
        cols = 5
        for i, channel in enumerate(self.generator.channels):
            widget = ChannelWidget(channel)
            row = i // cols
            col = i % cols
            grid_layout.addWidget(widget, row, col)
            self.channel_widgets.append(widget)
            
        scroll_area.setWidget(grid_widget)
        main_layout.addWidget(scroll_area)
        
        # Нижняя информационная панель
        info_layout = QHBoxLayout()
        
        modbus_info = QLabel("Modbus TCP: 127.0.0.1:502 | Holding Registers: 40001-40040")
        modbus_info.setStyleSheet("color: #666666; font-size: 10px;")
        info_layout.addWidget(modbus_info)
        
        info_layout.addStretch()
        
        version_label = QLabel("Версия: 1.0.0")
        version_label.setStyleSheet("color: #999999; font-size: 9px;")
        info_layout.addWidget(version_label)
        
        main_layout.addLayout(info_layout)
        
        # Применяем общий стиль
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333333;
            }
        """)
        
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
        
        # Обновляем виджеты
        for i, widget in enumerate(self.channel_widgets):
            if i < len(self.generator.channels):
                widget.update_display()
                
        # Счетчик FPS
        self.frame_count += 1
        if self.frame_count >= 50:
            self.fps_label.setText(f"FPS: {self.frame_count * 2}")  # 50 кадров за 1 секунду?
            self.frame_count = 0