from PyQt5.QtWidgets import (QWidget, QGroupBox, QHBoxLayout, QVBoxLayout,
                             QLabel, QDoubleSpinBox, QSlider, QPushButton,
                             QSpinBox, QFrame, QTabWidget)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
import json
import os

from .collapsible_groupbox import CollapsibleGroupBox


class IntervalControl(CollapsibleGroupBox):
    """Виджет для управления интервалами обновления"""
    
    # Сигналы при изменении интервалов
    signal_interval_changed = pyqtSignal(float)  # Интервал обновления сигналов
    plc_interval_changed = pyqtSignal(float)     # Интервал записи в PLC
    
    # Имя файла для сохранения настроек
    CONFIG_FILE = "intervals_config.json"
    
    def __init__(self, parent=None):
        super().__init__("⏱ Интервалы обновления", parent, collapsed=False)
        self._current_interval = 0.01  # 10ms по умолчанию
        self._current_plc_interval = 0.2  # 200ms по умолчанию
        
        # Путь к файлу конфигурации
        self.config_path = self._get_config_path()
        
        # Загружаем сохраненные настройки
        self._load_config()
        
        # Создаем контейнер для содержимого
        content_widget = QWidget()
        self.setup_ui(content_widget)
        
        # Устанавливаем layout для GroupBox
        layout = QVBoxLayout()
        layout.addWidget(content_widget)
        self.setLayout(layout)
        
        # Собираем все дочерние виджеты для сворачивания
        self._content_widgets = []
        for child in content_widget.findChildren(QWidget):
            self._content_widgets.append(child)
        self._content_widgets.append(content_widget)
        
        self.setup_connections()
        
        # Применяем загруженные настройки
        self._apply_config()
        
    def _get_config_path(self):
        """Получить путь к файлу конфигурации интервалов"""
        home_dir = os.path.expanduser("~")
        config_dir = os.path.join(home_dir, ".analog_simulator")
        
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            
        return os.path.join(config_dir, self.CONFIG_FILE)
        
    def _load_config(self):
        """Загрузить настройки интервалов из файла"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self._current_interval = config.get('signal_interval', 0.01)
                    self._current_plc_interval = config.get('plc_interval', 0.2)
                    return True
        except Exception as e:
            print(f"Ошибка загрузки настроек интервалов: {e}")
        return False
        
    def _save_config(self):
        """Сохранить настройки интервалов в файл"""
        try:
            config = {
                'signal_interval': self._current_interval,
                'plc_interval': self._current_plc_interval
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения настроек интервалов: {e}")
            return False
            
    def _apply_config(self):
        """Применить загруженные настройки"""
        # Применяем интервал сигналов
        self.interval_spin.blockSignals(True)
        self.interval_spin.setValue(self._current_interval)
        self.interval_spin.blockSignals(False)
        
        slider_value = int(self._current_interval * 1000)
        self.interval_slider.blockSignals(True)
        self.interval_slider.setValue(max(1, min(1000, slider_value)))
        self.interval_slider.blockSignals(False)
        
        # Применяем интервал PLC
        self.plc_interval_spin.blockSignals(True)
        self.plc_interval_spin.setValue(self._current_plc_interval)
        self.plc_interval_spin.blockSignals(False)
        
        plc_slider_value = int(self._current_plc_interval * 1000)
        self.plc_interval_slider.blockSignals(True)
        self.plc_interval_slider.setValue(max(10, min(2000, plc_slider_value)))
        self.plc_interval_slider.blockSignals(False)
        
        # Обновляем информацию
        self.update_signal_info(self._current_interval)
        self.update_plc_info(self._current_plc_interval)
        
    def setup_ui(self, container):
        """Настройка интерфейса"""
        layout = QVBoxLayout()
        container.setLayout(layout)
        
        # Создаем вкладки для разных интервалов
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e8e8e8;
                border: 1px solid #d0d0d0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 6px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #4CAF50;
            }
            QTabBar::tab:hover {
                background-color: #d0d0d0;
            }
        """)
        
        # Вкладка 1: Интервал обновления сигналов
        signal_tab = QWidget()
        signal_layout = QVBoxLayout()
        signal_tab.setLayout(signal_layout)
        self._setup_signal_interval_ui(signal_layout)
        tabs.addTab(signal_tab, "📊 Сигналы")
        
        # Вкладка 2: Интервал записи в PLC
        plc_tab = QWidget()
        plc_layout = QVBoxLayout()
        plc_tab.setLayout(plc_layout)
        self._setup_plc_interval_ui(plc_layout)
        tabs.addTab(plc_tab, "🔌 PLC")
        
        layout.addWidget(tabs)
        
        # Информационная строка (общая)
        info_layout = QHBoxLayout()
        
        self.status_label = QLabel("✅ Сигналы: 0.010 с (100 Гц) | PLC: 0.200 с (5 Гц)")
        self.status_label.setStyleSheet("color: #666666; font-size: 9px;")
        info_layout.addWidget(self.status_label)
        
        info_layout.addStretch()
        
        self.update_count_label = QLabel("Обновлений/сек: 100")
        self.update_count_label.setStyleSheet("color: #666666; font-size: 9px;")
        info_layout.addWidget(self.update_count_label)
        
        # Кнопка сохранения
        self.save_btn = QPushButton("💾 Сохранить настройки")
        self.save_btn.clicked.connect(self.save_settings)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        info_layout.addWidget(self.save_btn)
        
        layout.addLayout(info_layout)
        
    def save_settings(self):
        """Сохранить текущие настройки"""
        if self._save_config():
            self.status_label.setText("✅ Настройки сохранены!")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 9px;")
            
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self._update_status())
            
    def _setup_signal_interval_ui(self, layout):
        """Настройка интерфейса для интервала сигналов"""
        # Основная панель
        main_layout = QHBoxLayout()
        
        # Значение в секундах
        value_layout = QVBoxLayout()
        value_layout.addWidget(QLabel("Интервал обновления сигналов:"))
        
        # DoubleSpinBox для точной настройки
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.001, 10.0)
        self.interval_spin.setSingleStep(0.001)
        self.interval_spin.setDecimals(3)
        self.interval_spin.setValue(0.01)
        self.interval_spin.setSuffix(" с")
        self.interval_spin.setMaximumWidth(120)
        value_layout.addWidget(self.interval_spin)
        
        main_layout.addLayout(value_layout)
        
        # Слайдер для быстрой настройки
        slider_layout = QVBoxLayout()
        slider_layout.addWidget(QLabel("Быстрая настройка:"))
        
        self.interval_slider = QSlider(Qt.Horizontal)
        self.interval_slider.setRange(1, 1000)  # 1ms до 1000ms
        self.interval_slider.setValue(10)  # 10ms
        self.interval_slider.setTickPosition(QSlider.TicksBelow)
        self.interval_slider.setTickInterval(100)
        self.interval_slider.setMinimumWidth(200)
        slider_layout.addWidget(self.interval_slider)
        
        main_layout.addLayout(slider_layout)
        
        # Информация о частоте
        freq_layout = QVBoxLayout()
        freq_layout.addWidget(QLabel("Частота обновления:"))
        
        self.freq_label = QLabel("100.0 Гц")
        self.freq_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.freq_label.setStyleSheet("color: #0066CC;")
        freq_layout.addWidget(self.freq_label)
        
        main_layout.addLayout(freq_layout)
        
        # Кнопки быстрых установок
        quick_layout = QVBoxLayout()
        quick_layout.addWidget(QLabel("Быстрые установки:"))
        
        quick_buttons_layout = QHBoxLayout()
        
        presets = [
            ("1ms", 0.001),
            ("10ms", 0.01),
            ("50ms", 0.05),
            ("100ms", 0.1),
            ("500ms", 0.5),
            ("1s", 1.0)
        ]
        
        self.preset_buttons = []
        for label, value in presets:
            btn = QPushButton(label)
            btn.setMaximumWidth(50)
            btn.setMaximumHeight(25)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #e0e0e0;
                    border: 1px solid #b0b0b0;
                    border-radius: 3px;
                    font-size: 8px;
                    padding: 2px;
                }
                QPushButton:hover {
                    background-color: #d0d0d0;
                }
                QPushButton:pressed {
                    background-color: #4CAF50;
                    color: white;
                }
            """)
            btn.clicked.connect(lambda checked, v=value: self.set_signal_interval(v))
            quick_buttons_layout.addWidget(btn)
            self.preset_buttons.append(btn)
            
        quick_layout.addLayout(quick_buttons_layout)
        main_layout.addLayout(quick_layout)
        
        layout.addLayout(main_layout)
        
    def _setup_plc_interval_ui(self, layout):
        """Настройка интерфейса для интервала записи в PLC"""
        # Основная панель
        main_layout = QHBoxLayout()
        
        # Значение в секундах
        value_layout = QVBoxLayout()
        value_layout.addWidget(QLabel("Интервал записи в PLC:"))
        
        # DoubleSpinBox для точной настройки
        self.plc_interval_spin = QDoubleSpinBox()
        self.plc_interval_spin.setRange(0.01, 10.0)
        self.plc_interval_spin.setSingleStep(0.01)
        self.plc_interval_spin.setDecimals(3)
        self.plc_interval_spin.setValue(0.2)
        self.plc_interval_spin.setSuffix(" с")
        self.plc_interval_spin.setMaximumWidth(120)
        value_layout.addWidget(self.plc_interval_spin)
        
        main_layout.addLayout(value_layout)
        
        # Слайдер для быстрой настройки
        slider_layout = QVBoxLayout()
        slider_layout.addWidget(QLabel("Быстрая настройка:"))
        
        self.plc_interval_slider = QSlider(Qt.Horizontal)
        self.plc_interval_slider.setRange(10, 2000)  # 10ms до 2000ms
        self.plc_interval_slider.setValue(200)  # 200ms
        self.plc_interval_slider.setTickPosition(QSlider.TicksBelow)
        self.plc_interval_slider.setTickInterval(200)
        self.plc_interval_slider.setMinimumWidth(200)
        slider_layout.addWidget(self.plc_interval_slider)
        
        main_layout.addLayout(slider_layout)
        
        # Информация о частоте записи
        freq_layout = QVBoxLayout()
        freq_layout.addWidget(QLabel("Частота записи:"))
        
        self.plc_freq_label = QLabel("5.0 Гц")
        self.plc_freq_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.plc_freq_label.setStyleSheet("color: #FF6F00;")
        freq_layout.addWidget(self.plc_freq_label)
        
        main_layout.addLayout(freq_layout)
        
        # Кнопки быстрых установок для PLC
        quick_layout = QVBoxLayout()
        quick_layout.addWidget(QLabel("Быстрые установки:"))
        
        quick_buttons_layout = QHBoxLayout()
        
        plc_presets = [
            ("50ms", 0.05),
            ("100ms", 0.1),
            ("200ms", 0.2),
            ("500ms", 0.5),
            ("1s", 1.0),
            ("2s", 2.0)
        ]
        
        self.plc_preset_buttons = []
        for label, value in plc_presets:
            btn = QPushButton(label)
            btn.setMaximumWidth(50)
            btn.setMaximumHeight(25)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #e0e0e0;
                    border: 1px solid #b0b0b0;
                    border-radius: 3px;
                    font-size: 8px;
                    padding: 2px;
                }
                QPushButton:hover {
                    background-color: #d0d0d0;
                }
                QPushButton:pressed {
                    background-color: #FF6F00;
                    color: white;
                }
            """)
            btn.clicked.connect(lambda checked, v=value: self.set_plc_interval(v))
            quick_buttons_layout.addWidget(btn)
            self.plc_preset_buttons.append(btn)
            
        quick_layout.addLayout(quick_buttons_layout)
        main_layout.addLayout(quick_layout)
        
        layout.addLayout(main_layout)
        
        # Информационная строка для PLC
        info_layout = QHBoxLayout()
        
        self.plc_status_label = QLabel("💡 Рекомендуемый интервал: 100-500 мс")
        self.plc_status_label.setStyleSheet("color: #666666; font-size: 9px;")
        info_layout.addWidget(self.plc_status_label)
        
        info_layout.addStretch()
        
        self.plc_write_count_label = QLabel("Записей: 0")
        self.plc_write_count_label.setStyleSheet("color: #666666; font-size: 9px;")
        info_layout.addWidget(self.plc_write_count_label)
        
        layout.addLayout(info_layout)
        
    def setup_connections(self):
        """Настройка сигналов"""
        # Сигналы для интервала сигналов
        self.interval_spin.valueChanged.connect(self.on_signal_interval_changed)
        self.interval_slider.valueChanged.connect(self.on_signal_slider_changed)
        
        # Сигналы для интервала PLC
        self.plc_interval_spin.valueChanged.connect(self.on_plc_interval_changed)
        self.plc_interval_slider.valueChanged.connect(self.on_plc_slider_changed)
        
    def on_signal_interval_changed(self, value: float):
        """Изменение интервала сигналов через SpinBox"""
        self._current_interval = value
        # Обновляем слайдер
        slider_value = int(value * 1000)
        self.interval_slider.blockSignals(True)
        self.interval_slider.setValue(max(1, min(1000, slider_value)))
        self.interval_slider.blockSignals(False)
        
        # Обновляем информацию
        self.update_signal_info(value)
        
        # Автосохранение
        self._save_config()
        
        # Отправляем сигнал
        self.signal_interval_changed.emit(value)
        
    def on_signal_slider_changed(self, value: int):
        """Изменение интервала сигналов через Slider"""
        interval = value / 1000.0
        self._current_interval = interval
        
        # Обновляем SpinBox
        self.interval_spin.blockSignals(True)
        self.interval_spin.setValue(interval)
        self.interval_spin.blockSignals(False)
        
        # Обновляем информацию
        self.update_signal_info(interval)
        
        # Автосохранение
        self._save_config()
        
        # Отправляем сигнал
        self.signal_interval_changed.emit(interval)
        
    def on_plc_interval_changed(self, value: float):
        """Изменение интервала PLC через SpinBox"""
        self._current_plc_interval = value
        # Обновляем слайдер
        slider_value = int(value * 1000)
        self.plc_interval_slider.blockSignals(True)
        self.plc_interval_slider.setValue(max(10, min(2000, slider_value)))
        self.plc_interval_slider.blockSignals(False)
        
        # Обновляем информацию
        self.update_plc_info(value)
        
        # Автосохранение
        self._save_config()
        
        # Отправляем сигнал
        self.plc_interval_changed.emit(value)
        
    def on_plc_slider_changed(self, value: int):
        """Изменение интервала PLC через Slider"""
        interval = value / 1000.0
        self._current_plc_interval = interval
        
        # Обновляем SpinBox
        self.plc_interval_spin.blockSignals(True)
        self.plc_interval_spin.setValue(interval)
        self.plc_interval_spin.blockSignals(False)
        
        # Обновляем информацию
        self.update_plc_info(interval)
        
        # Автосохранение
        self._save_config()
        
        # Отправляем сигнал
        self.plc_interval_changed.emit(interval)
        
    def set_signal_interval(self, interval: float):
        """Установить интервал сигналов программно"""
        self._current_interval = interval
        
        self.interval_spin.blockSignals(True)
        self.interval_spin.setValue(interval)
        self.interval_spin.blockSignals(False)
        
        slider_value = int(interval * 1000)
        self.interval_slider.blockSignals(True)
        self.interval_slider.setValue(max(1, min(1000, slider_value)))
        self.interval_slider.blockSignals(False)
        
        self.update_signal_info(interval)
        self._save_config()
        self.signal_interval_changed.emit(interval)
        
    def set_plc_interval(self, interval: float):
        """Установить интервал PLC программно"""
        self._current_plc_interval = interval
        
        self.plc_interval_spin.blockSignals(True)
        self.plc_interval_spin.setValue(interval)
        self.plc_interval_spin.blockSignals(False)
        
        slider_value = int(interval * 1000)
        self.plc_interval_slider.blockSignals(True)
        self.plc_interval_slider.setValue(max(10, min(2000, slider_value)))
        self.plc_interval_slider.blockSignals(False)
        
        self.update_plc_info(interval)
        self._save_config()
        self.plc_interval_changed.emit(interval)
        
    def update_signal_info(self, interval: float):
        """Обновить информацию о сигналах"""
        freq = 1.0 / interval if interval > 0 else 0
        self.freq_label.setText(f"{freq:.1f} Гц")
        self.update_count_label.setText(f"Обновлений/сек: {int(freq)}")
        self._update_status()
        
    def update_plc_info(self, interval: float):
        """Обновить информацию о PLC"""
        freq = 1.0 / interval if interval > 0 else 0
        self.plc_freq_label.setText(f"{freq:.1f} Гц")
        
        # Рекомендации по интервалу
        if interval < 0.05:
            self.plc_status_label.setText("⚠️ Слишком часто! Рекомендуется 100-500 мс")
            self.plc_status_label.setStyleSheet("color: #f44336; font-size: 9px;")
        elif interval < 0.1:
            self.plc_status_label.setText("⚡ Очень часто! Рекомендуется 100-500 мс")
            self.plc_status_label.setStyleSheet("color: #FF9800; font-size: 9px;")
        elif interval <= 0.5:
            self.plc_status_label.setText("✅ Оптимальный интервал")
            self.plc_status_label.setStyleSheet("color: #4CAF50; font-size: 9px;")
        else:
            self.plc_status_label.setText("🐢 Медленный интервал, возможно задержки")
            self.plc_status_label.setStyleSheet("color: #666666; font-size: 9px;")
            
        self._update_status()
        
    def _update_status(self):
        """Обновить общий статус"""
        signal_freq = 1.0 / self._current_interval if self._current_interval > 0 else 0
        plc_freq = 1.0 / self._current_plc_interval if self._current_plc_interval > 0 else 0
        self.status_label.setText(
            f"✅ Сигналы: {self._current_interval:.3f} с ({signal_freq:.0f} Гц) | "
            f"PLC: {self._current_plc_interval:.3f} с ({plc_freq:.1f} Гц)"
        )
        self.status_label.setStyleSheet("color: #666666; font-size: 9px;")
        
    def get_signal_interval(self) -> float:
        """Получить текущий интервал сигналов"""
        return self._current_interval
        
    def get_plc_interval(self) -> float:
        """Получить текущий интервал PLC"""
        return self._current_plc_interval
        
    def update_plc_write_count(self, count: int):
        """Обновить счетчик записей в PLC"""
        self.plc_write_count_label.setText(f"Записей: {count}")


