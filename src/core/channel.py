from dataclasses import dataclass
from typing import Any, Dict

from .output_devices import (
    DEVICE_OWEN,
    default_address,
    normalize,
)
from .signal_types import SignalType


@dataclass
class AnalogChannel:
    """Модель канала (поддерживает аналоговые и дискретные сигналы)"""

    id: int
    name: str
    signal_type: SignalType = SignalType.SINE
    frequency: float = 1.0  # Гц
    amplitude: float = 50.0  # 0-100%
    constant_value: float = 0.0
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

    # Устройство вывода и адрес/регистр внутри него
    output_device: str = DEVICE_OWEN
    output_address: int = 0  # 0 = подставить значение по умолчанию

    # Устаревшие поля МУ210 — оставлены для обратной совместимости.
    mu210_module: int = 0  # Номер модуля, начиная с 1; 0 = назначить по id
    mu210_register: int = 0  # Оперативный регистр 3000-3007; 0 = по id

    def __post_init__(self) -> None:
        # Модуль/регистр МУ210 по умолчанию, как было раньше.
        if self.mu210_module <= 0:
            self.mu210_module = self.id // 8 + 1
        if self.mu210_register <= 0:
            self.mu210_register = 3000 + self.id % 8

        # Согласовать output_device / output_address.
        if self.output_address <= 0 and self.output_device == DEVICE_OWEN:
            # Старые каналы: адрес выводим из mu210_register.
            self.output_address = self.mu210_register
        self.output_device, self.output_address = normalize(
            self.output_device, self.output_address
        )

        # Держим mu210_* в согласии с output_*, если устройство — ОВЕН.
        if self.output_device == DEVICE_OWEN:
            self.mu210_register = self.output_address

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "signal_type": self.signal_type.name,
            "frequency": self.frequency,
            "amplitude": self.amplitude,
            "constant_value": self.constant_value,
            "offset": self.offset,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "enabled": self.enabled,
            "duty_cycle": self.duty_cycle,
            "pulse_width": self.pulse_width,
            "output_device": self.output_device,
            "output_address": self.output_address,
            # Обратная совместимость со старыми версиями:
            "mu210_module": self.mu210_module,
            "mu210_register": self.mu210_register,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalogChannel":
        device = data.get("output_device")
        address = data.get("output_address")

        if device is None:
            # Старый формат — жёстко ОВЕН.
            device = DEVICE_OWEN
            address = int(data.get("mu210_register", 0) or 0)
            if address <= 0:
                address = default_address(DEVICE_OWEN)

        if address is None:
            address = default_address(str(device))

        return cls(
            id=int(data["id"]),
            name=str(data["name"]),
            signal_type=SignalType[data["signal_type"]],
            frequency=float(data.get("frequency", 1.0)),
            amplitude=float(data.get("amplitude", 50.0)),
            constant_value=float(data.get("constant_value", 0.0)),
            offset=float(data.get("offset", 0.0)),
            min_value=float(data.get("min_value", 0.0)),
            max_value=float(data.get("max_value", 100.0)),
            enabled=bool(data.get("enabled", True)),
            duty_cycle=float(data.get("duty_cycle", 50.0)),
            pulse_width=float(data.get("pulse_width", 1.0)),
            output_device=str(device),
            output_address=int(address),
            mu210_module=int(data.get("mu210_module", data["id"] // 8 + 1)),
            mu210_register=int(data.get("mu210_register", 3000 + data["id"] % 8)),
        )
