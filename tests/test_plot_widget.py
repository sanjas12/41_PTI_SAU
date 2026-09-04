import os

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication, QFrame, QSizePolicy

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from ui.plot_widget import PlotWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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
    assert toolbar.maximumHeight() == 46
    assert status_bar.maximumHeight() == 34

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
    assert window.channels_list.item(0).text().startswith("[D] Ch05:")

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
