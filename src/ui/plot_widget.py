import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.signal_generator import SignalGenerator
from ui.styles import COLORS as UI_COLORS
from ui.styles import app_stylesheet


class ChannelBuffer:
    """Кольцевой буфер для хранения истории одного канала."""

    def __init__(self, max_points: int):
        self.max_points = max_points

        self.time = np.empty(max_points, dtype=np.float64)
        self.value = np.empty(max_points, dtype=np.float64)

        self.position = 0
        self.count = 0

    def append(self, timestamp: float, value: float) -> None:
        """Добавить одну точку."""
        self.time[self.position] = timestamp
        self.value[self.position] = value

        self.position = (self.position + 1) % self.max_points

        if self.count < self.max_points:
            self.count += 1

    def get_data(self):
        """Получить данные в правильном временном порядке."""
        if self.count == 0:
            return (
                self.time[:0],
                self.value[:0],
            )

        if self.count < self.max_points:
            return (
                self.time[: self.count],
                self.value[: self.count],
            )

        # Буфер заполнен.
        # position указывает на самую старую точку.
        if self.position == 0:
            return self.time, self.value

        return (
            np.concatenate(
                (
                    self.time[self.position :],
                    self.time[: self.position],
                )
            ),
            np.concatenate(
                (
                    self.value[self.position :],
                    self.value[: self.position],
                )
            ),
        )

    def clear(self) -> None:
        """Очистить буфер."""
        self.position = 0
        self.count = 0


