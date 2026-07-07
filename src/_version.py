from __future__ import annotations

import subprocess
from functools import lru_cache

__app_name__ = "TG-Naladka"
__version__ = "0.3.1"

GIT_REVISION_CMD: tuple[str, ...] = ("git", "rev-list", "--count", "HEAD")


def _revision_from_baked() -> str | None:
    """
    Читает ревизию из файла _revision.py, запечённого во время сборки.

    В exe-окружении файл лежит по пути doc/_revision.py → import doc._revision
    При сборке (build.py) файл кладётся в src/_revision.py → import _revision
    Возвращает None, если ни один вариант не найден (режим разработки без сборки).
    """
    # Вариант 1: exe-окружение — doc/_revision.py
    try:
        from doc._revision import __revision__  # type: ignore[import]
        return __revision__
    except ImportError:
        pass

    # Вариант 2: сборка — src/_revision.py рядом с модулями
    try:
        from _revision import __revision__  # type: ignore[import]
        return __revision__
    except ImportError:
        pass

    return None


@lru_cache(maxsize=1)
def git_revision() -> str:
    """
    Возвращает строку ревизии (например, «rev123»).

    Приоритет:
      1. Запечённый файл (doc/_revision.py или _revision.py)
      2. Живой вызов git (режим разработки)
      3. Фоллбэк «rev0»
    """
    baked = _revision_from_baked()
    if baked is not None:
        return baked

    try:
        count = subprocess.check_output(
            GIT_REVISION_CMD,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
        if not count.isdigit():
            return "rev0"
        return f"rev{count}"
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return "rev0"


__revision__ = git_revision()
__full_version__ = f"{__app_name__}-{__version__}+{__revision__}"