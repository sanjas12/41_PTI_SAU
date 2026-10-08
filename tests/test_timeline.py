from typing import Iterator

import pytest
from PyQt5.QtWidgets import QApplication

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from scenario.animation import AnimationTrack, Keyframe
from scenario.scenario_engine import ScenarioEngine, ScenarioMode
from scenario.scenario_model import Scenario, ScenarioStep
from scenario.scenario_widget import ScenarioWidget
from scenario.timeline_widget import KeyframeDialog, KeyMarker, TimelineWidget


@pytest.fixture
def app() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


def make_scenario() -> Scenario:
    return Scenario(
        timeline_duration=1.0,
        tracks=[
            AnimationTrack(0, "signal_type", [Keyframe(0.0, "CUSTOM", "hold")]),
            AnimationTrack(
                0, "constant_value", [Keyframe(0.0, 10.0), Keyframe(1.0, 30.0)]
            ),
        ],
    )


def test_timeline_only_runs_pauses_and_restores_manual_state(app: QApplication) -> None:
    channel = AnalogChannel(id=0, name="channel", constant_value=7.0)
    engine = ScenarioEngine(SignalGenerator([channel]))
    engine.load_scenario(make_scenario())
    engine.start_scenario()
    engine.timer.stop()
    assert engine.mode == ScenarioMode.SCENARIO
    assert channel.signal_type == SignalType.CUSTOM
    assert channel.constant_value == 10.0
    for _ in range(10):
        engine._update()
    assert channel.constant_value == pytest.approx(20.0)
    engine.pause_scenario()
    engine._update()
    assert channel.constant_value == pytest.approx(20.0)
    engine.resume_scenario()
    engine.timer.stop()
    engine.stop_scenario()
    assert channel.constant_value == 7.0
    assert channel.signal_type == SignalType.SINE


def test_completion_and_loop_reset_tracks(app: QApplication) -> None:
    channel = AnalogChannel(id=0, name="channel", constant_value=7.0)
    engine = ScenarioEngine(SignalGenerator([channel]))
    scenario = make_scenario()
    engine.load_scenario(scenario)
    engine.start_scenario()
    engine.timer.stop()
    for _ in range(20):
        engine._update()
    assert engine.mode == ScenarioMode.MANUAL
    assert channel.constant_value == 7.0
    assert not channel.enabled
    scenario.loop = True
    engine.start_scenario()
    engine.timer.stop()
    for _ in range(20):
        engine._update()
    assert engine.mode == ScenarioMode.SCENARIO
    assert channel.constant_value == 10.0
    assert channel.enabled
    engine.reset_scenario()
    assert channel.constant_value == 7.0
    assert engine._scenario_time == 0.0


def test_global_keys_override_graph_step_and_continue_after_it(
    app: QApplication,
) -> None:
    channel = AnalogChannel(id=0, name="channel", constant_value=7.0)
    engine = ScenarioEngine(SignalGenerator([channel]))
    scenario = make_scenario()
    scenario.steps = [
        ScenarioStep(
            channel_id=0, signal_type="Custom", constant_value=50.0, duration=0.1
        )
    ]
    engine.load_scenario(scenario)
    engine.start_scenario()
    engine.timer.stop()
    assert channel.constant_value == 10.0
    engine._update()
    engine._update()
    assert channel.enabled
    assert channel.constant_value == pytest.approx(12.0)
    engine.stop_scenario()


def test_editor_moves_deletes_keys_and_locks_during_playback(app: QApplication) -> None:
    channel = AnalogChannel(id=0, name="channel", constant_value=7.0)
    editor = TimelineWidget(SignalGenerator([channel]))
    scenario = make_scenario()
    editor.set_scenario(scenario)
    try:
        markers = [item for item in editor.scene.items() if isinstance(item, KeyMarker)]
        assert len(markers) == 3
        track = scenario.tracks[1]
        editor.move_key(track, track.keyframes[1], 2.0)
        app.processEvents()
        assert track.keyframes[1].time == 2.0
        assert scenario.get_total_duration() == 2.0
        editor.set_playhead(1.0)
        assert "20" in editor.preview.text()
        assert channel.constant_value == 7.0  # Предпросмотр не меняет выходы.
        editor.set_locked(True)
        editor.delete_track()
        editor.move_key(track, track.keyframes[1], 3.0)
        assert len(scenario.tracks) == 2
        assert track.keyframes[1].time == 2.0
        editor.set_locked(False)
        editor.track_combo.setCurrentIndex(1)
        editor.delete_track()
        assert len(scenario.tracks) == 1
    finally:
        editor.close()


