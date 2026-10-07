import os
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication, QFrame, QSizePolicy

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from ui.plot_widget import PlotWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_plot_window_centers_on_screen_available_area(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    available = QRect(1920, 40, 1600, 900)

    screen = SimpleNamespace(availableGeometry=lambda: available)
    monkeypatch.setattr(QApplication, "primaryScreen", lambda: screen)
    window = PlotWindow(SignalGenerator([]))
    try:
        assert window.geometry().center() == available.center()
        assert available.contains(window.geometry())
    finally:
        window.close()
        app.processEvents()


def test_constant_plot_shows_value_instead_of_frequency() -> None:
    app = QApplication.instance() or QApplication([])
    channel = AnalogChannel(
        id=0, name="constant", signal_type=SignalType.CUSTOM, constant_value=27.5
    )
    window = PlotWindow(SignalGenerator([channel]))
    try:
        item = window.channels_list.item(0)
        assert "Постоянный" in item.text()
        assert "27.5" in item.text()
        assert "Гц" not in item.toolTip()
        window.add_channel_to_plot(0)
        for _ in range(3):
            channel.current_value = window.generator._generate_signal(channel)
            window.update_plots()
        _times, values = window.plot_widgets[0].channel_data[0].get_data()
        assert np.array_equal(values, np.array([27.5, 27.5, 27.5]))
        channel.constant_value = 150.0
        window._update_channels_list()
        assert "Значение: 100" in window.channels_list.item(0).text()
    finally:
        window.close()
        app.processEvents()


def test_repeated_clear_keeps_legend_attached() -> None:
    app = QApplication.instance() or QApplication([])
    window = PlotWindow(SignalGenerator([AnalogChannel(id=0, name="channel")]))
    try:
        window.add_channel_to_plot(0)
        plot = window.plot_widgets[0]
        for _ in range(3):
            plot.clear_plot()
            assert plot._legend is not None
            assert plot._legend.scene() is not None
            assert not plot._legend.items
            window.add_channel_to_plot(0)
            assert len(plot._legend.items) == 1
        window.apply_theme("light")
        window.apply_theme("dark")
        plot.clear_plot()
        assert plot._legend.scene() is not None
    finally:
        window.close()
        app.processEvents()


def test_plot_acquisition_follows_running_state():
    app = QApplication.instance() or QApplication([])
    generator = SignalGenerator([AnalogChannel(id=0, name="channel")])
    window = PlotWindow(generator)
    window.add_channel_to_plot(0)
    buffer = window.plot_widgets[0].channel_data[0]

    window.set_acquisition_running(False)
    window.update_plots()
    assert buffer.count == 0
    assert window._acquisition_time == 0.0

    window.set_acquisition_running(True)
    window.update_plots()
    assert buffer.count == 1
    assert window._acquisition_time == 0.05

    window.set_acquisition_running(False)
    window.update_plots()
    assert buffer.count == 1
    assert window._acquisition_time == 0.05

    window.close()
    app.processEvents()


def test_plot_window_keeps_service_panels_compact():
    app = QApplication.instance() or QApplication([])
    window = PlotWindow(SignalGenerator([AnalogChannel(id=0, name="channel")]))

    toolbar = window.findChild(QFrame, "toolbar")
    status_bar = window.findChild(QFrame, "statusBar")
    assert toolbar is not None
    assert status_bar is not None
    assert toolbar.sizePolicy().verticalPolicy() == QSizePolicy.Fixed
    assert status_bar.sizePolicy().verticalPolicy() == QSizePolicy.Fixed
    assert toolbar.maximumHeight() == 38
    assert status_bar.maximumHeight() == 28
    assert window.plot_height == 260
    assert window.width() <= 1100
    assert window.height() <= 720
    assert window.minimumSizeHint().width() <= 1100

    window.close()
    app.processEvents()


def test_discrete_channel_is_visible_in_list_while_disabled():
    app = QApplication.instance() or QApplication([])
    channel = AnalogChannel(
        id=4,
        name="discrete",
        signal_type=SignalType.DISCRETE,
        enabled=False,
    )
    window = PlotWindow(SignalGenerator([channel]))

    assert window.channels_list.count() == 1
    assert window.channels_list.item(0).text().startswith("D05:")

    window.close()
    app.processEvents()


@pytest.mark.parametrize("signal_type", SignalType.get_discrete_types())
def test_discrete_channel_is_added_to_plot_as_step_curve(signal_type: SignalType):
    app = QApplication.instance() or QApplication([])
    channel = AnalogChannel(
        id=7,
        name="discrete",
        signal_type=signal_type,
        min_value=0.0,
        max_value=1.0,
    )
    generator = SignalGenerator([channel])
    window = PlotWindow(generator)
    window.add_channel_to_plot(channel.id)
    plot = window.plot_widgets[0]
    assert plot.get_channel_name(channel.id) == "D08 · discrete"

    channel.current_value = 0.0
    window.update_plots()
    channel.current_value = 1.0
    window.update_plots()
    plot.update_plot(window._acquisition_time)

    curve_x, curve_y = plot.curves[channel.id].getData()
    assert np.array_equal(curve_x, np.array([0.05, 0.10, 0.10]))
    assert np.array_equal(curve_y, np.array([0.0, 0.0, 1.0]))
    window.close()
    app.processEvents()


def test_plot_acquisition_uses_scenario_time():
    app = QApplication.instance() or QApplication([])
    channel = AnalogChannel(id=3, name="scenario channel")
    generator = SignalGenerator([channel])
    window = PlotWindow(generator)
    window.add_channel_to_plot(channel.id)

    window.begin_scenario_acquisition()
    window.set_scenario_time(2.75)
    window.update_plots()

    timestamps, _values = window.plot_widgets[0].channel_data[channel.id].get_data()
    assert window._acquisition_time == 2.75
    assert np.array_equal(timestamps, np.array([2.75]))

    window.end_scenario_acquisition()
    window.update_plots()
    assert window._acquisition_time == 2.80

    window.close()
    app.processEvents()
