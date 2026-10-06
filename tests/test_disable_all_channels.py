from pathlib import Path

import pytest
from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow


def test_disable_all_unchecks_every_channel_and_saves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        MainWindow, "_get_config_path", lambda self: str(tmp_path / "channels.json")
    )
    window = MainWindow()
    try:
        window.channel_widgets[0].enabled_check.setChecked(False)
        window.toolbar.disable_all_action.trigger()
        assert all(not channel.enabled for channel in window.generator.channels)
        assert all(
            not widget.enabled_check.isChecked() for widget in window.channel_widgets
        )
        assert all(
            not settings["enabled"]
            for settings in window.channel_repository.load().values()
        )
        window.toolbar.disable_all_action.trigger()
        assert all(not channel.enabled for channel in window.generator.channels)
        window.request_channel_mode("scenario")
        assert not window.toolbar.disable_all_action.isVisible()
        window.generator.channels[0].enabled = True
        window.disable_all_channels()
        assert window.generator.channels[0].enabled
    finally:
        window.close()
        app.processEvents()
