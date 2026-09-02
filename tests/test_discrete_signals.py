import pytest

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from scenario.scenario_engine import ScenarioEngine
from scenario.scenario_graph import node_header_color
from scenario.scenario_model import Scenario, ScenarioStep


def make_channel(signal_type: SignalType, time: float) -> AnalogChannel:
    return AnalogChannel(
        id=0,
        name="discrete",
        signal_type=signal_type,
        frequency=1.0,
        min_value=0.0,
        max_value=1.0,
        time=time,
    )


@pytest.mark.parametrize(
    ("time", "expected"),
    [(0.1, 1.0), (0.6, 0.0), (1.1, 1.0)],
)
def test_discrete_generates_binary_square_wave(time: float, expected: float):
    channel = make_channel(SignalType.DISCRETE, time)

    value = SignalGenerator([channel])._generate_signal(channel)

    assert value == expected
    assert channel.discrete_value is bool(expected)


def test_pwm_respects_duty_cycle():
    channel = make_channel(SignalType.PWM, 0.2)
    channel.duty_cycle = 25.0
    generator = SignalGenerator([channel])

    assert generator._generate_signal(channel) == 1.0
    channel.time = 0.3
    assert generator._generate_signal(channel) == 0.0


def test_pulse_width_may_use_the_whole_period():
    channel = make_channel(SignalType.PULSE, 0.75)
    channel.pulse_width = 0.8

    value = SignalGenerator([channel])._generate_signal(channel)

    assert value == 1.0


def test_discrete_scenario_node_has_a_distinct_header_color():
    assert node_header_color("Pwm").name() == "#4f5f9f"
    assert node_header_color("Sine").name() == "#315f4a"


def test_scenario_applies_discrete_parameters_to_channel():
    channel = make_channel(SignalType.SINE, 0.0)
    generator = SignalGenerator([channel])
    step = ScenarioStep(
        channel_id=0,
        signal_type="Pwm",
        duty_cycle=35.0,
        pulse_width=0.2,
    )
    engine = ScenarioEngine(generator)
    engine.scenario = Scenario(steps=[step])

    engine._apply_graph_step(step)

    assert channel.signal_type == SignalType.PWM
    assert channel.duty_cycle == 35.0
    assert channel.pulse_width == 0.2
