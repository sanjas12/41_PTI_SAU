"""Диалог общих настроек: тема, масштаб UI, интервалы."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from config.ui_settings import UISettings
from ui.interval_control import IntervalControl


class SettingsDialog(QDialog):
    """Единый диалог настроек: тема, масштаб, интервалы."""

    theme_changed = pyqtSignal(str)      # "light" / "dark"
    ui_scale_changed = pyqtSignal(str)   # "medium" / "large"
    signal_interval_changed = pyqtSignal(float)
    plc_interval_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setMinimumWidth(640)

        self._ui_settings = UISettings.instance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # --- Внешний вид ---
        appearance_group = QGroupBox("Внешний вид")
        appearance_form = QFormLayout(appearance_group)
        appearance_form.setSpacing(6)

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
        intervals_group = QGroupBox("Интервалы обновления")
        intervals_layout = QVBoxLayout(intervals_group)
        intervals_layout.setContentsMargins(6, 10, 6, 6)

        self.interval_control = IntervalControl()
        self.interval_control.set_collapsed(False)
        self.interval_control.signal_interval_changed.connect(
            self.signal_interval_changed.emit
        )
        self.interval_control.plc_interval_changed.connect(
            self.plc_interval_changed.emit
        )
        intervals_layout.addWidget(self.interval_control)

        layout.addWidget(intervals_group)

        # --- Кнопки ---
        buttons_row = QHBoxLayout()
        buttons_row.addStretch()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.button(QDialogButtonBox.Ok).setText("Закрыть")
        button_box.accepted.connect(self.accept)
        buttons_row.addWidget(button_box)

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