from pathlib import Path
from typing import List, Tuple
from unittest.mock import Mock

import pytest
from PyQt5.QtWidgets import QApplication

from application.controller import ApplicationController
from core.signal_generator import SignalGenerator
from devices.device_manager import DeviceManager


@pytest.fixture
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def setup_controller(app: QApplication) -> Tuple[ApplicationController, Mock]:
    interface = Mock()
    interface.is_connected.return_value = False
    interface.validate_manual_output_map.return_value = []
    devices = DeviceManager(SignalGenerator(), interfaces={"owen": interface})
    return ApplicationController(devices), interface


def test_manual_lifecycle_and_duplicate_commands(setup_controller: tuple) -> None:
    controller, _ = setup_controller
    states: List[Tuple[bool, bool]] = []
    controller.state_changed.connect(
        lambda: states.append((controller.is_running, controller.is_paused))
    )
    controller.pause_generation()
    controller.resume_generation()
    controller.stop_generation()
    assert not states
    controller.start_generation()
    controller.start_generation()
    controller.pause_generation()
    controller.pause_generation()
    controller.start_generation()
    controller.resume_generation()
    controller.resume_generation()
    controller.pause_generation()
    controller.stop_generation()
    controller.stop_generation()
    assert states == [
        (True, False),
        (True, True),
        (True, False),
        (True, True),
        (False, False),
    ]


def test_invalid_output_map_blocks_start(setup_controller: tuple) -> None:
    controller, interface = setup_controller
    interface.is_connected.return_value = True
    interface.validate_manual_output_map.return_value = ["Конфликт выходов"]
    errors: List[str] = []
    controller.validation_failed.connect(errors.append)
    controller.start_generation()
    assert not controller.is_running
    assert not controller.timer.isActive()
    assert len(errors) == 1
    assert "Конфликт выходов" in errors[0]
    interface.validate_manual_output_map.return_value = []
    controller.start_generation()
    assert controller.is_running


def test_offline_generation_does_not_validate_hardware(setup_controller: tuple) -> None:
    controller, interface = setup_controller
    controller.start_generation()
    interface.validate_manual_output_map.assert_not_called()
    assert controller.is_running


@pytest.mark.parametrize(
    "running,paused,scenario_view,engine_mode,expected",
    [
        (False, False, False, "manual", False),
        (True, False, False, "manual", True),
        (True, True, False, "manual", False),
        (True, False, True, "manual", False),
        (False, False, True, "scenario", True),
        (True, True, True, "scenario", True),
        (False, False, True, "paused", False),
        (True, False, True, "paused", False),
    ],
)
def test_timer_and_outputs_follow_manual_and_scenario_state(
    setup_controller: tuple,
    running: bool,
    paused: bool,
    scenario_view: bool,
    engine_mode: str,
    expected: bool,
) -> None:
    controller, interface = setup_controller
    if running:
        controller.start_generation()
    if paused:
        controller.pause_generation()
    try:
        assert controller.synchronize(scenario_view, engine_mode) is expected
        assert controller.timer.isActive() is expected
        interface.set_output_enabled.assert_called_once_with(expected)
        if expected:
            assert controller.timer.interval() == 10
    finally:
        controller.close()


def test_synchronize_stops_active_timer(setup_controller: tuple) -> None:
    controller, interface = setup_controller
    controller.start_generation()
    controller.synchronize(False, "manual")
    controller.pause_generation()
    assert not controller.synchronize(False, "manual")
    assert not controller.timer.isActive()
    interface.set_output_enabled.assert_called_with(False)


def test_window_delegates_commands_and_keeps_timer_in_sync(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ui.main_window import MainWindow

    monkeypatch.setattr(
        MainWindow, "_get_config_path", lambda self: str(tmp_path / "channels.json")
    )
    window = MainWindow()
    try:
        assert window.timer is window.controller.timer
        assert not window.timer.isActive()
        window.start_generation()
        assert window.is_running and window.timer.isActive()
        window.pause_generation()
        assert window.is_paused and not window.timer.isActive()
        window.resume_generation()
        assert not window.is_paused and window.timer.isActive()
        window.request_channel_mode("scenario")
        assert not window.timer.isActive()
        window.request_channel_mode("manual")
        assert window.timer.isActive()
        window.stop_generation()
        assert not window.is_running and not window.timer.isActive()
        window.start_generation()
    finally:
        window.close()
        assert not window.timer.isActive()
        app.processEvents()


def test_scenario_lifecycle_controls_shared_timer(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scenario.scenario_model import Scenario, ScenarioStep
    from ui.main_window import MainWindow

    monkeypatch.setattr(
        MainWindow, "_get_config_path", lambda self: str(tmp_path / "channels.json")
    )
    window = MainWindow()
    engine = window.scenario_engine
    try:
        engine.load_scenario(
            Scenario(
                steps=[ScenarioStep(channel_id=0, signal_type="Sine", duration=10.0)]
            )
        )
        engine.start_scenario()
        assert window.timer.isActive()
        assert not window.is_running
        engine.pause_scenario()
        assert not window.timer.isActive()
        engine.resume_scenario()
        assert window.timer.isActive()
        engine.stop_scenario()
        assert not window.timer.isActive()
    finally:
        engine.timer.stop()
        window.close()
        app.processEvents()
