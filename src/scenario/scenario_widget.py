import json
import os
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.signal_generator import SignalGenerator
from core.signal_types import SignalType

from .scenario_engine import ScenarioEngine, ScenarioMode
from .scenario_graph import ConnectionItem, ScenarioGraphScene, ScenarioGraphView
from .scenario_model import (
    TRIGGER_ALL,
    TRIGGER_ANY,
    TRIGGER_SPECIFIC,
    Scenario,
    ScenarioStep,
)

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


def format_duration(seconds: float) -> str:
    """Отформатировать длительность сценария без лишней точности."""
    if seconds < 60.0:
        return f"{seconds:g} с"
    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours} ч")
    if minutes:
        parts.append(f"{minutes} мин")
    if remaining_seconds:
        parts.append(f"{remaining_seconds} с")
    return " ".join(parts)


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
        self.engine.active_steps_changed.connect(self.on_active_steps_changed)
        self.engine.progress_changed.connect(self.on_progress_changed)
        self.engine.mode_changed.connect(self.on_mode_changed)

        self.setup_ui()
        self.update_graph()

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

        # Кнопка клонирования шага
        self.clone_step_btn = QPushButton("📋 Клонировать шаг")
        self.clone_step_btn.setToolTip("Клонировать выбранный шаг (Shift+D)")
        self.clone_step_btn.clicked.connect(self.clone_selected_step)
        self.clone_step_btn.setEnabled(False)
        title_layout.addWidget(self.clone_step_btn)

        self.add_step_action = QAction("Добавить шаг", self)
        self.add_step_action.setShortcut(QKeySequence("Shift+A"))
        self.add_step_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.add_step_action.setToolTip("Добавить шаг (Shift+A)")
        self.add_step_action.triggered.connect(self.add_step)
        self.addAction(self.add_step_action)

        self.clone_step_action = QAction("Клонировать шаг", self)
        self.clone_step_action.setShortcut(QKeySequence("Shift+D"))
        self.clone_step_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.clone_step_action.setToolTip("Клонировать выбранный шаг (Shift+D)")
        self.clone_step_action.triggered.connect(self.clone_selected_step)
        self.addAction(self.clone_step_action)

        self.trigger_btn = QPushButton("◉ Условие запуска")
        self.trigger_btn.setToolTip(
            "Настроить запуск выбранного блока при нескольких входящих связях"
        )
        self.trigger_btn.clicked.connect(self.configure_selected_trigger)
        title_layout.addWidget(self.trigger_btn)

        self.delete_btn = QPushButton("✕ Удалить")
        self.delete_btn.setToolTip("Удалить выбранный блок или выбранную связь")
        self.delete_btn.clicked.connect(self.delete_selected_step)
        title_layout.addWidget(self.delete_btn)

        settings_menu = QMenu(self)
        settings_menu.addAction(self.add_step_action)
        settings_menu.addAction(self.clone_step_action)

        self.settings_btn = QToolButton()
        self.settings_btn.setText("Настройки ▾")
        self.settings_btn.setToolTip("Действия и сочетания клавиш сценария")
        self.settings_btn.setPopupMode(QToolButton.InstantPopup)
        self.settings_btn.setMenu(settings_menu)
        title_layout.addWidget(self.settings_btn)

        layout.addLayout(title_layout)

        hint = QLabel(
            "Связь: перетащите линию от зелёного выхода к синему входу. "
            "Двойной щелчок по блоку — редактирование. Колесо мыши — масштаб. "
            "Shift+D — клонировать выбранный шаг."
        )
        hint.setObjectName("secondaryText")
        layout.addWidget(hint)

        self.graph_scene = ScenarioGraphScene(self)
        self.graph_scene.edit_requested.connect(self.edit_step_by_id)
        self.graph_scene.connection_requested.connect(self.add_connection)
        self.graph_scene.graph_changed.connect(self._emit_scenario_changed)
        self.graph_scene.selectionChanged.connect(self._on_selection_changed)
        self.graph_view = ScenarioGraphView(self.graph_scene, self)
        layout.addWidget(self.graph_view, stretch=1)

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
        self.steps_count_label.setStyleSheet(
            "color: #46515c; font-size: 10pt; font-weight: 600;"
        )
        status_layout.addWidget(self.steps_count_label)

        status_layout.addStretch()

        self.status_label = QLabel("Режим: Ручной")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 8px;")
        status_layout.addWidget(self.status_label)

        layout.addLayout(status_layout)

    def _on_selection_changed(self):
        """Обновить состояние кнопки клонирования при изменении выделения."""
        selected = [
            item.step
            for item in self.graph_scene.selectedItems()
            if hasattr(item, "step")
        ]
        self.clone_step_btn.setEnabled(len(selected) == 1)
        self.clone_step_action.setEnabled(len(selected) == 1)

    def update_graph(self) -> None:
        """Перестроить графическое представление сценария."""
        self.graph_scene.set_scenario(self.scenario)
        step_count = format_step_count(len(self.scenario.steps))
        total_duration = format_duration(self.scenario.get_total_duration())
        self.steps_count_label.setText(f"{step_count} · Общее время: {total_duration}")
        self.scenario_changed.emit(self.scenario)
        self._on_selection_changed()

    def _emit_scenario_changed(self) -> None:
        self.scenario_changed.emit(self.scenario)

    def add_step(self):
        """Добавить новый шаг"""
        dialog = StepEditDialog(self.generator, self)
        if dialog.exec_() == QDialog.Accepted:
            step = dialog.get_step()
            if step:
                step.position_x = float((len(self.scenario.steps) % 4) * 250)
                step.position_y = float((len(self.scenario.steps) // 4) * 170)
                self.scenario.steps.append(step)
                self.update_graph()
                self._log_change(
                    f"Добавлен шаг {self._step_number(step.id)}: {describe_step(step)}",
                    "success",
                )

    def clone_selected_step(self):
        """Клонировать выбранный шаг."""
        selected = [
            item.step
            for item in self.graph_scene.selectedItems()
            if hasattr(item, "step")
        ]
        if not selected:
            QMessageBox.information(self, "Выбор шага", "Сначала выберите шаг для клонирования")
            return
        
        source_step = selected[0]
        
        # Создаём копию шага с новым ID и смещённой позицией
        import copy
        import uuid
        
        new_step = copy.deepcopy(source_step)
        new_step.id = uuid.uuid4().hex
        new_step.position_x = source_step.position_x + 30
        new_step.position_y = source_step.position_y + 30
        
        # Добавляем новый шаг в сценарий
        self.scenario.steps.append(new_step)
        
        # Если были связи, копируем их (но только если источник не был стартовым)
        # Для простоты — не копируем связи, пользователь может добавить их вручную
        # или через перетаскивание
        
        self.update_graph()
        self._log_change(
            f"Клонирован шаг {self._step_number(source_step.id)} → "
            f"{self._step_number(new_step.id)}: {describe_step(new_step)}",
            "success",
        )
        
        # Выделяем новый шаг
        for item in self.graph_scene.items():
            if hasattr(item, "step") and item.step.id == new_step.id:
                item.setSelected(True)
                break

    def edit_step(self, index: int) -> None:
        """Редактировать шаг"""
        if 0 <= index < len(self.scenario.steps):
            dialog = StepEditDialog(self.generator, self, self.scenario.steps[index])
            if dialog.exec_() == QDialog.Accepted:
                step = dialog.get_step()
                if step:
                    self.scenario.steps[index] = step
                    self.update_graph()
                    self._log_change(
                        f"Изменён шаг {self._step_number(step.id)}: {describe_step(step)}",
                        "info",
                    )

    def edit_step_by_id(self, step_id: str) -> None:
        for index, step in enumerate(self.scenario.steps):
            if step.id == step_id:
                self.edit_step(index)
                return

    def delete_selected_step(self) -> None:
        selected_connections = [
            item
            for item in self.graph_scene.selectedItems()
            if isinstance(item, ConnectionItem)
        ]
        if selected_connections:
            item = selected_connections[0]
            source_number = item.source.number
            target_number = item.target.number
            self.scenario.connections = [
                connection
                for connection in self.scenario.connections
                if not (
                    connection.source_id == item.source.step.id
                    and connection.target_id == item.target.step.id
                )
            ]
            self.update_graph()
            self._log_change(
                f"Удалена связь: шаг {source_number} → шаг {target_number}",
                "warning",
            )
            return
        selected = [
            item.step.id
            for item in self.graph_scene.selectedItems()
            if hasattr(item, "step")
        ]
        if not selected:
            QMessageBox.information(self, "Выбор блока", "Сначала выберите блок")
            return
        self.delete_step_by_id(selected[0])

    def delete_step_by_id(self, step_id: str) -> None:
        for index, step in enumerate(self.scenario.steps):
            if step.id == step_id:
                self.delete_step(index)
                return

    def delete_step(self, index: int) -> None:
        """Удалить шаг"""
        if 0 <= index < len(self.scenario.steps):
            step_label = self._step_number(self.scenario.steps[index].id)
            reply = QMessageBox.question(
                self,
                "Подтверждение",
                f"Удалить шаг {step_label}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                removed_step = self.scenario.steps[index]
                self.scenario.remove_step(removed_step.id)
                self.update_graph()
                self._log_change(
                    f"Удалён шаг {step_label}: {describe_step(removed_step)}",
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
            self.scenario.connections.clear()
            self.update_graph()
            self._log_change(
                f"Очищен сценарий: удалено шагов — {removed_count}", "warning"
            )

    def add_connection(self, source_id: str, target_id: str) -> None:
        try:
            before = len(self.scenario.connections)
            self.scenario.add_connection(source_id, target_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Нельзя создать связь", str(exc))
            self._log_change(f"Связь не создана: {exc}", "warning")
            return
        if len(self.scenario.connections) == before:
            return
        self.update_graph()
        source_number = self._step_number(source_id)
        target_number = self._step_number(target_id)
        self._log_change(
            f"Создана связь: шаг {source_number} → шаг {target_number}", "success"
        )

    def _step_number(self, step_id: str) -> str:
        return self.scenario.get_step_label(step_id)

    def _step_index(self, step_id: str) -> int:
        return next(
            index
            for index, step in enumerate(self.scenario.steps)
            if step.id == step_id
        )

    def configure_selected_trigger(self) -> None:
        selected = [
            item.step
            for item in self.graph_scene.selectedItems()
            if hasattr(item, "step")
        ]
        if not selected:
            QMessageBox.information(self, "Выбор блока", "Сначала выберите блок")
            return
        step = selected[0]
        incoming = self.scenario.incoming_ids(step.id)
        if len(incoming) < 2:
            QMessageBox.information(
                self,
                "Условие запуска",
                "Настройка нужна блоку как минимум с двумя входящими связями.",
            )
            return

        options = [
            "После завершения всех входящих шагов",
            "После любого входящего шага",
        ]
        source_by_option = {}
        for source_id in sorted(incoming, key=self._step_index):
            option = f"После завершения шага {self._step_number(source_id)}"
            options.append(option)
            source_by_option[option] = source_id
        choice, accepted = QInputDialog.getItem(
            self,
            "Условие запуска",
            "Когда запускать выбранный блок:",
            options,
            0,
            False,
        )
        if not accepted:
            return
        if choice == options[0]:
            step.trigger_mode = TRIGGER_ALL
            step.trigger_step_id = None
        elif choice == options[1]:
            step.trigger_mode = TRIGGER_ANY
            step.trigger_step_id = None
        else:
            step.trigger_mode = TRIGGER_SPECIFIC
            step.trigger_step_id = source_by_option[choice]
        self.update_graph()
        self._log_change(
            f"Для шага {self._step_number(step.id)} задано условие: {choice.lower()}",
            "info",
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

    def on_active_steps_changed(self, labels: str) -> None:
        if not labels:
            return
        if "," in labels:
            self.status_label.setText(f"Выполняются шаги {labels}")
        else:
            self.status_label.setText(f"Выполняется шаг {labels}")

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
                self.update_graph()
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

        # Нарастание (не реализовано)
        self.ramp_up_spin = QDoubleSpinBox()
        self.ramp_up_spin.setRange(0, 60)
        self.ramp_up_spin.setValue(self.step.ramp_up)
        self.ramp_up_spin.setSuffix(" с")
        self.ramp_up_spin.setEnabled(False)
        self.ramp_up_spin.setToolTip("Плавное нарастание пока не реализовано")
        form_layout.addRow("Нарастание (не реализовано):", self.ramp_up_spin)

        # Затухание (не реализовано)
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
            id=self.step.id,
            channel_id=self.channel_combo.currentData(),
            signal_type=self.type_combo.currentData(),
            amplitude=self.amp_spin.value(),
            frequency=self.freq_spin.value(),
            offset=self.offset_spin.value(),
            duration=self.duration_spin.value(),
            ramp_up=self.ramp_up_spin.value(),
            ramp_down=self.ramp_down_spin.value(),
            position_x=self.step.position_x,
            position_y=self.step.position_y,
            trigger_mode=self.step.trigger_mode,
            trigger_step_id=self.step.trigger_step_id,
        )
