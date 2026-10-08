"""Проверка и применение дорожек к копиям каналов без обмена с оборудованием."""

import math
from dataclasses import replace
from typing import Dict, List, Optional

from core.channel import AnalogChannel
from core.output_devices import register_choices
from core.signal_types import SignalType
from scenario.scenario_model import Scenario


def apply_tracks(
    scenario: Scenario, time: float, channels: Dict[int, AnalogChannel]
) -> None:
    """Применить ключи всех дорожек атомарно относительно следующей генерации."""
    routing_channels = set()
    for track in scenario.tracks:
        if not track.keyframes or time < min(key.time for key in track.keyframes):
            continue
        channel = channels.get(track.channel_id)
        if channel is None:
            continue
        value = track.evaluate(time, getattr(channel, track.parameter))
        if track.parameter == "signal_type":
            value = SignalType[value]
        elif track.parameter in ("mu210_module", "output_address"):
            value = int(value)
        setattr(channel, track.parameter, value)
        if track.parameter in ("output_device", "output_address"):
            routing_channels.add(channel.id)
    for channel_id in routing_channels:
        channel = channels[channel_id]
        if channel.output_device == "owen":
            channel.mu210_register = channel.output_address


def validate_timeline(
    scenario: Scenario,
    channels: List[AnalogChannel],
    module_count: Optional[int] = None,
) -> List[str]:
    """Проверить ключи и карты выходов в точках изменения общей шкалы."""
    errors: List[str] = []
    if not scenario.tracks:
        return errors
    if not math.isfinite(scenario.timeline_duration) or scenario.timeline_duration <= 0:
        return ["Длительность шкалы должна быть конечной и больше нуля"]
    known = {channel.id for channel in channels}
    used = set()
    for track in scenario.tracks:
        if track.channel_id not in known:
            errors.append(f"Дорожка: канал {track.channel_id + 1} не найден")
        target = (track.channel_id, track.parameter)
        if target in used:
            errors.append("Один параметр канала нельзя назначить двум дорожкам")
        used.add(target)
        try:
            track.validate()
        except ValueError as exc:
            errors.append(f"Канал {track.channel_id + 1}: {exc}")
    if errors:
        return errors
    animated = {track.channel_id for track in scenario.tracks if track.keyframes}
    timings = scenario.get_step_timings()
    if len(timings) != len(scenario.steps):
        return ["Граф шагов содержит цикл или потерянные связи"]
    times = {0.0, scenario.get_total_duration()}
    times.update(key.time for track in scenario.tracks for key in track.keyframes)
    times.update(time for interval in timings.values() for time in interval)
    # Значения непрерывных параметров проверяем с обеих сторон границ скачков.
    times.update(max(0.0, time - 0.000001) for time in list(times))
    for time in sorted(times):
        state = {channel.id: replace(channel) for channel in channels}
        for channel_id in animated:
            state[channel_id].enabled = True
        active = set(animated) | {channel.id for channel in channels if channel.enabled}
        for step in scenario.steps:
            start, end = timings.get(step.id, (0.0, step.duration))
            if not start <= time < end or step.channel_id not in state:
                continue
            channel = state[step.channel_id]
            active.add(channel.id)
            try:
                channel.signal_type = SignalType[step.signal_type.upper()]
            except KeyError:
                return ["Шаг содержит неизвестный тип сигнала"]
            channel.enabled = True
            if step.mu210_module is not None:
                channel.mu210_module = step.mu210_module
            if step.output_device != "owen" or step.mu210_register is not None:
                channel.output_device = step.output_device
                channel.output_address = step.output_address
        apply_tracks(scenario, time, state)
        outputs: Dict[tuple, int] = {}
        for channel_id in active:
            channel = state[channel_id]
            prefix = f"{time:g} с, канал {channel_id + 1}"
            if channel.min_value > channel.max_value:
                errors.append(f"{prefix}: минимум больше максимума")
            if not channel.enabled or not channel.signal_type.is_analog():
                continue
            valid = {address for _, address in register_choices(channel.output_device)}
            if channel.output_address not in valid:
                errors.append(f"{prefix}: недопустимый адрес устройства")
            if channel.output_device != "owen":
                continue
            if (
                module_count is not None
                and not 1 <= channel.mu210_module <= module_count
            ):
                errors.append(f"{prefix}: модуль МУ210 отсутствует")
            output = (channel.mu210_module, channel.output_address)
            if output in outputs:
                errors.append(
                    f"{prefix}: конфликт выхода с каналом {outputs[output] + 1}"
                )
            outputs[output] = channel_id
    return list(dict.fromkeys(errors))
