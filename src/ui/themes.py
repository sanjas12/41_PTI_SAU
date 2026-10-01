"""Определения светлой и тёмной промышленных тем."""

from dataclasses import dataclass
from typing import Final

import config.config as cfg


@dataclass(frozen=True)
class ThemeColors:
    """Набор цветов для одной темы."""

    # Фоны
    canvas: str          # фон окна/рабочей области
    surface: str         # фон панелей и GroupBox
    surface_alt: str     # фон карточек и вложенных блоков
    surface_raised: str  # фон приподнятых элементов (toolbar, statusbar)

    # Границы
    border: str
    border_strong: str

    # Текст
    text: str
    text_muted: str
    text_inverse: str    # текст на цветном фоне (кнопки)

    # Акценты
    primary: str         # основной акцент (синий)
    primary_hover: str
    primary_soft: str    # мягкий фон для hover

    # Статусы
    success: str
    warning: str
    danger: str
    disabled: str

    # Специальные
    toolbar_bg: str
    statusbar_bg: str
    menu_bg: str
    menu_hover: str

    # Графики
    plot_bg: str
    plot_grid: str
    plot_axis: str
    plot_text: str
    plot_legend_bg: str
    plot_legend_border: str


# ---------------------------------------------------------------
# Светлая тема
# ---------------------------------------------------------------

LIGHT_THEME: Final[ThemeColors] = ThemeColors(
    canvas="#eef1f4",
    surface="#ffffff",
    surface_alt="#f7f8fa",
    surface_raised="#e6e8eb",

    border="#c7ced6",
    border_strong="#9da8b3",

    text="#1f2933",
    text_muted="#66727d",
    text_inverse="#ffffff",

    primary="#246b8f",
    primary_hover="#1d5a78",
    primary_soft="#e5f1f7",

    success="#2f7d4a",
    warning="#a56616",
    danger="#b23a3a",
    disabled="#aab2ba",

    toolbar_bg="#e6e8eb",
    statusbar_bg="#e6e8eb",
    menu_bg="#ffffff",
    menu_hover="#e5f1f7",

    plot_bg="#ffffff",
    plot_grid="#d0d7de",
    plot_axis="#8a929b",
    plot_text="#1f2933",
    plot_legend_bg="#f7f8fa",
    plot_legend_border="#9da8b3",
)


# ---------------------------------------------------------------
# Тёмная тема
# ---------------------------------------------------------------

DARK_THEME: Final[ThemeColors] = ThemeColors(
    canvas="#1e1e1e",
    surface="#2b2b2b",
    surface_alt="#333333",
    surface_raised="#252525",

    border="#444444",
    border_strong="#5a5a5a",

    text="#e0e0e0",
    text_muted="#9aa0a6",
    text_inverse="#ffffff",

    primary="#4a9eff",
    primary_hover="#6cb1ff",
    primary_soft="#1f3a52",

    success="#4caf50",
    warning="#ff9800",
    danger="#f44336",
    disabled="#6a6a6a",

    toolbar_bg="#252525",
    statusbar_bg="#252525",
    menu_bg="#2b2b2b",
    menu_hover="#1f3a52",

    plot_bg="#101214",
    plot_grid="#2a2f35",
    plot_axis="#8a929b",
    plot_text="#c7cdd3",
    plot_legend_bg="#181b1e",
    plot_legend_border="#525a63",
)


# ---------------------------------------------------------------
# Доступ
# ---------------------------------------------------------------

_THEMES = {
    "light": LIGHT_THEME,
    "dark": DARK_THEME,
}


def get_theme(name: str) -> ThemeColors:
    """Вернуть палитру по имени темы."""
    return _THEMES.get(name, LIGHT_THEME)


# ---------------------------------------------------------------
# Генерация QSS
# ---------------------------------------------------------------

