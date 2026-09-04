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
    mu210_module: int = 0  # Номер модуля, начиная с 1; 0 = назначить по id
    mu210_register: int = 0  # Оперативный регистр 3000-3007; 0 = по id

    def __post_init__(self) -> None:
        if self.mu210_module <= 0:
            self.mu210_module = self.id // 8 + 1
        if self.mu210_register <= 0:
            self.mu210_register = 3000 + self.id % 8

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
            "mu210_module": self.mu210_module,
            "mu210_register": self.mu210_register,
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
            mu210_module=data.get("mu210_module", data["id"] // 8 + 1),
            mu210_register=data.get("mu210_register", 3000 + data["id"] % 8),
        )
