from typing import List, Optional
from unittest.mock import Mock

import pytest
from PyQt5.QtCore import QThread, QThreadPool
from PyQt5.QtWidgets import QApplication

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from devices.moxa_e1242_interface import MoxaE1242Interface
from modbus.worker import Runnable


class DeferredPool:
    def __init__(self) -> None:
        self.tasks: List[Runnable] = []

    def start(self, task: Runnable) -> None:
        self.tasks.append(task)


@pytest.fixture
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def interface(app: QApplication) -> MoxaE1242Interface:
    channels = [
        AnalogChannel(id=0, name="AI", output_device="moxa_e1242", output_address=0),
        AnalogChannel(
            id=1,
            name="DO",
            signal_type=SignalType.DISCRETE,
            output_device="moxa_e1242",
            output_address=1,
            current_value=1.0,
        ),
    ]
    adapter = MoxaE1242Interface(SignalGenerator(channels))
    adapter.modbus = Mock()
    adapter.modbus.read_input.return_value = [65535, 0, 0, 0]
    adapter.modbus.read_discrete_inputs.return_value = [False, True, False, True]
    adapter.modbus.write_multiple_coils.return_value = True
    adapter._connected = True
    adapter._is_configured = True
    adapter.thread_pool = DeferredPool()
    return adapter


def test_slow_exchange_does_not_accumulate_tasks(interface: MoxaE1242Interface) -> None:
    interface.update_device_data()
    interface.update_device_data()
    assert len(interface.thread_pool.tasks) == 1
    interface.thread_pool.tasks[0].run()
    interface.update_device_data()
    assert len(interface.thread_pool.tasks) == 2


def test_outputs_are_snapshot_and_protocol_is_preserved(
    interface: MoxaE1242Interface,
) -> None:
    interface.set_output_enabled(True)
    interface.update_device_data()
    interface.generator.channels[1].current_value = 0.0
    interface.thread_pool.tasks[0].run()
    interface.modbus.write_multiple_coils.assert_called_once_with(
        0, [False, True, False, False]
    )
    interface.modbus.read_input.assert_called_once_with(0, 4)
    interface.modbus.read_discrete_inputs.assert_called_once_with(0, 4)
    assert interface.write_count == 1
    assert interface.generator.channels[0].current_value == 100.0


def test_stop_cancels_queued_write_but_keeps_reading(
    interface: MoxaE1242Interface,
) -> None:
    interface.set_output_enabled(True)
    interface.update_device_data()
    interface.set_output_enabled(False)
    interface.thread_pool.tasks[0].run()
    interface.modbus.write_multiple_coils.assert_not_called()
    interface.modbus.read_input.assert_called_once_with(0, 4)


@pytest.mark.parametrize("disconnect", [False, True])
def test_stale_input_is_not_applied(
    interface: MoxaE1242Interface, disconnect: bool
) -> None:
    interface.update_device_data()
    if disconnect:
        interface.disconnect()
    else:
        interface.generator.channels[0].output_address = 1
    interface.thread_pool.tasks[0].run()
    assert interface.generator.channels[0].current_value == 0.0


def test_failure_releases_pending_and_keeps_partial_input(
    interface: MoxaE1242Interface,
) -> None:
    errors: List[str] = []
    interface.error_occurred.connect(errors.append)
    interface.modbus.read_input.side_effect = OSError("fake timeout")
    interface.update_device_data()
    interface.thread_pool.tasks[0].run()
    assert errors
    interface.update_device_data()
    assert len(interface.thread_pool.tasks) == 2


def test_input_is_applied_only_in_gui_thread(
    interface: MoxaE1242Interface, app: QApplication
) -> None:
    pool = QThreadPool()
    interface.thread_pool = pool
    threads = []
    original = interface._apply_ai_raw

    def apply(index: int, raw: int, channel_id: Optional[int] = None) -> None:
        threads.append(QThread.currentThread())
        original(index, raw, channel_id)

    interface._apply_ai_raw = apply
    interface.update_device_data()
    assert pool.waitForDone(3000)
    assert interface.generator.channels[0].current_value == 0.0
    app.processEvents()
    assert interface.generator.channels[0].current_value == 100.0
    assert threads and all(thread is app.thread() for thread in threads)


def test_disabled_output_still_reads_inputs(interface: MoxaE1242Interface) -> None:
    data = []
    interface.data_updated.connect(data.append)
    interface.update_device_data()
    interface.thread_pool.tasks[0].run()
    interface.modbus.write_multiple_coils.assert_not_called()
    assert data == [{"di": [False, True, False, True]}]


def test_unexpected_failure_releases_pending(interface: MoxaE1242Interface) -> None:
    interface.modbus.read_input.side_effect = TypeError("fake bad client")
    interface.update_device_data()
    interface.thread_pool.tasks[0].run()
    interface.update_device_data()
    assert len(interface.thread_pool.tasks) == 2


def test_pending_exchange_prevents_reconfiguration(
    interface: MoxaE1242Interface,
) -> None:
    interface.update_device_data()
    assert not interface.configure("fake", 502)
    interface.modbus.configure.assert_not_called()


def test_short_response_reports_error_and_keeps_previous_value(
    interface: MoxaE1242Interface,
) -> None:
    interface.modbus.read_input.return_value = [65535]
    errors = []
    interface.error_occurred.connect(errors.append)
    interface.update_device_data()
    interface.thread_pool.tasks[0].run()
    assert interface.generator.channels[0].current_value == 0.0
    assert errors


def test_reconnected_interface_ignores_old_response(
    interface: MoxaE1242Interface,
) -> None:
    interface.update_device_data()
    interface.disconnect()
    interface.start_polling()
    interface.update_timer.stop()
    interface.update_device_data()
    assert len(interface.thread_pool.tasks) == 1
    interface.thread_pool.tasks[0].run()
    assert interface.generator.channels[0].current_value == 0.0
    interface.update_device_data()
    assert len(interface.thread_pool.tasks) == 2
