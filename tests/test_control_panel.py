from PyQt5.QtWidgets import QApplication

from ui.control_panel import format_scenario_time
from ui.main_window import MainWindow


def test_format_scenario_time_uses_minutes_and_seconds():
    assert format_scenario_time(65.0) == "01:05"


def test_format_scenario_time_adds_hours_when_needed():
    assert format_scenario_time(3661.0) == "01:01:01"


def test_format_scenario_time_does_not_show_negative_values():
    assert format_scenario_time(-3.0) == "00:00"


def test_main_window_starts_in_stopped_state(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    config_path = tmp_path / "channels.json"
    monkeypatch.setattr(MainWindow, "_get_config_path", lambda _self: str(config_path))

    window = MainWindow()

    assert window.is_running is False
    assert window.is_paused is False
    assert window.timer.isActive() is False
    assert window.status_label.text() == "● Остановлен"
    assert window.control_panel.play_btn.isEnabled() is True
    assert window.control_panel.stop_btn.isEnabled() is False

    window.close()
    app.processEvents()
