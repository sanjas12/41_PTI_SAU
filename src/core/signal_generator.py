import numpy as np
from typing import List, Optional
from .channel import AnalogChannel
from .signal_types import SignalType
import random
import time


class SignalGenerator:
    """Генерирует сигналы для всех каналов"""
    
    def __init__(self, channels: Optional[List[AnalogChannel]] = None):
        self.channels = channels or []
        self._dt = 0.01  # Шаг времени 10ms (100 Гц)
        self._update_interval = 0.5  # Интервал обновления в секундах (по умолчанию 500ms)
        self._last_update_time = 0
        self._time_accumulator = 0  # Аккумулятор времени для синхронизации
        
    def add_channel(self, channel: AnalogChannel):
        """Добавить канал"""
        self.channels.append(channel)
        
    def remove_channel(self, channel_id: int):
        """Удалить канал по ID"""
        self.channels = [ch for ch in self.channels if ch.id != channel_id]
        
    def get_channel(self, channel_id: int) -> Optional[AnalogChannel]:
        """Получить канал по ID"""
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
        self._time_accumulator = 0
        
    def get_update_interval(self) -> float:
        """Получить текущий интервал обновления в секундах"""
        return self._update_interval
        
    def update(self, dt: float = None) -> List[float]:
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
        
        # Проверяем, нужно ли обновлять значения
        if current_time - self._last_update_time >= self._update_interval:
            # Вычисляем сколько шагов нужно сделать для синхронизации
            steps = int(self._time_accumulator / self._update_interval)
            if steps > 0:
                step_dt = self._update_interval
                # Обновляем значения за несколько шагов
                for _ in range(min(steps, 10)):  # Ограничиваем максимум 10 шагов за раз
                    for channel in self.channels:
                        if not channel.enabled:
                            continue
                        channel.time += step_dt
                        value = self._generate_signal(channel)
                        value = max(channel.min_value, min(channel.max_value, value))
                        channel.current_value = value
                
                self._time_accumulator = 0
                self._last_update_time = current_time
        else:
            # Если время не пришло, просто пропускаем обновление
            pass
            
        return self.get_values()
    
    def _generate_signal(self, channel: AnalogChannel) -> float:
        """Генерирует значение для конкретного канала"""
        t = channel.time
        freq = channel.frequency
        amp = channel.amplitude / 100.0  # Нормализуем амплитуду
        offset = channel.offset / 100.0  # Нормализуем смещение
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
            # Простой случайный сигнал с обновлением каждые 100ms
            if int(t * 10) % 10 == 0:
                raw = random.uniform(-1, 1)
            else:
                raw = channel.current_value  # Держим предыдущее значение
                
        else:  # CUSTOM или по умолчанию
            raw = np.sin(2 * np.pi * freq * t)
            
        # Масштабируем в диапазон [min, max]
        scaled = mid + raw * amp * range_val
        
        return scaled
    
    def get_values(self) -> List[float]:
        """Получить текущие значения всех каналов"""
        return [ch.current_value for ch in self.channels]
    
    def get_value(self, channel_id: int) -> Optional[float]:
        """Получить значение конкретного канала"""
        channel = self.get_channel(channel_id)
        return channel.current_value if channel else None
        
    def get_channel_info(self) -> List[dict]:
        """Получить информацию о всех каналах"""
        info = []
        for ch in self.channels:
            info.append({
                'id': ch.id,
                'name': ch.name,
                'type': str(ch.signal_type),
                'frequency': ch.frequency,
                'amplitude': ch.amplitude,
                'enabled': ch.enabled,
                'current_value': ch.current_value
            })
        return info