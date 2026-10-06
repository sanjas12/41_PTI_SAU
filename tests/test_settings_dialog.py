from pathlib import Path

import pytest
from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QApplication, QTabWidget

from ui.interval_control import IntervalControl
from ui.settings_dialog import SettingsDialog
from ui.themes import build_stylesheet


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("large", [False, True])
def test_settings_layout_and_interval_signals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, theme: str, large: bool
) -> None:
    app = QApplication.instance() or QApplication([])
    previous_style = app.styleSheet()
    monkeypatch.setattr(
        IntervalControl,
        "_get_config_path",
        lambda self: str(tmp_path / "intervals.json"),
    )
    app.setStyleSheet(build_stylesheet(theme, large=large))
    dialog = SettingsDialog()
    control = dialog.interval_control
    signal_values = []
    device_values = []
    dialog.signal_interval_changed.connect(signal_values.append)
    dialog.plc_interval_changed.connect(device_values.append)
    try:
        dialog.show()
        app.processEvents()
        assert not control.isCheckable()
        assert not control.styleSheet()
        tabs = control.findChild(QTabWidget)
        for index, buttons in enumerate(
            [control.preset_buttons, control.plc_preset_buttons]
        ):
            tabs.setCurrentIndex(index)
            app.processEvents()
            rectangles = []
            for button in buttons + [control.save_btn, dialog.close_btn]:
                assert button.isVisible()
                assert button.width() >= button.minimumSizeHint().width()
                assert button.height() >= button.minimumSizeHint().height()
                assert not button.styleSheet()
                rect = button.rect()
                rect.moveTopLeft(button.mapTo(dialog, QPoint(0, 0)))
                assert dialog.rect().contains(rect)
                assert all(not rect.intersects(other) for other in rectangles)
                rectangles.append(rect)
        control.set_signal_interval(0.05)
        control.set_plc_interval(0.5)
        assert signal_values[-1] == 0.05
        assert device_values[-1] == 0.5
    finally:
        dialog.close()
        app.setStyleSheet(previous_style)
        app.processEvents()
