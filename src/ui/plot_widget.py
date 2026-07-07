import sys
import pyqtgraph as pg
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QComboBox, QCheckBox, 
                             QSplitter, QFrame, QGridLayout, QSpinBox,
                             QDoubleSpinBox, QGroupBox, QTabWidget)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor
import numpy as np
from collections import deque

from core.signal_generator import SignalGenerator
from core.channel import AnalogChannel


class PlotWidget(pg.PlotWidget):
    """Виджет графика для отображения сигнала"""
    
    def __init__(self, max_points=500, parent=None):
        super().__init__(parent)
        self.max_points = max_points
        self.channel_id = None
        self.channel_name = ""
        self.is_visible = True
        
        # Данные для хранения истории
        self.time_data = deque(maxlen=max_points)
        self.value_data = deque(maxlen=max_points)
        
        # Инициализируем данные нулями
        for i in range(max_points):
            self.time_data.append(i * 0.01)
            self.value_data.append(0)
        
        self.setup_plot()
        
    def setup_plot(self):
        """Настройка графика"""
        # Настройка осей
        self.setLabel('left', 'Значение', units='%')
        self.setLabel('bottom', 'Время', units='с')
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setMouseEnabled(x=True, y=True)
        
        # Добавляем легенду
        self.addLegend()
        
        # Основная линия сигнала
        self.curve = self.plot(
            list(self.time_data), 
            list(self.value_data),
            pen=pg.mkPen(color=(0, 100, 200), width=2, style=Qt.SolidLine),
            name='Сигнал'
        )
        
        # Линия среднего значения
        self.mean_curve = self.plot(
            list(self.time_data),
            [0] * len(self.time_data),
            pen=pg.mkPen(color=(200, 100, 0), width=1, style=Qt.DashLine),
            name='Среднее'
        )
        
        # Заполненная область
        self.fill_curve = self.plot(
            list(self.time_data),
            list(self.value_data),
            fillLevel=0,
            brush=pg.mkBrush(100, 150, 255, 30),
            pen=None
        )
        
    def set_channel(self, channel_id, channel_name=""):
        """Установить канал для отображения"""
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.clear_plot()
        
    def update_data(self, value, time_step=0.01):
        """Обновить данные графика"""
        if not self.is_visible:
            return
            
        # Добавляем новое значение
        current_time = len(self.time_data) * time_step
        self.time_data.append(current_time)
        self.value_data.append(value)
        
    def update_plot(self):
        """Обновить отображение графика"""
        if not self.is_visible or len(self.time_data) == 0:
            return
            
        # Обновляем основную кривую
        self.curve.setData(list(self.time_data), list(self.value_data))
        
        # Обновляем линию среднего
        if len(self.value_data) > 0:
            mean_val = np.mean(list(self.value_data))
            self.mean_curve.setData(
                list(self.time_data), 
                [mean_val] * len(self.time_data)
            )
            
            # Обновляем заполненную область
            self.fill_curve.setData(
                list(self.time_data),
                list(self.value_data)
            )
        
    def auto_range(self):
        """Автоматическое масштабирование"""
        self.autoRange()
        
    def clear_plot(self):
        """Очистить данные графика"""
        self.time_data.clear()
        self.value_data.clear()
        # Заполняем нулями
        for i in range(self.max_points):
            self.time_data.append(i * 0.01)
            self.value_data.append(0)
        self.update_plot()
        
    def showEvent(self, event):
        """Виджет становится видимым"""
        self.is_visible = True
        super().showEvent(event)
        
    def hideEvent(self, event):
        """Виджет скрывается"""
        self.is_visible = False
        super().hideEvent(event)


