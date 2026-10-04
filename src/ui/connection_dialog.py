"""Модальное окно настройки подключения к устройству вывода."""

from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ui.connection_panel import ConnectionPanel


class ConnectionDialog(QDialog):
    """Диалог подключения: обёртка над ConnectionPanel.

    ConnectionPanel остаётся источником истины по параметрам и логике
    подключения. Диалог лишь размещает панель в модальном окне,
    пробрасывает наружу её сигналы и добавляет кнопку «Закрыть».
    """

    connected = pyqtSignal(bool)
    connection_changed = pyqtSignal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Подключение")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.resize(640, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Панель подключения — та же, что была на главном окне.
        self.connection_panel = ConnectionPanel(self)
        # В диалоге сворачивание не нужно — держим панель развёрнутой.
        self.connection_panel.set_collapsed(False)
        self.connection_panel.setCheckable(False)
        self.connection_panel.connected.connect(self.connected.emit)
        self.connection_panel.connection_changed.connect(self.connection_changed.emit)
        layout.addWidget(self.connection_panel)

        # Кнопка закрытия
        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.accept)
        buttons_row.addWidget(self.close_btn)
        layout.addLayout(buttons_row)

    # ------------------------------------------------------------------
    # Прокси-методы — чтобы MainWindow мог работать с диалогом так же,
    # как раньше работал с панелью.
    # ------------------------------------------------------------------

    def set_connection_status(self, connected: bool) -> None:
        self.connection_panel.set_connection_status(connected)

    def get_connection_params(self) -> dict:
        return self.connection_panel.get_connection_params()
