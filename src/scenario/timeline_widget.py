"""Общая шкала параметров: дорожки и перемещаемые ключевые кадры."""

from typing import Any, Optional

from PyQt5.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QMouseEvent, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.output_devices import ALL_DEVICES, device_label
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from scenario.animation import PARAMETERS, STEP_PARAMETERS, AnimationTrack, Keyframe
from scenario.scenario_model import Scenario
from ui.styles import COLORS


class KeyframeDialog(QDialog):
    def __init__(self, track: AnimationTrack, key: Keyframe, parent: QWidget) -> None:
        super().__init__(parent)
        self.track = track
        self.setWindowTitle("Ключевой кадр — " + PARAMETERS[track.parameter])
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.time_spin = QDoubleSpinBox()
        self.time_spin.setDecimals(3)
        self.time_spin.setRange(0.0, 86400.0)
        self.time_spin.setSuffix(" с")
        self.time_spin.setValue(key.time)
        form.addRow("Время от начала сценария:", self.time_spin)
        self.choice = QComboBox()
        self.number = QDoubleSpinBox()
        self.number.setDecimals(3)
        self.number.setRange(-10000.0, 10000.0)
        parameter = track.parameter
        if parameter == "signal_type":
            for signal_type in SignalType:
                self.choice.addItem(str(signal_type), signal_type.name)
        elif parameter == "output_device":
            for device in ALL_DEVICES:
                self.choice.addItem(device_label(device), device)
        elif parameter == "enabled":
            self.choice.addItem("Выключен", False)
            self.choice.addItem("Включён", True)
        else:
            if parameter in ("amplitude", "duty_cycle"):
                self.number.setRange(0.0, 100.0)
            elif parameter == "offset":
                self.number.setRange(-100.0, 100.0)
            elif parameter in ("frequency", "pulse_width"):
                self.number.setRange(0.001, 100.0)
            elif parameter in ("output_address", "mu210_module"):
                self.number.setDecimals(0)
                self.number.setRange(0.0, 65535.0)
                if parameter == "mu210_module":
                    self.number.setRange(1.0, 32.0)
            self.number.setValue(float(key.value))
        self.uses_choice = parameter in ("signal_type", "output_device", "enabled")
        if self.uses_choice:
            self.choice.setCurrentIndex(max(0, self.choice.findData(key.value)))
        form.addRow("Значение:", self.choice if self.uses_choice else self.number)
        self.interpolation = QComboBox()
        if parameter not in STEP_PARAMETERS:
            self.interpolation.addItem("Линейно", "linear")
        self.interpolation.addItem("Скачком (удерживать)", "hold")
        self.interpolation.setCurrentIndex(
            max(0, self.interpolation.findData(key.interpolation))
        )
        form.addRow("Переход к следующему ключу:", self.interpolation)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_key(self) -> Keyframe:
        value = self.choice.currentData() if self.uses_choice else self.number.value()
        if self.track.parameter in ("mu210_module", "output_address"):
            value = int(value)
        return Keyframe(self.time_spin.value(), value, self.interpolation.currentData())


class KeyMarker(QGraphicsPolygonItem):
    def __init__(
        self, editor: "TimelineWidget", track: AnimationTrack, key: Keyframe, row: int
    ) -> None:
        super().__init__(
            QPolygonF([QPointF(-6, 0), QPointF(0, -6), QPointF(6, 0), QPointF(0, 6)])
        )
        self.editor = editor
        self.track = track
        self.key = key
        self.row = row
        self.setBrush(QColor("#f2ba4d"))
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setToolTip(
            f"{key.time:g} с: {key.value} · {key.interpolation}\nДвойной щелчок — редактировать"
        )
        self.setPos(editor.time_x(key.time), 52 + row * 34)
        self.setZValue(2)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        self.editor.move_selected_markers(self)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        event.accept()
        editor, track, key = self.editor, self.track, self.key
        QTimer.singleShot(0, lambda: editor.edit_key(track, key))

    def itemChange(self, change: Any, value: Any) -> Any:  # noqa: N802
        if change == QGraphicsItem.ItemPositionChange:
            return QPointF(max(self.editor.label_width, value.x()), 52 + self.row * 34)
        return super().itemChange(change, value)


class TimelineView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, editor: "TimelineWidget") -> None:
        super().__init__(scene)
        self.editor = editor

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        position = self.mapToScene(event.pos())
        if (
            not self.editor.locked
            and event.button() == Qt.LeftButton
            and position.y() < 26
            and position.x() >= self.editor.label_width
        ):
            self.editor.set_playhead(
                max(0.0, (position.x() - self.editor.label_width) / self.editor.scale)
            )
            event.accept()
            return
        super().mousePressEvent(event)


