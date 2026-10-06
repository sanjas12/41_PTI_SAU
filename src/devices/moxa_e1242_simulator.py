"""Локальный Modbus TCP стенд: четыре AI raw, DI и DO E1242."""

from typing import List

from pyModbusTCP.server import DataBank, ModbusServer


class MoxaE1242Simulator:
    """Изолированная карта данных; сервер слушает только loopback.

    Эмулируется используемая приложением карта AI raw, DI и DO.
    Настройки оборудования и масштабированные REAL не эмулируются.
    """

    HOST = "127.0.0.1"

    def __init__(self, port: int = 1502) -> None:
        self.data = DataBank(
            coils_size=4, d_inputs_size=4, h_regs_size=0, i_regs_size=4
        )
        self.data.set_input_registers(0, [0, 16384, 32768, 65535])
        self.server = ModbusServer(
            host=self.HOST, port=port, no_block=True, data_bank=self.data
        )

    @property
    def is_running(self) -> bool:
        return bool(self.server.is_run)

    def start(self) -> None:
        self.server.start()

    def stop(self) -> None:
        self.server.stop()

    def set_ai(self, index: int, value: int) -> None:
        if not 0 <= index < 4 or not 0 <= value <= 65535:
            raise ValueError("AI должен иметь индекс 0–3 и значение 0–65535")
        self.data.set_input_registers(index, [value])

    def set_di(self, index: int, value: bool) -> None:
        if not 0 <= index < 4:
            raise ValueError("Индекс DI должен быть 0–3")
        self.data.set_discrete_inputs(index, [value])

    def get_do(self) -> List[bool]:
        return self.data.get_coils(0, 4) or [False] * 4
