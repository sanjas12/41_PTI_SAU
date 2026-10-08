"""Строка состояния главного окна с индикаторами режима и подключения."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QLabel,
    QStatusBar,
    QWidget,
)


class IndicatorLabel(QLabel):
    """Компактный индикатор в стиле «утопленной» панели.

    Используется для отображения состояния (режим, подключение, FPS).
    Зелёный фон — активное состояние, белый — нейтральное, серый — отключено.
    """

    STATE_ACTIVE = "active"
    STATE_NEUTRAL = "neutral"
    STATE_OFFLINE = "offline"

    _STYLES = {
        STATE_ACTIVE: """
            QLabel {
                background-color: #2f8f4b;
                color: white;
                border: 1px solid #1f6a37;
                border-radius: 0px;
                padding: 1px 8px;
                font-weight: 600;
            }
        """,
        STATE_NEUTRAL: """
            QLabel {
                background-color: #ffffff;
                color: #1f2933;
                border: 1px solid #9da8b3;
                border-radius: 0px;
                padding: 1px 8px;
            }
        """,
        STATE_OFFLINE: """
            QLabel {
                background-color: #f0f0f0;
                color: #66727d;
                border: 1px solid #9da8b3;
                border-radius: 0px;
                padding: 1px 8px;
            }
        """,
    }

    def __init__(self, text: str = "", state: str = STATE_NEUTRAL, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(18)
        self.set_state(state)

    def set_state(self, state: str) -> None:
        """Переключить визуальное состояние индикатора."""
        style = self._STYLES.get(state, self._STYLES[self.STATE_NEUTRAL])
        self.setStyleSheet(style)


class AppStatusBar(QStatusBar):
    """Строка состояния: статус слева, индикаторы справа."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.setStyleSheet("""
            QStatusBar {
                background-color: #e6e8eb;
                border-top: 1px solid #c7ced6;
            }
            QStatusBar::item {
                border: none;
            }
        """)

        # Левая часть — общий статус приложения
        self.ready_label = QLabel("Ready")
        self.ready_label.setStyleSheet(
            "color: #1f2933; padding-left: 6px; font-size: 9pt;"
        )
        self.addWidget(self.ready_label)

        # Распорка, прижимающая индикаторы вправо
        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().Expanding, spacer.sizePolicy().Preferred
        )
        self.addWidget(spacer, 1)

        # --- Правая часть — индикаторы состояния ---
        self.mode_indicator = IndicatorLabel("Ручной", IndicatorLabel.STATE_NEUTRAL)
        self.mode_indicator.setToolTip("Текущий режим работы")
        self.addPermanentWidget(self.mode_indicator)

        self.run_indicator = IndicatorLabel("Остановлен", IndicatorLabel.STATE_OFFLINE)
        self.run_indicator.setToolTip("Состояние генерации/сценария")
        self.addPermanentWidget(self.run_indicator)

        self.device_indicator = IndicatorLabel(
            "Устройство не выбрано", IndicatorLabel.STATE_NEUTRAL
        )
        self.device_indicator.setToolTip("Активное устройство вывода")
        self.addPermanentWidget(self.device_indicator)

        self.connection_indicator = IndicatorLabel(
            "OFFLINE", IndicatorLabel.STATE_OFFLINE
        )
        self.connection_indicator.setToolTip("Статус подключения к устройству")
        self.addPermanentWidget(self.connection_indicator)

        self.fps_indicator = IndicatorLabel("FPS: 0", IndicatorLabel.STATE_NEUTRAL)
        self.fps_indicator.setToolTip("Частота обновления интерфейса")
        self.addPermanentWidget(self.fps_indicator)

        # Минимальные отступы для компактного вида
        self.setContentsMargins(0, 0, 0, 0)

    # ------------------------------------------------------------------
    # Обновление индикаторов
    # ------------------------------------------------------------------

    def set_ready_text(self, text: str) -> None:
        """Обновить текст общего статуса слева."""
        self.ready_label.setText(text)

    def set_mode(self, mode: str) -> None:
        """Установить режим: manual / scenario / paused."""
        mapping = {
            "manual": ("Ручной", IndicatorLabel.STATE_NEUTRAL),
            "scenario": ("Сценарий", IndicatorLabel.STATE_ACTIVE),
            "paused": ("Пауза", IndicatorLabel.STATE_ACTIVE),
        }
        text, state = mapping.get(mode, ("Ручной", IndicatorLabel.STATE_NEUTRAL))
        self.mode_indicator.setText(text)
        self.mode_indicator.set_state(state)

    def set_running(self, running: bool, paused: bool = False) -> None:
        """Установить состояние работы."""
        if paused:
            self.run_indicator.setText("Пауза")
            self.run_indicator.set_state(IndicatorLabel.STATE_ACTIVE)
        elif running:
            self.run_indicator.setText("Работает")
            self.run_indicator.set_state(IndicatorLabel.STATE_ACTIVE)
        else:
            self.run_indicator.setText("Остановлен")
            self.run_indicator.set_state(IndicatorLabel.STATE_OFFLINE)

    def set_device(self, device_name: str) -> None:
        """Показать имя активного устройства."""
        self.device_indicator.setText(device_name)
        self.device_indicator.set_state(IndicatorLabel.STATE_NEUTRAL)

    def set_connection(self, connected: bool, host: str = "", port: int = 0) -> None:
        """Обновить индикатор подключения."""
        if connected and host:
            self.connection_indicator.setText(f"TCPIP:{host}")
            self.connection_indicator.set_state(IndicatorLabel.STATE_ACTIVE)
            self.connection_indicator.setToolTip(f"Подключено к {host}:{port}")
        else:
            self.connection_indicator.setText("OFFLINE")
            self.connection_indicator.set_state(IndicatorLabel.STATE_OFFLINE)
            self.connection_indicator.setToolTip("Нет подключения")

    def set_fps(self, fps: int) -> None:
        """Обновить индикатор FPS."""
        self.fps_indicator.setText(f"FPS: {fps}")
