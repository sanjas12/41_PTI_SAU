from pathlib import Path
from typing import Iterator

import pytest
from PyQt5.QtWidgets import QApplication, QDialog

from core.device_channels import create_device_channels
from core.signal_types import SignalType
from ui.connection_dialog import ConnectionDialog
from ui.main_window import MainWindow


@pytest.fixture
def app() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


@pytest.mark.parametrize("modules", [1, 2, 3])
def test_mu210_profile_has_eight_analog_outputs_per_module(modules: int) -> None:
    channels = create_device_channels("owen", modules, {})
    assert len(channels) == modules * 8
    assert all(channel.signal_type == SignalType.CUSTOM for channel in channels)
    assert all(
        (channel.min_value, channel.max_value) == (0.0, 100.0) for channel in channels
    )
    assert [(channel.mu210_module, channel.output_address) for channel in channels] == [
        (index // 8 + 1, 3000 + index % 8) for index in range(modules * 8)
    ]


@pytest.mark.parametrize("device", ["plc", "simulator"])
def test_plc_profile_uses_existing_real_register_map(device: str) -> None:
    channels = create_device_channels(device, 1, {})
    assert len(channels) == 20
    assert all(channel.output_device == "plc" for channel in channels)
    assert [channel.output_address for channel in channels] == list(range(0, 40, 2))


def test_profile_preserves_signal_settings_but_does_not_create_discrete_outputs() -> (
    None
):
    channels = create_device_channels(
        "owen",
        1,
        {
            "0": {"name": "Saved", "signal_type": "CUSTOM", "constant_value": 27.5},
            "1": {"signal_type": "PWM"},
            "20": {"signal_type": "PWM"},
        },
    )
    assert channels[0].name == "Saved"
    assert channels[0].constant_value == 27.5
    assert len(channels) == 8
    assert all(channel.signal_type.is_analog() for channel in channels)


def test_valid_manual_binding_is_preserved_without_duplicating_new_outputs() -> None:
    channels = create_device_channels(
        "owen",
        2,
        {"0": {"output_device": "owen", "mu210_module": 2, "output_address": 3007}},
    )
    assert (channels[0].mu210_module, channels[0].output_address) == (2, 3007)
    targets = {(channel.mu210_module, channel.output_address) for channel in channels}
    assert len(targets) == 16


def test_startup_opens_connection_defaults_without_network_or_erasing_saved_channels(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "channels.json"
    path.write_text('{"0": {"name": "Saved"}}', encoding="utf-8")
    original = path.read_bytes()
    monkeypatch.setattr(MainWindow, "_get_config_path", lambda _self: str(path))
    monkeypatch.setattr(ConnectionDialog, "exec_", lambda _self: QDialog.Rejected)
    window = MainWindow(startup_connection=True)
    try:
        window.show()
        app.processEvents()
        assert window.connection_dialog is not None
        assert window.connection_dialog.get_connection_params()["device_type"] == "owen"
        assert not window.generator.channels
        assert not window.active_output_interface.is_connected()
        window._on_device_connected(False)
        assert not window.generator.channels
    finally:
        window.close()
    assert path.read_bytes() == original


def test_successful_connection_rebuilds_channels_and_closes_dialog(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        MainWindow, "_get_config_path", lambda _self: str(tmp_path / "channels.json")
    )
    window = MainWindow(startup_connection=True)
    try:
        window._ensure_connection_dialog()
        interface = window.active_output_interface
        # configure только готовит клиентов; тест не вызывает open и не выходит в сеть.
        interface.configure("127.0.0.1;127.0.0.2", 502, 1)
        window._on_device_connected(True)
        assert len(window.generator.channels) == 16
        assert len(window.channel_widgets) == 16
        assert window.scenario_widget.timeline.channel_combo.count() == 16
        assert window.connection_dialog.result() == QDialog.Accepted
        assert window.discrete_channels_group.isHidden()
        assert not window.timer.isActive()
        assert not window.is_running
    finally:
        window.close()
