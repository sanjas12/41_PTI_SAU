from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


class SignalHistory:
    """Хранилище полной истории значений всех каналов.

    История начинается с момента создания объекта и не ограничивается
    по времени. Отображаемый диапазон выбирается отдельно в PlotWindow.
    """

    def __init__(self, channel_ids: Optional[Sequence[int]] = None):
        self._times: List[float] = []
        self._values: Dict[int, List[float]] = {}

        if channel_ids is not None:
            for channel_id in channel_ids:
                self._values[channel_id] = []

    def add_sample(
        self,
        timestamp: float,
        values: Dict[int, float],
    ) -> None:
        """Добавить один синхронный отсчёт."""

        self._times.append(float(timestamp))

        # Добавляем значения существующим каналам.
        for channel_id in self._values:
            self._values[channel_id].append(float(values.get(channel_id, np.nan)))

        # Если появился новый канал — создаём для него историю.
        for channel_id, value in values.items():
            if channel_id not in self._values:
                self._values[channel_id] = [np.nan] * (len(self._times) - 1)

                self._values[channel_id].append(float(value))

    def add_channels_sample(
        self,
        timestamp: float,
        channels,
    ) -> None:
        """Добавить отсчёт непосредственно из списка AnalogChannel."""

        values = {channel.id: channel.current_value for channel in channels}

        self.add_sample(timestamp, values)

    def clear(self) -> None:
        """Очистить всю историю."""

        self._times.clear()

        for values in self._values.values():
            values.clear()

    def sample_count(self) -> int:
        return len(self._times)

    def duration(self) -> float:
        """Длительность записанной истории в секундах."""

        if len(self._times) < 2:
            return 0.0

        return self._times[-1] - self._times[0]

    def get_times(self) -> np.ndarray:
        return np.asarray(self._times, dtype=float)

    def get_channel(self, channel_id: int) -> np.ndarray:
        values = self._values.get(channel_id)

        if values is None:
            return np.asarray([], dtype=float)

        return np.asarray(values, dtype=float)

    def get_data(
        self,
        channel_ids: Sequence[int],
    ) -> Tuple[np.ndarray, Dict[int, np.ndarray]]:
        """Получить временную шкалу и данные выбранных каналов."""

        times = self.get_times()

        values = {
            channel_id: self.get_channel(channel_id) for channel_id in channel_ids
        }

        return times, values

    def get_latest_time(self) -> float:
        if not self._times:
            return 0.0

        return self._times[-1]

    def get_time_range(self) -> Tuple[float, float]:
        if not self._times:
            return 0.0, 0.0

        return self._times[0], self._times[-1]

    def get_value_at_time(
        self,
        channel_id: int,
        timestamp: float,
    ) -> Optional[float]:
        """Получить значение канала, ближайшее к указанному времени."""

        times = self.get_times()
        values = self.get_channel(channel_id)

        if len(times) == 0 or len(values) == 0:
            return None

        index = int(np.searchsorted(times, timestamp))

        if index <= 0:
            index = 0
        elif index >= len(times):
            index = len(times) - 1
        else:
            # Выбираем ближайшую точку.
            left = index - 1
            right = index

            if abs(times[left] - timestamp) <= abs(times[right] - timestamp):
                index = left

        value = values[index]

        if np.isnan(value):
            return None

        return float(value)
