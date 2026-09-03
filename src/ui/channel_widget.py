from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from core.channel import AnalogChannel
from core.signal_types import SignalType
from ui.styles import COLORS


class ChannelSettingsDialog(QDialog):
    """Диалог настроек канала"""

    def __init__(self, channel: AnalogChannel, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.setWindowTitle(f"Настройки канала {channel.id + 1}: {channel.name}")
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        form_layout = QFormLayout()

        self.name_edit = QLineEdit(self.channel.name)
        form_layout.addRow("Имя канала:", self.name_edit)

        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-10000, 10000)
        self.min_spin.setValue(self.channel.min_value)
        self.min_spin.setSingleStep(0.1)
        form_layout.addRow("Минимум:", self.min_spin)

        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-10000, 10000)
        self.max_spin.setValue(self.channel.max_value)
        self.max_spin.setSingleStep(0.1)
        form_layout.addRow("Максимум:", self.max_spin)

        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.01, 100)
        self.freq_spin.setValue(self.channel.frequency)
        self.freq_spin.setSingleStep(0.1)
        form_layout.addRow("Частота (Гц):", self.freq_spin)

        self.amp_spin = QDoubleSpinBox()
        self.amp_spin.setRange(0, 100)
        self.amp_spin.setValue(self.channel.amplitude)
        self.amp_spin.setSingleStep(1)
        form_layout.addRow("Амплитуда (%):", self.amp_spin)

        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-100, 100)
        self.offset_spin.setValue(self.channel.offset)
        self.offset_spin.setSingleStep(1)
        form_layout.addRow("Смещение (%):", self.offset_spin)

        self.kind_combo = QComboBox()
        self.kind_combo.addItem("Аналоговый", "analog")
        self.kind_combo.addItem("Дискретный", "discrete")
        self.kind_combo.setCurrentIndex(
            1 if self.channel.signal_type.is_discrete() else 0
        )
        self.kind_combo.currentIndexChanged.connect(self._populate_signal_types)
        form_layout.addRow("Категория канала:", self.kind_combo)

        self.type_combo = QComboBox()
        self.type_combo.currentIndexChanged.connect(self._update_parameter_visibility)
        form_layout.addRow("Тип сигнала:", self.type_combo)

        self.duty_label = QLabel("Скважность (%):")
        self.duty_spin = QDoubleSpinBox()
        self.duty_spin.setRange(0.0, 100.0)
        self.duty_spin.setValue(self.channel.duty_cycle)
        self.duty_spin.setSuffix(" %")
        form_layout.addRow(self.duty_label, self.duty_spin)

        self.pulse_width_label = QLabel("Длительность импульса:")
        self.pulse_width_spin = QDoubleSpinBox()
        self.pulse_width_spin.setRange(0.001, 10.0)
        self.pulse_width_spin.setDecimals(3)
        self.pulse_width_spin.setValue(self.channel.pulse_width)
        self.pulse_width_spin.setSuffix(" с")
        form_layout.addRow(self.pulse_width_label, self.pulse_width_spin)

        self._populate_signal_types()

        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(self.channel.enabled)
        form_layout.addRow("Включен:", self.enabled_check)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setMinimumWidth(350)

    def _populate_signal_types(self) -> None:
        """Заполнить типы сигналов выбранной категории."""
        current_name = self.channel.signal_type.name
        signal_types = (
            SignalType.get_discrete_types()
            if self.kind_combo.currentData() == "discrete"
            else SignalType.get_analog_types()
        )
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        for signal_type in signal_types:
            self.type_combo.addItem(str(signal_type), signal_type.name)
        index = self.type_combo.findData(current_name)
        self.type_combo.setCurrentIndex(index if index >= 0 else 0)
        self.type_combo.blockSignals(False)
        self._update_parameter_visibility()

    def _update_parameter_visibility(self) -> None:
        """Показывать только параметры выбранного типа сигнала."""
        signal_name = self.type_combo.currentData()
        is_pwm = signal_name == SignalType.PWM.name
        is_pulse = signal_name == SignalType.PULSE.name
        self.duty_label.setVisible(is_pwm)
        self.duty_spin.setVisible(is_pwm)
        self.pulse_width_label.setVisible(is_pulse)
        self.pulse_width_spin.setVisible(is_pulse)

    def get_settings(self) -> dict:
        """Получить измененные настройки"""
        return {
            "name": self.name_edit.text(),
            "min_value": self.min_spin.value(),
            "max_value": self.max_spin.value(),
            "frequency": self.freq_spin.value(),
            "amplitude": self.amp_spin.value(),
            "offset": self.offset_spin.value(),
            "signal_type": self.type_combo.currentData(),
            "enabled": self.enabled_check.isChecked(),
            "duty_cycle": self.duty_spin.value(),
            "pulse_width": self.pulse_width_spin.value(),
        }


