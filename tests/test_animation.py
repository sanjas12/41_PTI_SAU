import math
from typing import List

import pytest

from core.channel import AnalogChannel
from scenario.animation import AnimationTrack, Keyframe
from scenario.scenario_model import Scenario
from scenario.timeline_state import apply_tracks, validate_timeline


def test_linear_keys_use_baseline_before_first_and_hold_after_last() -> None:
    track = AnimationTrack(
        0, "constant_value", [Keyframe(1.0, 10.0), Keyframe(3.0, 30.0)]
    )
    assert track.evaluate(0.5, 7.0) == 7.0
    assert track.evaluate(1.0, 7.0) == 10.0
    assert track.evaluate(2.0, 7.0) == 20.0
    assert track.evaluate(3.0, 7.0) == 30.0
    assert track.evaluate(9.0, 7.0) == 30.0


def test_each_segment_uses_left_key_interpolation() -> None:
    track = AnimationTrack(
        0,
        "amplitude",
        [
            Keyframe(0.0, 10.0, "hold"),
            Keyframe(2.0, 30.0),
            Keyframe(4.0, 50.0),
        ],
    )
    assert track.evaluate(1.0, 0.0) == 10.0
    assert track.evaluate(2.0, 0.0) == 30.0
    assert track.evaluate(3.0, 0.0) == 40.0


@pytest.mark.parametrize(
    "keys",
    [
        [Keyframe(-1.0, 10.0)],
        [Keyframe(math.nan, 10.0)],
        [Keyframe(0.0, math.inf)],
        [Keyframe(0.0, 10.0), Keyframe(0.0, 20.0)],
        [Keyframe(0.0, 101.0)],
        [Keyframe(0.0, 10.0, "bezier")],
    ],
)
def test_invalid_keys_are_rejected(keys: List[Keyframe]) -> None:
    with pytest.raises(ValueError):
        AnimationTrack(0, "amplitude", keys).validate()


def test_routing_is_applied_together_and_only_as_hold() -> None:
    channels = {
        0: AnalogChannel(id=0, name="channel", output_device="plc", output_address=0)
    }
    scenario = Scenario(
        tracks=[
            AnimationTrack(0, "output_device", [Keyframe(1.0, "owen", "hold")]),
            AnimationTrack(0, "output_address", [Keyframe(1.0, 3004, "hold")]),
            AnimationTrack(0, "mu210_module", [Keyframe(1.0, 2, "hold")]),
        ]
    )
    assert validate_timeline(scenario, list(channels.values()), 2) == []
    apply_tracks(scenario, 0.5, channels)
    assert channels[0].output_device == "plc"
    apply_tracks(scenario, 1.0, channels)
    assert (
        channels[0].output_device,
        channels[0].output_address,
        channels[0].mu210_register,
    ) == ("owen", 3004, 3004)
    assert channels[0].mu210_module == 2
    with pytest.raises(ValueError):
        AnimationTrack(0, "output_device", [Keyframe(1.0, "plc")]).validate()


def test_routing_conflicts_missing_modules_and_ranges_are_rejected() -> None:
    channels = [AnalogChannel(id=0, name="first"), AnalogChannel(id=1, name="second")]
    scenario = Scenario(
        tracks=[
            AnimationTrack(0, "constant_value", [Keyframe(0.0, 10.0)]),
            AnimationTrack(1, "output_address", [Keyframe(1.0, 3000, "hold")]),
            AnimationTrack(1, "mu210_module", [Keyframe(2.0, 3, "hold")]),
            AnimationTrack(0, "min_value", [Keyframe(3.0, 150.0)]),
        ]
    )
    errors = validate_timeline(scenario, channels, 2)
    assert any("конфликт" in error for error in errors)
    assert any("отсутствует" in error for error in errors)
    assert any("минимум" in error for error in errors)
    assert channels[1].output_address == 3001


def test_animation_serialization_and_old_scenarios() -> None:
    scenario = Scenario(
        timeline_duration=10.0,
        tracks=[
            AnimationTrack(
                0, "frequency", [Keyframe(0.0, 1.0), Keyframe(10.0, 2.0, "hold")]
            ),
        ],
    )
    loaded = Scenario.from_dict(scenario.to_dict())
    assert loaded.to_dict() == scenario.to_dict()
    assert loaded.get_total_duration() == 10.0
    assert Scenario.from_dict({"steps": []}).tracks == []
    assert Scenario().get_total_duration() == 0.0
