"""Интерфейс для Moxa ioLogik E1242 (4 AI + 4 DI + 4 DO) через Modbus/TCP.

Карта регистров — Appendix A мануала «ioLogik E1200 Series User's Manual v15.2»:

  DI  (2x, Input Status)      адрес 00000, 4 бита
  DO  (0x, Coil)              адрес 00000, 4 бита
  AI  raw  (3x, Input Reg.)   адрес 00000, 4 слова (0..65535)
  AI  scaled (3x, Input Reg.) адрес 00008, 4 канала x 2 слова (float)

Протокол: Modbus/TCP, порт по умолчанию 502, Unit ID = 1.
"""

import struct
import time
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QObject, QThreadPool, QTimer, pyqtSignal

from core.signal_generator import SignalGenerator
from modbus.modbus_client import ModbusClientWrapper
from modbus.worker import Runnable


class MoxaE1242Interface(QObject):
    """Modbus/TCP-интерфейс к Moxa ioLogik E1242."""

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
    AI_RAW_START = 0
    AI_RAW_COUNT = 4
    AI_SCALED_START = 8       # 4 канала x 2 слова, начиная с 30009
    AI_SCALED_COUNT = 8

    # Масштаб сырых AI: 0..65535 -> 0..100 %
    AI_RAW_MAX = 65535.0

    def __init__(self, generator: SignalGenerator, parent=None, debug: bool = False):
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

        self.thread_pool = QThreadPool.globalInstance()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_device_data)

        if self.debug:
            print("[E1242_DEBUG] MoxaE1242Interface инициализирован")

    # ==============================================================
    # Жизненный цикл
    # ==============================================================

    def configure(self, host: str, port: int = 502, unit_id: int = 1) -> bool:
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
        self._connected = self.modbus.is_connected()
        if not self._connected:
            return
        self.write_count = 0
        self.update_timer.start(max(10, int(self.write_interval * 1000)))
        self.connection_status.emit(True)

    def disconnect(self) -> None:
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

    # ==============================================================
    # Цикл обмена
    # ==============================================================

    def update_device_data(self) -> None:
        """Один цикл: пишем DO, читаем AI и DI (в отдельном потоке)."""
        if not self._connected or not self._is_configured:
            return
        task = Runnable(self._exchange)
        task.signals.error.connect(
            lambda e: self.error_occurred.emit(f"Ошибка обмена E1242: {e}")
        )
        self.thread_pool.start(task)

    def _exchange(self) -> None:
        """Выполняется в рабочем потоке."""
        # --- 1. Запись DO (только если генерация активна) ---
        if self._output_enabled:
            do_bits = self._collect_do_bits()
            try:
                ok = self.modbus.write_multiple_coils(self.DO_START, do_bits)
            except Exception as e:
                self.error_occurred.emit(f"Ошибка записи DO E1242: {e}")
                ok = False
            if ok:
                self.write_count += 1
                if self.debug and self.write_count % 10 == 0:
                    self.debug_data.emit(
                        {
                            "write_count": self.write_count,
                            "registers": do_bits,
                            "timestamp": time.time(),
                        }
                    )
                self.write_completed.emit(True)
            else:
                self.write_completed.emit(False)

        # --- 2. Чтение AI raw ---
        try:
            raw = self.modbus.read_input(self.AI_RAW_START, self.AI_RAW_COUNT)
        except Exception as e:
            self.error_occurred.emit(f"Ошибка чтения AI E1242: {e}")
            raw = None
        if raw:
            for i, value in enumerate(raw):
                self._apply_ai_raw(i, value)

        # --- 3. Чтение DI ---
        try:
            di_bits = self.modbus.read_discrete_inputs(self.DI_START, self.DI_COUNT)
        except Exception as e:
            self.error_occurred.emit(f"Ошибка чтения DI E1242: {e}")
            di_bits = None
        if di_bits:
            self.data_updated.emit({"di": list(di_bits)})

    def _collect_do_bits(self) -> List[bool]:
        """4 дискретных канала генератора -> 4 bool для write_multiple_coils."""
        discrete = [
            ch for ch in self.generator.channels if ch.signal_type.is_discrete()
        ]
        bits: List[bool] = []
        for i in range(self.DO_COUNT):
            if i < len(discrete):
                bits.append(bool(discrete[i].current_value >= 0.5))
            else:
                bits.append(False)
        return bits

    def _apply_ai_raw(self, index: int, raw_value: int) -> None:
        """Сырое значение 0..65535 -> 0..100 % и записать в аналоговый канал."""
        analog = [
            ch for ch in self.generator.channels if ch.signal_type.is_analog()
        ]
        if index >= len(analog):
            return
        percent = max(0.0, min(100.0, raw_value / self.AI_RAW_MAX * 100.0))
        analog[index].current_value = percent

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
                "start": self.AI_RAW_START,
                "end": self.AI_RAW_START + self.AI_RAW_COUNT - 1,
                "description": "AI, сырые значения (UINT16, 0..65535)",
                "channels": [f"AI-{i:02d}" for i in range(self.AI_RAW_COUNT)],
            },
            "di": {
                "start": self.DI_START,
                "end": self.DI_START + self.DI_COUNT - 1,
                "description": "DI, дискретные входы (биты)",
            },
            "do": {
                "start": self.DO_START,
                "end": self.DO_START + self.DO_COUNT - 1,
                "description": "DO, дискретные выходы (биты)",
            },
        }

    # ==============================================================
    # Чтение регистров (используется PLCRegisterView)
    # ==============================================================

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