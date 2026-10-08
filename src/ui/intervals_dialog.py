"""Модальное окно настройки интервалов обновления."""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
)

from ui.interval_control import IntervalControl


class IntervalsDialog(QDialog):
    """Диалог интервалов: обёртка над IntervalControl.

    IntervalControl остаётся источником истины по значениям интервалов
    и их автосохранению. Диалог лишь размещает панель в модальном окне
    и пробрасывает её сигналы наружу.
    """

    signal_interval_changed = pyqtSignal(float)
    plc_interval_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Интервалы обновления")
        self.setModal(True)
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.interval_control = IntervalControl()
        # В диалоге сворачивание не нужно — держим панель развёрнутой.
        self.interval_control.set_collapsed(False)
        self.interval_control.signal_interval_changed.connect(
            self.signal_interval_changed.emit
        )
        self.interval_control.plc_interval_changed.connect(
            self.plc_interval_changed.emit
        )
        layout.addWidget(self.interval_control)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.accept)
        buttons_row.addWidget(self.close_btn)
        layout.addLayout(buttons_row)
