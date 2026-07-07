import sys
import os
from PyQt5.QtWidgets import QApplication
import logging
import os
import sys
import time
import traceback
from typing import Any, Dict

import config.config as cfg
from _version import __full_version__
from ui.main_window import MainWindow
from ui.styles import app_stylesheet


logger = logging.getLogger(__name__)


# Перехват необработанных исключений
def excepthook(exc_type, exc_value, exc_tb):
    """Перехват исключений, не пойманных try-except."""
    # KeyboardInterrupt не считаем крашем
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    error_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    # Пишем в тот же каталог, что и основной лог
    log_dir = os.path.dirname(os.path.abspath(cfg.LOG_FILE))
    crash_path = os.path.join(log_dir, "crash.log")

    try:
        with open(crash_path, "w", encoding="utf-8") as f:
            f.write(error_text)
    except OSError:
        pass  # если не можем записать — не падаем повторно

    # Логируем через стандартный логгер (попадёт в основной лог)
    logger.critical("Необработанное исключение:\n%s", error_text)

    # Показываем пользователю — только если есть QApplication
    app = QApplication.instance()
    if app is not None:
        QMessageBox.critical(
            None,
            "Критическая ошибка",
            f"Приложение завершилось с ошибкой.\n\nПодробности: {crash_path}",
        )
    else:
        print(error_text, file=sys.stderr)

    sys.exit(1)


sys.excepthook = excepthook


def setup_logging() -> None:
    """Настраиваем систему логирования."""
    kwargs: Dict[str, Any] = {
        "filename": cfg.LOG_FILE,
        "level": cfg.LEVEL_LOG,
        "format": cfg.FORMAT,
        "filemode": "a",
    }
    if sys.version_info >= (3, 9):
        kwargs["encoding"] = "utf-8"

    logging.basicConfig(**kwargs)


def log_startup_begin() -> None:
    """Отбивка старта — что запустилось, в каком окружении."""
    sep = "=" * 55
    logger.info(sep)
    logger.info(f"{__full_version__} — запуск")
    logger.info(sep)
    logger.info("PID:        %d", os.getpid())
    logger.info("Python:     %s", sys.version.split()[0])
    logger.info("Платформа:  %s", sys.platform)
    logger.info("Лог-файл:   %s", os.path.abspath(cfg.LOG_FILE))
    logger.info("Уровень лога: %s", logging.getLevelName(cfg.LEVEL_LOG))


def log_startup_done(elapsed: float) -> None:
    sep = "=" * 55
    logger.info(sep)
    logger.info("  Приложение запущено  (%.2f с)", elapsed)
    logger.info(sep)

def main():

    setup_logging()

    log_startup_begin()

    cfg.load_runtime_settings()

    exit_code = 0
    t0 = time.monotonic()

    try:
        app = QApplication(sys.argv)
        app.setStyleSheet(app_stylesheet())
    
        # Создаем главное окно
        window = MainWindow()
        window.show()

        log_startup_done(time.monotonic() - t0)
    
        exit_code = app.exec_()
    
    except Exception:
        exit_code = 1
        logger.critical("Критическая ошибка при запуске", exc_info=True)
        raise

    finally:
        if exit_code == 0:
            logger.info("Приложение завершено штатно (код %d)", exit_code)
        else:
            logger.warning("Приложение завершено с ошибкой (код %d)", exit_code)

    sys.exit(exit_code)

if __name__ == "__main__":
    main()