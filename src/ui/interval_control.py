from PyQt5.QtWidgets import (QWidget, QGroupBox, QHBoxLayout, QVBoxLayout,
                             QLabel, QDoubleSpinBox, QSlider, QPushButton,
                             QSpinBox, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class CollapsibleGroupBox(QGroupBox):
    """GroupBox с возможностью сворачивания/разворачивания"""
    
    def __init__(self, title, parent=None, collapsed=False):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(not collapsed)
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
        """)
        self.toggled.connect(self.on_toggled)
        self._collapsed = collapsed
        self._content_widgets = []
        
    def add_content_widget(self, widget):
        """Добавить виджет в содержимое GroupBox"""
        self._content_widgets.append(widget)
        
    def on_toggled(self, checked):
        """Обработчик изменения состояния"""
        self._collapsed = not checked
        self.update_content_visibility(checked)
        
    def update_content_visibility(self, visible):
        """Обновить видимость содержимого"""
        for widget in self._content_widgets:
            widget.setVisible(visible)
            
    def set_collapsed(self, collapsed):
        """Установить состояние свернуто/развернуто"""
        self.setChecked(not collapsed)
        self._collapsed = collapsed
        self.update_content_visibility(not collapsed)
        
    def is_collapsed(self):
        """Проверить, свернут ли GroupBox"""
        return self._collapsed


class IntervalControl(CollapsibleGroupBox):
    """Виджет для управления интервалом обновления сигналов"""
    
    # Сигнал при изменении интервала
    interval_changed = pyqtSignal(float)  # Новый интервал в секундах
    
    def __init__(self, parent=None):
        super().__init__("⏱ Интервал обновления", parent, collapsed=False)
        self._current_interval = 0.01  # 10ms по умолчанию
        
        # Создаем контейнер для содержимого
        content_widget = QWidget()
        self.setup_ui(content_widget)
        
        # Устанавливаем layout
        layout = QVBoxLayout()
        layout.addWidget(content_widget)
        self.setLayout(layout)
        
        # Добавляем все виджеты в список для сворачивания
        self._content_widgets = content_widget.findChildren(QWidget)
        
        self.setup_connections()
        
    def setup_ui(self, container):
        """Настройка интерфейса"""
        layout = QVBoxLayout()
        container.setLayout(layout)
        
        # Основная панель
        main_layout = QHBoxLayout()
        
        # Значение в секундах
        value_layout = QVBoxLayout()
        value_layout.addWidget(QLabel("Интервал (сек):"))
        
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
            btn.clicked.connect(lambda checked, v=value: self.set_interval(v))
            quick_buttons_layout.addWidget(btn)
            self.preset_buttons.append(btn)
            
        quick_layout.addLayout(quick_buttons_layout)
        main_layout.addLayout(quick_layout)
        
        layout.addLayout(main_layout)
        
        # Информационная строка
        info_layout = QHBoxLayout()
        
        self.status_label = QLabel("✅ Интервал: 0.010 с (100.0 Гц)")
        self.status_label.setStyleSheet("color: #666666; font-size: 9px;")
        info_layout.addWidget(self.status_label)
        
        info_layout.addStretch()
        
        self.update_count_label = QLabel("Обновлений/сек: 100")
        self.update_count_label.setStyleSheet("color: #666666; font-size: 9px;")
        info_layout.addWidget(self.update_count_label)
        
        layout.addLayout(info_layout)
        
        # Стили
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
            QDoubleSpinBox, QSlider {
                background-color: white;
            }
            QLabel {
                color: #333333;
            }
        """)
        
        self.setMaximumHeight(180)
        
    def setup_connections(self):
        """Настройка сигналов"""
        self.interval_spin.valueChanged.connect(self.on_interval_changed)
        self.interval_slider.valueChanged.connect(self.on_slider_changed)
        
    def on_interval_changed(self, value: float):
        """Изменение интервала через SpinBox"""
        self._current_interval = value
        # Обновляем слайдер
        slider_value = int(value * 1000)
        self.interval_slider.blockSignals(True)
        self.interval_slider.setValue(max(1, min(1000, slider_value)))
        self.interval_slider.blockSignals(False)
        
        # Обновляем информацию
        self.update_info(value)
        
        # Отправляем сигнал
        self.interval_changed.emit(value)
        
    def on_slider_changed(self, value: int):
        """Изменение интервала через Slider"""
        interval = value / 1000.0
        self._current_interval = interval
        
        # Обновляем SpinBox
        self.interval_spin.blockSignals(True)
        self.interval_spin.setValue(interval)
        self.interval_spin.blockSignals(False)
        
        # Обновляем информацию
        self.update_info(interval)
        
        # Отправляем сигнал
        self.interval_changed.emit(interval)
        
    def set_interval(self, interval: float):
        """Установить интервал программно"""
        self._current_interval = interval
        
        # Обновляем все элементы управления
        self.interval_spin.blockSignals(True)
        self.interval_spin.setValue(interval)
        self.interval_spin.blockSignals(False)
        
        slider_value = int(interval * 1000)
        self.interval_slider.blockSignals(True)
        self.interval_slider.setValue(max(1, min(1000, slider_value)))
        self.interval_slider.blockSignals(False)
        
        # Обновляем информацию
        self.update_info(interval)
        
        # Отправляем сигнал
        self.interval_changed.emit(interval)
        
    def update_info(self, interval: float):
        """Обновить информационные метки"""
        freq = 1.0 / interval if interval > 0 else 0
        
        self.freq_label.setText(f"{freq:.1f} Гц")
        self.status_label.setText(f"✅ Интервал: {interval:.3f} с ({freq:.1f} Гц)")
        self.update_count_label.setText(f"Обновлений/сек: {int(freq)}")
        
    def get_interval(self) -> float:
        """Получить текущий интервал"""
        return self._current_interval


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