class PlotWidget(pg.PlotWidget):
    """График для отображения нескольких каналов."""

    remove_requested = pyqtSignal(int)
    clear_requested = pyqtSignal(int)
    add_channel_requested = pyqtSignal(int)

    COLORS = [
        (0, 150, 255),
        (255, 80, 80),
        (80, 200, 80),
        (255, 150, 0),
        (180, 0, 255),
        (0, 200, 200),
        (255, 0, 150),
        (100, 100, 100),
    ]

    def __init__(
        self,
        plot_index: int,
        generator: SignalGenerator,
        max_points: int = 2000,
        time_window: float = 10.0,
        parent=None,
    ):
        super().__init__(parent)

        self.plot_index = plot_index
        self.generator = generator

        self.max_points = max_points
        self.time_window = time_window

        self.is_visible = True

        # channel_id -> ChannelBuffer
        self.channel_data: Dict[int, ChannelBuffer] = {}

        # channel_id -> PlotDataItem
        self.curves: Dict[int, pg.PlotDataItem] = {}

        # channel_id -> цвет
        self.channel_colors: Dict[int, int] = {}

        self.start_time = time.monotonic()

        self._legend = None

        self.setup_plot()

    # ------------------------------------------------------------------
    # Настройка
    # ------------------------------------------------------------------

    def setup_plot(self) -> None:
        """Настроить внешний вид графика."""

        self.setBackground("#101214")
        self.getPlotItem().setContentsMargins(6, 5, 6, 4)

        for axis_name in ("left", "bottom"):
            axis = self.getAxis(axis_name)
            axis.setPen(pg.mkPen("#8a929b"))
            axis.setTextPen(pg.mkPen("#c7cdd3"))

        self.setLabel(
            "left",
            "Значение",
            units="%",
            color="#c7cdd3",
        )

        self.setLabel(
            "bottom",
            "Время",
            units="с",
            color="#c7cdd3",
        )

        self.showGrid(
            x=True,
            y=True,
            alpha=0.28,
        )

        self.setMouseEnabled(
            x=True,
            y=True,
        )

        self._legend = self.addLegend(
            brush=pg.mkBrush(24, 27, 30, 220),
            pen=pg.mkPen("#525a63"),
        )

        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.customContextMenuRequested.connect(self.show_context_menu)

        self.setMinimumHeight(200)
        self.setStyleSheet(
            f"border: 1px solid {UI_COLORS['border']}; border-radius: 3px;"
        )

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        self.update_title()

    # ------------------------------------------------------------------
    # Информация о каналах
    # ------------------------------------------------------------------

    def get_channel(self, channel_id: int):
        """Получить канал генератора."""
        return self.generator.get_channel(channel_id)

    def get_channel_name(self, channel_id: int) -> str:
        """Получить отображаемое имя канала."""
        channel = self.get_channel(channel_id)

        if channel is None:
            return f"Ch{channel_id + 1}"

        return channel.name

    # ------------------------------------------------------------------
    # Работа с каналами
    # ------------------------------------------------------------------

    def set_channel(
        self,
        channel_id: int,
        color_index: Optional[int] = None,
    ) -> None:
        """Добавить канал на график."""

        if channel_id in self.channel_data:
            return

        if color_index is None:
            color_index = len(self.channel_data)

        self.channel_data[channel_id] = ChannelBuffer(self.max_points)

        self.channel_colors[channel_id] = color_index

        color = self.COLORS[color_index % len(self.COLORS)]

        name = self.get_channel_name(channel_id)

        curve = self.plot(
            [],
            [],
            pen=pg.mkPen(
                color=color,
                width=2,
            ),
            name=name,
        )

        self.curves[channel_id] = curve

        self.update_title()

    def remove_channel(self, channel_id: int) -> None:
        """Удалить канал с графика."""

        if channel_id not in self.channel_data:
            return

        curve = self.curves.pop(
            channel_id,
            None,
        )

        if curve is not None:
            self.removeItem(curve)

        self.channel_data.pop(
            channel_id,
            None,
        )

        self.channel_colors.pop(
            channel_id,
            None,
        )

        self.update_legend()
        self.update_title()

    def clear_plot(self) -> None:
        """Полностью очистить график."""

        for curve in self.curves.values():
            self.removeItem(curve)

        self.curves.clear()
        self.channel_data.clear()
        self.channel_colors.clear()

        self.update_legend()
        self.update_title()

    def get_channel_count(self) -> int:
        """Количество каналов."""
        return len(self.channel_data)

    def get_channel_ids(self) -> List[int]:
        """Список ID каналов."""
        return list(self.channel_data.keys())

    # ------------------------------------------------------------------
    # Данные
    # ------------------------------------------------------------------

    def append_value(
        self,
        channel_id: int,
        value: float,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Добавить новое значение.

        ВАЖНО:
        Здесь график НЕ перерисовывается.
        """

        buffer = self.channel_data.get(channel_id)

        if buffer is None:
            return

        try:
            value = float(value)
        except (TypeError, ValueError):
            return

        if not np.isfinite(value):
            return

        if timestamp is None:
            channel = self.generator.get_channel(channel_id)
            if channel is not None:
                timestamp = channel.time
            else:
                timestamp = time.monotonic() - self.start_time

        buffer.append(
            timestamp,
            value,
        )

    def update_plot(self, current_time: Optional[float] = None) -> None:
        """
        Обновить визуальное представление.

        Этот метод вызывается один раз за кадр.
        """

        if not self.is_visible:
            return

        for channel_id, buffer in self.channel_data.items():
            curve = self.curves.get(channel_id)

            if curve is None:
                continue

            x, y = buffer.get_data()

            channel = self.generator.get_channel(channel_id)
            if channel is not None and channel.signal_type.is_discrete():
                x, y = self._build_step_curve(x, y)

            curve.setData(
                x,
                y,
            )

        if not self.channel_data:
            return

        resolved_current_time: float = 0.0 if current_time is None else current_time
        if current_time is None:
            # Получаем максимальное время из каналов
            for channel_id in self.get_channel_ids():
                channel = self.generator.get_channel(channel_id)
                if channel is not None and channel.time > resolved_current_time:
                    resolved_current_time = channel.time

        min_time = max(
            0.0,
            resolved_current_time - self.time_window,
        )

        self.setXRange(
            min_time,
            max(resolved_current_time, self.time_window),
            padding=0.02,
        )

    @staticmethod
    def _build_step_curve(
        x: np.ndarray, y: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Преобразовать точки в ступенчатую линию с вертикальными фронтами."""
        if x.size < 2:
            return x, y
        step_x = np.repeat(x, 2)[1:]
        step_y = np.repeat(y, 2)[:-1]
        return step_x, step_y

    # ------------------------------------------------------------------
    # Легенда
    # ------------------------------------------------------------------

    def update_legend(self) -> None:
        """Пересоздать легенду."""

        if self._legend is not None:
            self._legend.scene().removeItem(self._legend)

        self._legend = self.addLegend(
            brush=pg.mkBrush(24, 27, 30, 220),
            pen=pg.mkPen("#525a63"),
        )

        for channel_id, curve in self.curves.items():
            name = self.get_channel_name(channel_id)

            self._legend.addItem(  # type: ignore
                curve,
                name,
            )

    # ------------------------------------------------------------------
    # Заголовок
    # ------------------------------------------------------------------

    def update_title(self) -> None:
        """Обновить заголовок графика."""

        channel_ids = self.get_channel_ids()

        if not channel_ids:
            self.setTitle(
                f"График {self.plot_index + 1} · каналы не добавлены",
                color="#aeb6be",
                size="9pt",
            )
            return

        names = [self.get_channel_name(channel_id) for channel_id in channel_ids]

        title = f"График {self.plot_index + 1}: {', '.join(names)}"

        if len(title) > 60:
            title = title[:57] + "..."

        self.setTitle(title, color="#e5e9ed", size="9pt")

    # ------------------------------------------------------------------
    # Настройки
    # ------------------------------------------------------------------

    def set_time_window(
        self,
        time_window: float,
    ) -> None:
        """Изменить временное окно."""

        self.time_window = max(
            0.1,
            float(time_window),
        )

    # ------------------------------------------------------------------
    # Контекстное меню
    # ------------------------------------------------------------------

    def show_context_menu(self, position) -> None:
        """Показать контекстное меню."""

        menu = QMenu(self)

        clear_action = QAction(
            "Очистить данные графика",
            self,
        )

        clear_action.triggered.connect(
            lambda: self.clear_requested.emit(self.plot_index)
        )

        menu.addAction(clear_action)

        add_action = QAction(
            "Добавить канал",
            self,
        )

        add_action.triggered.connect(
            lambda: self.add_channel_requested.emit(self.plot_index)
        )

        menu.addAction(add_action)

        if self.channel_data:
            menu.addSeparator()

            channel_menu = QMenu(
                "Каналы на графике",
                self,
            )

            for channel_id in self.get_channel_ids():
                action = QAction(
                    f"Ch{channel_id + 1}: {self.get_channel_name(channel_id)}",
                    self,
                )

                action.setEnabled(False)

                channel_menu.addAction(action)

            menu.addMenu(channel_menu)

        menu.addSeparator()

        remove_action = QAction(
            "Удалить график",
            self,
        )

        remove_action.triggered.connect(
            lambda: self.remove_requested.emit(self.plot_index)
        )

        menu.addAction(remove_action)

        menu.exec_(self.mapToGlobal(position))

    # ------------------------------------------------------------------
    # Видимость
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        self.is_visible = True
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self.is_visible = False
        super().hideEvent(event)


class PlotWindow(QMainWindow):
    """Главное окно графиков."""

    UPDATE_INTERVAL_MS = 50

    def __init__(
        self,
        generator: SignalGenerator,
        parent=None,
    ):
        super().__init__(parent)

        self.generator = generator

        self.setWindowTitle("Графики сигналов")

        self._setup_window_geometry()

        # --------------------------------------------------------------
        # Настройки
        # --------------------------------------------------------------

        self.time_window = 10.0
        self.max_points = 2000
        self.plot_height = 320

        # --------------------------------------------------------------
        # Графики
        # --------------------------------------------------------------

        self.plot_widgets: List[PlotWidget] = []

        # --------------------------------------------------------------
        # UI
        # --------------------------------------------------------------

        self.channels_list: QListWidget
        self.selection_info: QLabel
        self.plots_container: QWidget
        self.plots_layout: QVBoxLayout
        self.plots_count_label: QLabel
        self.fps_label: QLabel
        self.add_selected_btn: QPushButton
        self.time_window_spin: QDoubleSpinBox
        self.height_spin: QSpinBox
        self.progress_bar: QProgressBar  # ← НОВЫЙ ВИДЖЕТ
        self.progress_label: QLabel  # ← НОВЫЙ ВИДЖЕТ

        # --------------------------------------------------------------
        # Состояние
        # --------------------------------------------------------------

        self.is_running = True
        self._acquisition_time = 0.0
        self._scenario_time: Optional[float] = None
        self.update_counter = 0

        # --------------------------------------------------------------
        # UI
        # --------------------------------------------------------------

        self.setup_ui()
        self.setup_connections()

        # --------------------------------------------------------------
        # Таймер
        # --------------------------------------------------------------

        self.timer = QTimer(self)

        self.timer.timeout.connect(self.update_plots)

        self.timer.start(self.UPDATE_INTERVAL_MS)

        # --------------------------------------------------------------
        # Первый график
        # --------------------------------------------------------------

        self.add_plot()

        self._update_channels_list()

    # ==================================================================
    # Окно
    # ==================================================================

    def _setup_window_geometry(self) -> None:
        """Установить размер окна."""

        screen = QApplication.primaryScreen()

        if screen is not None:
            geometry = screen.availableGeometry()

            width = geometry.width() - 40
            height = geometry.height() - 60

        else:
            width = 1800
            height = 1000

        self.setGeometry(
            20,
            30,
            width,
            height,
        )

        self._window_width = width
        self._window_height = height

    # ==================================================================
    # UI
    # ==================================================================

    def setup_ui(self) -> None:
        """Создать интерфейс."""

        central_widget = QWidget()

        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        main_layout.setContentsMargins(6, 6, 6, 5)
        main_layout.setSpacing(5)

        header = QWidget()
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header.setFixedHeight(36)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Графики сигналов")
        title.setObjectName("pageTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Прогресс-бар выполнения сценария
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setFixedHeight(22)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFormat("Сценарий: %p%")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #4CAF50;
                border-radius: 4px;
                background-color: #1e1e1e;
                color: #ffffff;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        header_layout.addWidget(self.progress_bar)

        self.fps_label = QLabel("Обновлений: 0")
        self.fps_label.setObjectName("statusPill")
        header_layout.addWidget(self.fps_label)
        main_layout.addWidget(header)

        # Верхняя панель
        main_layout.addWidget(self._create_control_panel())

        # Основная область
        splitter = QSplitter(Qt.Horizontal)

        splitter.setHandleWidth(5)

        left_panel = self._create_channels_panel()

        right_panel = self._create_plots_panel()

        splitter.addWidget(left_panel)

        splitter.addWidget(right_panel)

        left_width = 250
        right_width = self._window_width - left_width - 50

        splitter.setSizes(
            [
                left_width,
                right_width,
            ]
        )

        main_layout.addWidget(splitter, 1)

        # Нижняя панель
        main_layout.addWidget(self._create_info_panel())

        self._apply_styles()

    def _apply_styles(self) -> None:
        """Применить стили."""

        self.setStyleSheet(
            app_stylesheet()
            + f"""
            QLabel#pageTitle {{
                color: {UI_COLORS["text"]};
                font-size: 15pt;
                font-weight: 600;
            }}
            QFrame#toolbar, QFrame#statusBar, QFrame#panelCard {{
                background-color: {UI_COLORS["surface"]};
                border: 1px solid {UI_COLORS["border"]};
                border-radius: 3px;
            }}
            QLabel#sectionTitle {{
                color: {UI_COLORS["text"]};
                font-weight: 600;
            }}
            QLabel#statusPill {{
                color: {UI_COLORS["primary"]};
                background-color: {UI_COLORS["primary_soft"]};
                border: 1px solid {UI_COLORS["border"]};
                border-radius: 9px;
                padding: 3px 9px;
            }}
            QPushButton#primaryButton {{
                color: white;
                background-color: {UI_COLORS["primary"]};
                border-color: {UI_COLORS["primary"]};
                font-weight: 600;
            }}
            QPushButton#primaryButton:hover {{
                background-color: {UI_COLORS["primary_hover"]};
            }}
            QPushButton#dangerButton {{ color: {UI_COLORS["danger"]}; }}
            QListWidget {{
                background-color: {UI_COLORS["surface_alt"]};
                border: 1px solid {UI_COLORS["border"]};
                border-radius: 2px;
                outline: none;
            }}
            QListWidget::item {{ padding: 6px 5px; }}
            QListWidget::item:selected {{
                color: white;
                background-color: {UI_COLORS["primary"]};
            }}
            QListWidget::item:hover:!selected {{
                background-color: {UI_COLORS["primary_soft"]};
            }}
            """
        )

    # ==================================================================
    # Панель управления
    # ==================================================================

    def _create_control_panel(self):
        """Создать панель управления."""

        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar.setMaximumHeight(46)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # Добавить график
        self.add_plot_btn = QPushButton("＋ Добавить график")
        self.add_plot_btn.setObjectName("primaryButton")

        self.add_plot_btn.clicked.connect(self.add_plot)

        layout.addWidget(self.add_plot_btn)

        # Удалить последний
        self.remove_last_btn = QPushButton("− Удалить последний")
        self.remove_last_btn.setObjectName("dangerButton")

        self.remove_last_btn.clicked.connect(self.remove_last_plot)

        layout.addWidget(self.remove_last_btn)

        # Очистить всё
        self.clear_all_btn = QPushButton("Очистить данные")

        self.clear_all_btn.clicked.connect(self.clear_all_plots)

        layout.addWidget(self.clear_all_btn)

        # Автомасштаб
        self.auto_btn = QPushButton("Автомасштаб")

        self.auto_btn.clicked.connect(self.auto_range_all)

        layout.addWidget(self.auto_btn)

        layout.addStretch()

        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        layout.addWidget(QLabel("Высота"))

        self.height_spin = QSpinBox()

        self.height_spin.setRange(
            130,
            400,
        )

        self.height_spin.setValue(self.plot_height)

        self.height_spin.setSingleStep(10)

        self.height_spin.setSuffix(" px")

        self.height_spin.setMaximumWidth(80)

        self.height_spin.valueChanged.connect(self.on_height_changed)

        layout.addWidget(self.height_spin)

        # Временное окно
        layout.addWidget(QLabel("Окно"))

        self.time_window_spin = QDoubleSpinBox()

        self.time_window_spin.setRange(
            1,
            60,
        )

        self.time_window_spin.setValue(self.time_window)

        self.time_window_spin.setSingleStep(1)

        self.time_window_spin.setMaximumWidth(60)

        self.time_window_spin.valueChanged.connect(self.on_time_window_changed)

        self.time_window_spin.setSuffix(" с")
        layout.addWidget(self.time_window_spin)

        return toolbar

    # ==================================================================
    # Панель каналов
    # ==================================================================

    def _create_channels_panel(self):
        """Создать список каналов."""

        widget = QFrame()
        widget.setObjectName("panelCard")

        layout = QVBoxLayout(widget)

        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        title = QLabel("Каналы")
        title.setObjectName("sectionTitle")

        layout.addWidget(title)

        self.channels_list = QListWidget()

        self.channels_list.setSelectionMode(QListWidget.ExtendedSelection)

        self.channels_list.setContextMenuPolicy(Qt.CustomContextMenu)

        self.channels_list.customContextMenuRequested.connect(self.show_channel_menu)

        self.channels_list.setMinimumWidth(220)
        self.channels_list.setMaximumWidth(280)

        layout.addWidget(self.channels_list)

        info_layout = QHBoxLayout()

        info_layout.setSpacing(2)

        self.selection_info = QLabel("Выбрано: 0")

        self.selection_info.setObjectName("secondaryText")

        info_layout.addWidget(self.selection_info)

        info_layout.addStretch()

        self.add_selected_btn = QPushButton("Добавить на график")
        self.add_selected_btn.setObjectName("primaryButton")

        self.add_selected_btn.setToolTip("Добавить выбранные каналы на график")

        self.add_selected_btn.clicked.connect(self.add_selected_channels)

        info_layout.addWidget(self.add_selected_btn)

        layout.addLayout(info_layout)

        return widget

    # ==================================================================
    # Панель графиков
    # ==================================================================

    def _create_plots_panel(self):
        """Создать область графиков."""

        widget = QFrame()
        widget.setObjectName("panelCard")

        layout = QVBoxLayout(widget)

        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        title_layout = QHBoxLayout()
        title = QLabel("Область графиков")
        title.setObjectName("sectionTitle")
        title_layout.addWidget(title)
        title_layout.addStretch()
        hint = QLabel("Правый щелчок по графику открывает действия")
        hint.setObjectName("secondaryText")
        title_layout.addWidget(hint)

        layout.addLayout(title_layout)

        self.plots_container = QWidget()

        self.plots_layout = QVBoxLayout(self.plots_container)

        self.plots_layout.setSpacing(4)

        self.plots_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.plots_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.plots_container)
        layout.addWidget(scroll)

        return widget

    # ==================================================================
    # Нижняя панель
    # ==================================================================

    def _create_info_panel(self):
        """Создать информационную панель."""

        panel = QFrame()
        panel.setObjectName("statusBar")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        panel.setMaximumHeight(34)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(5)

        info_label = QLabel(
            "Ctrl + щелчок — выбор нескольких каналов · "
            "правый щелчок — дополнительные действия"
        )
        info_label.setObjectName("secondaryText")

        layout.addWidget(info_label)

        layout.addStretch()

        self.plots_count_label = QLabel("Графиков: 0")

        self.plots_count_label.setObjectName("secondaryText")

        layout.addWidget(self.plots_count_label)

        return panel

    # ==================================================================
    # Каналы
    # ==================================================================

    def _update_channels_list(self) -> None:
        """Обновить список каналов."""

        if self.channels_list is None:
            return

        self.channels_list.clear()

        for channel in self.generator.channels:
            channel_kind = "D" if channel.signal_type.is_discrete() else "A"
            plot_indices = []

            for index, plot in enumerate(self.plot_widgets):
                if channel.id in plot.get_channel_ids():
                    plot_indices.append(str(index + 1))

            status = ""

            if plot_indices:
                status = f" [Гр.{', '.join(plot_indices)}]"

            text = (
                f"[{channel_kind}] Ch{channel.id + 1:02d}: "
                f"{channel.name[:12]} "
                f"({str(channel.signal_type)})"
                f"{status}"
            )

            item = QListWidgetItem(text)

            item.setData(
                Qt.UserRole,
                channel.id,
            )

            if plot_indices:
                item.setBackground(QColor(UI_COLORS["primary_soft"]))

            self.channels_list.addItem(item)

        self.update_selection_info()

    def show_channel_menu(self, position) -> None:
        """Контекстное меню канала."""

        item = self.channels_list.itemAt(position)

        if item is None:
            return

        channel_id = item.data(Qt.UserRole)

        if channel_id is None:
            return

        channel = self.generator.get_channel(channel_id)

        if channel is None:
            return

        menu = QMenu(self)

        add_action = QAction(
            "Добавить на график",
            self,
        )

        add_action.triggered.connect(lambda: self.add_channel_to_plot(channel_id))

        menu.addAction(add_action)

        plot_indices = [
            index
            for index, plot in enumerate(self.plot_widgets)
            if channel_id in plot.get_channel_ids()
        ]

        if plot_indices:
            remove_menu = QMenu(
                "Удалить с графиков",
                self,
            )

            for plot_index in plot_indices:
                action = QAction(
                    f"С графика {plot_index + 1}",
                    self,
                )

                action.triggered.connect(
                    lambda checked=False, pi=plot_index, cid=channel_id: (
                        self.remove_channel_from_plot(
                            cid,
                            pi,
                        )
                    )
                )

                remove_menu.addAction(action)

            menu.addMenu(remove_menu)

        menu.addSeparator()

        info_action = QAction(
            (
                f"{channel.name[:15]} | "
                f"{channel.min_value:.0f}-"
                f"{channel.max_value:.0f} | "
                f"{channel.frequency:.1f} Гц"
            ),
            self,
        )

        info_action.setEnabled(False)

        menu.addAction(info_action)

        menu.exec_(self.channels_list.mapToGlobal(position))

    # ==================================================================
    # Добавление / удаление каналов
    # ==================================================================

    def add_channel_to_plot(
        self,
        channel_id: int,
        plot_index: Optional[int] = None,
    ) -> None:
        """Добавить канал на график."""

        if not self.plot_widgets:
            self.add_plot()

        if plot_index is None:
            plot_index = min(
                range(len(self.plot_widgets)),
                key=lambda i: self.plot_widgets[i].get_channel_count(),
            )

        if not (0 <= plot_index < len(self.plot_widgets)):
            return

        plot = self.plot_widgets[plot_index]

        if channel_id in plot.get_channel_ids():
            return

        plot.set_channel(channel_id)

        self._update_channels_list()

    def remove_channel_from_plot(
        self,
        channel_id: int,
        plot_index: int,
    ) -> None:
        """Удалить канал с графика."""

        if not (0 <= plot_index < len(self.plot_widgets)):
            return

        plot = self.plot_widgets[plot_index]

        plot.remove_channel(channel_id)

        self._update_channels_list()

    def add_selected_channels(self) -> None:
        """Добавить выбранные каналы."""

        selected_items = self.channels_list.selectedItems()

        if not selected_items:
            QMessageBox.information(
                self,
                "Информация",
                "Выберите каналы для добавления",
            )

            return

        channel_ids = []

        for item in selected_items:
            channel_id = item.data(Qt.UserRole)

            if channel_id is not None:
                channel_ids.append(channel_id)

        if not channel_ids:
            return

        plot_names = [str(index + 1) for index in range(len(self.plot_widgets))]

        plot_names.append("Новый график")

        selected_plot, ok = QInputDialog.getItem(
            self,
            "Выбор графика",
            "Выберите график:",
            plot_names,
            0,
            False,
        )

        if not ok:
            return

        if selected_plot == "Новый график":
            plot = self.add_plot()

        else:
            plot_index = int(selected_plot) - 1

            plot = self.plot_widgets[plot_index]

        added_count = 0

        for channel_id in channel_ids:
            if channel_id not in plot.get_channel_ids():
                plot.set_channel(channel_id)

                added_count += 1

        self._update_channels_list()

        if added_count:
            self.selection_info.setText(f"✅ +{added_count}")

            QTimer.singleShot(
                1500,
                self.update_selection_info,
            )

    def update_selection_info(self) -> None:
        """Обновить количество выбранных каналов."""

        if self.channels_list is None:
            return

        count = len(self.channels_list.selectedItems())

        if self.selection_info:
            self.selection_info.setText(f"Выбрано: {count}")

    # ==================================================================
    # Графики
    # ==================================================================

    def add_plot(self) -> PlotWidget:
        """Добавить новый график."""

        plot_index = len(self.plot_widgets)

        plot = PlotWidget(
            plot_index=plot_index,
            generator=self.generator,
            max_points=self.max_points,
            time_window=self.time_window,
        )

        plot.setMinimumHeight(self.plot_height)

        plot.setMaximumHeight(self.plot_height + 20)

        plot.remove_requested.connect(self.remove_plot)

        plot.clear_requested.connect(self.clear_plot)

        plot.add_channel_requested.connect(self.on_add_channel_requested)

        self.plot_widgets.append(plot)

        self.plots_layout.insertWidget(self.plots_layout.count() - 1, plot)

        self._update_plot_numbers()

        self._update_channels_list()

        return plot

    def remove_last_plot(self) -> None:
        """Удалить последний график."""

        if len(self.plot_widgets) <= 1:
            QMessageBox.information(
                self,
                "Информация",
                "Должен быть хотя бы один график",
            )

            return

        self.remove_plot(len(self.plot_widgets) - 1)

    def remove_plot(
        self,
        plot_index: int,
    ) -> None:
        """Удалить график."""

        if len(self.plot_widgets) <= 1:
            QMessageBox.information(
                self,
                "Информация",
                "Должен быть хотя бы один график",
            )

            return

        if not (0 <= plot_index < len(self.plot_widgets)):
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение",
            (f"Удалить график {plot_index + 1}?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        plot = self.plot_widgets.pop(plot_index)

        self.plots_layout.removeWidget(plot)

        plot.setParent(None)
        plot.deleteLater()

        self._update_plot_numbers()

        self._update_channels_list()

    def _update_plot_numbers(self) -> None:
        """Обновить индексы всех графиков."""

        for index, plot in enumerate(self.plot_widgets):
            plot.plot_index = index
            plot.update_title()

        self.plots_count_label.setText(f"Графиков: {len(self.plot_widgets)}")

    def clear_plot(
        self,
        plot_index: int,
    ) -> None:
        """Очистить один график."""

        if not (0 <= plot_index < len(self.plot_widgets)):
            return

        self.plot_widgets[plot_index].clear_plot()

        self._update_channels_list()

    def clear_all_plots(self) -> None:
        """Очистить все графики."""

        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Очистить все графики?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        for plot in self.plot_widgets:
            plot.clear_plot()

        self._update_channels_list()

    # ==================================================================
    # Контекстное меню графика
    # ==================================================================

    def on_add_channel_requested(
        self,
        plot_index: int,
    ) -> None:
        """Добавить канал через меню графика."""

        if not self.generator.channels:
            return

        channel_ids = [channel.id for channel in self.generator.channels]

        channel_names = [
            (f"Ch{channel.id + 1}: {channel.name} ({str(channel.signal_type)})")
            for channel in self.generator.channels
        ]

        channel_name, ok = QInputDialog.getItem(
            self,
            "Добавить канал",
            "Выберите канал:",
            channel_names,
            0,
            False,
        )

        if not ok:
            return

        try:
            index = channel_names.index(channel_name)
        except ValueError:
            return

        self.add_channel_to_plot(
            channel_ids[index],
            plot_index,
        )

    # ==================================================================
    # Настройки
    # ==================================================================

    def on_time_window_changed(
        self,
        value: float,
    ) -> None:
        """Изменить временное окно."""
        self.time_window = float(value)
        for plot in self.plot_widgets:
            plot.set_time_window(self.time_window)

    def on_height_changed(
        self,
        value: int,
    ) -> None:
        """Изменить высоту графиков."""

        self.plot_height = value

        for plot in self.plot_widgets:
            plot.setMinimumHeight(value)

            plot.setMaximumHeight(value + 20)

    def auto_range_all(self) -> None:
        """Автомасштабировать графики."""

        for plot in self.plot_widgets:
            plot.autoRange()

    # ==================================================================
    # Обновление
    # ==================================================================

    def set_acquisition_running(self, running: bool) -> None:
        """Синхронизировать запись графиков с кнопками управления."""
        self.is_running = running

    def begin_scenario_acquisition(self) -> None:
        """Начать запись по единой временной шкале сценария."""
        self._scenario_time = 0.0
        self._acquisition_time = 0.0
        for plot in self.plot_widgets:
            for buffer in plot.channel_data.values():
                buffer.clear()
            for curve in plot.curves.values():
                curve.setData([], [])

    def set_scenario_time(self, elapsed_seconds: float) -> None:
        """Синхронизировать временную шкалу графиков с движком сценария."""
        self._scenario_time = max(0.0, elapsed_seconds)

    def end_scenario_acquisition(self) -> None:
        """Вернуть графики к собственной шкале времени."""
        self._scenario_time = None

    def set_scenario_progress(self, progress: int) -> None:
        """Обновить индикатор выполнения сценария."""
        if progress > 0:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(progress)
            if progress >= 100:
                self.progress_bar.setFormat("Сценарий завершён")
            else:
                self.progress_bar.setFormat(f"Сценарий: {progress}%")
        else:
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)

    def update_plots(self) -> None:
        """
        Один цикл обновления.

        Сначала добавляем новые значения во все буферы,
        затем один раз перерисовываем каждый график.
        """

        if not self.is_running:
            return

        self.update_counter += 1
        if self._scenario_time is None:
            self._acquisition_time += self.UPDATE_INTERVAL_MS / 1000.0
        else:
            self._acquisition_time = self._scenario_time

        # --------------------------------------------------------------
        # 1. Записываем данные ТОЛЬКО ДЛЯ ВКЛЮЧЁННЫХ каналов
        # --------------------------------------------------------------

        for plot in self.plot_widgets:
            for channel_id in plot.get_channel_ids():
                channel = self.generator.get_channel(channel_id)
                if channel is None:
                    continue

                # Проверяем, включён ли канал
                if not channel.enabled:
                    # Канал отключён — не добавляем новые данные
                    continue

                plot.append_value(
                    channel_id,
                    channel.current_value,
                    self._acquisition_time,
                )

        # --------------------------------------------------------------
        # 2. Обновляем отображение
        # --------------------------------------------------------------

        # Все графики используют единую шкалу времени сбора данных.
        current_time = self._acquisition_time

        for plot in self.plot_widgets:
            plot.update_plot(current_time)

        # --------------------------------------------------------------
        # Информация
        # --------------------------------------------------------------

        if self.update_counter % 20 == 0 and self.fps_label is not None:
            self.fps_label.setText(f"Обновлений: {self.update_counter}")

    # ==================================================================
    # Qt events
    # ==================================================================

    def closeEvent(self, event) -> None:  # type: ignore  # noqa: N802
        """Корректно закрыть окно."""

        self.is_running = False

        if self.timer.isActive():
            self.timer.stop()

        event.accept()

    def setup_connections(self) -> None:
        """Настроить соединения сигналов."""

        if self.channels_list is not None:
            self.channels_list.itemSelectionChanged.connect(self.update_selection_info)

    def get_active_channels(self) -> List[int]:
        """Получить список ID активных (включенных) каналов."""
        return [ch.id for ch in self.generator.channels if ch.enabled]

    def clear_all_plots_data(self) -> None:
        """Очистить данные всех графиков без подтверждения (для сброса)."""
        for plot in self.plot_widgets:
            plot.clear_plot()
        self._update_channels_list()
