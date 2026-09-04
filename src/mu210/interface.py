import threading
import time
from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, QThreadPool, QTimer, pyqtSignal

from core.signal_generator import SignalGenerator
from modbus.modbus_client import ModbusClientWrapper
from modbus.worker import Runnable


class MU210Interface(QObject):
    """Передаёт восемь аналоговых каналов напрямую в ОВЕН МУ210-501."""

    OUTPUT_VALUE_START = 3000
    OUTPUT_COUNT = 8
    OUTPUT_STATUS_START = 3128

    connection_status = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    debug_data = pyqtSignal(dict)
    write_completed = pyqtSignal(bool)

    def __init__(self, generator: SignalGenerator, parent=None) -> None:
        super().__init__(parent)
        self.generator = generator
        self.modbus = ModbusClientWrapper()
        self.write_interval = 0.2
        self.write_count = 0
        self.last_written_data: Dict[str, object] = {}
        self._configured = False
        self._connected = False
        self._output_enabled = False
        self._write_pending = False
        self._lock = threading.Lock()
        self.thread_pool = QThreadPool.globalInstance()
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_output_data)

    def configure(self, host: str, port: int, unit_id: int = 1) -> None:
        """Настроить сетевые параметры модуля."""
        self.modbus.configure(host, port, unit_id)
        self._configured = True
        self._connected = False

    def open(self) -> bool:
        """Открыть TCP-соединение без запуска Qt-таймера."""
        if not self._configured:
            raise RuntimeError("МУ210-501 не настроен")
        self._connected = self.modbus.open()
        return self._connected

    def start_polling(self) -> None:
        """Запустить периодическую передачу после успешного подключения."""
        if not self._connected:
            return
        self.write_count = 0
        self._write_pending = False
        self.update_timer.start(max(10, int(self.write_interval * 1000)))
        self.connection_status.emit(True)

    def disconnect(self) -> None:
        """Остановить передачу и закрыть соединение."""
        self.update_timer.stop()
        self._connected = False
        self._write_pending = False
        self.modbus.close()
        self.connection_status.emit(False)

    def is_connected(self) -> bool:
        return self._configured and self._connected

    def set_output_enabled(self, enabled: bool) -> None:
        """Разрешить значения генератора; при Stop передаются нули."""
        was_enabled = self._output_enabled
        self._output_enabled = enabled
        if was_enabled and not enabled:
            self.update_output_data()

    def prepare_output_values(self) -> List[int]:
        """Преобразовать первые 8 аналоговых каналов в 0...1000 промилле."""
        analog_channels = [
            channel
            for channel in self.generator.channels
            if channel.signal_type.is_analog()
        ][: self.OUTPUT_COUNT]
        values: List[int] = []
        for channel in analog_channels:
            span = channel.max_value - channel.min_value
            if not self._output_enabled or not channel.enabled or span <= 0.0:
                values.append(0)
                continue
            normalized = (channel.current_value - channel.min_value) / span
            values.append(round(max(0.0, min(1.0, normalized)) * 1000.0))
        values.extend([0] * (self.OUTPUT_COUNT - len(values)))
        return values

    def _write_outputs(self, values: List[int]) -> bool:
        result = self.modbus.write_multiple_registers(self.OUTPUT_VALUE_START, values)
        if not result:
            raise RuntimeError("МУ210-501 отклонил запись выходов")
        return True

    def update_output_data(self) -> None:
        """Поставить одну пакетную запись в фоновый пул без накопления очереди."""
        if not self.is_connected() or self._write_pending:
            return
        values = self.prepare_output_values()
        self._write_pending = True
        task = Runnable(self._write_outputs, values)
        task.signals.result.connect(
            lambda result, sent_values=values: self._on_write_finished(
                bool(result), sent_values
            )
        )
        task.signals.error.connect(self._on_write_error)
        self.thread_pool.start(task)

    def _on_write_finished(self, result: bool, values: List[int]) -> None:
        with self._lock:
            self._write_pending = False
            if result:
                self.write_count += 1
                self.last_written_data = {
                    "write_count": self.write_count,
                    "timestamp": time.time(),
                    "start_address": self.OUTPUT_VALUE_START,
                    "values": list(values),
                }
        self.write_completed.emit(result)
        if result and not self._output_enabled and any(values):
            self.update_output_data()
        if result and self.write_count % 10 == 0:
            self.debug_data.emit(dict(self.last_written_data))

    def _on_write_error(self, message: str) -> None:
        self._write_pending = False
        self.error_occurred.emit(f"Ошибка записи МУ210-501: {message}")
        self.write_completed.emit(False)

    def read_plc_data(self, address: int, count: int) -> Optional[List[int]]:
        """Прочитать holding-регистры для диагностического окна."""
        if not self.is_connected():
            return None
        return self.modbus.read_holding(address, count)

    def get_register_map(self) -> dict:
        """Вернуть карту оперативных регистров МУ210-501."""
        return {
            "analog_outputs": {
                "start": 3000,
                "end": 3007,
                "description": "AO1-AO8 (UINT16, 0...1000 промилле)",
                "channels": [f"AO{index + 1}" for index in range(8)],
            },
            "output_status": {
                "start": 3128,
                "end": 3135,
                "description": "Состояние выходов (UINT16)",
            },
            "output_modes": {
                "start": 3160,
                "end": 3167,
                "description": "Режимы AO1-AO8 (UINT16)",
            },
        }

    def get_last_written_data(self) -> dict:
        return dict(self.last_written_data)

    def set_write_interval(self, interval: float) -> None:
        self.write_interval = max(0.01, min(10.0, interval))
        if self.update_timer.isActive():
            self.update_timer.start(max(10, int(self.write_interval * 1000)))
