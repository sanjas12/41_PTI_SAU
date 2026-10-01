"""Настройки пользовательского интерфейса: тема и масштаб."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Final

logger = logging.getLogger(__name__)

# Значения по умолчанию
DEFAULT_THEME: Final[str] = "light"
DEFAULT_UI_SCALE: Final[str] = "medium"

VALID_THEMES: Final[set] = {"light", "dark"}
VALID_UI_SCALES: Final[set] = {"medium", "large"}


def _get_settings_path() -> Path:
    """Путь к файлу ui_settings.json в домашней папке пользователя."""
    home_dir = Path.home()
    config_dir = home_dir / ".analog_simulator"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "ui_settings.json"


class UISettings:
    """Хранилище настроек UI (тема, масштаб) с автосохранением."""

    _instance: "UISettings | None" = None

    def __init__(self) -> None:
        self._path = _get_settings_path()
        self._data: Dict[str, Any] = {
            "theme": DEFAULT_THEME,
            "ui_scale": DEFAULT_UI_SCALE,
        }
        self._load()

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> "UISettings":
        if cls._instance is None:
            cls._instance = UISettings()
        return cls._instance

    # ------------------------------------------------------------------
    # Загрузка / сохранение
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            logger.info("ui_settings.json не найден — используются значения по умолчанию")
            self._save()
            return

        try:
            with self._path.open(encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.exception("Ошибка чтения ui_settings.json: %s", exc)
            return

        theme = loaded.get("theme", DEFAULT_THEME)
        scale = loaded.get("ui_scale", DEFAULT_UI_SCALE)
        self._data["theme"] = theme if theme in VALID_THEMES else DEFAULT_THEME
        self._data["ui_scale"] = scale if scale in VALID_UI_SCALES else DEFAULT_UI_SCALE

    def _save(self) -> None:
        try:
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.exception("Ошибка сохранения ui_settings.json: %s", exc)

    # ------------------------------------------------------------------
    # Свойства
    # ------------------------------------------------------------------

    @property
    def theme(self) -> str:
        return self._data["theme"]

    @theme.setter
    def theme(self, value: str) -> None:
        if value not in VALID_THEMES:
            logger.warning("Неизвестная тема: %s", value)
            return
        self._data["theme"] = value
        self._save()

    @property
    def ui_scale(self) -> str:
        return self._data["ui_scale"]

    @ui_scale.setter
    def ui_scale(self, value: str) -> None:
        if value not in VALID_UI_SCALES:
            logger.warning("Неизвестный масштаб UI: %s", value)
            return
        self._data["ui_scale"] = value
        self._save()

    # ------------------------------------------------------------------
    # Хелперы
    # ------------------------------------------------------------------

    def is_dark(self) -> bool:
        return self.theme == "dark"

    def is_large(self) -> bool:
        return self.ui_scale == "large"

    def scale_factor(self) -> float:
        """Коэффициент масштаба для шрифтов и отступов."""
        return 1.25 if self.is_large() else 1.0