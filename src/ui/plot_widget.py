import sys
import pyqtgraph as pg
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QComboBox, QCheckBox,
                             QSplitter, QFrame, QGridLayout, QSpinBox,
                             QDoubleSpinBox, QGroupBox, QTabWidget,
                             QListWidget, QListWidgetItem, QScrollArea)
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
        
        # Данные для хранения истории - используем numpy массивы для скорости
        self.time_data = np.zeros(max_points)
        self.value_data = np.zeros(max_points)
        self.data_index = 0
        self.is_full = False
        
        # Время старта для синхронизации
        self.start_time = 0
        
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
        
        # Основная линия сигнала - используем более яркий цвет
        self.curve = self.plot(
            self.time_data, 
            self.value_data,
            pen=pg.mkPen(color=(0, 150, 255), width=2, style=Qt.SolidLine),
            name='Сигнал'
        )
        
        # Линия среднего значения
        self.mean_curve = self.plot(
            self.time_data,
            np.zeros(len(self.time_data)),
            pen=pg.mkPen(color=(255, 150, 0), width=1, style=Qt.DashLine),
            name='Среднее'
        )
        
        # Заполненная область
        self.fill_curve = self.plot(
            self.time_data,
            self.value_data,
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
        
        # Текущее время
        current_time = self.data_index * time_step if not self.is_full else self.max_points * time_step
        
        # Добавляем новое значение
        if self.data_index < self.max_points:
            self.time_data[self.data_index] = current_time
            self.value_data[self.data_index] = value
            self.data_index += 1
        else:
            # Сдвигаем данные для FIFO
            self.time_data = np.roll(self.time_data, -1)
            self.value_data = np.roll(self.value_data, -1)
            self.time_data[-1] = current_time
            self.value_data[-1] = value
            self.is_full = True
            
    def update_plot(self):
        """Обновить отображение графика"""
        if not self.is_visible:
            return
        
        # Определяем количество точек для отображения
        if self.is_full:
            display_count = self.max_points
        else:
            display_count = self.data_index
            
        if display_count == 0:
            return
            
        # Обновляем основную кривую
        self.curve.setData(
            self.time_data[:display_count], 
            self.value_data[:display_count]
        )
        
        # Обновляем линию среднего
        if display_count > 0:
            mean_val = np.mean(self.value_data[:display_count])
            self.mean_curve.setData(
                self.time_data[:display_count], 
                np.full(display_count, mean_val)
            )
            
            # Обновляем заполненную область
            self.fill_curve.setData(
                self.time_data[:display_count],
                self.value_data[:display_count]
            )
        
    def auto_range(self):
        """Автоматическое масштабирование"""
        self.autoRange()
        
    def clear_plot(self):
        """Очистить данные графика"""
        self.time_data = np.zeros(self.max_points)
        self.value_data = np.zeros(self.max_points)
        self.data_index = 0
        self.is_full = False
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
    """Окно с графиками"""
    
    def __init__(self, generator: SignalGenerator, parent=None):
        super().__init__(parent)
        self.generator = generator
        self.setWindowTitle("📊 Графики сигналов")
        self.setGeometry(200, 200, 1200, 800)
        
        self.selected_channels = []
        self.max_channels_on_plot = 4
        
        # Хранилище данных для каждого канала
        self.channel_data = {}
        
        self.setup_ui()
        self.setup_plots()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(50)  # 20 FPS
        self.is_running = True
        
        # Счетчик времени для обновления
        self.update_counter = 0
        
    def setup_ui(self):
        """Настройка интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Панель управления
        control_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Добавить на график")
        self.add_btn.clicked.connect(self.add_selected_channels)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        control_layout.addWidget(self.add_btn)
        
        self.clear_btn = QPushButton("🗑 Очистить графики")
        self.clear_btn.clicked.connect(self.clear_all_plots)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        control_layout.addWidget(self.clear_btn)
        
        self.auto_btn = QPushButton("📐 Авто-масштаб")
        self.auto_btn.clicked.connect(self.auto_range_all)
        self.auto_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        control_layout.addWidget(self.auto_btn)
        
        control_layout.addStretch()
        
        control_layout.addWidget(QLabel("Каналов на графике:"))
        self.channels_spin = QSpinBox()
        self.channels_spin.setRange(1, 10)
        self.channels_spin.setValue(self.max_channels_on_plot)
        self.channels_spin.valueChanged.connect(self.set_max_channels)
        control_layout.addWidget(self.channels_spin)
        
        control_layout.addStretch()
        
        self.fps_label = QLabel("Обновлений: 0")
        self.fps_label.setStyleSheet("color: #666666;")
        control_layout.addWidget(self.fps_label)
        
        self.close_btn = QPushButton("✕ Закрыть")
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        control_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(control_layout)
        
        # Основной разделитель
        splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - список каналов
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        
        title = QLabel("📋 Доступные каналы (Ctrl+клик для множественного выбора)")
        title.setStyleSheet("font-weight: bold; padding: 5px; background-color: #e8e8e8;")
        left_layout.addWidget(title)
        
        self.channels_list = QListWidget()
        self.channels_list.setSelectionMode(QListWidget.MultiSelection)
        self.channels_list.setStyleSheet("""
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
        
        for channel in self.generator.channels:
            item = QListWidgetItem(
                f"Ch{channel.id+1:02d}: {channel.name} ({str(channel.signal_type)})"
            )
            item.setData(Qt.UserRole, channel.id)
            self.channels_list.addItem(item)
            
        left_layout.addWidget(self.channels_list)
        
        self.selection_info = QLabel("Выбрано: 0 каналов")
        self.selection_info.setStyleSheet("color: #666666; padding: 5px;")
        self.channels_list.itemSelectionChanged.connect(self.update_selection_info)
        left_layout.addWidget(self.selection_info)
        
        splitter.addWidget(left_widget)
        
        # Правая панель - графики
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        
        title = QLabel("📈 Графики сигналов (в реальном времени)")
        title.setStyleSheet("font-weight: bold; padding: 5px; background-color: #e8e8e8;")
        right_layout.addWidget(title)
        
        self.plots_widget = QWidget()
        self.plots_layout = QVBoxLayout()
        self.plots_layout.setSpacing(5)
        self.plots_widget.setLayout(self.plots_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: white; }")
        scroll.setWidget(self.plots_widget)
        
        right_layout.addWidget(scroll)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 900])
        
        main_layout.addWidget(splitter)
        
        # Информационная панель
        info_layout = QHBoxLayout()
        info_label = QLabel("💡 Выберите каналы и нажмите 'Добавить на график'")
        info_label.setStyleSheet("color: #666666; font-size: 10px;")
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        self.plots_count_label = QLabel("Графиков: 0")
        self.plots_count_label.setStyleSheet("color: #999999; font-size: 9px;")
        info_layout.addWidget(self.plots_count_label)
        main_layout.addLayout(info_layout)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
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
        
    def setup_plots(self):
        """Создать начальные графики"""
        self.plot_widgets = []
        self.plot_channels = []
        self.add_plot()
        
    def add_plot(self):
        """Добавить новый график"""
        plot_widget = PlotWidget(max_points=1000)  # Увеличили до 1000 точек
        self.plot_widgets.append(plot_widget)
        self.plot_channels.append([])
        self.plots_layout.addWidget(plot_widget)
        self.plots_count_label.setText(f"Графиков: {len(self.plot_widgets)}")
        
    def remove_plot(self, index):
        """Удалить график"""
        if len(self.plot_widgets) <= 1:
            return
            
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
            
        channel_ids = []
        for item in selected_items:
            channel_id = item.data(Qt.UserRole)
            channel_ids.append(channel_id)
            
        # Находим свободный график
        target_plot = None
        for i, channels in enumerate(self.plot_channels):
            if len(channels) < self.max_channels_on_plot:
                target_plot = i
                break
                
        if target_plot is None:
            self.add_plot()
            target_plot = len(self.plot_widgets) - 1
            
        # Инициализируем данные для каналов
        for channel_id in channel_ids:
            if channel_id not in self.plot_channels[target_plot]:
                self.plot_channels[target_plot].append(channel_id)
                # Инициализируем данные для канала
                if channel_id not in self.channel_data:
                    self.channel_data[channel_id] = {
                        'time': deque(maxlen=1000),
                        'value': deque(maxlen=1000),
                        'initialized': False
                    }
                
        self.update_plot_channels(target_plot)
        
    def clear_all_plots(self):
        """Очистить все графики"""
        for i in range(len(self.plot_channels)):
            self.plot_channels[i] = []
            self.plot_widgets[i].clear_plot()
        self.channel_data.clear()
            
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
        
        # Используем первый канал для отображения
        if channel_ids:
            plot.set_channel(channel_ids[0], f"Канал {channel_ids[0]+1}")
            
    def update_plots(self):
        """Обновить все графики"""
        if not self.is_running:
            return
            
        self.update_counter += 1
        
        # Обновляем данные для каждого графика
        for i, (plot, channel_ids) in enumerate(zip(self.plot_widgets, self.plot_channels)):
            if not channel_ids:
                continue
                
            # Обновляем данные для первого канала на графике
            channel_id = channel_ids[0]
            channel = self.generator.get_channel(channel_id)
            
            if channel and channel.enabled:
                # Инициализируем данные для канала если нужно
                if channel_id not in self.channel_data:
                    self.channel_data[channel_id] = {
                        'time': deque(maxlen=1000),
                        'value': deque(maxlen=1000),
                        'initialized': False
                    }
                
                data = self.channel_data[channel_id]
                
                # Добавляем новое значение
                current_time = len(data['time']) * 0.01
                data['time'].append(current_time)
                data['value'].append(channel.current_value)
                data['initialized'] = True
                
                # Обновляем данные в виджете графика
                plot.update_data(channel.current_value, 0.01)
                
            # Обновляем отображение графика
            plot.update_plot()
            
        # Обновляем FPS
        if self.update_counter % 20 == 0:
            self.fps_label.setText(f"Обновлений: {self.update_counter}")
            
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        self.is_running = False
        self.timer.stop()
        event.accept()