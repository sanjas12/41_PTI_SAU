from typing import Any, Dict

import pytest

from core.channel import AnalogChannel
from scenario.scenario_model import ScenarioStep


@pytest.mark.parametrize(
    "device,expected", [("owen", 3000), ("plc", 0), ("simulator", 0)]
)
@pytest.mark.parametrize("include_address", [False, True])
def test_missing_or_null_address_uses_device_default(
    device: str, expected: int, include_address: bool
) -> None:
    data: Dict[str, Any] = {
        "id": 0,
        "name": "channel",
        "channel_id": 0,
        "signal_type": "SINE",
        "output_device": device,
    }
    if include_address:
        data["output_address"] = None
    assert AnalogChannel.from_dict(data).output_address == expected
    assert ScenarioStep.from_dict(data).output_address == expected


def test_explicit_zero_address_is_preserved() -> None:
    step = ScenarioStep.from_dict(
        {
            "channel_id": 0,
            "signal_type": "SINE",
            "output_device": "plc",
            "output_address": 0,
        }
    )
    assert step.output_address == 0


def test_legacy_scenario_with_null_register_loads_default_address() -> None:
    step = ScenarioStep.from_dict(
        {
            "channel_id": 0,
            "signal_type": "SINE",
            "mu210_register": None,
        }
    )
    assert step.output_address == 3000
    assert step.mu210_register is None
