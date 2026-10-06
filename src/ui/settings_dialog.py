"""Диалог общих настроек: тема, масштаб UI, интервалы."""

from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.ui_settings import UISettings
from ui.interval_control import IntervalControl


class SettingsDialog(QDialog):
    """Единый диалог настроек: тема, масштаб, интервалы."""

    theme_changed = pyqtSignal(str)  # "light" / "dark"
    ui_scale_changed = pyqtSignal(str)  # "medium" / "large"
    signal_interval_changed = pyqtSignal(float)
    plc_interval_changed = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.resize(640, 520)

        self._ui_settings = UISettings.instance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # --- Внешний вид ---
        appearance_group = QGroupBox("Внешний вид")
        appearance_form = QFormLayout(appearance_group)
        appearance_form.setContentsMargins(12, 18, 12, 12)
        appearance_form.setHorizontalSpacing(12)
        appearance_form.setVerticalSpacing(8)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Светлая", "light")
        self.theme_combo.addItem("Тёмная", "dark")
        idx = self.theme_combo.findData(self._ui_settings.theme)
        self.theme_combo.setCurrentIndex(max(0, idx))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        appearance_form.addRow("Тема:", self.theme_combo)

        self.scale_combo = QComboBox()
        self.scale_combo.addItem("Средний", "medium")
        self.scale_combo.addItem("Крупный", "large")
        idx = self.scale_combo.findData(self._ui_settings.ui_scale)
        self.scale_combo.setCurrentIndex(max(0, idx))
        self.scale_combo.currentIndexChanged.connect(self._on_scale_changed)
        appearance_form.addRow("Размер интерфейса:", self.scale_combo)

        hint = QLabel(
            "Изменения применяются сразу после выбора. "
            "Настройки сохраняются автоматически."
        )
        hint.setObjectName("secondaryText")
        hint.setWordWrap(True)
        appearance_form.addRow("", hint)

        layout.addWidget(appearance_group)

        # --- Интервалы ---
        self.interval_control = IntervalControl(self)
        self.interval_control.setCheckable(False)
        self.interval_control.set_collapsed(False)
        self.interval_control.signal_interval_changed.connect(
            self.signal_interval_changed.emit
        )
        self.interval_control.plc_interval_changed.connect(
            self.plc_interval_changed.emit
        )
        layout.addWidget(self.interval_control)

        # --- Кнопки ---
        buttons_row = QHBoxLayout()
        buttons_row.addStretch()

        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.accept)
        buttons_row.addWidget(self.close_btn)

        layout.addLayout(buttons_row)

    # ------------------------------------------------------------------
    # Обработчики
    # ------------------------------------------------------------------

    def _on_theme_changed(self) -> None:
        theme = self.theme_combo.currentData()
        self._ui_settings.theme = theme
        self.theme_changed.emit(theme)

    def _on_scale_changed(self) -> None:
        scale = self.scale_combo.currentData()
        self._ui_settings.ui_scale = scale
        self.ui_scale_changed.emit(scale)
