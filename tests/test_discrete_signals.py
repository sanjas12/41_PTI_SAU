import pytest
from PyQt5.QtWidgets import QApplication

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from scenario.scenario_engine import ScenarioEngine
from scenario.scenario_graph import NODE_WIDTH, ScenarioGraphScene, node_header_color
from scenario.scenario_model import Scenario, ScenarioStep
from scenario.scenario_widget import ScenarioWidget, StepEditDialog


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


def test_add_step_menu_separates_analog_and_discrete_signals():
    app = QApplication.instance() or QApplication([])
    generator = SignalGenerator([make_channel(SignalType.SINE, 0.0)])
    widget = ScenarioWidget(generator, ScenarioEngine(generator))

    action_names = [action.text() for action in widget.add_step_btn.menu().actions()]

    assert action_names == ["Аналоговый сигнал", "Дискретный сигнал"]
    widget.close()
    app.processEvents()


def test_discrete_step_dialog_contains_only_discrete_types():
    app = QApplication.instance() or QApplication([])
    generator = SignalGenerator([make_channel(SignalType.SINE, 0.0)])
    dialog = StepEditDialog(generator, signal_types=SignalType.get_discrete_types())

    available_types = {
        dialog.type_combo.itemData(index) for index in range(dialog.type_combo.count())
    }

    assert available_types == {
        signal_type.name.capitalize() for signal_type in SignalType.get_discrete_types()
    }
    dialog.close()
    app.processEvents()


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


def test_scenario_playhead_tracks_progress_between_steps():
    app = QApplication.instance() or QApplication([])
    first = ScenarioStep(channel_id=0, signal_type="Sine", position_x=0.0)
    second = ScenarioStep(channel_id=0, signal_type="Sine", position_x=250.0)
    first.duration = 5.0
    second.duration = 5.0
    scenario = Scenario(steps=[first, second])
    scenario.add_connection(first.id, second.id)
    scene = ScenarioGraphScene()
    scene.set_scenario(scenario)

    scene.set_playhead(25.0, 2.5)

    assert scene.playhead_line is not None
    assert scene.playhead_label is not None
    expected_x = NODE_WIDTH / 2.0
    assert scene.playhead_line.line().x1() == pytest.approx(expected_x)
    assert scene.playhead_label.text() == "00:02"
    assert scene.nodes[first.id].pos().x() == 0.0
    assert scene.nodes[second.id].pos().x() == 250.0
    assert scene.duration_bars[first.id].rect().width() == pytest.approx(NODE_WIDTH)

    scene.nodes[second.id].setPos(480.0, 30.0)
    assert second.position_x == 480.0
    assert scene.duration_bars[second.id].rect().x() == 480.0
    app.processEvents()


def test_scenario_graph_can_be_reloaded_in_the_same_scene():
    app = QApplication.instance() or QApplication([])
    scene = ScenarioGraphScene()
    original = Scenario(
        steps=[ScenarioStep(channel_id=0, signal_type="Sine", position_x=75.0)]
    )
    loaded = Scenario(
        steps=[ScenarioStep(channel_id=0, signal_type="Sine", position_x=320.0)]
    )

    scene.set_scenario(original)
    scene.set_scenario(loaded)

    loaded_node = scene.nodes[loaded.steps[0].id]
    assert loaded_node.pos().x() == 320.0
    assert scene.playhead_line is not None
    assert scene.playhead_label is not None
    app.processEvents()
