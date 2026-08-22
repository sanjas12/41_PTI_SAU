import json
import os
from typing import Optional

from PyQt5.QtCore import QMimeData, Qt, pyqtSignal
from PyQt5.QtGui import QDrag, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.signal_generator import SignalGenerator
from core.signal_types import SignalType

from .scenario_engine import ScenarioEngine, ScenarioMode
from .scenario_model import Scenario, ScenarioStep

SIGNAL_TYPE_NAMES = {
    "Sine": "Синус",
    "Square": "Меандр",
    "Sawtooth": "Пилообразный",
    "Triangle": "Треугольный",
    "Random": "Случайный",
    "Custom": "Пользовательский",
}


def describe_step(step: ScenarioStep) -> str:
    """Вернуть краткое понятное описание шага для UI и журнала."""
    signal_name = SIGNAL_TYPE_NAMES.get(step.signal_type, step.signal_type)
    return (
        f"канал {step.channel_id + 1}, {signal_name}, "
        f"A={step.amplitude:g} %, f={step.frequency:g} Гц, "
        f"смещение={step.offset:g} %, {step.duration:g} с"
    )


def format_step_count(count: int) -> str:
    """Согласовать слово «шаг» с количеством."""
    if count % 10 == 1 and count % 100 != 11:
        suffix = "шаг"
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        suffix = "шага"
    else:
        suffix = "шагов"
    return f"{count} {suffix}"


class StepWidget(QFrame):
    """Виджет для отображения шага сценария (drag&drop)"""

    edit_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    move_requested = pyqtSignal(int, int)

    def __init__(self, step_index: int, step: ScenarioStep, parent=None):
        super().__init__(parent)
        self.step_index = step_index
        self.step = step
        self.setup_ui()
        self.setAcceptDrops(True)

    def setup_ui(self):
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 2px;
                margin: 1px;
            }
            QFrame:hover {
                background-color: #e8f5e9;
                border: 2px solid #4CAF50;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(3)

        # Номер шага
        self.number_label = QLabel(f"Шаг {self.step_index + 1}")
        self.number_label.setStyleSheet(
            "font-weight: bold; color: #666; min-width: 25px; font-size: 8px;"
        )
        layout.addWidget(self.number_label)

        # Информация о канале
        channel_info = f"Канал {self.step.channel_id + 1}"
        self.channel_label = QLabel(channel_info)
        self.channel_label.setStyleSheet(
            "font-weight: bold; min-width: 25px; font-size: 8px;"
        )
        layout.addWidget(self.channel_label)

        # Тип сигнала
        type_color = {
            "Sine": "#2196F3",
            "Square": "#f44336",
            "Sawtooth": "#FF9800",
            "Triangle": "#4CAF50",
            "Random": "#9C27B0",
            "Custom": "#795548",
        }.get(self.step.signal_type, "#666666")

        signal_name = SIGNAL_TYPE_NAMES.get(
            self.step.signal_type, self.step.signal_type
        )
        self.type_label = QLabel(signal_name)
        self.type_label.setStyleSheet(
            f"color: {type_color}; font-weight: bold; min-width: 30px; font-size: 8px;"
        )
        layout.addWidget(self.type_label)

        # Длительность
        duration = f"{self.step.duration:g} с"
        self.duration_label = QLabel(duration)
        self.duration_label.setStyleSheet(
            "color: #666; min-width: 25px; font-size: 8px;"
        )
        layout.addWidget(self.duration_label)

        parameters = QLabel(
            f"A {self.step.amplitude:g} % · f {self.step.frequency:g} Гц · "
            f"смещение {self.step.offset:g} %"
        )
        parameters.setObjectName("secondaryText")
        layout.addWidget(parameters)

        layout.addStretch()

        # Кнопка удаления
        self.delete_btn = QPushButton("✕")
        self.delete_btn.setFixedSize(16, 16)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 8px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_step)
        layout.addWidget(self.delete_btn)

        self.setLayout(layout)
        self.setMinimumHeight(32)
        self.setMaximumHeight(38)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(str(self.step_index))
            drag.setMimeData(mime_data)

            pixmap = QPixmap(self.size())
            self.render(pixmap)
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())

            drag.exec_(Qt.MoveAction)

    def contextMenuEvent(self, event):  # noqa: N802
        menu = QMenu()

        edit_action = QAction("✏️ Редактировать", self)
        edit_action.triggered.connect(self.edit_step)
        menu.addAction(edit_action)

        delete_action = QAction("🗑 Удалить", self)
        delete_action.triggered.connect(self.delete_step)
        menu.addAction(delete_action)

        menu.addSeparator()

        move_up = QAction("⬆ Вверх", self)
        move_up.triggered.connect(self.move_up)
        menu.addAction(move_up)

        move_down = QAction("⬇ Вниз", self)
        move_down.triggered.connect(self.move_down)
        menu.addAction(move_down)

        menu.exec_(event.globalPos())

    def edit_step(self):
        self.edit_requested.emit(self.step_index)

    def delete_step(self):
        self.delete_requested.emit(self.step_index)

    def move_up(self):
        self.move_requested.emit(self.step_index, -1)

    def move_down(self):
        self.move_requested.emit(self.step_index, 1)


