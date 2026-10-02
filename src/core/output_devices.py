"""Справочник устройств вывода и их адресных пространств.

Используется в UI (ChannelSettingsDialog, StepEditDialog) и в моделях
(AnalogChannel, ScenarioStep), чтобы не хардкодить список устройств
и регистров в нескольких местах.
"""

from typing import List, Tuple

DEVICE_OWEN = "owen"
DEVICE_PLC = "plc"
DEVICE_MOXA_E1242 = "moxa_e1242"
DEVICE_SIMULATOR = "simulator"

ALL_DEVICES = (
    DEVICE_OWEN,
    DEVICE_PLC,
    DEVICE_MOXA_E1242,
    DEVICE_SIMULATOR,
)


def device_label(device: str) -> str:
    """Человекочитаемое название устройства."""
    return {
        DEVICE_OWEN: "ОВЕН МУ210-501",
        DEVICE_PLC: "PLC Modicon Premium",
        DEVICE_MOXA_E1242: "Moxa ioLogik E1242",
        DEVICE_SIMULATOR: "Simulator",
    }.get(device, device)


def register_choices(device: str) -> List[Tuple[str, int]]:
    """Список пар (подпись, значение) для выпадающего списка регистров."""
    if device == DEVICE_OWEN:
        return [(f"AO{i + 1} — регистр {3000 + i}", 3000 + i) for i in range(8)]

    if device == DEVICE_PLC:
        # PLC хранит float (REAL) в 2 регистрах, начиная с %MW0.
        # Шаг 2, 20 каналов -> %MW0, %MW2, ..., %MW38.
        return [(f"%MW{i} (float)", i) for i in range(0, 40, 2)]

    if device == DEVICE_MOXA_E1242:
        # 4 канала E1242: AI-00..AI-03 (чтение) / DO-00..DO-03 (запись).
        return [(f"Канал {i:02d} (AI/DO-{i:02d})", i) for i in range(4)]

    if device == DEVICE_SIMULATOR:
        return [("— (не используется) —", 0)]

    return []


def default_address(device: str) -> int:
    """Адрес/регистр по умолчанию для устройства."""
    choices = register_choices(device)
    return choices[0][1] if choices else 0


def normalize(device: str, address: int) -> Tuple[str, int]:
    """Привести пару (устройство, адрес) к допустимому виду.

    Если устройство неизвестно — возвращает ("owen", 3000).
    Если адрес не входит в список допустимых — берёт первый из списка.
    """
    if device not in ALL_DEVICES:
        return DEVICE_OWEN, 3000
    valid_values = {value for _, value in register_choices(device)}
    if address not in valid_values:
        address = default_address(device)
    return device, address