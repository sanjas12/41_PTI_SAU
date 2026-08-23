import pytest

from scenario.scenario_model import (
    TRIGGER_ALL,
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
