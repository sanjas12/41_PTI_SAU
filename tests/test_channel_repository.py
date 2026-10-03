import json
from pathlib import Path

import pytest

from core.channel import AnalogChannel
from core.channel_repository import ChannelRepository
from core.signal_types import SignalType


def test_missing_configuration_returns_defaults(tmp_path: Path) -> None:
    assert ChannelRepository(str(tmp_path / "missing.json")).load() == {}


def test_saved_configuration_preserves_existing_format(tmp_path: Path) -> None:
    path = tmp_path / "channels.json"
    channel = AnalogChannel(
        id=3,
        name="Канал",
        signal_type=SignalType.SINE,
        output_device="plc",
        output_address=6,
    )
    repository = ChannelRepository(str(path))
    repository.save([channel])
    expected = channel.to_dict()
    expected.pop("id")
    assert repository.load() == {"3": expected}
    assert json.loads(path.read_text(encoding="utf-8")) == {"3": expected}
    assert "Канал" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("text", ["", "{broken", "[]", '{"0": null}'])
def test_invalid_configuration_is_reported(tmp_path: Path, text: str) -> None:
    path = tmp_path / "channels.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        ChannelRepository(str(path)).load()


def test_save_error_is_propagated(tmp_path: Path) -> None:
    repository = ChannelRepository(str(tmp_path))
    with pytest.raises(OSError):
        repository.save([])


def test_main_window_restores_saved_channels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PyQt5.QtWidgets import QApplication

    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    path = tmp_path / "channels.json"
    monkeypatch.setattr(MainWindow, "_get_config_path", lambda self: str(path))
    window = MainWindow()
    try:
        channel = window.generator.channels[0]
        channel.name = "Сохранённый канал"
        channel.output_device = "plc"
        channel.output_address = 6
        assert window._save_channels_config()
    finally:
        window.close()
    restored = MainWindow()
    try:
        channel = restored.generator.channels[0]
        assert channel.name == "Сохранённый канал"
        assert (channel.output_device, channel.output_address) == ("plc", 6)
        assert not restored.active_output_interface.is_connected()
    finally:
        restored.close()
        app.processEvents()