class ChannelWidget(QFrame):
    """Виджет для отображения и управления одним каналом"""

    channel_selected = pyqtSignal(int)
    channel_type_changed = pyqtSignal(int, str)
    channel_settings_changed = pyqtSignal(int)

    def __init__(self, channel: AnalogChannel, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.setup_ui()
        self.update_display()

    def setup_ui(self):
        self.setObjectName("channelCard")

        layout = QVBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(5, 5, 5, 5)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.type_badge = QLabel()
        self.type_badge.setAlignment(Qt.AlignCenter)
        self.type_badge.setFixedWidth(22)
        header_layout.addWidget(self.type_badge)

        self.name_label = QLabel(f"Ch{self.channel.id + 1}: {self.channel.name}")
        self.name_label.setObjectName("channelName")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFont(QFont("Arial", 8, QFont.Bold))
        self.name_label.mousePressEvent = self.on_name_click
        header_layout.addWidget(self.name_label, 1)
        layout.addLayout(header_layout)

        self.value_label = QLabel("0.00")
        self.value_label.setObjectName("channelValue")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.value_label)

        self.bar_frame = QFrame()
        bar_layout = QVBoxLayout()
        bar_layout.setContentsMargins(0, 0, 0, 0)
        self.bar = QFrame()
        self.bar.setFixedHeight(4)
        self.bar.setStyleSheet(
            f"background-color: {COLORS['success']}; border-radius: 2px;"
        )
        bar_layout.addWidget(self.bar)

        bounds_layout = QHBoxLayout()
        bounds_layout.setContentsMargins(0, 0, 0, 0)
        self.min_label = QLabel(f"{self.channel.min_value:.0f}")
        self.min_label.setObjectName("channelBound")
        self.min_label.setAlignment(Qt.AlignLeft)
        bounds_layout.addWidget(self.min_label)
        bounds_layout.addStretch()
        self.max_label = QLabel(f"{self.channel.max_value:.0f}")
        self.max_label.setObjectName("channelBound")
        self.max_label.setAlignment(Qt.AlignRight)
        bounds_layout.addWidget(self.max_label)

        bar_layout.addLayout(bounds_layout)
        self.bar_frame.setLayout(bar_layout)
        layout.addWidget(self.bar_frame)

        self.type_combo = QComboBox()
        for signal_type in SignalType:
            self.type_combo.addItem(str(signal_type), signal_type.name)
        index = self.type_combo.findData(self.channel.signal_type.name)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        layout.addWidget(self.type_combo)

        settings_layout = QHBoxLayout()
        settings_layout.setContentsMargins(0, 0, 0, 0)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("iconButton")
        self.settings_btn.setToolTip("Настройки канала")
        self.settings_btn.clicked.connect(self.open_settings)
        settings_layout.addWidget(self.settings_btn, alignment=Qt.AlignCenter)

        self.enabled_check = QCheckBox("Вкл")
        self.enabled_check.setChecked(self.channel.enabled)
        self.enabled_check.stateChanged.connect(self.on_enabled_changed)
        settings_layout.addWidget(self.enabled_check, alignment=Qt.AlignCenter)

        layout.addLayout(settings_layout)

        self.setLayout(layout)
        self.setMinimumSize(112, 154)
        self.setMaximumWidth(148)
        self.update_type_designation()

    def update_type_designation(self) -> None:
        """Показать обозначение аналогового или дискретного канала."""
        is_discrete = self.channel.signal_type.is_discrete()
        designation = "D" if is_discrete else "A"
        color = "#3b82f6" if is_discrete else "#22a06b"
        kind = "Дискретный" if is_discrete else "Аналоговый"
        self.type_badge.setText(designation)
        self.type_badge.setToolTip(f"{kind} канал")
        self.type_badge.setStyleSheet(
            f"background: {color}; color: white; border-radius: 4px; "
            "font-weight: bold; padding: 2px;"
        )

    def on_name_click(self, event):
        self.channel_selected.emit(self.channel.id)

    def on_type_changed(self, text: str):
        try:
            signal_name = self.type_combo.currentData()
            signal_type = SignalType[signal_name]
            self.channel.signal_type = signal_type
            self.update_type_designation()
            self.channel_type_changed.emit(self.channel.id, str(signal_type))
        except (KeyError, TypeError):
            pass

    def open_settings(self):
        dialog = ChannelSettingsDialog(self.channel, self)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()

            self.channel.name = settings["name"]
            self.channel.min_value = settings["min_value"]
            self.channel.max_value = settings["max_value"]
            self.channel.frequency = settings["frequency"]
            self.channel.amplitude = settings["amplitude"]
            self.channel.offset = settings["offset"]
            self.channel.signal_type = SignalType[settings["signal_type"]]
            self.channel.enabled = settings["enabled"]
            self.channel.duty_cycle = settings["duty_cycle"]
            self.channel.pulse_width = settings["pulse_width"]

            self.name_label.setText(f"Ch{self.channel.id + 1}: {self.channel.name}")
            self.min_label.setText(f"{self.channel.min_value:.0f}")
            self.max_label.setText(f"{self.channel.max_value:.0f}")

            index = self.type_combo.findData(self.channel.signal_type.name)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)

            self.enabled_check.setChecked(self.channel.enabled)
            self.update_type_designation()
            self.update_display()

            self.channel_settings_changed.emit(self.channel.id)

    def on_enabled_changed(self, state):
        self.channel.enabled = bool(state)
        if not state:
            self.value_label.setStyleSheet(f"color: {COLORS['disabled']};")
            self.bar.setStyleSheet(
                f"background-color: {COLORS['disabled']}; border-radius: 2px;"
            )
            self.type_combo.setEnabled(False)
            self.settings_btn.setEnabled(False)
        else:
            self.value_label.setStyleSheet(f"color: {COLORS['primary']};")
            self.bar.setStyleSheet(
                f"background-color: {COLORS['success']}; border-radius: 2px;"
            )
            self.type_combo.setEnabled(True)
            self.settings_btn.setEnabled(True)

    def update_display(self):
        """Обновить отображение значения"""
        try:
            # Проверяем существование основных виджетов
            if not hasattr(self, "value_label") or not self.value_label:
                return

            if self.channel.enabled:
                value = self.channel.current_value
                self.value_label.setText(f"{value:.1f}")

                range_val = self.channel.max_value - self.channel.min_value
                if range_val > 0:
                    percent = (value - self.channel.min_value) / range_val
                    bar_width = max(0, min(100, percent * 100))
                else:
                    bar_width = 50

                if self.bar:
                    self.bar.setStyleSheet(f"""
                        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 {COLORS["success"]},
                            stop:{bar_width / 100} {COLORS["success"]},
                            stop:{bar_width / 100} {COLORS["border"]},
                            stop:1 {COLORS["border"]});
                        border-radius: 2px;
                    """)
            else:
                if self.value_label:
                    self.value_label.setText("Off")
                if self.bar:
                    self.bar.setStyleSheet(
                        f"background-color: {COLORS['disabled']}; border-radius: 2px;"
                    )

        except (RuntimeError, AttributeError):
            # Виджет уже удален - просто игнорируем
            # print(f"[DEBUG] Widget update error: {e}")
            pass

    def update_channel(self, channel: AnalogChannel):
        self.channel = channel
        self.name_label.setText(f"Ch{channel.id + 1}: {channel.name}")
        self.min_label.setText(f"{channel.min_value:.0f}")
        self.max_label.setText(f"{channel.max_value:.0f}")

        index = self.type_combo.findData(channel.signal_type.name)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)

        self.enabled_check.setChecked(channel.enabled)
        self.update_type_designation()
        self.update_display()
