from pathlib import Path

import pytest
from PyQt5.QtWidgets import QApplication

from scenario.scenario_model import Scenario, ScenarioStep
from ui.main_window import MainWindow


def test_toolbar_progress_follows_scenario_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        MainWindow, "_get_config_path", lambda self: str(tmp_path / "channels.json")
    )
    window = MainWindow()
    engine = window.scenario_engine
    toolbar = window.toolbar
    try:
        actions = toolbar.actions()
        assert (
            actions[actions.index(toolbar.reset_action) + 1]
            is toolbar.scenario_progress_action
        )
        assert not toolbar.scenario_progress_action.isVisible()
        window.scenario_widget.scenario = Scenario(
            steps=[ScenarioStep(channel_id=0, signal_type="Sine", duration=1.0)]
        )
        window.request_channel_mode("scenario")
        assert toolbar.scenario_progress_action.isVisible()
        toolbar.play_action.trigger()
        for _ in range(5):
            engine._update()
        progress = toolbar.scenario_progress.value()
        assert 0 < progress < 100
        toolbar.pause_action.trigger()
        assert toolbar.scenario_progress.value() == progress
        toolbar.stop_action.trigger()
        assert toolbar.scenario_progress.value() == 0
        toolbar.play_action.trigger()
        for _ in range(25):
            engine._update()
        assert toolbar.scenario_progress.value() == 100
        assert toolbar.scenario_progress.format() == "Сценарий завершён"
        toolbar.reset_action.trigger()
        assert toolbar.scenario_progress.value() == 0
        window.request_channel_mode("manual")
        assert not toolbar.scenario_progress_action.isVisible()
    finally:
        engine.timer.stop()
        window.close()
        app.processEvents()