class ScenarioWidget(QWidget):
    """Виджет конструктора сценариев"""

    scenario_changed = pyqtSignal(object)
    scenario_saved = pyqtSignal(str)

    def __init__(self, generator: SignalGenerator, engine: ScenarioEngine, parent=None):
        super().__init__(parent)

        self.generator = generator
        self.engine = engine
        self.scenario = Scenario()
        self.current_file = None

        # Подключаем сигналы двигателя
        self.engine.scenario_started.connect(self.on_scenario_started)
        self.engine.scenario_stopped.connect(self.on_scenario_stopped)
        self.engine.scenario_finished.connect(self.on_scenario_finished)
        self.engine.step_changed.connect(self.on_step_changed)
        self.engine.progress_changed.connect(self.on_progress_changed)
        self.engine.mode_changed.connect(self.on_mode_changed)

        self.setup_ui()
        self.update_step_list()

    def _log_change(self, message: str, level: str = "info") -> None:
        """Передать событие редактора в общий журнал приложения."""
        self.engine.log_signal.emit(message, level)

    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.setLayout(layout)

        # Минимальная высота задаётся, максимальная — нет: реальная высота
        # теперь управляется вертикальным QSplitter в MainWindow.
        self.setMinimumHeight(150)

        # Заголовок
        title_layout = QHBoxLayout()
        title_layout.setSpacing(3)

        title = QLabel("Редактор сценария")
        title.setStyleSheet("font-size: 10px; font-weight: bold;")
        title_layout.addWidget(title)

        title_layout.addStretch()

        # Кнопка добавления шага
        self.add_step_btn = QPushButton("＋ Добавить шаг")
        self.add_step_btn.setToolTip("Добавить новый шаг в конец сценария")
        self.add_step_btn.clicked.connect(self.add_step)
        title_layout.addWidget(self.add_step_btn)

        layout.addLayout(title_layout)

        # Список шагов
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout()
        self.steps_layout.setSpacing(1)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_container.setLayout(self.steps_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(100)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: white;
            }
        """)
        scroll.setWidget(self.steps_container)
        layout.addWidget(scroll, stretch=1)

        # Нижняя панель
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(3)

        # Play/Stop/Пауза/прогресс переехали в общий ControlPanel — эти
        # кнопки теперь работают и для ручного режима, и для сценария,
        # в зависимости от того, какая вкладка выбрана в MainWindow.
        # Здесь остаются только специфичные для конструктора сценария
        # действия: сохранить/загрузить сценарий в файл.
        self.save_btn = QPushButton("💾  Сохранить в файл")
        self.save_btn.setToolTip("Сохранить текущий сценарий в JSON-файл")
        self.save_btn.clicked.connect(self.save_scenario)
        bottom_layout.addWidget(self.save_btn)

        self.load_btn = QPushButton("📂  Загрузить из файла")
        self.load_btn.setToolTip("Загрузить сценарий из JSON-файла")
        self.load_btn.clicked.connect(self.load_scenario)
        bottom_layout.addWidget(self.load_btn)

        self.clear_btn = QPushButton("🗑  Очистить шаги")
        self.clear_btn.setToolTip("Удалить все шаги текущего сценария")
        self.clear_btn.clicked.connect(self.clear_steps)
        bottom_layout.addWidget(self.clear_btn)

        bottom_layout.addStretch()

        layout.addLayout(bottom_layout)

        # Статус
        status_layout = QHBoxLayout()
        status_layout.setSpacing(5)

        self.steps_count_label = QLabel("0 шагов")
        self.steps_count_label.setStyleSheet("color: #666; font-size: 8px;")
        status_layout.addWidget(self.steps_count_label)

        status_layout.addStretch()

        self.status_label = QLabel("Режим: Ручной")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 8px;")
        status_layout.addWidget(self.status_label)

        layout.addLayout(status_layout)

    def update_step_list(self):
        """Обновить список шагов"""
        # Очищаем контейнер
        for i in reversed(range(self.steps_layout.count())):
            widget = self.steps_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Добавляем шаги
        for i, step in enumerate(self.scenario.steps):
            step_widget = StepWidget(i, step, self)
            step_widget.edit_requested.connect(self.edit_step)
            step_widget.delete_requested.connect(self.delete_step)
            step_widget.move_requested.connect(self.move_step)
            self.steps_layout.addWidget(step_widget)

        if not self.scenario.steps:
            empty_label = QLabel(
                "Сценарий пока пуст. Нажмите «Добавить шаг», чтобы настроить "
                "первое действие."
            )
            empty_label.setObjectName("secondaryText")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setWordWrap(True)
            self.steps_layout.addWidget(empty_label)

        # Обновляем информацию
        self.steps_count_label.setText(format_step_count(len(self.scenario.steps)))

        # Отправляем сигнал об изменении
        self.scenario_changed.emit(self.scenario)

    def add_step(self):
        """Добавить новый шаг"""
        dialog = StepEditDialog(self.generator, self)
        if dialog.exec_() == QDialog.Accepted:
            step = dialog.get_step()
            if step:
                self.scenario.steps.append(step)
                self.update_step_list()
                self._log_change(
                    f"Добавлен шаг {len(self.scenario.steps)}: {describe_step(step)}",
                    "success",
                )

    def edit_step(self, index: int):
        """Редактировать шаг"""
        if 0 <= index < len(self.scenario.steps):
            dialog = StepEditDialog(self.generator, self, self.scenario.steps[index])
            if dialog.exec_() == QDialog.Accepted:
                step = dialog.get_step()
                if step:
                    self.scenario.steps[index] = step
                    self.update_step_list()
                    self._log_change(
                        f"Изменён шаг {index + 1}: {describe_step(step)}",
                        "info",
                    )

    def delete_step(self, index: int):
        """Удалить шаг"""
        if 0 <= index < len(self.scenario.steps):
            reply = QMessageBox.question(
                self,
                "Подтверждение",
                f"Удалить шаг #{index + 1}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                removed_step = self.scenario.steps.pop(index)
                self.update_step_list()
                self._log_change(
                    f"Удалён шаг {index + 1}: {describe_step(removed_step)}",
                    "warning",
                )

    def clear_steps(self):
        """Очистить все шаги"""
        if not self.scenario.steps:
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Очистить все шаги?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            removed_count = len(self.scenario.steps)
            self.scenario.steps.clear()
            self.update_step_list()
            self._log_change(
                f"Очищен сценарий: удалено шагов — {removed_count}", "warning"
            )

    def move_step(self, index: int, direction: int):
        """Переместить шаг"""
        new_index = index + direction
        if 0 <= new_index < len(self.scenario.steps):
            self.scenario.steps[index], self.scenario.steps[new_index] = (
                self.scenario.steps[new_index],
                self.scenario.steps[index],
            )
            self.update_step_list()
            self._log_change(
                f"Шаг {index + 1} перемещён на позицию {new_index + 1}", "info"
            )

    def play_scenario(self):
        """Запустить сценарий"""
        if not self.scenario.steps:
            QMessageBox.warning(self, "Предупреждение", "Сценарий пуст!")
            return

        self.engine.load_scenario(self.scenario)
        self.engine.start_scenario()

    def stop_scenario(self):
        """Остановить сценарий"""
        self.engine.stop_scenario()

    def pause_scenario(self):
        """Пауза сценария"""
        if self.engine.mode == ScenarioMode.SCENARIO:
            self.engine.pause_scenario()
        else:
            self.engine.resume_scenario()

    def switch_mode(self):
        """Переключить режим"""
        if self.engine.mode == ScenarioMode.MANUAL:
            self.engine.start_scenario()
        else:
            self.engine.set_manual_mode()

    def set_engine_mode(self, target_mode: str) -> bool:
        """Явно перевести движок в нужный режим (используется внешним
        переключателем режима в MainWindow — сегментированным тумблером
        Ручной/Сценарий).

        В отличие от switch_mode() (просто переключает на противоположный),
        этот метод идемпотентен и проверяет осмысленность перехода:
        нельзя войти в режим сценария, если сценарий пуст.

        Возвращает True, если переход выполнен (или уже был в нужном
        состоянии), False — если переход отклонён.
        """
        if target_mode == "scenario":
            if self.engine.mode == ScenarioMode.SCENARIO:
                return True
            if not self.scenario.steps:
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    "Сценарий пуст — добавьте хотя бы один шаг, прежде чем переключаться в этот режим.",
                )
                return False
            self.play_scenario()
            return True
        elif target_mode == "manual":
            if self.engine.mode == ScenarioMode.MANUAL:
                return True
            self.stop_scenario()
            self.engine.set_manual_mode()
            return True
        return False

    def on_scenario_started(self, name: str):
        self.status_label.setText(f"Выполняется: {name[:15]}")
        self.status_label.setStyleSheet(
            "color: #4CAF50; font-weight: bold; font-size: 8px;"
        )

    def on_scenario_stopped(self):
        self.status_label.setText("Остановлен")
        self.status_label.setStyleSheet("color: #f44336; font-size: 8px;")

    def on_scenario_finished(self):
        self.status_label.setText("Завершен")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 8px;")

    def on_step_changed(self, current: int, total: int):
        if current > 0:
            self.status_label.setText(f"Выполняется шаг {current} из {total}")

    def on_progress_changed(self, progress: float):
        # Прогресс-бар теперь в ControlPanel — MainWindow подписан на
        # тот же сигнал engine.progress_changed напрямую.
        pass

    def on_mode_changed(self, mode: str):
        if mode == "manual":
            self.status_label.setText("Режим: Ручной")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 8px;")
        elif mode == "scenario":
            self.status_label.setText("Режим: Сценарий")
            self.status_label.setStyleSheet("color: #FF9800; font-size: 8px;")
        elif mode == "paused":
            self.status_label.setText("Режим: Пауза")
            self.status_label.setStyleSheet("color: #2196F3; font-size: 8px;")

    def save_scenario(self):
        if not self.scenario.steps:
            message = "Нельзя сохранить сценарий без шагов"
            QMessageBox.warning(self, "Сценарий пуст", message)
            self._log_change(message, "warning")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить сценарий",
            f"{self.scenario.name}.json",
            "JSON files (*.json)",
        )

        if filepath:
            try:
                self.scenario.save_to_file(filepath)
                self.current_file = filepath
                self.scenario_saved.emit(filepath)
                self._log_change(
                    f"Сценарий сохранён: {os.path.basename(filepath)} "
                    f"({format_step_count(len(self.scenario.steps))})",
                    "success",
                )
                QMessageBox.information(self, "Сценарий сохранён", f"Файл:\n{filepath}")
            except (OSError, TypeError, ValueError) as exc:
                self._log_change(f"Ошибка сохранения сценария: {exc}", "error")
                QMessageBox.critical(
                    self, "Ошибка сохранения", f"Не удалось сохранить сценарий:\n{exc}"
                )

    def load_scenario(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Загрузить сценарий", "", "JSON files (*.json)"
        )

        if filepath:
            try:
                self.scenario = Scenario.load_from_file(filepath)
                self.current_file = filepath
                self.update_step_list()
                self._log_change(
                    f"Сценарий загружен: {os.path.basename(filepath)} "
                    f"({format_step_count(len(self.scenario.steps))})",
                    "success",
                )
                QMessageBox.information(self, "Сценарий загружен", f"Файл:\n{filepath}")
            except (
                OSError,
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                self._log_change(f"Ошибка загрузки сценария: {exc}", "error")
                QMessageBox.critical(
                    self, "Ошибка загрузки", f"Не удалось загрузить сценарий:\n{exc}"
                )


class StepEditDialog(QDialog):
    """Диалог редактирования шага"""

    def __init__(
        self,
        generator: SignalGenerator,
        parent=None,
        step: Optional[ScenarioStep] = None,
    ):
        super().__init__(parent)
        self.generator = generator
        self.step = step or ScenarioStep(channel_id=0, signal_type="Sine")
        self.setWindowTitle("Редактирование шага" if step else "Добавление шага")
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        form_layout = QFormLayout()
        form_layout.setSpacing(5)

        # Канал
        self.channel_combo = QComboBox()
        for channel in self.generator.channels:
            self.channel_combo.addItem(
                f"Канал {channel.id + 1}: {channel.name}", channel.id
            )
        if self.step:
            index = self.channel_combo.findData(self.step.channel_id)
            if index >= 0:
                self.channel_combo.setCurrentIndex(index)
        form_layout.addRow("Канал:", self.channel_combo)

        # Тип сигнала
        self.type_combo = QComboBox()
        for signal_type in SignalType:
            serialized_name = signal_type.name.capitalize()
            display_name = SIGNAL_TYPE_NAMES.get(serialized_name, serialized_name)
            self.type_combo.addItem(display_name, serialized_name)
        if self.step:
            index = self.type_combo.findData(self.step.signal_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
        form_layout.addRow("Тип сигнала:", self.type_combo)

        # Амплитуда
        self.amp_spin = QDoubleSpinBox()
        self.amp_spin.setRange(0, 100)
        self.amp_spin.setValue(self.step.amplitude)
        self.amp_spin.setSuffix(" %")
        form_layout.addRow("Амплитуда:", self.amp_spin)

        # Частота
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.01, 100)
        self.freq_spin.setValue(self.step.frequency)
        self.freq_spin.setSuffix(" Гц")
        form_layout.addRow("Частота:", self.freq_spin)

        # Смещение относительно центра диапазона канала
        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-100, 100)
        self.offset_spin.setValue(self.step.offset)
        self.offset_spin.setSuffix(" %")
        form_layout.addRow("Смещение:", self.offset_spin)

        # Длительность
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 3600)
        self.duration_spin.setValue(self.step.duration)
        self.duration_spin.setSuffix(" с")
        form_layout.addRow("Длительность:", self.duration_spin)

        # Нарастание
        self.ramp_up_spin = QDoubleSpinBox()
        self.ramp_up_spin.setRange(0, 60)
        self.ramp_up_spin.setValue(self.step.ramp_up)
        self.ramp_up_spin.setSuffix(" с")
        self.ramp_up_spin.setEnabled(False)
        self.ramp_up_spin.setToolTip("Плавное нарастание пока не реализовано")
        form_layout.addRow("Нарастание (не реализовано):", self.ramp_up_spin)

        # Затухание
        self.ramp_down_spin = QDoubleSpinBox()
        self.ramp_down_spin.setRange(0, 60)
        self.ramp_down_spin.setValue(self.step.ramp_down)
        self.ramp_down_spin.setSuffix(" с")
        self.ramp_down_spin.setEnabled(False)
        self.ramp_down_spin.setToolTip("Плавное затухание пока не реализовано")
        form_layout.addRow("Затухание (не реализовано):", self.ramp_down_spin)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("Применить")
        button_box.button(QDialogButtonBox.Cancel).setText("Отмена")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setMinimumWidth(300)

    def get_step(self) -> ScenarioStep:
        return ScenarioStep(
            channel_id=self.channel_combo.currentData(),
            signal_type=self.type_combo.currentData(),
            amplitude=self.amp_spin.value(),
            frequency=self.freq_spin.value(),
            offset=self.offset_spin.value(),
            duration=self.duration_spin.value(),
            ramp_up=self.ramp_up_spin.value(),
            ramp_down=self.ramp_down_spin.value(),
        )
