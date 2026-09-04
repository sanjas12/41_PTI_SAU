import json
import os

from PyQt5.QtCore import Qt, QThreadPool, QTimer
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from _version import __full_version__
from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from modbus.modbus_client import ModbusClientWrapper
from modbus.worker import Runnable
from plc.plc_interface import PLCInterface
from plc.plc_register_view import PLCRegisterView
from scenario.scenario_engine import ScenarioEngine
from scenario.scenario_model import Scenario
from scenario.scenario_widget import ScenarioWidget
from ui.channel_widget import ChannelWidget

# Импорты для сценариев - ВЫНОСИМ В КОНЕЦ ФАЙЛА
from ui.connection_panel import ConnectionPanel
from ui.control_panel import ControlPanel
from ui.event_log_panel import EventLogPanel
from ui.interval_control import IntervalControl
from ui.plot_widget import PlotWindow


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
        self.scenario_engine.mode_changed.connect(self.on_scenario_mode_changed)
        self.scenario_engine.scenario_started.connect(self.on_scenario_started)
        self.scenario_engine.scenario_stopped.connect(self.on_scenario_stopped)
        self.scenario_engine.scenario_finished.connect(self.on_scenario_finished)
        self.scenario_engine.progress_changed.connect(self.on_scenario_progress_changed)
        self.scenario_engine.time_updated.connect(self.on_scenario_time_updated)

        # Создаем интерфейс для PLC
        self.plc_interface = PLCInterface(self.generator, self, debug=True)
        self.plc_interface.connection_status.connect(self.on_plc_connection_status)
        self.plc_interface.error_occurred.connect(
            lambda e: self.log(f"PLC Error: {e}", "error")
        )
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
        self.is_paused = False
        self.plot_window = None
        self.plc_view = None

        # Генерация уже запущена (см. self.timer.start(10) выше) — приводим
        # кнопки ControlPanel в соответствие, иначе они остались бы в
        # состоянии по умолчанию из конструктора (Play доступен, Stop и
        # Пауза — нет).
        self._refresh_control_buttons()

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

    def _load_channels_config(self) -> dict:
        """Загрузить конфигурацию каналов из файла"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, encoding="utf-8") as f:
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
                }

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            self.log(f"Ошибка сохранения конфигурации каналов: {e}", "error")
            return False

    def setup_ui(self):
        """Настройка UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        central_widget.setLayout(main_layout)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        left_container = QWidget()
        left_container_layout = QVBoxLayout()
        left_container_layout.setContentsMargins(0, 0, 0, 0)
        left_container_layout.setSpacing(6)
        left_container.setLayout(left_container_layout)

        # --- Общие настройки, не зависящие от режима работы ---
        # Подключение и интервалы образуют одну верхнюю строку. Основная
        # рабочая область каналов остаётся ниже и занимает всю ширину.
        settings_row = QHBoxLayout()
        settings_row.setContentsMargins(0, 0, 0, 0)
        settings_row.setSpacing(6)

        self.connection_panel = ConnectionPanel()
        self.connection_panel.connection_changed.connect(self.on_connection_changed)
        self.connection_panel.connected.connect(self.on_connection_status_changed)
        settings_row.addWidget(self.connection_panel, 1, Qt.AlignTop)

        self.interval_control = IntervalControl()
        self.interval_control.signal_interval_changed.connect(
            self.on_signal_interval_changed
        )
        self.interval_control.plc_interval_changed.connect(self.on_plc_interval_changed)
        settings_row.addWidget(self.interval_control, 1, Qt.AlignTop)

        left_container_layout.addLayout(settings_row)

        # ============================================================
        # СЕКЦИЯ "УПРАВЛЕНИЕ КАНАЛАМИ": режим + панель режима + сетка
        # ============================================================
        # ControlPanel управляет именно каналами (Старт/Стоп генерации,
        # Сброс), поэтому идеологически живёт в одной секции с сеткой
        # каналов, а не отдельным блоком наверху. Второй режим работы тех
        # же каналов — Сценарий. Сегментированный тумблер переключает,
        # какая панель управления показана (ControlPanel/ScenarioWidget).
        # Сетка каналов — часть ручного режима: видна только когда
        # выбран "Ручной", в режиме "Сценарий" скрыта целиком.

        channels_group = QGroupBox("Управление каналами")
        channels_group_layout = QVBoxLayout()
        channels_group_layout.setContentsMargins(6, 10, 6, 6)
        channels_group.setLayout(channels_group_layout)

        # --- ControlPanel: общая для обоих режимов, не переключается ---
        self.control_panel = ControlPanel()
        self.control_panel.play_clicked.connect(self.on_play_clicked)
        self.control_panel.stop_clicked.connect(self.on_stop_clicked)
        self.control_panel.pause_clicked.connect(self.on_pause_clicked)
        self.control_panel.reset_clicked.connect(self.reset_signals)
        self.control_panel.plot_clicked.connect(self.open_plot_window)
        self.control_panel.plc_clicked.connect(self.open_plc_view)
        self.control_panel.save_channels_clicked.connect(self.save_channels)
        self.control_panel.toggle_all_clicked.connect(
            self.on_toggle_all_channels_clicked
        )
        channels_group_layout.addWidget(self.control_panel)
        channels_group_layout.addWidget(self._create_info_bar())

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
        channels_group_layout.addLayout(mode_row)

        # --- Переключаемая часть: сетка каналов (ручной) ⇄ конструктор сценария ---
        # QStackedWidget, а не QSplitter: сетка и конструктор сценария больше
        # никогда не видны одновременно, делить между ними место не нужно —
        # видимая страница получает всё доступное пространство целиком.
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

        # --- Сетка каналов ---
        self.channel_grid_scroll = QScrollArea()
        self.channel_grid_scroll.setWidgetResizable(True)

        self.channel_grid_widget = QWidget()
        channel_sections_layout = QVBoxLayout()
        channel_sections_layout.setContentsMargins(4, 4, 4, 4)
        channel_sections_layout.setSpacing(8)
        self.channel_grid_widget.setLayout(channel_sections_layout)

        self.analog_channels_group = QGroupBox("Аналоговые каналы · A")
        self.analog_channels_layout = QGridLayout()
        self.analog_channels_layout.setSpacing(6)
        self.analog_channels_group.setLayout(self.analog_channels_layout)
        channel_sections_layout.addWidget(self.analog_channels_group)

        self.discrete_channels_group = QGroupBox("Дискретные каналы · D")
        self.discrete_channels_layout = QGridLayout()
        self.discrete_channels_layout.setSpacing(6)
        self.discrete_channels_group.setLayout(self.discrete_channels_layout)
        channel_sections_layout.addWidget(self.discrete_channels_group)
        channel_sections_layout.addStretch()

        self.channel_widgets = []
        for channel in self.generator.channels:
            widget = ChannelWidget(channel)
            widget.channel_selected.connect(self.on_channel_selected)
            widget.channel_type_changed.connect(self.on_channel_type_changed)
            widget.channel_settings_changed.connect(self.on_channel_settings_changed)
            self.channel_widgets.append(widget)
        self._rebuild_manual_channel_layout()

        self.channel_grid_scroll.setWidget(self.channel_grid_widget)

        self.mode_stack = QStackedWidget()
        self.mode_stack.addWidget(self.channel_grid_scroll)  # index 0 — "manual"
        self.mode_stack.addWidget(scenario_group)  # index 1 — "scenario"

        channels_group_layout.addWidget(self.mode_stack, 1)
        left_container_layout.addWidget(channels_group, 1)

        splitter.addWidget(left_container)

        self.event_log_panel = EventLogPanel(self)
        splitter.addWidget(self.event_log_panel)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([1050, 350])

    def _create_info_bar(self):
        """Создать компактную строку состояния внутри управления каналами."""
        panel = QFrame()
        panel.setObjectName("infoBar")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self.status_label = QLabel("● Работает")
        self.status_label.setStyleSheet(
            "color: #00CC00; font-weight: bold; font-size: 12px;"
        )
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("Режим:"))
        self.mode_label = QLabel("Ручной")
        self.mode_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(self.mode_label)

        layout.addWidget(QLabel("Канал:"))
        self.selected_channel_label = QLabel("Канал 1")
        self.selected_channel_label.setStyleSheet("color: #0066CC; font-weight: bold;")
        layout.addWidget(self.selected_channel_label)

        layout.addWidget(QLabel("Тип:"))
        self.selected_type_label = QLabel("Sine")
        self.selected_type_label.setObjectName("secondaryText")
        layout.addWidget(self.selected_type_label)

        layout.addWidget(QLabel("Диапазон:"))
        self.selected_bounds_label = QLabel("0 - 100")
        self.selected_bounds_label.setObjectName("secondaryText")
        layout.addWidget(self.selected_bounds_label)

        self.stats_label = QLabel("Каналов: 20 · Активных: 20")
        self.stats_label.setObjectName("secondaryText")
        layout.addWidget(self.stats_label)
        layout.addStretch()

        version_label = QLabel(__full_version__)
        version_label.setObjectName("secondaryText")
        layout.addWidget(version_label)
        return panel

    def save_channels(self):
        """Сохранить настройки каналов"""
        if self._save_channels_config():
            self.log("Настройки каналов сохранены", "success")
            QMessageBox.information(
                self, "Успех", f"Настройки каналов сохранены в:\n{self.config_path}"
            )
        else:
            QMessageBox.warning(
                self, "Ошибка", "Не удалось сохранить настройки каналов"
            )

    def on_channel_settings_changed(self, channel_id: int):
        channel = self.generator.get_channel(channel_id)
        if channel:
            self.log(
                f"Канал {channel_id + 1}: изменены настройки "
                f"(границы: {channel.min_value:.1f}-{channel.max_value:.1f}, "
                f"частота: {channel.frequency:.1f} Гц, "
                f"амплитуда: {channel.amplitude:.0f}%)",
                "info",
            )
            self._save_channels_config()

            if self.selected_channel_label.text().startswith(f"Канал {channel_id + 1}"):
                self.selected_bounds_label.setText(
                    f"{channel.min_value:.0f} - {channel.max_value:.0f}"
                )

    def _rebuild_manual_channel_layout(self) -> None:
        """Разнести карточки по секциям аналоговых и дискретных каналов."""
        for layout in (self.analog_channels_layout, self.discrete_channels_layout):
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(self.channel_grid_widget)

        analog_widgets = [
            widget
            for widget in self.channel_widgets
            if widget.channel.signal_type.is_analog()
        ]
        discrete_widgets = [
            widget
            for widget in self.channel_widgets
            if widget.channel.signal_type.is_discrete()
        ]
        columns = 4
        for widgets, layout in (
            (analog_widgets, self.analog_channels_layout),
            (discrete_widgets, self.discrete_channels_layout),
        ):
            for index, widget in enumerate(widgets):
                layout.addWidget(widget, index // columns, index % columns)

        self.analog_channels_group.setVisible(bool(analog_widgets))
        self.discrete_channels_group.setVisible(bool(discrete_widgets))

    def on_channel_type_changed(self, channel_id: int, type_name: str):
        self._rebuild_manual_channel_layout()
        channel = self.generator.get_channel(channel_id)
        if channel:
            self.log(
                f"Канал {channel_id + 1}: тип сигнала изменен на {type_name}", "info"
            )
            self._save_channels_config()

            if self.selected_channel_label.text().startswith(f"Канал {channel_id + 1}"):
                self.selected_type_label.setText(type_name)

    def on_signal_interval_changed(self, interval: float):
        self.generator.set_update_interval(interval)
        freq = 1.0 / interval if interval > 0 else 0
        self.log(
            f"Интервал обновления сигналов изменен: {interval:.3f} с ({freq:.1f} Гц)",
            "info",
        )

        self.status_label.setText(f"⏱ Сигналы: {interval:.3f} с")
        self.status_label.setStyleSheet(
            "color: #FF9800; font-weight: bold; font-size: 12px;"
        )

        from PyQt5.QtCore import QTimer

        QTimer.singleShot(2000, lambda: self.status_label.setText("● Работает"))
        QTimer.singleShot(
            2000,
            lambda: self.status_label.setStyleSheet(
                "color: #00CC00; font-weight: bold; font-size: 12px;"
            ),
        )

    def on_plc_interval_changed(self, interval: float):
        if hasattr(self, "plc_interface"):
            self.plc_interface.set_write_interval(interval)
            freq = 1.0 / interval if interval > 0 else 0
            self.log(
                f"Интервал записи в PLC изменен: {interval:.3f} с ({freq:.1f} Гц)",
                "info",
            )

    def on_connection_changed(self, params):
        host = params["host"]
        port = params["port"]
        unit_id = params["unit_id"]

        try:
            self.modbus.configure(host, port, unit_id)
            self.log(
                f"Настроено подключение к {host}:{port} (Unit ID: {unit_id})", "info"
            )
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
        if hasattr(self, "event_log_panel"):
            self.event_log_panel.log(message, level)
        else:
            print(f"[{level.upper()}] {message}")

    def on_channel_selected(self, channel_id):
        channel = self.generator.get_channel(channel_id)
        if channel:
            self.selected_channel_label.setText(
                f"Канал {channel_id + 1}: {channel.name}"
            )
            self.selected_type_label.setText(str(channel.signal_type))
            self.selected_bounds_label.setText(
                f"{channel.min_value:.0f} - {channel.max_value:.0f}"
            )
            self.status_label.setText(f"📊 Канал {channel_id + 1}: {channel.name}")
            self.status_label.setStyleSheet(
                "color: #0066CC; font-weight: bold; font-size: 12px;"
            )

    def open_plot_window(self):
        if self.plot_window is None or not self.plot_window.isVisible():
            self.plot_window = PlotWindow(self.generator, self)
            self.plot_window.show()
            self._auto_populate_plot_window()
            self._sync_generation_timer()
        else:
            self.plot_window.raise_()
            self.plot_window.activateWindow()

    def _auto_populate_plot_window(self):
        """При открытии окна графиков сразу выводим на него каналы,
        релевантные текущему режиму:
        - "Ручной" — все настроенные аналоговые и дискретные каналы,
        КАЖДЫЙ на своём отдельном графике. Выключенный канал остаётся
        доступен на графике, но новые значения для него не записываются;
        - "Сценарий" — все каналы, задействованные хоть в одном шаге
        текущего загруженного сценария, все на одном общем графике.
        При этом время окна автоматически выставляется равным общей
        длительности сценария.
        """
        if not self.plot_window:
            return

        if self._is_scenario_view_active():
            # --- РЕЖИМ СЦЕНАРИЯ ---
            channel_ids = self._get_scenario_channel_ids()
            for channel_id in channel_ids:
                self.plot_window.add_channel_to_plot(channel_id)

            # Устанавливаем время окна = общая длительность сценария
            scenario = getattr(self.scenario_widget, "scenario", None)
            if scenario:
                total_duration = scenario.get_total_duration()
                if total_duration > 0:
                    # Добавляем запас 10% для наглядности
                    time_window = total_duration * 1.1
                    # Ограничиваем максимум 60 секунд
                    time_window = min(time_window, 60.0)
                    # Обновляем спинбокс и применяем к графикам
                    self.plot_window.time_window_spin.setValue(time_window)
                    self.plot_window.on_time_window_changed(time_window)

                    # Обновляем подпись в информационной панели
                    self.status_label.setText(
                        f"⏱ Окно: {time_window:.1f} с (по сценарию)"
                    )
                    self.status_label.setStyleSheet(
                        "color: #4CAF50; font-weight: bold; font-size: 12px;"
                    )
                    self.log(
                        f"Время окна графиков установлено: {time_window:.1f} с "
                        f"(общая длительность сценария: {total_duration:.1f} с)",
                        "info",
                    )
        else:
            # --- РУЧНОЙ РЕЖИМ ---
            channel_ids = [channel.id for channel in self.generator.channels]
            for i, channel_id in enumerate(channel_ids):
                if i == 0 and self.plot_window.plot_widgets:
                    # Переиспользуем пустой график, который PlotWindow
                    # уже создал сам при открытии — иначе он повис бы
                    # пустым первым графиком перед всеми остальными.
                    plot_index = 0
                else:
                    plot = self.plot_window.add_plot()
                    plot_index = plot.plot_index
                self.plot_window.add_channel_to_plot(channel_id, plot_index=plot_index)

    def _get_scenario_channel_ids(self):
        """ID каналов, задействованных хоть в одном шаге текущего
        сценария (self.scenario_widget.scenario), без повторов, в
        порядке первого появления."""
        scenario = getattr(self.scenario_widget, "scenario", None)
        if not scenario or not getattr(scenario, "steps", None):
            return []
        seen = []
        for step in scenario.steps:
            if step.channel_id not in seen:
                seen.append(step.channel_id)
        return seen

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

    def on_scenario_mode_changed(self, mode: str):
        """Синхронизирует UI с фактическим режимом движка сценариев.

        Асимметрично специально: запуск/возобновление сценария
        автоматически переключает вид на "Сценарий" (удобно — то, что
        сейчас происходит, сразу видно). А вот когда сценарий
        останавливается или завершается сам (движок всегда возвращает
        mode в "manual" — это внутреннее состояние движка, а не
        команда UI), вид НЕ трогаем: пользователь мог быть на вкладке
        "Сценарий" и должен там же остаться, просто в состоянии
        Play-доступен/Stop-Пауза недоступны. Обратно на "Ручной" вид
        переключает только явный клик по тумблеру — см. request_channel_mode.
        """
        self._engine_mode = mode
        if hasattr(self, "mode_label"):
            mode_names = {
                "manual": "Ручной",
                "scenario": "Сценарий",
                "paused": "Пауза",
            }
            self.mode_label.setText(mode_names.get(mode, mode))
        if mode in ("scenario", "paused"):
            self._show_channel_mode_view("scenario")
        else:
            self._refresh_control_buttons()
        self._sync_generation_timer()

    def _sync_generation_timer(self):
        """Общий self.timer (тот, что вызывает update_signals) должен
        тикать, если реально что-то генерирует значения — ручной режим
        ИЛИ активно проигрываемый сценарий. На паузе сценария (mode ==
        "paused") таймер тоже останавливаем: пауза должна замораживать
        не только переход между шагами (это делает свой таймер внутри
        ScenarioEngine), но и сами значения каналов, а их считает
        generator.update(), вызываемый именно отсюда.
        """
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

    def _show_channel_mode_view(self, view: str):
        """Переключить ВИДИМУЮ панель (сетка каналов ИЛИ конструктор
        сценария) — чисто UI-действие, движок не трогает.

        Используется и явным кликом по тумблеру, и синхронизацией с
        фактическим режимом движка (on_scenario_mode_changed).
        """
        is_scenario_view = view == "scenario"

        if hasattr(self, "mode_stack") and self.mode_stack:
            # mode_stack: index 0 — сетка каналов (ручной), index 1 — конструктор сценария.
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

    def _refresh_control_buttons(self):
        """Единая точка, решающая состояние Play/Stop/Пауза/прогресс-бара
        в ControlPanel — общей панели для ручного режима и сценария.

        Что именно отражают кнопки, зависит от того, какая вкладка сейчас
        выбрана: в "Сценарий" — состояние ScenarioEngine, в "Ручной" —
        self.is_running/self.is_paused. Вызывается при любой смене вида
        или состояния — это единственное место, где выставляется иконка
        Пауза/Возобновить, чтобы не разъезжаться с реальным состоянием.
        """
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
        else:
            self.control_panel.set_running_state(self.is_running)
            self.control_panel.set_pause_enabled(self.is_running)
            self.control_panel.set_pause_icon(paused=self.is_paused)
            self.control_panel.set_progress_visible(False)
            self.control_panel.set_toggle_all_enabled(True)

    def _is_scenario_view_active(self) -> bool:
        return hasattr(self, "mode_stack") and self.mode_stack.currentIndex() == 1

    def on_play_clicked(self):
        """Play: запускает сценарий, если открыта вкладка "Сценарий",
        иначе — обычную ручную генерацию."""
        if self._is_scenario_view_active():
            self.scenario_widget.play_scenario()
        else:
            self.start_generation()

    def on_stop_clicked(self):
        if self._is_scenario_view_active():
            self.scenario_widget.stop_scenario()
        else:
            self.stop_generation()

    def on_pause_clicked(self):
        """Пауза/Возобновить — работает одинаково в обоих режимах:
        замораживает таймер, не сбрасывая состояние (в отличие от Stop).
        Повторный клик по той же кнопке возобновляет."""
        if self._is_scenario_view_active():
            self.scenario_widget.pause_scenario()
        else:
            if self.is_paused:
                self.resume_generation()
            else:
                self.pause_generation()

    def on_scenario_started(self, name: str):
        self._update_scenario_time(0.0)
        self._refresh_control_buttons()

        # Показываем прогресс в окне графиков
        if self.plot_window and self.plot_window.isVisible():
            self.plot_window.begin_scenario_acquisition()
            self.plot_window.set_scenario_progress(0)
            self.plot_window.progress_bar.setVisible(True)

    def on_scenario_stopped(self):
        self._refresh_control_buttons()
        if hasattr(self, "control_panel"):
            self.control_panel.set_progress(0)
            self._update_scenario_time(0.0)

        # Скрываем прогресс в окне графиков
        if self.plot_window and self.plot_window.isVisible():
            self.plot_window.end_scenario_acquisition()
            self.plot_window.set_scenario_progress(0)
            self.plot_window.progress_bar.setVisible(False)

    def on_scenario_finished(self):
        scenario = self.scenario_engine.scenario
        if scenario:
            self.control_panel.set_progress(100)
            self._update_scenario_time(scenario.get_total_duration())
        self._refresh_control_buttons()

        # Показываем завершение в окне графиков
        if self.plot_window and self.plot_window.isVisible():
            self.plot_window.end_scenario_acquisition()
            self.plot_window.set_scenario_progress(100)

    def on_scenario_progress_changed(self, progress: float):
        """Обновить прогресс сценария."""
        if hasattr(self, "control_panel"):
            self.control_panel.set_progress(int(progress))

        # Передаём прогресс в окно графиков
        if self.plot_window and self.plot_window.isVisible():
            self.plot_window.set_scenario_progress(int(progress))

    def on_scenario_time_updated(self, elapsed: float) -> None:
        self._update_scenario_time(elapsed)
        if self.plot_window and self.plot_window.isVisible():
            self.plot_window.set_scenario_time(elapsed)

    def on_scenario_definition_changed(self, scenario: Scenario) -> None:
        """Показать расчётное время ещё до запуска сценария."""
        if self.scenario_engine.is_running():
            return
        self.control_panel.set_progress(0)
        self.control_panel.set_scenario_time(0.0, scenario.get_total_duration())

    def _update_scenario_time(self, elapsed: float) -> None:
        if not hasattr(self, "control_panel"):
            return
        scenario = self.scenario_engine.scenario
        total = scenario.get_total_duration() if scenario else 0.0
        self.control_panel.set_scenario_time(elapsed, total)

    def request_channel_mode(self, target_mode: str):
        """Обработчик клика по тумблеру Ручной/Сценарий.

        Важно: переход к виду "Сценарий" — это просто открыть конструктор
        шагов, а НЕ запустить сценарий. Раньше клик сразу просил движок
        перейти в режим "Сценарий", а тот отказывался, если сценарий
        пуст — получался тупик: увидеть конструктор (чтобы добавить
        первый шаг) можно было только после перехода, а перейти —
        только если шаги уже есть.

        Реальный запуск — по кнопке Play в ControlPanel (см. on_play_clicked),
        она уже сама проверяет, что сценарий не пуст.

        Единственный случай, когда тумблер обращается к движку: уход
        из работающего/приостановленного сценария обратно в "Ручной" —
        это явная просьба остановить его. Вид переключаем явно сами,
        не полагаясь на сигнал mode_changed от движка: он теперь не
        дёргает вид сам по себе при возврате в "manual" (см.
        on_scenario_mode_changed) — это нужно, чтобы сценарий, дошедший
        до конца САМ, не перебрасывал пользователя на вкладку "Ручной".
        """
        if target_mode == "scenario":
            self._show_channel_mode_view("scenario")
            return

        # target_mode == "manual"
        if getattr(self, "_engine_mode", "manual") in ("scenario", "paused"):
            self.scenario_widget.set_engine_mode("manual")
        self._show_channel_mode_view("manual")

    def on_plc_debug_data(self, debug_info: dict):
        self.log(
            f"Запись PLC #{debug_info['write_count']}: "
            f"{len(debug_info.get('registers', []))} регистров",
            "debug",
        )

    def start_generation(self):
        if self.is_running:
            return
        self.is_running = True
        self.is_paused = False
        self._sync_generation_timer()
        self.status_label.setText("● Работает")
        self.status_label.setStyleSheet(
            "color: #00CC00; font-weight: bold; font-size: 12px;"
        )
        self._refresh_control_buttons()

    def stop_generation(self):
        if not self.is_running:
            return
        self.is_running = False
        self.is_paused = False
        self._sync_generation_timer()
        self.status_label.setText("● Остановлен")
        self.status_label.setStyleSheet(
            "color: #FF4444; font-weight: bold; font-size: 12px;"
        )
        self._refresh_control_buttons()

    def pause_generation(self):
        """Заморозить таймер, не сбрасывая is_running — в отличие от
        stop_generation() это временная приостановка, из которой можно
        вернуться resume_generation(), а не полный сброс состояния."""
        if not self.is_running or self.is_paused:
            return
        self.is_paused = True
        self._sync_generation_timer()
        self.status_label.setText("⏸ Пауза")
        self.status_label.setStyleSheet(
            "color: #FF9800; font-weight: bold; font-size: 12px;"
        )
        self._refresh_control_buttons()

    def resume_generation(self):
        if not self.is_running or not self.is_paused:
            return
        self.is_paused = False
        self._sync_generation_timer()
        self.status_label.setText("● Работает")
        self.status_label.setStyleSheet(
            "color: #00CC00; font-weight: bold; font-size: 12px;"
        )
        self._refresh_control_buttons()

    def reset_signals(self):
        """Сбросить сигналы и очистить графики."""
        # Сбрасываем значения каналов
        for channel in self.generator.channels:
            channel.time = 0
            channel.current_value = 0

        # Очищаем графики, если окно открыто
        if self.plot_window and self.plot_window.isVisible():
            for plot in self.plot_window.plot_widgets:
                plot.clear_plot()
            self.plot_window._update_channels_list()
            self.log("Графики очищены", "info")

        self.update_signals()
        self.log("Сигналы сброшены", "info")

    def on_toggle_all_channels_clicked(self):
        """Включить/выключить разом все каналы. Актуально только для
        ручного режима — в сценарии enabled каждого канала выставляет
        сам ScenarioEngine по шагам (см. _refresh_control_buttons,
        где кнопка гасится в режиме "Сценарий").

        Логика "все включены → выключить всё, иначе → включить всё":
        если хотя бы один канал выключен, первый клик включает всех
        разом, а не переключает вразнобой.
        """
        if self._is_scenario_view_active():
            return

        all_enabled = all(ch.enabled for ch in self.generator.channels)
        new_state = not all_enabled

        for widget in self.channel_widgets:
            try:
                widget.enabled_check.setChecked(new_state)
            except (RuntimeError, AttributeError):
                continue

    def update_signals(self):
        """Обновить сигналы и UI"""
        scenario_running = (
            hasattr(self, "scenario_engine") and self.scenario_engine.is_running()
        )

        if not self.is_running and not scenario_running:
            return

        # generator.update() — единственное место, которое реально считает
        # current_value по параметрам канала (signal_type/frequency/amplitude/
        # offset). ScenarioEngine на каждом шаге меняет только эти параметры
        # (_apply_step), саму генерацию значения не делает — значит,
        # update() должен работать и во время сценария, иначе значения
        # каналов (а с ними и графики в PlotWindow, который тянет их
        # напрямую из generator) просто замирают на месте.
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
                self.stats_label.setText(
                    f"Каналов: {len(self.generator.channels)} · Активных: {active_count}"
                )
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

    def closeEvent(self, event):  # type: ignore # noqa: N802
        self._save_channels_config()
        self.log("Настройки каналов сохранены", "info")

        if self.plot_window:
            self.plot_window.close()
        if self.plc_view:
            self.plc_view.close()
        self.plc_interface.disconnect()
        self.modbus.close()
        event.accept()
