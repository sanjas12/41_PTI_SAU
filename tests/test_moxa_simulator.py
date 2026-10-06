import socket
from pathlib import Path
from typing import Iterator

import pytest
from pyModbusTCP.client import ModbusClient
from PyQt5.QtWidgets import QApplication

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from devices.moxa_e1242_interface import MoxaE1242Interface
from devices.moxa_e1242_simulator import MoxaE1242Simulator
from devices.moxa_simulator_interface import MoxaSimulatorInterface
from scenario.scenario_engine import ScenarioEngine
from scenario.scenario_model import Scenario, ScenarioStep
from ui.moxa_simulator_dialog import MoxaSimulatorDialog
from ui.plc_register_view import PLCRegisterView


@pytest.fixture
def port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def simulator(port: int) -> Iterator[MoxaE1242Simulator]:
    server = MoxaE1242Simulator(port)
    server.start()
    try:
        yield server
    finally:
        server.stop()


def test_loopback_protocol(simulator: MoxaE1242Simulator, port: int) -> None:
    client = ModbusClient(host="127.0.0.1", port=port, unit_id=1, timeout=1)
    try:
        assert client.open()
        simulator.set_ai(1, 50000)
        simulator.set_di(2, True)
        assert client.read_input_registers(0, 4) == [0, 50000, 32768, 65535]
        assert client.read_discrete_inputs(0, 4) == [False, False, True, False]
        assert client.write_multiple_coils(0, [True, False, True, False])
        assert simulator.get_do() == [True, False, True, False]
        assert client.read_coils(0, 4) == simulator.get_do()
        assert client.read_input_registers(4, 1) is None
        assert client.read_holding_registers(0, 1) is None
    finally:
        client.close()


def test_application_adapter_and_register_window(
    simulator: MoxaE1242Simulator, port: int
) -> None:
    app = QApplication.instance() or QApplication([])
    adapter = MoxaE1242Interface(
        SignalGenerator(
            [
                AnalogChannel(
                    id=0,
                    name="DO",
                    signal_type=SignalType.DISCRETE,
                    output_device="moxa_e1242",
                    output_address=0,
                    current_value=1.0,
                ),
            ]
        )
    )
    window = PLCRegisterView(adapter, "Fake Moxa")
    try:
        assert adapter.configure("127.0.0.1", port, 1)
        assert adapter.open()
        adapter.start_polling()
        adapter.update_timer.stop()
        simulator.set_di(1, True)
        adapter.set_output_enabled(True)
        result = adapter._exchange(
            adapter.modbus,
            adapter._collect_do_bits(),
            adapter._cancel_write,
            adapter._exchange_revision,
        )
        assert result["written"]
        assert adapter.read_register_group("di", 0, 4) == [0, 1, 0, 0]
        assert adapter.read_register_group("do", 0, 4) == [1, 0, 0, 0]
        window.refresh_data()
        assert window.table.rowCount() == 12
        assert window.table.item(8, 4).text() == "1"
        assert window.table.item(8, 2).text() == "BOOL"
    finally:
        window.timer.stop()
        window.close()
        adapter.disconnect()
        app.processEvents()


def test_simulator_dialog_stops_on_close(port: int) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = MoxaSimulatorDialog()
    dialog.port_spin.setValue(port)
    try:
        dialog.start_server()
        assert dialog.simulator is not None
        server = dialog.simulator
        dialog.ai_spins[0].setValue(12345)
        dialog.di_checks[0].setChecked(True)
        assert server.data.get_input_registers(0, 1) == [12345]
        assert server.data.get_discrete_inputs(0, 1) == [True]
        params = []
        dialog.connect_requested.connect(params.append)
        dialog.connect_btn.click()
        assert params[0]["host"] == "127.0.0.1"
        assert params[0]["port"] == port
        dialog.reject()
        assert dialog.simulator is None
        assert not server.is_running
    finally:
        dialog.stop_server()
        dialog.close()
        app.processEvents()


def test_invalid_input_is_rejected() -> None:
    simulator = MoxaE1242Simulator()
    with pytest.raises(ValueError):
        simulator.set_ai(4, 0)
    with pytest.raises(ValueError):
        simulator.set_ai(0, 65536)
    with pytest.raises(ValueError):
        simulator.set_di(-1, False)


def test_simulator_is_separate_output_device_and_starts_on_connection(
    port: int,
) -> None:
    app = QApplication.instance() or QApplication([])
    fake = AnalogChannel(
        id=0,
        name="fake",
        signal_type=SignalType.DISCRETE,
        output_device="moxa_e1242_simulator",
        output_address=0,
        current_value=1.0,
    )
    real = AnalogChannel(
        id=1,
        name="real",
        signal_type=SignalType.DISCRETE,
        output_device="moxa_e1242",
        output_address=1,
        current_value=1.0,
    )
    adapter = MoxaSimulatorInterface(SignalGenerator([fake, real]))
    try:
        assert fake.output_device == "moxa_e1242_simulator"
        assert adapter.configure("127.0.0.1", port, 1)
        assert adapter.open()
        adapter.start_polling()
        adapter.update_timer.stop()
        assert adapter._collect_do_bits() == [True, False, False, False]
        result = adapter._exchange(
            adapter.modbus,
            adapter._collect_do_bits(),
            adapter._cancel_write,
            adapter._exchange_revision,
        )
        assert result["written"]
        assert adapter.read_register_group("do", 0, 4) == [1, 0, 0, 0]
        server = adapter.local_server
        assert server is not None
        adapter.disconnect()
        assert not server.is_running
    finally:
        adapter.disconnect()
        app.processEvents()


def test_scenario_routes_to_simulator_and_restores_manual_assignment() -> None:
    app = QApplication.instance() or QApplication([])
    channel = AnalogChannel(
        id=0, name="channel", output_device="moxa_e1242", output_address=1
    )
    engine = ScenarioEngine(SignalGenerator([channel]))
    step = ScenarioStep(
        channel_id=0,
        signal_type="Discrete",
        output_device="moxa_e1242_simulator",
        output_address=3,
    )
    engine.scenario = Scenario(steps=[step])
    engine._save_channel_configs()
    engine._apply_graph_step(step)
    assert (channel.output_device, channel.output_address) == (
        "moxa_e1242_simulator",
        3,
    )
    engine._restore_channel_configs()
    assert (channel.output_device, channel.output_address) == ("moxa_e1242", 1)
    app.processEvents()


def test_simulator_opens_from_main_menu_and_closes_with_application(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, port: int
) -> None:
    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        MainWindow, "_get_config_path", lambda self: str(tmp_path / "channels.json")
    )
    window = MainWindow()
    try:
        window.menu_bar.moxa_simulator_action.trigger()
        dialog = window.moxa_simulator_dialog
        assert dialog is not None and dialog.isVisible()
        dialog.port_spin.setValue(port)
        dialog.start_server()
        server = dialog.simulator
        assert server is not None
        window.close()
        assert dialog.simulator is None
        assert not server.is_running
    finally:
        window.close()
        app.processEvents()
