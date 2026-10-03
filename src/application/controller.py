"""Управление ручной генерацией и её согласование с режимом сценария."""

from typing import Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from devices.device_manager import DeviceManager


class ApplicationController(QObject):
    """Хранит состояние генерации; UI отвечает за отображение и выбор панели.

    Движок сценария пока остаётся отдельным владельцем его состояния.
    Контроллер получает режим сценария при синхронизации, сохраняя
    существующий интервал генерации 10 мс и правила разрешения выходов.
    """

    state_changed = pyqtSignal()
    validation_failed = pyqtSignal(str)
    log_signal = pyqtSignal(str, str)

    def __init__(
        self, devices: DeviceManager, parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.devices = devices
        self.timer = QTimer(self)
        self._is_running = False
        self._is_paused = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def start_generation(self) -> None:
        if self._is_running:
            return
        interface = self.devices.active_interface
        if interface.is_connected():
            errors = interface.validate_manual_output_map()
            if errors:
                message = "Нельзя запустить ручной режим:\n• " + "\n• ".join(errors)
                self.log_signal.emit(message.replace("\n• ", "; "), "error")
                self.validation_failed.emit(message)
                return
        self._is_running = True
        self._is_paused = False
        self.state_changed.emit()

    def stop_generation(self) -> None:
        if not self._is_running:
            return
        self._is_running = False
        self._is_paused = False
        self.state_changed.emit()

    def pause_generation(self) -> None:
        if not self._is_running or self._is_paused:
            return
        self._is_paused = True
        self.state_changed.emit()

    def resume_generation(self) -> None:
        if not self._is_running or not self._is_paused:
            return
        self._is_paused = False
        self.state_changed.emit()

    def synchronize(self, scenario_view: bool, engine_mode: str) -> bool:
        """Согласовать таймер и выходы; вернуть состояние сбора для графиков."""
        manual_running = not scenario_view and self._is_running and not self._is_paused
        should_run = manual_running or engine_mode == "scenario"
        if should_run and not self.timer.isActive():
            self.timer.start(10)
        elif not should_run and self.timer.isActive():
            self.timer.stop()
        interface = self.devices.active_interface
        if hasattr(interface, "set_output_enabled"):
            interface.set_output_enabled(should_run)
        return should_run

    def close(self) -> None:
        """Остановить таймер перед закрытием интерфейсов оборудования."""
        self.timer.stop()
