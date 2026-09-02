import pytest

from scenario.scenario_model import (
    TRIGGER_ALL,
    TRIGGER_ANY,
    TRIGGER_SPECIFIC,
    Scenario,
    ScenarioStep,
)


def make_step(step_id: str) -> ScenarioStep:
    return ScenarioStep(channel_id=0, signal_type="Sine", id=step_id)


def test_legacy_steps_are_imported_as_a_linear_graph():
    scenario = Scenario.from_dict(
        {
            "version": "1.0",
            "steps": [
                {"channel_id": 0, "signal_type": "Sine"},
                {"channel_id": 1, "signal_type": "Square"},
            ],
        }
    )

    assert scenario.version == "2.0"
    assert len(scenario.connections) == 1
    assert scenario.connections[0].source_id == scenario.steps[0].id
    assert scenario.connections[0].target_id == scenario.steps[1].id


def test_connection_that_creates_cycle_is_rejected():
    first = make_step("first")
    second = make_step("second")
    scenario = Scenario(steps=[first, second])
    scenario.add_connection(first.id, second.id)

    with pytest.raises(ValueError, match="цикл"):
        scenario.add_connection(second.id, first.id)


def test_graph_settings_survive_serialization():
    first = make_step("first")
    second = make_step("second")
    second.position_x = 250.0
    second.position_y = 80.0
    second.trigger_mode = TRIGGER_ALL
    scenario = Scenario(steps=[first, second])
    scenario.add_connection(first.id, second.id)

    restored = Scenario.from_dict(scenario.to_dict())

    assert restored.to_dict() == scenario.to_dict()


def test_parallel_steps_receive_branch_numbers():
    first = make_step("first")
    upper = make_step("upper")
    lower = make_step("lower")
    final = make_step("final")
    scenario = Scenario(steps=[first, upper, lower, final])
    scenario.add_connection(first.id, upper.id)
    scenario.add_connection(first.id, lower.id)
    scenario.add_connection(upper.id, final.id)
    scenario.add_connection(lower.id, final.id)

    assert scenario.get_step_labels() == {
        "first": "1",
        "upper": "2.1",
        "lower": "2.2",
        "final": "3",
    }


def test_linear_steps_keep_integer_numbers():
    first = make_step("first")
    second = make_step("second")
    third = make_step("third")
    scenario = Scenario(steps=[first, second, third])
    scenario.add_connection(first.id, second.id)
    scenario.add_connection(second.id, third.id)

    assert scenario.get_step_labels() == {
        "first": "1",
        "second": "2",
        "third": "3",
    }


def test_total_duration_uses_longest_parallel_branch():
    first = make_step("first")
    first.duration = 5.0
    short = make_step("short")
    short.duration = 3.0
    long = make_step("long")
    long.duration = 7.0
    scenario = Scenario(steps=[first, short, long])
    scenario.add_connection(first.id, short.id)
    scenario.add_connection(first.id, long.id)

    assert scenario.get_total_duration() == pytest.approx(12.0)


def test_step_timings_describe_parallel_branch_intervals():
    first = make_step("first")
    first.duration = 5.0
    short = make_step("short")
    short.duration = 3.0
    long = make_step("long")
    long.duration = 7.0
    scenario = Scenario(steps=[first, short, long])
    scenario.add_connection(first.id, short.id)
    scenario.add_connection(first.id, long.id)

    assert scenario.get_step_timings() == {
        "first": (0.0, 5.0),
        "short": (5.0, 8.0),
        "long": (5.0, 12.0),
    }


@pytest.mark.parametrize(
    ("trigger_mode", "trigger_step_id", "expected"),
    [
        (TRIGGER_ALL, None, 17.0),
        (TRIGGER_ANY, None, 13.0),
        (TRIGGER_SPECIFIC, "short", 13.0),
        (TRIGGER_SPECIFIC, "long", 17.0),
    ],
)
def test_total_duration_respects_join_condition(
    trigger_mode: str, trigger_step_id: str, expected: float
):
    first = make_step("first")
    first.duration = 5.0
    short = make_step("short")
    short.duration = 3.0
    long = make_step("long")
    long.duration = 7.0
    final = make_step("final")
    final.duration = 5.0
    final.trigger_mode = trigger_mode
    final.trigger_step_id = trigger_step_id
    scenario = Scenario(steps=[first, short, long, final])
    scenario.add_connection(first.id, short.id)
    scenario.add_connection(first.id, long.id)
    scenario.add_connection(short.id, final.id)
    scenario.add_connection(long.id, final.id)

    assert scenario.get_total_duration() == pytest.approx(expected)
