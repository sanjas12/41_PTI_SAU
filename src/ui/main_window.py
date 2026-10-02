import json
import os
from typing import List

from PyQt5.QtCore import Qt, QSettings, QThreadPool, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from _version import __full_version__
from config.ui_settings import UISettings
from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from modbus.worker import Runnable
from mu210.interface import MU210Interface
from plc.plc_interface import PLCInterface
from plc.plc_register_view import PLCRegisterView
from scenario.scenario_engine import ScenarioEngine
from scenario.scenario_model import Scenario
from scenario.scenario_widget import ScenarioWidget
from ui.channel_widget import ChannelWidget
from ui.connection_dialog import ConnectionDialog
from ui.control_panel import ControlPanel
from ui.event_log_panel import EventLogPanel
from ui.menu_bar import AppMenuBar
from ui.plot_widget import PlotWindow
from ui.settings_dialog import SettingsDialog
from ui.status_bar import AppStatusBar
from ui.themes import build_stylesheet
from ui.toolbar import AppToolBar


class MainWindow(QMainWindow):
    """Главное окно приложения."""

    CHANNELS_CONFIG_FILE = "channels_config.json"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(__full_version__)
        self.setGeometry(100, 100, 900, 900)

        # Настройки UI (тема + масштаб)
        self.ui_settings = UISettings.instance()

        # QSettings для сохранения геометрии разделителя между запусками
        self._settings = QSettings("AnalogSimulator", "MainWindow")

        # Путь к файлу конфигурации каналов
        self.config_path = self._get_config_path()

        # Каналы
        self.generator = SignalGenerator()
        self._setup_channels()

        # Движок сценариев
        self.scenario_engine = ScenarioEngine(self.generator, self)
        self.scenario_engine.log_signal.connect(self.log)
        self.scenario_engine.mode_changed.connect(self.on_scenario_mode_changed)
        self.scenario_engine.scenario_started.connect(self.on_scenario_started)
        self.scenario_engine.scenario_stopped.connect(self.on_scenario_stopped)
        self.scenario_engine.scenario_finished.connect(self.on_scenario_finished)
        self.scenario_engine.progress_changed.connect(self.on_scenario_progress_changed)
        self.scenario_engine.time_updated.connect(self.on_scenario_time_updated)

        # Интерфейс с МУ210-501 (основной) и PLC (резервный)
        self.output_interface = MU210Interface(self.generator, self)
        self.scenario_engine.start_validator = self._validate_scenario_output_map
        self.scenario_engine.validation_failed.connect(
            self._show_output_map_validation_error
        )
        self.plc_interface = PLCInterface(self.generator, self)
        self.active_output_interface = self.output_interface
        self.active_device_type = "owen"

        self.output_interface.connection_status.connect(
            self.on_output_connection_status
        )
        self.output_interface.error_occurred.connect(
            lambda e: self.log(f"МУ210-501: {e}", "error")
        )
        self.output_interface.debug_data.connect(self.on_output_debug_data)

        self.plc_interface.connection_status.connect(self.on_output_connection_status)
        self.plc_interface.error_occurred.connect(
            lambda e: self.log(f"PLC/Simulator: {e}", "error")
        )
        self.plc_interface.debug_data.connect(self.on_output_debug_data)

        # Состояние приложения
        self.frame_count = 0
        self.is_running = False
        self.is_paused = False
        self._engine_mode = "manual"

        # Внешние окна
        self.plot_window: PlotWindow | None = None
        self.plc_view: PLCRegisterView | None = None
        self.connection_dialog: ConnectionDialog | None = None
        self.settings_dialog: SettingsDialog | None = None

        # Собираем UI
        self.setup_ui()

        # Применяем сохранённую тему
        self._apply_theme(self.ui_settings.theme)

        # Таймер запускается только по Play
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_signals)

        # Синхронизация UI с исходным состоянием
        self._refresh_status_bar()
        self._refresh_control_buttons()

        # Пул потоков для асинхронных операций
        self.thread_pool = QThreadPool.globalInstance()

    # ==================================================================
    # Конфигурация каналов
    # ==================================================================

    def _get_config_path(self) -> str:
        home_dir = os.path.expanduser("~")
        config_dir = os.path.join(home_dir, ".analog_simulator")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        return os.path.join(config_dir, self.CHANNELS_CONFIG_FILE)

    def _setup_channels(self) -> None:
        """Создать каналы с загрузкой сохранённых настроек."""
        saved_config = self._load_channels_config()
        signal_types = [
            SignalType.SINE,
            SignalType.SQUARE,
            SignalType.SAWTOOTH,
            SignalType.TRIANGLE,
            SignalType.RANDOM,
        ]

        for i in range(20):
            stype = signal_types[i % len(signal_types)]

            if saved_config and str(i) in saved_config:
                cfg = saved_config[str(i)]
                channel = AnalogChannel(
                    id=i,
                    name=cfg.get("name", f"Ch_{i + 1:02d}"),
                    signal_type=SignalType[cfg.get("signal_type", stype.name)],
                    frequency=cfg.get("frequency", 0.5 + (i % 10) * 0.3),
                    amplitude=cfg.get("amplitude", 30 + (i % 7) * 10),
                    offset=cfg.get("offset", 10 + (i % 9) * 5),
                    min_value=cfg.get("min_value", (i % 5) * 10),
                    max_value=cfg.get("max_value", 100 - (i % 3) * 5),
                    enabled=cfg.get("enabled", True),
                    duty_cycle=cfg.get("duty_cycle", 50.0),
                    pulse_width=cfg.get("pulse_width", 1.0),
                    mu210_module=cfg.get("mu210_module", i // 8 + 1),
                    mu210_register=cfg.get("mu210_register", 3000 + i % 8),
                )
            else:
                min_val = (i % 5) * 10
                max_val = 100 - (i % 3) * 5
                channel = AnalogChannel(
                    id=i,
                    name=f"Ch_{i + 1:02d}",
                    signal_type=stype,
                    frequency=0.5 + (i % 10) * 0.3,
                    amplitude=30 + (i % 7) * 10,
                    offset=10 + (i % 9) * 5,
                    min_value=min_val,
                    max_value=max_val,
                    enabled=True,
                )

            self.generator.add_channel(channel)

        # Дополнительные дискретные каналы, сохранённые ранее
        extra_ids = sorted(
            int(channel_id)
            for channel_id in saved_config
            if channel_id.isdigit() and int(channel_id) >= 20
        )
        discrete_types = SignalType.get_discrete_types()
        for channel_id in extra_ids:
            cfg = saved_config[str(channel_id)]
            default_type = discrete_types[(channel_id - 20) % len(discrete_types)]
            channel = AnalogChannel(
                id=channel_id,
                name=cfg.get("name", f"Discrete_{channel_id - 19:02d}"),
                signal_type=SignalType[cfg.get("signal_type", default_type.name)],
                frequency=cfg.get("frequency", 1.0),
                amplitude=cfg.get("amplitude", 100.0),
                offset=cfg.get("offset", 0.0),
                min_value=cfg.get("min_value", 0.0),
                max_value=cfg.get("max_value", 1.0),
                enabled=cfg.get("enabled", True),
                duty_cycle=cfg.get("duty_cycle", 50.0),
                pulse_width=cfg.get("pulse_width", 0.1),
                mu210_module=cfg.get("mu210_module", channel_id // 8 + 1),
                mu210_register=cfg.get("mu210_register", 3000 + channel_id % 8),
            )
            self.generator.add_channel(channel)

        self._ensure_discrete_channel_count(self.generator, 10)

    @staticmethod
    def _ensure_discrete_channel_count(
        generator: SignalGenerator, target_count: int
    ) -> None:
        """Добавить недостающие логические дискретные каналы (D01…D10)."""
        discrete_count = sum(
            channel.signal_type.is_discrete() for channel in generator.channels
        )
        missing_count = max(0, target_count - discrete_count)
        if missing_count == 0:
            return

        next_id = max((channel.id for channel in generator.channels), default=-1) + 1
        discrete_types = SignalType.get_discrete_types()
        for offset in range(missing_count):
            category_number = discrete_count + offset + 1
            generator.add_channel(
                AnalogChannel(
                    id=next_id + offset,
                    name=f"Discrete_{category_number:02d}",
                    signal_type=discrete_types[
                        (category_number - 1) % len(discrete_types)
                    ],
                    frequency=1.0,
                    amplitude=100.0,
                    offset=0.0,
                    min_value=0.0,
                    max_value=1.0,
                    enabled=True,
                    duty_cycle=50.0,
                    pulse_width=0.1,
                )
            )

    def _load_channels_config(self) -> dict:
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки конфигурации каналов: {e}")
        return {}

    def _save_channels_config(self) -> bool:
        try:
            config = {}
            for channel in self.generator.channels:
                config[str(channel.id)] = {
                    "name": channel.name,
                    "signal_type": channel.signal_type.name,
                    "frequency": channel.frequency,
                    "amplitude": channel.amplitude,
                    "offset": channel.offset,
                    "min_value": channel.min_value,
                    "max_value": channel.max_value,
                    "enabled": channel.enabled,
                    "duty_cycle": channel.duty_cycle,
                    "pulse_width": channel.pulse_width,
                    "mu210_module": channel.mu210_module,
                    "mu210_register": channel.mu210_register,
                }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.log(f"Ошибка сохранения конфигурации каналов: {e}", "error")
            return False

    # ==================================================================
    # UI
    # ==================================================================

    def setup_ui(self) -> None:
        """Настройка UI главного окна."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # --- Верхнее меню ---
        self.menu_bar = AppMenuBar(self)
        self.setMenuBar(self.menu_bar)
        self._connect_menu_actions()
        self.menu_bar.sync_theme_actions(self.ui_settings.theme)
        self.menu_bar.sync_scale_actions(self.ui_settings.ui_scale)

        # --- Toolbar ---
        self.toolbar = AppToolBar(self)
        self.toolbar.play_clicked.connect(self.on_play_clicked)
        self.toolbar.stop_clicked.connect(self.on_stop_clicked)
        self.toolbar.pause_clicked.connect(self.on_pause_clicked)
        self.toolbar.reset_clicked.connect(self.reset_signals)
        self.toolbar.plots_clicked.connect(self.open_plot_window)
        self.toolbar.registers_clicked.connect(self.open_plc_view)
        self.toolbar.save_clicked.connect(self.save_channels)
        self.toolbar.settings_clicked.connect(self.open_settings_dialog)
        self.addToolBar(self.toolbar)

        # --- StatusBar ---
        self.status_bar = AppStatusBar(self)
        self.setStatusBar(self.status_bar)

        # --- Основная область ---
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        central_widget.setLayout(main_layout)

        # QSplitter: левая часть — каналы/сценарий, правая — журнал событий.
        # Его можно тянуть мышью за ручку между панелями.
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)  # нельзя схлопнуть в ноль
        self.splitter.setHandleWidth(6)              # ручку легче поймать мышью
        main_layout.addWidget(self.splitter)

        # Левая панель — управление + рабочая область
        left_container = QWidget()
        left_container.setMinimumWidth(400)
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_container.setLayout(left_layout)

        # --- ControlPanel (сам является GroupBox — без обёртки) ---
        # self.control_panel = ControlPanel()
        # self.control_panel.play_clicked.connect(self.on_play_clicked)
        # self.control_panel.stop_clicked.connect(self.on_stop_clicked)
        # self.control_panel.pause_clicked.connect(self.on_pause_clicked)
        # self.control_panel.reset_clicked.connect(self.reset_signals)
        # self.control_panel.plot_clicked.connect(self.open_plot_window)
        # self.control_panel.plc_clicked.connect(self.open_plc_view)
        # self.control_panel.save_channels_clicked.connect(self.save_channels)
        # self.control_panel.toggle_all_clicked.connect(
        #     self.on_toggle_all_channels_clicked
        # )
        # left_layout.addWidget(self.control_panel)

        # --- Сегментированный тумблер: Ручной ⇄ Сценарий ---
        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)

        self.manual_mode_btn = QPushButton("Ручной режим")
        self.scenario_mode_btn = QPushButton("Сценарий")
        for btn in (self.manual_mode_btn, self.scenario_mode_btn):
            btn.setObjectName("modeButton")
            btn.setCheckable(True)
            btn.setMinimumHeight(30)

        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)
        self.mode_button_group.addButton(self.manual_mode_btn)
        self.mode_button_group.addButton(self.scenario_mode_btn)
        self.manual_mode_btn.setChecked(True)

        self.manual_mode_btn.clicked.connect(
            lambda: self.request_channel_mode("manual")
        )
        self.scenario_mode_btn.clicked.connect(
            lambda: self.request_channel_mode("scenario")
        )

        mode_row.addWidget(self.manual_mode_btn)
        mode_row.addWidget(self.scenario_mode_btn)
        mode_row.addStretch()
        left_layout.addLayout(mode_row)

        # --- Переключаемая часть: сетка каналов ⇄ конструктор сценария ---
        scenario_group = QGroupBox("Сценарий")
        scenario_layout = QVBoxLayout()
        scenario_layout.setContentsMargins(5, 5, 5, 5)
        scenario_layout.setSpacing(3)
        scenario_group.setLayout(scenario_layout)

        self.scenario_widget = ScenarioWidget(
            self.generator, self.scenario_engine, self
        )
        self.scenario_widget.scenario_changed.connect(
            self.on_scenario_definition_changed
        )
        self.on_scenario_definition_changed(self.scenario_widget.scenario)
        scenario_layout.addWidget(self.scenario_widget)

        # --- Сетка каналов: аналоговые + дискретные ---
        self.channel_grid_scroll = QScrollArea()
        self.channel_grid_scroll.setWidgetResizable(True)

        self.channel_grid_widget = QWidget()
        sections_layout = QVBoxLayout()
        sections_layout.setContentsMargins(4, 4, 4, 4)
        sections_layout.setSpacing(8)
        self.channel_grid_widget.setLayout(sections_layout)

        # Аналоговые
        self.analog_channels_group = QGroupBox("▼ Аналоговые каналы · A")
        self.analog_channels_group.setCheckable(True)
        self.analog_channels_group.setChecked(True)
        self.analog_channels_group.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Maximum
        )
        self.analog_channels_layout = QGridLayout()
        self.analog_channels_layout.setSpacing(6)
        self.analog_channels_group.setLayout(self.analog_channels_layout)
        self.analog_channels_group.toggled.connect(
            lambda expanded: self._set_channel_section_expanded(
                self.analog_channels_group,
                self.analog_channels_layout,
                "Аналоговые каналы · A",
                expanded,
            )
        )
        sections_layout.addWidget(self.analog_channels_group)

        # Дискретные
        self.discrete_channels_group = QGroupBox("▼ Дискретные каналы · D")
        self.discrete_channels_group.setCheckable(True)
        self.discrete_channels_group.setChecked(True)
        self.discrete_channels_group.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Maximum
        )
        self.discrete_channels_layout = QGridLayout()
        self.discrete_channels_layout.setSpacing(6)
        self.discrete_channels_group.setLayout(self.discrete_channels_layout)
        self.discrete_channels_group.toggled.connect(
            lambda expanded: self._set_channel_section_expanded(
                self.discrete_channels_group,
                self.discrete_channels_layout,
                "Дискретные каналы · D",
                expanded,
            )
        )
        sections_layout.addWidget(self.discrete_channels_group)
        sections_layout.addStretch()

        # Карточки каналов
        self.channel_widgets: List[ChannelWidget] = []
        for channel in self.generator.channels:
            widget = ChannelWidget(channel)
            widget.channel_selected.connect(self.on_channel_selected)
            widget.channel_type_changed.connect(self.on_channel_type_changed)
            widget.channel_settings_changed.connect(self.on_channel_settings_changed)
            self.channel_widgets.append(widget)
        self._rebuild_manual_channel_layout()

        self.channel_grid_scroll.setWidget(self.channel_grid_widget)

        # QStackedWidget: 0 — сетка каналов, 1 — конструктор сценария
        self.mode_stack = QStackedWidget()
        self.mode_stack.addWidget(self.channel_grid_scroll)
        self.mode_stack.addWidget(scenario_group)

        left_layout.addWidget(self.mode_stack, 1)
        self.splitter.addWidget(left_container)

        # Правая панель — журнал событий
        self.event_log_panel = EventLogPanel(self)
        self.event_log_panel.setMinimumWidth(180)
        self.splitter.addWidget(self.event_log_panel)

        # Пропорции: левая часть в 3 раза «жаднее» до свободного места
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)

        # Восстановить позицию разделителя из QSettings (если есть)
        saved_sizes = self._settings.value("splitter_sizes")
        restored = False
        if saved_sizes:
            try:
                sizes = [int(x) for x in saved_sizes]
                if len(sizes) == 2 and all(s > 0 for s in sizes):
                    self.splitter.setSizes(sizes)
                    restored = True
            except (TypeError, ValueError):
                pass
        if not restored:
            self.splitter.setSizes([700, 200])

    # ==================================================================
    # Меню → действия
    # ==================================================================

    def _connect_menu_actions(self) -> None:
        mb = self.menu_bar

        # Файл
        mb.open_scenario_action.triggered.connect(self._open_scenario_from_menu)
        mb.save_scenario_action.triggered.connect(self._save_scenario_from_menu)
        mb.save_channels_action.triggered.connect(self.save_channels)
        mb.exit_action.triggered.connect(self.close)

        # Подключение
        mb.connect_action.triggered.connect(self.open_connection_dialog)
        mb.disconnect_action.triggered.connect(self.disconnect_device)
        mb.device_owen_action.triggered.connect(
            lambda: self._select_device_from_menu("owen")
        )
        mb.device_plc_action.triggered.connect(
            lambda: self._select_device_from_menu("plc")
        )
        mb.device_sim_action.triggered.connect(
            lambda: self._select_device_from_menu("simulator")
        )

        # Настройки
        mb.settings_action.triggered.connect(self.open_settings_dialog)
        mb.theme_light_action.triggered.connect(lambda: self._apply_theme("light"))
        mb.theme_dark_action.triggered.connect(lambda: self._apply_theme("dark"))
        mb.scale_medium_action.triggered.connect(
            lambda: self._apply_ui_scale("medium")
        )
        mb.scale_large_action.triggered.connect(
            lambda: self._apply_ui_scale("large")
        )
        mb.plots_action.triggered.connect(self.open_plot_window)
        mb.registers_action.triggered.connect(self.open_plc_view)

        # Справка
        mb.about_action.triggered.connect(self._show_about_dialog)

    def _open_scenario_from_menu(self) -> None:
        self._show_channel_mode_view("scenario")
        self.scenario_widget.load_scenario()

    def _save_scenario_from_menu(self) -> None:
        self._show_channel_mode_view("scenario")
        self.scenario_widget.save_scenario()

    def _show_about_dialog(self) -> None:
        QMessageBox.information(
            self,
            "О программе",
            f"<b>Analog Signal Simulator</b><br>"
            f"Версия: {__full_version__}<br><br>"
            f"Симулятор аналоговых и дискретных сигналов с поддержкой "
            f"МУ210-501, PLC Modicon Premium и сценарного управления.",
        )

    # ==================================================================
    # Тема и масштаб UI
    # ==================================================================

    def _apply_theme(self, theme_name: str) -> None:
        """Применить тему ко всему приложению."""
        self.ui_settings.theme = theme_name
        large = self.ui_settings.is_large()
        qss = build_stylesheet(theme_name, large=large)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)

        if hasattr(self, "toolbar"):
            self.toolbar.apply_theme(theme_name)
        if hasattr(self, "menu_bar"):
            self.menu_bar.sync_theme_actions(theme_name)

        if self.plot_window is not None and self.plot_window.isVisible():
            self.plot_window.apply_theme(theme_name)

        self.log(f"Тема переключена: {theme_name}", "info")

    def _apply_ui_scale(self, scale: str) -> None:
        """Применить масштаб интерфейса."""
        self.ui_settings.ui_scale = scale
        self._apply_theme(self.ui_settings.theme)
        if hasattr(self, "menu_bar"):
            self.menu_bar.sync_scale_actions(scale)
        self.log(f"Размер интерфейса: {scale}", "info")

    # ==================================================================
    # Диалоги
    # ==================================================================

    def open_connection_dialog(self) -> None:
        """Открыть модальное окно подключения."""
        if self.connection_dialog is None:
            self.connection_dialog = ConnectionDialog(self)
            self.connection_dialog.connected.connect(
                self.on_connection_status_changed
            )
            self.connection_dialog.connection_changed.connect(
                self.on_connection_changed
            )
            self.connection_dialog.set_connection_status(
                self.active_output_interface.is_connected()
            )
        self.connection_dialog.exec_()

    def open_settings_dialog(self) -> None:
        """Открыть единый диалог настроек."""
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
            self.settings_dialog.theme_changed.connect(self._apply_theme)
            self.settings_dialog.ui_scale_changed.connect(self._apply_ui_scale)
            self.settings_dialog.signal_interval_changed.connect(
                self.on_signal_interval_changed
            )
            self.settings_dialog.plc_interval_changed.connect(
                self.on_plc_interval_changed
            )
        self.settings_dialog.exec_()

    def _select_device_from_menu(self, device_type: str) -> None:
        """Переключить активное устройство из меню."""
        if device_type == self.active_device_type:
            return
        if self.connection_dialog is not None:
            self.connection_dialog.connection_panel.select_device_type(device_type)
        self.on_connection_changed(
            {
                "host": "",
                "port": 0,
                "unit_id": 1,
                "device_type": device_type,
            }
        )

    # ==================================================================
    # Строка состояния
    # ==================================================================

    def _refresh_status_bar(self) -> None:
        """Обновить индикаторы строки состояния."""
        if not hasattr(self, "status_bar"):
            return

        # Режим
        self.status_bar.set_mode(getattr(self, "_engine_mode", "manual"))

        # Работа / пауза
        scenario_running = self.scenario_engine.is_running()
        self.status_bar.set_running(
            self.is_running or scenario_running, paused=self.is_paused
        )

        # Устройство
        device_names = {
            "plc": "PLC Modicon Premium",
            "simulator": "Simulator",
            "owen": "ОВЕН МУ210-501",
        }
        self.status_bar.set_device(device_names.get(self.active_device_type, "—"))

        # Подключение
        params = (
            self.connection_dialog.connection_panel.get_connection_params()
            if self.connection_dialog is not None
            else {"host": "", "port": 0}
        )
        self.status_bar.set_connection(
            self.active_output_interface.is_connected(),
            params.get("host", ""),
            params.get("port", 0),
        )

    # ==================================================================
    # Работа с секциями каналов
    # ==================================================================

    def _rebuild_manual_channel_layout(self) -> None:
        """Разнести карточки по секциям аналоговых и дискретных каналов."""
        for layout in (self.analog_channels_layout, self.discrete_channels_layout):
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(self.channel_grid_widget)

        analog_widgets = [
            w for w in self.channel_widgets if w.channel.signal_type.is_analog()
        ]
        discrete_widgets = [
            w for w in self.channel_widgets if w.channel.signal_type.is_discrete()
        ]
        columns = 6
        for widgets, layout in (
            (analog_widgets, self.analog_channels_layout),
            (discrete_widgets, self.discrete_channels_layout),
        ):
            for index, widget in enumerate(widgets):
                widget.set_category_number(index + 1)
                layout.addWidget(widget, index // columns, index % columns)

        self.analog_channels_group.setVisible(bool(analog_widgets))
        self.discrete_channels_group.setVisible(bool(discrete_widgets))
        self._set_channel_section_expanded(
            self.analog_channels_group,
            self.analog_channels_layout,
            "Аналоговые каналы · A",
            self.analog_channels_group.isChecked(),
        )
        self._set_channel_section_expanded(
            self.discrete_channels_group,
            self.discrete_channels_layout,
            "Дискретные каналы · D",
            self.discrete_channels_group.isChecked(),
        )

    @staticmethod
    def _set_channel_section_expanded(
        group: QGroupBox,
        layout: QGridLayout,
        title: str,
        expanded: bool,
    ) -> None:
        """Показать или скрыть карточки одной категории каналов."""
        group.setTitle(f"{'▼' if expanded else '▶'} {title}")
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if widget is not None:
                widget.setVisible(expanded)
        group.setMaximumHeight(16777215 if expanded else 30)

    def _manual_channel_designation(self, channel: AnalogChannel) -> str:
        """Обозначение канала внутри его категории (A01…/D01…)."""
        same_category = [
            c
            for c in self.generator.channels
            if c.signal_type.is_discrete() == channel.signal_type.is_discrete()
        ]
        category_number = same_category.index(channel) + 1
        prefix = "D" if channel.signal_type.is_discrete() else "A"
        return f"{prefix}{category_number:02d}"

    # ==================================================================
    # Обработчики каналов
    # ==================================================================

    def save_channels(self) -> None:
        """Сохранить настройки каналов."""
        if self._save_channels_config():
            self.log("Настройки каналов сохранены", "success")
            QMessageBox.information(
                self,
                "Успех",
                f"Настройки каналов сохранены в:\n{self.config_path}",
            )
        else:
            QMessageBox.warning(
                self, "Ошибка", "Не удалось сохранить настройки каналов"
            )

    def on_channel_settings_changed(self, channel_id: int) -> None:
        channel = self.generator.get_channel(channel_id)
        if channel:
            designation = self._manual_channel_designation(channel)
            self.log(
                f"{designation}: изменены настройки "
                f"(границы: {channel.min_value:.1f}-{channel.max_value:.1f}, "
                f"частота: {channel.frequency:.1f} Гц, "
                f"амплитуда: {channel.amplitude:.0f}%, "
                f"МУ210 №{channel.mu210_module}/R{channel.mu210_register})",
                "info",
            )
            self._save_channels_config()

    def on_channel_type_changed(self, channel_id: int, type_name: str) -> None:
        self._rebuild_manual_channel_layout()
        channel = self.generator.get_channel(channel_id)
        if channel:
            designation = self._manual_channel_designation(channel)
            self.log(f"{designation}: тип сигнала изменён на {type_name}", "info")
            self._save_channels_config()

    def on_channel_selected(self, channel_id: int) -> None:
        channel = self.generator.get_channel(channel_id)
        if channel:
            designation = self._manual_channel_designation(channel)
            self.log(f"Выбран {designation}: {channel.name}", "debug")

    def on_signal_interval_changed(self, interval: float) -> None:
        self.generator.set_update_interval(interval)
        freq = 1.0 / interval if interval > 0 else 0
        self.log(
            f"Интервал обновления сигналов изменён: {interval:.3f} с "
            f"({freq:.1f} Гц)",
            "info",
        )

    def on_plc_interval_changed(self, interval: float) -> None:
        if hasattr(self, "active_output_interface"):
            self.active_output_interface.set_write_interval(interval)
            freq = 1.0 / interval if interval > 0 else 0
            self.log(
                f"Интервал записи в устройство изменён: {interval:.3f} с "
                f"({freq:.1f} Гц)",
                "info",
            )

    # ==================================================================
    # Подключение / устройство
    # ==================================================================

    def disconnect_device(self) -> None:
        """Отключиться от активного устройства."""
        if self.active_output_interface.is_connected():
            self.active_output_interface.disconnect()
        self._refresh_status_bar()

    def on_connection_changed(self, params: dict) -> None:
        host = params.get("host", "")
        port = params.get("port", 0)
        unit_id = params.get("unit_id", 1)
        device_type = params.get("device_type", self.active_device_type)

        try:
            previous_interface = self.active_output_interface
            previous_device_type = self.active_device_type
            selected_interface = (
                self.output_interface if device_type == "owen" else self.plc_interface
            )
            if previous_device_type != device_type:
                previous_interface.disconnect()
                if self.plc_view is not None:
                    self.plc_view.close()
                    self.plc_view = None
            self.active_output_interface = selected_interface
            self.active_device_type = device_type
            if host and port:
                selected_interface.configure(host, port, unit_id)
                self.log(
                    f"Настроен {self._active_device_name()}: {host}:{port} "
                    f"(Unit ID: {unit_id})",
                    "info",
                )
            self._refresh_status_bar()
        except Exception as e:
            self.log(f"Ошибка настройки подключения: {e}", "error")

    def on_connection_status_changed(self, connected: bool) -> None:
        if connected:
            active_interface = self.active_output_interface

            def after_connect(ok: bool) -> None:
                if active_interface is not self.active_output_interface:
                    active_interface.disconnect()
                    return
                if ok:
                    self.log(
                        f"Подключение к {self._active_device_name()} установлено",
                        "success",
                    )
                    active_interface.start_polling()
                else:
                    self.log("Не удалось подключиться", "error")
                if self.connection_dialog is not None:
                    self.connection_dialog.set_connection_status(
                        active_interface.is_connected()
                    )
                self._refresh_status_bar()

            self._submit(active_interface.open, after_connect)
        else:
            self.active_output_interface.disconnect()
            self.log("Соединение закрыто", "info")
            self._refresh_status_bar()

    def _active_device_name(self) -> str:
        return {
            "plc": "PLC Modicon Premium",
            "simulator": "Simulator",
            "owen": "ОВЕН МУ210-501",
        }[self.active_device_type]

    def _submit(self, fn, on_result, *args, **kwargs) -> None:
        job = Runnable(fn, *args, **kwargs)
        job.signals.result.connect(on_result)
        job.signals.error.connect(lambda e: self.log(f"Ошибка: {e}", "error"))
        self.thread_pool.start(job)

    def log(self, message: str, level: str = "info") -> None:
        if hasattr(self, "event_log_panel"):
            self.event_log_panel.log(message, level)
        else:
            print(f"[{level.upper()}] {message}")

    # ==================================================================
    # Окно графиков
    # ==================================================================

    def open_plot_window(self) -> None:
        if self.plot_window is None or not self.plot_window.isVisible():
            self.plot_window = PlotWindow(self.generator, self)
            self.plot_window.show()
            self.plot_window.apply_theme(self.ui_settings.theme)
            self._auto_populate_plot_window()
            self._sync_generation_timer()
        else:
            self.plot_window.raise_()
            self.plot_window.activateWindow()

    def _auto_populate_plot_window(self) -> None:
        """Заполнить графики каналами, релевантными текущему режиму."""
        if not self.plot_window:
            return

        if self._is_scenario_view_active():
            # Режим сценария: один общий график для всех каналов сценария
            for channel_id in self._get_scenario_channel_ids():
                self.plot_window.add_channel_to_plot(channel_id)

            scenario = getattr(self.scenario_widget, "scenario", None)
            if scenario:
                total_duration = scenario.get_total_duration()
                if total_duration > 0:
                    time_window = min(total_duration * 1.1, 60.0)
                    self.plot_window.time_window_spin.setValue(time_window)
                    self.plot_window.on_time_window_changed(time_window)
                    self.log(
                        f"Время окна графиков установлено: {time_window:.1f} с "
                        f"(общая длительность сценария: {total_duration:.1f} с)",
                        "info",
                    )
        else:
            # Ручной режим: каждый канал на своём графике
            channel_ids = self._get_enabled_manual_channel_ids()
            for i, channel_id in enumerate(channel_ids):
                if i == 0 and self.plot_window.plot_widgets:
                    plot_index = 0
                else:
                    plot = self.plot_window.add_plot()
                    plot_index = plot.plot_index
                self.plot_window.add_channel_to_plot(channel_id, plot_index=plot_index)

    def _get_enabled_manual_channel_ids(self) -> List[int]:
        return [c.id for c in self.generator.channels if c.enabled]

    def _get_scenario_channel_ids(self) -> List[int]:
        scenario = getattr(self.scenario_widget, "scenario", None)
        if not scenario or not getattr(scenario, "steps", None):
            return []
        seen: List[int] = []
        for step in scenario.steps:
            if step.channel_id not in seen:
                seen.append(step.channel_id)
        return seen

    # ==================================================================
    # Окно регистров устройства
    # ==================================================================

    def open_plc_view(self) -> None:
        if self.plc_view is None or not self.plc_view.isVisible():
            self.plc_view = PLCRegisterView(
                self.active_output_interface, self._active_device_name(), self
            )
            self.plc_view.show()
        else:
            self.plc_view.raise_()
            self.plc_view.activateWindow()

    def on_output_connection_status(self, connected: bool) -> None:
        if connected:
            self.log(f"Интерфейс {self._active_device_name()} активен", "success")
        else:
            self.log(f"Интерфейс {self._active_device_name()} отключен", "warning")
        self._refresh_status_bar()

    # ==================================================================
    # Режим сценария / ручной
    # ==================================================================

    def on_scenario_mode_changed(self, mode: str) -> None:
        """Синхронизировать UI с фактическим режимом движка сценариев."""
        self._engine_mode = mode
        if mode in ("scenario", "paused"):
            self._show_channel_mode_view("scenario")
        else:
            self._refresh_control_buttons()
        self._sync_generation_timer()
        self._refresh_status_bar()

    def _sync_generation_timer(self) -> None:
        """Таймер генерации активен в ручном режиме или во время сценария."""
        engine_mode = getattr(self, "_engine_mode", "manual")
        scenario_view = self._is_scenario_view_active()
        manual_running = not scenario_view and self.is_running and not self.is_paused
        should_run = manual_running or engine_mode == "scenario"

        if should_run and not self.timer.isActive():
            self.timer.start(10)
        elif not should_run and self.timer.isActive():
            self.timer.stop()

        if self.plot_window is not None:
            self.plot_window.set_acquisition_running(should_run)

        if hasattr(self, "active_output_interface") and hasattr(
            self.active_output_interface, "set_output_enabled"
        ):
            self.active_output_interface.set_output_enabled(should_run)

    def _show_channel_mode_view(self, view: str) -> None:
        """Переключить видимую панель: сетка каналов ⇄ редактор сценария."""
        is_scenario_view = view == "scenario"

        if hasattr(self, "mode_stack") and self.mode_stack:
            self.mode_stack.setCurrentIndex(1 if is_scenario_view else 0)

        if hasattr(self, "manual_mode_btn") and hasattr(self, "scenario_mode_btn"):
            self.manual_mode_btn.blockSignals(True)
            self.scenario_mode_btn.blockSignals(True)
            self.manual_mode_btn.setChecked(not is_scenario_view)
            self.scenario_mode_btn.setChecked(is_scenario_view)
            self.manual_mode_btn.blockSignals(False)
            self.scenario_mode_btn.blockSignals(False)

        self._refresh_control_buttons()
        self._sync_generation_timer()
        self._refresh_status_bar()

    def _refresh_control_buttons(self) -> None:
        """Состояние Play/Stop/Пауза/прогресса в ControlPanel и ToolBar."""
        if not (hasattr(self, "control_panel") and self.control_panel):
            return

        if self._is_scenario_view_active():
            engine_mode = getattr(self, "_engine_mode", "manual")
            scenario_running = engine_mode in ("scenario", "paused")
            self.control_panel.set_running_state(scenario_running)
            self.control_panel.set_pause_enabled(scenario_running)
            self.control_panel.set_pause_icon(paused=(engine_mode == "paused"))
            self.control_panel.set_progress_visible(True)
            self.control_panel.set_toggle_all_enabled(False)
            if hasattr(self, "toolbar"):
                self.toolbar.set_running_state(
                    scenario_running, paused=(engine_mode == "paused")
                )
        else:
            self.control_panel.set_running_state(self.is_running)
            self.control_panel.set_pause_enabled(self.is_running)
            self.control_panel.set_pause_icon(paused=self.is_paused)
            self.control_panel.set_progress_visible(False)
            self.control_panel.set_toggle_all_enabled(True)
            if hasattr(self, "toolbar"):
                self.toolbar.set_running_state(self.is_running, paused=self.is_paused)

    def _is_scenario_view_active(self) -> bool:
        return hasattr(self, "mode_stack") and self.mode_stack.currentIndex() == 1

    def on_play_clicked(self) -> None:
        if self._is_scenario_view_active():
            self.scenario_widget.play_scenario()
        else:
            self.start_generation()

    def on_stop_clicked(self) -> None:
        if self._is_scenario_view_active():
            self.scenario_widget.stop_scenario()
        else:
            self.stop_generation()

    def on_pause_clicked(self) -> None:
        if self._is_scenario_view_active():
            self.scenario_widget.pause_scenario()
        else:
            if self.is_paused:
                self.resume_generation()
            else:
                self.pause_generation()

    # ==================================================================
    # Сигналы движка сценариев
    # ==================================================================

    def on_scenario_started(self, name: str) -> None:
        self._update_scenario_time(0.0)
        self._refresh_control_buttons()
        self._refresh_status_bar()

        if self.plot_window and self.plot_window.isVisible():
            self.plot_window.begin_scenario_acquisition()
            self.plot_window.set_scenario_progress(0)
            self.plot_window.progress_bar.setVisible(True)

    def on_scenario_stopped(self) -> None:
        self._refresh_control_buttons()
        if hasattr(self, "control_panel"):
            self.control_panel.set_progress(0)
            self._update_scenario_time(0.0)
        self._refresh_status_bar()

        if self.plot_window and self.plot_window.isVisible():
            self.plot_window.end_scenario_acquisition()
            self.plot_window.set_scenario_progress(0)
            self.plot_window.progress_bar.setVisible(False)

    def on_scenario_finished(self) -> None:
        scenario = self.scenario_engine.scenario
        if scenario:
            self.control_panel.set_progress(100)
            self._update_scenario_time(scenario.get_total_duration())
        self._refresh_control_buttons()
        self._refresh_status_bar()

        if self.plot_window and self.plot_window.isVisible():
            self.plot_window.end_scenario_acquisition()
            self.plot_window.set_scenario_progress(100)

    def on_scenario_progress_changed(self, progress: float) -> None:
        if hasattr(self, "control_panel"):
            self.control_panel.set_progress(int(progress))
        if self.plot_window and self.plot_window.isVisible():
            self.plot_window.set_scenario_progress(int(progress))

    def on_scenario_time_updated(self, elapsed: float) -> None:
        self._update_scenario_time(elapsed)
        if self.plot_window and self.plot_window.isVisible():
            self.plot_window.set_scenario_time(elapsed)

    def on_scenario_definition_changed(self, scenario: Scenario) -> None:
        if self.scenario_engine.is_running():
            return
        if not hasattr(self, "control_panel") or not self.control_panel:
            return
        self.control_panel.set_progress(0)
        self.control_panel.set_scenario_time(0.0, scenario.get_total_duration())

    def _update_scenario_time(self, elapsed: float) -> None:
        if not hasattr(self, "control_panel"):
            return
        scenario = self.scenario_engine.scenario
        total = scenario.get_total_duration() if scenario else 0.0
        self.control_panel.set_scenario_time(elapsed, total)

    def request_channel_mode(self, target_mode: str) -> None:
        """Обработчик клика по тумблеру Ручной/Сценарий."""
        if target_mode == "scenario":
            self._show_channel_mode_view("scenario")
            return

        if getattr(self, "_engine_mode", "manual") in ("scenario", "paused"):
            self.scenario_widget.set_engine_mode("manual")
        self._show_channel_mode_view("manual")

    # ==================================================================
    # Отладочные данные
    # ==================================================================

    def on_output_debug_data(self, debug_info: dict) -> None:
        if "values" in debug_info:
            details = f"AO={debug_info['values']}"
        else:
            details = f"регистров={len(debug_info.get('registers', []))}"
        self.log(
            f"Запись {self._active_device_name()} "
            f"#{debug_info['write_count']}: {details}",
            "debug",
        )

    # ==================================================================
    # Старт / стоп / пауза (ручной режим)
    # ==================================================================

    def start_generation(self) -> None:
        if self.is_running:
            return
        if self.active_device_type == "owen" and self.output_interface.is_connected():
            errors = self.output_interface.validate_manual_output_map()
            if errors:
                message = "Нельзя запустить ручной режим:\n• " + "\n• ".join(errors)
                self.log(message.replace("\n• ", "; "), "error")
                self._show_output_map_validation_error(message)
                return
        self.is_running = True
        self.is_paused = False
        self._sync_generation_timer()
        self._refresh_control_buttons()
        self._refresh_status_bar()

    def _validate_scenario_output_map(self, scenario: Scenario) -> List[str]:
        if (
            self.active_device_type != "owen"
            or not self.output_interface.is_connected()
        ):
            return []
        return self.output_interface.validate_scenario_output_map(scenario)

    def _show_output_map_validation_error(self, message: str) -> None:
        QMessageBox.warning(self, "Ошибка карты выходов", message)

    def stop_generation(self) -> None:
        if not self.is_running:
            return
        self.is_running = False
        self.is_paused = False
        self._sync_generation_timer()
        self._refresh_control_buttons()
        self._refresh_status_bar()

    def pause_generation(self) -> None:
        if not self.is_running or self.is_paused:
            return
        self.is_paused = True
        self._sync_generation_timer()
        self._refresh_control_buttons()
        self._refresh_status_bar()

    def resume_generation(self) -> None:
        if not self.is_running or not self.is_paused:
            return
        self.is_paused = False
        self._sync_generation_timer()
        self._refresh_control_buttons()
        self._refresh_status_bar()

    def reset_signals(self) -> None:
        """Сбросить сигналы и очистить графики."""
        for channel in self.generator.channels:
            channel.time = 0
            channel.current_value = 0

        if self.plot_window and self.plot_window.isVisible():
            for plot in self.plot_window.plot_widgets:
                plot.clear_plot()
            self.plot_window._update_channels_list()
            self.log("Графики очищены", "info")

        self.update_signals()
        self.log("Сигналы сброшены", "info")

    def on_toggle_all_channels_clicked(self) -> None:
        """Включить/выключить разом все каналы (только ручной режим)."""
        if self._is_scenario_view_active():
            return

        all_enabled = all(ch.enabled for ch in self.generator.channels)
        new_state = not all_enabled

        for widget in self.channel_widgets:
            try:
                widget.enabled_check.setChecked(new_state)
            except (RuntimeError, AttributeError):
                continue

    # ==================================================================
    # Цикл обновления
    # ==================================================================

    def update_signals(self) -> None:
        """Обновить сигналы и UI."""
        scenario_running = (
            hasattr(self, "scenario_engine") and self.scenario_engine.is_running()
        )

        if not self.is_running and not scenario_running:
            return

        self.generator.update(dt=0.01)

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
            except (RuntimeError, AttributeError):
                continue

        self.frame_count += 1
        if self.frame_count >= 50:
            fps = self.frame_count * 2
            try:
                if self.control_panel:
                    self.control_panel.update_fps(fps)
            except (RuntimeError, AttributeError):
                pass
            if hasattr(self, "status_bar"):
                self.status_bar.set_fps(fps)
            self.frame_count = 0

    # ==================================================================
    # Закрытие окна
    # ==================================================================

    def closeEvent(self, event) -> None:  # type: ignore # noqa: N802
        # Сохраняем позицию разделителя
        if hasattr(self, "splitter"):
            self._settings.setValue("splitter_sizes", self.splitter.sizes())

        self._save_channels_config()
        self.log("Настройки каналов сохранены", "info")

        if self.plot_window:
            self.plot_window.close()
        if self.plc_view:
            self.plc_view.close()
        if self.connection_dialog:
            self.connection_dialog.close()
        if self.settings_dialog:
            self.settings_dialog.close()

        self.output_interface.disconnect()
        self.plc_interface.disconnect()
        event.accept()
        