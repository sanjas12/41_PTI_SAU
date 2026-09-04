from enum import Enum
from typing import Dict, List, Optional, Set

from PyQt5.QtCore import QMutex, QMutexLocker, QObject, QTimer, pyqtSignal

from core.signal_generator import SignalGenerator
from core.signal_types import SignalType

from .scenario_model import TRIGGER_ANY, TRIGGER_SPECIFIC, Scenario, ScenarioStep


class ScenarioMode(Enum):
    """Режимы работы"""

    MANUAL = "manual"  # Ручной режим
    SCENARIO = "scenario"  # Режим сценария
    PAUSED = "paused"  # Приостановлен


class ScenarioEngine(QObject):
    """Движок воспроизведения сценариев"""

    # Сигналы
    mode_changed = pyqtSignal(str)  # Изменение режима
    step_changed = pyqtSignal(int, int)  # (current_step, total_steps)
    progress_changed = pyqtSignal(float)  # Прогресс в процентах
    time_updated = pyqtSignal(float)  # Текущее время сценария
    scenario_started = pyqtSignal(str)  # Запущен сценарий
    scenario_stopped = pyqtSignal()  # Остановлен сценарий
    scenario_finished = pyqtSignal()  # Завершен сценарий
    active_steps_changed = pyqtSignal(str)  # Отображаемые номера активных блоков
    log_signal = pyqtSignal(str, str)  # (message, level)

    def __init__(self, generator: SignalGenerator, parent=None):
        super().__init__(parent)
        self.generator = generator
        self.scenario: Optional[Scenario] = None
        self.mode = ScenarioMode.MANUAL

        self._current_step = 0
        self._step_time = 0.0
        self._scenario_time = 0.0
        self._is_running = False
        self._mutex = QMutex()

        # Кэш для оригинальных настроек каналов
        self._original_channel_configs: Dict[int, dict] = {}

        # Таймер обновления
        self.timer = QTimer()
        self.timer.timeout.connect(self._update)
        self.timer.setInterval(50)  # 50ms

        # Флаг, что сценарий активен
        self._scenario_active = False
        self._active_steps: Dict[str, float] = {}
        self._started_steps: Set[str] = set()
        self._completed_steps: Set[str] = set()

        # Данные для плавного перехода (ramp)
        self._ramp_data: Dict[int, dict] = {}

    def load_scenario(self, scenario: Scenario):
        """Загрузить сценарий"""
        with QMutexLocker(self._mutex):
            self.scenario = scenario
            self._current_step = 0
            self._step_time = 0.0
            self._scenario_time = 0.0
            self._ramp_data.clear()
            self._active_steps.clear()
            self._started_steps.clear()
            self._completed_steps.clear()

            if scenario:
                self.log_signal.emit(f"Загружен сценарий: {scenario.name}", "info")
                self.step_changed.emit(0, len(scenario.steps))

    def start_scenario(self):
        """Запустить сценарий"""
        if not self.scenario or not self.scenario.steps:
            self.log_signal.emit("Сценарий пуст!", "warning")
            return

        with QMutexLocker(self._mutex):
            # Сохраняем текущие настройки каналов
            self._save_channel_configs()

            # НЕ СБРАСЫВАЕМ ВСЕ КАНАЛЫ — время должно идти с 0 только для тех,
            # у кого есть шаги, но они будут обнулены в _apply_graph_step
            # for channel in self.generator.channels:
            #     channel.time = 0.0  ← УДАЛЯЕМ
            #     channel.current_value = 0.0

            # Останавливаем ручную генерацию
            self.mode = ScenarioMode.SCENARIO
            self._is_running = True
            self._step_time = 0.0
            self._scenario_time = 0.0
            self._active_steps.clear()
            self._started_steps.clear()
            self._completed_steps.clear()

            self._start_ready_steps()
            if not self._active_steps:
                self.log_signal.emit(
                    "Сценарий не содержит стартового блока или содержит цикл",
                    "error",
                )
                self._is_running = False
                self.mode = ScenarioMode.MANUAL
                self._restore_channel_configs()
                return

            # Запускаем таймер
            self.timer.start()

            self.mode_changed.emit("scenario")
            self.scenario_started.emit(self.scenario.name)
            self.step_changed.emit(0, len(self.scenario.steps))
            self._emit_active_steps()
            self.log_signal.emit(f"Запущен сценарий: {self.scenario.name}", "success")

    def stop_scenario(self):
        """Остановить сценарий"""
        with QMutexLocker(self._mutex):
            self._is_running = False
            self.timer.stop()

            # Восстанавливаем настройки каналов
            self._restore_channel_configs()

            # Включаем все каналы обратно
            for channel in self.generator.channels:
                channel.enabled = True
                # Сбрасываем время для корректной генерации
                channel.time = 0

            self.mode = ScenarioMode.MANUAL
            self.mode_changed.emit("manual")
            self.scenario_stopped.emit()
            self.log_signal.emit("Сценарий остановлен, каналы восстановлены", "info")

    def pause_scenario(self):
        """Приостановить сценарий"""
        if self._is_running and self.mode == ScenarioMode.SCENARIO:
            self.mode = ScenarioMode.PAUSED
            self.timer.stop()
            self.mode_changed.emit("paused")
            self.log_signal.emit("Сценарий приостановлен", "info")

    def resume_scenario(self):
        """Возобновить сценарий"""
        if self.mode == ScenarioMode.PAUSED:
            self.mode = ScenarioMode.SCENARIO
            self.timer.start()
            self.mode_changed.emit("scenario")
            self.log_signal.emit("Сценарий возобновлен", "info")

    def _save_channel_configs(self):
        """Сохранить текущие настройки каналов"""
        self._original_channel_configs.clear()
        for channel in self.generator.channels:
            self._original_channel_configs[channel.id] = {
                "enabled": channel.enabled,
                "signal_type": channel.signal_type,
                "frequency": channel.frequency,
                "amplitude": channel.amplitude,
                "offset": channel.offset,
                "duty_cycle": channel.duty_cycle,
                "pulse_width": channel.pulse_width,
                "min_value": channel.min_value,
                "max_value": channel.max_value,
                "mu210_module": channel.mu210_module,
                "mu210_register": channel.mu210_register,
            }

    def _restore_channel_configs(self):
        """Восстановить настройки каналов"""
        for channel in self.generator.channels:
            if channel.id in self._original_channel_configs:
                config = self._original_channel_configs[channel.id]
                channel.enabled = config["enabled"]
                channel.signal_type = config["signal_type"]
                channel.frequency = config["frequency"]
                channel.amplitude = config["amplitude"]
                channel.offset = config["offset"]
                channel.duty_cycle = config["duty_cycle"]
                channel.pulse_width = config["pulse_width"]
                channel.min_value = config["min_value"]
                channel.max_value = config["max_value"]
                channel.mu210_module = config["mu210_module"]
                channel.mu210_register = config["mu210_register"]
                # Сбрасываем время для корректной генерации
                channel.time = 0
        self._original_channel_configs.clear()

    def _apply_step(self, step_index: int):
        """Применить шаг сценария"""
        if not self.scenario or step_index >= len(self.scenario.steps):
            return

        step = self.scenario.steps[step_index]
        channel = self.generator.get_channel(step.channel_id)
        if not channel:
            return

        # Применяем настройки
        channel.signal_type = SignalType[step.signal_type.upper()]
        channel.frequency = step.frequency
        channel.amplitude = step.amplitude
        channel.offset = step.offset
        channel.duty_cycle = step.duty_cycle
        channel.pulse_width = step.pulse_width
        if step.mu210_module is not None:
            channel.mu210_module = step.mu210_module
        if step.mu210_register is not None:
            channel.mu210_register = step.mu210_register
        channel.enabled = True

        # Сохраняем данные для плавного перехода
        self._ramp_data[step.channel_id] = {
            "target_value": channel.current_value,
            "ramp_up": step.ramp_up,
            "start_value": channel.current_value,
            "elapsed": 0.0,
        }

        self.step_changed.emit(step_index + 1, len(self.scenario.steps))
        self.log_signal.emit(
            f"Шаг {step_index + 1}: Канал {step.channel_id + 1} - {step.signal_type} "
            f"({step.duration:.1f}с)",
            "info",
        )

    def _apply_graph_step(self, step: ScenarioStep) -> None:
        """Применить блок графа и отметить его активным."""
        if not self.scenario:
            return
        self._started_steps.add(step.id)
        channel = self.generator.get_channel(step.channel_id)
        if not channel:
            self.log_signal.emit(
                f"Шаг для канала {step.channel_id + 1} пропущен: канал не найден",
                "error",
            )
            self._completed_steps.add(step.id)
            return

        # Применяем настройки
        channel.signal_type = SignalType[step.signal_type.upper()]
        channel.frequency = step.frequency
        channel.amplitude = step.amplitude
        channel.offset = step.offset
        channel.duty_cycle = step.duty_cycle
        channel.pulse_width = step.pulse_width
        if step.mu210_module is not None:
            channel.mu210_module = step.mu210_module
        if step.mu210_register is not None:
            channel.mu210_register = step.mu210_register
        channel.enabled = True  # ← ВКЛЮЧАЕМ КАНАЛ
        # channel.time = 0.0
        channel.current_value = 0.0

        self._active_steps[step.id] = 0.0
        index = self.scenario.steps.index(step) + 1
        label = self.scenario.get_step_label(step.id)
        self.step_changed.emit(index, len(self.scenario.steps))
        self.log_signal.emit(
            f"Запущен шаг {label}: Канал {step.channel_id + 1} - "
            f"{step.signal_type} ({step.duration:.1f}с), "
            f"МУ210 №{channel.mu210_module}/R{channel.mu210_register}",
            "info",
        )

    def _can_start(self, step: ScenarioStep) -> bool:
        """Проверить, может ли шаг быть запущен."""
        if not self.scenario or step.id in self._started_steps:
            return False
        incoming = self.scenario.incoming_ids(step.id)
        if not incoming:
            return True
        if step.trigger_mode == TRIGGER_ANY:
            return bool(incoming & self._completed_steps)
        if step.trigger_mode == TRIGGER_SPECIFIC:
            return step.trigger_step_id in self._completed_steps
        # TRIGGER_ALL — все входящие шаги завершены
        return incoming <= self._completed_steps

    def _emit_active_steps(self) -> None:
        if not self.scenario:
            return
        labels = self.scenario.get_step_labels()
        active_labels = [
            labels[step.id]
            for step in self.scenario.steps
            if step.id in self._active_steps
        ]
        self.active_steps_changed.emit(", ".join(active_labels))

    def _update(self):
        """Обновление состояния (вызывается по таймеру)"""
        if not self._is_running or self.mode != ScenarioMode.SCENARIO:
            return

        dt = 0.05
        self._scenario_time += dt

        # Обновляем время
        self.time_updated.emit(self._scenario_time)

        # Обновляем прогресс
        if self.scenario:
            total = self.scenario.get_total_duration()
            if total > 0:
                progress = (self._scenario_time / total) * 100
                self.progress_changed.emit(min(100, progress))

        if self.scenario:
            step_by_id = {step.id: step for step in self.scenario.steps}
            completed_now = []
            for step_id in list(self._active_steps):
                elapsed = self._active_steps[step_id] + dt
                self._active_steps[step_id] = elapsed
                if elapsed >= step_by_id[step_id].duration:
                    completed_now.append(step_id)

            for step_id in completed_now:
                del self._active_steps[step_id]
                self._completed_steps.add(step_id)
                self.log_signal.emit(
                    f"Завершён шаг {self.scenario.get_step_label(step_id)}",
                    "info",
                )

            if completed_now:
                # Проверяем, какие шаги готовы к запуску
                self._start_ready_steps()
                self._disable_channels_without_active_steps(completed_now, step_by_id)
                self._emit_active_steps()

            if not self._active_steps:
                if len(self._completed_steps) == len(self.scenario.steps):
                    if self.scenario.loop:
                        self._started_steps.clear()
                        self._completed_steps.clear()
                        self._scenario_time = 0.0
                        self._start_ready_steps()
                        self.log_signal.emit("Сценарий зациклен", "info")
                    else:
                        self._finish_scenario()
                        return
                else:
                    # Проверяем, есть ли шаги, которые должны были запуститься
                    ready_to_start = []
                    for step in self.scenario.steps:
                        if self._can_start(step) and step.id not in self._started_steps:
                            ready_to_start.append(step.id)

                    if ready_to_start:
                        # Запускаем готовые шаги
                        for step in self.scenario.steps:
                            if step.id in ready_to_start:
                                self._apply_graph_step(step)
                        self._emit_active_steps()
                    else:
                        # Если есть незавершённые шаги, но нет готовых к запуску
                        # это нормально — ждём завершения текущих
                        pass

        # Обновляем значения сигналов
        self._apply_ramp()

    def _disable_channels_without_active_steps(
        self,
        completed_step_ids: List[str],
        step_by_id: Dict[str, ScenarioStep],
    ) -> None:
        """Выключить каналы, для которых больше нет активного шага."""
        active_channel_ids = {
            step_by_id[step_id].channel_id for step_id in self._active_steps
        }
        completed_channel_ids = {
            step_by_id[step_id].channel_id for step_id in completed_step_ids
        }
        for channel_id in completed_channel_ids - active_channel_ids:
            channel = self.generator.get_channel(channel_id)
            if channel is None:
                continue
            channel.current_value = channel.min_value
            channel.enabled = False

    def _apply_ramp(self):
        """Применить плавный переход (ramp)"""
        for channel_id, _data in self._ramp_data.items():
            channel = self.generator.get_channel(channel_id)
            if not channel:
                continue

            # Здесь можно реализовать плавное изменение значения
            # Если нужно, можно добавить интерполяцию
            pass

    def _finish_scenario(self):
        """Завершить сценарий"""
        self._is_running = False
        self.timer.stop()

        scenario_channel_ids = (
            {step.channel_id for step in self.scenario.steps}
            if self.scenario
            else set()
        )

        # Восстанавливаем настройки каналов
        self._restore_channel_configs()

        # После штатного завершения выходы сценария должны оставаться выключенными.
        for channel_id in scenario_channel_ids:
            channel = self.generator.get_channel(channel_id)
            if channel is None:
                continue
            channel.enabled = False
            channel.time = 0.0
            channel.current_value = channel.min_value

        self.mode = ScenarioMode.MANUAL
        self.mode_changed.emit("manual")
        self.scenario_finished.emit()
        self.log_signal.emit("Сценарий завершен, каналы восстановлены", "success")

    def set_manual_mode(self):
        """Переключиться в ручной режим"""
        if self.mode == ScenarioMode.SCENARIO or self.mode == ScenarioMode.PAUSED:
            self.stop_scenario()

        # Убеждаемся, что все каналы включены
        for channel in self.generator.channels:
            channel.enabled = True
            channel.time = 0

        self.mode = ScenarioMode.MANUAL
        self.mode_changed.emit("manual")

    def get_mode(self) -> str:
        """Получить текущий режим"""
        return self.mode.value

    def is_running(self) -> bool:
        """Проверить, запущен ли сценарий"""
        return self._is_running

    def get_progress(self) -> float:
        """Получить прогресс выполнения"""
        if not self.scenario:
            return 0.0
        total = self.scenario.get_total_duration()
        if total <= 0:
            return 0.0
        return min(100, (self._scenario_time / total) * 100)

    def enable_all_channels(self, enabled: bool = True):
        """Включить/выключить все каналы"""
        for channel in self.generator.channels:
            channel.enabled = enabled
            if enabled:
                channel.time = 0

    def _start_ready_steps(self) -> None:
        if not self.scenario:
            return
        started = []
        for step in self.scenario.steps:
            if self._can_start(step):
                self._apply_graph_step(step)
                started.append(step.id)
        if started:
            self.log_signal.emit(
                f"Запущены шаги: {', '.join(self.scenario.get_step_label(sid) for sid in started)}",
                "info",
            )
