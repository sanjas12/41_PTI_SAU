import threading
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from PyQt5.QtCore import QObject, QThreadPool, QTimer, pyqtSignal

from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from modbus.modbus_client import ModbusClientWrapper
from modbus.worker import Runnable

if TYPE_CHECKING:
    from scenario.scenario_model import Scenario


class MU210Interface(QObject):
    """Распределяет аналоговые каналы по цепочке ОВЕН МУ210-501."""

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
        self.modbus_clients = [ModbusClientWrapper()]
        self.modbus = self.modbus_clients[0]
        self.hosts: List[str] = []
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
        """Настроить модули; IP разделяются запятыми или точками с запятой."""
        hosts = [item.strip() for item in host.replace(";", ",").split(",")]
        self.hosts = [item for item in hosts if item]
        if not self.hosts:
            raise ValueError("Не указан IP-адрес МУ210-501")
        self.modbus_clients = []
        for module_host in self.hosts:
            client = ModbusClientWrapper()
            client.configure(module_host, port, unit_id)
            self.modbus_clients.append(client)
        self.modbus = self.modbus_clients[0]
        self._configured = True
        self._connected = False

    def open(self) -> bool:
        """Открыть TCP-соединение без запуска Qt-таймера."""
        if not self._configured:
            raise RuntimeError("МУ210-501 не настроен")
        opened_clients = []
        try:
            for module_host, client in zip(self.hosts, self.modbus_clients):
                if not client.open():
                    raise RuntimeError(
                        f"МУ210-501 с адресом {module_host} отклонил соединение"
                    )
                opened_clients.append(client)
        except Exception:
            for client in opened_clients:
                client.close()
            self._connected = False
            raise
        self._connected = True
        return True

    def start_polling(self) -> None:
        """Запустить периодическую передачу после успешного подключения."""
        self._connected = bool(self.modbus_clients) and all(
            client.is_connected() for client in self.modbus_clients
        )
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
        errors = []
        for module_host, client in zip(self.hosts, self.modbus_clients):
            try:
                client.close()
            except Exception as exc:
                errors.append(f"{module_host}: {exc}")
        self.connection_status.emit(False)
        if errors:
            self.error_occurred.emit("Ошибки отключения МУ210: " + "; ".join(errors))

    def is_connected(self) -> bool:
        return self._configured and self._connected

    def validate_manual_output_map(self) -> List[str]:
        """Проверить назначения активных аналоговых каналов перед запуском."""
        targets: Dict[Tuple[int, int], str] = {}
        errors: List[str] = []
        for channel in self.generator.channels:
            if not channel.enabled or not channel.signal_type.is_analog():
                continue
            self._validate_output_target(
                channel.mu210_module,
                channel.mu210_register,
                channel.name,
                targets,
                errors,
            )
        return errors

    def validate_scenario_output_map(self, scenario: "Scenario") -> List[str]:
        """Проверить физические выходы аналоговых шагов с учётом их времени."""
        channels = {channel.id: channel for channel in self.generator.channels}
        timings = scenario.get_step_timings()
        assignments: Dict[Tuple[int, int], List[Tuple[float, float, str]]] = {}
        errors: List[str] = []

        for index, step in enumerate(scenario.steps, start=1):
            try:
                is_analog = SignalType[step.signal_type.upper()].is_analog()
            except KeyError:
                continue
            if not is_analog:
                continue

            channel = channels.get(step.channel_id)
            if channel is None:
                errors.append(f"Шаг {index}: канал {step.channel_id} не найден")
                continue
            module = (
                step.mu210_module
                if step.mu210_module is not None
                else channel.mu210_module
            )
            register = (
                step.mu210_register
                if step.mu210_register is not None
                else channel.mu210_register
            )
            label = f"шаг {index} ({channel.name})"
            if not self._validate_output_target(module, register, label, {}, errors):
                continue

            start, end = timings.get(step.id, (0.0, step.duration))
            target = (module, register)
            for other_start, other_end, other_label in assignments.get(target, []):
                if start < other_end and other_start < end:
                    errors.append(
                        f"{label} и {other_label} одновременно используют "
                        f"МУ210 №{module}, регистр {register}"
                    )
            assignments.setdefault(target, []).append((start, end, label))
        return errors

    def _validate_output_target(
        self,
        module: int,
        register: int,
        label: str,
        targets: Dict[Tuple[int, int], str],
        errors: List[str],
    ) -> bool:
        module_count = len(self.hosts) if self._configured else len(self.modbus_clients)
        if not 1 <= module <= module_count:
            errors.append(
                f"{label}: модуль МУ210 №{module} отсутствует "
                f"(настроено: {module_count})"
            )
            return False
        if (
            not self.OUTPUT_VALUE_START
            <= register
            < (self.OUTPUT_VALUE_START + self.OUTPUT_COUNT)
        ):
            errors.append(
                f"{label}: регистр {register} вне диапазона "
                f"{self.OUTPUT_VALUE_START}–"
                f"{self.OUTPUT_VALUE_START + self.OUTPUT_COUNT - 1}"
            )
            return False

        target = (module, register)
        previous = targets.get(target)
        if previous is not None:
            errors.append(
                f"{label} и {previous} назначены на МУ210 №{module}, регистр {register}"
            )
            return False
        targets[target] = label
        return True

    def set_output_enabled(self, enabled: bool) -> None:
        """Разрешить значения генератора; при Stop передаются нули."""
        was_enabled = self._output_enabled
        self._output_enabled = enabled
        if was_enabled and not enabled:
            self.update_output_data()

    def prepare_output_values(self) -> List[int]:
        """Преобразовать первые 8 аналоговых каналов в 0...1000 промилле."""
        return self.prepare_module_output_values()[0]

    def prepare_module_output_values(self) -> List[List[int]]:
        """Разложить аналоговые каналы по настроенным модулям и регистрам."""
        analog_channels = [
            channel
            for channel in self.generator.channels
            if channel.signal_type.is_analog()
        ]
        module_values = [[0] * self.OUTPUT_COUNT for _ in self.modbus_clients]
        if not self._output_enabled:
            return module_values
        occupied = set()
        for channel in analog_channels:
            module_index = channel.mu210_module - 1
            output_index = channel.mu210_register - self.OUTPUT_VALUE_START
            if not 0 <= module_index < len(module_values):
                continue
            if not 0 <= output_index < self.OUTPUT_COUNT:
                raise ValueError(
                    f"Канал {channel.name}: неверный регистр {channel.mu210_register}"
                )
            target = (module_index, output_index)
            if channel.enabled and target in occupied:
                raise ValueError(
                    f"Несколько активных каналов назначены на МУ210 "
                    f"№{channel.mu210_module}, регистр {channel.mu210_register}"
                )
            if not channel.enabled:
                continue
            occupied.add(target)
            span = channel.max_value - channel.min_value
            if span <= 0.0:
                continue
            normalized = (channel.current_value - channel.min_value) / span
            module_values[module_index][output_index] = round(
                max(0.0, min(1.0, normalized)) * 1000.0
            )
        return module_values

    def _write_outputs(self, values: List[int]) -> bool:
        result = self.modbus.write_multiple_registers(self.OUTPUT_VALUE_START, values)
        if not result:
            raise RuntimeError("МУ210-501 отклонил запись выходов")
        return True

    def _write_all_outputs(self, module_values: List[List[int]]) -> bool:
        errors = []
        for index, values in enumerate(module_values):
            try:
                result = self.modbus_clients[index].write_multiple_registers(
                    self.OUTPUT_VALUE_START, values
                )
                if not result:
                    errors.append(f"МУ210 #{index + 1}: запись отклонена")
            except Exception as exc:
                errors.append(f"МУ210 #{index + 1}: {exc}")
        if errors:
            raise RuntimeError("; ".join(errors))
        return True

    def update_output_data(self) -> None:
        """Поставить одну пакетную запись в фоновый пул без накопления очереди."""
        if not self.is_connected() or self._write_pending:
            return
        try:
            module_values = self.prepare_module_output_values()
        except ValueError as exc:
            self.error_occurred.emit(str(exc))
            return
        self._write_pending = True
        task = Runnable(self._write_all_outputs, module_values)
        task.signals.result.connect(
            lambda result, sent_values=module_values: self._on_write_finished(
                bool(result), sent_values
            )
        )
        task.signals.error.connect(self._on_write_error)
        self.thread_pool.start(task)

    def _on_write_finished(self, result: bool, values: List[List[int]]) -> None:
        with self._lock:
            self._write_pending = False
            if result:
                self.write_count += 1
                self.last_written_data = {
                    "write_count": self.write_count,
                    "timestamp": time.time(),
                    "start_address": self.OUTPUT_VALUE_START,
                    "values": [list(module) for module in values],
                }
        self.write_completed.emit(result)
        if (
            result
            and not self._output_enabled
            and any(any(module) for module in values)
        ):
            self.update_output_data()
        if result and self.write_count % 10 == 0:
            self.debug_data.emit(dict(self.last_written_data))

    def _on_write_error(self, message: str) -> None:
        self._write_pending = False
        self.error_occurred.emit(f"Ошибка записи МУ210-501: {message}")
        self.write_completed.emit(False)

    def read_plc_data(
        self, address: int, count: int, module_index: int = 0
    ) -> Optional[List[int]]:
        """Прочитать holding-регистры для диагностического окна."""
        if not self.is_connected():
            return None
        return self.modbus_clients[module_index].read_holding(address, count)

    def get_device_labels(self) -> List[str]:
        """Вернуть подписи модулей для окна диагностики."""
        return [f"МУ210 #{index + 1} ({host})" for index, host in enumerate(self.hosts)]

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
