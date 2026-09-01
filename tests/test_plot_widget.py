import os

from PyQt5.QtWidgets import QApplication

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
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
