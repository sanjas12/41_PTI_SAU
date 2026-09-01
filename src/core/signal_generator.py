import random
import time
from typing import Any, Dict, List, Optional

import numpy as np

from .channel import AnalogChannel
from .signal_types import SignalType


class SignalGenerator:
    """Генерирует сигналы для всех каналов"""

    RANDOM_HOLD_SECONDS = 0.1

    def __init__(self, channels: Optional[List[AnalogChannel]] = None):
        self.channels = channels or []
        self._dt = 0.01  # Шаг времени 10ms (100 Гц)
        self._update_interval = (
            0.05  # Интервал обновления в секундах (по умолчанию 500ms)
        )
        self._last_update_time: float = 0.0
        self._time_accumulator: float = 0.0  # Аккумулятор времени для синхронизации
        # RANDOM хранится в нормализованном диапазоне [-1, 1]. Нельзя
        # использовать current_value: он уже масштабирован в диапазон канала.
        self._random_values: Dict[int, float] = {}
        self._random_buckets: Dict[int, int] = {}
        # Для дискретных сигналов
        self._discrete_state: Dict[int, bool] = {}
        self._last_toggle_time: Dict[int, float] = {}
        self._pulse_state: Dict[int, bool] = {}
        self._pulse_timer: Dict[int, float] = {}

    def add_channel(self, channel: AnalogChannel):
        self.channels.append(channel)

    def remove_channel(self, channel_id: int):
        self.channels = [ch for ch in self.channels if ch.id != channel_id]
        self._random_values.pop(channel_id, None)
        self._random_buckets.pop(channel_id, None)
        self._discrete_state.pop(channel_id, None)
        self._last_toggle_time.pop(channel_id, None)
        self._pulse_state.pop(channel_id, None)
        self._pulse_timer.pop(channel_id, None)

    def get_channel(self, channel_id: int) -> Optional[AnalogChannel]:
        for ch in self.channels:
            if ch.id == channel_id:
                return ch
        return None

    def set_update_interval(self, interval_seconds: float):
        """
        Установить интервал обновления значений

        Args:
            interval_seconds: Интервал в секундах (0.001 - 10.0)
        """
        # Ограничиваем диапазон
        self._update_interval = max(0.001, min(10.0, interval_seconds))
        # Сбрасываем аккумулятор для плавного перехода
        self._time_accumulator = 0.0

    def get_update_interval(self) -> float:
        """Получить текущий интервал обновления в секундах"""
        return self._update_interval

    def update(self, dt: Optional[float] = None) -> List[float]:
        """
        Обновить значения всех каналов

        Args:
            dt: Шаг времени в секундах (если None, использует сохраненный)

        Returns:
            List[float]: Текущие значения всех каналов
        """
        if dt is None:
            dt = self._dt

        # Аккумулируем время
        self._time_accumulator += dt
        current_time = time.time()

        if current_time - self._last_update_time >= self._update_interval:
            steps = int(self._time_accumulator / self._update_interval)
            if steps > 0:
                for _ in range(min(steps, 10)):
                    for channel in self.channels:
                        if not channel.enabled:
                            continue
                        channel.time += self._update_interval
                        if channel.signal_type.is_analog():
                            value = self._generate_analog_signal(channel)
                        else:
                            value = self._generate_discrete_signal(channel)
                        value = max(channel.min_value, min(channel.max_value, value))
                        channel.current_value = value

                self._time_accumulator = 0.0
                self._last_update_time = current_time

        return self.get_values()

    def _generate_analog_signal(self, channel: AnalogChannel) -> float:
        """Генерирует аналоговый сигнал"""
        t = channel.time
        freq = channel.frequency
        amp = channel.amplitude / 100.0
        offset = channel.offset / 100.0
        range_val = (channel.max_value - channel.min_value) / 2
        mid = (channel.max_value + channel.min_value) / 2

        if channel.signal_type == SignalType.SINE:
            raw = np.sin(2 * np.pi * freq * t)
        elif channel.signal_type == SignalType.SQUARE:
            raw = np.sign(np.sin(2 * np.pi * freq * t))
        elif channel.signal_type == SignalType.SAWTOOTH:
            raw = 2 * (t * freq - np.floor(t * freq + 0.5))
        elif channel.signal_type == SignalType.TRIANGLE:
            raw = 2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1
        elif channel.signal_type == SignalType.RANDOM:
            bucket = int(t / self.RANDOM_HOLD_SECONDS)
            if self._random_buckets.get(channel.id) != bucket:
                self._random_values[channel.id] = random.uniform(-1.0, 1.0)
                self._random_buckets[channel.id] = bucket
            raw = self._random_values[channel.id]
        else:
            raw = np.sin(2 * np.pi * freq * t)

        scaled = mid + (raw * amp + offset) * range_val
        return scaled

    def _generate_discrete_signal(self, channel: AnalogChannel) -> float:
        """Генерирует дискретный сигнал (возвращает 0 или 100% от диапазона)"""
        t = channel.time
        freq = channel.frequency
        min_val = channel.min_value
        max_val = channel.max_value
        mid = (max_val + min_val) / 2
        
        # Дискретное значение по умолчанию
        discrete_value = False
        
        if channel.signal_type == SignalType.DISCRETE:
            # Простой дискретный: переключается с частотой
            period = 1.0 / freq if freq > 0 else 1.0
            discrete_value = (t % period) < (period / 2)
            
        elif channel.signal_type == SignalType.PULSE:
            # Импульсный: короткий импульс с периодом
            period = 1.0 / freq if freq > 0 else 1.0
            pulse_width = min(channel.pulse_width, period / 2)
            discrete_value = (t % period) < pulse_width
            
        elif channel.signal_type == SignalType.PWM:
            # ШИМ: с изменяемой скважностью
            period = 1.0 / freq if freq > 0 else 1.0
            duty = channel.duty_cycle / 100.0
            discrete_value = (t % period) < (period * duty)
            
        elif channel.signal_type == SignalType.STEP:
            # Ступенчатый: меняется по уровням
            # Амплитуда определяет количество уровней
            levels = max(2, int(channel.amplitude / 10) + 2)
            step_duration = 1.0 / freq if freq > 0 else 1.0
            level = int(t / step_duration) % levels
            # Возвращаем пропорциональное значение, но дискретное (0 или 100%)
            discrete_value = (level % 2) == 0
            
        elif channel.signal_type == SignalType.TOGGLE:
            # Переключающийся: меняет состояние при каждом достижении порога
            period = 1.0 / freq if freq > 0 else 1.0
            if channel.id not in self._last_toggle_time:
                self._last_toggle_time[channel.id] = 0.0
                self._discrete_state[channel.id] = False
            
            # Переключаем при каждом периоде
            if t - self._last_toggle_time[channel.id] >= period:
                self._discrete_state[channel.id] = not self._discrete_state.get(channel.id, False)
                self._last_toggle_time[channel.id] = t
            
            discrete_value = self._discrete_state.get(channel.id, False)
        
        else:
            # По умолчанию: меандр
            period = 1.0 / freq if freq > 0 else 1.0
            discrete_value = (t % period) < (period / 2)
        
        # Сохраняем дискретное состояние
        channel.discrete_value = discrete_value
        
        # Возвращаем 0 или 100% от диапазона
        return max_val if discrete_value else min_val

    def get_values(self) -> List[float]:
        return [ch.current_value for ch in self.channels]

    def get_value(self, channel_id: int) -> Optional[float]:
        channel = self.get_channel(channel_id)
        return channel.current_value if channel else None

    def get_channel_info(self) -> List[Dict[str, Any]]:
        info = []
        for ch in self.channels:
            info.append({
                "id": ch.id,
                "name": ch.name,
                "type": str(ch.signal_type),
                "frequency": ch.frequency,
                "amplitude": ch.amplitude,
                "enabled": ch.enabled,
                "current_value": ch.current_value,
                "is_analog": ch.signal_type.is_analog(),
                "is_discrete": ch.signal_type.is_discrete(),
                "discrete_value": ch.discrete_value if ch.signal_type.is_discrete() else None,
            })
        return info