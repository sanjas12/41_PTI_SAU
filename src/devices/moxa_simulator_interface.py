"""Отдельное устройство вывода с автоматически запускаемым локальным стендом."""

from typing import Optional

from PyQt5.QtCore import QObject

from core.signal_generator import SignalGenerator
from devices.moxa_e1242_interface import MoxaE1242Interface
from devices.moxa_e1242_simulator import MoxaE1242Simulator


class MoxaSimulatorInterface(MoxaE1242Interface):
    DEVICE_TYPE = "moxa_e1242_simulator"

    def __init__(
        self, generator: SignalGenerator, parent: Optional[QObject] = None
    ) -> None:
        super().__init__(generator, parent)
        self.local_server: Optional[MoxaE1242Simulator] = None
        self.owns_server = True

    def configure(self, host: str, port: int = 1502, unit_id: int = 1) -> bool:
        if host != "127.0.0.1":
            self.error_occurred.emit("Симулятор Moxa доступен только на 127.0.0.1")
            return False
        if not super().configure(host, port, unit_id):
            return False
        if self.local_server is not None and self.owns_server:
            self.local_server.stop()
        self.local_server = MoxaE1242Simulator(port)
        self.owns_server = True
        return True

    def open(self) -> bool:
        if self.local_server is None:
            raise RuntimeError("Симулятор Moxa не настроен")
        if self.owns_server:
            self.local_server.start()
        try:
            connected = super().open()
        except (OSError, RuntimeError):
            if self.owns_server:
                self.local_server.stop()
            raise
        if not connected and self.owns_server:
            self.local_server.stop()
        return connected

    def disconnect(self) -> None:
        super().disconnect()
        if self.local_server is not None and self.owns_server:
            self.local_server.stop()