class TimelineWidget(QWidget):
    changed = pyqtSignal()
    label_width = 210

    def __init__(
        self, generator: SignalGenerator, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.generator = generator
        self.scenario = Scenario()
        self.scale = 60.0
        self.locked = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        controls = QHBoxLayout()
        self.channel_combo = QComboBox()
        for channel in generator.channels:
            self.channel_combo.addItem(f"{channel.id + 1}: {channel.name}", channel.id)
        self.parameter_combo = QComboBox()
        for parameter, label in PARAMETERS.items():
            self.parameter_combo.addItem(label, parameter)
        for combo in (self.channel_combo, self.parameter_combo):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)
        self.add_track_button = QPushButton("+ Дорожка")
        self.add_track_button.clicked.connect(self.add_track)
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.05, 86400.0)
        self.duration_spin.setDecimals(3)
        self.duration_spin.setSuffix(" с")
        self.duration_spin.valueChanged.connect(self.change_duration)
        for widget in (self.channel_combo, self.parameter_combo, self.add_track_button):
            controls.addWidget(widget)
        controls.addWidget(QLabel("Длительность"))
        controls.addWidget(self.duration_spin)
        layout.addLayout(controls)
        key_controls = QGridLayout()
        self.track_combo = QComboBox()
        self.track_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.track_combo.setMinimumContentsLength(16)
        self.time_spin = QDoubleSpinBox()
        self.time_spin.setRange(0.0, 86400.0)
        self.time_spin.setDecimals(3)
        self.time_spin.setSuffix(" с")
        self.time_spin.valueChanged.connect(self.set_playhead)
        self.add_key_button = QPushButton("+ Ключ")
        self.add_key_button.clicked.connect(self.add_key)
        self.edit_key_button = QPushButton("Изменить ключ")
        self.edit_key_button.clicked.connect(self.edit_selected)
        self.delete_key_button = QPushButton("Удалить ключ")
        self.delete_key_button.clicked.connect(self.delete_selected)
        self.delete_track_button = QPushButton("Удалить дорожку")
        self.delete_track_button.clicked.connect(self.delete_track)
        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(5, 500)
        self.zoom_spin.setValue(int(self.scale))
        self.zoom_spin.setSuffix(" px/с")
        self.zoom_spin.valueChanged.connect(self.change_zoom)
        key_controls.addWidget(self.track_combo, 0, 0, 1, 2)
        key_controls.addWidget(self.time_spin, 0, 2)
        key_controls.addWidget(self.zoom_spin, 0, 3)
        for index, widget in enumerate(
            (
                self.add_key_button,
                self.edit_key_button,
                self.delete_key_button,
                self.delete_track_button,
            )
        ):
            key_controls.addWidget(widget, 1, index)
        layout.addLayout(key_controls)
        self.scene = QGraphicsScene(self)
        self.view = TimelineView(self.scene, self)
        self.view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        layout.addWidget(self.view, 1)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)
        hint = QLabel(
            "Время общее для всех каналов. Ромбы — ключи; перетаскивайте по времени. "
            "Двойной щелчок — значение и переход. Курсор — предпросмотр без вывода."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.playhead = self.scene.addLine(0, 0, 0, 0)
        self.refresh()

    def set_scenario(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.duration_spin.blockSignals(True)
        self.duration_spin.setValue(scenario.timeline_duration)
        self.duration_spin.blockSignals(False)
        self.refresh()

    def time_x(self, time: float) -> float:
        return self.label_width + time * self.scale

    def refresh(self) -> None:
        index = self.track_combo.currentIndex()
        self.track_combo.clear()
        self.scene.clear()
        self.scene.setBackgroundBrush(QColor(COLORS["surface_alt"]))
        duration = max(1.0, self.scenario.get_total_duration())
        width = self.time_x(duration) + 40
        height = max(100, 70 + len(self.scenario.tracks) * 34)
        self.scene.setSceneRect(0, 0, width, height)
        tick_step = max(1.0, duration / 50.0)
        for tick in range(int(duration / tick_step) + 1):
            time = tick * tick_step
            x = self.time_x(time)
            self.scene.addLine(x, 26, x, height, QPen(QColor("#7b8794"), 0.5))
            label = self.scene.addText(f"{time:g} с")
            label.setDefaultTextColor(QColor(COLORS["text"]))
            label.setPos(x - 12, 0)
        for row, track in enumerate(self.scenario.tracks):
            channel = self.generator.get_channel(track.channel_id)
            name = channel.name if channel is not None else str(track.channel_id + 1)
            text = f"{name[:12]} · {PARAMETERS[track.parameter]}"
            self.track_combo.addItem(text)
            label = self.scene.addText(text)
            label.setDefaultTextColor(QColor(COLORS["text"]))
            label.setTextWidth(self.label_width - 8)
            label.setPos(0, 40 + row * 34)
            self.scene.addLine(
                0,
                69 + row * 34,
                width,
                69 + row * 34,
                QPen(QColor(COLORS["border"])),
            )
            for key in track.keyframes:
                self.scene.addItem(KeyMarker(self, track, key, row))
        self.track_combo.setCurrentIndex(
            min(max(0, index), self.track_combo.count() - 1)
        )
        self.playhead = self.scene.addLine(0, 25, 0, height, QPen(QColor("#e34b4b"), 2))
        self.playhead.setZValue(3)
        self.set_playhead(self.time_spin.value())

    def set_playhead(self, time: float) -> None:
        self.time_spin.blockSignals(True)
        self.time_spin.setValue(time)
        self.time_spin.blockSignals(False)
        line = self.playhead.line()
        x = self.time_x(time)
        self.playhead.setLine(x, line.y1(), x, line.y2())
        values = []
        for track in self.scenario.tracks:
            channel = self.generator.get_channel(track.channel_id)
            if channel is None:
                continue
            baseline: Any = getattr(channel, track.parameter)
            if isinstance(baseline, SignalType):
                baseline = baseline.name
            value = track.evaluate(time, baseline)
            if track.parameter == "signal_type":
                value = str(SignalType[value])
            elif track.parameter == "output_device":
                value = device_label(value)
            elif track.parameter == "enabled":
                value = "Включён" if value else "Выключен"
            if isinstance(value, float):
                value = f"{value:g}"
            values.append(f"{channel.name}: {PARAMETERS[track.parameter]} = {value}")
        self.preview.setText(" · ".join(values) or "Добавьте дорожку и ключевые кадры")

    def set_locked(self, locked: bool) -> None:
        self.locked = locked
        self.view.setInteractive(not locked)
        for widget in (
            self.channel_combo,
            self.parameter_combo,
            self.add_track_button,
            self.duration_spin,
            self.add_key_button,
            self.edit_key_button,
            self.delete_key_button,
            self.delete_track_button,
            self.time_spin,
        ):
            widget.setEnabled(not locked)

    def commit(self) -> None:
        self.refresh()
        self.changed.emit()

    def add_track(self) -> None:
        if self.locked or self.channel_combo.currentData() is None:
            return
        target = (self.channel_combo.currentData(), self.parameter_combo.currentData())
        for index, track in enumerate(self.scenario.tracks):
            if (track.channel_id, track.parameter) == target:
                self.track_combo.setCurrentIndex(index)
                return
        self.scenario.tracks.append(AnimationTrack(*target))
        self.commit()
        self.track_combo.setCurrentIndex(len(self.scenario.tracks) - 1)

    def current_track(self) -> Optional[AnimationTrack]:
        index = self.track_combo.currentIndex()
        return (
            self.scenario.tracks[index]
            if 0 <= index < len(self.scenario.tracks)
            else None
        )

    def add_key(self) -> None:
        track = self.current_track()
        if self.locked or track is None:
            return
        channel = self.generator.get_channel(track.channel_id)
        if channel is None:
            return
        baseline = getattr(channel, track.parameter)
        if isinstance(baseline, SignalType):
            baseline = baseline.name
        time = self.time_spin.value()
        key = Keyframe(
            time,
            track.evaluate(time, baseline),
            "hold" if track.parameter in STEP_PARAMETERS else "linear",
        )
        self.edit_key(track, key)

    def edit_key(self, track: AnimationTrack, key: Keyframe) -> None:
        if self.locked:
            return
        dialog = KeyframeDialog(track, key, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        edited = dialog.get_key()
        keys = [item for item in track.keyframes if item is not key]
        keys.append(edited)
        try:
            AnimationTrack(track.channel_id, track.parameter, keys).validate()
        except ValueError as exc:
            QMessageBox.warning(self, "Ключевой кадр", str(exc))
            return
        track.keyframes = keys
        self.commit()

    def move_key(self, track: AnimationTrack, key: Keyframe, time: float) -> None:
        if self.locked:
            return
        previous = key.time
        key.time = time
        try:
            track.validate()
        except ValueError:
            key.time = previous
        QTimer.singleShot(0, self.commit)

    def move_selected_markers(self, marker: KeyMarker) -> None:
        if self.locked:
            return
        markers = [
            item for item in self.scene.selectedItems() if isinstance(item, KeyMarker)
        ]
        if marker not in markers:
            markers.append(marker)
        previous = [(item.key, item.key.time) for item in markers]
        for item in markers:
            item.key.time = round(
                max(0.0, (item.pos().x() - self.label_width) / self.scale), 3
            )
        try:
            for track in self.scenario.tracks:
                track.validate()
        except ValueError:
            for key, time in previous:
                key.time = time
        QTimer.singleShot(0, self.commit)

    def edit_selected(self) -> None:
        for item in self.scene.selectedItems():
            if isinstance(item, KeyMarker):
                self.edit_key(item.track, item.key)
                return

    def delete_selected(self) -> None:
        if self.locked:
            return
        for item in self.scene.selectedItems():
            if isinstance(item, KeyMarker):
                item.track.keyframes.remove(item.key)
        self.commit()

    def delete_track(self) -> None:
        track = self.current_track()
        if not self.locked and track is not None:
            self.scenario.tracks.remove(track)
            self.commit()

    def change_duration(self, duration: float) -> None:
        if not self.locked:
            self.scenario.timeline_duration = duration
            self.commit()

    def change_zoom(self, scale: int) -> None:
        self.scale = float(scale)
        self.refresh()
