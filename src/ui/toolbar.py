"""Верхняя панель инструментов главного окна."""

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import QAction, QProgressBar, QToolBar

from ui.themes import get_theme


class AppToolBar(QToolBar):
    """Классический toolbar с крупными иконками."""

    play_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    reset_clicked = pyqtSignal()
    disable_all_clicked = pyqtSignal()
    plots_clicked = pyqtSignal()
    registers_clicked = pyqtSignal()
    save_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Панель инструментов", parent)
        self.setMovable(False)
        self.setIconSize(QSize(22, 22))
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # --- Управление ---
        self.play_action = QAction("▶ Старт", self)
        self.play_action.setToolTip("Запустить генерацию/сценарий")
        self.play_action.triggered.connect(self.play_clicked.emit)
        self.addAction(self.play_action)

        self.pause_action = QAction("⏸ Пауза", self)
        self.pause_action.setToolTip("Пауза / Возобновить")
        self.pause_action.setEnabled(False)
        self.pause_action.triggered.connect(self.pause_clicked.emit)
        self.addAction(self.pause_action)

        self.stop_action = QAction("⏹ Стоп", self)
        self.stop_action.setToolTip("Остановить")
        self.stop_action.setEnabled(False)
        self.stop_action.triggered.connect(self.stop_clicked.emit)
        self.addAction(self.stop_action)

        self.reset_action = QAction("↺ Сброс", self)
        self.reset_action.setToolTip("Сбросить сигналы и очистить графики")
        self.reset_action.triggered.connect(self.reset_clicked.emit)
        self.addAction(self.reset_action)

        self.scenario_progress = QProgressBar(self)
        self.scenario_progress.setRange(0, 100)
        self.scenario_progress.setValue(0)
        self.scenario_progress.setFormat("Сценарий: %p%")
        self.scenario_progress.setFixedWidth(160)
        self.scenario_progress.setToolTip("Прогресс выполнения сценария")
        self.scenario_progress_action = self.addWidget(self.scenario_progress)
        self.scenario_progress_action.setVisible(False)

        self.disable_all_action = QAction("Выключить все", self)
        self.disable_all_action.setToolTip("Снять галку «Вкл.» у всех каналов")
        self.disable_all_action.triggered.connect(self.disable_all_clicked.emit)
        self.addAction(self.disable_all_action)

        self.addSeparator()

        # --- Окна ---
        self.plots_action = QAction("📊 Графики", self)
        self.plots_action.setToolTip("Открыть окно графиков")
        self.plots_action.triggered.connect(self.plots_clicked.emit)
        self.addAction(self.plots_action)

        self.registers_action = QAction("📋 Регистры", self)
        self.registers_action.setToolTip("Открыть окно регистров устройства")
        self.registers_action.triggered.connect(self.registers_clicked.emit)
        self.addAction(self.registers_action)

        self.addSeparator()

        # --- Данные ---
        self.save_action = QAction("💾 Сохранить каналы", self)
        self.save_action.setToolTip("Сохранить настройки каналов")
        self.save_action.triggered.connect(self.save_clicked.emit)
        self.addAction(self.save_action)

        self.settings_action = QAction("⚙ Настройки", self)
        self.settings_action.setToolTip("Открыть настройки")
        self.settings_action.triggered.connect(self.settings_clicked.emit)
        self.addAction(self.settings_action)

    # ------------------------------------------------------------------
    # Обновление состояния
    # ------------------------------------------------------------------

    def set_running_state(self, is_running: bool, paused: bool = False) -> None:
        """Синхронизировать доступность кнопок Play/Pause/Stop."""
        self.play_action.setEnabled(not is_running)
        self.pause_action.setEnabled(is_running)
        self.stop_action.setEnabled(is_running)
        self.set_pause_icon(paused)

    def set_pause_icon(self, paused: bool) -> None:
        if paused:
            self.pause_action.setText("▶ Возобновить")
        else:
            self.pause_action.setText("⏸ Пауза")

    def set_scenario_progress(self, progress: int) -> None:
        progress = max(0, min(100, progress))
        self.scenario_progress.setValue(progress)
        self.scenario_progress.setFormat(
            "Сценарий завершён" if progress == 100 else "Сценарий: %p%"
        )

    def apply_theme(self, theme_name: str) -> None:
        """Применить стили к toolbar под выбранную тему."""
        c = get_theme(theme_name)
        self.setStyleSheet(f"""
            QToolBar {{
                background-color: {c.toolbar_bg};
                border-bottom: 1px solid {c.border};
                spacing: 3px;
                padding: 3px 6px;
            }}
            QToolBar::separator {{
                width: 1px;
                background: {c.border_strong};
                margin: 4px 6px;
            }}
            QToolButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 4px 8px;
                color: {c.text};
            }}
            QToolButton:hover {{
                background-color: {c.primary_soft};
                border-color: {c.primary};
            }}
            QToolButton:pressed {{
                background-color: {c.primary};
                color: {c.text_inverse};
            }}
            QToolButton:disabled {{
                color: {c.disabled};
            }}
        """)
