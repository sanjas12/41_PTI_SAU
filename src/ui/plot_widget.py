import sys
import pyqtgraph as pg
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QComboBox, QCheckBox,
                             QSplitter, QFrame, QGridLayout, QSpinBox,
                             QDoubleSpinBox, QGroupBox, QTabWidget,
                             QListWidget, QListWidgetItem, QScrollArea,
                             QMenu, QAction, QMessageBox, QInputDialog,
                             QToolButton, QButtonGroup, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint, QSize
from PyQt5.QtGui import QFont, QColor, QContextMenuEvent, QIcon
import numpy as np
import time
from collections import deque

from core.signal_generator import SignalGenerator
from core.channel import AnalogChannel


class PlotWidget(pg.PlotWidget):
    """Виджет графика для отображения сигнала"""
    
    # Сигналы для управления
    remove_requested = pyqtSignal(int)  # index
    clear_requested = pyqtSignal(int)   # index
    add_channel_requested = pyqtSignal(int)  # plot_index
    
    def __init__(self, plot_index, max_points=2000, time_window=10.0, parent=None):
        super().__init__(parent)
        self.plot_index = plot_index
        self.max_points = max_points
        self.time_window = time_window
        self.is_visible = True
        self.channel_ids = []  # Список ID каналов на этом графике
        
        # Данные для хранения истории по каналам
        self.channel_data = {}  # channel_id -> (time_data, value_data)
        self.curves = {}  # channel_id -> curve_object
        self.colors = [
            (0, 150, 255),   # Синий
            (255, 80, 80),   # Красный
            (80, 200, 80),   # Зеленый
            (255, 150, 0),   # Оранжевый
            (180, 0, 255),   # Фиолетовый
            (0, 200, 200),   # Бирюзовый
            (255, 0, 150),   # Розовый
            (100, 100, 100), # Серый
        ]
        
        self.start_time = time.time()
        self.setup_plot()
        
    def setup_plot(self):
        """Настройка графика"""
        self.setLabel('left', 'Значение', units='%')
        self.setLabel('bottom', 'Время', units='с')
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setMouseEnabled(x=True, y=True)
        self.addLegend()
        
        # Контекстное меню
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Заголовок графика
        self.setTitle(f"График {self.plot_index + 1}")
        
        # Устанавливаем минимальную высоту
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
    def show_context_menu(self, position):
        """Показать контекстное меню графика"""
        menu = QMenu()
        
        clear_action = QAction("🗑 Очистить график", self)
        clear_action.triggered.connect(lambda: self.clear_requested.emit(self.plot_index))
        menu.addAction(clear_action)
        
        add_action = QAction("➕ Добавить канал", self)
        add_action.triggered.connect(lambda: self.add_channel_requested.emit(self.plot_index))
        menu.addAction(add_action)
        
        menu.addSeparator()
        
        # Показать список каналов на графике
        if self.channel_ids:
            channel_menu = QMenu("📊 Каналы на графике")
            for ch_id in self.channel_ids:
                channel = self.parent() and hasattr(self.parent(), 'generator') and self.parent().generator.get_channel(ch_id)
                if channel:
                    action = QAction(f"Ch{ch_id+1}: {channel.name}", self)
                    action.setEnabled(False)
                    channel_menu.addAction(action)
            menu.addMenu(channel_menu)
        
        menu.addSeparator()
        
        remove_action = QAction("❌ Удалить график", self)
        remove_action.triggered.connect(lambda: self.remove_requested.emit(self.plot_index))
        menu.addAction(remove_action)
        
        menu.exec_(self.mapToGlobal(position))
        
    def set_channel(self, channel_id, color_index=None):
        """Добавить канал на график"""
        if channel_id in self.channel_ids:
            return
            
        self.channel_ids.append(channel_id)
        
        # Инициализируем данные
        self.channel_data[channel_id] = {
            'time': deque(maxlen=self.max_points),
            'value': deque(maxlen=self.max_points),
            'color_index': color_index if color_index is not None else len(self.channel_ids) - 1
        }
        
        # Создаем кривую
        color = self.colors[self.channel_data[channel_id]['color_index'] % len(self.colors)]
        curve = self.plot(
            [], [],
            pen=pg.mkPen(color=color, width=2),
            name=f"Канал {channel_id+1}"
        )
        self.curves[channel_id] = curve
        
        # Обновляем легенду
        self.update_legend()
        
        # Обновляем заголовок
        self.update_title()
        
    def remove_channel(self, channel_id):
        """Удалить канал с графика"""
        if channel_id not in self.channel_ids:
            return
            
        self.channel_ids.remove(channel_id)
        
        # Удаляем кривую
        if channel_id in self.curves:
            self.removeItem(self.curves[channel_id])
            del self.curves[channel_id]
            
        # Удаляем данные
        if channel_id in self.channel_data:
            del self.channel_data[channel_id]
            
        # Обновляем легенду
        self.update_legend()
        self.update_title()
        
    def update_legend(self):
        """Обновить легенду"""
        # Пересоздаем легенду
        self.plotItem.legend = None
        self.addLegend()
        
        # Добавляем все кривые в легенду
        for channel_id, curve in self.curves.items():
            channel = self.parent() and hasattr(self.parent(), 'generator') and self.parent().generator.get_channel(channel_id)
            name = f"Канал {channel_id+1}"
            if channel:
                name = f"{channel.name}"
            self.plotItem.legend.addItem(curve, name)
            
    def update_title(self):
        """Обновить заголовок графика"""
        if self.channel_ids:
            names = []
            for ch_id in self.channel_ids:
                channel = self.parent() and hasattr(self.parent(), 'generator') and self.parent().generator.get_channel(ch_id)
                if channel:
                    names.append(channel.name)
                else:
                    names.append(f"Ch{ch_id+1}")
            title = f"График {self.plot_index + 1}: {', '.join(names)}"
            if len(title) > 60:
                title = title[:57] + "..."
            self.setTitle(title)
        else:
            self.setTitle(f"График {self.plot_index + 1} (пусто)")
            
    def update_data(self, channel_id, value):
        """Обновить данные для канала"""
        if channel_id not in self.channel_data:
            return
            
        current_time = time.time() - self.start_time
        data = self.channel_data[channel_id]
        data['time'].append(current_time)
        data['value'].append(value)
        
        # Обновляем кривую
        if channel_id in self.curves:
            self.curves[channel_id].setData(
                list(data['time']),
                list(data['value'])
            )
            
    def update_plot(self):
        """Обновить отображение графика"""
        if not self.is_visible:
            return
            
        # Обновляем все кривые
        for channel_id, data in self.channel_data.items():
            if channel_id in self.curves:
                self.curves[channel_id].setData(
                    list(data['time']),
                    list(data['value'])
                )
                
        # Автомасштабирование оси X
        if self.channel_ids:
            current_time = time.time() - self.start_time
            min_time = max(0, current_time - self.time_window)
            self.setXRange(min_time, current_time, padding=0.05)
            
    def clear_plot(self):
        """Очистить все данные графика"""
        self.channel_ids.clear()
        self.channel_data.clear()
        
        # Удаляем все кривые
        for curve in self.curves.values():
            self.removeItem(curve)
        self.curves.clear()
        
        # Обновляем легенду
        self.update_legend()
        self.update_title()
        
    def get_channel_count(self):
        """Получить количество каналов на графике"""
        return len(self.channel_ids)
        
    def get_channel_ids(self):
        """Получить список ID каналов на графике"""
        return self.channel_ids.copy()
        
    def set_time_window(self, time_window):
        """Установить временное окно"""
        self.time_window = time_window
        
    def showEvent(self, event):
        self.is_visible = True
        super().showEvent(event)
        
    def hideEvent(self, event):
        self.is_visible = False
        super().hideEvent(event)


