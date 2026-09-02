from dataclasses import dataclass
from typing import Any, Dict

from .signal_types import SignalType


@dataclass
class AnalogChannel:
    """Модель канала (поддерживает аналоговые и дискретные сигналы)"""

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

    # Параметры для дискретных сигналов
    duty_cycle: float = 50.0  # Скважность для PWM (0-100%)
    pulse_width: float = 1.0  # Длительность импульса (сек)
    discrete_value: bool = False  # Текущее дискретное значение

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "signal_type": self.signal_type.name,
            "frequency": self.frequency,
            "amplitude": self.amplitude,
            "offset": self.offset,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "enabled": self.enabled,
            "duty_cycle": self.duty_cycle,
            "pulse_width": self.pulse_width,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            name=data["name"],
            signal_type=SignalType[data["signal_type"]],
            frequency=data["frequency"],
            amplitude=data["amplitude"],
            offset=data["offset"],
            min_value=data["min_value"],
            max_value=data["max_value"],
            enabled=data["enabled"],
            duty_cycle=data.get("duty_cycle", 50.0),
            pulse_width=data.get("pulse_width", 1.0),
        )
