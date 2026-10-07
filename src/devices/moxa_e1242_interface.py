"""Интерфейс для Moxa ioLogik E1242 (4 AI + 4 DI + 4 DO) через Modbus/TCP.

Карта регистров — Appendix A мануала «ioLogik E1200 Series User's Manual v15.2»:

  DI  (2x, Input Status)      адрес 00000, 4 бита
  DO  (0x, Coil)              адрес 00000, 4 бита
  AI  raw  (3x, Input Reg.)   адрес 00000, 4 слова (0..65535)
  AI  scaled (3x, Input Reg.) адрес 00008, 4 канала x 2 слова (float)

Протокол: Modbus/TCP, порт по умолчанию 502, Unit ID = 1.
"""

import time
from threading import Event
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QObject, QThreadPool, QTimer, pyqtSignal, pyqtSlot

from core.signal_generator import SignalGenerator
from modbus.modbus_client import ModbusClientWrapper
from modbus.worker import Runnable


class MoxaE1242Interface(QObject):
    """Modbus/TCP-интерфейс к Moxa ioLogik E1242."""

    DEVICE_TYPE = "moxa_e1242"

    # Сигналы — те же, что у PLCInterface, чтобы MainWindow не пришлось
    # ничего переписывать.
    data_updated = pyqtSignal(dict)
    connection_status = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)
    debug_data = pyqtSignal(dict)
    write_completed = pyqtSignal(bool)

    # --------------------------------------------------------------
    # Карта регистров E1242
    # --------------------------------------------------------------
    DI_START = 0
    DI_COUNT = 4
    DO_START = 0
    DO_COUNT = 4
    AI_RAW_START = 1298
    AI_RAW_COUNT = 4
    AI_SCALED_START = 1312
    AI_SCALED_COUNT = 8

    # Масштаб сырых AI: 0..65535 -> 0..100 %
    AI_RAW_MAX = 65535.0

    def __init__(
        self,
        generator: SignalGenerator,
        parent: Optional[QObject] = None,
        debug: bool = False,
    ) -> None:
        super().__init__(parent)
        self.generator = generator
        self.debug = debug

        self.modbus = ModbusClientWrapper()

        self._connected = False
        self._is_configured = False
        self.write_count = 0

        # Читаем DI/AI с той же периодичностью, что и пишем DO.
        self.write_interval = 0.1  # 100 мс

        # Если генерация выключена — DO не пишем, но AI читать продолжаем.
        self._output_enabled = False
        self._exchange_pending = False
        self._exchange_revision = 0
        self._pending_revision = 0
        self._pending_ai_targets: Dict[int, int] = {}
        self._cancel_write = Event()

        self.thread_pool = QThreadPool.globalInstance()

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_device_data)

        if self.debug:
            print("[E1242_DEBUG] MoxaE1242Interface инициализирован")

    # ==============================================================
    # Жизненный цикл
    # ==============================================================

    def configure(self, host: str, port: int = 502, unit_id: int = 1) -> bool:
        if self._exchange_pending:
            self.error_occurred.emit(
                "Дождитесь завершения обмена E1242 перед настройкой"
            )
            return False
        self._exchange_revision += 1
        self.update_timer.stop()
        try:
            self.modbus.configure(host, port, unit_id)
            self._is_configured = True
            self._connected = False
            self.connection_status.emit(False)
            if self.debug:
                print(f"[E1242_DEBUG] Настроен Modbus: {host}:{port} (Unit {unit_id})")
            return True
        except Exception as e:
            msg = f"Ошибка настройки E1242: {e}"
            self.error_occurred.emit(msg)
            self._is_configured = False
            self._connected = False
            self.connection_status.emit(False)
            if self.debug:
                print(f"[E1242_DEBUG] ❌ {msg}")
            return False

    def open(self) -> bool:
        """Открыть соединение (вызывается из пула потоков MainWindow)."""
        if not self._is_configured:
            raise RuntimeError("E1242 не настроен")
        return self.modbus.open()

    def start_polling(self) -> None:
        """Соединение уже открыто — запустить периодический обмен."""
        self._exchange_revision += 1
        self._connected = self.modbus.is_connected()
        if not self._connected:
            return
        self.write_count = 0
        self.update_timer.start(max(10, int(self.write_interval * 1000)))
        self.connection_status.emit(True)

    def disconnect(self) -> None:
        self._exchange_revision += 1
        self._cancel_write.set()
        self._connected = False
        self.update_timer.stop()
        try:
            self.modbus.close()
            if self.debug:
                print("[E1242_DEBUG] 🔌 Отключено от E1242")
        except Exception as e:
            if self.debug:
                print(f"[E1242_DEBUG] Ошибка при отключении: {e}")
        self.connection_status.emit(False)

    def is_connected(self) -> bool:
        return self._connected and self._is_configured

    def set_write_interval(self, interval: float) -> None:
        self.write_interval = max(0.01, min(10.0, interval))
        if self.update_timer.isActive():
            self.update_timer.stop()
            self.update_timer.start(max(10, int(self.write_interval * 1000)))
        if self.debug:
            print(
                f"[E1242_DEBUG] Интервал обмена: {self.write_interval:.3f} с "
                f"({1.0 / self.write_interval:.1f} Гц)"
            )

    def set_output_enabled(self, enabled: bool) -> None:
        self._output_enabled = enabled
        if not enabled:
            self._cancel_write.set()

    # ==============================================================
    # Цикл обмена
    # ==============================================================

    def update_device_data(self) -> None:
        """Передать снимок в один фоновый цикл без накопления очереди."""
        if not self.is_connected() or self._exchange_pending:
            return
        do_bits = self._collect_do_bits() if self._output_enabled else None
        self._pending_ai_targets = {}
        for channel in self.generator.channels:
            if (
                channel.output_device == self.DEVICE_TYPE
                and channel.signal_type.is_analog()
            ):
                self._pending_ai_targets.setdefault(channel.output_address, channel.id)
        self._exchange_pending = True
        self._pending_revision = self._exchange_revision
        self._cancel_write = Event()
        task = Runnable(
            self._exchange,
            self.modbus,
            do_bits,
            self._cancel_write,
            self._pending_revision,
        )
        task.signals.result.connect(self._on_exchange_finished)
        task.signals.error.connect(self._on_exchange_error)
        try:
            self.thread_pool.start(task)
        except RuntimeError as exc:
            self._on_exchange_error(str(exc))

    def _exchange(
        self,
        client: ModbusClientWrapper,
        do_bits: Optional[List[bool]],
        cancel_write: Event,
        revision: int,
    ) -> Dict[str, Any]:
        """Рабочий поток: только Modbus и локальные данные, без изменения каналов."""
        errors: List[str] = []
        written: Optional[bool] = None
        if do_bits is not None and not cancel_write.is_set():
            try:
                written = bool(client.write_multiple_coils(self.DO_START, do_bits))
                if not written:
                    errors.append("Запись DO E1242 отклонена")
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append(f"Ошибка записи DO E1242: {exc}")
                written = False
        raw = None
        try:
            raw = client.read_input(self.AI_RAW_START, self.AI_RAW_COUNT)
            if raw is None or len(raw) != self.AI_RAW_COUNT:
                errors.append("Не получены все значения AI E1242")
                raw = None
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(f"Ошибка чтения AI E1242: {exc}")
        di_bits = None
        try:
            di_bits = client.read_discrete_inputs(self.DI_START, self.DI_COUNT)
            if di_bits is None or len(di_bits) != self.DI_COUNT:
                errors.append("Не получены все значения DI E1242")
                di_bits = None
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(f"Ошибка чтения DI E1242: {exc}")
        return {
            "revision": revision,
            "written": written,
            "do_bits": do_bits,
            "raw": raw,
            "di": di_bits,
            "errors": errors,
            "timestamp": time.time(),
        }

    @pyqtSlot(object)
    def _on_exchange_finished(self, result: Dict[str, Any]) -> None:
        """Применить результаты и выдать сигналы в потоке владельца QObject."""
        targets = self._pending_ai_targets
        self._exchange_pending = False
        self._pending_ai_targets = {}
        if result["revision"] != self._exchange_revision or not self.is_connected():
            return
        for message in result["errors"]:
            self.error_occurred.emit(message)
        raw = result["raw"]
        if raw is not None:
            for index, value in enumerate(raw):
                channel = self.generator.get_channel(targets.get(index, -1))
                if (
                    channel is not None
                    and channel.output_device == self.DEVICE_TYPE
                    and channel.signal_type.is_analog()
                    and channel.output_address == index
                ):
                    self._apply_ai_raw(index, value, channel.id)
        if result["di"] is not None:
            self.data_updated.emit({"di": list(result["di"])})
        written = result["written"]
        if written is not None:
            if written:
                self.write_count += 1
                if self.debug and self.write_count % 10 == 0:
                    self.debug_data.emit(
                        {
                            "write_count": self.write_count,
                            "registers": result["do_bits"],
                            "timestamp": result["timestamp"],
                        }
                    )
            self.write_completed.emit(written)

    @pyqtSlot(str)
    def _on_exchange_error(self, message: str) -> None:
        self._exchange_pending = False
        self._pending_ai_targets = {}
        if self._pending_revision == self._exchange_revision and self.is_connected():
            self.error_occurred.emit(f"Ошибка обмена E1242: {message}")

    def _collect_do_bits(self) -> List[bool]:
        """Собрать 4 DO-бита из каналов, привязанных к E1242."""
        # Отбираем дискретные каналы, назначенные на E1242.
        assigned: List[bool] = [False] * self.DO_COUNT
        for channel in self.generator.channels:
            if channel.output_device != self.DEVICE_TYPE:
                continue
            if not channel.signal_type.is_discrete():
                continue
            idx = channel.output_address
            if 0 <= idx < self.DO_COUNT:
                assigned[idx] = bool(channel.current_value >= 0.5)
        return assigned

    def _apply_ai_raw(
        self, index: int, raw_value: int, channel_id: Optional[int] = None
    ) -> None:
        for channel in self.generator.channels:
            if channel_id is not None and channel.id != channel_id:
                continue
            if channel.output_device != self.DEVICE_TYPE:
                continue
            if not channel.signal_type.is_analog():
                continue
            if channel.output_address != index:
                continue
            percent = max(0.0, min(100.0, raw_value / self.AI_RAW_MAX * 100.0))
            channel.current_value = percent
            break

    # ==============================================================
    # Валидаторы (нужны MainWindow / ScenarioEngine)
    # ==============================================================

    def validate_manual_output_map(self) -> List[str]:
        """У E1242 нет ограничений на карту выходов — все DO доступны."""
        return []

    def validate_scenario_output_map(self, scenario) -> List[str]:
        """У E1242 нет ограничений на карту выходов сценария."""
        return []

    # ==============================================================
    # Карта регистров (для PLCRegisterView)
    # ==============================================================

    def get_register_map(self) -> Dict[str, Any]:
        return {
            "ai_raw": {
                "start": self.AI_RAW_START,        # 1298
                "end": self.AI_RAW_START + self.AI_RAW_COUNT - 1,
                "description": "AI, сырые значения (UINT16, 0..65535)",
                "function": "input",               # 0x04
                "channels": [f"AI-{i:02d}" for i in range(self.AI_RAW_COUNT)],
            },
            "di": {
                "start": self.DI_START,            # 0
                "end": self.DI_START + self.DI_COUNT - 1,
                "description": "DI, дискретные входы (биты)",
                "function": "discrete",            # 0x02
            },
            "do": {
                "start": self.DO_START,            # 0
                "end": self.DO_START + self.DO_COUNT - 1,
                "description": "DO, дискретные выходы (биты)",
                "function": "coil",                # 0x01
            },
        }

    # ==============================================================
    # Чтение регистров (используется PLCRegisterView)
    # ==============================================================

    def read_register_group(
        self, group: str, address: int, count: int
    ) -> Optional[List[int]]:
        """Читать AI, DI и DO в соответствующем адресном пространстве Modbus."""
        if not self.is_connected():
            return None
        if group == "ai_raw":
            return self.modbus.read_input(address, count)
        if group == "di":
            values = self.modbus.read_discrete_inputs(address, count)
        elif group == "do":
            values = self.modbus.read_coils(address, count)
        else:
            raise ValueError("Неизвестная группа регистров Moxa")
        return [int(value) for value in values] if values is not None else None

    def read_plc_data(self, address: int, count: int) -> Optional[List[int]]:
        """Прочитать регистры по адресу — совместимость с PLCRegisterView.

        Для E1242:
          - адреса 0..3   -> AI raw (input registers)
          - адреса 8..15  -> AI scaled (input registers, 2 слова на канал)
          - остальное     -> пробуем как input registers
        """
        if not self._connected or not self._is_configured:
            return None
        try:
            if address >= self.AI_SCALED_START:
                # scaled-значения float — читаем 2 слова на канал
                return self.modbus.read_input(address, count)
            else:
                return self.modbus.read_input(address, count)
        except Exception as e:
            if self._connected:
                self.error_occurred.emit(f"Ошибка чтения E1242: {e}")
            return None

    # ==============================================================
    # Диагностика
    # ==============================================================

    def get_last_written_data(self) -> Dict[str, Any]:
        return {}

    def set_debug(self, enabled: bool) -> None:
        self.debug = enabled