class PlotWindow(QMainWindow):
    """Окно с графиками"""
    
    def __init__(self, generator: SignalGenerator, parent=None):
        super().__init__(parent)
        self.generator = generator
        self.setWindowTitle("📊 Графики сигналов")
        
        # Увеличиваем размер окна для размещения всех графиков без скролла
        # Получаем размер экрана
        screen = QApplication.primaryScreen()
        screen_size = screen.availableGeometry()
        
        # Устанавливаем окно на весь экран с небольшим отступом
        width = screen_size.width() - 40
        height = screen_size.height() - 60
        
        self.setGeometry(20, 30, width, height)
        
        # Список графиков
        self.plot_widgets = []
        self.next_plot_index = 0
        
        # Настройки
        self.time_window = 10.0  # секунд
        self.max_points = 2000
        self.plot_height = 200  # Высота каждого графика (уменьшена для размещения большего количества)
        
        # Инициализируем виджеты
        self.channels_list = None
        self.selection_info = None
        self.plots_container = None
        self.plots_layout = None
        self.plots_count_label = None
        self.fps_label = None
        self.add_selected_btn = None
        self.time_window_spin = None
        self.height_spin = None
        
        self.setup_ui()
        self.setup_connections()
        
        # Таймер обновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(50)  # 20 FPS
        self.is_running = True
        
        # Счетчик обновлений
        self.update_counter = 0
        
        # Добавляем начальный график
        self.add_plot()
        self._update_channels_list()
        
    def setup_ui(self):
        """Настройка интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(3)
        central_widget.setLayout(main_layout)
        
        # Верхняя панель управления
        control_layout = self._create_control_panel()
        main_layout.addLayout(control_layout)
        
        # Основная область с графиками - без скролла
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        
        # Левая панель - список каналов (меньше)
        left_panel = self._create_channels_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - графики
        right_panel = self._create_plots_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([250, width - 280])  # Динамический размер
        main_layout.addWidget(splitter)
        
        # Нижняя информационная панель
        info_layout = self._create_info_panel()
        main_layout.addLayout(info_layout)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 4px 10px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 9px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton#remove_btn {
                background-color: #f44336;
            }
            QPushButton#remove_btn:hover {
                background-color: #da190b;
            }
            QListWidget {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background-color: white;
                font-size: 9px;
            }
            QListWidget::item {
                padding: 3px;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e8f5e9;
            }
            QLabel {
                font-size: 9px;
            }
            QSpinBox, QDoubleSpinBox {
                font-size: 9px;
                padding: 2px;
            }
            QGroupBox {
                font-size: 9px;
            }
        """)
        
    def _create_control_panel(self):
        """Создать панель управления"""
        layout = QHBoxLayout()
        layout.setSpacing(5)
        
        # Кнопка добавления графика
        self.add_plot_btn = QPushButton("➕ Добавить график")
        self.add_plot_btn.clicked.connect(self.add_plot)
        layout.addWidget(self.add_plot_btn)
        
        # Кнопка удаления последнего графика
        self.remove_last_btn = QPushButton("➖ Удалить график")
        self.remove_last_btn.clicked.connect(self.remove_last_plot)
        self.remove_last_btn.setObjectName("remove_btn")
        layout.addWidget(self.remove_last_btn)
        
        # Кнопка очистки всех графиков
        self.clear_all_btn = QPushButton("🗑 Очистить все")
        self.clear_all_btn.clicked.connect(self.clear_all_plots)
        self.clear_all_btn.setObjectName("remove_btn")
        layout.addWidget(self.clear_all_btn)
        
        # Кнопка авто-масштаб
        self.auto_btn = QPushButton("📐 Авто-масштаб")
        self.auto_btn.clicked.connect(self.auto_range_all)
        layout.addWidget(self.auto_btn)
        
        layout.addStretch()
        
        # Настройка высоты графиков
        layout.addWidget(QLabel("Высота:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(150, 400)
        self.height_spin.setValue(self.plot_height)
        self.height_spin.setSingleStep(10)
        self.height_spin.setSuffix(" px")
        self.height_spin.setMaximumWidth(80)
        self.height_spin.valueChanged.connect(self.on_height_changed)
        layout.addWidget(self.height_spin)
        
        layout.addStretch()
        
        # Настройка временного окна
        layout.addWidget(QLabel("Окно (с):"))
        self.time_window_spin = QDoubleSpinBox()
        self.time_window_spin.setRange(1, 60)
        self.time_window_spin.setValue(self.time_window)
        self.time_window_spin.setSingleStep(1)
        self.time_window_spin.setMaximumWidth(60)
        self.time_window_spin.valueChanged.connect(self.on_time_window_changed)
        layout.addWidget(self.time_window_spin)
        
        layout.addStretch()
        
        self.fps_label = QLabel("Обновлений: 0")
        self.fps_label.setStyleSheet("color: #666666; font-size: 8px;")
        layout.addWidget(self.fps_label)
        
        return layout
        
    def _create_channels_panel(self):
        """Создать панель со списком каналов"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        widget.setLayout(layout)
        
        title = QLabel("📋 Каналы")
        title.setStyleSheet("font-weight: bold; padding: 3px; background-color: #e8e8e8; font-size: 9px;")
        layout.addWidget(title)
        
        # Список каналов с контекстным меню
        self.channels_list = QListWidget()
        self.channels_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.channels_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.channels_list.customContextMenuRequested.connect(self.show_channel_menu)
        self.channels_list.setMaximumWidth(200)
        
        layout.addWidget(self.channels_list)
        
        # Информация
        info_layout = QHBoxLayout()
        info_layout.setSpacing(2)
        
        self.selection_info = QLabel("Выбрано: 0")
        self.selection_info.setStyleSheet("color: #666666; font-size: 8px;")
        info_layout.addWidget(self.selection_info)
        
        info_layout.addStretch()
        
        self.add_selected_btn = QPushButton("➕")
        self.add_selected_btn.clicked.connect(self.add_selected_channels)
        self.add_selected_btn.setToolTip("Добавить выбранные каналы на график")
        self.add_selected_btn.setMaximumWidth(25)
        self.add_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
                padding: 2px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        info_layout.addWidget(self.add_selected_btn)
        
        layout.addLayout(info_layout)
        
        return widget
        
    def _create_plots_panel(self):
        """Создать панель с графиками (без скролла)"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        widget.setLayout(layout)
        
        title = QLabel("📈 Графики (ПКМ → меню)")
        title.setStyleSheet("font-weight: bold; padding: 3px; background-color: #e8e8e8; font-size: 9px;")
        layout.addWidget(title)
        
        # Область с графиками - без скролла
        self.plots_container = QWidget()
        self.plots_layout = QVBoxLayout()
        self.plots_layout.setSpacing(5)
        self.plots_layout.setContentsMargins(2, 2, 2, 2)
        self.plots_container.setLayout(self.plots_layout)
        
        layout.addWidget(self.plots_container)
        
        return widget
        
    def _create_info_panel(self):
        """Создать информационную панель"""
        layout = QHBoxLayout()
        layout.setSpacing(5)
        
        info_label = QLabel("💡 Клик → выбор | Ctrl+клик → множественный | ПКМ → меню")
        info_label.setStyleSheet("color: #666666; font-size: 8px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        self.plots_count_label = QLabel("Графиков: 0")
        self.plots_count_label.setStyleSheet("color: #999999; font-size: 8px;")
        layout.addWidget(self.plots_count_label)
        
        return layout
        
    def _update_channels_list(self):
        """Обновить список каналов"""
        if self.channels_list is None:
            return
            
        self.channels_list.clear()
        for channel in self.generator.channels:
            plot_indices = []
            for i, plot in enumerate(self.plot_widgets):
                if channel.id in plot.get_channel_ids():
                    plot_indices.append(str(i + 1))
            
            status = f" [Гр.{', '.join(plot_indices)}]" if plot_indices else ""
            type_color = {
                'Sine': '#2196F3',
                'Square': '#f44336',
                'Sawtooth': '#FF9800',
                'Triangle': '#4CAF50',
                'Random': '#9C27B0',
                'Custom': '#795548'
            }.get(str(channel.signal_type), '#666666')
            
            item = QListWidgetItem(
                f"Ch{channel.id+1:02d}: {channel.name[:8]} "
                f"<span style='color:{type_color};'>({str(channel.signal_type)[:4]})</span>{status}"
            )
            item.setData(Qt.UserRole, channel.id)
            
            if plot_indices:
                item.setBackground(QColor(200, 255, 200))
                
            self.channels_list.addItem(item)
            
        self.update_selection_info()
        
    def show_channel_menu(self, position):
        """Показать контекстное меню для канала"""
        if self.channels_list is None:
            return
            
        item = self.channels_list.itemAt(position)
        if not item:
            return
            
        channel_id = item.data(Qt.UserRole)
        if channel_id is None:
            return
            
        channel = self.generator.get_channel(channel_id)
        if not channel:
            return
            
        menu = QMenu()
        
        add_action = QAction("➕ Добавить на график", self)
        add_action.triggered.connect(lambda: self.add_channel_to_plot(channel_id))
        menu.addAction(add_action)
        
        plot_indices = []
        for i, plot in enumerate(self.plot_widgets):
            if channel_id in plot.get_channel_ids():
                plot_indices.append(i)
                
        if plot_indices:
            remove_menu = QMenu("❌ Удалить с графиков")
            for plot_index in plot_indices:
                action = QAction(f"С графика {plot_index + 1}", self)
                action.triggered.connect(
                    lambda checked, pi=plot_index, cid=channel_id: 
                    self.remove_channel_from_plot(cid, pi)
                )
                remove_menu.addAction(action)
            menu.addMenu(remove_menu)
            
        info_action = QAction(
            f"ℹ️ {channel.name[:10]} | {channel.min_value:.0f}-{channel.max_value:.0f} | {channel.frequency:.1f} Гц",
            self
        )
        info_action.setEnabled(False)
        menu.addAction(info_action)
            
        menu.exec_(self.channels_list.mapToGlobal(position))
        
    def add_channel_to_plot(self, channel_id, plot_index=None):
        """Добавить канал на график"""
        if plot_index is None:
            if self.plot_widgets:
                plot_index = min(
                    range(len(self.plot_widgets)), 
                    key=lambda i: self.plot_widgets[i].get_channel_count()
                )
            else:
                self.add_plot()
                plot_index = 0
                
        if plot_index >= len(self.plot_widgets):
            self.add_plot()
            plot_index = len(self.plot_widgets) - 1
            
        plot = self.plot_widgets[plot_index]
        
        if channel_id not in plot.get_channel_ids():
            plot.set_channel(channel_id)
            self._update_channels_list()
            
            channel = self.generator.get_channel(channel_id)
            if channel:
                print(f"[ГРАФИК] Канал {channel_id+1} добавлен на график {plot_index + 1}")
        else:
            print(f"[ГРАФИК] Канал {channel_id+1} уже есть на графике {plot_index + 1}")
            
    def remove_channel_from_plot(self, channel_id, plot_index):
        """Удалить канал с графика"""
        plot = self.plot_widgets[plot_index]
        plot.remove_channel(channel_id)
        self._update_channels_list()
        
    def add_selected_channels(self):
        """Добавить выбранные каналы на графики"""
        if self.channels_list is None:
            return
            
        selected_items = self.channels_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Информация", "Выберите каналы для добавления")
            return
        
        selected_channel_ids = []
        for item in selected_items:
            channel_id = item.data(Qt.UserRole)
            if channel_id is not None:
                selected_channel_ids.append(channel_id)
        
        if not selected_channel_ids:
            return
            
        plot_indices = [str(i + 1) for i in range(len(self.plot_widgets))]
        plot_indices.append("Новый график")
        
        plot_index_str, ok = QInputDialog.getItem(
            self,
            "Выбор графика",
            "Выберите график для добавления каналов:",
            plot_indices,
            0,
            False
        )
        
        if not ok:
            return
            
        if plot_index_str == "Новый график":
            self.add_plot()
            plot_index = len(self.plot_widgets) - 1
        else:
            plot_index = int(plot_index_str) - 1
            
        plot = self.plot_widgets[plot_index]
        
        added_count = 0
        for channel_id in selected_channel_ids:
            if channel_id not in plot.get_channel_ids():
                plot.set_channel(channel_id)
                added_count += 1
        
        self._update_channels_list()
        
        if added_count > 0:
            self.selection_info.setText(f"✅ +{added_count}")
            self.selection_info.setStyleSheet("color: #4CAF50; font-size: 8px;")
        else:
            self.selection_info.setText("⚠️ уже есть")
            self.selection_info.setStyleSheet("color: #FF9800; font-size: 8px;")
        
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1500, self.update_selection_info)
        
    def setup_connections(self):
        """Настройка сигналов"""
        if self.channels_list:
            self.channels_list.itemSelectionChanged.connect(self.update_selection_info)
        
    def update_selection_info(self):
        """Обновить информацию о выбранных каналах"""
        if self.channels_list is None:
            return
        count = len(self.channels_list.selectedItems())
        if self.selection_info:
            self.selection_info.setText(f"Выбрано: {count}")
            self.selection_info.setStyleSheet("color: #666666; font-size: 8px;")
        
    def add_plot(self):
        """Добавить новый график"""
        plot = PlotWidget(
            self.next_plot_index,
            max_points=self.max_points,
            time_window=self.time_window
        )
        plot.remove_requested.connect(self.remove_plot)
        plot.clear_requested.connect(self.clear_plot)
        plot.add_channel_requested.connect(self.on_add_channel_requested)
        
        # Устанавливаем высоту
        plot.setMinimumHeight(self.plot_height)
        plot.setMaximumHeight(self.plot_height + 30)
        
        self.plot_widgets.append(plot)
        self.plots_layout.addWidget(plot)
        self.next_plot_index += 1
        
        if self.plots_count_label:
            self.plots_count_label.setText(f"Графиков: {len(self.plot_widgets)}")
        
        print(f"[ГРАФИК] Добавлен график #{self.next_plot_index}")
        
        self._update_channels_list()
        
        return plot
        
    def remove_last_plot(self):
        """Удалить последний график"""
        if len(self.plot_widgets) <= 1:
            QMessageBox.information(self, "Информация", "Должен быть хотя бы один график")
            return
            
        plot_index = len(self.plot_widgets) - 1
        self.remove_plot(plot_index)
        
    def remove_plot(self, plot_index):
        """Удалить график"""
        if len(self.plot_widgets) <= 1:
            QMessageBox.information(self, "Информация", "Должен быть хотя бы один график")
            return
            
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить график {plot_index + 1}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        plot = self.plot_widgets[plot_index]
        self.plots_layout.removeWidget(plot)
        plot.deleteLater()
        self.plot_widgets.pop(plot_index)
        
        for i, p in enumerate(self.plot_widgets):
            p.plot_index = i
            
        if self.plots_count_label:
            self.plots_count_label.setText(f"Графиков: {len(self.plot_widgets)}")
        self._update_channels_list()
        
    def clear_plot(self, plot_index):
        """Очистить график"""
        plot = self.plot_widgets[plot_index]
        plot.clear_plot()
        self._update_channels_list()
        
    def on_add_channel_requested(self, plot_index):
        """Запрос на добавление канала на график"""
        channel_ids = [ch.id for ch in self.generator.channels]
        channel_names = [f"Ch{ch.id+1}: {ch.name} ({str(ch.signal_type)})" for ch in self.generator.channels]
        
        channel_name, ok = QInputDialog.getItem(
            self,
            "Добавить канал",
            "Выберите канал для добавления на график:",
            channel_names,
            0,
            False
        )
        
        if ok:
            channel_id = channel_ids[channel_names.index(channel_name)]
            self.add_channel_to_plot(channel_id, plot_index)
            
    def clear_all_plots(self):
        """Очистить все графики"""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Очистить все графики?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for plot in self.plot_widgets:
                plot.clear_plot()
            self._update_channels_list()
            
    def auto_range_all(self):
        """Автомасштабирование для всех графиков"""
        for plot in self.plot_widgets:
            plot.autoRange()
            
    def on_time_window_changed(self, value):
        """Изменено временное окно"""
        self.time_window = value
        for plot in self.plot_widgets:
            plot.set_time_window(value)
            
    def on_height_changed(self, value):
        """Изменена высота графиков"""
        self.plot_height = value
        for plot in self.plot_widgets:
            plot.setMinimumHeight(value)
            plot.setMaximumHeight(value + 30)
            
    def update_plots(self):
        """Обновить все графики"""
        if not self.is_running:
            return
            
        self.update_counter += 1
        
        values = self.generator.get_values()
        
        for plot in self.plot_widgets:
            for channel_id in plot.get_channel_ids():
                if 0 <= channel_id < len(values):
                    plot.update_data(channel_id, values[channel_id])
            plot.update_plot()
            
        if self.update_counter % 20 == 0:
            if self.fps_label:
                self.fps_label.setText(f"Обновлений: {self.update_counter}")
            
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        self.is_running = False
        self.timer.stop()
        event.accept()