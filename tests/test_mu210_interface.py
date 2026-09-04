from PyQt5.QtWidgets import QApplication

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from mu210.interface import MU210Interface


def make_interface(channels):
    QApplication.instance() or QApplication([])
    return MU210Interface(SignalGenerator(channels))


def test_mu210_maps_first_eight_analog_channels_to_permille():
    channels = [
        AnalogChannel(
            id=index,
            name=f"A{index + 1}",
            min_value=-10.0,
            max_value=10.0,
            current_value=float(index - 4),
        )
        for index in range(9)
    ]
    channels.insert(
        1,
        AnalogChannel(
            id=20,
            name="D1",
            signal_type=SignalType.DISCRETE,
            min_value=0.0,
            max_value=1.0,
            current_value=1.0,
        ),
    )
    interface = make_interface(channels)
    interface.set_output_enabled(True)

    assert interface.prepare_output_values() == [300, 350, 400, 450, 500, 550, 600, 650]


def test_mu210_outputs_zero_while_application_is_stopped():
    channel = AnalogChannel(
        id=0,
        name="A1",
        min_value=0.0,
        max_value=100.0,
        current_value=75.0,
    )
    interface = make_interface([channel])

    assert interface.prepare_output_values() == [0] * 8


def test_mu210_clamps_values_and_pads_missing_channels():
    channels = [
        AnalogChannel(
            id=0, name="low", min_value=0.0, max_value=10.0, current_value=-5.0
        ),
        AnalogChannel(
            id=1, name="high", min_value=0.0, max_value=10.0, current_value=15.0
        ),
    ]
    interface = make_interface(channels)
    interface.set_output_enabled(True)

    assert interface.prepare_output_values() == [0, 1000, 0, 0, 0, 0, 0, 0]


def test_mu210_writes_all_outputs_in_one_modbus_request():
    interface = make_interface([])
    calls = []

    def write_multiple_registers(address, values):
        calls.append((address, values))
        return True

    interface.modbus.write_multiple_registers = write_multiple_registers

    assert interface._write_outputs([100] * 8) is True
    assert calls == [(3000, [100] * 8)]


def test_mu210_distributes_analog_channels_between_modules():
    channels = [
        AnalogChannel(
            id=index,
            name=f"A{index + 1}",
            min_value=0.0,
            max_value=100.0,
            current_value=float(index + 1),
        )
        for index in range(20)
    ]
    interface = make_interface(channels)
    interface.configure("192.168.1.99, 192.168.1.100;192.168.1.101", 502, 1)
    interface.set_output_enabled(True)

    assert interface.prepare_module_output_values() == [
        [10, 20, 30, 40, 50, 60, 70, 80],
        [90, 100, 110, 120, 130, 140, 150, 160],
        [170, 180, 190, 200, 0, 0, 0, 0],
    ]
    assert interface.get_device_labels() == [
        "МУ210 #1 (192.168.1.99)",
        "МУ210 #2 (192.168.1.100)",
        "МУ210 #3 (192.168.1.101)",
    ]


def test_mu210_writes_each_module_separately():
    interface = make_interface([])
    interface.configure("192.168.1.99,192.168.1.100", 502, 1)
    calls = []

    for module_index, client in enumerate(interface.modbus_clients):
        client.write_multiple_registers = lambda address, values, index=module_index: (
            calls.append((index, address, values)) or True
        )

    values = [[100] * 8, [200] * 8]
    assert interface._write_all_outputs(values) is True
    assert calls == [(0, 3000, values[0]), (1, 3000, values[1])]
