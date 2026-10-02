"""Верхнее меню главного окна."""

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QAction, QActionGroup, QMenuBar


class AppMenuBar(QMenuBar):
    """Классическое меню: Файл / Подключение / Настройки / Справка."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # ----------------------------------------------------------
        # Файл
        # ----------------------------------------------------------
        file_menu = self.addMenu("Файл")

        self.open_scenario_action = QAction("Открыть сценарий…", self)
        self.open_scenario_action.setShortcut(QKeySequence("Ctrl+O"))
        file_menu.addAction(self.open_scenario_action)

        self.save_scenario_action = QAction("Сохранить сценарий…", self)
        self.save_scenario_action.setShortcut(QKeySequence("Ctrl+S"))
        file_menu.addAction(self.save_scenario_action)

        file_menu.addSeparator()

        self.save_channels_action = QAction("Сохранить настройки каналов", self)
        self.save_channels_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        file_menu.addAction(self.save_channels_action)

        file_menu.addSeparator()

        self.exit_action = QAction("Выход", self)
        self.exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        file_menu.addAction(self.exit_action)

        # ----------------------------------------------------------
        # Подключение
        # ----------------------------------------------------------
        connection_menu = self.addMenu("Подключение")

        self.connect_action = QAction("Подключиться…", self)
        self.connect_action.setShortcut(QKeySequence("Ctrl+K"))
        connection_menu.addAction(self.connect_action)

        self.disconnect_action = QAction("Отключиться", self)
        self.disconnect_action.setShortcut(QKeySequence("Ctrl+D"))
        connection_menu.addAction(self.disconnect_action)

        connection_menu.addSeparator()

        device_menu = connection_menu.addMenu("Тип устройства")
        self.device_group = QActionGroup(self)
        self.device_group.setExclusive(True)

        self.device_owen_action = QAction("ОВЕН МУ210-501", self)
        self.device_owen_action.setCheckable(True)
        self.device_owen_action.setChecked(True)
        self.device_owen_action.setShortcut(QKeySequence("Ctrl+1"))
        self.device_group.addAction(self.device_owen_action)
        device_menu.addAction(self.device_owen_action)

        self.device_plc_action = QAction("PLC Modicon Premium", self)
        self.device_plc_action.setCheckable(True)
        self.device_plc_action.setShortcut(QKeySequence("Ctrl+2"))
        self.device_group.addAction(self.device_plc_action)
        device_menu.addAction(self.device_plc_action)

        self.device_moxa_e1242_action = QAction("Moxa ioLogik E1242", self)
        self.device_moxa_e1242_action.setCheckable(True)
        self.device_moxa_e1242_action.setShortcut(QKeySequence("Ctrl+4"))
        self.device_group.addAction(self.device_moxa_e1242_action)
        device_menu.addAction(self.device_moxa_e1242_action)


        self.device_sim_action = QAction("Simulator", self)
        self.device_sim_action.setCheckable(True)
        self.device_sim_action.setShortcut(QKeySequence("Ctrl+3"))
        self.device_group.addAction(self.device_sim_action)
        device_menu.addAction(self.device_sim_action)

        # ----------------------------------------------------------
        # Настройки
        # ----------------------------------------------------------
        settings_menu = self.addMenu("Настройки")

        self.settings_action = QAction("Настройки…", self)
        self.settings_action.setShortcut(QKeySequence("Ctrl+I"))
        settings_menu.addAction(self.settings_action)

        settings_menu.addSeparator()

        # Тема
        theme_menu = settings_menu.addMenu("Тема")
        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)

        self.theme_light_action = QAction("Светлая", self)
        self.theme_light_action.setCheckable(True)
        self.theme_light_action.setChecked(True)
        self.theme_group.addAction(self.theme_light_action)
        theme_menu.addAction(self.theme_light_action)

        self.theme_dark_action = QAction("Тёмная", self)
        self.theme_dark_action.setCheckable(True)
        self.theme_group.addAction(self.theme_dark_action)
        theme_menu.addAction(self.theme_dark_action)

        # Размер интерфейса
        scale_menu = settings_menu.addMenu("Размер интерфейса")
        self.scale_group = QActionGroup(self)
        self.scale_group.setExclusive(True)

        self.scale_medium_action = QAction("Средний", self)
        self.scale_medium_action.setCheckable(True)
        self.scale_medium_action.setChecked(True)
        self.scale_group.addAction(self.scale_medium_action)
        scale_menu.addAction(self.scale_medium_action)

        self.scale_large_action = QAction("Крупный", self)
        self.scale_large_action.setCheckable(True)
        self.scale_group.addAction(self.scale_large_action)
        scale_menu.addAction(self.scale_large_action)

        settings_menu.addSeparator()

        self.plots_action = QAction("Графики", self)
        self.plots_action.setShortcut(QKeySequence("Ctrl+G"))
        settings_menu.addAction(self.plots_action)

        self.registers_action = QAction("Регистры устройства", self)
        self.registers_action.setShortcut(QKeySequence("Ctrl+R"))
        settings_menu.addAction(self.registers_action)

        # ----------------------------------------------------------
        # Справка
        # ----------------------------------------------------------
        help_menu = self.addMenu("Справка")

        self.about_action = QAction("О программе", self)
        self.about_action.setShortcut(QKeySequence("F1"))
        help_menu.addAction(self.about_action)

    # ------------------------------------------------------------------
    # Синхронизация состояния меню с настройками
    # ------------------------------------------------------------------

    def sync_theme_actions(self, theme: str) -> None:
        """Отметить актуальную тему в меню."""
        if theme == "dark":
            self.theme_dark_action.setChecked(True)
        else:
            self.theme_light_action.setChecked(True)

    def sync_scale_actions(self, scale: str) -> None:
        """Отметить актуальный масштаб в меню."""
        if scale == "large":
            self.scale_large_action.setChecked(True)
        else:
            self.scale_medium_action.setChecked(True)