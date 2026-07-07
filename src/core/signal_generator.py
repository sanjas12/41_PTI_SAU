import numpy as np
from typing import List, Optional
from .channel import AnalogChannel
from .signal_types import SignalType
import random

class SignalGenerator:
    """Генерирует сигналы для всех каналов"""
    
    def __init__(self, channels: Optional[List[AnalogChannel]] = None):
        self.channels = channels or []
        self._dt = 0.01  # Шаг времени 10ms (100 Гц)
        
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
        
    def update(self, dt: float = None):
        """
        Обновить значения всех каналов
        dt - шаг времени в секундах
        """
        if dt is None:
            dt = self._dt
            
        for channel in self.channels:
            if not channel.enabled:
                continue
                
            channel.time += dt
            value = self._generate_signal(channel)
            
            # Применяем ограничения
            value = max(channel.min_value, min(channel.max_value, value))
            channel.current_value = value
            
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