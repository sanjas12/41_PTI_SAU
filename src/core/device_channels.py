"""Создание каналов по поддерживаемой карте подключённого устройства."""

from typing import Any, Dict, List, Tuple

from core.channel import AnalogChannel
from core.signal_types import SignalType


def create_device_channels(
    device: str, module_count: int, saved: Dict[str, Dict[str, Any]]
) -> List[AnalogChannel]:
    """МУ210: 8 AO на модуль; PLC/Simulator: 20 REAL старой карты."""
    if device not in ("owen", "plc", "simulator"):
        raise ValueError("Неизвестный профиль устройства")
    if module_count < 1:
        raise ValueError("Нет подключённых модулей")
    count = module_count * 8 if device == "owen" else 20
    output_device = "owen" if device == "owen" else "plc"
    preferred: Dict[int, Tuple[int, int]] = {}
    reserved = set()
    if device == "owen":
        for index in range(count):
            config = saved.get(str(index), {})
            if config.get("output_device", "owen") != "owen":
                continue
            try:
                target = (
                    int(config.get("mu210_module", index // 8 + 1)),
                    int(
                        config.get(
                            "output_address",
                            config.get("mu210_register", 3000 + index % 8),
                        )
                    ),
                )
            except (TypeError, ValueError):
                continue
            if (
                config
                and 1 <= target[0] <= module_count
                and 3000 <= target[1] <= 3007
                and target not in reserved
            ):
                preferred[index] = target
                reserved.add(target)
    available = [
        (module, address)
        for module in range(1, module_count + 1)
        for address in range(3000, 3008)
        if (module, address) not in reserved
    ]
    channels: List[AnalogChannel] = []
    for index in range(count):
        module, address = (
            (preferred[index] if index in preferred else available.pop(0))
            if device == "owen"
            else (index // 8 + 1, index * 2)
        )
        data: Dict[str, Any] = {
            "id": index,
            "name": f"AO{index + 1:02d}",
            "signal_type": "CUSTOM",
            "constant_value": 0.0,
            "min_value": 0.0,
            "max_value": 100.0,
        }
        data.update(saved.get(str(index), {}))
        signal_type = SignalType[str(data.get("signal_type", "CUSTOM"))]
        if not signal_type.is_analog():
            data["signal_type"] = "CUSTOM"
        data.update(
            {
                "id": index,
                "output_device": output_device,
                "output_address": address,
                "mu210_module": module,
                "mu210_register": address if device == "owen" else 3000 + index % 8,
            }
        )
        channels.append(AnalogChannel.from_dict(data))
    return channels
