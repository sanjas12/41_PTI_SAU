import json
import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Final

logger = logging.getLogger(__name__)


class AxeName(Enum):
    """Названия осей графика."""

    LIST_SIGNALS = "Список сигналов"
    BASE_AXE = "Основная Ось"
    SECONDARY_AXE = "Вспомогательная Ось"
    TIME_AXE = "Ось Времени"


def get_base_path() -> Path:
    """
    Возвращает корень проекта (где лежит pyproject.toml или Readme.md)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent

    current = Path(__file__).resolve()

    for parent in current.parents:
        if (parent / "pyproject.toml").exists() or (parent / "Readme.md").exists():
            return parent

    return current.parent.parent


# --- Пути ---
BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
ROOT_DIR: Final[Path] = get_base_path()

CONFIG_DIR: Final[Path] = BASE_DIR / "config"

LOGS_DIR: Final[Path] = ROOT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

REPORT_DIR: Final[Path] = ROOT_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

LOG_FILE: Final[Path] = LOGS_DIR / "app.log"

PLOT_FILENAME: Final[Path] = REPORT_DIR / "plot.png"
PDF_FILENAME: Final[Path] = REPORT_DIR / "regulator_analysis.pdf"


# --- Константы ---
FORMAT: Final[str] = "%(asctime)s:%(levelname)s:%(name)s:%(message)s"

COMBINED_TIME: Final[str] = "Время"
DEFAULT_TIME: Final[str] = "дата/время"
DEFAULT_MS: Final[str] = "миллисекунды"


# --- Настройки ---
_SETTINGS_FILE: Final[Path] = ROOT_DIR / "settings.json"

_DEFAULTS: Final[Dict[str, Any]] = {
    "FONT_SIZE": 8,
    "FONT_FAMILY": "Arial",
    "TICK_MARK_COUNT_X": 15,
    "TICK_MARK_COUNT_Y": 10,
    "LEVEL_LOG": "INFO",
    "ANALYS_AIM": "Значение развертки. Положение ГСМ",
    "GSM_A_CUR": "ГСМ-А.Текущее положение",
    "GSM_B_CUR": "ГСМ-Б.Текущее положение",
}


_SETTINGS: Dict[str, Any] = {}


def _save_settings(data: Dict[str, Any]) -> None:
    """Сохраняет настройки в JSON-файл."""
    with _SETTINGS_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def _load_settings() -> Dict[str, Any]:
    """Загружает настройки с диска или создаёт дефолтные."""

    if not _SETTINGS_FILE.exists():
        logger.warning(
            "settings.json не найден, создаётся файл с настройками по умолчанию"
        )

        _save_settings(_DEFAULTS)

        logger.info("Создан новый settings.json")

        return _DEFAULTS.copy()

    try:
        with _SETTINGS_FILE.open(encoding="utf-8") as file:
            user_settings: Dict[str, Any] = json.load(file)

        logger.info(
            "settings.json успешно прочитан (%d параметров)",
            len(user_settings),
        )

    except json.JSONDecodeError:
        logger.exception("Ошибка парсинга settings.json (некорректный JSON)")
        logger.warning("Используются настройки по умолчанию")
        return _DEFAULTS.copy()

    except OSError:
        logger.exception("Ошибка чтения settings.json с диска")
        logger.warning("Используются настройки по умолчанию")
        return _DEFAULTS.copy()

    return {**_DEFAULTS, **user_settings}


def load_runtime_settings() -> None:
    """
    Вызывается ИЗ main после setup_logging().
    Безопасная инициализация логируемого конфига.
    """
    global _SETTINGS

    logger.info("Загрузка settings.json: %s", _SETTINGS_FILE)

    try:
        _SETTINGS = _load_settings()
    except Exception:
        logger.exception("Ошибка загрузки settings.json, используются дефолты")
        _SETTINGS = _DEFAULTS.copy()
        return

    overridden = [
        k for k in _SETTINGS if k in _DEFAULTS and _SETTINGS[k] != _DEFAULTS[k]
    ]

    if overridden:
        logger.info("Переопределены настройки: %s", ", ".join(overridden))


# --- Публичные значения (после load_runtime_settings) ---
def _get(key: str, default: Any) -> Any:
    return _SETTINGS.get(key, default)


FONT_SIZE: int = _get("FONT_SIZE", 8)

FONT_FAMILY: str = _get("FONT_FAMILY", "Arial")

TICK_MARK_COUNT_X: int = _get("TICK_MARK_COUNT_X", 15)

TICK_MARK_COUNT_Y: int = _get("TICK_MARK_COUNT_Y", 10)

LEVEL_LOG: int = getattr(
    logging,
    str(_get("LEVEL_LOG", "INFO")).upper(),
    logging.INFO,
)

ANALYS_AIM: str = _get(
    "ANALYS_AIM",
    "Значение развертки. Положение ГСМ",
)

GSM_A_CUR: str = _get("GSM_A_CUR", "ГСМ-А.Текущее положение")

GSM_B_CUR: str = _get("GSM_B_CUR", "ГСМ-Б.Текущее положение")