def build_stylesheet(theme_name: str, large: bool = False) -> str:
    """Сгенерировать QSS для выбранной темы и масштаба."""
    c = get_theme(theme_name)
    scale = 1.25 if large else 1.0
    base_size = cfg.FONT_SIZE * scale
    name_size = base_size + 1
    value_size = base_size + 3
    small_size = max(7, int(base_size - 1))
    pad = int(6 * scale)
    min_h = int(24 * scale)

    return f"""
        * {{
            font-family: {cfg.FONT_FAMILY};
            font-size: {base_size:.1f}pt;
            color: {c.text};
        }}

        QMainWindow, QDialog {{
            background-color: {c.canvas};
        }}

        QWidget {{
            selection-background-color: {c.primary};
            selection-color: {c.text_inverse};
        }}

        QLabel {{
            background-color: transparent;
        }}

        /* ---------- Меню ---------- */
        QMenuBar {{
            background-color: {c.menu_bg};
            border-bottom: 1px solid {c.border};
        }}
        QMenuBar::item {{
            padding: 4px 10px;
            background: transparent;
        }}
        QMenuBar::item:selected {{
            background-color: {c.menu_hover};
        }}
        QMenu {{
            background-color: {c.menu_bg};
            border: 1px solid {c.border_strong};
            padding: 4px;
        }}
        QMenu::item {{
            padding: 5px 24px 5px 20px;
        }}
        QMenu::item:selected {{
            background-color: {c.primary};
            color: {c.text_inverse};
        }}
        QMenu::separator {{
            height: 1px;
            background: {c.border};
            margin: 4px 6px;
        }}

        /* ---------- Toolbar ---------- */
        QToolBar {{
            background-color: {c.toolbar_bg};
            border-bottom: 1px solid {c.border};
            spacing: 3px;
            padding: 3px 6px;
        }}
        QToolBar::separator {{
            width: 1px;
            background: {c.border_strong};
            margin: 4px 6px;
        }}
        QToolButton {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 3px;
            padding: 4px 8px;
            min-height: {min_h}px;
            color: {c.text};
        }}
        QToolButton:hover {{
            background-color: {c.primary_soft};
            border-color: {c.primary};
        }}
        QToolButton:pressed {{
            background-color: {c.primary};
            color: {c.text_inverse};
        }}
        QToolButton:disabled {{
            color: {c.disabled};
        }}

        /* ---------- StatusBar ---------- */
        QStatusBar {{
            background-color: {c.statusbar_bg};
            border-top: 1px solid {c.border};
            padding: 0;
        }}
        QStatusBar::item {{
            border: none;
        }}

        /* ---------- GroupBox ---------- */
        QGroupBox {{
            background-color: {c.surface};
            border: 1px solid {c.border};
            border-radius: 3px;
            font-weight: 600;
            margin-top: 10px;
            padding-top: {pad}px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: {c.text};
            background-color: {c.surface};
        }}

        /* ---------- Поля ввода ---------- */
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            min-height: {min_h}px;
            padding: 2px 6px;
            background-color: {c.surface_alt};
            border: 1px solid {c.border_strong};
            border-radius: 2px;
            color: {c.text};
        }}
        QLineEdit:focus, QComboBox:focus,
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {c.primary};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {c.surface};
            color: {c.text};
            selection-background-color: {c.primary};
            selection-color: {c.text_inverse};
            border: 1px solid {c.border_strong};
        }}

        /* ---------- Кнопки ---------- */
        QPushButton {{
            min-height: {min_h}px;
            padding: 3px 10px;
            background-color: {c.surface_alt};
            border: 1px solid {c.border_strong};
            border-radius: 2px;
            color: {c.text};
        }}
        QPushButton:hover {{
            background-color: {c.primary_soft};
            border-color: {c.primary};
        }}
        QPushButton:pressed {{
            background-color: {c.primary};
            color: {c.text_inverse};
        }}
        QPushButton:disabled {{
            color: {c.disabled};
            background-color: {c.surface_raised};
            border-color: {c.border};
        }}
        QPushButton#modeButton {{
            min-width: 110px;
            border-radius: 0;
            font-weight: 600;
            color: {c.primary};
        }}
        QPushButton#modeButton:checked {{
            color: {c.text_inverse};
            background-color: {c.primary};
            border-color: {c.primary};
        }}
        QPushButton#iconButton {{
            min-width: {min_h}px;
            max-width: {min_h}px;
            min-height: {min_h}px;
            max-height: {min_h}px;
            padding: 0;
        }}

        /* ---------- Карточки каналов ---------- */
        QFrame#channelCard {{
            background-color: {c.surface_alt};
            border: 1px solid {c.border};
            border-radius: 3px;
        }}
        QFrame#channelCard:hover {{
            background-color: {c.primary_soft};
            border-color: {c.primary};
        }}
        QLabel#channelName {{
            color: {c.primary};
            font-weight: 600;
            font-size: {name_size:.1f}pt;
        }}
        QLabel#channelValue {{
            color: {c.primary};
            font-weight: 600;
            font-size: {value_size:.1f}pt;
        }}
        QLabel#channelBound, QLabel#secondaryText {{
            color: {c.text_muted};
            font-size: {small_size:.1f}pt;
        }}

        /* ---------- InfoBar ---------- */
        QFrame#infoBar {{
            background-color: {c.surface_alt};
            border: 1px solid {c.border};
            border-radius: 2px;
        }}

        /* ---------- Прокрутка ---------- */
        QScrollArea {{
            background-color: {c.canvas};
            border: none;
        }}
        QScrollBar:vertical {{
            width: 11px;
            background: {c.canvas};
        }}
        QScrollBar::handle:vertical {{
            min-height: 24px;
            background: {c.border_strong};
            border-radius: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {c.primary};
        }}
        QScrollBar:horizontal {{
            height: 11px;
            background: {c.canvas};
        }}
        QScrollBar::handle:horizontal {{
            min-width: 24px;
            background: {c.border_strong};
            border-radius: 2px;
        }}

        /* ---------- Splitter ---------- */
        QSplitter::handle {{
            background-color: {c.border};
            width: 2px;
        }}

        /* ---------- Прогресс ---------- */
        QProgressBar {{
            min-height: 16px;
            border: 1px solid {c.border};
            border-radius: 2px;
            background-color: {c.surface_alt};
            text-align: center;
            color: {c.text};
        }}
        QProgressBar::chunk {{
            background-color: {c.primary};
            border-radius: 1px;
        }}

        /* ---------- Журнал ---------- */
        QTextEdit#eventLog {{
            padding: 5px;
            background-color: {c.surface_alt};
            border: 1px solid {c.border};
            border-radius: 2px;
            color: {c.text};
        }}

        /* ---------- Подсказки ---------- */
        QToolTip {{
            color: {c.text};
            background-color: {c.surface};
            border: 1px solid {c.border_strong};
            padding: 3px;
        }}
    """