def test_scenario_widget_has_shared_timeline_tab(app: QApplication) -> None:
    generator = SignalGenerator([AnalogChannel(id=0, name="channel")])
    engine = ScenarioEngine(generator)
    widget = ScenarioWidget(generator, engine)
    try:
        widget.scenario = make_scenario()
        widget.update_graph()
        assert widget.editor_tabs.count() == 2
        assert widget.timeline.scenario is widget.scenario
        widget.on_mode_changed("paused")
        assert widget.timeline.locked
        widget.on_mode_changed("manual")
        assert not widget.timeline.locked
        widget.play_scenario()
        engine.timer.stop()
        assert engine.mode == ScenarioMode.SCENARIO
        assert widget.timeline.locked
        engine.stop_scenario()
        assert not widget.timeline.locked
    finally:
        widget.close()


def test_discrete_parameter_keys_and_enabled_state_restore(app: QApplication) -> None:
    channel = AnalogChannel(id=0, name="channel", enabled=False, duty_cycle=40.0)
    engine = ScenarioEngine(SignalGenerator([channel]))
    scenario = Scenario(
        timeline_duration=1.0,
        tracks=[
            AnimationTrack(0, "signal_type", [Keyframe(0.0, "PWM", "hold")]),
            AnimationTrack(
                0,
                "enabled",
                [Keyframe(0.0, True, "hold"), Keyframe(0.5, False, "hold")],
            ),
            AnimationTrack(0, "duty_cycle", [Keyframe(0.0, 20.0), Keyframe(1.0, 80.0)]),
            AnimationTrack(0, "pulse_width", [Keyframe(0.0, 0.01), Keyframe(1.0, 0.1)]),
        ],
    )
    engine.load_scenario(scenario)
    engine.start_scenario()
    engine.timer.stop()
    assert channel.signal_type == SignalType.PWM
    assert channel.enabled
    for _ in range(11):
        engine._update()
    assert not channel.enabled
    assert channel.duty_cycle == pytest.approx(53.0)
    engine.stop_scenario()
    assert not channel.enabled
    assert channel.duty_cycle == 40.0
    assert channel.pulse_width == 1.0


def test_key_dialog_uses_hold_for_routing_and_moving_duplicates_reverts(
    app: QApplication,
) -> None:
    editor = TimelineWidget(SignalGenerator([AnalogChannel(id=0, name="channel")]))
    track = AnimationTrack(
        0,
        "output_device",
        [Keyframe(0.0, "plc", "hold"), Keyframe(1.0, "owen", "hold")],
    )
    editor.set_scenario(Scenario(tracks=[track]))
    dialog = KeyframeDialog(track, track.keyframes[0], editor)
    try:
        assert dialog.interpolation.count() == 1
        assert dialog.get_key().interpolation == "hold"
        assert dialog.get_key().value == "plc"
        editor.move_key(track, track.keyframes[1], 0.0)
        app.processEvents()
        assert track.keyframes[1].time == 1.0
    finally:
        dialog.close()
        editor.close()


def test_invalid_timeline_does_not_start_or_modify_channels(app: QApplication) -> None:
    channel = AnalogChannel(id=0, name="channel", constant_value=7.0)
    engine = ScenarioEngine(SignalGenerator([channel]))
    scenario = make_scenario()
    scenario.tracks.append(
        AnimationTrack(0, "mu210_module", [Keyframe(0.0, 1.5, "hold")])
    )
    errors = []
    engine.validation_failed.connect(errors.append)
    engine.load_scenario(scenario)
    engine.start_scenario()
    assert errors
    assert engine.mode == ScenarioMode.MANUAL
    assert channel.constant_value == 7.0
    assert not engine.timer.isActive()
