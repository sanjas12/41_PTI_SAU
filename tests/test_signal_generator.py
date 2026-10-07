from unittest.mock import patch

import pytest

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType


@pytest.mark.parametrize("time", [0.0, 0.125, 12.0])
@pytest.mark.parametrize("value,expected", [(-30.0, -10.0), (27.5, 27.5), (90.0, 80.0)])
def test_constant_signal_holds_value_and_respects_range(
    time: float, value: float, expected: float
) -> None:
    channel = AnalogChannel(
        id=0,
        name="constant",
        signal_type=SignalType.CUSTOM,
        constant_value=value,
        min_value=-10.0,
        max_value=80.0,
        frequency=17.0,
        amplitude=90.0,
        offset=40.0,
        time=time,
    )
    assert SignalGenerator([channel])._generate_signal(channel) == expected


def test_constant_value_survives_channel_serialization() -> None:
    channel = AnalogChannel(
        id=0, name="constant", signal_type=SignalType.CUSTOM, constant_value=27.5
    )
    loaded = AnalogChannel.from_dict(channel.to_dict())
    assert loaded.signal_type == SignalType.CUSTOM
    assert loaded.constant_value == 27.5


def test_offset_shifts_signal_center_by_percent_of_half_range():
    channel = AnalogChannel(
        id=0,
        name="offset",
        signal_type=SignalType.SINE,
        frequency=1.0,
        amplitude=0.0,
        offset=20.0,
        min_value=0.0,
        max_value=100.0,
        time=0.0,
    )

    value = SignalGenerator([channel])._generate_signal(channel)

    assert value == pytest.approx(60.0)


def test_random_holds_normalized_value_until_next_interval():
    channel = AnalogChannel(
        id=0,
        name="random",
        signal_type=SignalType.RANDOM,
        amplitude=50.0,
        offset=0.0,
        min_value=0.0,
        max_value=100.0,
        time=0.01,
    )
    generator = SignalGenerator([channel])

    with patch(
        "core.signal_generator.random.uniform", side_effect=[0.5, -0.5]
    ) as mocked:
        first = generator._generate_signal(channel)
        channel.current_value = first
        channel.time = 0.09
        held = generator._generate_signal(channel)
        channel.time = 0.10
        next_value = generator._generate_signal(channel)

    assert first == pytest.approx(62.5)
    assert held == pytest.approx(first)
    assert next_value == pytest.approx(37.5)
    assert mocked.call_count == 2


def test_random_applies_offset_after_amplitude_scaling():
    channel = AnalogChannel(
        id=0,
        name="random-offset",
        signal_type=SignalType.RANDOM,
        amplitude=50.0,
        offset=20.0,
        min_value=0.0,
        max_value=100.0,
        time=0.0,
    )

    with patch("core.signal_generator.random.uniform", return_value=0.0):
        value = SignalGenerator([channel])._generate_signal(channel)

    assert value == pytest.approx(60.0)
