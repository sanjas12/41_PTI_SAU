from enum import Enum
from typing import Dict, Optional

from PyQt5.QtCore import QMutex, QMutexLocker, QObject, QTimer, pyqtSignal

from core.signal_generator import SignalGenerator
from core.signal_types import SignalType

from .scenario_model import Scenario


class ScenarioMode(Enum):
    """Режимы работы"""
    MANUAL = "manual"        # Ручной режим
    SCENARIO = "scenario"    # Режим сценария
    PAUSED = "paused"        # Приостановлен


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
            
            # Останавливаем ручную генерацию
            self.mode = ScenarioMode.SCENARIO
            self._is_running = True
            self._current_step = 0
            self._step_time = 0.0
            self._scenario_time = 0.0
            
            # Применяем первый шаг
            self._apply_step(0)
            
            # Запускаем таймер
            self.timer.start()
            
            self.mode_changed.emit("scenario")
            self.scenario_started.emit(self.scenario.name)
            self.step_changed.emit(0, len(self.scenario.steps))
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
                'enabled': channel.enabled,
                'signal_type': channel.signal_type,
                'frequency': channel.frequency,
                'amplitude': channel.amplitude,
                'offset': channel.offset,
                'min_value': channel.min_value,
                'max_value': channel.max_value
            }
            
    def _restore_channel_configs(self):
        """Восстановить настройки каналов"""
        for channel in self.generator.channels:
            if channel.id in self._original_channel_configs:
                config = self._original_channel_configs[channel.id]
                channel.enabled = config['enabled']
                channel.signal_type = config['signal_type']
                channel.frequency = config['frequency']
                channel.amplitude = config['amplitude']
                channel.offset = config['offset']
                channel.min_value = config['min_value']
                channel.max_value = config['max_value']
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
        channel.enabled = True
        
        # Сохраняем данные для плавного перехода
        self._ramp_data[step.channel_id] = {
            'target_value': channel.current_value,
            'ramp_up': step.ramp_up,
            'start_value': channel.current_value,
            'elapsed': 0.0
        }
        
        self.step_changed.emit(step_index + 1, len(self.scenario.steps))
        self.log_signal.emit(
            f"Шаг {step_index + 1}: Канал {step.channel_id + 1} - {step.signal_type} "
            f"({step.duration:.1f}с)", "info"
        )
        
    def _update(self):
        """Обновление состояния (вызывается по таймеру)"""
        if not self._is_running or self.mode != ScenarioMode.SCENARIO:
            return
            
        dt = 0.05  # 50ms
        self._step_time += dt
        self._scenario_time += dt
        
        # Обновляем время
        self.time_updated.emit(self._scenario_time)
        
        # Обновляем прогресс
        if self.scenario:
            total = self.scenario.get_total_duration()
            if total > 0:
                progress = (self._scenario_time / total) * 100
                self.progress_changed.emit(min(100, progress))
        
        # Проверяем завершение текущего шага
        if self.scenario and self._current_step < len(self.scenario.steps):
            step = self.scenario.steps[self._current_step]
            if self._step_time >= step.duration:
                # Переход к следующему шагу
                self._current_step += 1
                self._step_time = 0.0
                
                if self._current_step >= len(self.scenario.steps):
                    # Сценарий завершен
                    if self.scenario.loop:
                        # Зацикливание
                        self._current_step = 0
                        self._scenario_time = 0.0
                        self.log_signal.emit("Сценарий зациклен", "info")
                    else:
                        self._finish_scenario()
                        return
                
                # Применяем следующий шаг
                self._apply_step(self._current_step)
        
        # Обновляем значения сигналов с учетом плавного перехода
        self._apply_ramp()
        
    def _apply_ramp(self):
        """Применить плавный переход (ramp)"""
        for channel_id, data in self._ramp_data.items():
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
        
        # Восстанавливаем настройки каналов
        self._restore_channel_configs()
        
        # Включаем все каналы
        for channel in self.generator.channels:
            channel.enabled = True
            channel.time = 0
        
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