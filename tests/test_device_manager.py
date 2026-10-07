from typing import Any, Dict, List, Optional, Tuple

import pytest
from PyQt5.QtCore import QObject, QThread, QThreadPool, pyqtSignal
from PyQt5.QtWidgets import QApplication

from core.signal_generator import SignalGenerator
from devices.device_manager import DeviceManager
from modbus.worker import Runnable


class FakeInterface(QObject):
    connection_status = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    debug_data = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.connected = False
        self.poll_count = 0
        self.disconnect_count = 0
        self.parameters: Optional[Tuple[str, int, int]] = None
        self.open_result = True
        self.open_error = False
        self.configure_result = True
        self.poll_thread: Optional[QThread] = None

    def configure(self, host: str, port: int, unit_id: int) -> bool:
        self.parameters = (host, port, unit_id)
        return self.configure_result

    def open(self) -> bool:
        if self.open_error:
            raise RuntimeError("fake open failed")
        self.connected = self.open_result
        return self.open_result

    def start_polling(self) -> None:
        self.poll_count += 1
        self.poll_thread = QThread.currentThread()
        self.connection_status.emit(True)

    def is_connected(self) -> bool:
        return self.connected

    def disconnect(self) -> None:
        self.connected = False
        self.disconnect_count += 1
        self.connection_status.emit(False)


class DeferredPool:
    def __init__(self) -> None:
        self.tasks: List[Runnable] = []

    def start(self, task: Runnable) -> None:
        self.tasks.append(task)


@pytest.fixture
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def setup_manager(
    app: QApplication,
) -> Tuple[DeviceManager, Dict[str, Any], DeferredPool]:
    plc = FakeInterface()
    interfaces = {
        "owen": FakeInterface(),
        "plc": plc,
        "simulator": plc,
    }
    pool = DeferredPool()
    return (
        DeviceManager(SignalGenerator(), interfaces=interfaces, thread_pool=pool),
        interfaces,
        pool,
    )


@pytest.mark.parametrize("device_type", ["owen", "plc", "simulator"])
def test_configures_selected_adapter(setup_manager: tuple, device_type: str) -> None:
    manager, interfaces, pool = setup_manager
    manager.configure(
        {"device_type": device_type, "host": "fake", "port": 1234, "unit_id": 7}
    )
    assert manager.active_interface is interfaces[device_type]
    assert interfaces[device_type].parameters == ("fake", 1234, 7)
    assert not pool.tasks


def test_connection_is_deferred_and_duplicate_request_is_ignored(
    setup_manager: tuple,
) -> None:
    manager, interfaces, pool = setup_manager
    results = []
    manager.connection_finished.connect(results.append)
    manager.connect_device()
    manager.connect_device()
    assert len(pool.tasks) == 1
    assert interfaces["owen"].poll_count == 0
    pool.tasks[0].run()
    assert interfaces["owen"].poll_count == 1
    assert results == [True]


@pytest.mark.parametrize("action", ["disconnect", "switch", "close"])
def test_cancelled_open_never_starts_polling(setup_manager: tuple, action: str) -> None:
    manager, interfaces, pool = setup_manager
    manager.connect_device()
    if action == "disconnect":
        manager.disconnect_device()
    elif action == "switch":
        manager.configure({"device_type": "plc"})
    else:
        manager.close()
    pool.tasks[0].run()
    assert interfaces["owen"].poll_count == 0
    assert not interfaces["owen"].connected


@pytest.mark.parametrize("raises", [False, True])
def test_failed_open_reports_status_and_allows_retry(
    setup_manager: tuple, raises: bool
) -> None:
    manager, interfaces, pool = setup_manager
    interface = interfaces["owen"]
    interface.open_result = False
    interface.open_error = raises
    results = []
    manager.connection_finished.connect(results.append)
    manager.connect_device()
    pool.tasks[0].run()
    assert results == [False]
    assert interface.poll_count == 0
    manager.connect_device()
    assert len(pool.tasks) == 2


def test_inactive_adapter_does_not_change_active_status(setup_manager: tuple) -> None:
    manager, interfaces, _ = setup_manager
    statuses = []
    manager.connection_status.connect(statuses.append)
    interfaces["plc"].connection_status.emit(True)
    interfaces["owen"].connection_status.emit(True)
    assert statuses == [True]
    manager.close()
    assert interfaces["plc"].disconnect_count == 1


def test_configuration_failure_is_reported(setup_manager: tuple) -> None:
    manager, interfaces, _ = setup_manager
    interfaces["owen"].configure_result = False
    with pytest.raises(RuntimeError):
        manager.configure({"host": "fake", "port": 502})
    with pytest.raises(ValueError):
        manager.configure({"device_type": "unknown"})


def test_pending_open_cannot_be_reconfigured(setup_manager: tuple) -> None:
    manager, interfaces, pool = setup_manager
    manager.connect_device()
    with pytest.raises(RuntimeError, match="Дождитесь"):
        manager.configure({"host": "fake", "port": 502})
    assert interfaces["owen"].parameters is None
    pool.tasks[0].run()
    assert interfaces["owen"].poll_count == 1


def test_polling_starts_in_gui_thread(app: QApplication) -> None:
    interface = FakeInterface()
    pool = QThreadPool()
    manager = DeviceManager(
        SignalGenerator(), interfaces={"owen": interface}, thread_pool=pool
    )
    manager.connect_device()
    assert pool.waitForDone(3000)
    app.processEvents()
    assert interface.poll_count == 1
    assert interface.poll_thread is app.thread()
    manager.close()
