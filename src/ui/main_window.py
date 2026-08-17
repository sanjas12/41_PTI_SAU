import sys
import json
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QGridLayout,
                             QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox,
                             QCheckBox, QSlider, QFrame, QSplitter, QTabWidget,
                             QScrollArea, QListWidget, QListWidgetItem,
                             QDialog, QDialogButtonBox, QFormLayout,
                             QLineEdit, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QThreadPool
from PyQt5.QtGui import QFont, QColor, QPalette

from core.signal_generator import SignalGenerator
from core.channel import AnalogChannel
from core.signal_types import SignalType
from ui.plot_widget import PlotWindow
from ui.logger_window import LoggerWindow
from ui.connection_panel import ConnectionPanel
from ui.control_panel import ControlPanel
from ui.interval_control import IntervalControl
from ui.collapsible_groupbox import CollapsibleGroupBox
from modbus.modbus_client import ModbusClientWrapper
from modbus.worker import Runnable
from plc.plc_interface import PLCInterface
from plc.plc_register_view import PLCRegisterView

# Импорты для сценариев - ВЫНОСИМ В КОНЕЦ ФАЙЛА
from scenario.scenario_model import Scenario, ScenarioStep
from scenario.scenario_engine import ScenarioEngine, ScenarioMode

from _version import __full_version__


