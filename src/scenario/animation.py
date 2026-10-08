"""Ключевые кадры общей шкалы сценария; не зависит от Qt."""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.output_devices import ALL_DEVICES
from core.signal_types import SignalType

PARAMETERS = {
    "constant_value": "Постоянное значение",
    "amplitude": "Амплитуда (%)",
    "frequency": "Частота (Гц)",
    "offset": "Смещение (%)",
    "min_value": "Минимум",
    "max_value": "Максимум",
    "duty_cycle": "Скважность (%)",
    "pulse_width": "Длительность импульса (с)",
    "enabled": "Включён",
    "signal_type": "Тип сигнала",
    "output_device": "Устройство вывода",
    "output_address": "Регистр / адрес",
    "mu210_module": "Модуль МУ210",
}
STEP_PARAMETERS = {
    "enabled",
    "signal_type",
    "output_device",
    "output_address",
    "mu210_module",
}


@dataclass
class Keyframe:
    time: float
    value: Any
    interpolation: str = "linear"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.time,
            "value": self.value,
            "interpolation": self.interpolation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Keyframe":
        return cls(
            float(data["time"]), data["value"], str(data.get("interpolation", "linear"))
        )


@dataclass
class AnimationTrack:
    channel_id: int
    parameter: str
    keyframes: List[Keyframe] = field(default_factory=list)

    def validate(self) -> None:
        if self.parameter not in PARAMETERS:
            raise ValueError("Неизвестный параметр дорожки")
        times = set()
        for key in self.keyframes:
            if not math.isfinite(key.time) or key.time < 0 or key.time in times:
                raise ValueError(
                    "Время ключа должно быть конечным, неотрицательным и уникальным"
                )
            times.add(key.time)
            if key.interpolation not in ("linear", "hold"):
                raise ValueError("Неизвестная интерполяция")
            if self.parameter in STEP_PARAMETERS and key.interpolation != "hold":
                raise ValueError("Тип сигнала и привязка переключаются только скачком")
            value = key.value
            if self.parameter == "enabled":
                if not isinstance(value, bool):
                    raise ValueError("Включён должен быть логическим значением")
            elif self.parameter == "signal_type":
                if not isinstance(value, str) or value not in SignalType.__members__:
                    raise ValueError("Неизвестный тип сигнала")
            elif self.parameter == "output_device":
                if value not in ALL_DEVICES:
                    raise ValueError("Неизвестное устройство")
            else:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    raise ValueError("Значение должно быть конечным числом")
                if (
                    self.parameter in ("output_address", "mu210_module")
                    and int(value) != value
                ):
                    raise ValueError("Адрес и номер модуля должны быть целыми")
                if (
                    self.parameter in ("amplitude", "duty_cycle")
                    and not 0 <= value <= 100
                ):
                    raise ValueError("Значение должно быть от 0 до 100 %")
                if self.parameter == "offset" and not -100 <= value <= 100:
                    raise ValueError("Смещение должно быть от -100 до 100 %")
                if self.parameter in ("frequency", "pulse_width") and value <= 0:
                    raise ValueError("Значение должно быть больше нуля")
                if self.parameter == "mu210_module" and not 1 <= value <= 32:
                    raise ValueError("Номер модуля должен быть от 1 до 32")
                if self.parameter == "output_address" and not 0 <= value <= 65535:
                    raise ValueError("Адрес должен быть от 0 до 65535")

    def evaluate(self, time: float, baseline: Any) -> Any:
        """До первого ключа — исходное значение, после последнего — удержание."""
        keys = sorted(self.keyframes, key=lambda key: key.time)
        if not keys or time < keys[0].time:
            return baseline
        left = keys[0]
        for right in keys[1:]:
            if time < right.time:
                if left.interpolation == "hold" or self.parameter in STEP_PARAMETERS:
                    return left.value
                fraction = (time - left.time) / (right.time - left.time)
                return (
                    float(left.value)
                    + (float(right.value) - float(left.value)) * fraction
                )
            left = right
        return left.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "parameter": self.parameter,
            "keyframes": [
                key.to_dict()
                for key in sorted(self.keyframes, key=lambda key: key.time)
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnimationTrack":
        track = cls(
            int(data["channel_id"]),
            str(data["parameter"]),
            [Keyframe.from_dict(item) for item in data.get("keyframes", [])],
        )
        track.validate()
        return track
