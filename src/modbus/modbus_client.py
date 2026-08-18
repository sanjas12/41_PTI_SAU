import contextlib
import threading
from typing import List, Optional

from pyModbusTCP.client import ModbusClient


class ModbusClientWrapper:
    """Thread-safe обертка для Modbus TCP клиента"""
    
    NOT_CONNECT = "Нет соединения с устройством"

    def __init__(self) -> None:
        self._client: Optional[ModbusClient] = None
        self._lock = threading.Lock()
        self._connected = False

    def configure(self, host: str, port: int, unit_id: int) -> None:
        """Настройка параметров подключения"""
        if not host or not isinstance(port, int) or port <= 0 or port > 65535:
            raise ValueError("Неверные параметры подключения")
            
        with self._lock:
            if self._client is not None:
                with contextlib.suppress(Exception):
                    self._client.close()
            self._client = ModbusClient(
                host=host,
                port=port,
                unit_id=unit_id,
                auto_open=True,
                auto_close=False,
                timeout=3.0,
            )
            self._connected = False

    def open(self) -> bool:
        """Открыть соединение"""
        with self._lock:
            if self._client is None:
                raise RuntimeError(self.NOT_CONNECT)
            self._connected = bool(self._client.open())
            return self._connected

    def close(self) -> None:
        """Закрыть соединение"""
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._connected = False

    def is_connected(self) -> bool:
        """Проверить состояние соединения"""
        return self._connected

    # --- Операции чтения ---
    def read_holding(self, address: int, quantity: int) -> Optional[List[int]]:
        """Чтение Holding Registers (0x03)"""
        with self._lock:
            if self._client is None or not self._connected:
                raise RuntimeError(self.NOT_CONNECT)
            return self._client.read_holding_registers(address, quantity)

    def read_input(self, address: int, quantity: int) -> Optional[List[int]]:
        """Чтение Input Registers (0x04)"""
        with self._lock:
            if self._client is None or not self._connected:
                raise RuntimeError(self.NOT_CONNECT)
            return self._client.read_input_registers(address, quantity)

    def read_coils(self, address: int, quantity: int) -> Optional[List[bool]]:
        """Чтение Coils (0x01)"""
        with self._lock:
            if self._client is None or not self._connected:
                raise RuntimeError(self.NOT_CONNECT)
            return self._client.read_coils(address, quantity)

    def read_discrete_inputs(self, address: int, quantity: int) -> Optional[List[bool]]:
        """Чтение Discrete Inputs (0x02)"""
        with self._lock:
            if self._client is None or not self._connected:
                raise RuntimeError(self.NOT_CONNECT)
            return self._client.read_discrete_inputs(address, quantity)

    # --- Операции записи ---
    def write_single_register(self, address: int, value: int) -> bool:
        """Запись одного регистра (0x06)"""
        with self._lock:
            if self._client is None or not self._connected:
                raise RuntimeError(self.NOT_CONNECT)
            return bool(self._client.write_single_register(address, value))

    def write_multiple_registers(self, address: int, values: List[int]) -> bool:
        """Запись нескольких регистров (0x10)"""
        with self._lock:
            if self._client is None or not self._connected:
                raise RuntimeError(self.NOT_CONNECT)
            return bool(self._client.write_multiple_registers(address, values))

    def write_single_coil(self, address: int, value: bool) -> bool:
        """Запись одной катушки (0x05)"""
        with self._lock:
            if self._client is None or not self._connected:
                raise RuntimeError(self.NOT_CONNECT)
            return bool(self._client.write_single_coil(address, value))

    def write_multiple_coils(self, address: int, values: List[bool]) -> bool:
        """Запись нескольких катушек (0x0F)"""
        with self._lock:
            if self._client is None or not self._connected:
                raise RuntimeError(self.NOT_CONNECT)
            return bool(self._client.write_multiple_coils(address, values))