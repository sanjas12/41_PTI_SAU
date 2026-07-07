"""
Централизованное хранилище стилей Qt для всего приложения.

Использование:
    from ui.styles import app_stylesheet, MENU_BAR_STYLE
"""

import config.config as cfg


def app_stylesheet() -> str:
    """Глобальный стиль приложения (шрифт).
    Применяется один раз: app.setStyleSheet(app_stylesheet())
    """
    return f"* {{ font-size: {cfg.FONT_SIZE}pt; font-family: {cfg.FONT_FAMILY}; }}"


MENU_BAR_STYLE: str = """
    QMenuBar {
        background-color: transparent;
    }
    QMenuBar::item {
        background-color: transparent;
    }
    QMenuBar::item:selected {
        background-color: palette(highlight);
        color: palette(highlighted-text);
    }
"""
