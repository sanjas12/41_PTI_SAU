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

        self.device_sim_action = QAction("Simulator", self)
        self.device_sim_action.setCheckable(True)
        self.device_sim_action.setShortcut(QKeySequence("Ctrl+3"))
        self.device_group.addAction(self.device_sim_action)
        device_menu.addAction(self.device_sim_action)

        # ----------------------------------------------------------
        # Настройки
        # ----------------------------------------------------------
        settings_menu = self.addMenu("Настройки")

        self.intervals_action = QAction("Интервалы обновления…", self)
        self.intervals_action.setShortcut(QKeySequence("Ctrl+I"))
        settings_menu.addAction(self.intervals_action)

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