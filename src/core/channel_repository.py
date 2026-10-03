"""Хранение настроек каналов без зависимости от интерфейса Qt."""

import json
import os
from typing import Any, Dict, Iterable

from core.channel import AnalogChannel


class ChannelRepository:
    """Чтение и запись существующего формата channels_config.json.

    Отсутствующий файл означает настройки по умолчанию. Ошибки чтения,
    формата и записи передаются вызывающему слою для отображения или журнала.
    """

    def __init__(self, path: str) -> None:
        self.path = path

    @staticmethod
    def default_path(filename: str = "channels_config.json") -> str:
        directory = os.path.join(os.path.expanduser("~"), ".analog_simulator")
        os.makedirs(directory, exist_ok=True)
        return os.path.join(directory, filename)

    def load(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(self.path, encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict) or any(
            not isinstance(value, dict) for value in data.values()
        ):
            raise ValueError("Конфигурация каналов должна содержать объекты настроек")
        return data

    def save(self, channels: Iterable[AnalogChannel]) -> None:
        config = {}
        for channel in channels:
            settings = channel.to_dict()
            settings.pop("id")
            config[str(channel.id)] = settings
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=2)
