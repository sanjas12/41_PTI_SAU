"""Локальный Modbus TCP стенд: четыре AI raw, DI и DO E1242."""

from typing import List

from pyModbusTCP.server import DataBank, ModbusServer


class MoxaE1242Simulator:
    """Локальный Modbus TCP стенд: четыре AI raw, DI и DO E1242."""

    HOST = "127.0.0.1"

    # Реальные адреса E1242 (Default Modbus address)
    DI_START = 0
    DI_COUNT = 4
    DO_START = 0
    DO_COUNT = 4
    AI_RAW_START = 1298           # ← ИСПРАВЛЕНО: было 0
    AI_RAW_COUNT = 4

    def __init__(self, port: int = 1502) -> None:
        self.data = DataBank(
            coils_size=8,              # DO: 0..7 + запас
            d_inputs_size=8,           # DI: 0..7
            h_regs_size=0,
            i_regs_size=1400,          # AI raw: 1298..1301 → нужно 1302
        )
        # AI по умолчанию — на реальных адресах
        self.data.set_input_registers(
            self.AI_RAW_START, [0, 16384, 32768, 65535]
        )
        self.server = ModbusServer(
            host=self.HOST, port=port, no_block=True, data_bank=self.data
        )

    def set_ai(self, index: int, value: int) -> None:
        if not 0 <= index < self.AI_RAW_COUNT or not 0 <= value <= 65535:
            raise ValueError("AI должен иметь индекс 0–3 и значение 0–65535")
        self.data.set_input_registers(self.AI_RAW_START + index, [value])

    def set_di(self, index: int, value: bool) -> None:
        if not 0 <= index < self.DI_COUNT:
            raise ValueError("Индекс DI должен быть 0–3")
        self.data.set_discrete_inputs(self.DI_START + index, [value])

    def get_do(self) -> List[bool]:
        return self.data.get_coils(self.DO_START, self.DO_COUNT) or [False] * 4