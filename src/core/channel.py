from dataclasses import dataclass, field
from typing import Optional
from .signal_types import SignalType

@dataclass
class AnalogChannel:
    """Модель аналогового канала"""
    id: int
    name: str
    signal_type: SignalType = SignalType.SINE
    frequency: float = 1.0  # Гц
    amplitude: float = 50.0  # 0-100%
    offset: float = 0.0
    min_value: float = 0.0
    max_value: float = 100.0
    enabled: bool = True
    current_value: float = 0.0
    time: float = 0.0  # Внутреннее время для генерации
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'signal_type': self.signal_type.name,
            'frequency': self.frequency,
            'amplitude': self.amplitude,
            'offset': self.offset,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'enabled': self.enabled
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data['id'],
            name=data['name'],
            signal_type=SignalType[data['signal_type']],
            frequency=data['frequency'],
            amplitude=data['amplitude'],
            offset=data['offset'],
            min_value=data['min_value'],
            max_value=data['max_value'],
            enabled=data['enabled']
        )