class PlotWindow(QMainWindow):
    """Отдельное окно для отображения графиков"""
    
    def __init__(self, generator: SignalGenerator, parent=None):
        super().__init__(parent)
        self.generator = generator
        self.setWindowTitle("📊 Графики сигналов")
        self.setGeometry(200, 200, 1000, 700)
        
        # Список выбранных каналов для отображения
        self.selected_channels = []
        self.max_channels_on_plot = 4  # Максимум 4 канала на одном графике
        
        self.setup_ui()
        self.setup_plots()
        
        # Таймер для обновления графиков
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(50)  # 20 FPS для графиков
        
        self.is_running = True
        
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Верхняя панель управления
        control_layout = self._create_control_panel()
        main_layout.addLayout(control_layout)
        
        # Основной разделитель
        splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - список каналов
        left_panel = self._create_channels_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - графики
        right_panel = self._create_plots_panel()
        splitter.addWidget(right_panel)
        
        # Устанавливаем пропорции
        splitter.setSizes([300, 700])
        main_layout.addWidget(splitter)
        
        # Нижняя информационная панель
        info_layout = self._create_info_panel()
        main_layout.addLayout(info_layout)
        
        # Применяем стиль
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
            QPushButton:checked {
                background-color: #f44336;
            }
            QListWidget {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)
        
    def _create_control_panel(self):
        """Создать панель управления"""
        layout = QHBoxLayout()
        
        # Кнопка добавления канала на график
        self.add_btn = QPushButton("➕ Добавить на график")
        self.add_btn.clicked.connect(self.add_selected_channels)
        layout.addWidget(self.add_btn)
        
        # Кнопка очистки графиков
        self.clear_btn = QPushButton("🗑 Очистить графики")
        self.clear_btn.clicked.connect(self.clear_all_plots)
        self.clear_btn.setStyleSheet("background-color: #f44336;")
        layout.addWidget(self.clear_btn)
        
        # Кнопка авто-масштаб
        self.auto_btn = QPushButton("📐 Авто-масштаб")
        self.auto_btn.clicked.connect(self.auto_range_all)
        layout.addWidget(self.auto_btn)
        
        layout.addStretch()
        
        # Количество каналов на графике
        layout.addWidget(QLabel("Каналов на графике:"))
        self.channels_spin = QSpinBox()
        self.channels_spin.setRange(1, 10)
        self.channels_spin.setValue(self.max_channels_on_plot)
        self.channels_spin.valueChanged.connect(self.set_max_channels)
        layout.addWidget(self.channels_spin)
        
        # Кнопка закрытия
        self.close_btn = QPushButton("✕ Закрыть")
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setStyleSheet("background-color: #f44336;")
        layout.addWidget(self.close_btn)
        
        return layout
        
    def _create_channels_panel(self):
        """Создать панель со списком каналов"""
        from PyQt5.QtWidgets import QListWidget, QListWidgetItem
        
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        title = QLabel("📋 Доступные каналы")
        title.setStyleSheet("font-weight: bold; padding: 5px; background-color: #e8e8e8;")
        layout.addWidget(title)
        
        # Список каналов
        self.channels_list = QListWidget()
        self.channels_list.setSelectionMode(QListWidget.MultiSelection)
        
        # Заполняем список
        for channel in self.generator.channels:
            item = QListWidgetItem(
                f"Ch{channel.id+1:02d}: {channel.name} "
                f"({str(channel.signal_type)})"
            )
            item.setData(Qt.UserRole, channel.id)
            self.channels_list.addItem(item)
            
        layout.addWidget(self.channels_list)
        
        # Информация о выбранных
        self.selection_info = QLabel("Выбрано: 0 каналов")
        self.selection_info.setStyleSheet("color: #666666; padding: 5px;")
        self.channels_list.itemSelectionChanged.connect(self.update_selection_info)
        layout.addWidget(self.selection_info)
        
        widget.setLayout(layout)
        return widget
        
    def _create_plots_panel(self):
        """Создать панель с графиками"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        title = QLabel("📈 Графики сигналов")
        title.setStyleSheet("font-weight: bold; padding: 5px; background-color: #e8e8e8;")
        layout.addWidget(title)
        
        # Виджет для графиков
        self.plots_widget = QWidget()
        self.plots_layout = QVBoxLayout()
        self.plots_widget.setLayout(self.plots_layout)
        
        # Добавляем контейнер для графиков
        from PyQt5.QtWidgets import QScrollArea
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: white; }")
        scroll.setWidget(self.plots_widget)
        
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
        
    def _create_info_panel(self):
        """Создать нижнюю информационную панель"""
        layout = QHBoxLayout()
        
        info_text = "💡 Кликните на каналы (Ctrl+клик для множественного выбора) и нажмите 'Добавить на график'"
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        self.plots_count_label = QLabel("Графиков: 0")
        self.plots_count_label.setStyleSheet("color: #999999; font-size: 9px;")
        layout.addWidget(self.plots_count_label)
        
        return layout
        
    def setup_plots(self):
        """Создать начальные графики"""
        # Создаем один пустой график по умолчанию
        self.plot_widgets = []
        self.plot_channels = []
        self.add_plot()
        
    def add_plot(self):
        """Добавить новый график"""
        plot_widget = PlotWidget(max_points=500)
        self.plot_widgets.append(plot_widget)
        self.plot_channels.append([])  # Список каналов для этого графика
        
        # Добавляем в layout
        self.plots_layout.addWidget(plot_widget)
        
        # Обновляем счетчик
        self.plots_count_label.setText(f"Графиков: {len(self.plot_widgets)}")
        
    def remove_plot(self, index):
        """Удалить график"""
        if len(self.plot_widgets) <= 1:
            return  # Должен быть хотя бы один график
            
        plot_widget = self.plot_widgets.pop(index)
        self.plot_channels.pop(index)
        self.plots_layout.removeWidget(plot_widget)
        plot_widget.deleteLater()
        
        self.plots_count_label.setText(f"Графиков: {len(self.plot_widgets)}")
        
    def add_selected_channels(self):
        """Добавить выбранные каналы на график"""
        selected_items = self.channels_list.selectedItems()
        if not selected_items:
            return
            
        # Получаем ID выбранных каналов
        channel_ids = []
        for item in selected_items:
            channel_id = item.data(Qt.UserRole)
            channel_ids.append(channel_id)
            
        # Находим свободный график или создаем новый
        target_plot = None
        for i, channels in enumerate(self.plot_channels):
            if len(channels) < self.max_channels_on_plot:
                target_plot = i
                break
                
        if target_plot is None:
            # Создаем новый график
            self.add_plot()
            target_plot = len(self.plot_widgets) - 1
            
        # Добавляем каналы на график
        for channel_id in channel_ids:
            if channel_id not in self.plot_channels[target_plot]:
                self.plot_channels[target_plot].append(channel_id)
                
        # Обновляем отображение графика
        self.update_plot_channels(target_plot)
        
    def clear_all_plots(self):
        """Очистить все графики"""
        for i in range(len(self.plot_channels)):
            self.plot_channels[i] = []
            self.plot_widgets[i].clear_plot()
            
    def auto_range_all(self):
        """Автомасштабирование для всех графиков"""
        for plot in self.plot_widgets:
            plot.auto_range()
            
    def set_max_channels(self, value):
        """Установить максимальное количество каналов на графике"""
        self.max_channels_on_plot = value
        
    def update_selection_info(self):
        """Обновить информацию о выбранных каналах"""
        count = len(self.channels_list.selectedItems())
        self.selection_info.setText(f"Выбрано: {count} каналов")
        
    def update_plot_channels(self, plot_index):
        """Обновить отображение каналов на графике"""
        plot = self.plot_widgets[plot_index]
        channel_ids = self.plot_channels[plot_index]
        
        # Очищаем график
        plot.clear_plot()
        
        # Добавляем линии для каждого канала
        colors = [(0, 100, 200), (200, 50, 50), (50, 200, 50), (200, 100, 0)]
        
        for i, channel_id in enumerate(channel_ids):
            channel = self.generator.get_channel(channel_id)
            if channel:
                # Используем данные из буфера
                pass  # Данные будут обновляться через update_plots
        
    def update_plots(self):
        """Обновить все графики"""
        if not self.is_running:
            return
            
        # Для каждого графика
        for i, (plot, channel_ids) in enumerate(zip(self.plot_widgets, self.plot_channels)):
            if not channel_ids:
                continue
                
            # Обновляем данные для каждого канала на графике
            # Берем первый канал для отображения (для простоты)
            # В реальном проекте нужно хранить данные для каждого канала отдельно
            channel_id = channel_ids[0]
            channel = self.generator.get_channel(channel_id)
            
            if channel and channel.enabled:
                plot.update_data(channel.current_value, 0.01)
                
            # Обновляем отображение
            plot.update_plot()
            
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        self.is_running = False
        self.timer.stop()
        event.accept()