class ChannelSettingsDialog(QDialog):
    """Диалог настроек канала"""
    
    def __init__(self, channel: AnalogChannel, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.setWindowTitle(f"Настройки канала {channel.id+1}: {channel.name}")
        self.setModal(True)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit(self.channel.name)
        form_layout.addRow("Имя канала:", self.name_edit)
        
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-10000, 10000)
        self.min_spin.setValue(self.channel.min_value)
        self.min_spin.setSingleStep(0.1)
        form_layout.addRow("Минимум:", self.min_spin)
        
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-10000, 10000)
        self.max_spin.setValue(self.channel.max_value)
        self.max_spin.setSingleStep(0.1)
        form_layout.addRow("Максимум:", self.max_spin)
        
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.01, 100)
        self.freq_spin.setValue(self.channel.frequency)
        self.freq_spin.setSingleStep(0.1)
        form_layout.addRow("Частота (Гц):", self.freq_spin)
        
        self.amp_spin = QDoubleSpinBox()
        self.amp_spin.setRange(0, 100)
        self.amp_spin.setValue(self.channel.amplitude)
        self.amp_spin.setSingleStep(1)
        form_layout.addRow("Амплитуда (%):", self.amp_spin)
        
        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-100, 100)
        self.offset_spin.setValue(self.channel.offset)
        self.offset_spin.setSingleStep(1)
        form_layout.addRow("Смещение (%):", self.offset_spin)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems([st.name.capitalize() for st in SignalType])
        current_type = self.channel.signal_type.name.capitalize()
        index = self.type_combo.findText(current_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        form_layout.addRow("Тип сигнала:", self.type_combo)
        
        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(self.channel.enabled)
        form_layout.addRow("Включен:", self.enabled_check)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setMinimumWidth(350)
        
    def get_settings(self) -> dict:
        """Получить измененные настройки"""
        return {
            'name': self.name_edit.text(),
            'min_value': self.min_spin.value(),
            'max_value': self.max_spin.value(),
            'frequency': self.freq_spin.value(),
            'amplitude': self.amp_spin.value(),
            'offset': self.offset_spin.value(),
            'signal_type': self.type_combo.currentText().upper(),
            'enabled': self.enabled_check.isChecked()
        }


class ChannelWidget(QFrame):
    """Виджет для отображения и управления одним каналом"""
    
    channel_selected = pyqtSignal(int)
    channel_type_changed = pyqtSignal(int, str)
    channel_settings_changed = pyqtSignal(int)
    
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
        
        self.name_label = QLabel(f"Ch{self.channel.id+1}: {self.channel.name}")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFont(QFont("Arial", 8, QFont.Bold))
        self.name_label.setStyleSheet("color: #0066CC; cursor: pointer;")
        self.name_label.mousePressEvent = self.on_name_click
        layout.addWidget(self.name_label)
        
        self.value_label = QLabel("0.00")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.value_label.setStyleSheet("color: #0066CC;")
        layout.addWidget(self.value_label)
        
        self.bar_frame = QFrame()
        bar_layout = QVBoxLayout()
        bar_layout.setContentsMargins(0, 0, 0, 0)
        self.bar = QFrame()
        self.bar.setFixedHeight(4)
        self.bar.setStyleSheet("background-color: #4CAF50; border-radius: 2px;")
        bar_layout.addWidget(self.bar)
        
        bounds_layout = QHBoxLayout()
        bounds_layout.setContentsMargins(0, 0, 0, 0)
        self.min_label = QLabel(f"{self.channel.min_value:.0f}")
        self.min_label.setStyleSheet("color: #999999; font-size: 6px;")
        self.min_label.setAlignment(Qt.AlignLeft)
        bounds_layout.addWidget(self.min_label)
        bounds_layout.addStretch()
        self.max_label = QLabel(f"{self.channel.max_value:.0f}")
        self.max_label.setStyleSheet("color: #999999; font-size: 6px;")
        self.max_label.setAlignment(Qt.AlignRight)
        bounds_layout.addWidget(self.max_label)
        
        bar_layout.addLayout(bounds_layout)
        self.bar_frame.setLayout(bar_layout)
        layout.addWidget(self.bar_frame)
        
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
        
        settings_layout = QHBoxLayout()
        settings_layout.setContentsMargins(0, 0, 0, 0)
        
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(20, 20)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                border: 1px solid #b0b0b0;
                border-radius: 10px;
                font-size: 10px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)
        self.settings_btn.clicked.connect(self.open_settings)
        settings_layout.addWidget(self.settings_btn, alignment=Qt.AlignCenter)
        
        self.enabled_check = QCheckBox("Вкл")
        self.enabled_check.setChecked(self.channel.enabled)
        self.enabled_check.stateChanged.connect(self.on_enabled_changed)
        self.enabled_check.setStyleSheet("font-size: 8px;")
        settings_layout.addWidget(self.enabled_check, alignment=Qt.AlignCenter)
        
        layout.addLayout(settings_layout)
        
        self.setLayout(layout)
        self.setMinimumSize(100, 160)
        self.setMaximumSize(120, 180)
        
    def on_name_click(self, event):
        self.channel_selected.emit(self.channel.id)
        
    def on_type_changed(self, text: str):
        try:
            signal_type = SignalType[text.upper()]
            self.channel.signal_type = signal_type
            self.channel_type_changed.emit(self.channel.id, text)
        except KeyError:
            pass
        
    def open_settings(self):
        dialog = ChannelSettingsDialog(self.channel, self)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            
            self.channel.name = settings['name']
            self.channel.min_value = settings['min_value']
            self.channel.max_value = settings['max_value']
            self.channel.frequency = settings['frequency']
            self.channel.amplitude = settings['amplitude']
            self.channel.offset = settings['offset']
            self.channel.signal_type = SignalType[settings['signal_type']]
            self.channel.enabled = settings['enabled']
            
            self.name_label.setText(f"Ch{self.channel.id+1}: {self.channel.name}")
            self.min_label.setText(f"{self.channel.min_value:.0f}")
            self.max_label.setText(f"{self.channel.max_value:.0f}")
            
            current_type = self.channel.signal_type.name.capitalize()
            index = self.type_combo.findText(current_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
                
            self.enabled_check.setChecked(self.channel.enabled)
            self.update_display()
            
            self.channel_settings_changed.emit(self.channel.id)
        
    def on_enabled_changed(self, state):
        self.channel.enabled = bool(state)
        if not state:
            self.value_label.setStyleSheet("color: #999999;")
            self.bar.setStyleSheet("background-color: #cccccc; border-radius: 2px;")
            self.type_combo.setEnabled(False)
            self.settings_btn.setEnabled(False)
        else:
            self.value_label.setStyleSheet("color: #0066CC;")
            self.bar.setStyleSheet("background-color: #4CAF50; border-radius: 2px;")
            self.type_combo.setEnabled(True)
            self.settings_btn.setEnabled(True)
            
    def update_display(self):
        """Обновить отображение значения"""
        try:
            # Проверяем существование основных виджетов
            if not hasattr(self, 'value_label') or not self.value_label:
                return
                
            if self.channel.enabled:
                value = self.channel.current_value
                self.value_label.setText(f"{value:.1f}")
                
                range_val = self.channel.max_value - self.channel.min_value
                if range_val > 0:
                    percent = (value - self.channel.min_value) / range_val
                    bar_width = max(0, min(100, percent * 100))
                else:
                    bar_width = 50
                    
                if self.bar:
                    self.bar.setStyleSheet(f"""
                        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #4CAF50, stop:{bar_width/100} #4CAF50,
                            stop:{bar_width/100} #e0e0e0, stop:1 #e0e0e0);
                        border-radius: 2px;
                    """)
            else:
                if self.value_label:
                    self.value_label.setText("Off")
                if self.bar:
                    self.bar.setStyleSheet("background-color: #cccccc; border-radius: 2px;")
                    
        except (RuntimeError, AttributeError) as e:
            # Виджет уже удален - просто игнорируем
            # print(f"[DEBUG] Widget update error: {e}")
            pass
            
    def update_channel(self, channel: AnalogChannel):
        self.channel = channel
        self.name_label.setText(f"Ch{channel.id+1}: {channel.name}")
        self.min_label.setText(f"{channel.min_value:.0f}")
        self.max_label.setText(f"{channel.max_value:.0f}")
        
        current_type = channel.signal_type.name.capitalize()
        index = self.type_combo.findText(current_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
            
        self.enabled_check.setChecked(channel.enabled)
        self.update_display()


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    CHANNELS_CONFIG_FILE = "channels_config.json"
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(__full_version__)
        self.setGeometry(100, 100, 1400, 900)
        
        # Путь к файлу конфигурации
        self.config_path = self._get_config_path()
        
        # Создаем генератор с 20 каналами
        self.generator = SignalGenerator()
        self._setup_channels()
        
        # Создаем Modbus клиент
        self.modbus = ModbusClientWrapper()
        
        # Создаем движок сценариев
        self.scenario_engine = ScenarioEngine(self.generator, self)
        self.scenario_engine.log_signal.connect(self.log)
        
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
        
    def _get_config_path(self):
        """Получить путь к файлу конфигурации каналов"""
        home_dir = os.path.expanduser("~")
        config_dir = os.path.join(home_dir, ".analog_simulator")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        return os.path.join(config_dir, self.CHANNELS_CONFIG_FILE)
        
    def _setup_channels(self):
        """Создать каналы с загрузкой сохраненных настроек"""
        saved_config = self._load_channels_config()
        
        signal_types = [SignalType.SINE, SignalType.SQUARE, 
                       SignalType.SAWTOOTH, SignalType.TRIANGLE,
                       SignalType.RANDOM]
        
        for i in range(20):
            stype = signal_types[i % len(signal_types)]
            
            if saved_config and str(i) in saved_config:
                cfg = saved_config[str(i)]
                channel = AnalogChannel(
                    id=i,
                    name=cfg.get('name', f"Ch_{i+1:02d}"),
                    signal_type=SignalType[cfg.get('signal_type', stype.name)],
                    frequency=cfg.get('frequency', 0.5 + (i % 10) * 0.3),
                    amplitude=cfg.get('amplitude', 30 + (i % 7) * 10),
                    offset=cfg.get('offset', 10 + (i % 9) * 5),
                    min_value=cfg.get('min_value', (i % 5) * 10),
                    max_value=cfg.get('max_value', 100 - (i % 3) * 5),
                    enabled=cfg.get('enabled', True)
                )
            else:
                min_val = (i % 5) * 10
                max_val = 100 - (i % 3) * 5
                channel = AnalogChannel(
                    id=i,
                    name=f"Ch_{i+1:02d}",
                    signal_type=stype,
                    frequency=0.5 + (i % 10) * 0.3,
                    amplitude=30 + (i % 7) * 10,
                    offset=10 + (i % 9) * 5,
                    min_value=min_val,
                    max_value=max_val,
                    enabled=True
                )
            
            self.generator.add_channel(channel)
            
    def _load_channels_config(self) -> dict:
        """Загрузить конфигурацию каналов из файла"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки конфигурации каналов: {e}")
        return {}
        
    def _save_channels_config(self):
        """Сохранить конфигурацию каналов в файл"""
        try:
            config = {}
            for channel in self.generator.channels:
                config[str(channel.id)] = {
                    'name': channel.name,
                    'signal_type': channel.signal_type.name,
                    'frequency': channel.frequency,
                    'amplitude': channel.amplitude,
                    'offset': channel.offset,
                    'min_value': channel.min_value,
                    'max_value': channel.max_value,
                    'enabled': channel.enabled
                }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                
            return True
        except Exception as e:
            self.log(f"Ошибка сохранения конфигурации каналов: {e}", "error")
            return False
            
    def setup_ui(self):
        """Настройка UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Горизонтальный разделитель: левая панель и правая панель
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # ЛЕВАЯ ПАНЕЛЬ
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        # Панель подключения (сворачиваемая)
        self.connection_panel = ConnectionPanel()
        self.connection_panel.connection_changed.connect(self.on_connection_changed)
        self.connection_panel.connected.connect(self.on_connection_status_changed)
        left_layout.addWidget(self.connection_panel)
        
        # Панель управления (сворачиваемая)
        self.control_panel = ControlPanel()
        self.control_panel.start_stop_clicked.connect(self.toggle_generation)
        self.control_panel.reset_clicked.connect(self.reset_signals)
        self.control_panel.plot_clicked.connect(self.open_plot_window)
        self.control_panel.logger_clicked.connect(self.open_logger_window)
        self.control_panel.plc_clicked.connect(self.open_plc_view)
        self.control_panel.save_channels_clicked.connect(self.save_channels)
        left_layout.addWidget(self.control_panel)
        
        # Интервал обновления (сворачиваемый)
        self.interval_control = IntervalControl()
        self.interval_control.signal_interval_changed.connect(self.on_signal_interval_changed)
        self.interval_control.plc_interval_changed.connect(self.on_plc_interval_changed)
        left_layout.addWidget(self.interval_control)
        
        # КОНСТРУКТОР СЦЕНАРИЕВ (сворачиваемый, с ограничением высоты)
        from scenario.scenario_widget import ScenarioWidget
        
        # Оборачиваем сценарий в сворачиваемый GroupBox
        scenario_group = CollapsibleGroupBox("🎬 Сценарии", self, collapsed=True)  # По умолчанию свернут
        scenario_layout = QVBoxLayout()
        scenario_group.setLayout(scenario_layout)
        
        self.scenario_widget = ScenarioWidget(self.generator, self.scenario_engine, self)
        # Ограничиваем высоту виджета сценария
        self.scenario_widget.setMaximumHeight(250)
        scenario_layout.addWidget(self.scenario_widget)
        
        left_layout.addWidget(scenario_group)
        
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
            widget.channel_type_changed.connect(self.on_channel_type_changed)
            widget.channel_settings_changed.connect(self.on_channel_settings_changed)
            row = i // cols
            col = i % cols
            grid_layout.addWidget(widget, row, col)
            self.channel_widgets.append(widget)
            
        scroll.setWidget(grid_widget)
        left_layout.addWidget(scroll)
        
        # ПРАВАЯ ПАНЕЛЬ - информация
        right_panel = self._create_info_panel()
        main_layout.addWidget(right_panel)
        
        # Устанавливаем пропорции
        main_layout.setStretchFactor(left_panel, 3)
        main_layout.setStretchFactor(right_panel, 1)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QLabel { color: #333333; }
        """)
        
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
        
        # Режим работы
        layout.addWidget(QLabel("Режим:"))
        self.mode_label = QLabel("Ручной")
        self.mode_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(self.mode_label)
        
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
        
        # Границы выбранного канала
        layout.addWidget(QLabel("Границы:"))
        self.selected_bounds_label = QLabel("0 - 100")
        self.selected_bounds_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.selected_bounds_label)
        
        layout.addSpacing(10)
        
        # Статистика
        layout.addWidget(QLabel("Статистика:"))
        self.stats_label = QLabel("Каналов: 20\nАктивных: 20")
        self.stats_label.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(self.stats_label)
        
        layout.addStretch()
        
        # Версия
        version_label = QLabel(__full_version__)
        version_label.setStyleSheet("color: #999999; font-size: 9px;")
        layout.addWidget(version_label)
        
        return panel
        
    def save_channels(self):
        """Сохранить настройки каналов"""
        if self._save_channels_config():
            self.log("Настройки каналов сохранены", "success")
            QMessageBox.information(
                self,
                "Успех",
                f"Настройки каналов сохранены в:\n{self.config_path}"
            )
        else:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не удалось сохранить настройки каналов"
            )
        
    def on_channel_settings_changed(self, channel_id: int):
        channel = self.generator.get_channel(channel_id)
        if channel:
            self.log(
                f"Канал {channel_id+1}: изменены настройки "
                f"(границы: {channel.min_value:.1f}-{channel.max_value:.1f}, "
                f"частота: {channel.frequency:.1f} Гц, "
                f"амплитуда: {channel.amplitude:.0f}%)",
                "info"
            )
            self._save_channels_config()
            
            if self.selected_channel_label.text().startswith(f"Канал {channel_id+1}"):
                self.selected_bounds_label.setText(f"{channel.min_value:.0f} - {channel.max_value:.0f}")
        
    def on_channel_type_changed(self, channel_id: int, type_name: str):
        channel = self.generator.get_channel(channel_id)
        if channel:
            self.log(f"Канал {channel_id+1}: тип сигнала изменен на {type_name}", "info")
            self._save_channels_config()
            
            if self.selected_channel_label.text().startswith(f"Канал {channel_id+1}"):
                self.selected_type_label.setText(type_name)
                
    def on_signal_interval_changed(self, interval: float):
        self.generator.set_update_interval(interval)
        freq = 1.0 / interval if interval > 0 else 0
        self.log(f"Интервал обновления сигналов изменен: {interval:.3f} с ({freq:.1f} Гц)", "info")
        
        self.status_label.setText(f"⏱ Сигналы: {interval:.3f} с")
        self.status_label.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 12px;")
        
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.status_label.setText("● Работает"))
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #00CC00; font-weight: bold; font-size: 12px;"))

    def on_plc_interval_changed(self, interval: float):
        if hasattr(self, 'plc_interface'):
            self.plc_interface.set_write_interval(interval)
            freq = 1.0 / interval if interval > 0 else 0
            self.log(f"Интервал записи в PLC изменен: {interval:.3f} с ({freq:.1f} Гц)", "info")
        
    def on_connection_changed(self, params):
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
        job = Runnable(fn, *args, **kwargs)
        job.signals.result.connect(on_result)
        job.signals.error.connect(lambda e: self.log(f"Ошибка: {e}", "error"))
        self.thread_pool.start(job)
        
    def log(self, message: str, level: str = "info"):
        if self.logger_window and self.logger_window.isVisible():
            self.logger_window.log(message, level)
        else:
            print(f"[{level.upper()}] {message}")
            
    def on_channel_selected(self, channel_id):
        channel = self.generator.get_channel(channel_id)
        if channel:
            self.selected_channel_label.setText(f"Канал {channel_id+1}: {channel.name}")
            self.selected_type_label.setText(str(channel.signal_type))
            self.selected_bounds_label.setText(f"{channel.min_value:.0f} - {channel.max_value:.0f}")
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
            self.is_running = False
            self.control_panel.set_start_button_state(False)
            self.status_label.setText("● Остановлен")
            self.status_label.setStyleSheet("color: #FF4444; font-weight: bold; font-size: 12px;")
        else:
            self.timer.start(10)
            self.is_running = True
            self.control_panel.set_start_button_state(True)
            self.status_label.setText("● Работает")
            self.status_label.setStyleSheet("color: #00CC00; font-weight: bold; font-size: 12px;")
            
    def reset_signals(self):
        for channel in self.generator.channels:
            channel.time = 0
            channel.current_value = 0
        self.update_signals()
            
    def update_signals(self):
        """Обновить сигналы и UI"""
        if not self.is_running:
            return
            
        # Проверяем, не запущен ли сценарий
        if hasattr(self, 'scenario_engine') and self.scenario_engine.is_running():
            # Если сценарий запущен, не обновляем сигналы вручную
            return
            
        self.generator.update(dt=0.01)
        
        active_count = 0
        
        # Обновляем виджеты каналов
        for i, widget in enumerate(self.channel_widgets):
            if i >= len(self.generator.channels):
                break
                
            try:
                if widget is None:
                    continue
                    
                try:
                    widget.isHidden()
                except RuntimeError:
                    continue
                    
                widget.update_display()
                if self.generator.channels[i].enabled:
                    active_count += 1
                    
            except (RuntimeError, AttributeError):
                continue
                        
        # Обновляем статистику
        try:
            if self.stats_label:
                self.stats_label.setText(f"Каналов: {len(self.generator.channels)}\nАктивных: {active_count}")
        except (RuntimeError, AttributeError):
            pass
        
        self.frame_count += 1
        if self.frame_count >= 50:
            fps = self.frame_count * 2
            try:
                if self.control_panel:
                    self.control_panel.update_fps(fps)
            except (RuntimeError, AttributeError):
                pass
            self.frame_count = 0
            
    def closeEvent(self, event):
        self._save_channels_config()
        self.log("Настройки каналов сохранены", "info")
        
        if self.plot_window:
            self.plot_window.close()
        if self.logger_window:
            self.logger_window.close()
        if self.plc_view:
            self.plc_view.close()
        self.plc_interface.disconnect()
        self.modbus.close()
        event.accept()