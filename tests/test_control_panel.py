from ui.control_panel import format_scenario_time


def test_format_scenario_time_uses_minutes_and_seconds():
    assert format_scenario_time(65.0) == "01:05"


def test_format_scenario_time_adds_hours_when_needed():
    assert format_scenario_time(3661.0) == "01:01:01"


def test_format_scenario_time_does_not_show_negative_values():
    assert format_scenario_time(-3.0) == "00:00"
