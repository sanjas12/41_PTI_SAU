"""Выбор устройства и жизненный цикл подключения без зависимости от окна."""

from typing import Any, Dict, Optional, Tuple

from PyQt5.QtCore import QObject, QThreadPool, pyqtSignal, pyqtSlot

from core.output_devices import device_label
from core.signal_generator import SignalGenerator
from modbus.worker import Runnable
from mu210.interface import MU210Interface
from plc.moxa_e1242_interface import MoxaE1242Interface
from plc.plc_interface import PLCInterface


class DeviceManager(QObject):
    """Владеет адаптерами; открывает соединение в пуле, запускает таймеры в Qt.

    interfaces и thread_pool можно подменить для тестов без оборудования.
    Ревизия подключения предотвращает запуск обмена после отмены запроса.
    """

    connection_status = pyqtSignal(bool)
    connection_finished = pyqtSignal(bool)
    device_changed = pyqtSignal(str)
    log_signal = pyqtSignal(str, str)
    debug_data = pyqtSignal(dict)

    def __init__(
        self,
        generator: SignalGenerator,
        parent: Optional[QObject] = None,
        interfaces: Optional[Dict[str, Any]] = None,
        thread_pool: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        if interfaces is None:
            plc = PLCInterface(generator, self)
            interfaces = {
                "owen": MU210Interface(generator, self),
                "plc": plc,
                "simulator": plc,
                "moxa_e1242": MoxaE1242Interface(generator, self),
            }
        self.interfaces = interfaces
        self.active_device_type = "owen"
        self.thread_pool = (
            thread_pool if thread_pool is not None else QThreadPool.globalInstance()
        )
        self._revision = 0
        self._pending: Optional[Tuple[Any, int]] = None
        self._closed = False
        for interface in self._unique_interfaces():
            interface.connection_status.connect(
                lambda connected, source=interface: self._forward_status(
                    source, connected
                )
            )
            interface.error_occurred.connect(
                lambda message, source=interface: self.log_signal.emit(
                    f"{self._interface_label(source)}: {message}", "error"
                )
            )
            interface.debug_data.connect(
                lambda data, source=interface: self._forward_debug(source, data)
            )

    def _unique_interfaces(self) -> list:
        return list({id(value): value for value in self.interfaces.values()}.values())

    @property
    def active_interface(self) -> Any:
        return self.interfaces[self.active_device_type]

    @property
    def active_device_name(self) -> str:
        return device_label(self.active_device_type)

    def _interface_label(self, interface: Any) -> str:
        if interface is self.active_interface:
            return self.active_device_name
        return next(
            device_label(key)
            for key, value in self.interfaces.items()
            if value is interface
        )

    def _forward_status(self, source: Any, connected: bool) -> None:
        if source is self.active_interface and not self._closed:
            self.connection_status.emit(connected)

    def _forward_debug(self, source: Any, data: dict) -> None:
        if source is self.active_interface and not self._closed:
            self.debug_data.emit(data)

    def configure(self, params: Dict[str, Any]) -> None:
        if self._closed:
            raise RuntimeError("Менеджер устройств закрыт")
        device_type = params.get("device_type", self.active_device_type)
        if device_type not in self.interfaces:
            raise ValueError("Неизвестный тип устройства")
        selected = self.interfaces[device_type]
        host, port = params.get("host", ""), params.get("port", 0)
        if host and port and self._pending is not None:
            raise RuntimeError("Дождитесь завершения подключения перед настройкой")
        self._revision += 1
        if device_type != self.active_device_type:
            self.active_interface.disconnect()
            self.active_device_type = device_type
            self.device_changed.emit(device_type)
        if host and port:
            unit_id = params.get("unit_id", 1)
            if selected.configure(host, port, unit_id) is False:
                raise RuntimeError("Устройство отклонило параметры подключения")
            self.log_signal.emit(
                f"Настроен {self.active_device_name}: {host}:{port} "
                f"(Unit ID: {unit_id})",
                "info",
            )

    def connect_device(self) -> None:
        if self._closed or self._pending is not None:
            return
        self._pending = (self.active_interface, self._revision)
        task = Runnable(self.active_interface.open)
        task.signals.result.connect(self._on_open_finished)
        task.signals.error.connect(self._on_open_error)
        self.thread_pool.start(task)

    @pyqtSlot(object)
    def _on_open_finished(self, result: Any) -> None:
        pending = self._pending
        self._pending = None
        if pending is None:
            return
        interface, revision = pending
        if self._closed or revision != self._revision:
            interface.disconnect()
            return
        if result:
            interface.start_polling()
            self.log_signal.emit(
                f"Подключение к {self.active_device_name} установлено", "success"
            )
        else:
            self.log_signal.emit("Не удалось подключиться", "error")
        self.connection_finished.emit(interface.is_connected())

    @pyqtSlot(str)
    def _on_open_error(self, message: str) -> None:
        self.log_signal.emit(f"Ошибка подключения: {message}", "error")
        self._on_open_finished(False)

    def disconnect_device(self) -> None:
        self._revision += 1
        self.active_interface.disconnect()

    def close(self) -> None:
        self._revision += 1
        self._closed = True
        for interface in self._unique_interfaces():
            interface.disconnect()