# ============================================================
# БЫСТРОЕ ТЕСТИРОВАНИЕ
# ============================================================
def test_interval_control():
    """Тестовая функция для проверки работы IntervalControl"""
    import sys
    from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ IntervalControl")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    
    window = QWidget()
    window.setWindowTitle("Тест IntervalControl")
    window.setGeometry(200, 200, 600, 200)
    
    layout = QVBoxLayout()
    window.setLayout(layout)
    
    # Создаем виджет
    interval_control = IntervalControl()
    layout.addWidget(interval_control)
    
    # Метка для отображения изменений
    info_label = QLabel("Изменяйте интервал и смотрите сигналы")
    info_label.setAlignment(Qt.AlignCenter)
    info_label.setStyleSheet("color: #666666; padding: 10px;")
    layout.addWidget(info_label)
    
    # Подключаем сигнал
    def on_interval_changed(interval):
        freq = 1.0 / interval if interval > 0 else 0
        info_label.setText(f"✅ Интервал: {interval:.3f} с | Частота: {freq:.1f} Гц")
        info_label.setStyleSheet("color: #4CAF50; padding: 10px;")
        print(f"[ТЕСТ] Интервал изменен: {interval:.3f} с ({freq:.1f} Гц)")
    
    interval_control.interval_changed.connect(on_interval_changed)
    
    window.show()
    
    print("\n✅ Тестовое окно открыто")
    print("📋 Инструкция:")
    print("  1. Изменяйте значение в SpinBox")
    print("  2. Перемещайте слайдер")
    print("  3. Нажимайте кнопки быстрых установок")
    print("  4. Смотрите изменения в метке и консоли")
    print("\nЗакройте окно для завершения теста")
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    test_interval_control()