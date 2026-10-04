from pathlib import Path

import pytest
from PyQt5.QtWidgets import QApplication

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from scenario.scenario_model import Scenario, ScenarioStep
from ui.main_window import MainWindow


@pytest.mark.parametrize("mode", ["manual", "scenario"])
@pytest.mark.parametrize("reset_paused", [False, True])
def test_toolbar_pause_resume_stop_and_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, reset_paused: bool
) -> None:
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        MainWindow, "_get_config_path", lambda self: str(tmp_path / "channels.json")
    )
    window = MainWindow()
    engine = window.scenario_engine
    toolbar = window.toolbar
    try:
        if mode == "scenario":
            window.scenario_widget.scenario = Scenario(
                steps=[ScenarioStep(channel_id=0, signal_type="Sine", duration=10.0)]
            )
            window.request_channel_mode("scenario")
        toolbar.play_action.trigger()
        assert window.timer.isActive()
        assert toolbar.pause_action.isEnabled()
        assert toolbar.stop_action.isEnabled()
        assert not toolbar.play_action.isEnabled()
        toolbar.pause_action.trigger()
        assert not window.timer.isActive()
        assert "Возобновить" in toolbar.pause_action.text()
        toolbar.pause_action.trigger()
        assert window.timer.isActive()
        toolbar.stop_action.trigger()
        assert not window.timer.isActive()
        assert toolbar.play_action.isEnabled()
        assert not toolbar.pause_action.isEnabled()
        assert not toolbar.stop_action.isEnabled()
        toolbar.play_action.trigger()
        if mode == "scenario":
            engine._update()
            assert engine.get_progress() > 0
        channel = window.generator.channels[0]
        channel.time = 5.0
        channel.current_value = 75.0
        if reset_paused:
            toolbar.pause_action.trigger()
        toolbar.reset_action.trigger()
        assert not window.timer.isActive()
        assert channel.time == 0.0
        assert channel.current_value == 0.0
        assert toolbar.play_action.isEnabled()
        assert not engine.is_running()
        assert engine.get_progress() == 0.0
        toolbar.play_action.trigger()
        assert window.timer.isActive()
    finally:
        engine.timer.stop()
        window.close()
        app.processEvents()


def test_reset_restarts_toggle_from_initial_state() -> None:
    channel = AnalogChannel(
        id=0,
        name="toggle",
        signal_type=SignalType.TOGGLE,
        frequency=1.0,
        min_value=0.0,
        max_value=1.0,
    )
    generator = SignalGenerator([channel])
    channel.time = 5.0
    assert generator._generate_signal(channel) == 1.0
    generator.reset()
    assert not channel.discrete_value
    channel.time = 0.5
    assert generator._generate_signal(channel) == 0.0
    channel.time = 1.0
    assert generator._generate_signal(channel) == 1.0
