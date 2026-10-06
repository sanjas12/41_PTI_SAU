"""Панель ручного управления локальным симулятором Moxa."""

from typing import List, Optional

from pyModbusTCP.server import ModbusServer
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from devices.moxa_e1242_simulator import MoxaE1242Simulator


class MoxaSimulatorDialog(QDialog):
    connect_requested = pyqtSignal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Симулятор Moxa ioLogik E1242")
        self.setMinimumWidth(560)
        self.simulator: Optional[MoxaE1242Simulator] = None
        self.owns_server = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        address = QHBoxLayout()
        address.addWidget(QLabel("Адрес: 127.0.0.1 · Unit ID: 1 · Порт:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(1502)
        address.addWidget(self.port_spin)
        layout.addLayout(address)
        hint = QLabel(
            "AI raw: FC04, адреса 0–3. DI: FC02, адреса 0–3. DO: FC01/FC15, адреса 0–3."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        grid = QGridLayout()
        for column, text in enumerate(
            ["Канал", "AI raw (0–65535)", "DI", "DO (от приложения)"]
        ):
            grid.addWidget(QLabel(text), 0, column)
        self.ai_spins: List[QSpinBox] = []
        self.di_checks: List[QCheckBox] = []
        self.do_checks: List[QCheckBox] = []
        for index, value in enumerate([0, 16384, 32768, 65535]):
            grid.addWidget(QLabel(str(index)), index + 1, 0)
            ai = QSpinBox()
            ai.setRange(0, 65535)
            ai.setValue(value)
            ai.valueChanged.connect(lambda value, i=index: self._set_ai(i, value))
            di = QCheckBox()
            di.toggled.connect(lambda value, i=index: self._set_di(i, value))
            output = QCheckBox()
            output.setEnabled(False)
            self.ai_spins.append(ai)
            self.di_checks.append(di)
            self.do_checks.append(output)
            grid.addWidget(ai, index + 1, 1)
            grid.addWidget(di, index + 1, 2)
            grid.addWidget(output, index + 1, 3)
        layout.addLayout(grid)
        self.status = QLabel("Сервер остановлен")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.start_btn = QPushButton("Запустить сервер")
        self.stop_btn = QPushButton("Остановить сервер")
        self.connect_btn = QPushButton("Подключить приложение")
        self.stop_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)
        self.connect_btn.clicked.connect(self._request_connection)
        for button in [self.start_btn, self.stop_btn, self.connect_btn]:
            actions.addWidget(button)
        layout.addLayout(actions)
        close = QPushButton("Закрыть")
        close.clicked.connect(self.close)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(close)
        layout.addLayout(footer)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.refresh_outputs)

    def start_server(self) -> None:
        if self.simulator is not None:
            return
        simulator = MoxaE1242Simulator(self.port_spin.value())
        for index in range(4):
            simulator.set_ai(index, self.ai_spins[index].value())
            simulator.set_di(index, self.di_checks[index].isChecked())
        try:
            simulator.start()
        except (OSError, ModbusServer.Error) as exc:
            self.status.setText(f"Не удалось запустить сервер: {exc}")
            return
        self.simulator = simulator
        self.port_spin.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.connect_btn.setEnabled(True)
        self.status.setText(f"Сервер запущен: 127.0.0.1:{self.port_spin.value()}")
        self.timer.start()

    def stop_server(self) -> None:
        self.timer.stop()
        if self.simulator is not None:
            if self.owns_server:
                self.simulator.stop()
            self.simulator = None
        self.owns_server = True
        self.port_spin.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        self.status.setText("Сервер остановлен")
        for output in self.do_checks:
            output.setChecked(False)

    def _set_ai(self, index: int, value: int) -> None:
        if self.simulator is not None:
            self.simulator.set_ai(index, value)

    def attach_simulator(self, simulator: MoxaE1242Simulator) -> None:
        if self.simulator is simulator:
            return
        self.stop_server()
        self.simulator = simulator
        self.owns_server = False
        self.port_spin.setValue(simulator.server.port)
        self.port_spin.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        values = simulator.data.get_input_registers(0, 4) or [0] * 4
        inputs = simulator.data.get_discrete_inputs(0, 4) or [False] * 4
        for index in range(4):
            self.ai_spins[index].setValue(values[index])
            self.di_checks[index].setChecked(inputs[index])
        self.status.setText("Симулятор подключён; отключение через меню «Подключение»")
        self.timer.start()

    def _set_di(self, index: int, value: bool) -> None:
        if self.simulator is not None:
            self.simulator.set_di(index, value)

    def refresh_outputs(self) -> None:
        if self.simulator is not None:
            for check, value in zip(self.do_checks, self.simulator.get_do()):
                check.setChecked(value)

    def _request_connection(self) -> None:
        if self.simulator is not None:
            self.connect_requested.emit(
                {
                    "device_type": "moxa_e1242_simulator",
                    "host": "127.0.0.1",
                    "port": self.port_spin.value(),
                    "unit_id": 1,
                }
            )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.stop_server()
        super().closeEvent(event)

    def done(self, result: int) -> None:
        self.stop_server()
        super().done(result)
